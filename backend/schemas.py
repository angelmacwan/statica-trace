"""
schemas.py — Pydantic request/response models for the FastAPI backend.

These are *separate* from agentreplay/schema.py (the universal trace schema).
They define the HTTP API contract: what the server accepts and returns.

Backlog: Module 2
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Project endpoints
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ProjectResponse(BaseModel):
    id: str
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectCreateResponse(ProjectResponse):
    api_key: str


# ---------------------------------------------------------------------------
# Trace list / detail
# ---------------------------------------------------------------------------


class TraceListItem(BaseModel):
    trace_id: str
    source: str
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    duration_ms: float | None

    model_config = {"from_attributes": True}


class TraceListResponse(BaseModel):
    items: list[TraceListItem]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


class ReplayRequest(BaseModel):
    trace_id: str
    span_id: str
    edited_input: dict


class ReplayResponse(BaseModel):
    replay_id: str
    trace_id: str
    span_id: str
    original_output: dict | None
    replayed_output: dict
