"""Real-time collaboration WebSocket endpoint."""

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from backend.api.common import get_cors_origins
from backend.api.websocket import Connection, get_workspace_manager
from backend.core.ratelimit import ws_limiter
from backend.db.models import User, Workspace, WorkspaceMember
from backend.db.session import get_session

router = APIRouter(tags=["realtime"])
cors_origins = get_cors_origins()


# ═══════════════════════════════════════════════════════════════
# WEBSOCKET (Real-time Collaboration)
# ═══════════════════════════════════════════════════════════════


@router.websocket("/ws/workspace/{workspace_id}")
async def workspace_ws(workspace_id: str, ws: WebSocket):
    from backend.auth.jwt import decode_token as _decode_ws_token

    # Origin validation: browsers always send an Origin header on WebSocket
    # handshakes. Cross-origin sockets are rejected unless the origin is an
    # explicitly configured CORS origin (production frontend domain).
    origin = ws.headers.get("origin", "")
    if origin and origin not in cors_origins:
        await ws.close(code=1008, reason="Origin not allowed")
        return

    # WebSocket routes bypass the slowapi middleware: throttle connection
    # creation with the in-process sliding-window limiter.
    client_ip = ws.client.host if ws.client else "unknown"
    if not ws_limiter.allow(f"ws:{client_ip}"):
        await ws.close(code=1008, reason="Rate limit exceeded")
        return

    protocols = ws.headers.get("sec-websocket-protocol", "")
    parts = [p.strip() for p in protocols.split(",")] if protocols else []
    token = ""
    if len(parts) >= 2 and parts[0] == "research-swarm":
        token = parts[1]
    if not token:
        token = ws.query_params.get("token", "")
    user_id = ws.query_params.get("user_id", "")

    payload = _decode_ws_token(token)
    if not payload or payload.get("type") != "access":
        await ws.close(code=4001, reason="Authentication required")
        return

    token_user_id = payload.get("sub")
    if user_id and user_id != token_user_id:
        await ws.close(code=4001, reason="User ID mismatch")
        return

    resolved_user_id = token_user_id or "anonymous"
    user_name = payload.get("name", "Anonymous")

    ws_user = None
    async for _ws_session in get_session():
        ws_result = await _ws_session.execute(
            select(Workspace).where(
                Workspace.id == workspace_id, Workspace.is_active.is_(True)
            )
        )
        workspace = ws_result.scalar_one_or_none()
        if not workspace:
            await ws.close(code=4004, reason="Workspace not found")
            return

        user_result = await _ws_session.execute(
            select(User).where(User.id == resolved_user_id, User.is_active.is_(True))
        )
        ws_user = user_result.scalar_one_or_none()
        if not ws_user:
            await ws.close(code=4001, reason="User not found")
            return

        if not ws_user.is_superuser:
            member_result = await _ws_session.execute(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.user_id == resolved_user_id,
                )
            )
            if not member_result.scalar_one_or_none():
                await ws.close(code=4003, reason="Not a member of this workspace")
                return
        break  # only one iteration needed

    await ws.accept(subprotocol="research-swarm")

    mgr = get_workspace_manager()
    room = mgr.get_or_create(workspace_id)
    conn = Connection(ws, resolved_user_id, user_name)
    room.add(conn)
    await mgr.broadcast_presence(workspace_id)

    # Send chat history to newly joined user
    history = room.get_chat_history()
    if history:
        await ws.send_text(
            json.dumps({"type": "chat:history", "payload": {"messages": history}})
        )

    try:
        while True:
            data = await ws.receive_text()
            await room.handle_message(data, conn)
    except WebSocketDisconnect:
        pass
    finally:
        mgr.disconnect(workspace_id, resolved_user_id)
        await mgr.broadcast_presence(workspace_id)
