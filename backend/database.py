"""
database.py — Database connection and session management.

Uses SQLAlchemy (async) against Postgres in production and SQLite in tests.
The connection URL is read from the DATABASE_URL environment variable.

Backlog: 2.1.1
"""

from __future__ import annotations

import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# ---------------------------------------------------------------------------
# Engine setup
# ---------------------------------------------------------------------------

_DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    # Safe fallback for local dev only — never commit real credentials.
    "sqlite+aiosqlite:///./statica_trace_dev.db",
)

# SQLite does not support the asyncpg driver; swap the scheme when needed.
# In production, DATABASE_URL will start with "postgresql+asyncpg://".
engine = create_async_engine(
    _DATABASE_URL,
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# ORM base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Dependency: async DB session
# ---------------------------------------------------------------------------


async def get_db() -> AsyncSession:  # type: ignore[override]
    """FastAPI dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Migration helper: create all tables defined in models.py
# ---------------------------------------------------------------------------


async def create_tables() -> None:
    """
    Create all tables (idempotent).  In production, use Alembic migrations
    instead.  This helper is used for dev and test environments.
    """
    # Import models so their metadata is registered on Base.
    from backend import models  # noqa: F401  (side-effect import)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def apply_indexes() -> None:
    """
    Apply composite indexes that SQLAlchemy's DDL may not emit automatically
    (e.g. DESC ordering).  Safe to run multiple times.
    """
    async with engine.begin() as conn:
        dialect = conn.dialect.name
        if dialect == "postgresql":
            await conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_traces_project
                        ON traces(project_id, created_at DESC);
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_traces_status
                        ON traces(project_id, status);
                    """
                )
            )
