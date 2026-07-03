"""Tests for WebSocket collaboration manager."""
from __future__ import annotations
import pytest
from backend.api.websocket import WorkspaceRoom, WorkspaceManager, Connection, get_workspace_manager


class FakeWebSocket:
    def __init__(self):
        self.sent: list[str] = []

    async def send_text(self, text: str):
        self.sent.append(text)


class TestWorkspaceRoom:
    def test_add_and_remove(self):
        room = WorkspaceRoom("ws-1")
        ws = FakeWebSocket()
        conn = Connection(ws, "user-1", "Alice")
        room.add(conn)
        assert "user-1" in room.user_ids
        room.remove("user-1")
        assert "user-1" not in room.user_ids

    @pytest.mark.asyncio
    async def test_broadcast_excludes_sender(self):
        room = WorkspaceRoom("ws-1")
        ws1 = FakeWebSocket()
        ws2 = FakeWebSocket()
        room.add(Connection(ws1, "user-1", "Alice"))
        room.add(Connection(ws2, "user-2", "Bob"))
        await room.broadcast({"type": "test"}, exclude="user-1")
        assert len(ws1.sent) == 0  # excluded
        assert len(ws2.sent) >= 1  # received


class TestWorkspaceManager:
    def test_get_or_create(self):
        mgr = WorkspaceManager()
        room = mgr.get_or_create("ws-1")
        assert room is mgr.get_or_create("ws-1")

    def test_disconnect_removes_user(self):
        mgr = WorkspaceManager()
        room = mgr.get_or_create("ws-1")
        ws = FakeWebSocket()
        room.add(Connection(ws, "user-1", "Alice"))
        mgr.disconnect("ws-1", "user-1")
        assert "user-1" not in room.user_ids

    @pytest.mark.asyncio
    async def test_broadcast_presence(self):
        mgr = WorkspaceManager()
        room = mgr.get_or_create("ws-1")
        ws = FakeWebSocket()
        room.add(Connection(ws, "user-1", "Alice"))
        await mgr.broadcast_presence("ws-1")
        assert len(ws.sent) >= 1
        assert '"type": "presence"' in ws.sent[0]
