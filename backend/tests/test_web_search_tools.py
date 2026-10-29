"""Tests for web search tools.

Split from backend/tests/test_realtime_stream_infra.py.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from backend.tools.search import hybrid_search_web, search_web


def asyncio_run(coroutine):
    return asyncio.run(coroutine)


class TestWebSearchTools:
    def _registry(self, provider):
        registry = MagicMock()
        registry.get_search.return_value = provider
        registry.get_llm.return_value = None
        return registry

    def test_search_web_without_provider_and_with_error(self):
        with patch(
            "backend.tools.search.get_plugin_registry",
            return_value=self._registry(None),
        ):
            assert search_web("query") == []

        provider = MagicMock()
        provider.search = AsyncMock(side_effect=RuntimeError("search down"))
        with patch(
            "backend.tools.search.get_plugin_registry",
            return_value=self._registry(provider),
        ):
            assert search_web("query") == []

    def test_search_web_returns_provider_results(self):
        provider = MagicMock()
        provider.search = AsyncMock(return_value=[{"title": "T"}])
        with patch(
            "backend.tools.search.get_plugin_registry",
            return_value=self._registry(provider),
        ):
            assert search_web("query", max_results=2) == [{"title": "T"}]

    def test_hybrid_search_returns_aggregated_results(self):
        with patch(
            "backend.search.aggregator.aggregate_search",
            AsyncMock(return_value=[{"title": "aggregated"}]),
        ):
            assert hybrid_search_web("query") == [{"title": "aggregated"}]

    def test_hybrid_search_falls_back_to_provider_and_reranks(self):
        provider = MagicMock()
        provider.search = AsyncMock(return_value=[{"title": "raw"}])
        registry = self._registry(provider)
        with patch(
            "backend.search.aggregator.aggregate_search",
            AsyncMock(side_effect=RuntimeError("aggregate down")),
        ), patch(
            "backend.search.hybrid.hybrid_rerank",
            return_value=[{"title": "reranked"}],
        ) as rerank, patch(
            "backend.tools.search.get_plugin_registry", return_value=registry
        ):
            results = hybrid_search_web("query", max_results=3)

        assert results == [{"title": "reranked"}]
        embed_fn = rerank.call_args.kwargs["embed_fn"]
        assert embed_fn("text") is None

    def test_hybrid_search_uses_llm_embeddings_and_handles_empty(self):
        provider = MagicMock()
        provider.search = AsyncMock(return_value=[{"title": "raw"}])
        llm = MagicMock()
        llm.create_embedding.return_value = [0.1]
        registry = self._registry(provider)
        registry.get_llm.return_value = llm

        captured = {}

        def fake_rerank(query, raw, **kwargs):
            captured.update(kwargs)
            return [{"title": "reranked"}]

        with patch(
            "backend.search.aggregator.aggregate_search",
            AsyncMock(return_value=[]),
        ), patch("backend.search.hybrid.hybrid_rerank", side_effect=fake_rerank), patch(
            "backend.tools.search.get_plugin_registry", return_value=registry
        ):
            assert hybrid_search_web("query") == [{"title": "reranked"}]
        assert captured["embed_fn"]("text") == [0.1]

        provider.search = AsyncMock(return_value=[])
        with patch(
            "backend.search.aggregator.aggregate_search",
            AsyncMock(return_value=[]),
        ), patch("backend.tools.search.get_plugin_registry", return_value=registry):
            assert hybrid_search_web("query") == []

        provider.search = AsyncMock(side_effect=RuntimeError("provider down"))
        with patch(
            "backend.search.aggregator.aggregate_search",
            AsyncMock(side_effect=RuntimeError("aggregate down")),
        ), patch("backend.tools.search.get_plugin_registry", return_value=registry):
            assert hybrid_search_web("query") == []
