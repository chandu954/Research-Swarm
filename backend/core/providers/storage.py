"""Storage provider interface (files, documents)."""
from __future__ import annotations
from abc import abstractmethod
from typing import Any
from backend.core.plugin import PluginInterface, PluginSpec


class StorageProvider(PluginInterface):
    spec: PluginSpec

    @abstractmethod
    async def save(self, path: str, content: bytes) -> str:
        ...

    @abstractmethod
    async def load(self, path: str) -> bytes | None:
        ...

    @abstractmethod
    async def delete(self, path: str) -> bool:
        ...

    @abstractmethod
    async def exists(self, path: str) -> bool:
        ...
