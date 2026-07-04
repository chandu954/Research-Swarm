"""Text embedding tool — delegates to the plugin registry."""
from __future__ import annotations
from typing import Any
from loguru import logger

from backend.core.registry import get_plugin_registry


def get_embedding_client() -> Any:
    """Return the configured embedding provider from the plugin registry."""
    registry = get_plugin_registry()
    return registry.get_embedding()


def create_embeddings(
    texts: list[str],
    model: str | None = None,
    **kwargs: Any,
) -> list[list[float]] | None:
    """Create embeddings using the configured provider from the plugin registry."""
    registry = get_plugin_registry()
    provider = registry.get_embedding()
    if provider is None:
        logger.error("No embedding provider available")
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
