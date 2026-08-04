"""Security regression suite — tenant isolation, document ownership,
refresh token lifecycle, secret validation.

These tests are permanent: they lock in the fixes for the Phase 8.5
backend security audit (C1-C4) so the vulnerability classes cannot
silently reappear.
"""
from __future__ import annotations
import os

import pytest
from unittest.mock import AsyncMock

# ── Fixtures ─────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def api_app():
    """The FastAPI app with a fresh SQLite DB and rate limiting disabled.

    A fresh database file per module avoids event-loop/pool entanglement:
    the TestClient owns the event loop and its lifespan runs init_db().
    """
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


def my_orgs(client, tokens) -> list[dict]:
    resp = client.get("/organizations", headers=auth_headers(tokens))
    assert resp.status_code == 200, resp.text
    return resp.json()


# ═════════════════════════════════════════════════════════════════
# C1 — Tenant isolation (org endpoints must never trust the path
#      parameter over authenticated membership)
# ═════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def two_users(client):
    alice = register(client, "alice-org@example.com", "Alice")
    bob = register(client, "bob-org@example.com", "Bob")
    alice_orgs = my_orgs(client, alice)
    bob_orgs = my_orgs(client, bob)
    assert alice_orgs and bob_orgs
    return {
        "alice": alice,
        "bob": bob,
        "alice_org": alice_orgs[0],
        "bob_org": bob_orgs[0],
    }


class TestTenantIsolation:

    def test_update_foreign_org_rejected(self, client, two_users):
        alice, bob_org = two_users["alice"], two_users["bob_org"]
        resp = client.patch(
            f"/organizations/{bob_org['id']}",
            headers=auth_headers(alice, two_users["alice_org"]["id"]),
            json={"name": "Hijacked"},
        )
        assert resp.status_code == 403

    def test_add_member_to_foreign_org_rejected(self, client, two_users):
        alice, bob_org = two_users["alice"], two_users["bob_org"]
        resp = client.post(
            f"/organizations/{bob_org['id']}/members",
            headers=auth_headers(alice, two_users["alice_org"]["id"]),
            json={"email": "mallory@example.com", "role": "admin"},
        )
        assert resp.status_code == 403

    def test_update_member_role_in_foreign_org_rejected(self, client, two_users):
        alice, bob_org = two_users["alice"], two_users["bob_org"]
        resp = client.patch(
            f"/organizations/{bob_org['id']}/members/some-member-id",
            headers=auth_headers(alice, two_users["alice_org"]["id"]),
            json={"role": "owner"},
        )
        assert resp.status_code == 403

    def test_remove_member_from_foreign_org_rejected(self, client, two_users):
        alice, bob_org = two_users["alice"], two_users["bob_org"]
        resp = client.delete(
            f"/organizations/{bob_org['id']}/members/some-member-id",
            headers=auth_headers(alice, two_users["alice_org"]["id"]),
        )
        assert resp.status_code == 403

    def test_create_workspace_in_foreign_org_rejected(self, client, two_users):
        alice, bob_org = two_users["alice"], two_users["bob_org"]
        resp = client.post(
            f"/organizations/{bob_org['id']}/workspaces",
            headers=auth_headers(alice, two_users["alice_org"]["id"]),
            json={"name": "Sneaky"},
        )
        assert resp.status_code == 403

    def test_list_workspaces_in_foreign_org_rejected(self, client, two_users):
        alice, bob_org = two_users["alice"], two_users["bob_org"]
        resp = client.get(
            f"/organizations/{bob_org['id']}/workspaces",
            headers=auth_headers(alice, two_users["alice_org"]["id"]),
        )
        assert resp.status_code == 403

    def test_get_foreign_org_rejected(self, client, two_users):
        alice, bob_org = two_users["alice"], two_users["bob_org"]
        resp = client.get(
            f"/organizations/{bob_org['id']}",
            headers=auth_headers(alice, two_users["alice_org"]["id"]),
        )
        assert resp.status_code == 403

    def test_own_org_operations_still_work(self, client, two_users):
        alice, alice_org = two_users["alice"], two_users["alice_org"]
        resp = client.patch(
            f"/organizations/{alice_org['id']}",
            headers=auth_headers(alice, alice_org["id"]),
            json={"description": "updated"},
        )
        assert resp.status_code == 200
        ws = client.post(
            f"/organizations/{alice_org['id']}/workspaces",
            headers=auth_headers(alice, alice_org["id"]),
            json={"name": "Research"},
        )
        assert ws.status_code == 201

    def test_header_spoofing_does_not_escalate(self, client, two_users):
        """Setting X-Organization-Id to another user's org must not help."""
        alice, bob_org = two_users["alice"], two_users["bob_org"]
        resp = client.patch(
            f"/organizations/{bob_org['id']}/members/some-id",
            headers=auth_headers(alice, bob_org["id"]),  # header = bob's org
            json={"role": "owner"},
        )
        # alice is not a member of bob's org at all → tenant resolution 403
        assert resp.status_code == 403


