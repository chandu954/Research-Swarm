"""Integration tests for hybrid search pipeline end-to-end."""
from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock
from backend.tools.search import hybrid_search_web, search_web


class TestHybridSearchWeb:
    @patch("backend.search.aggregator.aggregate_search")
    def test_hybrid_search_uses_aggregator(self, mock_agg):
        mock_agg.return_value = [
            {"title": "Python", "snippet": "Python programming", "source": "test", "position": 1},
            {"title": "Java", "snippet": "Java programming", "source": "test", "position": 2},
        ]
        result = hybrid_search_web("Python", max_results=2)
        assert len(result) > 0
        mock_agg.assert_called_once()

    @patch("backend.search.aggregator.aggregate_search")
    def test_hybrid_search_empty_fallback(self, mock_agg):
        mock_agg.return_value = []
        # When aggregator returns empty, should fall through to search_web
        # We mock search_web to also return empty
        with patch("backend.tools.search.search_web", return_value=[]):
            result = hybrid_search_web("nothing", max_results=5)
            assert result == []

    @patch("backend.search.aggregator.aggregate_search")
    def test_hybrid_search_with_rerank(self, mock_agg):
        mock_agg.return_value = [
            {"title": "Result A", "snippet": "Some content about the query topic", "source": "test", "position": 1, "hybrid_score": 0.85, "bm25_score": 0.7, "dense_score": 0.9},
            {"title": "Result B", "snippet": "Unrelated information here", "source": "test", "position": 2, "hybrid_score": 0.3, "bm25_score": 0.2, "dense_score": 0.4},
        ]
        result = hybrid_search_web("query topic", max_results=2)
        assert len(result) == 2
        assert "hybrid_score" in result[0]
        assert "bm25_score" in result[0]
        assert "dense_score" in result[0]

    @patch("backend.search.aggregator.aggregate_search")
    def test_hybrid_search_passes_max_results(self, mock_agg):
        mock_agg.return_value = [
            {"title": f"Result {i}", "snippet": f"Snippet {i}", "source": "test", "position": i}
            for i in range(5)
        ]
        result = hybrid_search_web("test query", max_results=3)
        assert len(result) == 5
        mock_agg.assert_called_once()
        args, kwargs = mock_agg.call_args
        assert kwargs.get("max_results") == 3
        assert kwargs.get("hybrid") is True
