"""Shared test helpers for API route unit tests.

Extracted from backend/tests/test_api_routes_units.py so the split test
modules can reuse the same fixtures without duplication.
"""

# ruff: noqa: F401

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from backend.auth.tenant import (
    TenantContext,
    _resolve_permissions,
    _slugify,
    get_tenant_context,
    require_org,
    require_org_permission,
    require_permission,
    reset_tenant_context,
    resolve_optional_tenant,
    resolve_org_from_subdomain,
    resolve_tenant_dependencies,
    set_tenant_context,
    tenant_filter,
)
from backend.db.models import (
    Conversation,
    Message,
    Organization,
    OrganizationMember,
    Project,
    User,
    Workspace,
    WorkspaceMember,
)
from backend.db.schemas import (
    AddMemberRequest,
    ConversationCreate,
    ConversationUpdate,
    MemberRole,
    OrganizationCreate,
    OrganizationUpdate,
    ProjectCreate,
    ProjectUpdate,
    UpdateMemberRoleRequest,
    WorkspaceCreate,
    WorkspaceUpdate,
)


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

    def fetchall(self):
        return self.value or []


class Session:
    def __init__(self, *results, scalar_values=()):
        self.results = list(results)
        self.scalar_values = list(scalar_values)
        self.added = []
        self.deleted = []
        self.flushes = 0
        self.commits = 0

    async def execute(self, *_args, **_kwargs):
        return Result(self.results.pop(0) if self.results else None)

    async def scalar(self, *_args, **_kwargs):
        return self.scalar_values.pop(0) if self.scalar_values else None

    async def flush(self):
        self.flushes += 1
        for item in self.added:
            _ensure_defaults(item)

    async def commit(self):
        self.commits += 1

    def add(self, item):
        self.added.append(item)
        _ensure_defaults(item)

    async def delete(self, item):
        self.deleted.append(item)

    def scalars(self):
        return self

    def all(self):
        return self.scalar_values.pop(0) if self.scalar_values else []


def _ensure_defaults(item):
    if getattr(item, "id", None) is None:
        item.id = str(uuid.uuid4())
    for attr in ("created_at", "updated_at", "joined_at"):
        if hasattr(item, attr) and getattr(item, attr) is None:
            setattr(item, attr, NOW)
    for attr in ("is_active", "trusted"):
        if hasattr(item, attr) and getattr(item, attr) is None:
            setattr(item, attr, True)


def _user(user_id="user-1", **overrides):
    values = {
        "id": user_id,
        "email": f"{user_id}@example.com",
        "name": "User",
        "is_active": True,
        "mfa_enabled": False,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return User(**values)


def _org(**overrides):
    values = {
        "id": "org-1",
        "name": "Org",
        "slug": "org",
        "description": None,
        "avatar_url": None,
        "owner_id": "user-1",
        "is_active": True,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return Organization(**values)


def _workspace(**overrides):
    values = {
        "id": "ws-1",
        "organization_id": "org-1",
        "name": "Workspace",
        "slug": "workspace",
        "description": None,
        "owner_id": "user-1",
        "is_active": True,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return Workspace(**values)


def _project(**overrides):
    values = {
        "id": "proj-1",
        "organization_id": "org-1",
        "workspace_id": "ws-1",
        "name": "Project",
        "slug": "project",
        "description": None,
        "owner_id": "user-1",
        "is_active": True,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return Project(**values)


def _membership(**overrides):
    values = {
        "id": "member-1",
        "organization_id": "org-1",
        "user_id": "user-1",
        "role": "owner",
        "joined_at": NOW,
    }
    values.update(overrides)
    return OrganizationMember(**values)


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
    return TenantContext(**values)


def _session_generator(session):
    async def generator():
        yield session

    return generator


def _conversation(**overrides):
    values = {
        "id": "conv-1",
        "user_id": "user-1",
        "organization_id": "org-1",
        "workspace_id": "ws-1",
        "project_id": "proj-1",
        "title": "Conversation",
        "description": None,
        "is_archived": False,
        "is_pinned": False,
        "is_favorited": False,
        "visibility": "workspace",
        "is_deleted": False,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return Conversation(**values)
