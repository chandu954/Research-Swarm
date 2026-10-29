"""Tests for database session helpers.

Split from backend/tests/test_realtime_stream_infra.py.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.db.session import get_session
from sqlalchemy import Boolean, Column, Integer, MetaData, String, Table
from sqlalchemy.dialects import sqlite as sqlite_dialect


def asyncio_run(coroutine):
    return asyncio.run(coroutine)


class FakeSessionContext:
    def __init__(self):
        self.session = MagicMock()
        self.session.commit = AsyncMock()
        self.session.rollback = AsyncMock()
        self.session.close = AsyncMock()

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_args):
        return False


class TestDatabaseSessionHelpers:
    def test_get_session_commits_and_closes(self):
        context = FakeSessionContext()

        async def consume():
            generator = get_session()
            session = await generator.__anext__()
            assert session is context.session
            with pytest.raises(StopAsyncIteration):
                await generator.__anext__()

        with patch("backend.db.session._async_session_factory", return_value=context):
            asyncio_run(consume())

        context.session.commit.assert_awaited_once()
        context.session.close.assert_awaited_once()
        context.session.rollback.assert_not_awaited()

    def test_get_session_rolls_back_on_error(self):
        context = FakeSessionContext()

        async def consume():
            generator = get_session()
            await generator.__anext__()
            with pytest.raises(RuntimeError, match="boom"):
                await generator.athrow(RuntimeError("boom"))

        with patch("backend.db.session._async_session_factory", return_value=context):
            asyncio_run(consume())

        context.session.rollback.assert_awaited_once()
        context.session.close.assert_awaited_once()
        context.session.commit.assert_not_awaited()

    def test_migrate_columns_adds_missing_columns(self):
        from backend.db import session as session_module

        metadata = MetaData()
        table = Table(
            "t",
            metadata,
            Column("existing", String),
            Column("flag", Boolean, nullable=False),
            Column("count", Integer, nullable=False),
            Column("label", String, nullable=True, default="x"),
            Column("bad", String),
        )
        broken = Table("broken", metadata, Column("x", String))

        alters: list[str] = []

        class Rows:
            def __init__(self, rows):
                self._rows = rows

            def fetchall(self):
                return self._rows

        class Connection:
            dialect = sqlite_dialect.dialect()

            async def execute(self, statement, params=None):
                sql = str(statement)
                if "information_schema" in sql:
                    if params["t"] == "broken":
                        raise RuntimeError("information schema unavailable")
                    return Rows([("existing",)])
                if "ADD COLUMN bad" in sql:
                    raise RuntimeError("alter failed")
                alters.append(sql)
                return MagicMock()

        class Begin:
            async def __aenter__(self):
                return Connection()

            async def __aexit__(self, *_args):
                return False

        class Engine:
            def begin(self):
                return Begin()

        fake_base = SimpleNamespace(
            metadata=SimpleNamespace(tables={"broken": broken, "t": table})
        )
        with patch.object(session_module, "Base", fake_base), patch.object(
            session_module, "_engine", Engine()
        ):
            asyncio_run(session_module._migrate_columns())

        joined = "\n".join(alters)
        assert "ADD COLUMN flag BOOLEAN NOT NULL DEFAULT false" in joined
        assert "ADD COLUMN count INTEGER NOT NULL DEFAULT 0" in joined
        assert "ADD COLUMN label VARCHAR NULL DEFAULT x" in joined
        assert "existing" not in joined
        assert "ADD COLUMN bad" not in joined

    def test_init_db_and_close_db(self):
        from backend.db import session as session_module

        connection = MagicMock()
        connection.run_sync = AsyncMock()

        class Begin:
            async def __aenter__(self):
                return connection

            async def __aexit__(self, *_args):
                return False

        engine = MagicMock()
        engine.begin.return_value = Begin()
        engine.dispose = AsyncMock()

        with patch.object(session_module, "_engine", engine), patch.object(
            session_module, "_migrate_columns", AsyncMock()
        ) as migrate:
            asyncio_run(session_module.init_db())
            asyncio_run(session_module.close_db())

        connection.run_sync.assert_awaited_once()
        migrate.assert_awaited_once()
        engine.dispose.assert_awaited_once()
