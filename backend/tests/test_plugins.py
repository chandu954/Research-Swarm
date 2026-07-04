"""Tests for PluginInterface and external integration plugins."""
from __future__ import annotations
import pytest
from backend.core.plugin import PluginInterface, PluginSpec
from backend.plugins.base import Plugin


class MockPlugin(Plugin):
    spec = PluginSpec(
        name="test_plugin",
        description="Test plugin",
        version="1.0.0",
        tags=["greet", "echo"],
    )

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True

    async def execute(self, action: str, **kwargs):
        if action == "greet":
            return f"Hello, {kwargs.get('name', 'world')}!"
        if action == "echo":
            return kwargs
        raise ValueError(f"Unknown action: {action}")


class TestPluginInterface:
    def test_spec(self):
        p = MockPlugin()
        assert p.spec.name == "test_plugin"
        assert "greet" in p.spec.tags

    def test_initialize(self):
        p = MockPlugin()
        assert not p._initialized
        import asyncio
        asyncio.run(p.initialize())
        assert p._initialized

    def test_execute_async(self):
        p = MockPlugin()
        import asyncio
        result = asyncio.run(p.execute("greet", name="World"))
        assert result == "Hello, World!"
        result = asyncio.run(p.execute("echo", foo="bar"))
        assert result == {"foo": "bar"}

    def test_list_actions(self):
        p = MockPlugin()
        assert p.list_actions() == ["greet", "echo"]


class TestExternalPlugins:
    def test_github_plugin_imports(self):
        from backend.plugins.github import GitHubPlugin
        p = GitHubPlugin()
        assert p.spec.name == "github"
        assert "search_issues" in p.spec.tags
        assert "get_repo" in p.spec.tags

    def test_notion_plugin_imports(self):
        from backend.plugins.notion import NotionPlugin
        p = NotionPlugin()
        assert p.spec.name == "notion"
        assert "query_database" in p.spec.tags

    def test_slack_plugin_imports(self):
        from backend.plugins.slack import SlackPlugin
        p = SlackPlugin()
        assert p.spec.name == "slack"
        assert "search_messages" in p.spec.tags

    def test_github_requires_token(self):
        from backend.plugins.github import GitHubPlugin
        p = GitHubPlugin()
        spec = p.spec
        assert isinstance(spec, PluginSpec)
        assert spec.version == "1.0.0"
