"""Behavioural coverage for authentication registration, login, and refresh."""

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
