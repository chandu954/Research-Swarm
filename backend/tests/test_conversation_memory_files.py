"""Tests for conversation memory files.

Split from backend/tests/test_memory_graph_plugins.py.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from backend.agents.memory import (
    ConversationMemory,
)
from backend.auth.tenant import TenantContext, _resolve_permissions
from backend.db.models import User


def asyncio_run(coroutine):
    return asyncio.run(coroutine)


NOW = datetime.now(timezone.utc)


def _user():
    return User(
        id="user-1",
        email="user@example.com",
        name="User",
        is_active=True,
        mfa_enabled=False,
        created_at=NOW,
        updated_at=NOW,
    )


def _ctx():
    return TenantContext(
        organization_id="org-1",
        organization_slug="org",
        user_id="user-1",
        user_role="owner",
        permissions=_resolve_permissions("owner"),
    )


@pytest.fixture
def memory(tmp_path):
    ConversationMemory._semantic_client = None
    ConversationMemory._semantic_collection = None
    return ConversationMemory(str(tmp_path))


class TestConversationMemoryFiles:
    def test_create_add_and_get_history(self, memory):
        conversation_id = memory.create_conversation({"topic": "RAG"})
        assert memory.get_history(conversation_id) == []
        assert memory.get_history("missing") == []

        memory.add_turn(conversation_id, "user", "hello")
        memory.add_turn(conversation_id, "assistant", "world")
        memory.add_turn(conversation_id, "user", "third")
        history = memory.get_history(conversation_id)
        assert len(history) == 3
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "hello"
