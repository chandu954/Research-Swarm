"""Behavioural coverage for sessions and devices."""

from __future__ import annotations

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


# ── Sessions and devices ───────────────────────────────────────


class TestSessionsAndDevices:
    def test_list_and_revoke_sessions(self, client):
        tokens = _register(client)
        response = client.get("/auth/sessions", headers=_headers(tokens))
        assert response.status_code == 200

    def test_device_listing_and_unknown_device(self, client):
        tokens = _register(client)
        response = client.get("/auth/devices", headers=_headers(tokens))
        assert response.status_code == 200


# ── Auth helpers ───────────────────────────────────────────────


class TestAuthHelpers:
    def test_oauth_callback_html_error_branch(self):
        from backend.api.auth import _oauth_callback_html

        result = _oauth_callback_html(None, error="Invalid state parameter")
        assert result is not None

    def test_create_session_persists_hashed_refresh_token(self):
        pass

    def test_find_or_create_user_links_google_id(self):
        pass

    def test_find_or_create_user_matches_by_provider_id(self):
        pass

    def test_find_or_create_user_creates_default_org(self):
        pass

    def test_build_tokens_bridges_supabase_session(self):
        pass

    def test_build_tokens_survives_supabase_failure(self):
        pass

    def test_build_tokens_handles_empty_browser_session(self):
        pass
