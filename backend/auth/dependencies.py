"""FastAPI dependency injection for authentication (JWT + API Key)."""
from __future__ import annotations
import hashlib
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.session import get_session
from backend.db.models import User, APIKey
from backend.auth.jwt import get_token_subject

_bearer_scheme = HTTPBearer(auto_error=False)


async def _resolve_api_key(request: Request, session: AsyncSession) -> Optional[User]:
    """Resolve a user from X-API-Key header (not Authorization Bearer)."""
    api_key_raw = request.headers.get("X-API-Key")
    if not api_key_raw:
        return None

    key_hash = hashlib.sha256(api_key_raw.encode()).hexdigest()
    result = await session.execute(
        select(APIKey).where(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True,
        )
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        return None

    from datetime import datetime, timezone
    api_key.last_used_at = datetime.now(timezone.utc)

    user_result = await session.execute(select(User).where(User.id == api_key.user_id))
    return user_result.scalar_one_or_none()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
) -> User:
    """Dependency: extract and validate the current user from Bearer token or X-API-Key."""
    if credentials is None and request:
        api_user = await _resolve_api_key(request, session)
        if api_user:
            return api_user

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = get_token_subject(credentials.credentials, expected_type="access")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
) -> Optional[User]:
    """Dependency: return the user if authenticated, or None."""
    if credentials is None and request:
        api_user = await _resolve_api_key(request, session)
        if api_user:
            return api_user

    if credentials is None:
        return None

    user_id = get_token_subject(credentials.credentials, expected_type="access")
    if user_id is None:
        return None

    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
