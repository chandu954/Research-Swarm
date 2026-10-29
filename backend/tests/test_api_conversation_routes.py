"""Conversation route unit tests.

Split from backend/tests/test_api_routes_units.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from backend.tests._api_test_helpers import (
    Session,
    _conversation,
    _ctx,
    _user,
    asyncio_run,
)
from fastapi import HTTPException


class TestConversationRoutes:
    def test_list_with_filters_and_message_counts(self):
        from backend.api.conversations import list_conversations

        session = Session([_conversation()], scalar_values=[3])
        response = asyncio_run(
            list_conversations(
                ws_id="ignored",
                proj_id="proj-1",
                archived=False,
                search="Conv",
                limit=10,
                offset=0,
                current_user=_user(),
                session=session,
                ctx=_ctx(workspace_id="ws-1"),
            )
        )
        assert response[0].message_count == 3

        session = Session([], scalar_values=[None])
        assert (
            asyncio_run(
                list_conversations(
                    ws_id="ws-2",
                    proj_id=None,
                    archived=True,
                    search=None,
                    limit=10,
                    offset=0,
                    current_user=_user(),
                    session=session,
                    ctx=_ctx(workspace_id=None),
                )
            )
            == []
        )

    def test_create_conversation(self):
        from backend.api.conversations import create_conversation
        from backend.db.schemas import ConversationCreate

        session = Session()
        with patch("backend.api.conversations.log_audit", new=AsyncMock()) as audit:
            response = asyncio_run(
                create_conversation(
                    ConversationCreate(title="Mine"),
                    current_user=_user(),
                    session=session,
                    ctx=_ctx(),
                )
            )
        assert response.title == "Mine"
        assert audit.await_count == 1

        with patch("backend.api.conversations.log_audit", new=AsyncMock()):
            response = asyncio_run(
                create_conversation(
                    ConversationCreate(project_id="body-project"),
                    current_user=_user(),
                    session=Session(),
                    ctx=_ctx(project_id="ctx-project"),
                )
            )
        assert response.title == "New Conversation"

    def test_get_conversation(self):
        from backend.api.conversations import get_conversation
        from backend.db.models import Message
        from backend.tests._api_test_helpers import NOW

        message = Message(
            id="msg-1",
            conversation_id="conv-1",
            role="user",
            content="hi",
            sources=[],
            metadata_={},
            created_at=NOW,
        )
        session = Session(_conversation(), [message])
        response = asyncio_run(
            get_conversation(
                "conv-1", current_user=_user(), session=session, ctx=_ctx()
            )
        )
        assert response.messages[0].content == "hi"

        with pytest.raises(HTTPException) as missing:
            asyncio_run(
                get_conversation(
                    "missing", current_user=_user(), session=Session(None), ctx=_ctx()
                )
            )
        assert missing.value.status_code == 404

    def test_update_conversation(self):
        from backend.api.conversations import update_conversation
        from backend.db.schemas import ConversationUpdate

        conv = _conversation()
        response = asyncio_run(
            update_conversation(
                "conv-1",
                ConversationUpdate(
                    title="New",
                    description="Desc",
                    is_archived=True,
                    is_pinned=True,
                    is_favorited=True,
                    visibility="private",
                ),
                current_user=_user(),
                session=Session(conv),
                ctx=_ctx(),
            )
        )
        assert response.title == "New"
        assert response.visibility == "private"

        with pytest.raises(HTTPException):
            asyncio_run(
                update_conversation(
                    "missing",
                    ConversationUpdate(),
                    current_user=_user(),
                    session=Session(None),
                    ctx=_ctx(),
                )
            )

    def test_delete_conversation(self):
        from backend.api.conversations import delete_conversation

        conv = _conversation()
        with patch("backend.api.conversations.log_audit", new=AsyncMock()):
            assert asyncio_run(
                delete_conversation(
                    "conv-1", current_user=_user(), session=Session(conv), ctx=_ctx()
                )
            ) == {"status": "deleted"}
        assert conv.is_deleted is True
        assert conv.deleted_at is not None

        with pytest.raises(HTTPException):
            asyncio_run(
                delete_conversation(
                    "missing", current_user=_user(), session=Session(None), ctx=_ctx()
                )
            )
