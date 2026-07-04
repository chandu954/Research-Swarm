"""DEPRECATED — unified provider registry.

This module is kept for backward compatibility. All new code should use
``backend.core.registry.PluginRegistry`` and ``get_plugin_registry()`` instead.

The compat shim delegates to ``PluginRegistry`` so old callers continue to work.
"""
from __future__ import annotations
import os
import warnings
from typing import Any
from loguru import logger

from backend.core.registry import get_plugin_registry as _new_registry


def _warn():
    warnings.warn(
        "providers.registry.get_provider_registry() is deprecated. "
        "Use core.registry.get_plugin_registry() instead.",
        DeprecationWarning,
        stacklevel=3,
    )


class ProviderRegistry:
    """DEPRECATED compat shim — delegates to PluginRegistry."""

    def __init__(self) -> None:
        self._initialized = False

    def register_search(self, name: str, provider: Any, default: bool = False) -> None:
        _warn()
        reg = _new_registry()
        reg.register(provider, "search", default=default)

    def register_embedding(self, name: str, provider: Any, default: bool = False) -> None:
        _warn()
        reg = _new_registry()
        reg.register(provider, "embedding", default=default)

    def register_llm(self, name: str, provider: Any, default: bool = False) -> None:
        _warn()
        reg = _new_registry()
        reg.register(provider, "llm", default=default)

    def get_search(self, name: str | None = None) -> Any:
        _warn()
        return _new_registry().get_search(name)

    def get_embedding(self, name: str | None = None) -> Any:
        _warn()
        return _new_registry().get_embedding(name)

    def get_llm(self, name: str | None = None) -> Any:
        _warn()
        return _new_registry().get_llm(name)

    def list_searches(self) -> dict[str, Any]:
        _warn()
        reg = _new_registry()
        return {s.spec.name: s for s in reg._plugins.get("search", {}).values()}

    def list_embeddings(self) -> dict[str, Any]:
        _warn()
        reg = _new_registry()
        return {s.spec.name: s for s in reg._plugins.get("embedding", {}).values()}

    def list_llms(self) -> dict[str, Any]:
        _warn()
        reg = _new_registry()
        return {s.spec.name: s for s in reg._plugins.get("llm", {}).values()}

    def list_all(self) -> dict[str, Any]:
        return {
            "search": self.list_searches(),
            "embedding": self.list_embeddings(),
            "llm": self.list_llms(),
        }

    def initialize_builtins(self) -> None:
        """No-op — builtins are initialized in _register_builtin_plugins()."""
        if self._initialized:
            return
        self._initialized = True
        logger.debug("ProviderRegistry.initialize_builtins() called (delegated)")

    def get_default_llm_inner(self) -> Any:
        _warn()
        wrapper = self.get_llm()
        if wrapper is None:
            raise ValueError("No LLM provider available")
        return wrapper

    def get_all_llm_inner(self) -> dict[str, Any]:
        _warn()
        reg = _new_registry()
        return reg._plugins.get("llm", {}).copy()


_registry: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    _warn()
    return _registry
