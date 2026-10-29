"""Tests for search providers (DuckDuckGo, Bing, Serper, fallback).

Split from backend/tests/test_realtime_stream_infra.py.
"""

from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from backend.providers.search import (
    BingProvider,
    DuckDuckGoProvider,
    SerperProvider,
    _clean_url,
    _fallback_search,
    _format_results,
)


def asyncio_run(coroutine):
    return asyncio.run(coroutine)


class FakeHttpResponse:
    def __init__(self, payload=None, text="", error=None):
        self.payload = payload or {}
        self.text = text
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.payload


class FakeDDGS:
    results = []
    error = None
    calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def text(self, *args, **kwargs):
        FakeDDGS.calls.append((args, kwargs))
        if FakeDDGS.error:
            raise FakeDDGS.error
        return FakeDDGS.results


class TestSearchProviders:
    def test_clean_url_and_format_results(self):
        assert _clean_url("") == ""
        assert _clean_url("https://a.test/x") == "https://a.test/x"
        assert _clean_url("a.test/x") == "https://a.test/x"
        assert (
            _clean_url("https://a.test/x?utm_source=y&ref=z&q=1")
            == "https://a.test/x?q=1"
        )

        formatted = _format_results(
            [
                {"href": "a.test", "title": "A", "body": "Snippet"},
                {"href": "", "title": "skip"},
                {"href": "b.test", "title": "B"},
            ],
            "duckduckgo",
        )
        assert [item["url"] for item in formatted] == [
            "https://a.test",
            "https://b.test",
        ]
        assert formatted[0]["position"] == 1
        assert formatted[1]["position"] == 3
        assert formatted[1]["snippet"] == ""

    def test_duckduckgo_uses_first_successful_backend(self, monkeypatch):
        FakeDDGS.results = [
            {"href": "example.com/page", "title": "Example", "body": "Body"}
        ]
        FakeDDGS.error = None
        FakeDDGS.calls = []
        monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=FakeDDGS))

        provider = DuckDuckGoProvider()
        results = asyncio_run(provider.search("query", max_results=2, region="us-en"))

        assert results[0]["source"] == "duckduckgo"
        assert results[0]["url"] == "https://example.com/page"
        assert FakeDDGS.calls[0][1]["backend"] == "html"

    def test_duckduckgo_falls_back_when_packages_missing(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "ddgs", None)
        monkeypatch.setitem(sys.modules, "duckduckgo_search", None)
        with patch(
            "backend.providers.search._fallback_search",
            AsyncMock(return_value=[{"title": "fallback"}]),
        ) as fallback:
            results = asyncio_run(DuckDuckGoProvider().search("query"))
        assert results == [{"title": "fallback"}]
        fallback.assert_awaited_once()

    def test_duckduckgo_retries_then_falls_back(self, monkeypatch):
        FakeDDGS.error = RuntimeError("backend down")
        FakeDDGS.results = []
        monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=FakeDDGS))
        with patch(
            "backend.providers.search.asyncio.sleep", AsyncMock()
        ) as sleep, patch(
            "backend.providers.search._fallback_search",
            AsyncMock(return_value=[]),
        ) as fallback:
            assert asyncio_run(DuckDuckGoProvider().search("query")) == []
        sleep.assert_awaited_once()
        fallback.assert_awaited_once()

    def test_bing_without_key_falls_back(self, monkeypatch):
        monkeypatch.delenv("BING_API_KEY", raising=False)
        with patch.object(
            DuckDuckGoProvider, "search", AsyncMock(return_value=[{"title": "ddg"}])
        ) as ddg:
            results = asyncio_run(BingProvider().search("query", max_results=3))
        assert results == [{"title": "ddg"}]
        ddg.assert_awaited_once()

    def test_bing_success_and_failure(self, monkeypatch):
        monkeypatch.setenv("BING_API_KEY", "key")
        response = FakeHttpResponse(
            {
                "webPages": {
                    "value": [
                        {"name": "One", "url": "https://one.test", "snippet": "S1"},
                        {"url": "https://two.test"},
                    ]
                }
            }
        )
        client = AsyncMock()
        client.get.return_value = response
        client.__aenter__.return_value = client
        client.__aexit__.return_value = False
        with patch("backend.providers.search.httpx.AsyncClient", return_value=client):
            results = asyncio_run(BingProvider().search("query", max_results=5))
        assert results[0]["title"] == "One"
        assert results[1]["title"] == "Result 2"
        assert (
            client.get.call_args.kwargs["headers"]["Ocp-Apim-Subscription-Key"] == "key"
        )

        response.error = RuntimeError("api down")
        with patch("backend.providers.search.httpx.AsyncClient", return_value=client):
            assert asyncio_run(BingProvider().search("query")) == []

    def test_serper_without_key_falls_back(self, monkeypatch):
        monkeypatch.delenv("SERPER_API_KEY", raising=False)
        with patch.object(
            DuckDuckGoProvider, "search", AsyncMock(return_value=[{"title": "ddg"}])
        ) as ddg:
            results = asyncio_run(SerperProvider().search("query"))
        assert results == [{"title": "ddg"}]
        ddg.assert_awaited_once()

    def test_serper_success_and_failure(self, monkeypatch):
        monkeypatch.setenv("SERPER_API_KEY", "key")
        response = FakeHttpResponse(
            {
                "organic": [
                    {"title": "One", "link": "https://one.test", "snippet": "S"},
                    {"link": "https://two.test"},
                ]
            }
        )
        client = AsyncMock()
        client.post.return_value = response
        client.__aenter__.return_value = client
        client.__aexit__.return_value = False
        with patch("backend.providers.search.httpx.AsyncClient", return_value=client):
            results = asyncio_run(SerperProvider().search("query"))
        assert results[0]["source"] == "serper"
        assert results[1]["title"] == "Result 2"

        response.error = RuntimeError("api down")
        with patch("backend.providers.search.httpx.AsyncClient", return_value=client):
            assert asyncio_run(SerperProvider().search("query")) == []

    def test_fallback_html_parsing_and_errors(self):
        response = FakeHttpResponse(
            text=(
                '<a href="https://one.test" class="result-link">One <b>Title</b></a>'
                '<a href="https://two.test" class="result-link">Two</a>'
            )
        )
        client = MagicMock()
        client.get.return_value = response
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        with patch("backend.providers.search.httpx.Client", return_value=client):
            results = _fallback_search("query", max_results=1)
        assert len(results) == 1
        assert results[0]["title"] == "One Title"

        response.text = "<html>nothing</html>"
        with patch("backend.providers.search.httpx.Client", return_value=client):
            assert _fallback_search("query") == []

        response.error = RuntimeError("network down")
        with patch("backend.providers.search.httpx.Client", return_value=client):
            assert _fallback_search("query") == []
