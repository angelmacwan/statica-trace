"""
Shared pytest fixtures for the entire Statica Trace test suite.

These fixtures provide ready-made Pydantic model instances (sample traces,
spans, etc.) that all test modules can import and use without re-defining
their own factories.

Referenced by: backlog items 0.1.2
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

# ---------------------------------------------------------------------------
# Lazy import guard: conftest is collected before the agentreplay package is
# installed as an editable dependency. Use a try/except so pytest --collect
# doesn't blow up in a fresh environment before `make install`.
# ---------------------------------------------------------------------------
try:
    from agentreplay.schema import (
        Message,
        RetrievedContext,
        Span,
        SpanInput,
        SpanOutput,
        SpanType,
        ToolCall,
        ToolDefinition,
        Trace,
        TraceSource,
        TraceStatus,
    )

    _SCHEMA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SCHEMA_AVAILABLE = False


# ---------------------------------------------------------------------------
# Helper: current UTC timestamp
# ---------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(tz=UTC)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_llm_call_span() -> Span:
    """A minimal but complete llm_call span with one user message and output."""
    assert _SCHEMA_AVAILABLE, "agentreplay package not installed — run `make install`"
    return Span(
        span_id=str(uuid.uuid4()),
        parent_span_id=None,
        type=SpanType.llm_call,
        name="chat",
        started_at=_now(),
        ended_at=_now(),
        input=SpanInput(
            messages=[
                Message(role="system", content="You are a helpful assistant."),
                Message(role="user", content="What is 2+2?"),
            ],
            model="gpt-4o-mini",
            params={"temperature": 0.0, "max_tokens": 256},
        ),
        output=SpanOutput(content="4"),
    )


@pytest.fixture()
def sample_tool_call_span() -> Span:
    """A tool_call span that references a parent llm_call span."""
    assert _SCHEMA_AVAILABLE, "agentreplay package not installed — run `make install`"
    parent_id = str(uuid.uuid4())
    return Span(
        span_id=str(uuid.uuid4()),
        parent_span_id=parent_id,
        type=SpanType.tool_call,
        name="search",
        started_at=_now(),
        ended_at=_now(),
        input=SpanInput(
            messages=[],
            tools=[ToolDefinition(name="search", schema={"query": "string"})],
        ),
        output=SpanOutput(
            tool_calls=[
                ToolCall(name="search", arguments={"query": "capital of France"})
            ]
        ),
    )


@pytest.fixture()
def sample_rag_span() -> Span:
    """A retrieval span with retrieved_context populated."""
    assert _SCHEMA_AVAILABLE, "agentreplay package not installed — run `make install`"
    return Span(
        span_id=str(uuid.uuid4()),
        parent_span_id=None,
        type=SpanType.retrieval,
        name="retrieve",
        started_at=_now(),
        ended_at=_now(),
        input=SpanInput(
            messages=[Message(role="user", content="What is Paris?")],
            retrieved_context=[
                RetrievedContext(
                    source="wikipedia",
                    content="Paris is the capital of France.",
                    score=0.95,
                )
            ],
        ),
        output=SpanOutput(content="Paris is the capital of France."),
    )


@pytest.fixture()
def sample_trace(
    sample_llm_call_span: Span,
    sample_tool_call_span: Span,
) -> Trace:
    """
    A complete Trace containing one llm_call span and one tool_call span.
    The tool_call's parent_span_id is updated to reference the llm_call span.
    """
    assert _SCHEMA_AVAILABLE, "agentreplay package not installed — run `make install`"
    # Wire the parent relationship properly
    sample_tool_call_span.parent_span_id = sample_llm_call_span.span_id

    return Trace(
        trace_id=str(uuid.uuid4()),
        project_id=str(uuid.uuid4()),
        source=TraceSource.langchain,
        started_at=_now(),
        ended_at=_now(),
        status=TraceStatus.success,
        spans=[sample_llm_call_span, sample_tool_call_span],
    )
