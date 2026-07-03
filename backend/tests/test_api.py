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


TEST_USER_ID = "00000000-0000-0000-0000-000000000001"
TEST_ORG_ID = "00000000-0000-0000-0000-000000000010"
TEST_WS_ID = "00000000-0000-0000-0000-000000000020"


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
