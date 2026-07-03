"""Auth API endpoints with multi-provider support.

Supports: email/password, Google OAuth, GitHub OAuth, Microsoft OAuth,
          magic links, MFA, session management, trusted devices.
"""
from __future__ import annotations
import os
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from datetime import timedelta
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from backend.db.session import get_session
from backend.db.models import User, UserSession, UserDevice
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

    return _build_tokens(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    refresh_token: str,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    user_id = get_token_subject(refresh_token, expected_type="refresh")
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


# ── Google OAuth ────────────────────────────────────────────────

@router.get("/google")
async def google_login():
    return {"url": get_google_auth_url()}


@router.get("/google/callback", response_model=TokenResponse)
async def google_callback(
    code: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    tokens = await exchange_google_code(code)
    if not tokens:
        raise HTTPException(status_code=400, detail="Failed to exchange Google code")

    userinfo = await get_google_userinfo(tokens.get("access_token", ""))
    if not userinfo:
        raise HTTPException(status_code=400, detail="Failed to get Google user info")

    user = await _find_or_create_user(
        email=userinfo.get("email", ""),
        name=userinfo.get("name", ""),
        provider_data={"id": userinfo.get("id"), "avatar_url": userinfo.get("picture")},
        provider="google",
        db_session=session,
    )
    return _build_tokens(user)


# ── GitHub OAuth ────────────────────────────────────────────────

@router.get("/github")
async def github_login():
    return {"url": get_github_auth_url()}


@router.get("/github/callback", response_model=TokenResponse)
async def github_callback(
    code: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    tokens = await exchange_github_code(code)
    if not tokens:
        raise HTTPException(status_code=400, detail="Failed to exchange GitHub code")

    userinfo = await get_github_userinfo(tokens.get("access_token", ""))
    if not userinfo:
        raise HTTPException(status_code=400, detail="Failed to get GitHub user info")

    user = await _find_or_create_user(
        email=userinfo.get("email", ""),
        name=userinfo.get("name") or userinfo.get("login", ""),
        provider_data={"id": str(userinfo.get("id")), "avatar_url": userinfo.get("avatar_url")},
        provider="github",
        db_session=session,
    )
    return _build_tokens(user)


# ── Microsoft OAuth ─────────────────────────────────────────────

@router.get("/microsoft")
async def microsoft_login():
    return {"url": get_microsoft_auth_url()}


@router.get("/microsoft/callback", response_model=TokenResponse)
async def microsoft_callback(
    code: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    tokens = await exchange_microsoft_code(code)
    if not tokens:
        raise HTTPException(status_code=400, detail="Failed to exchange Microsoft code")

    userinfo = await get_microsoft_userinfo(tokens.get("access_token", ""))
    if not userinfo:
        raise HTTPException(status_code=400, detail="Failed to get Microsoft user info")

    user = await _find_or_create_user(
        email=userinfo.get("mail") or userinfo.get("userPrincipalName", ""),
        name=userinfo.get("displayName", ""),
        provider_data={"id": userinfo.get("id"), "avatar_url": None},
        provider="microsoft",
        db_session=session,
    )
    return _build_tokens(user)


# ── Forgot Password ─────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(..., min_length=8, max_length=128)


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user:
        reset_token = create_access_token(user.id, {"type": "password_reset"})
        logger.info(f"Password reset for {body.email}: token={reset_token[:20]}...")
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
