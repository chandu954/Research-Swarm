"""Tests for Weather plugin.

Split from backend/tests/test_realtime_stream_infra.py.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def asyncio_run(coroutine):
    return asyncio.run(coroutine)


class TestWeatherPlugin:
    def _plugin(self, units="metric"):
        from backend.plugins.weather import WeatherPlugin

        plugin = WeatherPlugin()
        plugin._units = units
        plugin._base_url = "https://weather.test/v1"
        plugin._client = AsyncMock()
        return plugin

    def test_initialize_and_cleanup(self):
        from backend.plugins.weather import WeatherPlugin

        plugin = WeatherPlugin()
        plugin._config = {"units": "imperial"}
        with patch("backend.plugins.weather.httpx.AsyncClient") as client_cls:
            asyncio_run(plugin.initialize())
        assert plugin._units == "imperial"
        client_cls.assert_called_once()
        plugin._client = AsyncMock()
        asyncio_run(plugin.cleanup())
        plugin._client.aclose.assert_awaited_once()

    def test_forecast_metric_and_imperial(self):
        response = MagicMock()
        response.json.return_value = {"current": {}}
        plugin = self._plugin()
        plugin._client.get.return_value = response

        assert asyncio_run(
            plugin.execute("forecast", {"latitude": 1.0, "longitude": 2.0})
        ) == {"current": {}}
        assert (
            plugin._client.get.call_args.kwargs["params"]["temperature_unit"]
            == "celsius"
        )

        imperial = self._plugin(units="imperial")
        imperial._client.get.return_value = response
        asyncio_run(imperial.execute("forecast", {"latitude": 1.0, "longitude": 2.0}))
        assert (
            imperial._client.get.call_args.kwargs["params"]["temperature_unit"]
            == "fahrenheit"
        )

    def test_geocode_and_unknown_action(self):
        response = MagicMock()
        response.json.return_value = {"results": [{"name": "Paris"}]}
        plugin = self._plugin()
        plugin._client.get.return_value = response

        assert asyncio_run(plugin.execute("geocode", {"city": "Paris"})) == {
            "results": [{"name": "Paris"}]
        }
        assert plugin._client.get.call_args.args[0].startswith("https://geocoding")

        with pytest.raises(ValueError, match="Unknown action"):
            asyncio_run(plugin.execute("storm", {}))
