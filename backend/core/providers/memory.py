"""Memory provider interface."""
from __future__ import annotations
from abc import abstractmethod
from typing import Any
from backend.core.plugin import PluginInterface, PluginSpec


class MemoryProvider(PluginInterface):
    spec: PluginSpec

    @abstractmethod
    async def store(self, key: str, value: Any, tags: list[str] | None = None) -> None:
        ...

    @abstractmethod
    async def retrieve(self, key: str) -> Any | None:
        ...

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        ...
