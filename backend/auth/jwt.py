"""JWT token creation and verification."""
from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from loguru import logger


SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_EXPIRE", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("JWT_REFRESH_EXPIRE", "7"))

if SECRET_KEY == "change-me-in-production":
    logger.warning("JWT_SECRET_KEY is set to default 'change-me-in-production'. Set a strong random secret in production.")


def create_access_token(subject: str, extra_claims: Optional[dict[str, Any]] = None) -> str:
    """Create a short-lived JWT access token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": now,
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """Create a long-lived JWT refresh token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": now,
        "type": "refresh",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict[str, Any]]:
    """Decode and verify a JWT token. Returns the payload or None."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"JWT decode failed: {e}")
        return None


def get_token_subject(token: str, expected_type: str = "access") -> Optional[str]:
    """Extract the subject (user ID) from a valid token of the expected type."""
    payload = decode_token(token)
    if payload is None:
        return None
    if payload.get("type") != expected_type:
        logger.warning(f"Token type mismatch: expected {expected_type}, got {payload.get('type')}")
        return None
    return payload.get("sub")
