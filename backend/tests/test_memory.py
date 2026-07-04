"""Tests for conversation memory module."""
from __future__ import annotations
import tempfile
import pytest

from backend.agents.memory import ConversationMemory


class TestConversationMemory:
    """Unit tests for conversation memory."""

    @pytest.fixture
    def memory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield ConversationMemory(memory_dir=tmpdir)

    def test_create_conversation(self, memory):
        """Creating a conversation should return a valid ID."""
        conv_id = memory.create_conversation(metadata={"source": "test"})
        assert conv_id is not None
        assert len(conv_id) > 0

    def test_add_turn(self, memory):
        """Adding a turn should persist it."""
        conv_id = memory.create_conversation()
        memory.add_turn(conv_id, "user", "Hello")
        memory.add_turn(conv_id, "assistant", "Hi there!")

        history = memory.get_history(conv_id)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Hi there!"

    def test_get_history_limits(self, memory):
        """get_history should respect max_turns."""
        conv_id = memory.create_conversation()
        for i in range(20):
            memory.add_turn(conv_id, "user", f"Message {i}")

        full = memory.get_history(conv_id, max_turns=100)
        assert len(full) == 20

        limited = memory.get_history(conv_id, max_turns=5)
        assert len(limited) == 5
        assert limited[0]["content"] == "Message 15"  # Most recent

    def test_get_nonexistent_conversation(self, memory):
        """Getting history for a nonexistent conversation should return [None]."""
        history = memory.get_history("nonexistent-id")
        assert history == []

    def test_list_conversations(self, memory):
        """list_conversations should return recent conversations."""
        conv1 = memory.create_conversation(metadata={"query": "First"})
        conv2 = memory.create_conversation(metadata={"query": "Second"})

        memory.add_turn(conv1, "user", "Hello")
        memory.add_turn(conv2, "user", "World")

        convs = memory.list_conversations(limit=10)
        assert len(convs) >= 2

    def test_delete_conversation(self, memory):
        """Deleting a conversation should remove it."""
        conv_id = memory.create_conversation()
        memory.add_turn(conv_id, "user", "Test")
        memory.delete_conversation(conv_id)
        history = memory.get_history(conv_id)
        assert history == []

    def test_persistence_across_instances(self, memory):
        """Conversations should persist to disk."""
        conv_id = memory.create_conversation()
        memory.add_turn(conv_id, "user", "Persist me")

        # Create new memory instance pointing to same directory
        memory2 = ConversationMemory(memory_dir=memory.memory_dir)
        history = memory2.get_history(conv_id)
        assert len(history) == 1
        assert history[0]["content"] == "Persist me"

    def test_add_turn_with_metadata(self, memory):
        """Turns should support custom metadata."""
        conv_id = memory.create_conversation()
        memory.add_turn(conv_id, "user", "Query", metadata={"task_id": "abc-123"})

        conv = memory.get_conversation(conv_id)
        assert conv is not None
        assert conv.turns[0].metadata["task_id"] == "abc-123"
