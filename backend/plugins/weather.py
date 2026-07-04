"""Example plugin: Weather forecast via Open-Meteo (free, no API key needed)."""
from __future__ import annotations
from typing import Any
import httpx

from backend.plugins.base import Plugin
from backend.core.plugin import PluginSpec


class WeatherPlugin(Plugin):
    """Fetches weather data for a given location using Open-Meteo API."""

    @property
    def spec(self) -> PluginSpec:
        return PluginSpec(
            name="weather",
            version="1.0.0",
            description="Weather forecast plugin (free, Open-Meteo)",
            config_schema={
                "units": {
                    "type": "string",
                    "enum": ["metric", "imperial"],
                    "default": "metric",
                    "description": "Temperature units",
                },
            },
        )

    async def initialize(self) -> None:
        self._client = httpx.AsyncClient(timeout=10.0)
        self._base_url = "https://api.open-meteo.com/v1"
        self._units = self._config.get("units", "metric")

    async def cleanup(self) -> None:
        await self._client.aclose()

    async def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        if action == "forecast":
            return await self._forecast(
                latitude=params["latitude"],
                longitude=params["longitude"],
            )
        if action == "geocode":
            return await self._geocode(params["city"])
        raise ValueError(f"Unknown action: {action}. Supported: forecast, geocode")

    async def _forecast(self, latitude: float, longitude: float) -> dict[str, Any]:
        temp_unit = "fahrenheit" if self._units == "imperial" else "celsius"
        resp = await self._client.get(
            f"{self._base_url}/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "temperature_unit": temp_unit,
                "timezone": "auto",
                "forecast_days": 3,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def _geocode(self, city: str) -> dict[str, Any]:
        resp = await self._client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 5, "language": "en", "format": "json"},
        )
        resp.raise_for_status()
        return resp.json()
