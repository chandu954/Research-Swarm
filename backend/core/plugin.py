"""Unified plugin interface for all ResearchSwarm extensions.

Every major system (LLM, search, embedding, vector DB, storage, OCR,
export, memory, auth) implements PluginInterface.  This allows the
registry, configuration, lifecycle, and discovery to be uniform.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PluginSpec:
    name: str
    description: str = ""
    version: str = "1.0.0"
    config_schema: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


class PluginInterface(ABC):
    """Base interface for every plugin in the system.

    Subclasses override the abstract methods and may add domain-specific
    methods (e.g. LLMProvider.generate, SearchProvider.search).
    """

    spec: PluginSpec

    @abstractmethod
    async def initialize(self) -> None:
        """Set up the plugin (clients, auth, lazy imports)."""

    async def cleanup(self) -> None:
        """Tear down resources."""

    def is_configured(self) -> bool:
        required = {k for k, v in self.spec.config_schema.items() if v.get("required")}
        return required.issubset(self.config.keys())

    @property
    def config(self) -> dict[str, Any]:
        return getattr(self, "_config", {})

    @config.setter
    def config(self, value: dict[str, Any]) -> None:
        self._config = value
