"""
main.py — FastAPI application entry point for Statica Trace backend.

Implements all API endpoints defined in DOCS/agent-replay-debugger-spec.md § 8.3:

    POST   /v1/projects          — create project + return api_key  (2.1.2)
    GET    /v1/projects/me       — current project info             (2.1.4)
    POST   /v1/ingest            — ingest a trace payload           (2.2.1)
    GET    /v1/traces            — list traces (paginated)          (2.3.1)
    GET    /v1/traces/{id}       — full trace detail                (2.3.2)
    POST   /v1/replay            — replay an llm_call span          (2.4.1)

Backlog: Module 2
"""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agentreplay.schema import SpanType, Trace
from backend.auth import get_current_project_id
from backend.database import create_tables, get_db
from backend.models import Project, ReplayRecord, TraceRecord
from backend.replay_engine import run_replay
from backend.schemas import (
    ProjectCreate,
    ProjectCreateResponse,
    ProjectResponse,
    ReplayRequest,
    ReplayResponse,
    TraceListItem,
    TraceListResponse,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Statica Trace API",
    description="Agent replay debugger — trace ingestion and replay engine.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:  # pragma: no cover
    await create_tables()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/healthz", tags=["health"])
async def healthz() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /v1/projects — create project (no auth required)
# ---------------------------------------------------------------------------


@app.post(
    "/v1/projects",
    status_code=status.HTTP_201_CREATED,
    response_model=ProjectCreateResponse,
    tags=["projects"],
)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
) -> ProjectCreateResponse:
    """Create a new project and return a unique API key."""
    api_key = secrets.token_urlsafe(32)
    project = Project(
        id=str(uuid.uuid4()),
        name=body.name,
        api_key=api_key,
        created_at=datetime.now(tz=UTC),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectCreateResponse(
        id=project.id,
        name=project.name,
        api_key=project.api_key,
        created_at=project.created_at,
    )


# ---------------------------------------------------------------------------
# GET /v1/projects/me — project info (auth required)
# ---------------------------------------------------------------------------


@app.get(
    "/v1/projects/me",
    response_model=ProjectResponse,
    tags=["projects"],
)
async def get_project_me(
    project_id: Annotated[str, Depends(get_current_project_id)],
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Return authenticated project metadata. Does NOT return the api_key."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project: Project | None = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return ProjectResponse(
        id=project.id,
        name=project.name,
        created_at=project.created_at,
    )


# ---------------------------------------------------------------------------
# POST /v1/ingest — ingest a trace (auth required)
# ---------------------------------------------------------------------------


@app.post(
    "/v1/ingest",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["traces"],
)
async def ingest_trace(
    trace: Trace,
    project_id: Annotated[str, Depends(get_current_project_id)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Accept a validated Trace payload and store it as a JSONB blob.

    The ``project_id`` in the payload is **overridden** by the authenticated
    project to prevent cross-project pollution.
    """
    raw_payload = trace.model_dump(mode="json")
    # Ensure the stored project_id matches the authenticated caller.
    raw_payload["project_id"] = project_id

    record = TraceRecord(
        id=str(uuid.uuid4()),
        project_id=project_id,
        source=trace.source.value,
        status=trace.status.value,
        started_at=trace.started_at,
        ended_at=trace.ended_at,
        raw=raw_payload,
        created_at=datetime.now(tz=UTC),
    )
    db.add(record)
    await db.commit()
    return {"trace_id": record.id, "status": "accepted"}


# ---------------------------------------------------------------------------
# GET /v1/traces — list traces (auth required)
# ---------------------------------------------------------------------------


@app.get(
    "/v1/traces",
    response_model=TraceListResponse,
    tags=["traces"],
)
async def list_traces(
    project_id: Annotated[str, Depends(get_current_project_id)],
    db: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> TraceListResponse:
    """
    Return a paginated list of traces for the authenticated project.

    Query params:
    - ``status``: ``success`` | ``error``  — optional filter
    - ``limit``:  max rows (default 50)
    - ``offset``: pagination offset (default 0)

    Default sort: ``created_at DESC`` (newest first).
    """
    base_q = select(TraceRecord).where(TraceRecord.project_id == project_id)
    count_q = select(func.count()).where(TraceRecord.project_id == project_id)

    if status_filter in ("success", "error"):
        base_q = base_q.where(TraceRecord.status == status_filter)
        count_q = count_q.select_from(TraceRecord).where(
            TraceRecord.project_id == project_id,
            TraceRecord.status == status_filter,
        )

    base_q = base_q.order_by(TraceRecord.created_at.desc()).limit(limit).offset(offset)

    rows = (await db.execute(base_q)).scalars().all()
    total = (await db.execute(count_q)).scalar_one()

    items: list[TraceListItem] = []
    for row in rows:
        duration_ms: float | None = None
        if row.started_at and row.ended_at:
            duration_ms = (row.ended_at - row.started_at).total_seconds() * 1000
        items.append(
            TraceListItem(
                trace_id=row.id,
                source=row.source,
                status=row.status,
                started_at=row.started_at,
                ended_at=row.ended_at,
                duration_ms=duration_ms,
            )
        )

    return TraceListResponse(items=items, total=total, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# GET /v1/traces/{id} — trace detail (auth required)
# ---------------------------------------------------------------------------


@app.get(
    "/v1/traces/{trace_id}",
    tags=["traces"],
)
async def get_trace(
    trace_id: str,
    project_id: Annotated[str, Depends(get_current_project_id)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Return the full trace payload (including all spans) for a single trace.

    Returns HTTP 404 if the trace does not exist or belongs to another project.
    """
    result = await db.execute(
        select(TraceRecord).where(
            TraceRecord.id == trace_id,
            TraceRecord.project_id == project_id,
        )
    )
    record: TraceRecord | None = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Trace not found.")
    return record.raw


# ---------------------------------------------------------------------------
# POST /v1/replay — replay an llm_call span (auth required)
# ---------------------------------------------------------------------------


@app.post(
    "/v1/replay",
    response_model=ReplayResponse,
    tags=["replay"],
)
async def replay_span(
    body: ReplayRequest,
    project_id: Annotated[str, Depends(get_current_project_id)],
    x_provider_api_key: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> ReplayResponse:
    """
    Replay a single ``llm_call`` span with the caller's edited input.

    Requirements:
    - ``X-Provider-Api-Key`` header must be present (OpenAI or Anthropic key).
    - Only ``llm_call`` spans are replayable; returns 400 for other types.
    - The provider key is **never** stored.
    """
    if not x_provider_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Provider-Api-Key header is required to perform a replay.",
        )

    # Fetch the trace (must belong to authenticated project).
    result = await db.execute(
        select(TraceRecord).where(
            TraceRecord.id == body.trace_id,
            TraceRecord.project_id == project_id,
        )
    )
    trace_record: TraceRecord | None = result.scalar_one_or_none()
    if trace_record is None:
        raise HTTPException(status_code=404, detail="Trace not found.")

    # Find the span within the raw payload.
    raw = trace_record.raw or {}
    spans: list[dict] = raw.get("spans", [])
    span_raw: dict | None = next(
        (s for s in spans if s.get("span_id") == body.span_id), None
    )
    if span_raw is None:
        raise HTTPException(status_code=404, detail="Span not found in trace.")

    # Only llm_call spans are replayable.
    if span_raw.get("type") != SpanType.llm_call.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only 'llm_call' spans are replayable. "
            f"Span type is '{span_raw.get('type')}'.",
        )

    # Run the replay against the live provider API.
    replayed_output = await run_replay(
        span_raw=span_raw,
        edited_input=body.edited_input,
        provider_api_key=x_provider_api_key,
        source=raw.get("source", ""),
    )

    # Persist the replay attempt.
    original_output: dict | None = span_raw.get("output")
    replay_record = ReplayRecord(
        id=str(uuid.uuid4()),
        trace_id=body.trace_id,
        span_id=body.span_id,
        edited_input=body.edited_input,
        output=replayed_output,
        created_at=datetime.now(tz=UTC),
    )
    db.add(replay_record)
    await db.commit()

    return ReplayResponse(
        replay_id=replay_record.id,
        trace_id=body.trace_id,
        span_id=body.span_id,
        original_output=original_output,
        replayed_output=replayed_output,
    )
