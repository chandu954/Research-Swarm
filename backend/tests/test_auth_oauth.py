"""Behavioural coverage for Google OAuth."""

from __future__ import annotations

import os
import re
import sqlite3
import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient


def _database_path() -> str:
    url = os.environ.get("DATABASE_URL", "")
    match = re.match(r"sqlite\+aiosqlite:///(.*)", url)
    assert match, f"expected a SQLite test database, got {url!r}"
    return os.path.abspath(match.group(1))


def _sqlite_update(sql: str, params: tuple = ()) -> None:
    with sqlite3.connect(_database_path()) as connection:
        connection.execute(sql, params)
        connection.commit()


def _sqlite_scalar(sql: str, params: tuple = ()):
    with sqlite3.connect(_database_path()) as connection:
        row = connection.execute(sql, params).fetchone()
    return row[0] if row else None


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

        assert _sqlite_scalar("SELECT id FROM users WHERE email = ?", (email,))
        assert (
            _sqlite_scalar("SELECT google_id FROM users WHERE email = ?", (email,))
            == "google-123"
        )
