"""Tests for embedding providers (Ollama, OpenRouter).

Split from backend/tests/test_realtime_stream_infra.py.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from backend.providers.embedding import (
    OllamaEmbeddingProvider,
    OpenRouterEmbeddingProvider,
)


def asyncio_run(coroutine):
    return asyncio.run(coroutine)


class TestEmbeddingProviders:
    def test_ollama_lifecycle_and_embedding_paths(self, monkeypatch):
        provider = OllamaEmbeddingProvider()
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test")
        with patch("backend.providers.embedding.httpx.Client") as client_cls:
            asyncio_run(provider.initialize())
        assert provider.base_url == "http://ollama.test"
        client_cls.assert_called_once()

        asyncio_run(provider.cleanup())
        assert provider._client is None

        assert provider.embed([]) is None
        with pytest.raises(RuntimeError):
            provider.embed(["text"])

        response = FakeHttpResponse({"embedding": [0.1, 0.2]})
        client = MagicMock()
        client.post.return_value = response
        provider._client = client
        assert provider.embed(["one", "two"], model="m") == [
            [0.1, 0.2],
            [0.1, 0.2],
        ]
        assert client.post.call_args.kwargs["json"]["truncate"] is True
        assert provider.embed_query("one", model="m") == [0.1, 0.2]

        response.payload = {}
        assert provider.embed(["one"]) is None

        response.error = RuntimeError("embedding failed")
        result = provider.embed(["one"])
        assert result == [[0.0] * 768]

        provider._client = None
        with pytest.raises(RuntimeError):
            provider.embed_query("one")

    def test_openrouter_lifecycle_and_embedding_paths(self, monkeypatch):
        provider = OpenRouterEmbeddingProvider()
        monkeypatch.setenv("OPENROUTER_API_KEY", "key")
        with patch("backend.providers.embedding.httpx.Client") as client_cls:
            asyncio_run(provider.initialize())
        assert provider.api_key == "key"
        client_cls.assert_called_once()

        asyncio_run(provider.cleanup())
        assert provider._client is None

        assert provider.embed([]) is None
        with pytest.raises(RuntimeError):
            provider.embed(["text"])

        response = FakeHttpResponse({"data": [{"embedding": [0.3]}]})
        client = MagicMock()
        client.post.return_value = response
        provider._client = client
        assert provider.embed(["one"]) == [[0.3]]
        assert provider.embed_query("one") == [0.3]
        assert client.post.call_args.kwargs["headers"]["Authorization"] == "Bearer key"

        response.error = RuntimeError("embedding failed")
        assert provider.embed(["one"]) == [[0.0] * 768]


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
