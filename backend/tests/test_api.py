"""Integration tests for the FastAPI endpoints."""
from __future__ import annotations
from datetime import datetime, timezone
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from backend.api.main import app
from backend.auth import dependencies as auth_deps
from backend.auth.tenant import resolve_tenant_dependencies, TenantContext
from backend.db.models import User


TEST_USER_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1"
TEST_ORG_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1"
TEST_WS_ID = "cccccccc-cccc-4ccc-8ccc-ccccccccccc1"


def _mock_user() -> User:
    return User(
        id=TEST_USER_ID,
        email="test@example.com",
        name="Test User",
        is_active=True,
        mfa_enabled=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


async def _override_get_current_user():
    return _mock_user()


async def _override_resolve_tenant():
    return TenantContext(
        organization_id=TEST_ORG_ID,
        organization_slug="test-org",
        workspace_id=TEST_WS_ID,
        project_id=None,
    )


@pytest_asyncio.fixture
async def client():
    """Create a test client (no auth overrides)."""
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest_asyncio.fixture
async def auth_client(client):
    """Create a test client with overridden auth dependencies."""
    app.dependency_overrides[auth_deps.get_current_user] = _override_get_current_user
    app.dependency_overrides[resolve_tenant_dependencies] = _override_resolve_tenant
    yield client
    app.dependency_overrides.clear()


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        """Health endpoint should return 200."""
        response = await client.get("/health")
        assert response.status_code in (200, 500)


class TestAuthEndpoints:
    """Tests for auth endpoints."""

    @pytest.mark.asyncio
    async def test_register_missing_fields(self, client):
        """Register without required fields should return 422."""
        response = await client.post("/auth/register", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_missing_fields(self, client):
        """Login without required fields should return 422."""
        response = await client.post("/auth/login", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_me_without_token(self, client):
        """GET /auth/me without token should return 401."""
        response = await client.get("/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_missing_token(self, client):
        """POST /auth/refresh without token should return 422."""
        response = await client.post("/auth/refresh", json={})
        assert response.status_code == 422


class TestDocumentEndpoints:
    """Tests for document endpoints."""

    @pytest.mark.asyncio
    async def test_upload_without_file(self, auth_client):
        """POST /upload without file should return 422."""
        response = await auth_client.post("/upload")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_documents(self, auth_client):
        """GET /documents should return a list."""
        response = await auth_client.get("/documents")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestResearchEndpoints:
    """Tests for research endpoints."""

    @pytest.mark.asyncio
    async def test_research_empty_query(self, auth_client):
        """POST /research with empty query should return 422."""
        response = await auth_client.post("/research", json={"query": ""})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_research_missing_query(self, auth_client):
        """POST /research without query should return 422."""
        response = await auth_client.post("/research", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_research_valid_request(self, auth_client):
        """POST /research with valid request should be processed."""
        with patch("backend.api.main.create_research_graph") as mock_graph:
            mock_graph_instance = MagicMock()
            mock_graph_instance.ainvoke = AsyncMock(return_value={
                "answer": "Test answer",
                "sources": [],
                "plan": [],
                "logs": [],
                "status": "completed",
                "errors": [],
                "plan_reasoning": None,
            })
            mock_graph.return_value = mock_graph_instance
            response = await auth_client.post("/research", json={"query": "What is AI?"})
            assert response.status_code == 200


class TestConversationEndpoints:
    """Tests for conversation endpoints."""

    @pytest.mark.asyncio
    async def test_list_conversations(self, auth_client):
        """GET /conversations should return a list."""
        response = await auth_client.get("/conversations")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_nonexistent_conversation(self, auth_client):
        """GET /conversations/{id} with nonexistent ID should return 404."""
        response = await auth_client.get("/conversations/nonexistent-id")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_conversation_create_read_update_and_soft_delete(self, auth_client):
        created = await auth_client.post(
            "/conversations", json={"title": "Coverage workflow"}
        )
        assert created.status_code == 201
        conversation_id = created.json()["id"]
        assert created.json()["title"] == "Coverage workflow"

        updated = await auth_client.patch(
            f"/conversations/{conversation_id}",
            json={
                "title": "Updated workflow",
                "description": "A regression test",
                "is_archived": True,
                "is_pinned": True,
                "is_favorited": True,
                "visibility": "private",
            },
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["title"] == "Updated workflow"
        assert updated.json()["is_archived"] is True
        assert updated.json()["is_pinned"] is True
        assert updated.json()["is_favorited"] is True

        unarchived = await auth_client.patch(
            f"/conversations/{conversation_id}", json={"is_archived": False}
        )
        assert unarchived.status_code == 200
        listed = await auth_client.get("/conversations?archived=false")
        assert conversation_id in {item["id"] for item in listed.json()}

        deleted = await auth_client.delete(f"/conversations/{conversation_id}")
        assert deleted.status_code == 200
        assert deleted.json() == {"status": "deleted"}
        listed = await auth_client.get("/conversations?archived=false")
        assert conversation_id not in {item["id"] for item in listed.json()}

    @pytest.mark.asyncio
    async def test_update_and_delete_unknown_conversation_return_404(self, auth_client):
        updated = await auth_client.patch(
            "/conversations/missing", json={"title": "No conversation"}
        )
        deleted = await auth_client.delete("/conversations/missing")
        assert updated.status_code == 404
        assert deleted.status_code == 404


class TestAPIKeyEndpoints:
    @pytest.mark.asyncio
    async def test_key_is_only_returned_at_creation_and_can_be_revoked(
        self, auth_client
    ):
        created = await auth_client.post(
            "/api-keys", json={"name": "automation", "permissions": ["research:read"]}
        )
        assert created.status_code == 201
        payload = created.json()
        assert payload["raw_key"].startswith("rs_")
        assert payload["key_prefix"] == payload["raw_key"][:8]

        listed = await auth_client.get("/api-keys")
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        assert "raw_key" not in listed.json()[0]

        deleted = await auth_client.delete(f"/api-keys/{payload['id']}")
        assert deleted.status_code == 200
        assert deleted.json() == {"status": "deleted"}
        assert (await auth_client.get("/api-keys")).json()[0]["is_active"] is False

    @pytest.mark.asyncio
    async def test_revoking_unknown_key_returns_404(self, auth_client):
        response = await auth_client.delete("/api-keys/missing")
        assert response.status_code == 404


class TestProviderEndpoints:
    @pytest.mark.asyncio
    async def test_provider_create_update_list_and_delete(self, auth_client):
        payload = {
            "name": "coverage-provider",
            "provider_type": "search",
            "provider_key": "duckduckgo",
            "config": {"region": "us"},
        }
        created = await auth_client.post("/providers", json=payload)
        assert created.status_code == 200
        provider_id = created.json()["id"]

        duplicate = await auth_client.post("/providers", json=payload)
        assert duplicate.status_code == 409
        fetched = await auth_client.get(f"/providers/{provider_id}")
        assert fetched.status_code == 200
        assert fetched.json()["config"] == {"region": "us"}

        updated = await auth_client.patch(
            f"/providers/{provider_id}",
            json={
                "name": "renamed-provider",
                "config": {"region": "eu"},
                "is_active": False,
            },
        )
        assert updated.status_code == 200
        assert updated.json()["name"] == "renamed-provider"
        assert updated.json()["is_active"] is False

        listed = await auth_client.get("/providers")
        assert listed.status_code == 200
        assert listed.json()["custom"] == []
        deleted = await auth_client.delete(f"/providers/{provider_id}")
        assert deleted.status_code == 200
        assert deleted.json() == {"status": "deleted"}
        assert (await auth_client.get(f"/providers/{provider_id}")).status_code == 404

    @pytest.mark.asyncio
    async def test_provider_rejects_invalid_type_and_unknown_update(self, auth_client):
        invalid = await auth_client.post(
            "/providers",
            json={"name": "bad", "provider_type": "unknown", "provider_key": "x"},
        )
        missing = await auth_client.patch(
            "/providers/missing", json={"is_active": False}
        )
        assert invalid.status_code == 422
        assert missing.status_code == 404


class TestPluginContractEndpoints:
    @pytest.mark.asyncio
    async def test_plugin_config_and_execution_follow_declared_contract(
        self, auth_client, monkeypatch
    ):
        from backend.api import main
        from backend.core.plugin import PluginSpec

        class Plugin:
            spec = PluginSpec(
                name="fixture",
                description="fixture plugin",
                version="1",
                tags=["echo"],
                config_schema={"token": str},
            )

            def __init__(self):
                self._config = {}

            def is_configured(self):
                return bool(self._config)

        plugin = Plugin()

        class Registry:
            def get(self, name):
                return plugin if name == "fixture" else None

            def list_plugins(self):
                return [plugin.spec]

            def is_configured(self, name):
                return name == "fixture" and plugin.is_configured()

            async def execute(self, name, action, **kwargs):
                return kwargs

        monkeypatch.setattr(main, "get_plugin_registry", lambda: Registry())

        listed = await auth_client.get("/plugins")
        assert listed.status_code == 200
        assert listed.json() == [
            {"name": "fixture", "configured": False, "actions": ["echo"], "error": None}
        ]

        unknown_plugin = await auth_client.post(
            "/plugins/missing/configure", json={"name": "missing", "config": {}}
        )
        undeclared = await auth_client.post(
            "/plugins/fixture/configure",
            json={"name": "fixture", "config": {"extra": "value"}},
        )
        assert unknown_plugin.status_code == 404
        assert undeclared.status_code == 422

        configured = await auth_client.post(
            "/plugins/fixture/configure",
            json={"name": "fixture", "config": {"token": "test"}},
        )
        assert configured.status_code == 200
        bad_action = await auth_client.post("/plugins/fixture/execute?action=delete")
        assert bad_action.status_code == 400
        executed = await auth_client.post(
            "/plugins/fixture/execute?action=echo", json={"message": "hello"}
        )
        assert executed.status_code == 200
        assert executed.json()["result"] == {"message": "hello"}


class TestBillingAndModelEndpoints:
    @pytest.mark.asyncio
    async def test_usage_is_tenant_scoped_and_audit_query_can_filter(self, auth_client):
        usage = await auth_client.get("/billing/usage")
        assert usage.status_code == 200
        assert usage.json()["tokens_in"] == 0
        assert usage.json()["estimated_cost"] == 0

        foreign_usage = await auth_client.get(
            "/billing/usage",
            params={"organization_id": "dddddddd-dddd-4ddd-8ddd-ddddddddddd1"},
        )
        assert foreign_usage.status_code == 403

        logs = await auth_client.get("/audit-logs", params={"action": "not-present"})
        assert logs.status_code == 200
        assert logs.json() == []

    @pytest.mark.asyncio
    async def test_models_endpoint_reports_missing_openrouter_key_and_unknown_provider(
        self, client, monkeypatch
    ):
        monkeypatch.setenv("LLM_PROVIDER", "openrouter")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        missing_key = await client.get("/models")
        assert missing_key.status_code == 200
        assert missing_key.json() == {
            "provider": "openrouter",
            "models": [],
            "error": "No API key configured",
        }

        monkeypatch.setenv("LLM_PROVIDER", "custom")
        custom = await client.get("/models")
        assert custom.status_code == 200
        assert custom.json()["provider"] == "custom"
        assert "available_providers" in custom.json()
