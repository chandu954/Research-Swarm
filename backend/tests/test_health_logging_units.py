"""Unit tests for the health/readiness endpoints and structured logging."""

from __future__ import annotations

import json
from typing import Any, Dict

import pytest
import pytest_asyncio
from backend.api.common import ensure_app_state
from backend.api.main import app
from backend.core.logging import JSONFormatter, setup_logging
from httpx import ASGITransport, AsyncClient
from loguru import logger


@pytest.fixture(autouse=True)
def _reset_logging_initialized():
    import backend.core.logging as logging_module

    previous = logging_module._initialized
    logging_module._initialized = False
    yield
    logging_module._initialized = previous


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest.mark.asyncio
async def test_health_returns_healthy(client, monkeypatch, tmp_path):
    ensure_app_state(app)
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("LOG_FILE", str(tmp_path / "test.log"))
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["version"] == "3.0.0"
    assert "uptime" in body
    assert isinstance(body["tools_available"], int)
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["openrouter"] == "unconfigured"


@pytest.mark.asyncio
async def test_ready_returns_ready(client):
    ensure_app_state(app)
    resp = await client.get("/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


def test_json_formatter_shape():
    record: Dict[str, Any] = {
        "level": type("Level", (), {"name": "INFO"})(),
        "name": "backend.api.health",
        "module": "health",
        "function": "health_check",
        "line": 42,
        "message": "database connection ok",
        "extra": {"request_id": "req_1"},
        "exception": None,
    }
    entry = JSONFormatter()(record)
    parsed = json.loads(entry)
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "backend.api.health"
    assert parsed["module"] == "health"
    assert parsed["function"] == "health_check"
    assert parsed["line"] == 42
    assert parsed["message"] == "database connection ok"
    assert parsed["extra"]["request_id"] == "req_1"
    assert "timestamp" in parsed


def test_setup_logging_text_format(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_FORMAT", "text")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FILE", str(tmp_path / "test.log"))
    setup_logging(json_format=False)
    setup_logging(json_format=False)
    assert logger._core.handlers


def test_setup_logging_json_format(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("LOG_FILE", str(tmp_path / "test.log"))
    setup_logging(json_format=True)
    assert logger._core.handlers
