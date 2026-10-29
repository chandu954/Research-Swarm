"""Security regression suite — document isolation (C2)."""

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


def my_orgs(client, tokens) -> list[dict]:
    resp = client.get("/organizations", headers=auth_headers(tokens))
    assert resp.status_code == 200, resp.text
    return resp.json()


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


class TestTenantIsolationRoutes:
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
