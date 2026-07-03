from __future__ import annotations
import os
from typing import Optional
from loguru import logger

from backend.llm.base import LLMProvider
from backend.llm.ollama_provider import OllamaProvider
from backend.llm.openrouter_provider import OpenRouterProvider
from backend.llm.context import get_llm_provider, get_planner_model, get_research_model, get_document_model, get_answer_model, ProviderOverrides
from backend.providers.registry import get_provider_registry


_providers: dict[str, LLMProvider] = {}


class FailoverProvider(LLMProvider):
    """Wraps two providers and fails over from primary to secondary on error."""

    def __init__(self, primary: LLMProvider, secondary: LLMProvider):
        self.primary = primary
        self.secondary = secondary

    def generate(self, prompt: str, model: str, system_prompt: Optional[str] = None, options: Optional[dict] = None) -> str:
        try:
            return self.primary.generate(prompt, model, system_prompt, options)
        except Exception as e:
            logger.warning(f"Primary provider failed, falling back: {e}")
            try:
                return self.secondary.generate(prompt, model, system_prompt, options)
            except Exception as e2:
                logger.error(f"Secondary provider also failed: {e2}")
                raise

    def create_embedding(self, model: str, text: str) -> list[float]:
        try:
            return self.primary.create_embedding(model, text)
        except Exception as e:
            logger.warning(f"Primary embedding failed, falling back: {e}")
            return self.secondary.create_embedding(model, text)


def get_llm_provider_instance(provider_name: Optional[str] = None) -> LLMProvider:
    name = (provider_name or get_llm_provider()).lower()
    failover = os.getenv("LLM_FAILOVER", "false").lower() == "true"

    cache_key = f"{name}_failover_{failover}"
    if cache_key in _providers:
        return _providers[cache_key]

    if name == "ollama":
        logger.info("Using Ollama provider (local models)")
        _providers[cache_key] = OllamaProvider()
    elif name == "openrouter":
        primary = OpenRouterProvider()
        if failover:
            logger.info("Using OpenRouter provider with Ollama failover")
            _providers[cache_key] = FailoverProvider(primary, OllamaProvider())
        else:
            logger.info("Using OpenRouter provider (cloud models)")
            _providers[cache_key] = primary
    else:
        # Try registry for custom LLM plugins
        registry = get_provider_registry()
        wrapper = registry.get_llm(name)
        if wrapper is not None:
            logger.info(f"Using LLM provider from registry: {name}")
            _providers[cache_key] = wrapper.inner
        else:
            raise ValueError(f"Unknown LLM provider: {name}. Available: {list(registry.list_llms().keys())}")

    return _providers[cache_key]


def resolve_model(agent: str, override: Optional[str] = None) -> str:
    if override:
        return override
    env_key = {
        "planner": get_planner_model,
        "research_agent": get_research_model,
        "document_agent": get_document_model,
        "answer_agent": get_answer_model,
    }.get(agent)
    if not env_key:
        return "qwen3:14b"
    return env_key()


def apply_provider_overrides(
    llm_provider: Optional[str] = None,
    planner_model: Optional[str] = None,
    research_model: Optional[str] = None,
    document_model: Optional[str] = None,
    answer_model: Optional[str] = None,
    openrouter_key: Optional[str] = None,
) -> ProviderOverrides:
    overrides = ProviderOverrides()
    overrides.apply(
        llm_provider=llm_provider,
        planner_model=planner_model,
        research_model=research_model,
        document_model=document_model,
        answer_model=answer_model,
        openrouter_key=openrouter_key,
    )
    clear_provider_cache()
    return overrides


def restore_provider_overrides(overrides: ProviderOverrides) -> None:
    overrides.restore()
    clear_provider_cache()


def clear_provider_cache() -> None:
    _providers.clear()
