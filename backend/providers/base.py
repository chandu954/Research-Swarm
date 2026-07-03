from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderInfo:
    name: str
    description: str
    version: str = "1.0.0"
    config_schema: dict = field(default_factory=dict)


class SearchProvider(ABC):
    @abstractmethod
    def search(self, query: str, max_results: int = 5, **kwargs: Any) -> list[dict[str, Any]]:
        ...

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(name=type(self).__name__, description="")


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str], model: str | None = None, **kwargs: Any) -> list[list[float]] | None:
        ...

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(name=type(self).__name__, description="")
