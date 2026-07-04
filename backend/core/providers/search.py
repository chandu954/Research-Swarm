"""Search provider interface."""
from __future__ import annotations
from abc import abstractmethod
from typing import Any
from backend.core.plugin import PluginInterface, PluginSpec


class SearchProvider(PluginInterface):
    spec: PluginSpec

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 5,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        ...
