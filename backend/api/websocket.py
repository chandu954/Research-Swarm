"""WebSocket manager for real-time collaboration (presence, shared workspaces)."""
from __future__ import annotations
import json
import time
from typing import Dict, Set, Any, Optional
from fastapi import WebSocket
from loguru import logger


class Connection:
    def __init__(self, ws: WebSocket, user_id: str, name: str = "Anonymous"):
        self.ws = ws
        self.user_id = user_id
        self.name = name
        self.connected_at = time.time()


class WorkspaceRoom:
    """Manages WebSocket connections for a shared workspace."""

    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id
        self.connections: Dict[str, Connection] = {}

    @property
    def user_ids(self) -> Set[str]:
        return set(self.connections.keys())

    def add(self, conn: Connection) -> None:
        self.connections[conn.user_id] = conn

    def remove(self, user_id: str) -> None:
        self.connections.pop(user_id, None)

    def broadcast(self, message: dict, exclude: Optional[str] = None) -> None:
        payload = json.dumps(message)
        stale = []
        for uid, conn in self.connections.items():
            if uid == exclude:
                continue
            try:
                import asyncio
                if asyncio.iscoroutinefunction(conn.ws.send_text):
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(conn.ws.send_text(payload))
                    else:
                        loop.run_until_complete(conn.ws.send_text(payload))
                else:
                    conn.ws.send_text(payload)
            except Exception:
                stale.append(uid)
        for uid in stale:
            self.remove(uid)


class WorkspaceManager:
    """Singleton managing all active workspace rooms."""

    def __init__(self):
        self._rooms: Dict[str, WorkspaceRoom] = {}

    def get_or_create(self, workspace_id: str) -> WorkspaceRoom:
        if workspace_id not in self._rooms:
            self._rooms[workspace_id] = WorkspaceRoom(workspace_id)
        return self._rooms[workspace_id]

    def broadcast_presence(self, workspace_id: str) -> None:
        room = self._rooms.get(workspace_id)
        if not room:
            return
        users = [
            {
                "userId": conn.user_id,
                "name": conn.name,
                "status": "online",
                "lastSeen": conn.connected_at,
            }
            for conn in room.connections.values()
        ]
        room.broadcast({"type": "presence", "users": users})

    def disconnect(self, workspace_id: str, user_id: str) -> None:
        room = self._rooms.get(workspace_id)
        if room:
            room.remove(user_id)
            self.broadcast_presence(workspace_id)
            if not room.connections:
                self._rooms.pop(workspace_id, None)


_manager: Optional[WorkspaceManager] = None


def get_workspace_manager() -> WorkspaceManager:
    global _manager
    if _manager is None:
        _manager = WorkspaceManager()
    return _manager