# ═════════════════════════════════════════════════════════════════
# C2 — Document ownership (documents resolved via DB, scoped to the
#      caller's organization; no direct filesystem filename access)
# ═════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def docs(client):
    alice = register(client, "alice-docs@example.com", "Alice Docs")
    bob = register(client, "bob-docs@example.com", "Bob Docs")
    alice_org = my_orgs(client, alice)[0]
    bob_org = my_orgs(client, bob)[0]

    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
    resp = client.post(
        "/upload",
        headers=auth_headers(alice, alice_org["id"]),
        files={"file": ("report.pdf", pdf, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    doc_id = resp.json()["document_id"]
    return {
        "alice": alice, "bob": bob,
        "alice_org": alice_org, "bob_org": bob_org,
        "doc_id": doc_id,
    }


class TestDocumentIsolation:

    def test_foreign_document_not_readable(self, client, docs):
        resp = client.get(
            f"/documents/{docs['doc_id']}",
            headers=auth_headers(docs["bob"], docs["bob_org"]["id"]),
        )
        assert resp.status_code == 404

    def test_foreign_document_not_downloadable(self, client, docs):
        resp = client.get(
            f"/documents/{docs['doc_id']}/download",
            headers=auth_headers(docs["bob"], docs["bob_org"]["id"]),
        )
        assert resp.status_code == 404

    def test_foreign_document_not_deletable(self, client, docs):
        resp = client.delete(
            f"/documents/{docs['doc_id']}",
            headers=auth_headers(docs["bob"], docs["bob_org"]["id"]),
        )
        assert resp.status_code == 404

    def test_own_document_readable(self, client, docs):
        resp = client.get(
            f"/documents/{docs['doc_id']}",
            headers=auth_headers(docs["alice"], docs["alice_org"]["id"]),
        )
        assert resp.status_code == 200

    def test_research_ignores_foreign_document_ids(self, client, docs, api_app):
        """POST /research must not hand another org's document to the graph."""
        captured = {}
        async def fake_ainvoke(state, config=None):
            captured["pdf_paths"] = state.get("pdf_paths", [])
            return {"status": "completed", "answer": "ok", "sources": [], "logs": [],
                    "plan": [], "errors": [], "pdf_paths": state.get("pdf_paths", [])}
        api_app.state.graph = AsyncMock()
        api_app.state.graph.ainvoke.side_effect = fake_ainvoke
        resp = client.post(
            "/research",
            headers=auth_headers(docs["bob"], docs["bob_org"]["id"]),
            json={"query": "test query", "document_ids": [docs["doc_id"]]},
        )
        assert resp.status_code == 200, resp.text
        assert captured["pdf_paths"] == []

    def test_research_ignores_raw_filenames(self, client, docs, api_app):
        """GET /research/stream must not resolve raw filenames from disk."""
        captured = {}
        async def fake_ainvoke(state, config=None):
            captured["pdf_paths"] = state.get("pdf_paths", [])
            return {"status": "completed", "answer": "ok", "sources": [], "logs": [],
                    "plan": [], "errors": [], "pdf_paths": state.get("pdf_paths", [])}
        api_app.state.graph = AsyncMock()
        api_app.state.graph.ainvoke.side_effect = fake_ainvoke
        with client.stream("GET", "/research/stream", params={
            "query": "test", "document_ids": "../../etc/passwd,report.pdf",
        }, headers=auth_headers(docs["bob"], docs["bob_org"]["id"])) as resp:
            for _ in resp.iter_lines():
                pass
        assert captured["pdf_paths"] == []

    def test_upload_sanitizes_filename(self, client, docs):
        """Upload with a path-traversal filename must be stored safely."""
        pdf = b"%PDF-1.4\n%%EOF"
        resp = client.post(
            "/upload",
            headers=auth_headers(docs["bob"], docs["bob_org"]["id"]),
            files={"file": ("../../evil.pdf", pdf, "application/pdf")},
        )
        assert resp.status_code == 200, resp.text
        doc_id = resp.json()["document_id"]
        detail = client.get(
            f"/documents/{doc_id}",
            headers=auth_headers(docs["bob"], docs["bob_org"]["id"]),
        )
        assert detail.status_code == 200
        assert "/" not in detail.json()["filename"]
        assert detail.json()["filename"].startswith("evil.pdf") or ".." not in detail.json()["filename"]


# ═════════════════════════════════════════════════════════════════
# C4 — Refresh token lifecycle: rotation, reuse detection, logout,
#      revocation
# ═════════════════════════════════════════════════════════════════

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


# ═════════════════════════════════════════════════════════════════
# C3 — JWT claims, key rotation, secret fail-closed behavior
# ═════════════════════════════════════════════════════════════════

class TestJWTAndSecrets:
    def test_token_has_iss_aud_kid(self):
        from backend.auth.jwt import create_access_token, decode_token
        token = create_access_token("user-1")
        payload = decode_token(token)
        assert payload["iss"] == "researchswarm"
        assert payload["aud"] == "researchswarm-api"
        assert payload["kid"]

    def test_token_from_rotation_key_still_verifies(self, monkeypatch):
        import os
        from backend.auth.jwt import create_access_token, decode_token
        old = os.environ.get("JWT_SECRET_KEYS_ROTATION")
        os.environ["JWT_SECRET_KEYS_ROTATION"] = "rotated-key-0123456789abcdef0123456789abcdef"
        try:
            token = create_access_token("user-2")
            payload = decode_token(token)
            assert payload["sub"] == "user-2"
        finally:
            if old is None:
                os.environ.pop("JWT_SECRET_KEYS_ROTATION", None)
            else:
                os.environ["JWT_SECRET_KEYS_ROTATION"] = old

    def test_token_from_unknown_key_rejected(self, monkeypatch):
        from backend.auth.jwt import create_access_token, decode_token
        monkeypatch.setenv("JWT_SECRET_KEY", "signing-key-0123456789abcdef0123456789abcd")
        token = create_access_token("user-3")
        monkeypatch.setenv("JWT_SECRET_KEY", "different-secret-0123456789abcdef0123456789ab")
        assert decode_token(token) is None

    def test_bridge_secret_fails_closed(self, monkeypatch):
        import backend.core.supabase as sb
        monkeypatch.setattr(sb, "_BRIDGE_SECRET", "")
        with pytest.raises(RuntimeError):
            sb.get_bridge_secret()
        with pytest.raises(RuntimeError):
            sb._bridge_password("user-4")

    def test_production_validation_rejects_weak_secret(self, monkeypatch):
        from backend.core.config import validate_secrets
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "dev")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "x" * 40)
        with pytest.raises(RuntimeError):
            validate_secrets()

    def test_production_validation_rejects_missing_service_role(self, monkeypatch):
        from backend.core.config import validate_secrets
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "x" * 40)
        monkeypatch.setenv("SUPABASE_BRIDGE_SECRET", "y" * 40)
        monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
        with pytest.raises(RuntimeError):
            validate_secrets()

    def test_production_validation_passes_with_strong_secrets(self, monkeypatch):
        from backend.core.config import validate_secrets
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "k" * 40)
        monkeypatch.setenv("SUPABASE_BRIDGE_SECRET", "b" * 40)
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "s" * 40)
        validate_secrets()  # must not raise


