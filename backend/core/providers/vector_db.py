"""Vector database provider interface."""
from __future__ import annotations
from abc import abstractmethod
from typing import Any
from backend.core.plugin import PluginInterface, PluginSpec


class VectorDBProvider(PluginInterface):
    spec: PluginSpec

    @abstractmethod
    async def store(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]] | None = None,
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        ...

    @abstractmethod
    async def query(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def delete(self, ids: list[str]) -> None:
        ...
