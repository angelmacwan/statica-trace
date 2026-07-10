"""
schema.py — Universal trace schema for Statica Trace.

This is the canonical Pydantic data model that every capture path (custom
SDK adapters and OTel bridge) must normalize into before storage.

Matches the data model in DOCS/agent-replay-debugger-spec.md § 6.

Backlog: 1.1.1 (schema definition), 0.1.2 (fixtures import from here)
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TraceSource(StrEnum):
    """The capture source / integration that produced this trace."""

    langchain = "langchain"
    langgraph = "langgraph"
    openai = "openai"
    anthropic = "anthropic"
    otel = "otel"


# Alias used on individual spans (same values, kept separate for clarity)
SpanSource = TraceSource


class TraceStatus(StrEnum):
    success = "success"
    error = "error"


class SpanType(StrEnum):
    llm_call = "llm_call"
    tool_call = "tool_call"
    retrieval = "retrieval"
    agent_step = "agent_step"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class Message(BaseModel):
    """A single chat message (system / user / assistant / tool)."""

    role: str
    content: str


class ToolDefinition(BaseModel):
    """A tool that was made available to the model during an llm_call span."""

    name: str
    schema_: dict[str, Any] = Field(default_factory=dict, alias="schema")

    model_config = {"populate_by_name": True}


class ToolCall(BaseModel):
    """A tool invocation returned by the model."""

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class RetrievedContext(BaseModel):
    """A single retrieved document chunk (RAG span)."""

    source: str
    content: str
    score: float | None = None


class SpanInput(BaseModel):
    """Everything the model / tool received as input."""

    messages: list[Message] = Field(default_factory=list)
    model: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    tools: list[ToolDefinition] = Field(default_factory=list)
    retrieved_context: list[RetrievedContext] = Field(default_factory=list)


class SpanOutput(BaseModel):
    """Everything produced by the model / tool."""

    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


class SpanError(BaseModel):
    """Error information when a span completes with status: error."""

    message: str
    type: str


# ---------------------------------------------------------------------------
# Top-level models
# ---------------------------------------------------------------------------


class Span(BaseModel):
    """A single step within a trace (llm_call, tool_call, retrieval, agent_step)."""

    span_id: str
    parent_span_id: str | None = None
    type: SpanType
    name: str
    started_at: datetime
    ended_at: datetime
    input: SpanInput = Field(default_factory=SpanInput)
    output: SpanOutput = Field(default_factory=SpanOutput)
    error: SpanError | None = None
    status: TraceStatus = TraceStatus.success


class Trace(BaseModel):
    """
    The top-level trace object.  Every capture path must produce one of these
    and call .model_dump() before sending to the ingest endpoint.
    """

    trace_id: str
    project_id: str
    source: TraceSource
    started_at: datetime
    ended_at: datetime
    status: TraceStatus
    spans: list[Span] = Field(default_factory=list)
