"""Embedding provider interface."""
from __future__ import annotations
from abc import abstractmethod
from typing import Any
from backend.core.plugin import PluginInterface, PluginSpec


class EmbeddingProvider(PluginInterface):
    spec: PluginSpec

    @abstractmethod
    def embed(
        self,
        texts: list[str],
        model: str | None = None,
        **kwargs: Any,
    ) -> list[list[float]] | None:
        ...

    @abstractmethod
    def embed_query(self, text: str, model: str | None = None) -> list[float] | None:
        ...
