"""Health endpoint unit tests.

Split from backend/tests/test_api_routes_units.py.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from backend.tests._api_test_helpers import Session, _session_generator, asyncio_run
from fastapi.responses import JSONResponse


class TestHealthEndpoints:
    def _request(self):
        registry = MagicMock()
        registry.list_tools.return_value = [1, 2]
        app = SimpleNamespace(
            state=SimpleNamespace(
                start_time=100.0,
                registry=registry,
            )
        )
        return SimpleNamespace(app=app)

    def test_health_ok_with_openrouter_configured(self, monkeypatch):
        from backend.api.health import health_check

        monkeypatch.setenv("LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("OPENROUTER_API_KEY", "key")
        with patch(
            "backend.db.session.get_session", _session_generator(Session())
        ), patch("backend.api.health.get_plugin_registry") as registry, patch(
            "backend.api.health.time.time", return_value=105.0
        ):
            registry.return_value.list_types.return_value = ["llm"]
            result = asyncio_run(health_check(self._request()))

        assert result["status"] == "healthy"
        assert result["uptime"] == 5.0
        assert result["tools_available"] == 2
        assert result["checks"] == {"database": "ok", "openrouter": "ok"}

    def test_health_degraded_when_database_fails(self, monkeypatch):
        from backend.api.health import health_check

        monkeypatch.setenv("LLM_PROVIDER", "openrouter")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        def failing():
            raise RuntimeError("db down")

        with patch("backend.db.session.get_session", failing), patch(
            "backend.api.health.get_plugin_registry"
        ) as registry:
            registry.return_value.list_types.return_value = []
            result = asyncio_run(health_check(self._request()))

        assert result["status"] == "degraded"
        assert result["checks"]["database"] == "error: db down"
        assert result["checks"]["openrouter"] == "unconfigured"

    def test_health_checks_ollama(self, monkeypatch):
        from backend.api.health import health_check

        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        response = SimpleNamespace(status_code=200)
        client = AsyncMock()
        client.get.return_value = response
        client.__aenter__.return_value = client
        client.__aexit__.return_value = False

        with patch(
            "backend.db.session.get_session", _session_generator(Session())
        ), patch("backend.api.health.get_plugin_registry"), patch(
            "httpx.AsyncClient", return_value=client
        ):
            result = asyncio_run(health_check(self._request()))
        assert result["checks"]["ollama"] == "ok"

        response.status_code = 500
        with patch(
            "backend.db.session.get_session", _session_generator(Session())
        ), patch("backend.api.health.get_plugin_registry"), patch(
            "httpx.AsyncClient", return_value=client
        ):
            assert (
                asyncio_run(health_check(self._request()))["checks"]["ollama"]
                == "error"
            )

    def test_health_ollama_connection_error(self, monkeypatch):
        from backend.api.health import health_check

        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        with patch(
            "backend.db.session.get_session", _session_generator(Session())
        ), patch("backend.api.health.get_plugin_registry"), patch(
            "httpx.AsyncClient", side_effect=RuntimeError("down")
        ):
            result = asyncio_run(health_check(self._request()))
        assert result["checks"]["ollama"] == "error"

    def test_ready_ok_and_not_ready(self):
        from backend.api.health import ready_check

        with patch("backend.db.session.get_session", _session_generator(Session())):
            assert asyncio_run(ready_check(self._request())) == {"status": "ready"}

        with patch("backend.db.session.get_session", side_effect=RuntimeError("down")):
            response = asyncio_run(ready_check(self._request()))
        assert isinstance(response, JSONResponse)
        assert response.status_code == 503
