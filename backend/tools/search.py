"""Web search tool — uses the search aggregator for multi-provider results."""
from __future__ import annotations
import os
from typing import Any
from loguru import logger

from backend.core.registry import get_plugin_registry


def search_web(
    query: str,
    max_results: int = 5,
    region: str = "wt-wt",
    safesearch: str = "moderate",
) -> list[dict[str, Any]]:
    """Search using the default provider from the plugin registry."""
    registry = get_plugin_registry()
    provider = registry.get_search()
    if provider is None:
        logger.error("No search provider available")
        return []
    import asyncio
    try:
        return asyncio.run(provider.search(query, max_results=max_results))
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return []


def hybrid_search_web(
    query: str,
    max_results: int = 5,
    region: str = "wt-wt",
    safesearch: str = "moderate",
) -> list[dict[str, Any]]:
    """Aggregate search across all configured providers + hybrid rerank."""
    from backend.search.aggregator import aggregate_search
    import asyncio
    try:
        results = asyncio.run(
            aggregate_search(query, max_results=max_results, hybrid=True)
        )
        if results:
            return results
    except Exception as e:
        logger.warning(f"Aggregate search failed, falling back: {e}")

    registry = get_plugin_registry()
    provider = registry.get_search()
    if provider is None:
        return []
    try:
        raw = asyncio.run(provider.search(query, max_results=max_results * 2))
        if not raw:
            return []
        from backend.search.hybrid import hybrid_rerank
        llm = registry.get_llm()
        embed_fn = lambda t: llm.create_embedding(model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"), text=t) if llm else None
        return hybrid_rerank(query, raw, bm25_weight=0.3, top_k=max_results, embed_fn=embed_fn)
    except Exception as e:
        logger.warning(f"Fallback search failed: {e}")
        return []
