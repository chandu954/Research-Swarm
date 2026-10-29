"""Security regression suite — refresh token lifecycle (C4)."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock

import pytest


@pytest.fixture(scope="module")
def api_app():
    """The FastAPI app with a fresh SQLite DB and rate limiting disabled."""
    import re

    from backend.db.session import _engine

    url = os.environ.get("DATABASE_URL", "")
    m = re.match(r"sqlite\+aiosqlite:///(.*)", url)
    if m:
        db_path = os.path.abspath(m.group(1))
        if os.path.exists(db_path):
            os.remove(db_path)
    _engine.sync_engine.dispose()

    from backend.api.main import app
    app.state.limiter.enabled = False
    app.state.graph = AsyncMock()
    app.state.graph.ainvoke.return_value = {
        "status": "completed", "answer": "test answer", "sources": [],
        "logs": [], "plan": [], "errors": [], "pdf_paths": [],
    }
    return app


@pytest.fixture(scope="module")
def client(api_app):
    from fastapi.testclient import TestClient
    with TestClient(api_app) as c:
        yield c


def register(client, email: str, name: str = "Test User", password: str = "test-password-123"):
    resp = client.post("/auth/register", json={
        "email": email, "password": password, "name": name,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestRefreshLifecycle:
    def test_refresh_rotates_tokens(self, client):
        tokens = register(client, "rotate@example.com")
        r1 = tokens["refresh_token"]
        resp = client.post("/auth/refresh", json={"refresh_token": r1})
        assert resp.status_code == 200, resp.text
        r2 = resp.json()["refresh_token"]
        assert r2 != r1
        # Old token must no longer work after rotation
        old = client.post("/auth/refresh", json={"refresh_token": r1})
        assert old.status_code == 401

    def test_refresh_reuse_revokes_all_sessions(self, client):
        tokens = register(client, "reuse@example.com")
        r1 = tokens["refresh_token"]
        resp = client.post("/auth/refresh", json={"refresh_token": r1})
        assert resp.status_code == 200
        r2 = resp.json()["refresh_token"]
        # Replay the rotated token → reuse detection
        replay = client.post("/auth/refresh", json={"refresh_token": r1})
        assert replay.status_code == 401
        # All sessions revoked: the freshly rotated token is dead too
        after = client.post("/auth/refresh", json={"refresh_token": r2})
        assert after.status_code == 401

    def test_logout_revokes_refresh_token(self, client):
        tokens = register(client, "logout@example.com")
        r1 = tokens["refresh_token"]
        out = client.post("/auth/logout", json={"refresh_token": r1})
        assert out.status_code == 200
        resp = client.post("/auth/refresh", json={"refresh_token": r1})
        assert resp.status_code == 401

    def test_refresh_after_password_reset_revoked(self, client):
        from backend.auth.jwt import create_access_token, decode_token
        tokens = register(client, "pwreset@example.com")
        r1 = tokens["refresh_token"]
        user_id = decode_token(tokens["access_token"])["sub"]
        reset_token = create_access_token(user_id, {"type": "password_reset", "sub": user_id})
        resp = client.post("/auth/reset-password", json={"token": reset_token, "password": "brand-new-password-1"})
        assert resp.status_code == 200, resp.text
        after = client.post("/auth/refresh", json={"refresh_token": r1})
        assert after.status_code == 401

    def test_refresh_with_garbage_token(self, client):
        resp = client.post("/auth/refresh", json={"refresh_token": "not-a-jwt"})
        assert resp.status_code == 401
