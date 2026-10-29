"""Shared test helpers for workspace/document unit tests.

Split from backend/tests/test_workspace_documents_units.py.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from backend.auth.tenant import _resolve_permissions
from backend.db.models import (
    APIKey,
    AuditLog,
    Conversation,
    Document,
    DocumentVersion,
    Message,
    Notification,
    User,
)
from backend.db.schemas import APIKeyCreate, SearchRequest

__all__ = [
    "APIKey",
    "APIKeyCreate",
    "AuditLog",
    "Conversation",
    "Document",
    "DocumentVersion",
    "Message",
    "Notification",
    "Result",
    "SearchRequest",
    "Session",
    "User",
    "_audit",
    "_conversation",
    "_ctx",
    "_document",
    "_notification",
    "_user",
    "asyncio_run",
]



def asyncio_run(coroutine):
    return asyncio.run(coroutine)


NOW = datetime.now(timezone.utc)


class Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        if isinstance(self.value, list):
            return self.value
        return [] if self.value is None else [self.value]

    def one(self):
        return self.value


class Session:
    def __init__(self, *results, scalar_values=()):
        self.results = list(results)
        self.scalar_values = list(scalar_values)
        self.added = []
        self.deleted = []
        self.flushes = 0

    async def execute(self, *_args, **_kwargs):
        return Result(self.results.pop(0) if self.results else None)

    async def scalar(self, *_args, **_kwargs):
        return self.scalar_values.pop(0) if self.scalar_values else None

    async def flush(self):
        self.flushes += 1
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = str(uuid.uuid4())
            for attr in ("created_at", "updated_at", "joined_at"):
                if hasattr(item, attr) and getattr(item, attr) is None:
                    setattr(item, attr, NOW)
            for attr in ("is_active", "is_read", "is_deleted", "has_ocr"):
                if hasattr(item, attr) and getattr(item, attr) is None:
                    setattr(item, attr, True if attr != "is_read" else False)

    def add(self, item):
        self.added.append(item)

    async def delete(self, item):
        self.deleted.append(item)


def _user(user_id="user-1"):
    return User(
        id=user_id,
        email=f"{user_id}@example.com",
        name="User",
        is_active=True,
        mfa_enabled=False,
        created_at=NOW,
        updated_at=NOW,
    )


def _ctx(**overrides):
    values = {
        "organization_id": "org-1",
        "organization_slug": "org",
        "workspace_id": None,
        "project_id": None,
        "user_id": "user-1",
        "user_role": "owner",
        "permissions": _resolve_permissions("owner"),
    }
    values.update(overrides)
    from backend.auth.tenant import TenantContext

    return TenantContext(**values)


def _document(**overrides):
    values = {
        "id": "doc-1",
        "user_id": "user-1",
        "organization_id": "org-1",
        "workspace_id": "ws-1",
        "project_id": None,
        "filename": "stored.pdf",
        "original_filename": "report.pdf",
        "size_bytes": 10,
        "mime_type": "application/pdf",
        "storage_path": "/tmp/report.pdf",
        "storage_backend": "local",
        "auto_tags": [],
        "is_deleted": False,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return Document(**values)


def _notification(**overrides):
    values = {
        "id": "notif-1",
        "user_id": "user-1",
        "organization_id": "org-1",
        "type": "info",
        "title": "Hello",
        "body": "Body",
        "data": {},
        "is_read": False,
        "created_at": NOW,
    }
    values.update(overrides)
    return Notification(**values)


def _audit(**overrides):
    values = {
        "id": "audit-1",
        "organization_id": "org-1",
        "workspace_id": None,
        "user_id": "user-1",
        "action": "research.completed",
        "resource_type": "session",
        "resource_id": "s-1",
        "details": {},
        "ip_address": None,
        "user_agent": None,
        "created_at": NOW,
    }
    values.update(overrides)
    return AuditLog(**values)


def _conversation(**overrides):
    values = {
        "id": "conv-12345678",
        "user_id": "user-1",
        "organization_id": "org-1",
        "workspace_id": "ws-1",
        "project_id": None,
        "title": "Title",
        "description": "Description",
        "is_archived": False,
        "is_pinned": False,
        "is_favorited": False,
        "is_deleted": False,
        "visibility": "workspace",
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return Conversation(**values)
