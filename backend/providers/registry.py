"""Unified provider registry — manages search, embedding, and LLM providers."""
from __future__ import annotations
import os
from typing import Any
from loguru import logger

from backend.providers.base import SearchProvider, EmbeddingProvider
from backend.providers.search import DuckDuckGoProvider, BingProvider, SerperProvider
from backend.providers.embedding import OllamaEmbeddingProvider, OpenRouterEmbeddingProvider
from backend.providers.llm import LLMProviderWrapper, get_builtin_llm_providers


class ProviderRegistry:
    """Singleton registry for all provider types."""

    def __init__(self) -> None:
        self._search: dict[str, SearchProvider] = {}
        self._embedding: dict[str, EmbeddingProvider] = {}
        self._llm: dict[str, LLMProviderWrapper] = {}
        self._default_search: str = "duckduckgo"
        self._default_embedding: str | None = None
        self._default_llm: str | None = None
        self._initialized = False

    def register_search(self, name: str, provider: SearchProvider, default: bool = False) -> None:
        self._search[name] = provider
        if default or self._default_search is None:
            self._default_search = name
        logger.info(f"Registered search provider: {name}")

    def register_embedding(self, name: str, provider: EmbeddingProvider, default: bool = False) -> None:
        self._embedding[name] = provider
        if default or self._default_embedding is None:
            self._default_embedding = name
        logger.info(f"Registered embedding provider: {name}")

    def register_llm(self, name: str, provider: LLMProviderWrapper, default: bool = False) -> None:
        self._llm[name] = provider
        if default or self._default_llm is None:
            self._default_llm = name
        logger.info(f"Registered LLM provider: {name}")

    def get_search(self, name: str | None = None) -> SearchProvider | None:
        key = name or os.getenv("SEARCH_BACKEND", self._default_search)
        return self._search.get(key)

    def get_embedding(self, name: str | None = None) -> EmbeddingProvider | None:
        key = name or self._default_embedding
        if key is None:
            key = "ollama" if "ollama" in self._embedding else next(iter(self._embedding), None)
        return self._embedding.get(key)

    def get_llm(self, name: str | None = None) -> LLMProviderWrapper | None:
        key = name or os.getenv("LLM_PROVIDER", self._default_llm)
        return self._llm.get(key)

    def list_searches(self) -> dict[str, Any]:
        return {n: {"description": p.info.description} for n, p in self._search.items()}

    def list_embeddings(self) -> dict[str, Any]:
        return {n: {"description": p.info.description} for n, p in self._embedding.items()}

    def list_llms(self) -> dict[str, Any]:
        return {n: {"description": p.info.description} for n, p in self._llm.items()}

    def list_all(self) -> dict[str, Any]:
        return {
            "search": self.list_searches(),
            "embedding": self.list_embeddings(),
            "llm": self.list_llms(),
        }

    def initialize_builtins(self) -> None:
        if self._initialized:
            return

        self.register_search("duckduckgo", DuckDuckGoProvider(), default=True)
        self.register_search("bing", BingProvider())
        self.register_search("serper", SerperProvider())

        try:
            self.register_embedding("ollama", OllamaEmbeddingProvider(), default=True)
        except Exception as e:
            logger.warning(f"Failed to register Ollama embedding: {e}")

        try:
            self.register_embedding("openrouter", OpenRouterEmbeddingProvider())
        except Exception as e:
            logger.warning(f"Failed to register OpenRouter embedding: {e}")

        llm_providers = get_builtin_llm_providers()
        for name, wrapper in llm_providers.items():
            self.register_llm(name, wrapper, default=(name == "openrouter"))

        self._initialized = True

    def get_default_llm_inner(self) -> Any:
        wrapper = self.get_llm()
        if wrapper is None:
            raise ValueError(f"No LLM provider available (providers: {list(self._llm.keys())})")
        return wrapper.inner

    def get_all_llm_inner(self) -> dict[str, Any]:
        return {n: w.inner for n, w in self._llm.items()}


_registry: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry
