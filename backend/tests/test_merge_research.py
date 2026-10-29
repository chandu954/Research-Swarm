"""Tests for merge research helper.

Split from backend/tests/test_realtime_stream_infra.py.
"""

from __future__ import annotations

from backend.agents.merge import merge_research


class TestMergeResearch:
    def test_merges_and_deduplicates_web_and_documents(self):
        result = merge_research(
            [
                {"content": "same", "title": "A", "url": "https://a", "source": "bing"},
                {"snippet": "same", "title": "dup"},
                {"title": "title only"},
                {"content": "   ", "title": "blank"},
            ],
            [
                {"content": "doc", "filename": "paper.pdf", "page": 2},
                {"text": "same"},
                {"text": "second", "title": "Doc title"},
            ],
        )

        assert result["source_count"] == 4
        assert result["document_count"] == 3
        assert result["has_evidence"] is True
        assert [item["content"] for item in result["merged_evidence"]] == [
            "same",
            "title only",
            "doc",
            "second",
        ]
        assert result["merged_evidence"][0]["source"] == "bing"
        assert result["merged_evidence"][2]["title"] == "paper.pdf"
        assert result["merged_evidence"][3]["title"] == "Doc title"

    def test_empty_inputs(self):
        result = merge_research([], [])
        assert result == {
            "merged_evidence": [],
            "has_evidence": False,
            "source_count": 0,
            "document_count": 0,
        }
