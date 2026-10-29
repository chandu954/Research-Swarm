"""Tests for WebSocket room lifecycle and presence.

Split from backend/tests/test_realtime_stream_infra.py.
"""

from __future__ import annotations

import json
import time
from unittest.mock import patch

from backend.api.websocket import (
    Connection,
    WorkspaceManager,
    WorkspaceRoom,
    get_workspace_manager,
)


def asyncio_run(coroutine):
    return __import__("asyncio").run(coroutine)


class FakeSocket:
    def __init__(self, fail=False):
        self.sent: list[str] = []
        self.fail = fail

    async def send_text(self, text: str):
        if self.fail:
            raise RuntimeError("socket closed")
        self.sent.append(text)


class TestWorkspaceRoomBranches:
    def test_typing_users_filters_stale_entries(self):
        room = WorkspaceRoom("ws-1")
        room.add(Connection(FakeSocket(), "user-1", "Alice"))
        room.add(Connection(FakeSocket(), "user-2", "Bob"))
        room._typing["user-1"] = time.time()
        room._typing["user-2"] = time.time() - 60
        room._typing["ghost"] = time.time() - 60

        active = room.typing_users

        assert active == [{"userId": "user-1", "name": "Alice"}]
        assert "user-2" not in room._typing
        assert "ghost" not in room._typing

    def test_handle_message_ignores_invalid_and_unknown_messages(self):
        room = WorkspaceRoom("ws-1")
        conn = Connection(FakeSocket(), "user-1", "Alice")
        room.add(conn)

        asyncio_run(room.handle_message("not-json", conn))
        asyncio_run(room.handle_message(json.dumps({"type": "unknown"}), conn))
        asyncio_run(room.handle_message(json.dumps({"type": "ping"}), conn))

        assert json.loads(conn.ws.sent[0]) == {"type": "pong"}

    def test_chat_send_ignores_empty_and_caps_history(self):
        room = WorkspaceRoom("ws-1")
        conn = Connection(FakeSocket(), "user-1", "Alice")
        room.add(conn)

        asyncio_run(room.handle_message(json.dumps({"type": "chat:send"}), conn))
        asyncio_run(
            room.handle_message(
                json.dumps({"type": "chat:send", "payload": {"content": "   "}}),
                conn,
            )
        )
        assert room.chat_messages == []

        for index in range(101):
            asyncio_run(
                room.handle_message(
                    json.dumps(
                        {
                            "type": "chat:send",
                            "payload": {"content": f"message-{index}"},
                        }
                    ),
                    conn,
                )
            )

        assert len(room.chat_messages) == 100
        assert room.chat_messages[0].content == "message-1"
        history = room.get_chat_history()
        assert len(history) == 50
        assert history[-1]["content"] == "message-100"

    def test_typing_broadcast_excludes_sender(self):
        room = WorkspaceRoom("ws-1")
        sender = Connection(FakeSocket(), "user-1", "Alice")
        other = Connection(FakeSocket(), "user-2", "Bob")
        room.add(sender)
        room.add(other)

        asyncio_run(
            room.handle_message(
                json.dumps({"type": "typing", "payload": {"isTyping": True}}), sender
            )
        )

        assert sender.ws.sent == []
        payload = json.loads(other.ws.sent[-1])
        assert payload["type"] == "typing"
        assert payload["payload"]["typingUsers"][0]["userId"] == "user-1"

        asyncio_run(
            room.handle_message(
                json.dumps({"type": "typing", "payload": {"isTyping": False}}), sender
            )
        )
        assert "user-1" not in room._typing

    def test_research_and_document_broadcasts(self):
        room = WorkspaceRoom("ws-1")
        socket = FakeSocket()
        room.add(Connection(socket, "user-1", "Alice"))

        asyncio_run(room.broadcast_research_start("u", "A", "task", "q" * 300))
        asyncio_run(room.broadcast_research_log("task", {"line": 1}))
        asyncio_run(room.broadcast_research_complete("task", "u"))
        asyncio_run(room.broadcast_document_added({"id": "doc"}))
        asyncio_run(room.broadcast_document_removed("doc"))

        types = [json.loads(item)["type"] for item in socket.sent]
        assert types == [
            "research:start",
            "research:log",
            "research:complete",
            "document:added",
            "document:removed",
        ]
        assert len(json.loads(socket.sent[0])["payload"]["query"]) == 200

    def test_broadcast_drops_stale_connections_and_swallows_send_errors(self):
        room = WorkspaceRoom("ws-1")
        good = Connection(FakeSocket(), "user-1", "Alice")
        bad = Connection(FakeSocket(fail=True), "user-2", "Bob")
        room.add(good)
        room.add(bad)

        asyncio_run(room.broadcast({"type": "test"}))
        assert "user-2" not in room.user_ids
        assert len(good.ws.sent) == 1

        asyncio_run(room._send(Connection(FakeSocket(fail=True), "x"), {"type": "x"}))

    def test_manager_presence_disconnect_and_singleton(self):
        manager = WorkspaceManager()
        asyncio_run(manager.broadcast_presence("missing"))
        manager.disconnect("missing", "user")

        room = manager.get_or_create("ws-1")
        room.add(Connection(FakeSocket(), "user-1", "Alice"))
        asyncio_run(manager.broadcast_presence("ws-1"))
        assert json.loads(room.connections["user-1"].ws.sent[-1])["type"] == "presence"

        manager.disconnect("ws-1", "user-1")
        assert "ws-1" not in manager._rooms

        with patch("backend.api.websocket._manager", None):
            assert get_workspace_manager() is get_workspace_manager()
