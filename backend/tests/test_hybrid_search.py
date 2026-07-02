"""Integration tests for hybrid search pipeline end-to-end."""
from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock
from backend.tools.search import hybrid_search_web, search_web


class TestHybridSearchWeb:
    @patch("backend.tools.search.search_web")
    def test_hybrid_search_uses_raw_search(self, mock_search):
        mock_search.return_value = [
            {"title": "Python", "snippet": "Python programming", "source": "test", "position": 1},
            {"title": "Java", "snippet": "Java programming", "source": "test", "position": 2},
        ]
        result = hybrid_search_web("Python", max_results=2)
        assert len(result) > 0
        mock_search.assert_called_once()

    @patch("backend.tools.search.search_web")
    def test_hybrid_search_empty_fallback(self, mock_search):
        mock_search.return_value = []
        result = hybrid_search_web("nothing", max_results=5)
        assert result == []

    @patch("backend.tools.search.search_web")
    def test_hybrid_search_with_rerank(self, mock_search):
        mock_search.return_value = [
            {"title": "Result A", "snippet": "Some content about the query topic", "source": "test", "position": 1},
            {"title": "Result B", "snippet": "Unrelated information here", "source": "test", "position": 2},
        ]
        result = hybrid_search_web("query topic", max_results=2)
        assert len(result) == 2
        # Should have hybrid scoring fields
        assert "hybrid_score" in result[0]
        assert "bm25_score" in result[0]
        assert "dense_score" in result[0]

    @patch("backend.tools.search.search_web")
    def test_hybrid_search_top_k(self, mock_search):
        mock_search.return_value = [
            {"title": f"Result {i}", "snippet": f"Snippet {i}", "source": "test", "position": i}
            for i in range(10)
        ]
        result = hybrid_search_web("test query", max_results=3)
        assert len(result) <= 3
