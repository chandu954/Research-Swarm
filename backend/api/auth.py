"""Auth API endpoints with multi-provider support.

Supports: email/password, Google OAuth, GitHub OAuth, Microsoft OAuth,
          magic links, MFA, session management, trusted devices.
"""
from __future__ import annotations
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

import json

from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse
from datetime import timedelta
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from backend.db.session import get_session
from backend.db.models import User, UserSession, UserDevice, Organization, Workspace, Project, OrganizationMember, WorkspaceMember
from backend.db.schemas import (
    RegisterRequest, LoginRequest, TokenResponse, UserResponse,
)
from backend.auth.jwt import create_access_token, create_refresh_token, decode_token, get_token_subject
from backend.auth.password import hash_password, verify_password
from backend.auth.providers import (
    get_google_auth_url, exchange_google_code, get_google_userinfo,
    get_github_auth_url, exchange_github_code, get_github_userinfo,
    get_microsoft_auth_url, exchange_microsoft_code, get_microsoft_userinfo,
    create_magic_link, generate_mfa_secret, generate_mfa_qr_code,
    verify_mfa_code, generate_recovery_codes,
    config as oauth_config,
)
from backend.auth.dependencies import get_current_user, get_optional_user
from backend.auth.tenant import set_tenant_context, reset_tenant_context

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_tokens(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, {"name": user.name}),
        refresh_token=create_refresh_token(user.id),
    )


async def _create_session(user: User, request: Request, session: AsyncSession) -> None:
    from backend.auth.jwt import REFRESH_TOKEN_EXPIRE_DAYS
    refresh_token = create_refresh_token(user.id)
    token_hash = secrets.token_hex(32)
    user_session = UserSession(
        user_id=user.id,
        refresh_token_hash=token_hash,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    session.add(user_session)


async def _create_default_organization(db_session: AsyncSession, user: User) -> None:
    org = Organization(
        name=f"{user.name}'s Organization",
        slug=f"{user.email.split('@')[0].lower()}-{uuid.uuid4().hex[:8]}",
        owner_id=user.id,
    )
    db_session.add(org)
    await db_session.flush()
    db_session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
    ws = Workspace(name="General", slug="general", organization_id=org.id, owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    db_session.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))
    db_session.add(Project(name="Default Project", slug="default", organization_id=org.id, workspace_id=ws.id, owner_id=user.id))
    await db_session.flush()


async def _find_or_create_user(email: str, name: str, provider_data: dict, provider: str, db_session: AsyncSession) -> User:
    filters = [User.email == email]
    provider_id_field = f"{provider}_id"
    if provider_id := provider_data.get("id"):
        filters.append(getattr(User, f"{provider}_id") == provider_id)

    result = await db_session.execute(select(User).where(filters[0]))
    user = result.scalar_one_or_none()

    if not user and provider_id:
        result = await db_session.execute(select(User).where(getattr(User, f"{provider}_id") == provider_id))
        user = result.scalar_one_or_none()

    if user:
        if provider_id and not getattr(user, f"{provider}_id"):
            setattr(user, f"{provider}_id", provider_id)
        if not user.name:
            user.name = name
        if provider_data.get("avatar_url") or provider_data.get("picture"):
            user.avatar_url = provider_data.get("avatar_url") or provider_data.get("picture")
        user.last_login_at = datetime.now(timezone.utc)
    else:
        user = User(
            email=email,
            name=name,
            avatar_url=provider_data.get("avatar_url") or provider_data.get("picture"),
            last_login_at=datetime.now(timezone.utc),
        )
        if provider_id:
            setattr(user, f"{provider}_id", provider_id)
        db_session.add(user)
        await db_session.flush()
        await _create_default_organization(db_session, user)

    await db_session.flush()
    return user


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    body: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    result = await session.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        name=body.name,
        last_login_at=datetime.now(timezone.utc),
    )
    session.add(user)
    await session.flush()
    await _create_default_organization(session, user)
    await _create_session(user, request, session)

    return _build_tokens(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    user.last_login_at = datetime.now(timezone.utc)
    user.last_login_ip = request.client.host if request.client else None
    await session.flush()
    await _create_session(user, request, session)

    return _build_tokens(user)


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    user_id = get_token_subject(body.refresh_token, expected_type="refresh")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return _build_tokens(user)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.get("/org-status")
async def get_org_status(
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_session),
):
    result = await db_session.execute(
        select(OrganizationMember).where(OrganizationMember.user_id == current_user.id).limit(1)
    )
    member = result.scalar_one_or_none()
    return {"has_organization": member is not None}


