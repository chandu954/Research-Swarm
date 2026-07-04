"""Parallel search aggregator — queries all registered search providers and merges results."""
from __future__ import annotations
import asyncio
from typing import Any
from loguru import logger

from backend.core.registry import get_plugin_registry
from backend.search.hybrid import hybrid_rerank


async def aggregate_search(
    query: str,
    max_results: int = 5,
    provider_filter: list[str] | None = None,
    hybrid: bool = True,
) -> list[dict[str, Any]]:
    """Query all registered search providers in parallel and merge results.

    Args:
        query: The search query.
        max_results: Maximum number of final results.
        provider_filter: If set, only query these provider names.
        hybrid: Whether to apply BM25+dense hybrid reranking.

    Returns:
        Deduplicated and reranked search results.
    """
    registry = get_plugin_registry()
    providers = registry.list_plugins("search")
    if not providers:
        logger.error("No search providers registered")
        return []

    tasks = []
    names = []
    for spec in providers:
        name = spec.name
        if provider_filter and name not in provider_filter:
            continue
        provider = registry.get_search(name)
        if provider is None:
            continue
        tasks.append(_run_search(provider, query, max_results))
        names.append(name)

    if not tasks:
        logger.warning("No search providers matched the filter")
        return []

    results_per_provider = await asyncio.gather(*tasks, return_exceptions=True)

    all_results: list[dict[str, Any]] = []
    for name, res in zip(names, results_per_provider):
        if isinstance(res, Exception):
            logger.warning(f"Search provider '{name}' failed: {res}")
            continue
        if not res:
            logger.info(f"Search provider '{name}' returned no results")
            continue
        for r in res:
            r["_provider"] = name
        all_results.extend(res)
        logger.info(f"Search provider '{name}' returned {len(res)} results")

    if not all_results:
        return []

    # Deduplicate by URL
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for r in all_results:
        url = r.get("url", "")
        if url and url not in seen:
            seen.add(url)
            deduped.append(r)

    logger.info(f"Aggregated {len(all_results)} raw results → {len(deduped)} unique")

    if hybrid:
        embed_fn = None
        embedding_provider = registry.get_embedding()
        if embedding_provider is not None and hasattr(embedding_provider, "embed_query"):
            embed_fn = lambda t: embedding_provider.embed_query(t)
        reranked = hybrid_rerank(query, deduped, bm25_weight=0.3, top_k=max_results, embed_fn=embed_fn)
        return reranked

    return deduped[:max_results]


async def _run_search(provider: Any, query: str, max_results: int) -> list[dict[str, Any]]:
    """Execute search on a single provider with a timeout."""
    try:
        result = await asyncio.wait_for(
            provider.search(query, max_results=max_results),
            timeout=15.0,
        )
        return result or []
    except asyncio.TimeoutError:
        logger.warning(f"Search provider timed out")
        return []
