"""Hybrid search: BM25 lexical + dense embedding fusion with cross-encoder reranking."""
from __future__ import annotations
import math
from typing import List, Dict, Any, Optional
from loguru import logger

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None


def build_bm25_index(documents: List[Dict[str, Any]]) -> Optional[BM25Okapi]:
    """Build a BM25 index from a list of result dicts with 'title' and 'snippet' keys."""
    if BM25Okapi is None:
        logger.warning("rank_bm25 not installed, skipping BM25")
        return None
    if not documents:
        return None
    corpus = [_bm25_tokenize(d.get("title", "") + " " + d.get("snippet", "")) for d in documents]
    return BM25Okapi(corpus)


def _bm25_tokenize(text: str) -> List[str]:
    return text.lower().split()


def bm25_scores(bm25: BM25Okapi, query: str, doc_count: int) -> List[float]:
    """Get BM25 scores for a query against all documents in the index."""
    tokens = _bm25_tokenize(query)
    scores = bm25.get_scores(tokens)
    # Normalize to 0-1 using sigmoid-like tanh
    normalized = [1.0 / (1.0 + math.exp(-s / 2.0)) for s in scores]
    return normalized


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def fus_hybrid_score(
    bm25_score: float,
    dense_score: float,
    bm25_weight: float = 0.3,
) -> float:
    """Fuse BM25 and dense scores with weighted combination."""
    return bm25_score * bm25_weight + dense_score * (1.0 - bm25_weight)


def hybrid_rerank(
    query: str,
    results: List[Dict[str, Any]],
    query_embedding: Optional[List[float]] = None,
    embed_fn=None,
    bm25_weight: float = 0.3,
    top_k: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Rerank results using hybrid BM25 + dense fusion.

    Args:
        query: The search query.
        results: List of result dicts with 'title', 'snippet', and optionally 'content'.
        query_embedding: Pre-computed query embedding (optional).
        embed_fn: Function to compute embedding if query_embedding not provided.
        bm25_weight: Weight for BM25 score (0.0 = pure dense, 1.0 = pure BM25).
        top_k: Number of top results to return.

    Returns:
        Reranked results with 'hybrid_score' field added.
    """
    if not results:
        return results

    logger.debug(f"Hybrid reranking {len(results)} results (BM25 weight={bm25_weight})")

    # BM25 scores
    bm25 = build_bm25_index(results)
    bm25_scores_list = bm25_scores(bm25, query, len(results)) if bm25 else [0.0] * len(results)

    # Dense scores: compute embeddings if needed
    if query_embedding is None and embed_fn is not None:
        try:
            query_embedding = embed_fn(query)
        except Exception as e:
            logger.debug(f"Embedding failed, falling back to BM25-only: {e}")
            query_embedding = None

    if query_embedding:
        dense_scores_list = []
        for r in results:
            content = r.get("content") or r.get("snippet") or r.get("title") or ""
            ctx = r.get("metadata", {})
            chunk_content = ctx.get("content") if isinstance(ctx, dict) else ""
            text = chunk_content or content
            try:
                if embed_fn:
                    r_emb = embed_fn(text[:2000])
                    dense_scores_list.append(_cosine_similarity(query_embedding, r_emb))
                else:
                    dense_scores_list.append(0.0)
            except Exception:
                dense_scores_list.append(0.0)
    else:
        dense_scores_list = [0.0] * len(results)

    # Fuse scores
    for i, r in enumerate(results):
        r["bm25_score"] = round(bm25_scores_list[i], 4) if bm25_scores_list[i] else 0.0
        r["dense_score"] = round(dense_scores_list[i], 4) if i < len(dense_scores_list) else 0.0
        r["hybrid_score"] = round(
            fus_hybrid_score(r["bm25_score"], r["dense_score"], bm25_weight), 4
        )

    results.sort(key=lambda x: x.get("hybrid_score", 0.0), reverse=True)

    if top_k:
        results = results[:top_k]

    logger.debug(f"Hybrid rerank complete. Top score: {results[0].get('hybrid_score', 0):.4f}")
    return results
