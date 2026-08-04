"""Squashed into 0001: multi-tenant baseline now lives in the initial migration.

The original 0002 was never runnable against a fresh database (it mutated
`workspaces` / `workspace_members` tables that the original 0001 never
created, and created `user_sessions` before its `user_devices` dependency).

The complete, FK-safe, single-ID-type schema is now created by 0001. This
revision is kept as an explicit pass-through so the chain (0001 -> 0002 ->
head) stays linear and `alembic upgrade head` succeeds on an empty database.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-04 00:00:00.000000
"""
from __future__ import annotations
from typing import Sequence, Union

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
