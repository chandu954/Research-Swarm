"""LLM provider interface."""
from __future__ import annotations
from abc import abstractmethod
from collections.abc import Generator
from typing import Any
from backend.core.plugin import PluginInterface, PluginSpec


class LLMProvider(PluginInterface):
    spec: PluginSpec

    @abstractmethod
    def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        ...

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
