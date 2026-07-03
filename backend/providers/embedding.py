"""Built-in embedding providers: Ollama, OpenRouter."""
from __future__ import annotations
import os
from typing import Any
from loguru import logger
import httpx

from backend.providers.base import EmbeddingProvider, ProviderInfo


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(base_url=self.base_url, timeout=60)
        return self._client

    def embed(self, texts: list[str], model: str | None = None, **kwargs: Any) -> list[list[float]] | None:
        if not texts:
            logger.warning("No texts provided for embedding")
            return None
        model = model or os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
        embeddings: list[list[float]] = []
        for i, text in enumerate(texts):
            try:
                response = self.client.post(
                    "/api/embeddings",
                    json={"model": model, "prompt": text, "truncate": True},
                )
                response.raise_for_status()
                data = response.json()
                embedding = data.get("embedding")
                if embedding:
                    embeddings.append(embedding)
                    if (i + 1) % 10 == 0:
                        logger.info(f"Embedded {i + 1}/{len(texts)} texts")
            except Exception as e:
                logger.error(f"Failed to create embedding for text {i}: {e}")
                embeddings.append([0.0] * 768)
        logger.info(f"Successfully created {len(embeddings)} embeddings")
        return embeddings if embeddings else None

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(name="ollama", description="Ollama local embeddings")


class OpenRouterEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=60.0)
        return self._client

    def embed(self, texts: list[str], model: str | None = None, **kwargs: Any) -> list[list[float]] | None:
        if not texts:
            logger.warning("No texts provided for embedding")
            return None
        model = model or os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        embeddings: list[list[float]] = []
        for text in texts:
            payload = {"model": model, "input": text}
            try:
                response = self.client.post(
                    "https://openrouter.ai/api/v1/embeddings",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()
                embeddings.append(data["data"][0]["embedding"])
            except Exception as e:
                logger.error(f"OpenRouter embedding failed: {e}")
                embeddings.append([0.0] * 768)
        logger.info(f"OpenRouter: created {len(embeddings)} embeddings")
        return embeddings if embeddings else None

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(name="openrouter", description="OpenRouter cloud embeddings")
