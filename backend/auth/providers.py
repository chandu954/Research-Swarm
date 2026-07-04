"""Multi-provider OAuth and authentication support.

Supports: Google, GitHub, Microsoft, Magic Links, MFA
"""
from __future__ import annotations
import os
import secrets
import hashlib
from typing import Optional
from urllib.parse import urlencode
from datetime import datetime, timedelta, timezone

import httpx
from loguru import logger


# ── Configuration ───────────────────────────────────────────────

class OAuthConfig:
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_uri: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

    github_client_id: str = os.getenv("GITHUB_CLIENT_ID", "")
    github_client_secret: str = os.getenv("GITHUB_CLIENT_SECRET", "")
    github_redirect_uri: str = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8000/auth/github/callback")

    microsoft_client_id: str = os.getenv("MICROSOFT_CLIENT_ID", "")
    microsoft_client_secret: str = os.getenv("MICROSOFT_CLIENT_SECRET", "")
    microsoft_redirect_uri: str = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:8000/auth/microsoft/callback")
    microsoft_tenant: str = os.getenv("MICROSOFT_TENANT", "common")

    magic_link_secret: str = os.getenv("MAGIC_LINK_SECRET", "")
    magic_link_expire_minutes: int = int(os.getenv("MAGIC_LINK_EXPIRE", "15"))

    app_url: str = os.getenv("APP_URL", "http://localhost:3000")


config = OAuthConfig()


# ── Helpers ─────────────────────────────────────────────────────

def _get_provider_redirect_uri(provider: str) -> str:
    return os.getenv(f"{provider.upper()}_REDIRECT_URI", f"http://localhost:8000/auth/{provider}/callback")


# ── Google OAuth ────────────────────────────────────────────────

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


def get_google_auth_url(state: str = "") -> str:
    params = {
        "client_id": config.google_client_id,
        "redirect_uri": config.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
    }
    if state:
        params["state"] = state
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_google_code(code: str) -> Optional[dict]:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": config.google_client_id,
                    "client_secret": config.google_client_secret,
                    "redirect_uri": config.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Google token exchange failed: {e}")
            return None


async def get_google_userinfo(access_token: str) -> Optional[dict]:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Google userinfo failed: {e}")
            return None


# ── GitHub OAuth ────────────────────────────────────────────────

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USERINFO_URL = "https://api.github.com/user"
GITHUB_EMAIL_URL = "https://api.github.com/user/emails"


def get_github_auth_url(state: str = "") -> str:
    params = {
        "client_id": config.github_client_id,
        "redirect_uri": config.github_redirect_uri,
        "scope": "read:user user:email",
    }
    if state:
        params["state"] = state
    return f"{GITHUB_AUTH_URL}?{urlencode(params)}"


async def exchange_github_code(code: str) -> Optional[dict]:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                GITHUB_TOKEN_URL,
                data={
                    "client_id": config.github_client_id,
                    "client_secret": config.github_client_secret,
                    "code": code,
                    "redirect_uri": config.github_redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"GitHub token exchange failed: {e}")
            return None


async def get_github_userinfo(access_token: str) -> Optional[dict]:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                GITHUB_USERINFO_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
            if not data.get("email"):
                email_resp = await client.get(
                    GITHUB_EMAIL_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if email_resp.status_code == 200:
                    emails = email_resp.json()
                    primary = next((e for e in emails if e.get("primary")), {})
                    data["email"] = primary.get("email", "")
            return data
        except Exception as e:
            logger.error(f"GitHub userinfo failed: {e}")
            return None


# ── Microsoft OAuth ─────────────────────────────────────────────

MICROSOFT_AUTH_URL = f"https://login.microsoftonline.com/{config.microsoft_tenant}/oauth2/v2.0/authorize"
MICROSOFT_TOKEN_URL = f"https://login.microsoftonline.com/{config.microsoft_tenant}/oauth2/v2.0/token"
MICROSOFT_USERINFO_URL = "https://graph.microsoft.com/v1.0/me"


def get_microsoft_auth_url(state: str = "") -> str:
    params = {
        "client_id": config.microsoft_client_id,
        "redirect_uri": config.microsoft_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile User.Read",
    }
    if state:
        params["state"] = state
    return f"{MICROSOFT_AUTH_URL}?{urlencode(params)}"


async def exchange_microsoft_code(code: str) -> Optional[dict]:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                MICROSOFT_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": config.microsoft_client_id,
                    "client_secret": config.microsoft_client_secret,
                    "redirect_uri": config.microsoft_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Microsoft token exchange failed: {e}")
            return None


async def get_microsoft_userinfo(access_token: str) -> Optional[dict]:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                MICROSOFT_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Microsoft userinfo failed: {e}")
            return None


# ── Magic Links ─────────────────────────────────────────────────

_magic_link_store: dict[str, dict] = {}

def _cleanup_expired_magic_links() -> None:
    now = datetime.now(timezone.utc)
    expired = [k for k, v in _magic_link_store.items() if v.get("expires_at", now) < now]
    for k in expired:
        _magic_link_store.pop(k, None)

def generate_magic_link_token(email: str) -> str:
    raw = f"{email}:{secrets.token_urlsafe(32)}:{datetime.now(timezone.utc).timestamp()}"
    token = hashlib.sha256(raw.encode()).hexdigest()
    return token


def create_magic_link(email: str) -> tuple[str, str, datetime]:
    token = generate_magic_link_token(email)
    expire_minutes = config.magic_link_expire_minutes
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    _cleanup_expired_magic_links()
    _magic_link_store[token] = {"email": email, "expires_at": expires_at, "used": False}
    return f"{config.app_url}/auth/magic?token={token}&email={email}", token, expires_at


def verify_magic_token(token: str, email: str) -> bool:
    _cleanup_expired_magic_links()
    entry = _magic_link_store.get(token)
    if not entry:
        return False
    if entry["used"]:
        return False
    if entry["email"] != email:
        return False
    if datetime.now(timezone.utc) > entry["expires_at"]:
        _magic_link_store.pop(token, None)
        return False
    entry["used"] = True
    return True


# ── MFA ─────────────────────────────────────────────────────────

import pyotp


def generate_mfa_secret() -> str:
    return pyotp.random_base32()


def generate_mfa_qr_code(secret: str, email: str) -> str:
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name="ResearchSwarm")
    return uri


def verify_mfa_code(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code)


def generate_recovery_codes(count: int = 8) -> list[str]:
    return [secrets.token_hex(4) for _ in range(count)]
