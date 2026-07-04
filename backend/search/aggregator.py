"""Parallel search aggregator — queries all registered search providers and merges results."""
from __future__ import annotations
import asyncio
import re
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlparse
from loguru import logger

from backend.core.registry import get_plugin_registry
from backend.search.hybrid import hybrid_rerank


def _normalize_url(url: str) -> str:
    """Normalize a URL for dedup: strip trailing slash, protocol, and www."""
    url = url.strip().rstrip("/")
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    if hostname.startswith("www."):
        hostname = hostname[4:]
    path = parsed.path.rstrip("/")
    return f"{hostname}{path}"


def _title_similarity(a: str, b: str) -> float:
    """Score how similar two titles are (0-1), used for content-based dedup."""
    a_clean = re.sub(r"[^a-z0-9\s]", "", a.lower()).strip()
    b_clean = re.sub(r"[^a-z0-9\s]", "", b.lower()).strip()
    if not a_clean or not b_clean:
        return 0.0
    if len(a_clean) < 8 or len(b_clean) < 8:
        return 0.0
    return SequenceMatcher(None, a_clean, b_clean).ratio()


def _domain(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _deduplicate(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate by URL exact match, then fuzzy title match (threshold 0.85)."""
    seen_urls: set[str] = set()
    seen_titles: list[str] = []
    deduped: list[dict[str, Any]] = []

    for r in results:
        url_raw = r.get("url", "")
        norm = _normalize_url(url_raw) if url_raw else ""

        # Exact URL dedup
        if norm and norm in seen_urls:
            continue
        if norm:
            seen_urls.add(norm)

        # Fuzzy title dedup (URL-less or similar title)
        title = r.get("title", "")
        is_duplicate = False
        for existing_title in seen_titles:
            if _title_similarity(title, existing_title) > 0.85:
                is_duplicate = True
                break
        if is_duplicate:
            continue
        seen_titles.append(title)

        deduped.append(r)

    return deduped


def _score_source_diversity(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Boost results from underrepresented domains; penalize same-domain clusters."""
    if not results:
        return results

    domain_counts: dict[str, int] = {}
    for r in results:
        d = _domain(r.get("url", ""))
        if d:
            domain_counts[d] = domain_counts.get(d, 0) + 1

    max_count = max(domain_counts.values()) if domain_counts else 1
    for r in results:
        d = _domain(r.get("url", ""))
        count = domain_counts.get(d, 1)
        diversity_penalty = 1.0 - (count - 1) / max_count * 0.3
        r["source_diversity_score"] = round(diversity_penalty, 4)

    return results


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

    deduped = _deduplicate(all_results)
    logger.info(f"Aggregated {len(all_results)} raw results → {len(deduped)} unique")

    deduped = _score_source_diversity(deduped)

    if hybrid:
        embed_fn = None
        embedding_provider = registry.get_embedding()
        if embedding_provider is not None and hasattr(embedding_provider, "embed_query"):
            embed_fn = lambda t: embedding_provider.embed_query(t)
        reranked = hybrid_rerank(query, deduped, bm25_weight=0.3, top_k=max_results, embed_fn=embed_fn)
        # Boost diverse sources on top of hybrid scores
        for r in reranked:
            div = r.get("source_diversity_score", 1.0)
            r["hybrid_score"] = round(r.get("hybrid_score", 0.0) * div, 4)
        reranked.sort(key=lambda x: x.get("hybrid_score", 0.0), reverse=True)
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
        logger.warning("Search provider timed out")
        return []
