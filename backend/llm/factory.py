from __future__ import annotations
import os
from typing import Optional
from loguru import logger

from backend.llm.base import LLMProvider
from backend.llm.ollama_provider import OllamaProvider
from backend.llm.openrouter_provider import OpenRouterProvider


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


def get_llm_provider(provider_name: Optional[str] = None) -> LLMProvider:
    name = (provider_name or os.getenv("LLM_PROVIDER", "ollama")).lower()
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
        raise ValueError(f"Unknown LLM provider: {name}")

    return _providers[cache_key]


def resolve_model(agent: str, override: Optional[str] = None) -> str:
    if override:
        return override
    env_key = {
        "planner": "PLANNER_MODEL",
        "research_agent": "RESEARCH_MODEL",
        "document_agent": "DOCUMENT_MODEL",
        "answer_agent": "ANSWER_MODEL",
    }.get(agent)
    if not env_key:
        return "qwen3:14b"
    return os.getenv(env_key, "qwen3:14b")


def apply_provider_overrides(
    llm_provider: Optional[str] = None,
    planner_model: Optional[str] = None,
    research_model: Optional[str] = None,
    document_model: Optional[str] = None,
    answer_model: Optional[str] = None,
    openrouter_key: Optional[str] = None,
) -> dict:
    backup = {
        "LLM_PROVIDER": os.environ.get("LLM_PROVIDER", ""),
        "PLANNER_MODEL": os.environ.get("PLANNER_MODEL", ""),
        "RESEARCH_MODEL": os.environ.get("RESEARCH_MODEL", ""),
        "DOCUMENT_MODEL": os.environ.get("DOCUMENT_MODEL", ""),
        "ANSWER_MODEL": os.environ.get("ANSWER_MODEL", ""),
        "OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY", ""),
    }
    if llm_provider:
        os.environ["LLM_PROVIDER"] = llm_provider
    if planner_model:
        os.environ["PLANNER_MODEL"] = planner_model
    if research_model:
        os.environ["RESEARCH_MODEL"] = research_model
    if document_model:
        os.environ["DOCUMENT_MODEL"] = document_model
    if answer_model:
        os.environ["ANSWER_MODEL"] = answer_model
    if openrouter_key:
        os.environ["OPENROUTER_API_KEY"] = openrouter_key
    clear_provider_cache()
    return backup


def restore_provider_overrides(backup: dict) -> None:
    for key, val in backup.items():
        if val:
            os.environ[key] = val
        else:
            os.environ.pop(key, None)
    clear_provider_cache()


def clear_provider_cache() -> None:
    _providers.clear()
