"""LLM provider factory — resolves providers and models at runtime.

Providers are registered in the global PluginRegistry.  The factory
handles context-var overrides and provider caching.
"""
from __future__ import annotations
import os
from typing import Any
from loguru import logger

from backend.llm.base import LLMProvider
from backend.llm.context import (
    get_llm_provider,
    get_planner_model,
    get_research_model,
    get_document_model,
    get_answer_model,
    ProviderOverrides,
)
from backend.core.registry import get_plugin_registry


def get_llm_provider_instance(provider_name: str | None = None) -> LLMProvider:
    name = (provider_name or get_llm_provider()).lower()
    registry = get_plugin_registry()
    provider = registry.get_llm(name)
    if provider is not None:
        return provider
    raise ValueError(f"Unknown LLM provider: {name}. Available: {list(registry.list('llm').keys())}")


def resolve_model(agent: str, override: str | None = None) -> str:
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
    llm_provider: str | None = None,
    planner_model: str | None = None,
    research_model: str | None = None,
    document_model: str | None = None,
    answer_model: str | None = None,
) -> ProviderOverrides:
    overrides = ProviderOverrides()
    overrides.apply(
        llm_provider=llm_provider,
        planner_model=planner_model,
        research_model=research_model,
        document_model=document_model,
        answer_model=answer_model,
    )
    return overrides


def restore_provider_overrides(overrides: ProviderOverrides) -> None:
    overrides.restore()