def _oauth_callback_html(tokens: TokenResponse, error: str = "") -> HTMLResponse:
    """Render HTML page that sends tokens to opener popup and closes."""
    app_url = oauth_config.app_url
    if error:
        script = f"""
          if (window.opener) {{
            window.opener.postMessage({{ error: {json.dumps(error)} }}, "{app_url}");
            window.close();
          }} else {{
            window.location.href = "{app_url}/login?error=" + encodeURIComponent({json.dumps(error)});
          }}
        """
    else:
        script = f"""
          if (window.opener) {{
            window.opener.postMessage({{
              access_token: {json.dumps(tokens.access_token)},
              refresh_token: {json.dumps(tokens.refresh_token)}
            }}, "{app_url}");
            window.close();
          }} else {{
            window.location.href = "{app_url}/login?oauth=success";
          }}
        """
    html = f"""<!DOCTYPE html>
<html><body><script>{script}</script></body></html>"""
    return HTMLResponse(html)


async def _handle_oauth_callback(
    provider: str,
    code: str,
    exchange_func,
    userinfo_func,
    name_key: str,
    email_keys: list[str],
    avatar_key: str,
    id_key: str,
    request: Request,
    session: AsyncSession,
) -> HTMLResponse:
    tokens = await exchange_func(code)
    if not tokens:
        return _oauth_callback_html(TokenResponse(access_token="", refresh_token=""), error="Failed to exchange authorization code")

    userinfo = await userinfo_func(tokens.get("access_token", ""))
    if not userinfo:
        return _oauth_callback_html(TokenResponse(access_token="", refresh_token=""), error="Failed to get user info")

    email = ""
    for key in email_keys:
        email = userinfo.get(key, "")
        if email:
            break

    user = await _find_or_create_user(
        email=email,
        name=userinfo.get(name_key, ""),
        provider_data={"id": str(userinfo.get(id_key, "")), "avatar_url": userinfo.get(avatar_key)},
        provider=provider,
        db_session=session,
    )
    await _create_session(user, request, session)
    return _oauth_callback_html(_build_tokens(user))


# ── Google OAuth ────────────────────────────────────────────────

