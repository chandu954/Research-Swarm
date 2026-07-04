"""Plugin ABC for MCP-style external integrations — extends core PluginInterface."""
from __future__ import annotations
from abc import abstractmethod
from typing import Any

from backend.core.plugin import PluginInterface, PluginSpec


class Plugin(PluginInterface):
    """Base class for external integrations (GitHub, Notion, Slack, etc.)."""

    spec: PluginSpec

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}

    @property
    def config(self) -> dict[str, Any]:
        return self._config

    @config.setter
    def config(self, value: dict[str, Any]) -> None:
        self._config = value

    async def initialize(self) -> None:
        pass

    @abstractmethod
    async def execute(self, action: str, **kwargs: Any) -> Any:
        ...

    def list_actions(self) -> list[str]:
        return list(self.spec.tags) if self.spec.tags else []
