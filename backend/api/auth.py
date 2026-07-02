"""Auth API endpoints: register, login, refresh, me, Google OAuth."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.session import get_session
from backend.db.models import User
from backend.db.schemas import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
)
from backend.auth.jwt import (
    create_access_token,
    create_refresh_token,
    get_token_subject,
)
from backend.auth.password import hash_password, verify_password
from backend.auth.oauth import get_google_auth_url, exchange_google_code, get_google_userinfo
from backend.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    """Register a new user account."""
    result = await session.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        name=body.name,
    )
    session.add(user)
    await session.flush()

    return TokenResponse(
        access_token=create_access_token(user.id, {"name": user.name}),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    """Authenticate with email and password."""
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return TokenResponse(
        access_token=create_access_token(user.id, {"name": user.name}),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(refresh_token: str, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    """Exchange a refresh token for a new access + refresh token pair."""
    user_id = get_token_subject(refresh_token, expected_type="refresh")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return TokenResponse(
        access_token=create_access_token(user.id, {"name": user.name}),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Get the current authenticated user's profile."""
    return UserResponse.model_validate(current_user)


@router.get("/google")
async def google_login():
    """Redirect to Google OAuth consent screen."""
    return {"url": get_google_auth_url()}


@router.get("/google/callback", response_model=TokenResponse)
async def google_callback(code: str, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    """Handle Google OAuth callback and return JWT tokens."""
    tokens = await exchange_google_code(code)
    if not tokens:
        raise HTTPException(status_code=400, detail="Failed to exchange Google code")

    userinfo = await get_google_userinfo(tokens.get("access_token", ""))
    if not userinfo:
        raise HTTPException(status_code=400, detail="Failed to get Google user info")

    google_id = userinfo.get("id")
    email = userinfo.get("email", "")
    name = userinfo.get("name", "")

    result = await session.execute(
        select(User).where((User.google_id == google_id) | (User.email == email))
    )
    user = result.scalar_one_or_none()

    if user:
        if not user.google_id:
            user.google_id = google_id
        if not user.name:
            user.name = name
        user.avatar_url = userinfo.get("picture", user.avatar_url)
    else:
        user = User(
            email=email,
            google_id=google_id,
            name=name,
            avatar_url=userinfo.get("picture"),
        )
        session.add(user)

    await session.flush()

    return TokenResponse(
        access_token=create_access_token(user.id, {"name": user.name}),
        refresh_token=create_refresh_token(user.id),
    )
