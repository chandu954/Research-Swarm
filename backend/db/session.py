"""Async SQLAlchemy session and engine for PostgreSQL."""
from __future__ import annotations
import os, re
from typing import AsyncGenerator

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
# Auto-fix Railway/Neon PostgreSQL URLs missing the +asyncpg driver
if _raw_db_url.startswith("postgresql://") and "+asyncpg" not in _raw_db_url:
    _raw_db_url = _raw_db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
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


async def init_db() -> None:
    """Create all tables (for development; use Alembic in production)."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")


async def close_db() -> None:
    """Dispose of the engine."""
    await _engine.dispose()
    logger.info("Database engine disposed")
