"""Text embedding tool — delegates to the provider registry."""
from __future__ import annotations
from typing import Any
from loguru import logger

from backend.providers.registry import get_provider_registry


def get_embedding_client() -> Any:
    """Return the configured embedding provider instance."""
    registry = get_provider_registry()
    return registry.get_embedding()


def create_embeddings(
    texts: list[str],
    model: str | None = None,
    **kwargs: Any,
) -> list[list[float]] | None:
    """Create embeddings using the configured provider from the registry."""
    registry = get_provider_registry()
    provider = registry.get_embedding()
    if provider is None:
        logger.error(f"No embedding provider available (registered: {list(registry.list_embeddings().keys())})")
        return None
    return provider.embed(texts, model=model, **kwargs)


def create_single_embedding(
    text: str,
    model: str | None = None,
    **kwargs: Any,
) -> list[float] | None:
    """Create a single embedding vector."""
    embeddings = create_embeddings([text], model=model, **kwargs)
    if embeddings and len(embeddings) > 0:
        return embeddings[0]
    return None
