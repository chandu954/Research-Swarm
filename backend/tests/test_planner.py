"""Tests for the Planner agent — LLM-based plan generation, validation, and fallback."""
from __future__ import annotations
import json
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

from backend.agents.planner import Planner, PlanResult


class TestPlanner:
    """Unit tests for the planner agent."""

    def test_planner_initialization(self):
        """Planner should initialize without errors."""
        planner = Planner()
        assert planner is not None
        assert planner.llm is not None

    @patch("backend.agents.planner.get_llm_provider")
    def test_planner_returns_valid_plan(self, mock_get_provider, sample_plan_result):
        """Planner should parse valid JSON from the LLM."""
        mock_provider = MagicMock()
        mock_provider.generate.return_value = json.dumps([
            {"agent": "research_agent", "action": "search_web", "description": "Search for info"},
        ])
        mock_get_provider.return_value = mock_provider

        planner = Planner()
        result = planner.create_plan("What is the latest AI research?")

        assert isinstance(result, PlanResult)
        assert len(result.steps) == 2  # planner adds answer_agent when missing
        assert result.steps[0]["agent"] == "research_agent"
        assert result.steps[-1]["agent"] == "answer_agent"
        assert result.reasoning != ""

    @patch("backend.agents.planner.get_llm_provider")
    def test_planner_handles_malformed_json(self, mock_get_provider):
        """Planner should handle JSON embedded in text."""
        mock_provider = MagicMock()
        mock_provider.generate.return_value = 'Here is the plan:\n[\n{"agent": "research_agent", "action": "search_web", "description": "test"}\n]\n'
        mock_get_provider.return_value = mock_provider

        planner = Planner()
        result = planner.create_plan("Test query")
        assert len(result.steps) >= 1
        assert result.steps[0]["agent"] == "research_agent"

    @patch("backend.agents.planner.get_llm_provider")
    def test_planner_handles_non_json_output(self, mock_get_provider):
        """Planner should fall back when LLM returns non-JSON."""
        mock_provider = MagicMock()
        mock_provider.generate.return_value = "I think we should search the web and then answer."
        mock_get_provider.return_value = mock_provider

        planner = Planner()
        result = planner.create_plan("Test query")
        assert len(result.steps) >= 1
        assert result.steps[-1]["agent"] == "answer_agent"

    @patch("backend.agents.planner.get_llm_provider")
    def test_planner_fallback_on_ollama_error(self, mock_get_provider):
        """Planner should produce a fallback plan when Ollama fails."""
        mock_provider = MagicMock()
        mock_provider.generate.side_effect = Exception("Ollama not reachable")
        mock_get_provider.return_value = mock_provider

        planner = Planner()
        result = planner.create_plan("What is AI?")
        assert len(result.steps) >= 1
        assert result.steps[-1]["agent"] == "answer_agent"

    def test_planner_fallback_has_research_steps(self):
        """Fallback plan should include research for research-like queries."""
        planner = Planner()

        # Test with a query that has research keywords
        result = planner._fallback_plan("What is the latest AI research?")
        agents = [s["agent"] for s in result.steps]
        assert "research_agent" in agents
        assert "answer_agent" in agents

    def test_planner_fallback_has_document_steps(self):
        """Fallback plan should include document steps for PDF-related queries."""
        planner = Planner()
        result = planner._fallback_plan("Summarize this PDF document")
        agents = [s["agent"] for s in result.steps]
        assert "document_agent" in agents
        assert "answer_agent" in agents

    def test_planner_fallback_always_ends_with_answer(self):
        """All fallback plans should end with answer_agent."""
        planner = Planner()
        queries = [
            "Hello",
            "Compare this PDF with latest research",
            "What is AI?",
            "Search for climate change papers",
        ]
        for query in queries:
            result = planner._fallback_plan(query)
            assert result.steps[-1]["agent"] == "answer_agent", f"Failed for query: {query}"

    def test_planner_validates_steps(self):
        """Step validation should reject unknown agents and fix missing answer."""
        planner = Planner()
        steps = [
            {"agent": "unknown_agent", "action": "do_thing"},
            {"agent": "research_agent", "action": "search_web"},
        ]
        validated = planner._validate_steps(steps)
        agents = [s["agent"] for s in validated]
        assert "unknown_agent" not in agents
        assert validated[-1]["agent"] == "answer_agent"

    def test_planner_validates_empty_steps(self):
        """Validation should return fallback for empty input."""
        planner = Planner()
        validated = planner._validate_steps([])
        assert len(validated) >= 1
        assert validated[-1]["agent"] == "answer_agent"

    def test_parse_output_valid_json(self):
        """_parse_output should extract valid JSON arrays."""
        planner = Planner()
        text = '[{"agent": "research_agent", "action": "search", "description": "test"}]'
        steps, reasoning = planner._parse_output(text)
        assert len(steps) == 2  # answer_agent is appended
        assert steps[0]["agent"] == "research_agent"

    def test_parse_output_json_embedded(self):
        """_parse_output should extract JSON from surrounding text."""
        planner = Planner()
        text = 'Here is the output:\n[{"agent": "research_agent", "action": "search", "description": "test"}]\n'
        steps, reasoning = planner._parse_output(text)
        assert len(steps) >= 1
        assert steps[0]["agent"] == "research_agent"

    def test_parse_output_invalid(self):
        """_parse_output should return fallback for unparseable input."""
        planner = Planner()
        steps, reasoning = planner._parse_output("Just some random text without JSON")
        assert len(steps) >= 1  # fallback
