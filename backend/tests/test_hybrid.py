"""Tests for hybrid search pipeline (BM25 + dense fusion + reranking)."""
from __future__ import annotations
import pytest
from backend.search.hybrid import (
    build_bm25_index,
    bm25_scores,
    _cosine_similarity,
    fus_hybrid_score,
    hybrid_rerank,
)


class TestBM25:
    def test_build_index(self):
        docs = [
            {"title": "Python programming", "snippet": "Python is a versatile language"},
            {"title": "Machine learning", "snippet": "ML models need training data"},
            {"title": "Web development", "snippet": "Building web apps with frameworks"},
        ]
        bm25 = build_bm25_index(docs)
        assert bm25 is not None

        scores = bm25_scores(bm25, "Python programming", len(docs))
        assert len(scores) == 3
        # First doc should score highest for "python programming"
        assert scores[0] > scores[1]

    def test_empty_docs(self):
        assert build_bm25_index([]) is None

    def test_single_doc(self):
        docs = [{"title": "Only result", "snippet": "Single snippet"}]
        bm25 = build_bm25_index(docs)
        assert bm25 is not None
        scores = bm25_scores(bm25, "test", len(docs))
        assert len(scores) == 1


class TestCosineSimilarity:
    def test_identical(self):
        v = [1.0, 2.0, 3.0]
        assert _cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert _cosine_similarity(a, b) == pytest.approx(0.0)

    def test_empty(self):
        assert _cosine_similarity([], []) == 0.0
        assert _cosine_similarity([1.0], []) == 0.0

    def test_mismatched_lengths(self):
        assert _cosine_similarity([1.0], [1.0, 2.0]) == 0.0


class TestFusion:
    def test_pure_bm25(self):
        assert fus_hybrid_score(1.0, 0.0, bm25_weight=1.0) == 1.0

    def test_pure_dense(self):
        assert fus_hybrid_score(0.0, 1.0, bm25_weight=0.0) == 1.0

    def test_mixed(self):
        score = fus_hybrid_score(0.8, 0.2, bm25_weight=0.3)
        expected = 0.8 * 0.3 + 0.2 * 0.7
        assert score == pytest.approx(expected)


class TestHybridRerank:
    def test_empty_results(self):
        assert hybrid_rerank("test", []) == []

    def test_bm25_only_rerank(self):
        docs = [
            {"title": "Python guide", "snippet": "Python programming tutorial"},
            {"title": "Java guide", "snippet": "Java programming tutorial"},
        ]
        reranked = hybrid_rerank("Python", docs, bm25_weight=1.0)
        assert len(reranked) == 2
        assert reranked[0]["title"] == "Python guide"
        assert "hybrid_score" in reranked[0]
        assert "bm25_score" in reranked[0]
        assert "dense_score" in reranked[0]

    def test_top_k(self):
        docs = [
            {"title": f"Result {i}", "snippet": f"Snippet {i}"} for i in range(10)
        ]
        reranked = hybrid_rerank("test", docs, bm25_weight=1.0, top_k=3)
        assert len(reranked) == 3

    def test_partial_metadata(self):
        docs = [{"title": "Only title"}]
        reranked = hybrid_rerank("test", docs, bm25_weight=1.0)
        assert len(reranked) == 1
        assert reranked[0]["hybrid_score"] >= 0.0
