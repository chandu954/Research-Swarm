"""JWT token creation and verification. No fallback secret — production must set JWT_SECRET_KEY."""
from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from loguru import logger


JWT_ISSUER: str = os.getenv("JWT_ISSUER", "researchswarm")
JWT_AUDIENCE: str = os.getenv("JWT_AUDIENCE", "researchswarm-api")
ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_EXPIRE", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("JWT_REFRESH_EXPIRE", "7"))


def _get_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError(
            "JWT_SECRET_KEY environment variable is not set. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )
    return secret


def _rotation_secrets() -> list[str]:
    """Active signing secret plus any previously-rotated secrets (verification only)."""
    secrets = [s for s in os.getenv("JWT_SECRET_KEYS_ROTATION", "").split(",") if s]
    primary = _get_secret()
    return [primary, *[s for s in secrets if s != primary]]


def _kid(secret: str) -> str:
    import hashlib
    return hashlib.sha256(secret.encode()).hexdigest()[:8]


def create_access_token(subject: str, extra_claims: Optional[dict[str, Any]] = None) -> str:
    """Create a short-lived JWT access token (signed with the primary key)."""
    import uuid
    secret = _get_secret()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "jti": uuid.uuid4().hex,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": now,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "kid": _kid(secret),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """Create a long-lived JWT refresh token (signed with the primary key).

    A random ``jti`` makes every issuance unique: rotated tokens are never
    byte-identical to their predecessor, and the token hash stored in the
    session row changes on rotation (reuse detection relies on this).
    """
    import uuid
    secret = _get_secret()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "jti": uuid.uuid4().hex,
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": now,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "kid": _kid(secret),
        "type": "refresh",
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict[str, Any]]:
    """Decode and verify a JWT token. Returns the payload or None.

    Verification supports key rotation: the `kid` claim selects the signing
    key; the primary key is always accepted regardless of `kid`.
    """
    candidates = _rotation_secrets()
    primary = candidates[0]
    try:
        unverified = jwt.get_unverified_header(token)
    except JWTError:
        return None
    kid = unverified.get("kid")
    selected = primary
    if kid:
        for secret in candidates:
            if _kid(secret) == kid:
                selected = secret
                break
    for secret in [selected, *([primary] if selected != primary else [])]:
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=[ALGORITHM],
                issuer=JWT_ISSUER,
                audience=JWT_AUDIENCE,
            )
            return payload
        except JWTError as e:
            logger.debug(f"JWT decode failed with candidate key: {e}")
    logger.warning("JWT decode failed for all candidate keys")
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
