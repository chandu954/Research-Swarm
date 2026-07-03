"""LLM provider wrappers that integrate existing LLM providers into the provider plugin system."""
from __future__ import annotations
from typing import Any
from loguru import logger

from backend.providers.base import ProviderInfo
from backend.llm.base import LLMProvider
from backend.llm.ollama_provider import OllamaProvider
from backend.llm.openrouter_provider import OpenRouterProvider


class LLMProviderWrapper:
    """Wraps an LLMProvider into the provider plugin system."""

    def __init__(self, name: str, provider: LLMProvider, description: str = "") -> None:
        self._name = name
        self._provider = provider
        self._description = description

    def generate(self, prompt: str, model: str, system_prompt: str | None = None, options: dict[str, Any] | None = None) -> str:
        return self._provider.generate(prompt, model, system_prompt, options)

    def create_embedding(self, model: str, text: str) -> list[float]:
        return self._provider.create_embedding(model, text)

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(name=self._name, description=self._description)

    @property
    def inner(self) -> LLMProvider:
        return self._provider


def get_builtin_llm_providers() -> dict[str, LLMProviderWrapper]:
    providers: dict[str, LLMProviderWrapper] = {}
    try:
        providers["ollama"] = LLMProviderWrapper(
            "ollama", OllamaProvider(), "Ollama local LLMs"
        )
        logger.info("Registered Ollama LLM provider")
    except Exception as e:
        logger.warning(f"Failed to register Ollama provider: {e}")

    try:
        providers["openrouter"] = LLMProviderWrapper(
            "openrouter", OpenRouterProvider(), "OpenRouter cloud LLMs"
        )
        logger.info("Registered OpenRouter LLM provider")
    except Exception as e:
        logger.warning(f"Failed to register OpenRouter provider: {e}")

    return providers
