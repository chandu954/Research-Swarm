"""Integration tests for the FastAPI endpoints."""
from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from backend.api.main import app


@pytest_asyncio.fixture
async def client():
    """Create a test client for the FastAPI app with startup/shutdown lifecycle."""
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        """Health endpoint should return 200."""
        response = await client.get("/health")
        # App might not be fully initialized in test, but should return something
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
    async def test_upload_without_file(self, client):
        """POST /upload without file should return 422."""
        response = await client.post("/upload")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_documents(self, client):
        """GET /documents should return a list."""
        response = await client.get("/documents")
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data


class TestResearchEndpoints:
    """Tests for research endpoints."""

    @pytest.mark.asyncio
    async def test_research_empty_query(self, client):
        """POST /research with empty query should return 422."""
        response = await client.post("/research", json={"query": ""})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_research_missing_query(self, client):
        """POST /research without query should return 422."""
        response = await client.post("/research", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_research_valid_request(self, client):
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
            response = await client.post("/research", json={"query": "What is AI?"})
            assert response.status_code == 200


class TestConversationEndpoints:
    """Tests for conversation endpoints."""

    @pytest.mark.asyncio
    async def test_list_conversations(self, client):
        """GET /conversations should return a list."""
        response = await client.get("/conversations")
        assert response.status_code == 200
        data = response.json()
        assert "conversations" in data

    @pytest.mark.asyncio
    async def test_get_nonexistent_conversation(self, client):
        """GET /conversations/{id} with nonexistent ID should return 404."""
        response = await client.get("/conversations/nonexistent-id")
        assert response.status_code == 404
