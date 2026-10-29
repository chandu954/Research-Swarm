"""Tests for graph helpers and nodes.

Split from backend/tests/test_memory_graph_plugins.py.
"""

from __future__ import annotations

from backend.agents import graph as graph_module


class TestGraphHelpers:
    def test_graph_module_exists(self):
        assert graph_module is not None


class TestGraphNodes:
    def test_graph_nodes_exist(self):
        assert graph_module is not None
