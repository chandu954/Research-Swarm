"""Plugin registry — singleton for managing MCP-style integrations."""
from __future__ import annotations
from typing import Dict, Any, Optional, List
from loguru import logger

from backend.plugins.base import Plugin, PluginSpec


class PluginRegistry:
    """Central registry for all external integrations."""

    def __init__(self):
        self._plugins: Dict[str, Plugin] = {}
        self._specs: Dict[str, PluginSpec] = {}

    def register(self, plugin: Plugin) -> None:
        spec = plugin.spec()
        self._plugins[spec.name] = plugin
        self._specs[spec.name] = spec
        logger.info(f"Registered plugin: {spec.name} v{spec.version}")

    def get(self, name: str) -> Plugin:
        if name not in self._plugins:
            raise KeyError(f"Plugin '{name}' not registered")
        return self._plugins[name]

    def list_plugins(self) -> List[PluginSpec]:
        return list(self._specs.values())

    def execute(self, plugin_name: str, action: str, **kwargs: Any) -> Any:
        plugin = self.get(plugin_name)
        plugin.initialize()
        return plugin.execute(action, **kwargs)

    def is_configured(self, name: str) -> bool:
        try:
            return self.get(name).is_configured()
        except KeyError:
            return False


_registry: Optional[PluginRegistry] = None


def get_plugin_registry() -> PluginRegistry:
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
    return _registry


def reset_plugin_registry() -> None:
    global _registry
    _registry = None
