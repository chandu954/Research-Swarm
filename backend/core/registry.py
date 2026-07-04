"""Unified plugin registry — single registry for all plugin types.

Replaces the separate provider/plugin registries with one consistent API.
"""
from __future__ import annotations
from typing import Any
from loguru import logger

from backend.core.plugin import PluginInterface, PluginSpec
from backend.core.providers.llm import LLMProvider
from backend.core.providers.search import SearchProvider
from backend.core.providers.embedding import EmbeddingProvider
from backend.core.providers.vector_db import VectorDBProvider
from backend.core.providers.storage import StorageProvider
from backend.core.providers.memory import MemoryProvider


PLUGIN_TYPE_KEY = "_plugin_type"


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, PluginInterface] = {}
        self._by_type: dict[str, dict[str, PluginInterface]] = {
            "llm": {},
            "search": {},
            "embedding": {},
            "vector_db": {},
            "storage": {},
            "memory": {},
            "external": {},
        }
        self._defaults: dict[str, str] = {}

    def register(
        self,
        plugin: PluginInterface,
        plugin_type: str | None = None,
        *,
        default: bool = False,
    ) -> None:
        name = plugin.spec.name
        self._plugins[name] = plugin
        ptype = plugin_type or getattr(plugin, PLUGIN_TYPE_KEY, "external")
        bucket = self._by_type.setdefault(ptype, {})
        bucket[name] = plugin
        if default or self._defaults.get(ptype) is None:
            self._defaults[ptype] = name
        logger.info(f"Registered {ptype} plugin: {name} v{plugin.spec.version}")

    def get(self, name: str) -> PluginInterface | None:
        return self._plugins.get(name)

    def get_typed(self, plugin_type: str, name: str | None = None) -> PluginInterface | None:
        bucket = self._by_type.get(plugin_type, {})
        if name:
            return bucket.get(name)
        default = self._defaults.get(plugin_type)
        return bucket.get(default) if default else next(iter(bucket.values()), None)

    def list(self, plugin_type: str | None = None) -> dict[str, PluginSpec]:
        if plugin_type:
            return {n: p.spec for n, p in self._by_type.get(plugin_type, {}).items()}
        return {n: p.spec for n, p in self._plugins.items()}

    def get_llm(self, name: str | None = None) -> LLMProvider | None:
        return self.get_typed("llm", name)  # type: ignore

    def get_search(self, name: str | None = None) -> SearchProvider | None:
        return self.get_typed("search", name)  # type: ignore

    def get_embedding(self, name: str | None = None) -> EmbeddingProvider | None:
        return self.get_typed("embedding", name)  # type: ignore

    def get_vector_db(self, name: str | None = None) -> VectorDBProvider | None:
        return self.get_typed("vector_db", name)  # type: ignore

    def get_storage(self, name: str | None = None) -> StorageProvider | None:
        return self.get_typed("storage", name)  # type: ignore

    def get_memory(self, name: str | None = None) -> MemoryProvider | None:
        return self.get_typed("memory", name)  # type: ignore

    def list_types(self) -> list[str]:
        return list(self._by_type.keys())

    def list_all(self) -> dict[str, Any]:
        return {ptype: {n: p.spec.description for n, p in bucket.items()}
                for ptype, bucket in self._by_type.items()}

    def list_plugins(self, type_filter: str | None = None) -> list[PluginSpec]:
        if type_filter:
            return [p.spec for p in self._by_type.get(type_filter, {}).values()]
        return list(self._plugins.values())

    def is_configured(self, name: str) -> bool:
        plugin = self._plugins.get(name)
        if plugin is None:
            return False
        spec = plugin.spec
        if spec.config_schema:
            return spec.config_schema.keys() <= plugin._config.keys()
        return True

    async def execute(self, name: str, action: str, **kwargs: Any) -> Any:
        plugin = self._plugins.get(name)
        if plugin is None:
            raise KeyError(f"Plugin '{name}' not found")
        if hasattr(plugin, "execute") and callable(getattr(plugin, "execute", None)):
            result = plugin.execute(action, **kwargs)
            if hasattr(result, "__await__"):
                return await result
            return result
        raise ValueError(f"Plugin '{name}' does not support execute")

    def set_default(self, plugin_type: str, name: str) -> None:
        if name in self._by_type.get(plugin_type, {}):
            self._defaults[plugin_type] = name


_registry: PluginRegistry | None = None


def get_plugin_registry() -> PluginRegistry:
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
    return _registry


def reset_plugin_registry() -> None:
    global _registry
    _registry = None