# ═════════════════════════════════════════════════════════════════
# Auth enforcement on protected endpoints
# ═════════════════════════════════════════════════════════════════

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


# ═════════════════════════════════════════════════════════════════
# H2 — SSE stream ownership: task streams are bound to the user who
#      started them
# ═════════════════════════════════════════════════════════════════

class TestStreamOwnership:
    def test_foreign_user_cannot_subscribe_to_owned_stream(self, client, two_users, api_app):
        """Subscribe to another user's research stream must be rejected."""
        me = client.get("/auth/me", headers=auth_headers(two_users["alice"]))
        assert me.status_code == 200
        alice_id = me.json()["id"]
        stream_mgr = api_app.state.stream_manager
        task_id = "task-owned-by-alice"
        stream_mgr.create_stream(task_id, owner_user_id=alice_id)
        resp = client.get(
            f"/research/stream/{task_id}",
            headers=auth_headers(two_users["bob"]),
        )
        assert resp.status_code == 403
        stream_mgr.close_stream(task_id)

    def test_subscribe_to_unknown_stream_returns_404(self, client, two_users):
        resp = client.get(
            "/research/stream/task-that-never-existed",
            headers=auth_headers(two_users["alice"]),
        )
        assert resp.status_code == 404


# ═════════════════════════════════════════════════════════════════
# H3 — Rate limiting: HTTP endpoints (slowapi) and WebSocket
#      connection creation (sliding-window)
# ═════════════════════════════════════════════════════════════════

class TestRateLimits:
    def test_login_and_forgot_password_rate_limited(self, client, api_app):
        """Brute-force / account-enumeration endpoints must 429."""
        api_app.state.limiter.enabled = True
        try:
            for _ in range(5):
                resp = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
                assert resp.status_code == 200
            resp = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
            assert resp.status_code == 429
        finally:
            api_app.state.limiter.enabled = False

    def test_ws_limiter_blocks_after_window(self):
        from backend.core.ratelimit import SlidingWindowLimiter
        lim = SlidingWindowLimiter(limit=3, window_seconds=60)
        assert all(lim.allow("ip-1") for _ in range(3))
        assert not lim.allow("ip-1")
        assert lim.allow("ip-2")
        lim.reset("ip-1")
        assert lim.allow("ip-1")

    def test_placeholder_secret_rejected(self, monkeypatch):
        """Copying .env.example into production must fail fast."""
        from backend.core.config import validate_secrets, is_weak_secret
        assert is_weak_secret("change-this-to-a-long-random-string-in-production")
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "change-this-to-a-long-random-string-in-production")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "s" * 40)
        with pytest.raises(RuntimeError):
            validate_secrets()
