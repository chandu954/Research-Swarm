"""Centralized environment configuration and secure-startup validation.

Single source of truth for the security-critical environment contract:
refuses to boot in production with missing or weak secrets, and ensures
local development never silently runs on a published default.
"""
from __future__ import annotations
import os
import secrets as _secrets

from loguru import logger

WEAK_SECRETS = {
    "dev", "secret", "changeme", "password", "test", "development",
    "production", "12345678", "1234567890", "default",
}

PLACEHOLDER_MARKERS = (
    "change-this", "changeme", "example", "placeholder", "your-secret", "xxx",
)


def environment() -> str:
    return os.getenv("ENVIRONMENT", "development")


def is_production() -> bool:
    return environment() == "production"


def is_weak_secret(value: str) -> bool:
    if not value:
        return True
    lowered = value.lower()
    if lowered in WEAK_SECRETS:
        return True
    if any(marker in lowered for marker in PLACEHOLDER_MARKERS):
        return True
    return len(value) < 32


def validate_secrets() -> None:
    """Fail fast when required secrets are missing or weak.

    - Production: refuses to start (RuntimeError) unless JWT_SECRET_KEY and
      SUPABASE_BRIDGE_SECRET are strong and SUPABASE_SERVICE_ROLE_KEY is set.
    - Development: auto-generates an ephemeral JWT secret when unset so local
      work never hard-fails, but the Supabase bridge still fails closed.
    """
    jwt_secret = os.getenv("JWT_SECRET_KEY", "")

    if is_production():
        problems: list[str] = []
        if not jwt_secret:
            problems.append("JWT_SECRET_KEY is not set")
        elif is_weak_secret(jwt_secret):
            problems.append("JWT_SECRET_KEY is too weak (min 32 chars, no placeholder values)")
        bridge = os.getenv("SUPABASE_BRIDGE_SECRET", jwt_secret)
        if is_weak_secret(bridge):
            problems.append("SUPABASE_BRIDGE_SECRET is missing or too weak")
        if not os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
            problems.append("SUPABASE_SERVICE_ROLE_KEY is not set")
        if problems:
            raise RuntimeError(f"Refusing to start in production: {'; '.join(problems)}")
        return

    if not jwt_secret:
        generated = _secrets.token_urlsafe(64)
        os.environ["JWT_SECRET_KEY"] = generated
        logger.warning("JWT_SECRET_KEY not set; generated an ephemeral development key")
