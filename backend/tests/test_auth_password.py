"""Behavioural coverage for password reset, magic links, and MFA."""

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
from backend.auth.providers import create_magic_link
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


# ── Password reset ─────────────────────────────────────────────


class TestPasswordReset:
    def test_forgot_password_is_enumeration_safe(self, client):
        tokens = _register(client)
        existing = client.post(
            "/auth/forgot-password", json={"email": tokens["email"]}
        )
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


# ── MFA ──────────────────────────────────────────────────────


class TestMFA:
    def test_mfa_setup_requires_auth(self, client):
        response = client.post("/auth/mfa/setup")
        assert response.status_code == 401

    def test_mfa_verify_requires_setup(self, client):
        tokens = _register(client)
        response = client.post(
            "/auth/mfa/verify",
            json={"code": "123456"},
            headers=_headers(tokens),
        )
        assert response.status_code == 400
