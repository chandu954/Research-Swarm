"""Magic link, password reset, and MFA endpoints.

Moved from backend/api/auth.py to keep the auth router focused on
email/password and session management.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import (
    _build_tokens,
    _create_session,
    get_current_user,
    get_session,
)
from backend.auth.password import hash_password
from backend.auth.providers import (
    create_magic_link,
    generate_mfa_qr_code,
    generate_mfa_secret,
    generate_recovery_codes,
    verify_magic_token,
    verify_mfa_code,
)
from backend.core.ratelimit import limiter
from backend.db.models import User, UserSession

router = APIRouter(tags=["auth"])


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(..., min_length=8, max_length=128)


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkVerify(BaseModel):
    token: str
    email: str


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


@router.post("/forgot-password")
@limiter.limit("5/hour")
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user:
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

    user.hashed_password = hash_password(body.password)
    await session.flush()
    result = await session.execute(
        select(UserSession).where(UserSession.user_id == user.id, UserSession.is_active)
    )
    for user_session in result.scalars().all():
        user_session.is_active = False
    await session.flush()
    return {"status": "password_reset"}


@router.post("/magic-link")
@limiter.limit("5/hour")
async def request_magic_link(
    body: MagicLinkRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    url, _token, _expires = create_magic_link(body.email)
    if os.getenv("ENVIRONMENT", "development") != "production":
        logger.info(f"Magic link for {body.email}: {url}")
        return {
            "message": "If the email exists, a magic link has been sent",
            "url": url,
        }
    return {"message": "If the email exists, a magic link has been sent"}


@router.post("/magic-link/verify", response_model=Any)
async def verify_magic_link(
    body: MagicLinkVerify,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    if not verify_magic_token(body.token, body.email):
        raise HTTPException(status_code=401, detail="Invalid or expired magic link")

    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired magic link")

    user.last_login_at = datetime.now(timezone.utc)
    await session.flush()
    refresh_token = await _create_session(user, request, session)
    return await _build_tokens(user, refresh_token=refresh_token)


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    current_user=Depends(get_current_user),
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
    current_user=Depends(get_current_user),
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
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    await session.flush()
    return {"status": "mfa_disabled"}
