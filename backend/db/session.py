"""Async SQLAlchemy session and engine for PostgreSQL."""
from __future__ import annotations
import os
from typing import AsyncGenerator
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from loguru import logger


_raw_db_url: str = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./data/research_swarm.db",
)
# Strip sslmode query param (asyncpg uses `ssl=` not `sslmode=`) and fix scheme
parsed = urlparse(_raw_db_url)
if parsed.scheme in ("postgresql", "postgresql+asyncpg"):
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs.pop("sslmode", None)
    query = urlencode(qs, doseq=True) if qs else ""
    _raw_db_url = urlunparse(parsed._replace(
        scheme="postgresql+asyncpg",
        query=query,
    ))
DATABASE_URL = _raw_db_url

if DATABASE_URL.startswith("sqlite"):
    _engine = create_async_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )
else:
    _engine = create_async_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=False,
    )

_async_session_factory = async_sessionmaker(
    _engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session for FastAPI dependency injection."""
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def _migrate_columns() -> None:
    """Add missing columns to existing tables (lightweight migration).

    Each ALTER TABLE runs in its own transaction so failures don't cascade.
    """
    import sqlalchemy as sa
    from sqlalchemy import text as sa_text

    for table_name, table in Base.metadata.tables.items():
        existing: list[str] = []
        dialect = None
        try:
            async with _engine.begin() as conn:
                dialect = conn.dialect
                rows = await conn.execute(
                    sa_text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = :t"
                    ),
                    {"t": table_name},
                )
                existing = [r[0] for r in rows.fetchall()]
        except Exception:
            continue

        for column in table.columns:
            if column.name not in existing:
                col_type_str = column.type.compile(dialect=dialect)
                nullable_str = "NULL" if column.nullable else "NOT NULL"
                default_str = ""
                if column.default is not None:
                    if hasattr(column.default, "arg") and isinstance(column.default.arg, str):
                        default_str = f" DEFAULT {column.default.arg}"
                try:
                    async with _engine.begin() as conn:
                        await conn.execute(
                            sa_text(
                                f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type_str} {nullable_str}{default_str}"
                            )
                        )
                    logger.info(f"Migrated: added column {table_name}.{column.name} ({col_type_str})")
                except Exception as e:
                    logger.warning(f"Migration: could not add {table_name}.{column.name}: {e}")


async def init_db() -> None:
    """Create all tables (for development; use Alembic in production)."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")
    await _migrate_columns()


async def close_db() -> None:
    """Dispose of the engine."""
    await _engine.dispose()
    logger.info("Database engine disposed")
