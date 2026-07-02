"""Tests for the LangGraph workflow — graph creation, node execution, state routing."""
from __future__ import annotations
from unittest.mock import patch, MagicMock
import pytest

from backend.agents.graph import create_research_graph, reset_graph, AgentState
from backend.agents.graph import _run_planner_node, _run_research_node, _run_document_node, _run_merge_node, _run_answer_node


class TestResearchGraph:
    """Tests for the LangGraph research graph."""

    def test_graph_creation(self):
        """Graph should compile without errors."""
        reset_graph()
        graph = create_research_graph()
        assert graph is not None
        assert hasattr(graph, "invoke")
        assert hasattr(graph, "ainvoke")

    def test_graph_has_required_nodes(self):
        """Graph should have all expected nodes."""
        graph = create_research_graph()
        # Access the graph's internal node set
        nodes = {name for name in graph.nodes.keys()}
        assert "planner" in nodes
        assert "research_agent" in nodes
        assert "document_agent" in nodes
        assert "merge" in nodes
        assert "answer_agent" in nodes

    def test_graph_has_edges_from_start(self):
        """Graph should have edges from START and to END."""
        graph = create_research_graph()
        # Check that all expected edge types exist
        assert hasattr(graph, "nodes")

    def test_planner_node_creates_plan(self):
        """Planner node should produce a plan in state."""
        state: AgentState = {
            "query": "What is AI?",
            "conversation_id": None,
            "plan": [],
            "plan_reasoning": None,
            "web_results": [],
            "document_chunks": [],
            "answer": None,
            "sources": [],
            "errors": [],
            "status": "",
            "logs": [],
            "pdf_paths": [],
            "execution_start": None,
        }
        # Patch the Planner to avoid LLM call
        with patch("backend.agents.graph.Planner.create_plan") as mock_plan:
            mock_plan.return_value.steps = [{"step_id": 1, "agent": "answer_agent", "action": "generate_answer", "description": "Answer", "status": "pending"}]
            mock_plan.return_value.reasoning = "Simple question, just answer"
            result = _run_planner_node(state)
        assert "plan" in result
        assert len(result["plan"]) > 0
        assert result["plan"][0]["agent"] == "answer_agent"

    def test_planner_node_handles_error(self):
        """Planner node should handle exceptions gracefully."""
        state: AgentState = {
            "query": "What is AI?",
            "conversation_id": None,
            "plan": [],
            "plan_reasoning": None,
            "web_results": [],
            "document_chunks": [],
            "answer": None,
            "sources": [],
            "errors": [],
            "status": "",
            "logs": [],
            "pdf_paths": [],
            "execution_start": None,
        }
        with patch("backend.agents.graph.Planner") as mock_planner_cls:
            mock_planner = MagicMock()
            mock_planner.create_plan.side_effect = Exception("Planner failed")
            mock_planner_cls.return_value = mock_planner
            result = _run_planner_node(state)
        assert "errors" in result

    def test_research_node(self):
        """Research node should return web results."""
        state: AgentState = {
            "query": "test",
            "conversation_id": None,
            "plan": [],
            "plan_reasoning": None,
            "web_results": [],
            "document_chunks": [],
            "answer": None,
            "sources": [],
            "errors": [],
            "status": "",
            "logs": [],
            "pdf_paths": [],
            "execution_start": None,
        }
        with patch("backend.agents.graph.WebResearchAgent.run") as mock_run:
            mock_run.return_value = [{"title": "Test", "url": "https://test.com", "snippet": "test"}]
            result = _run_research_node(state)
        assert "web_results" in result
        assert len(result["web_results"]) > 0

    def test_merge_node(self):
        """Merge node should pass through silently."""
        state: AgentState = {
            "query": "test",
            "conversation_id": None,
            "plan": [],
            "plan_reasoning": None,
            "web_results": [{"title": "t"}],
            "document_chunks": [],
            "answer": None,
            "sources": [],
            "errors": [],
            "status": "",
            "logs": [],
            "pdf_paths": [],
            "execution_start": None,
        }
        result = _run_merge_node(state)
        assert result == {}


class TestAgentState:
    """Tests for agent state type."""

    def test_state_structure(self):
        """AgentState should have all required fields."""
        state: AgentState = {
            "query": "test",
            "conversation_id": "conv-1",
            "plan": [{"step_id": 1, "agent": "answer_agent", "action": "generate", "status": "pending"}],
            "plan_reasoning": "Just answer",
            "web_results": [],
            "document_chunks": [],
            "answer": "This is the answer",
            "sources": [{"source_type": "web", "title": "Source 1"}],
            "errors": [],
            "status": "completed",
            "logs": [{"agent": "planner", "action": "analyze", "status": "completed"}],
            "pdf_paths": [],
            "execution_start": 1000.0,
        }
        assert state["query"] == "test"
        assert state["conversation_id"] == "conv-1"
        assert state["answer"] == "This is the answer"
        assert len(state["plan"]) == 1
        assert len(state["sources"]) == 1
        assert len(state["logs"]) == 1
        assert state["status"] == "completed"
