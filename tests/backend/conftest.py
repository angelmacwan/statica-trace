"""
conftest.py — Shared async fixtures for backend tests.

Uses an in-memory SQLite database (via aiosqlite) so no real Postgres is
needed during testing.  Each test gets a fresh database via a per-test
transaction rollback.

Backlog: 2.5.1, 2.5.2, 2.5.3, 2.5.4
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.database import Base, get_db
from backend.main import app
from backend.models import Project, TraceRecord

# ---------------------------------------------------------------------------
# In-memory SQLite engine shared across the test session
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_test_tables():
    """Create all tables once per test session."""
    # Import models to register metadata
    from backend import models  # noqa: F401

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture()
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a test DB session that is rolled back after each test.
    This gives each test a clean slate without re-creating tables.
    """
    async with test_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    An HTTPX AsyncClient wired to the FastAPI app with the test DB session
    injected via dependency override.
    """

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper: seed a project row directly
# ---------------------------------------------------------------------------


async def make_project(
    db: AsyncSession,
    name: str = "Test Project",
    api_key: str | None = None,
) -> Project:
    api_key = api_key or f"test-key-{uuid.uuid4().hex[:8]}"
    p = Project(
        id=str(uuid.uuid4()),
        name=name,
        api_key=api_key,
        created_at=datetime.now(tz=UTC),
    )
    db.add(p)
    await db.flush()
    return p


# ---------------------------------------------------------------------------
# Helper: seed a trace row directly
# ---------------------------------------------------------------------------


async def make_trace(
    db: AsyncSession,
    project_id: str,
    source: str = "openai",
    status: str = "success",
    raw: dict | None = None,
    created_at: datetime | None = None,
) -> TraceRecord:
    span_id = str(uuid.uuid4())
    default_raw = {
        "trace_id": str(uuid.uuid4()),
        "project_id": project_id,
        "source": source,
        "status": status,
        "started_at": "2024-01-01T00:00:00Z",
        "ended_at": "2024-01-01T00:00:05Z",
        "spans": [
            {
                "span_id": span_id,
                "parent_span_id": None,
                "type": "llm_call",
                "name": "chat",
                "started_at": "2024-01-01T00:00:00Z",
                "ended_at": "2024-01-01T00:00:05Z",
                "input": {
                    "messages": [{"role": "user", "content": "Hello"}],
                    "model": "gpt-4o-mini",
                    "params": {"temperature": 0.7},
                    "tools": [],
                    "retrieved_context": [],
                },
                "output": {"content": "Hi there!", "tool_calls": []},
                "error": None,
                "status": status,
            }
        ],
    }
    t = TraceRecord(
        id=str(uuid.uuid4()),
        project_id=project_id,
        source=source,
        status=status,
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
        ended_at=datetime(2024, 1, 1, 0, 0, 5, tzinfo=UTC),
        raw=raw or default_raw,
        created_at=created_at or datetime.now(tz=UTC),
    )
    db.add(t)
    await db.flush()
    return t
