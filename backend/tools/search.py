"""Web search tool — delegates to the provider registry."""
from __future__ import annotations
import os
from typing import Any
from loguru import logger

from backend.providers.registry import get_provider_registry


def search_web(
    query: str,
    max_results: int = 5,
    region: str = "wt-wt",
    safesearch: str = "moderate",
) -> list[dict[str, Any]]:
    """Search the web using the configured search provider from the registry."""
    registry = get_provider_registry()
    provider = registry.get_search()
    if provider is None:
        logger.error(f"No search provider available (registered: {list(registry.list_searches().keys())})")
        return []
    return provider.search(query, max_results=max_results, region=region, safesearch=safesearch)


def hybrid_search_web(
    query: str,
    max_results: int = 5,
    region: str = "wt-wt",
    safesearch: str = "moderate",
) -> list[dict[str, Any]]:
    """Search + hybrid-rerank by BM25 + embedding relevance."""
    from backend.search.hybrid import hybrid_rerank
    from backend.providers.registry import get_provider_registry

    raw = search_web(query, max_results * 2, region, safesearch)
    if not raw:
        return []

    try:
        registry = get_provider_registry()
        llm = registry.get_llm()
        embed_fn = lambda t: llm.create_embedding(model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"), text=t) if llm else None
        reranked = hybrid_rerank(query, raw, bm25_weight=0.3, top_k=max_results, embed_fn=embed_fn)
        return reranked
    except Exception as e:
        logger.warning(f"Hybrid rerank failed, falling back to raw results: {e}")
        return raw[:max_results]
