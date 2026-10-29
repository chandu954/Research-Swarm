"""Auth API endpoints with multi-provider support.

Supports: email/password, magic links, MFA, session management, trusted devices.

Google OAuth routes live in backend/api/auth_oauth.py.
Magic link, password reset, and MFA routes live in backend/api/auth_mfa.py.
Both sub-routers are included below.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user
from backend.auth.jwt import (
    create_access_token,
    create_refresh_token,
    get_token_subject,
)
from backend.auth.password import hash_password, verify_password
from backend.core.ratelimit import limiter
from backend.db.models import (
    Organization,
    OrganizationMember,
    Project,
    User,
    UserDevice,
    UserSession,
    Workspace,
    WorkspaceMember,
)
from backend.db.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from backend.db.session import get_session

router = APIRouter(prefix="/auth", tags=["auth"])


async def _build_tokens(
    user: User, refresh_token: Optional[str] = None
) -> TokenResponse:
    """Build JWT tokens and bridge the user's identity to Supabase.

    The Supabase identity is provisioned in the background so RLS, realtime
    and storage have an `auth.uid()` for this user — without a re-login.
    Persistence failures never break the primary JWT auth flow.

    `refresh_token` is the newly rotated refresh token when this is called
    from the refresh flow (the session row already stores its hash).
    """
    tokens = TokenResponse(
        access_token=create_access_token(user.id, {"name": user.name}),
        refresh_token=refresh_token or create_refresh_token(user.id),
    )
    try:
        from backend.core.supabase import (
            create_browser_session,
            ensure_supabase_user,
            upsert_profile,
        )

        sb_user = ensure_supabase_user(
            email=user.email,
            legacy_user_id=str(user.id),
            user_metadata={
                "name": user.name,
                "avatar_url": user.avatar_url or "",
            },
        )
        upsert_profile(
            supabase_user_id=sb_user["id"],
            legacy_user_id=str(user.id),
            email=user.email,
            name=user.name,
            avatar_url=user.avatar_url,
        )
        session = create_browser_session(user.email, str(user.id))
        if session and session["access_token"]:
            tokens.supabase_access_token = session["access_token"]
            tokens.supabase_refresh_token = session["refresh_token"]
    except Exception as exc:  # pragma: no cover - resilience path
        logger.warning(f"Supabase bridge skipped for {user.email}: {exc}")
    return tokens


async def _create_session(user: User, request: Request, session: AsyncSession) -> str:
    """Create a refresh-token session. Returns the raw refresh token (caller sets it as a cookie)."""
    from backend.auth.jwt import REFRESH_TOKEN_EXPIRE_DAYS

    refresh_token_value = create_refresh_token(user.id)
    token_hash = hashlib.sha256(refresh_token_value.encode()).hexdigest()
    user_session = UserSession(
        user_id=user.id,
        refresh_token_hash=token_hash,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        last_used_at=datetime.now(timezone.utc),
    )
    session.add(user_session)
    return refresh_token_value


async def _create_default_organization(db_session: AsyncSession, user: User) -> None:
    org = Organization(
        name=f"{user.name}'s Organization",
        slug=f"{user.email.split('@')[0].lower()}-{uuid.uuid4().hex[:8]}",
        owner_id=user.id,
    )
    db_session.add(org)
    await db_session.flush()
    db_session.add(
        OrganizationMember(organization_id=org.id, user_id=user.id, role="owner")
    )
    ws = Workspace(
        name="General", slug="general", organization_id=org.id, owner_id=user.id
    )
    db_session.add(ws)
    await db_session.flush()
    db_session.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))
    db_session.add(
        Project(
            name="Default Project",
            slug="default",
            organization_id=org.id,
            workspace_id=ws.id,
            owner_id=user.id,
        )
    )
    await db_session.flush()


async def _find_or_create_user(
    email: str, name: str, provider_data: dict, provider: str, db_session: AsyncSession
) -> User:
    filters = [User.email == email]
    if provider_id := provider_data.get("id"):
        filters.append(getattr(User, f"{provider}_id") == provider_id)

    result = await db_session.execute(select(User).where(filters[0]))
    user = result.scalar_one_or_none()

    if not user and provider_id:
        result = await db_session.execute(
            select(User).where(getattr(User, f"{provider}_id") == provider_id)
        )
        user = result.scalar_one_or_none()

    if user:
        if provider_id and not getattr(user, f"{provider}_id"):
            setattr(user, f"{provider}_id", provider_id)
        if not user.name:
            user.name = name
        if provider_data.get("avatar_url") or provider_data.get("picture"):
            user.avatar_url = provider_data.get("avatar_url") or provider_data.get(
                "picture"
            )
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
@limiter.limit("5/minute")
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
    refresh_token = await _create_session(user, request, session)

    return await _build_tokens(user, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
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
    refresh_token = await _create_session(user, request, session)

    return await _build_tokens(user, refresh_token=refresh_token)


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(
    body: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    user_id = get_token_subject(body.refresh_token, expected_type="refresh")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()
    now = datetime.now(timezone.utc)

    result = await session.execute(
        select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.refresh_token_hash == token_hash,
        )
    )
    user_session = result.scalar_one_or_none()

    if not user_session or not user_session.is_active:
        logger.warning(
            f"Refresh token reuse or revoked session for user={user_id}; revoking all sessions"
        )
        stale = await session.execute(
            select(UserSession).where(
                UserSession.user_id == user_id, UserSession.is_active
            )
        )
        for stale_session in stale.scalars().all():
            stale_session.is_active = False
        await session.commit()
        raise HTTPException(
            status_code=401, detail="Session revoked; please log in again"
        )

    if user_session.expires_at.tzinfo is None:
        user_session.expires_at = user_session.expires_at.replace(tzinfo=timezone.utc)
    if user_session.expires_at < now:
        user_session.is_active = False
        await session.commit()
        raise HTTPException(
            status_code=401, detail="Session expired; please log in again"
        )

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    new_refresh_token = create_refresh_token(user.id)
    user_session.refresh_token_hash = hashlib.sha256(
        new_refresh_token.encode()
    ).hexdigest()
    user_session.last_used_at = now
    await session.flush()

    return await _build_tokens(user, refresh_token=new_refresh_token)


class LogoutRequest(BaseModel):
    refresh_token: str


@router.post("/logout")
async def logout(
    body: LogoutRequest,
    session: AsyncSession = Depends(get_session),
):
    """Revoke the session that owns the presented refresh token."""
    user_id = get_token_subject(body.refresh_token, expected_type="refresh")
    if user_id:
        token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()
        result = await session.execute(
            select(UserSession).where(
                UserSession.user_id == user_id,
                UserSession.refresh_token_hash == token_hash,
                UserSession.is_active,
            )
        )
        user_session = result.scalar_one_or_none()
        if user_session:
            user_session.is_active = False
            await session.flush()
    return {"status": "logged_out"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.get("/org-status")
async def get_org_status(
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_session),
):
    result = await db_session.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == current_user.id
        ).limit(1)
    )
    member = result.scalar_one_or_none()
    return {"has_organization": member is not None}


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
        select(UserSession)
        .where(
            UserSession.user_id == current_user.id,
            UserSession.is_active,
        )
        .order_by(UserSession.last_used_at.desc().nullslast())
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


# Include sub-module routers (imported after all definitions to avoid circular imports).
from backend.api.auth_oauth import (  # noqa: E402, F401
    router as oauth_router,
    _oauth_callback_html,
    exchange_google_code,
    get_google_userinfo,
)  # noqa: F401
from backend.api.auth_mfa import router as mfa_router  # noqa: E402

router.include_router(oauth_router)
router.include_router(mfa_router)
