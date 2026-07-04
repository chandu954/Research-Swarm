"""WebSocket manager for real-time collaboration — presence, chat, typing, research/doc notifications."""
from __future__ import annotations
import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Dict, Set, Any, Optional, Callable, Awaitable
from fastapi import WebSocket
from loguru import logger


MAX_CHAT_HISTORY = 100
TYPING_TIMEOUT = 5.0


@dataclass
class ChatMessage:
    id: str
    userId: str
    userName: str
    content: str
    timestamp: float


class Connection:
    def __init__(self, ws: WebSocket, user_id: str, name: str = "Anonymous"):
        self.ws = ws
        self.user_id = user_id
        self.name = name
        self.connected_at = time.time()


MessageHandler = Callable[[dict, Connection, "WorkspaceRoom"], Awaitable[None]]


class WorkspaceRoom:
    """Manages WebSocket connections + shared state for a workspace."""

    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id
        self.connections: Dict[str, Connection] = {}
        self.chat_messages: list[ChatMessage] = []
        self._typing: Dict[str, float] = {}  # user_id -> last_typing_at
        self._handlers: Dict[str, MessageHandler] = {
            "chat:send": self._handle_chat_send,
            "typing": self._handle_typing,
            "ping": self._handle_ping,
        }

    @property
    def user_ids(self) -> Set[str]:
        return set(self.connections.keys())

    @property
    def typing_users(self) -> list[dict]:
        now = time.time()
        active = []
        stale = []
        for uid, last in self._typing.items():
            if now - last < TYPING_TIMEOUT:
                conn = self.connections.get(uid)
                if conn:
                    active.append({"userId": uid, "name": conn.name})
            else:
                stale.append(uid)
        for uid in stale:
            self._typing.pop(uid, None)
        return active

    def add(self, conn: Connection) -> None:
        self.connections[conn.user_id] = conn

    def remove(self, user_id: str) -> None:
        self.connections.pop(user_id, None)
        self._typing.pop(user_id, None)

    # ── Message Routing ──────────────────────────────────────

    async def handle_message(self, raw: str, conn: Connection) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        msg_type = msg.get("type", "")
        handler = self._handlers.get(msg_type)
        if handler:
            await handler(msg, conn)
        else:
            logger.debug(f"Unknown message type: {msg_type}")

    async def _handle_ping(self, msg: dict, conn: Connection) -> None:
        await self._send(conn, {"type": "pong"})

    # ── Chat ─────────────────────────────────────────────────

    async def _handle_chat_send(self, msg: dict, conn: Connection) -> None:
        content = (msg.get("payload") or {}).get("content", "").strip()
        if not content:
            return
        chat_msg = ChatMessage(
            id=f"chat_{int(time.time() * 1000)}_{conn.user_id[:8]}",
            userId=conn.user_id,
            userName=conn.name,
            content=content,
            timestamp=time.time(),
        )
        self.chat_messages.append(chat_msg)
        if len(self.chat_messages) > MAX_CHAT_HISTORY:
            self.chat_messages.pop(0)
        await self.broadcast({
            "type": "chat:message",
            "payload": {
                "id": chat_msg.id,
                "userId": chat_msg.userId,
                "userName": chat_msg.userName,
                "content": chat_msg.content,
                "timestamp": chat_msg.timestamp,
            },
        })

    def get_chat_history(self) -> list[dict]:
        return [
            {
                "id": m.id,
                "userId": m.userId,
                "userName": m.userName,
                "content": m.content,
                "timestamp": m.timestamp,
            }
            for m in self.chat_messages[-50:]
        ]

    # ── Typing ───────────────────────────────────────────────

    async def _handle_typing(self, msg: dict, conn: Connection) -> None:
        payload = msg.get("payload") or {}
        is_typing = payload.get("isTyping", False)
        if is_typing:
            self._typing[conn.user_id] = time.time()
        else:
            self._typing.pop(conn.user_id, None)
        await self.broadcast({
            "type": "typing",
            "payload": {"typingUsers": self.typing_users},
        }, exclude=conn.user_id)

    # ── Research / Document Notifications ────────────────────

    async def broadcast_research_start(self, user_id: str, user_name: str, task_id: str, query: str) -> None:
        await self.broadcast({
            "type": "research:start",
            "payload": {"userId": user_id, "userName": user_name, "taskId": task_id, "query": query[:200]},
        })

    async def broadcast_research_log(self, task_id: str, log: dict) -> None:
        await self.broadcast({
            "type": "research:log",
            "payload": {"taskId": task_id, "log": log},
        })

    async def broadcast_research_complete(self, task_id: str, user_id: str) -> None:
        await self.broadcast({
            "type": "research:complete",
            "payload": {"taskId": task_id, "userId": user_id},
        })

    async def broadcast_document_added(self, document: dict) -> None:
        await self.broadcast({"type": "document:added", "payload": {"document": document}})

    async def broadcast_document_removed(self, document_id: str) -> None:
        await self.broadcast({"type": "document:removed", "payload": {"documentId": document_id}})

    # ── Low-level Send / Broadcast ───────────────────────────

    async def broadcast(self, message: dict, exclude: Optional[str] = None) -> None:
        payload = json.dumps(message)
        stale: list[str] = []
        tasks = []
        for uid, conn in self.connections.items():
            if uid == exclude:
                continue
            tasks.append(self._safe_send(conn, payload, stale, uid))
        if tasks:
            await asyncio.gather(*tasks)
        for uid in stale:
            self.remove(uid)

    async def _send(self, conn: Connection, message: dict) -> None:
        try:
            await conn.ws.send_text(json.dumps(message))
        except Exception:
            pass

    async def _safe_send(self, conn: Connection, payload: str, stale: list, uid: str) -> None:
        try:
            await conn.ws.send_text(payload)
        except Exception:
            stale.append(uid)


class WorkspaceManager:
    """Singleton managing all active workspace rooms."""

    def __init__(self):
        self._rooms: Dict[str, WorkspaceRoom] = {}

    def get_or_create(self, workspace_id: str) -> WorkspaceRoom:
        if workspace_id not in self._rooms:
            self._rooms[workspace_id] = WorkspaceRoom(workspace_id)
        return self._rooms[workspace_id]

    async def broadcast_presence(self, workspace_id: str) -> None:
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
        await room.broadcast({"type": "presence", "users": users})

    def disconnect(self, workspace_id: str, user_id: str) -> None:
        room = self._rooms.get(workspace_id)
        if room:
            room.remove(user_id)
            if not room.connections:
                self._rooms.pop(workspace_id, None)


_manager: Optional[WorkspaceManager] = None


def get_workspace_manager() -> WorkspaceManager:
    global _manager
    if _manager is None:
        _manager = WorkspaceManager()
    return _manager
