"""Tests for OpenRouter LLM provider.

Split from backend/tests/test_realtime_stream_infra.py.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from backend.llm.openrouter_provider import OpenRouterProvider


def asyncio_run(coroutine):
    return asyncio.run(coroutine)


class TestOpenRouterProvider:
    def test_initialize_requires_key_and_cleanup(self, monkeypatch):
        provider = OpenRouterProvider()
        with patch(
            "backend.llm.openrouter_provider.get_openrouter_key", return_value=""
        ):
            with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
                asyncio_run(provider.initialize())

        with patch(
            "backend.llm.openrouter_provider.get_openrouter_key", return_value="key"
        ), patch("backend.llm.openrouter_provider.httpx.Client") as client_cls:
            asyncio_run(provider.initialize())
        assert provider.api_key == "key"
        client_cls.assert_called_once_with(timeout=60.0)

        client = provider._client
        asyncio_run(provider.cleanup())
        client.close.assert_called_once()
        assert provider._client is None

        with pytest.raises(RuntimeError, match="not initialized"):
            _ = provider.client

    def test_generate_once_builds_payload(self):
        provider = OpenRouterProvider()
        provider.api_key = "key"
        response = MagicMock()
        response.json.return_value = {
            "choices": [{"message": {"content": "  answer  "}}]
        }
        provider._client = MagicMock()
        provider._client.post.return_value = response

        result = provider._generate_once(
            "prompt",
            "model",
            system_prompt="system",
            options={"temperature": 0.7, "num_predict": 100},
        )
        assert result == "answer"
        payload = provider._client.post.call_args.kwargs["json"]
        assert payload["messages"][0] == {"role": "system", "content": "system"}
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 100

        provider._generate_once("prompt", "model")
        payload = provider._client.post.call_args.kwargs["json"]
        assert payload["messages"] == [{"role": "user", "content": "prompt"}]
        assert payload["temperature"] == 0.2
        assert payload["max_tokens"] == 4096

    def test_create_embedding_success_and_failure(self, monkeypatch):
        provider = OpenRouterProvider()
        provider.api_key = "key"
        provider._client = MagicMock()
        response = MagicMock()
        response.json.return_value = {"data": [{"embedding": [0.5]}]}
        provider._client.post.return_value = response

        assert provider.create_embedding("model", "text") == [0.5]
        monkeypatch.setenv("EMBEDDING_MODEL", "default-model")
        provider.create_embedding("", "text")
        assert (
            provider._client.post.call_args.kwargs["json"]["model"] == "default-model"
        )

        response.raise_for_status.side_effect = RuntimeError("embedding down")
        assert provider.create_embedding("model", "text") == []