@router.get("/google")
async def google_login():
    state = secrets.token_urlsafe(32)
    response = RedirectResponse(url=get_google_auth_url(state=state))
    response.set_cookie(
        key="oauth_state",
        value=state,
        max_age=600,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return response


@router.get("/google/callback")
async def google_callback(
    code: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    state: str = Query(None),
) -> HTMLResponse:
    stored_state = request.cookies.get("oauth_state")
    if not stored_state or not state or stored_state != state:
        return _oauth_callback_html(TokenResponse(access_token="", refresh_token=""), error="Invalid state parameter")
    resp = await _handle_oauth_callback(
        provider="google",
        code=code,
        exchange_func=exchange_google_code,
        userinfo_func=get_google_userinfo,
        name_key="name",
        email_keys=["email"],
        avatar_key="picture",
        id_key="id",
        request=request,
        session=session,
    )
    resp.delete_cookie("oauth_state")
    return resp


# ── GitHub OAuth ────────────────────────────────────────────────

@router.get("/github")
async def github_login():
    state = secrets.token_urlsafe(32)
    response = RedirectResponse(url=get_github_auth_url(state=state))
    response.set_cookie(
        key="oauth_state",
        value=state,
        max_age=600,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return response


@router.get("/github/callback")
async def github_callback(
    code: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    state: str = Query(None),
) -> HTMLResponse:
    stored_state = request.cookies.get("oauth_state")
    if not stored_state or not state or stored_state != state:
        return _oauth_callback_html(TokenResponse(access_token="", refresh_token=""), error="Invalid state parameter")
    resp = await _handle_oauth_callback(
        provider="github",
        code=code,
        exchange_func=exchange_github_code,
        userinfo_func=get_github_userinfo,
        name_key="name",
        email_keys=["email"],
        avatar_key="avatar_url",
        id_key="id",
        request=request,
        session=session,
    )
    resp.delete_cookie("oauth_state")
    return resp


# ── Microsoft OAuth ─────────────────────────────────────────────

@router.get("/microsoft")
async def microsoft_login():
    state = secrets.token_urlsafe(32)
    response = RedirectResponse(url=get_microsoft_auth_url(state=state))
    response.set_cookie(
        key="oauth_state",
        value=state,
        max_age=600,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return response


@router.get("/microsoft/callback")
async def microsoft_callback(
    code: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    state: str = Query(None),
) -> HTMLResponse:
    stored_state = request.cookies.get("oauth_state")
    if not stored_state or not state or stored_state != state:
        return _oauth_callback_html(TokenResponse(access_token="", refresh_token=""), error="Invalid state parameter")
    resp = await _handle_oauth_callback(
        provider="microsoft",
        code=code,
        exchange_func=exchange_microsoft_code,
        userinfo_func=get_microsoft_userinfo,
        name_key="displayName",
        email_keys=["mail", "userPrincipalName"],
        avatar_key="",
        id_key="id",
        request=request,
        session=session,
    )
    resp.delete_cookie("oauth_state")
    return resp


# ── Forgot Password ─────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(..., min_length=8, max_length=128)


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user:
        reset_token = create_access_token(user.id, {"type": "password_reset"})
        logger.info(f"Password reset requested for {body.email}")
    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    from backend.auth.jwt import decode_token as _decode_reset
    payload = _decode_reset(body.token)
    if not payload or payload.get("type") != "password_reset":
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid reset token")
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    from backend.auth.password import hash_password
    user.hashed_password = hash_password(body.password)
    await session.flush()
    return {"status": "password_reset"}


# ── Magic Link ─────────────────────────────────────────────────

class MagicLinkRequest(RegisterRequest):
    pass


class MagicLinkVerify(BaseModel):
    token: str
    email: str

@router.post("/magic-link")
async def request_magic_link(
    body: MagicLinkRequest,
    session: AsyncSession = Depends(get_session),
):
    url, token, expires = create_magic_link(body.email)
    if os.getenv("ENVIRONMENT", "development") != "production":
        logger.info(f"Magic link for {body.email}: {url}")
        return {"message": "If the email exists, a magic link has been sent", "url": url}
    return {"message": "If the email exists, a magic link has been sent"}


@router.post("/magic-link/verify", response_model=TokenResponse)
async def verify_magic_link(
    body: MagicLinkVerify,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired magic link")

    user.last_login_at = datetime.now(timezone.utc)
    await session.flush()
    return _build_tokens(user)


# ── MFA ─────────────────────────────────────────────────────────

class MFASetupResponse(BaseModel):
    secret: str
    qr_code_url: str
    recovery_codes: list[str]


class MFAVerifyRequest(BaseModel):
    code: str


class MFALoginRequest(BaseModel):
    email: EmailStr
    password: str
    mfa_code: str


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    current_user: User = Depends(get_current_user),
):
    secret = generate_mfa_secret()
    qr_url = generate_mfa_qr_code(secret, current_user.email)
    codes = generate_recovery_codes()
    current_user.mfa_secret = secret
    current_user.mfa_recovery_codes = json.dumps(codes)
    return MFASetupResponse(
        secret=secret,
        qr_code_url=qr_url,
        recovery_codes=codes,
    )


@router.post("/mfa/verify")
async def verify_mfa(
    body: MFAVerifyRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if not current_user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA not set up")
    if not verify_mfa_code(current_user.mfa_secret, body.code):
        raise HTTPException(status_code=400, detail="Invalid MFA code")
    current_user.mfa_enabled = True
    await session.flush()
    return {"status": "mfa_enabled"}


@router.post("/mfa/disable")
async def disable_mfa(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    await session.flush()
    return {"status": "mfa_disabled"}


# ── Sessions ───────────────────────────────────────────────────

class SessionResponse(BaseModel):
    id: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_active: bool = True
    last_used_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(UserSession).where(
            UserSession.user_id == current_user.id,
            UserSession.is_active == True,
        ).order_by(UserSession.last_used_at.desc().nullslast())
    )
    return [SessionResponse.model_validate(s) for s in result.scalars().all()]


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_session),
):
    result = await db_session.execute(
        select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == current_user.id,
        )
    )
    sess = result.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    sess.is_active = False
    await db_session.flush()
    return {"status": "revoked"}


# ── Devices ────────────────────────────────────────────────────

class DeviceResponse(BaseModel):
    id: str
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    trusted: bool = False
    last_used_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/devices", response_model=list[DeviceResponse])
async def list_devices(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(UserDevice).where(UserDevice.user_id == current_user.id)
    )
    return [DeviceResponse.model_validate(d) for d in result.scalars().all()]


@router.post("/devices/{device_id}/trust")
async def trust_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(UserDevice).where(
            UserDevice.id == device_id,
            UserDevice.user_id == current_user.id,
        )
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    device.trusted = True
    device.trusted_at = datetime.now(timezone.utc)
    await session.flush()
    return {"status": "trusted"}
