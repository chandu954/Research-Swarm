"""Integration tests for hybrid search pipeline end-to-end."""
from __future__ import annotations
from unittest.mock import patch
from backend.tools.search import hybrid_search_web


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
        # When the aggregator returns empty, hybrid_search_web falls back to
        # the plugin-registry search provider; with no provider configured
        # it must return an empty list without hitting the network.
        with patch("backend.tools.search.get_plugin_registry") as mock_registry:
            mock_registry.return_value.get_search.return_value = None
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
