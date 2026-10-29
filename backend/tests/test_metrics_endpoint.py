"""Tests for metrics endpoint.

Split from backend/tests/test_realtime_stream_infra.py.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import backend.api.metrics as metrics_module


def asyncio_run(coroutine):
    return asyncio.run(coroutine)


class TestMetricsEndpoint:
    def test_metrics_reports_plugins_and_uptime(self):
        class CallablePlugin:
            def name(self):
                return "callable"

            def version(self):
                return "2.0"

        plain = SimpleNamespace(name="plain", version="1.0")
        anonymous = object()
        registry = MagicMock()
        registry.list_types.return_value = ["llm", "search"]
        registry.list_plugins.side_effect = [
            [CallablePlugin(), plain],
            [anonymous],
        ]
        registry.is_configured.return_value = True

        with patch(
            "backend.api.metrics.get_plugin_registry", return_value=registry
        ), patch.object(metrics_module, "_start_time", 100.0), patch(
            "backend.api.metrics.time.time", return_value=105.4
        ):
            result = asyncio_run(metrics_module.metrics())

        assert result["status"] == "ok"
        assert result["uptime_seconds"] == 5
        assert result["plugins"]["llm"][0] == {
            "name": "callable",
            "version": "2.0",
            "configured": True,
        }
        assert result["plugins"]["llm"][1]["name"] == "plain"
        assert result["plugins"]["search"][0]["name"] == str(anonymous)
        assert result["plugins"]["search"][0]["version"] == "?"
