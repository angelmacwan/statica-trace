"""
models.py — SQLAlchemy ORM models for Statica Trace.

Mirrors the SQL schema in DOCS/agent-replay-debugger-spec.md § 8.2.

Backlog: 2.1.1
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from backend.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Portable JSONB / JSON column type
# ---------------------------------------------------------------------------


def _json_col() -> type:
    """Return JSONB on Postgres, JSON elsewhere (e.g. SQLite in tests)."""
    try:
        from sqlalchemy.dialects.postgresql import JSONB as _JSONB  # noqa: F811

        return _JSONB
    except ImportError:
        return JSON


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    api_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    traces: Mapped[list[TraceRecord]] = relationship(
        "TraceRecord", back_populates="project", lazy="select"
    )


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------


class TraceRecord(Base):
    __tablename__ = "traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    raw: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    project: Mapped[Project] = relationship("Project", back_populates="traces")
    replays: Mapped[list[ReplayRecord]] = relationship(
        "ReplayRecord", back_populates="trace", lazy="select"
    )

    __table_args__ = (
        Index("idx_traces_project_created", "project_id", "created_at"),
        Index("idx_traces_status", "project_id", "status"),
    )


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


class ReplayRecord(Base):
    __tablename__ = "replays"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    trace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("traces.id"), nullable=False
    )
    span_id: Mapped[str] = mapped_column(Text, nullable=False)
    edited_input: Mapped[dict] = mapped_column(JSON, nullable=False)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    trace: Mapped[TraceRecord] = relationship("TraceRecord", back_populates="replays")
