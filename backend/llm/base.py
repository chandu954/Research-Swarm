"""LLM provider base — extends core provider with streaming support."""
from __future__ import annotations
from collections.abc import Generator
from typing import Any

from backend.core.providers.llm import LLMProvider as CoreLLMProvider
from backend.core.plugin import PluginSpec


class LLMProvider(CoreLLMProvider):
    spec: PluginSpec

    def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        raise NotImplementedError

    def generate_stream(
        self,
        prompt: str,
        model: str,
        system_prompt: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> Generator[str, None, None]:
        raise NotImplementedError

    def create_embedding(self, model: str, text: str) -> list[float]:
        raise NotImplementedError
