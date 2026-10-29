"""Security regression suite — tenant isolation (C1)."""

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


class TestOrganizationLifecycle:
    def test_organization_and_membership_lifecycle(self, client):
        from uuid import uuid4

        owner_email = f"owner-{uuid4()}@example.com"
        owner = register(client, owner_email, "Org Owner")
        my_orgs(client, owner)

        created = client.post(
            "/organizations",
            headers=auth_headers(owner),
            json={
                "name": "Research Team",
                "slug": f"research-{uuid4().hex[:10]}",
                "description": "Initial",
            },
        )
        assert created.status_code == 201, created.text
        org = created.json()
        org_id = org["id"]
        org_headers = auth_headers(owner, org_id)
        assert org["member_count"] == 1

        duplicate = client.post(
            "/organizations",
            headers=auth_headers(owner),
            json={"name": org["name"], "slug": org["slug"]},
        )
        assert duplicate.status_code == 409

        details = client.get(f"/organizations/{org_id}", headers=org_headers)
        assert details.status_code == 200
        assert details.json()["member_count"] == 1
        updated = client.patch(
            f"/organizations/{org_id}",
            headers=org_headers,
            json={
                "name": "Updated Team",
                "description": "Updated",
                "avatar_url": "https://example.com/avatar.png",
            },
        )
        assert updated.status_code == 200
        assert updated.json()["name"] == "Updated Team"

        guest_email = f"guest-{uuid4()}@example.com"
        register(client, guest_email, "Guest")
        added = client.post(
            f"/organizations/{org_id}/members",
            headers=org_headers,
            json={"email": guest_email, "role": "researcher"},
        )
        assert added.status_code == 201, added.text
        member_id = added.json()["id"]
        assert added.json()["role"] == "researcher"
        assert (
            client.post(
                f"/organizations/{org_id}/members",
                headers=org_headers,
                json={"email": guest_email, "role": "viewer"},
            ).status_code
            == 409
        )
        assert (
            client.post(
                f"/organizations/{org_id}/members",
                headers=org_headers,
                json={"email": f"missing-{uuid4()}@example.com", "role": "viewer"},
            ).status_code
            == 404
        )

        members = client.get(f"/organizations/{org_id}/members", headers=org_headers)
        assert members.status_code == 200
        assert {item["email"] for item in members.json()} >= {owner_email, guest_email}
        assert (
            client.patch(
                f"/organizations/{org_id}/members/{member_id}",
                headers=org_headers,
                json={"role": "manager"},
            ).json()["role"]
            == "manager"
        )
        assert (
            client.patch(
                f"/organizations/{org_id}/members/missing",
                headers=org_headers,
                json={"role": "viewer"},
            ).status_code
            == 404
        )
        owner_member = next(item for item in members.json() if item["role"] == "owner")
        assert (
            client.patch(
                f"/organizations/{org_id}/members/{owner_member['id']}",
                headers=org_headers,
                json={"role": "admin"},
            ).status_code
            == 400
        )
        assert (
            client.delete(
                f"/organizations/{org_id}/members/{owner_member['id']}",
                headers=org_headers,
            ).status_code
            == 400
        )
        assert client.delete(
            f"/organizations/{org_id}/members/{member_id}", headers=org_headers
        ).json() == {"status": "removed"}
        assert (
            client.delete(
                f"/organizations/{org_id}/members/missing", headers=org_headers
            ).status_code
            == 404
        )

        assert client.delete(
            f"/organizations/{org_id}", headers=org_headers
        ).json() == {"status": "deleted"}
        assert (
            client.get(f"/organizations/{org_id}", headers=org_headers).status_code
            == 404
        )

    def test_workspace_and_project_lifecycle(self, client):
        from uuid import uuid4

        owner = register(
            client, f"workspace-owner-{uuid4()}@example.com", "Workspace Owner"
        )
        org = my_orgs(client, owner)[0]
        org_id = org["id"]
        headers = auth_headers(owner, org_id)

        created = client.post(
            f"/organizations/{org_id}/workspaces",
            headers=headers,
            json={"name": "Données / R&D"},
        )
        assert created.status_code == 201, created.text
        workspace = created.json()
        workspace_id = workspace["id"]
        assert workspace["slug"] == "donnees--rd"
        assert (
            client.post(
                f"/organizations/{org_id}/workspaces",
                headers=headers,
                json={"name": "Duplicate", "slug": workspace["slug"]},
            ).status_code
            == 409
        )
        listed_workspaces = client.get(
            f"/organizations/{org_id}/workspaces", headers=headers
        )
        assert listed_workspaces.status_code == 200
        assert workspace_id in {item["id"] for item in listed_workspaces.json()}
        assert (
            client.get(
                f"/organizations/{org_id}/workspaces/{workspace_id}", headers=headers
            ).status_code
            == 200
        )
        updated_workspace = client.patch(
            f"/organizations/{org_id}/workspaces/{workspace_id}",
            headers=headers,
            json={"name": "Updated Workspace", "description": "For regressions"},
        )
        assert updated_workspace.status_code == 200
        assert updated_workspace.json()["name"] == "Updated Workspace"
        assert (
            client.get(
                f"/organizations/{org_id}/workspaces/missing", headers=headers
            ).status_code
            == 404
        )

        project = client.post(
            f"/organizations/{org_id}/workspaces/{workspace_id}/projects",
            headers=headers,
            json={"name": "Démo Project"},
        )
        assert project.status_code == 201, project.text
        project_id = project.json()["id"]
        assert project.json()["slug"] == "demo-project"
        assert (
            client.post(
                f"/organizations/{org_id}/workspaces/{workspace_id}/projects",
                headers=headers,
                json={"name": "Duplicate", "slug": "demo-project"},
            ).status_code
            == 409
        )
        projects_url = f"/organizations/{org_id}/workspaces/{workspace_id}/projects"
        assert project_id in {
            item["id"] for item in client.get(projects_url, headers=headers).json()
        }
        project_url = f"{projects_url}/{project_id}"
        assert client.get(project_url, headers=headers).status_code == 200
        updated_project = client.patch(
            project_url,
            headers=headers,
            json={"name": "Renamed Project", "description": "Updated"},
        )
        assert updated_project.status_code == 200
        assert updated_project.json()["name"] == "Renamed Project"
        assert client.get(f"{projects_url}/missing", headers=headers).status_code == 404
        assert client.delete(project_url, headers=headers).json() == {
            "status": "deleted"
        }
        assert client.get(project_url, headers=headers).status_code == 404

        assert client.delete(
            f"/organizations/{org_id}/workspaces/{workspace_id}", headers=headers
        ).json() == {"status": "deleted"}
        assert (
            client.get(
                f"/organizations/{org_id}/workspaces/{workspace_id}", headers=headers
            ).status_code
            == 404
        )
        assert (
            client.delete(
                f"/organizations/{org_id}/workspaces/missing", headers=headers
            ).status_code
            == 404
        )
