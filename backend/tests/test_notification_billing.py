"""Tests for notification, global search, and billing routes.

Split from backend/tests/test_workspace_documents_units.py.
"""

from __future__ import annotations

import pytest
from backend.db.models import Message
from backend.db.schemas import SearchRequest
from backend.tests.test_workspace_doc_helpers import (
    NOW,
    Session,
    _conversation,
    _ctx,
    _document,
    _notification,
    _user,
    asyncio_run,
)
from fastapi import HTTPException


class TestNotificationRoutes:
    def test_list_unread_and_all(self):
        from backend.api.workspace import list_notifications

        session = Session([_notification()])
        response = asyncio_run(
            list_notifications(
                include_read=False,
                limit=10,
                current_user=_user(),
                session=session,
                ctx=_ctx(),
            )
        )
        assert response[0].title == "Hello"

        session = Session([])
        assert (
            asyncio_run(
                list_notifications(
                    include_read=True,
                    limit=10,
                    current_user=_user(),
                    session=session,
                    ctx=_ctx(),
                )
            )
            == []
        )

    def test_mark_read(self):
        from backend.api.workspace import mark_notification_read

        notification = _notification()
        assert asyncio_run(
            mark_notification_read(
                "notif-1", current_user=_user(), session=Session(notification)
            )
        ) == {"status": "read"}
        assert notification.is_read is True
        assert notification.read_at is not None

        with pytest.raises(HTTPException) as missing:
            asyncio_run(
                mark_notification_read(
                    "missing", current_user=_user(), session=Session(None)
                )
            )
        assert missing.value.status_code == 404

    def test_mark_all_read(self):
        from backend.api.workspace import mark_all_read

        session = Session()
        assert asyncio_run(mark_all_read(current_user=_user(), session=session)) == {
            "status": "all_read"
        }
        assert session.flushes == 1


class TestGlobalSearch:
    def test_searches_all_resource_types_and_sorts(self):
        from backend.api.workspace import global_search

        message = Message(
            id="msg-1",
            conversation_id="conv-12345678",
            role="user",
            content="A message about RAG",
            sources=[],
            metadata_={},
            created_at=NOW,
        )
        session = Session(
            [_conversation()],
            [_document()],
            [message],
        )
        response = asyncio_run(
            global_search(
                SearchRequest(query="RAG"),
                current_user=_user(),
                session=session,
                ctx=_ctx(),
            )
        )
        assert [item.resource_type for item in response] == [
            "conversation",
            "document",
            "message",
        ]
        assert response[-1].title.startswith("Message in conv-123")

    def test_searches_selected_types_only(self):
        from backend.api.workspace import global_search

        session = Session([])
        response = asyncio_run(
            global_search(
                SearchRequest(query="x", resource_types=["documents"]),
                current_user=_user(),
                session=session,
                ctx=_ctx(),
            )
        )
        assert response == []
        assert len(session.results) == 0


class TestBilling:
    def test_usage_for_own_org(self):
        from backend.api.workspace import get_billing_usage

        session = Session((1, 2, 3, 4, 5.5, 0.25))
        response = asyncio_run(
            get_billing_usage(
                organization_id="org-1",
                current_user=_user(),
                session=session,
                ctx=_ctx(),
            )
        )
        assert response.tokens_in == 1
        assert response.compute_seconds == 5.5
        assert response.estimated_cost == 0.25

    def test_usage_rejects_foreign_org(self):
        from backend.api.workspace import get_billing_usage

        with pytest.raises(HTTPException) as denied:
            asyncio_run(
                get_billing_usage(
                    organization_id="other",
                    current_user=_user(),
                    session=Session(),
                    ctx=_ctx(),
                )
            )
        assert denied.value.status_code == 403
