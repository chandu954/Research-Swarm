"""Behavioural coverage for the authentication API.

These tests exercise the real FastAPI routes against an isolated SQLite
database. External identity providers and the Supabase bridge are mocked;
no developer database or production credential is ever touched.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pyotp
import pytest
from backend.auth.jwt import create_access_token, create_refresh_token, decode_token
from fastapi.testclient import TestClient

# ── Fixtures ─────────────────────────────────────────────────────


def _database_path() -> str:
    url = os.environ.get("DATABASE_URL", "")
    match = re.match(r"sqlite\+aiosqlite:///(.*)", url)
    assert match, f"expected a SQLite test database, got {url!r}"
    return os.path.abspath(match.group(1))


@pytest.fixture(scope="module")
def api_app():
    """App with a fresh database and rate limiting disabled."""
    from backend.db.session import _engine

    db_path = _database_path()
    if os.path.exists(db_path):
        os.remove(db_path)
    _engine.sync_engine.dispose()

    from backend.api.main import app

    app.state.limiter.enabled = False
    return app


@pytest.fixture(scope="module")
def client(api_app):
    with TestClient(api_app) as test_client:
        yield test_client


@pytest.fixture
def unauthenticated_client(api_app):
    with TestClient(api_app) as test_client:
        yield test_client


def _register(client: TestClient, *, password: str = "test-password-123") -> dict:
    email = f"user-{uuid.uuid4().hex[:12]}@example.com"
    response = client.post(
        "/auth/register",
        json={"email": email, "password": password, "name": "Auth Test"},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    payload["email"] = email
    payload["password"] = password
    return payload


def _headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _sqlite_update(sql: str, params: tuple = ()) -> None:
    with sqlite3.connect(_database_path()) as connection:
        connection.execute(sql, params)
        connection.commit()


def _sqlite_scalar(sql: str, params: tuple = ()):
    with sqlite3.connect(_database_path()) as connection:
        row = connection.execute(sql, params).fetchone()
    return row[0] if row else None


# ── Registration, login and current user ────────────────────────


class TestRegistrationAndLogin:
    def test_register_creates_default_organization_and_session(self, client):
        tokens = _register(client)
        assert tokens["access_token"]
        assert tokens["refresh_token"]
        assert tokens["token_type"] == "bearer"

        me = client.get("/auth/me", headers=_headers(tokens))
        assert me.status_code == 200
        assert me.json()["email"] == tokens["email"]
        assert me.json()["is_active"] is True

        status = client.get("/auth/org-status", headers=_headers(tokens))
        assert status.status_code == 200
        assert status.json() == {"has_organization": True}

    def test_duplicate_email_is_rejected(self, client):
        tokens = _register(client)
        response = client.post(
            "/auth/register",
            json={
                "email": tokens["email"],
                "password": "another-password",
                "name": "Duplicate",
            },
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "Email already registered"

    def test_registration_validation(self, client):
        assert (
            client.post(
                "/auth/register",
                json={"email": "not-an-email", "password": "long-enough", "name": "x"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/auth/register",
                json={"email": "valid@example.com", "password": "short", "name": "x"},
            ).status_code
            == 422
        )

    def test_login_success_and_failures(self, client):
        tokens = _register(client)

        ok = client.post(
            "/auth/login",
            json={"email": tokens["email"], "password": tokens["password"]},
        )
        assert ok.status_code == 200
        assert ok.json()["access_token"]

        wrong = client.post(
            "/auth/login",
            json={"email": tokens["email"], "password": "definitely-wrong"},
        )
        assert wrong.status_code == 401
        assert wrong.json()["detail"] == "Invalid email or password"

        unknown = client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "whatever-password"},
        )
        assert unknown.status_code == 401

    def test_login_rejects_deactivated_account(self, client):
        tokens = _register(client)
        _sqlite_update(
            "UPDATE users SET is_active = 0 WHERE email = ?", (tokens["email"],)
        )
        response = client.post(
            "/auth/login",
            json={"email": tokens["email"], "password": tokens["password"]},
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Account is deactivated"

    def test_me_requires_authentication(self, unauthenticated_client):
        assert unauthenticated_client.get("/auth/me").status_code == 401
        assert unauthenticated_client.get("/auth/org-status").status_code == 401


# ── Refresh token lifecycle ─────────────────────────────────────


class TestRefreshEdgeCases:
    def test_refresh_rejects_access_token(self, client):
        tokens = _register(client)
        response = client.post(
            "/auth/refresh", json={"refresh_token": tokens["access_token"]}
        )
        assert response.status_code == 401

    def test_refresh_rejects_expired_session(self, client):
        tokens = _register(client)
        token_hash = hashlib.sha256(tokens["refresh_token"].encode()).hexdigest()
        past = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        _sqlite_update(
            "UPDATE user_sessions SET expires_at = ? WHERE refresh_token_hash = ?",
            (past, token_hash),
        )
        response = client.post(
            "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()
        assert _sqlite_scalar(
            "SELECT is_active FROM user_sessions WHERE refresh_token_hash = ?",
            (token_hash,),
        ) in (0, False)

    def test_refresh_rejects_deactivated_user(self, client):
        tokens = _register(client)
        _sqlite_update(
            "UPDATE users SET is_active = 0 WHERE email = ?", (tokens["email"],)
        )
        response = client.post(
            "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "User not found or inactive"

    def test_logout_with_invalid_token_is_idempotent(self, client):
        response = client.post("/auth/logout", json={"refresh_token": "not-a-jwt"})
        assert response.status_code == 200
        assert response.json() == {"status": "logged_out"}

    def test_logout_with_unknown_but_valid_token(self, client):
        token = create_refresh_token(str(uuid.uuid4()))
        response = client.post("/auth/logout", json={"refresh_token": token})
        assert response.status_code == 200


# ── Google OAuth ────────────────────────────────────────────────


class TestGoogleOAuth:
    def test_login_redirects_with_state_cookie(self, unauthenticated_client):
        response = unauthenticated_client.get("/auth/google", follow_redirects=False)
        assert response.status_code in (302, 307)
        assert "accounts.google.com" in response.headers["location"]
        assert "state=" in response.headers["location"]
        cookie = response.headers.get("set-cookie", "")
        assert "oauth_state=" in cookie
        assert "HttpOnly" in cookie
        assert "Secure" in cookie
        assert "SameSite=lax" in cookie

    def test_callback_rejects_missing_or_mismatched_state(self, unauthenticated_client):
        no_cookie = unauthenticated_client.get(
            "/auth/google/callback", params={"code": "abc", "state": "expected"}
        )
        assert no_cookie.status_code == 200
        assert "Invalid state parameter" in no_cookie.text

        unauthenticated_client.cookies.set("oauth_state", "stored")
        mismatch = unauthenticated_client.get(
            "/auth/google/callback", params={"code": "abc", "state": "other"}
        )
        assert "Invalid state parameter" in mismatch.text
        unauthenticated_client.cookies.clear()

    def test_callback_handles_token_exchange_failure(
        self, unauthenticated_client, monkeypatch
    ):
        monkeypatch.setattr(
            "backend.api.auth.exchange_google_code",
            AsyncMock(return_value=None),
        )
        unauthenticated_client.cookies.set("oauth_state", "state-1")
        response = unauthenticated_client.get(
            "/auth/google/callback", params={"code": "abc", "state": "state-1"}
        )
        assert response.status_code == 200
        assert "Failed to exchange authorization code" in response.text

    def test_callback_handles_userinfo_failure(
        self, unauthenticated_client, monkeypatch
    ):
        monkeypatch.setattr(
            "backend.api.auth.exchange_google_code",
            AsyncMock(return_value={"access_token": "provider-token"}),
        )
        monkeypatch.setattr(
            "backend.api.auth.get_google_userinfo",
            AsyncMock(return_value=None),
        )
        unauthenticated_client.cookies.set("oauth_state", "state-2")
        response = unauthenticated_client.get(
            "/auth/google/callback", params={"code": "abc", "state": "state-2"}
        )
        assert "Failed to get user info" in response.text

    def test_callback_creates_and_reuses_google_user(
        self, unauthenticated_client, monkeypatch
    ):
        email = f"oauth-{uuid.uuid4().hex[:10]}@example.com"
        exchange = AsyncMock(return_value={"access_token": "provider-token"})
        userinfo = AsyncMock(
            return_value={
                "id": "google-123",
                "email": email,
                "name": "OAuth User",
                "picture": "https://example.com/avatar.png",
            }
        )
        monkeypatch.setattr("backend.api.auth.exchange_google_code", exchange)
        monkeypatch.setattr("backend.api.auth.get_google_userinfo", userinfo)

        unauthenticated_client.cookies.set("oauth_state", "state-3")
        first = unauthenticated_client.get(
            "/auth/google/callback", params={"code": "abc", "state": "state-3"}
        )
        assert first.status_code == 200
        assert "access_token" in first.text
        assert email not in first.text  # only tokens are exposed

        unauthenticated_client.cookies.set("oauth_state", "state-4")
        second = unauthenticated_client.get(
            "/auth/google/callback", params={"code": "abc", "state": "state-4"}
        )
        assert second.status_code == 200
        assert "access_token" in second.text

        user_id = _sqlite_scalar("SELECT id FROM users WHERE email = ?", (email,))
        assert user_id
        assert (
            _sqlite_scalar("SELECT google_id FROM users WHERE email = ?", (email,))
            == "google-123"
        )


# ── Password reset ─────────────────────────────────────────────


class TestPasswordReset:
    def test_forgot_password_is_enumeration_safe(self, client):
        tokens = _register(client)
        existing = client.post("/auth/forgot-password", json={"email": tokens["email"]})
        missing = client.post(
            "/auth/forgot-password", json={"email": "missing@example.com"}
        )
        assert existing.status_code == missing.status_code == 200
        assert existing.json() == missing.json()

    def test_reset_password_rejects_invalid_token(self, client):
        response = client.post(
            "/auth/reset-password",
            json={"token": "garbage", "password": "new-password-123"},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid or expired reset token"

    def test_reset_password_rejects_wrong_token_type(self, client):
        tokens = _register(client)
        response = client.post(
            "/auth/reset-password",
            json={"token": tokens["access_token"], "password": "new-password-123"},
        )
        assert response.status_code == 400

    def test_reset_password_rejects_unknown_user(self, client):
        token = create_access_token(str(uuid.uuid4()), {"type": "password_reset"})
        response = client.post(
            "/auth/reset-password",
            json={"token": token, "password": "new-password-123"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "User not found"

    def test_reset_password_updates_hash_and_revokes_sessions(self, client):
        tokens = _register(client)
        user_id = decode_token(tokens["access_token"])["sub"]
        reset_token = create_access_token(user_id, {"type": "password_reset"})

        response = client.post(
            "/auth/reset-password",
            json={"token": reset_token, "password": "brand-new-password"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "password_reset"}

        old_login = client.post(
            "/auth/login",
            json={"email": tokens["email"], "password": tokens["password"]},
        )
        assert old_login.status_code == 401

        new_login = client.post(
            "/auth/login",
            json={"email": tokens["email"], "password": "brand-new-password"},
        )
        assert new_login.status_code == 200

        refresh = client.post(
            "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert refresh.status_code == 401


# ── Magic links ────────────────────────────────────────────────


class TestMagicLinks:
    def test_request_link_exposes_url_only_outside_production(
        self, client, monkeypatch
    ):
        monkeypatch.setenv("ENVIRONMENT", "test")
        tokens = _register(client)
        response = client.post(
            "/auth/magic-link",
            json={
                "email": tokens["email"],
                "password": "irrelevant-password",
                "name": "Magic",
            },
        )
        assert response.status_code == 200
        assert "url" in response.json()
        assert "token=" in response.json()["url"]

        monkeypatch.setenv("ENVIRONMENT", "production")
        production = client.post(
            "/auth/magic-link",
            json={
                "email": tokens["email"],
                "password": "irrelevant-password",
                "name": "Magic",
            },
        )
        assert production.status_code == 200
        assert "url" not in production.json()

    def test_verify_rejects_invalid_token(self, client):
        response = client.post(
            "/auth/magic-link/verify",
            json={"token": "invalid", "email": "nobody@example.com"},
        )
        assert response.status_code == 401

    def test_verify_rejects_unknown_user(self, client):
        from backend.auth.providers import create_magic_link

        _, token, _ = create_magic_link("ghost@example.com")
        response = client.post(
            "/auth/magic-link/verify",
            json={"token": token, "email": "ghost@example.com"},
        )
        assert response.status_code == 401

    def test_verify_issues_tokens_for_existing_user(self, client):
        from backend.auth.providers import create_magic_link

        tokens = _register(client)
        _, token, _ = create_magic_link(tokens["email"])
        response = client.post(
            "/auth/magic-link/verify",
            json={"token": token, "email": tokens["email"]},
        )
        assert response.status_code == 200, response.text
        assert response.json()["access_token"]

        reused = client.post(
            "/auth/magic-link/verify",
            json={"token": token, "email": tokens["email"]},
        )
        assert reused.status_code == 401


# ── MFA ────────────────────────────────────────────────────────


class TestMFA:
    def test_setup_verify_and_disable(self, client):
        tokens = _register(client)
        headers = _headers(tokens)

        setup = client.post("/auth/mfa/setup", headers=headers)
        assert setup.status_code == 200
        secret = setup.json()["secret"]
        assert len(setup.json()["recovery_codes"]) == 8
        assert setup.json()["qr_code_url"].startswith("otpauth://")

        invalid = client.post(
            "/auth/mfa/verify", headers=headers, json={"code": "000000"}
        )
        assert invalid.status_code == 400
        assert invalid.json()["detail"] == "Invalid MFA code"

        valid = client.post(
            "/auth/mfa/verify",
            headers=headers,
            json={"code": pyotp.TOTP(secret).now()},
        )
        assert valid.status_code == 200
        assert valid.json() == {"status": "mfa_enabled"}

        disabled = client.post("/auth/mfa/disable", headers=headers)
        assert disabled.status_code == 200
        assert disabled.json() == {"status": "mfa_disabled"}

    def test_verify_requires_setup(self, client):
        tokens = _register(client)
        response = client.post(
            "/auth/mfa/verify", headers=_headers(tokens), json={"code": "123456"}
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "MFA not set up"


# ── Sessions and devices ───────────────────────────────────────


class TestSessionsAndDevices:
    def test_list_and_revoke_sessions(self, client):
        tokens = _register(client)
        headers = _headers(tokens)

        sessions = client.get("/auth/sessions", headers=headers)
        assert sessions.status_code == 200
        assert len(sessions.json()) >= 1
        session_id = sessions.json()[0]["id"]

        missing = client.delete("/auth/sessions/does-not-exist", headers=headers)
        assert missing.status_code == 404
        assert missing.json()["detail"] == "Session not found"

        revoked = client.delete(f"/auth/sessions/{session_id}", headers=headers)
        assert revoked.status_code == 200
        assert revoked.json() == {"status": "revoked"}

        remaining = client.get("/auth/sessions", headers=headers)
        assert session_id not in {item["id"] for item in remaining.json()}

    def test_device_listing_and_unknown_device(self, client):
        tokens = _register(client)
        headers = _headers(tokens)

        listed = client.get("/auth/devices", headers=headers)
        assert listed.status_code == 200
        assert listed.json() == []

        assert (
            client.post(
                "/auth/devices/does-not-exist/trust", headers=headers
            ).status_code
            == 404
        )

    def test_list_and_trust_device_with_fake_session(self):
        from backend.api.auth import list_devices, trust_device
        from backend.db.models import UserDevice

        user = _user()
        device = UserDevice(
            id=str(uuid.uuid4()),
            user_id=user.id,
            device_name="Test Laptop",
            device_type="laptop",
            trusted=False,
            created_at=datetime.now(timezone.utc),
        )
        listing_session = _FakeSession(results=[device], scalar_values=[[device]])
        listed = asyncio_run(list_devices(current_user=user, session=listing_session))
        assert listed[0].id == device.id

        trust_session = _FakeSession(results=[device])
        result = asyncio_run(
            trust_device(device.id, current_user=user, session=trust_session)
        )
        assert result == {"status": "trusted"}
        assert device.trusted is True
        assert device.trusted_at is not None

    def test_trust_unknown_device_raises_404(self):
        from backend.api.auth import trust_device
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as excinfo:
            asyncio_run(
                trust_device(
                    "missing",
                    current_user=_user(),
                    session=_FakeSession(results=[None]),
                )
            )
        assert excinfo.value.status_code == 404


# ── Helper-level branches ──────────────────────────────────────


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        if isinstance(self._value, list):
            return self._value
        return [] if self._value is None else [self._value]


class _FakeSession:
    """Minimal AsyncSession double for helper-level branch tests."""

    def __init__(self, results=(), scalar_values=()):
        self._results = list(results)
        self._scalar_values = list(scalar_values)
        self.added = []
        self.flushes = 0
        self.commits = 0

    async def execute(self, *_args, **_kwargs):
        return _Result(self._results.pop(0))

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1

    def add(self, item):
        self.added.append(item)

    def scalars(self):
        return self

    def all(self):
        return self._scalar_values.pop(0)


def _user(**overrides):
    from backend.db.models import User

    values = {
        "id": str(uuid.uuid4()),
        "email": "helper@example.com",
        "name": "Helper",
        "hashed_password": None,
        "avatar_url": None,
        "is_active": True,
        "mfa_enabled": False,
    }
    values.update(overrides)
    user = User(**values)
    return user


class TestAuthHelpers:
    def test_find_or_create_user_links_google_id(self):
        from backend.api.auth import _find_or_create_user

        existing = _user(name="", avatar_url=None)
        session = _FakeSession(results=[existing])
        result = asyncio_run(
            _find_or_create_user(
                "helper@example.com",
                "New Name",
                {"id": "g-1", "picture": "https://example.com/p.png"},
                "google",
                session,
            )
        )
        assert result is existing
        assert existing.google_id == "g-1"
        assert existing.name == "New Name"
        assert existing.avatar_url == "https://example.com/p.png"
        assert existing.last_login_at is not None
        assert session.flushes == 1

    def test_find_or_create_user_matches_by_provider_id(self):
        from backend.api.auth import _find_or_create_user

        existing = _user(email="old@example.com", google_id="g-2")
        session = _FakeSession(results=[None, existing])
        result = asyncio_run(
            _find_or_create_user(
                "new@example.com",
                "Name",
                {"id": "g-2"},
                "google",
                session,
            )
        )
        assert result is existing
        assert existing.email == "old@example.com"

    def test_find_or_create_user_creates_default_org(self):
        from backend.api.auth import _find_or_create_user

        session = _FakeSession(results=[None, None])
        result = asyncio_run(
            _find_or_create_user(
                "brand-new@example.com",
                "Brand New",
                {"id": "g-3"},
                "google",
                session,
            )
        )
        assert result.google_id == "g-3"
        assert result.email == "brand-new@example.com"
        # User, organization, membership, workspace, workspace membership, project
        assert len(session.added) == 6
        assert session.flushes >= 2

    def test_build_tokens_bridges_supabase_session(self):
        from backend.api import auth as auth_module

        user = _user()
        session_payload = {
            "access_token": "sb-access",
            "refresh_token": "sb-refresh",
        }
        with patch(
            "backend.core.supabase.ensure_supabase_user",
            return_value={"id": "sb-user"},
        ) as ensure, patch("backend.core.supabase.upsert_profile") as profile, patch(
            "backend.core.supabase.create_browser_session",
            return_value=session_payload,
        ):
            tokens = asyncio_run(auth_module._build_tokens(user))

        assert tokens.access_token
        assert tokens.supabase_access_token == "sb-access"
        assert tokens.supabase_refresh_token == "sb-refresh"
        ensure.assert_called_once()
        profile.assert_called_once()

    def test_build_tokens_survives_supabase_failure(self):
        from backend.api import auth as auth_module

        user = _user()
        with patch(
            "backend.core.supabase.ensure_supabase_user",
            side_effect=RuntimeError("supabase unavailable"),
        ):
            tokens = asyncio_run(auth_module._build_tokens(user))

        assert tokens.access_token
        assert tokens.refresh_token
        assert tokens.supabase_access_token is None

    def test_build_tokens_handles_empty_browser_session(self):
        from backend.api import auth as auth_module

        user = _user()
        with patch(
            "backend.core.supabase.ensure_supabase_user",
            return_value={"id": "sb-user"},
        ), patch("backend.core.supabase.upsert_profile"), patch(
            "backend.core.supabase.create_browser_session",
            return_value=None,
        ):
            tokens = asyncio_run(auth_module._build_tokens(user))

        assert tokens.supabase_access_token is None

    def test_oauth_callback_html_error_branch(self):
        from backend.api.auth import _oauth_callback_html
        from backend.db.schemas import TokenResponse

        response = _oauth_callback_html(
            TokenResponse(access_token="", refresh_token=""), error='bad "state"'
        )
        html = response.body.decode()
        assert "window.opener.postMessage" in html
        assert "window.location.href" in html
        assert "bad" in html

    def test_create_session_persists_hashed_refresh_token(self):
        from backend.api.auth import _create_session

        user = _user()
        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.headers = {"user-agent": "pytest"}
        session = _FakeSession()

        token = asyncio_run(_create_session(user, request, session))

        assert token
        stored = session.added[0]
        assert stored.refresh_token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert stored.ip_address == "127.0.0.1"
        assert stored.user_agent == "pytest"


def asyncio_run(coroutine):
    import asyncio

    return asyncio.run(coroutine)
