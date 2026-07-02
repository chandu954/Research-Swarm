"""Tests for MCP plugin system."""
from __future__ import annotations
import pytest
from backend.plugins.base import Plugin, PluginSpec
from backend.plugins.registry import PluginRegistry, get_plugin_registry, reset_plugin_registry


class MockPlugin(Plugin):
    def spec(self) -> PluginSpec:
        return PluginSpec(
            name="test_plugin",
            description="Test plugin",
            version="1.0.0",
            config_schema={"key": "string"},
            actions=["greet", "echo"],
        )

    def execute(self, action: str, **kwargs):
        if action == "greet":
            return f"Hello, {kwargs.get('name', 'world')}!"
        if action == "echo":
            return kwargs
        raise ValueError(f"Unknown action: {action}")


class TestPluginBase:
    def test_spec(self):
        p = MockPlugin()
        spec = p.spec()
        assert spec.name == "test_plugin"
        assert "greet" in spec.actions
        assert "echo" in spec.actions

    def test_is_configured(self):
        p = MockPlugin(config={"key": "value"})
        assert p.is_configured()

        p2 = MockPlugin(config={})
        assert not p2.is_configured()

    def test_execute(self):
        p = MockPlugin()
        assert p.execute("greet", name="World") == "Hello, World!"
        assert p.execute("echo", foo="bar") == {"foo": "bar"}

    def test_initialize_once(self):
        p = MockPlugin()
        assert not p._initialized
        p.initialize()
        assert p._initialized
        p.initialize()  # should not raise
        assert p._initialized

    def test_list_actions(self):
        p = MockPlugin()
        assert p.list_actions() == ["greet", "echo"]


class TestPluginRegistry:
    def setup_method(self):
        reset_plugin_registry()

    def test_register_and_get(self):
        registry = get_plugin_registry()
        p = MockPlugin()
        registry.register(p)
        assert registry.get("test_plugin") is p

    def test_list_plugins(self):
        registry = get_plugin_registry()
        registry.register(MockPlugin())
        specs = registry.list_plugins()
        assert len(specs) == 1
        assert specs[0].name == "test_plugin"

    def test_execute_through_registry(self):
        registry = get_plugin_registry()
        p = MockPlugin()
        registry.register(p)
        result = registry.execute("test_plugin", "greet", name="Test")
        assert result == "Hello, Test!"

    def test_is_configured(self):
        registry = get_plugin_registry()
        p = MockPlugin(config={"key": "val"})
        registry.register(p)
        assert registry.is_configured("test_plugin")

    def test_is_configured_not_found(self):
        registry = get_plugin_registry()
        assert not registry.is_configured("nonexistent")

    def test_get_nonexistent(self):
        registry = get_plugin_registry()
        with pytest.raises(KeyError):
            registry.get("nope")

    def test_cache_singleton(self):
        reset_plugin_registry()
        r1 = get_plugin_registry()
        r2 = get_plugin_registry()
        assert r1 is r2
