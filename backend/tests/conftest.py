"""Pytest fixtures and configuration for ResearchSwarm tests."""
from __future__ import annotations
import asyncio
import pytest
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

from backend.agents.planner import Planner
from backend.agents.graph import create_research_graph, reset_graph
from backend.agents.memory import ConversationMemory, get_memory, ConversationTurn
from backend.tools.registry import ToolRegistry, get_registry, reset_registry


@pytest.fixture
def tool_registry() -> ToolRegistry:
    reset_registry()
    registry = get_registry()
    return registry


@pytest.fixture
def memory() -> ConversationMemory:
    mem = ConversationMemory(memory_dir="/tmp/test_memory")
    return mem


@pytest.fixture
def sample_plan_result(doc_id: str = "test_doc") -> list[dict]:
    return [
        {"step_id": 1, "agent": "research_agent", "action": "search_web", "description": "Search for info", "status": "pending"},
        {"step_id": 2, "agent": "document_agent", "action": "load_pdf", "description": "Load document", "status": "pending"},
        {"step_id": 3, "agent": "document_agent", "action": "retrieve_chunks", "description": "Retrieve chunks", "status": "pending"},
        {"step_id": 4, "agent": "answer_agent", "action": "generate_answer", "description": "Generate answer", "status": "pending"},
    ]


@pytest.fixture
def sample_web_results() -> list[dict]:
    return [
        {"title": "Test Result 1", "url": "https://example.com/1", "snippet": "This is test result one with relevant content about AI.", "source": "duckduckgo"},
        {"title": "Test Result 2", "url": "https://example.com/2", "snippet": "This is test result two with more research content.", "source": "duckduckgo"},
    ]


@pytest.fixture
def sample_document_chunks() -> list[dict]:
    return [
        {"content": "Machine learning is a subset of artificial intelligence. It involves training models on data.", "metadata": {"page_number": 1, "doc_id": "test_doc"}, "score": 0.95},
        {"content": "Deep learning uses neural networks with multiple layers to learn representations.", "metadata": {"page_number": 2, "doc_id": "test_doc"}, "score": 0.87},
    ]


@pytest.fixture
def sample_user() -> dict:
    return {
        "id": "test-user-id",
        "email": "test@example.com",
        "name": "Test User",
    }


# ── Async helpers ──────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Mock Ollama ────────────────────────────────────────────────

@pytest.fixture
def mock_ollama_generate():
    """Mock Ollama generate to return controlled responses."""
    with patch("backend.models.ollama.OllamaClient.generate") as mock:
        mock.return_value = '{"test": "response"}'
        yield mock


@pytest.fixture
def mock_ollama_embed():
    """Mock Ollama embedding to return a fake vector."""
    with patch("backend.models.ollama.OllamaClient.create_embedding") as mock:
        mock.return_value = [0.1] * 768
        yield mock


# ── Mock tool registry ─────────────────────────────────────────

@pytest.fixture
def registry_with_search(tool_registry) -> ToolRegistry:
    """Register a mock search tool."""
    async def mock_search(query: str, max_results: int = 5) -> list[dict]:
        return [
            {"title": "Mock Result", "url": "https://mock.com", "snippet": f"Mock result for {query}", "source": "mock"}
        ]
    tool_registry.register(
        "web_search",
        mock_search,
        MagicMock(name="web_search", description="Mock search"),
    )
    return tool_registry


@pytest.fixture
def registry_with_pdf(tool_registry) -> ToolRegistry:
    """Register a mock PDF loader."""
    def mock_load_pdf(file_path: str):
        return ("Mock PDF content with artificial intelligence and machine learning topics.", [{"page_number": 1, "text": "Mock PDF content"}])
    tool_registry.register(
        "load_pdf",
        mock_load_pdf,
        MagicMock(name="load_pdf", description="Mock PDF loader"),
    )
    return tool_registry


# ── Mock graph ─────────────────────────────────────────────────

@pytest.fixture
def research_graph():
    """Get a clean research graph for testing."""
    reset_graph()
    graph = create_research_graph()
    return graph
