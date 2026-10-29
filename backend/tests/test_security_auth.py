"""Security regression suite — auth enforcement and stream ownership."""

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


def auth_headers(tokens: dict, org_id: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    if org_id:
        headers["X-Organization-Id"] = org_id
    return headers


class TestAuthEnforcement:
    def test_upload_requires_auth(self, client):
        resp = client.post("/upload", files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")})
        assert resp.status_code == 401

    def test_research_requires_auth(self, client):
        resp = client.post("/research", json={"query": "test"})
        assert resp.status_code == 401

    def test_org_endpoints_require_auth(self, client):
        assert client.get("/organizations").status_code == 401
        assert client.get("/organizations/abc/workspaces").status_code == 401


class TestStreamOwnership:
    def test_foreign_user_cannot_subscribe_to_owned_stream(self, client, api_app):
        """Subscribe to another user's research stream must be rejected."""
        alice = register(client, "alice-stream@example.com", "Alice Stream")
        me = client.get("/auth/me", headers=auth_headers(alice))
        assert me.status_code == 200
        alice_id = me.json()["id"]
        stream_mgr = api_app.state.stream_manager
        task_id = "task-owned-by-alice"
        stream_mgr.create_stream(task_id, owner_user_id=alice_id)
        bob = register(client, "bob-stream@example.com", "Bob Stream")
        resp = client.get(
            f"/research/stream/{task_id}",
            headers=auth_headers(bob),
        )
        assert resp.status_code == 403
        stream_mgr.close_stream(task_id)

    def test_subscribe_to_unknown_stream_returns_404(self, client, api_app):
        alice = register(client, "alice-unknown@example.com", "Alice Unknown")
        resp = client.get(
            "/research/stream/task-that-never-existed",
            headers=auth_headers(alice),
        )
        assert resp.status_code == 404
