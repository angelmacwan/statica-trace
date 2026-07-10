"""
tests/test_schema.py — Unit tests for agentreplay/schema.py

Covers every Pydantic model, enum, serialization round-trip, and validation
edge-case required by backlog item 1.2.1.

Mocking strategy: pure in-process Pydantic validation — no I/O, no HTTP.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from agentreplay.schema import (
    Message,
    RetrievedContext,
    Span,
    SpanError,
    SpanInput,
    SpanOutput,
    SpanType,
    ToolCall,
    ToolDefinition,
    Trace,
    TraceSource,
    TraceStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _make_span(
    *,
    span_type: SpanType = SpanType.llm_call,
    parent_span_id: str | None = None,
) -> Span:
    """Return a minimal valid Span."""
    return Span(
        span_id=str(uuid.uuid4()),
        parent_span_id=parent_span_id,
        type=span_type,
        name="test-span",
        started_at=_now(),
        ended_at=_now(),
    )


def _make_trace(spans: list[Span] | None = None) -> Trace:
    """Return a minimal valid Trace."""
    return Trace(
        trace_id=str(uuid.uuid4()),
        project_id=str(uuid.uuid4()),
        source=TraceSource.langchain,
        started_at=_now(),
        ended_at=_now(),
        status=TraceStatus.success,
        spans=spans if spans is not None else [],
    )


# ===========================================================================
# 1. Enum Tests
# ===========================================================================


class TestTraceSource:
    """TraceSource enum — valid values and rejection of unknown strings."""

    def test_all_valid_values(self) -> None:
        for val in ("langchain", "langgraph", "openai", "anthropic", "otel"):
            src = TraceSource(val)
            assert src.value == val

    def test_unknown_value_raises(self) -> None:
        with pytest.raises(ValueError):
            TraceSource("unknown_source")

    def test_trace_source_in_model_rejects_unknown(self) -> None:
        """Validation through a Pydantic model also raises ValidationError."""
        with pytest.raises(ValidationError):
            Trace(
                trace_id=str(uuid.uuid4()),
                project_id=str(uuid.uuid4()),
                source="not_a_source",  # type: ignore[arg-type]
                started_at=_now(),
                ended_at=_now(),
                status=TraceStatus.success,
            )


class TestSpanType:
    """SpanType enum — valid values and rejection of unknown strings."""

    def test_all_valid_values(self) -> None:
        for val in ("llm_call", "tool_call", "retrieval", "agent_step"):
            stype = SpanType(val)
            assert stype.value == val

    def test_unknown_value_raises(self) -> None:
        with pytest.raises(ValueError):
            SpanType("bad_type")

    def test_span_type_in_model_rejects_unknown(self) -> None:
        with pytest.raises(ValidationError):
            Span(
                span_id=str(uuid.uuid4()),
                type="not_a_type",  # type: ignore[arg-type]
                name="x",
                started_at=_now(),
                ended_at=_now(),
            )


class TestTraceStatus:
    """TraceStatus enum values."""

    def test_success_and_error(self) -> None:
        assert TraceStatus("success") == TraceStatus.success
        assert TraceStatus("error") == TraceStatus.error

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError):
            TraceStatus("pending")


# ===========================================================================
# 2. Sub-model Construction
# ===========================================================================


class TestMessage:
    def test_valid_construction(self) -> None:
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_model_dump(self) -> None:
        msg = Message(role="assistant", content="Hi there")
        d = msg.model_dump()
        assert d == {"role": "assistant", "content": "Hi there"}

    def test_missing_role_raises(self) -> None:
        with pytest.raises(ValidationError):
            Message(content="oops")  # type: ignore[call-arg]

    def test_missing_content_raises(self) -> None:
        with pytest.raises(ValidationError):
            Message(role="user")  # type: ignore[call-arg]


class TestToolDefinition:
    def test_valid_via_keyword(self) -> None:
        td = ToolDefinition(name="search", schema={"type": "object"})
        assert td.name == "search"
        assert td.schema_ == {"type": "object"}

    def test_schema_field_alias(self) -> None:
        """The field is stored as schema_ but aliased as 'schema' in JSON."""
        td = ToolDefinition(name="calc", schema={"query": "string"})
        dumped = td.model_dump(by_alias=True)
        assert "schema" in dumped
        assert dumped["schema"] == {"query": "string"}

    def test_empty_schema_default(self) -> None:
        td = ToolDefinition(name="noop")
        assert td.schema_ == {}

    def test_model_dump_by_alias_round_trip(self) -> None:
        td = ToolDefinition(name="ping", schema={"x": 1})
        d = td.model_dump(by_alias=True)
        td2 = ToolDefinition.model_validate(d)
        assert td2.name == td.name
        assert td2.schema_ == td.schema_


class TestToolCall:
    def test_valid_construction(self) -> None:
        tc = ToolCall(name="get_weather", arguments={"city": "Paris"})
        assert tc.name == "get_weather"
        assert tc.arguments == {"city": "Paris"}

    def test_default_empty_arguments(self) -> None:
        tc = ToolCall(name="noop")
        assert tc.arguments == {}

    def test_model_dump(self) -> None:
        tc = ToolCall(name="foo", arguments={"a": 1})
        assert tc.model_dump() == {"name": "foo", "arguments": {"a": 1}}


class TestRetrievedContext:
    def test_valid_with_score(self) -> None:
        rc = RetrievedContext(source="wiki", content="Paris is a city.", score=0.9)
        assert rc.score == 0.9

    def test_score_optional(self) -> None:
        rc = RetrievedContext(source="web", content="Some content")
        assert rc.score is None

    def test_model_dump(self) -> None:
        rc = RetrievedContext(source="s3", content="doc", score=None)
        d = rc.model_dump()
        assert d["source"] == "s3"
        assert d["score"] is None


class TestSpanInput:
    def test_all_defaults(self) -> None:
        si = SpanInput()
        assert si.messages == []
        assert si.model is None
        assert si.params == {}
        assert si.tools == []
        assert si.retrieved_context == []

    def test_fully_populated(self) -> None:
        si = SpanInput(
            messages=[Message(role="user", content="Hi")],
            model="gpt-4o",
            params={"temperature": 0.7},
            tools=[ToolDefinition(name="calc")],
            retrieved_context=[RetrievedContext(source="db", content="chunk")],
        )
        assert si.model == "gpt-4o"
        assert len(si.messages) == 1
        assert len(si.tools) == 1
        assert len(si.retrieved_context) == 1

    def test_retrieved_context_can_be_omitted(self) -> None:
        """Acceptance criteria: retrieved_context can be omitted entirely."""
        si = SpanInput(messages=[Message(role="user", content="x")])
        assert si.retrieved_context == []


class TestSpanOutput:
    def test_all_defaults(self) -> None:
        so = SpanOutput()
        assert so.content is None
        assert so.tool_calls == []

    def test_with_content(self) -> None:
        so = SpanOutput(content="42")
        assert so.content == "42"

    def test_with_tool_calls(self) -> None:
        so = SpanOutput(tool_calls=[ToolCall(name="ping")])
        assert len(so.tool_calls) == 1


class TestSpanError:
    def test_valid_construction(self) -> None:
        err = SpanError(message="Something went wrong", type="ValueError")
        assert err.message == "Something went wrong"
        assert err.type == "ValueError"

    def test_model_dump(self) -> None:
        err = SpanError(message="oops", type="RuntimeError")
        assert err.model_dump() == {"message": "oops", "type": "RuntimeError"}

    def test_missing_fields_raise(self) -> None:
        with pytest.raises(ValidationError):
            SpanError(message="no type")  # type: ignore[call-arg]


# ===========================================================================
# 3. Span Construction
# ===========================================================================


class TestSpan:
    def test_minimal_required_fields(self) -> None:
        span = _make_span()
        assert span.parent_span_id is None
        assert span.status == TraceStatus.success
        assert span.error is None

    def test_root_span_is_valid(self) -> None:
        """Acceptance criteria: a span with parent_span_id=None is valid."""
        span = Span(
            span_id="root",
            parent_span_id=None,
            type=SpanType.agent_step,
            name="root",
            started_at=_now(),
            ended_at=_now(),
        )
        assert span.parent_span_id is None

    def test_child_span_with_parent(self) -> None:
        parent_id = str(uuid.uuid4())
        child = _make_span(parent_span_id=parent_id)
        assert child.parent_span_id == parent_id

    def test_all_span_types(self) -> None:
        for stype in SpanType:
            span = _make_span(span_type=stype)
            assert span.type == stype

    def test_error_span(self) -> None:
        span = _make_span()
        span.status = TraceStatus.error
        span.error = SpanError(message="boom", type="RuntimeError")
        assert span.status == TraceStatus.error
        assert span.error is not None

    def test_model_dump_shape(self) -> None:
        span = _make_span()
        d = span.model_dump()
        assert "span_id" in d
        assert "parent_span_id" in d
        assert "type" in d
        assert "input" in d
        assert "output" in d
        assert "error" in d

    def test_missing_span_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            Span(  # type: ignore[call-arg]
                type=SpanType.llm_call,
                name="x",
                started_at=_now(),
                ended_at=_now(),
            )


# ===========================================================================
# 4. Trace Construction
# ===========================================================================


class TestTrace:
    def test_zero_spans_is_valid(self) -> None:
        """Acceptance criteria: a Trace with zero spans is valid."""
        trace = _make_trace(spans=[])
        assert trace.spans == []

    def test_with_spans(self) -> None:
        spans = [_make_span() for _ in range(3)]
        trace = _make_trace(spans=spans)
        assert len(trace.spans) == 3

    def test_all_sources_valid(self) -> None:
        for src in TraceSource:
            trace = _make_trace()
            trace.source = src
            assert trace.source == src

    def test_model_dump_shape(self) -> None:
        trace = _make_trace()
        d = trace.model_dump()
        assert "trace_id" in d
        assert "project_id" in d
        assert "source" in d
        assert "started_at" in d
        assert "ended_at" in d
        assert "status" in d
        assert "spans" in d


# ===========================================================================
# 5. Serialization Round-Trip Tests
# ===========================================================================


class TestRoundTrip:
    """All acceptance criteria for .model_dump() / .model_validate() losslessness."""

    def test_simple_trace_round_trip(self) -> None:
        """Simple trace (no spans) serializes and deserializes without loss."""
        trace = _make_trace()
        d = trace.model_dump()
        restored = Trace.model_validate(d)
        assert restored.trace_id == trace.trace_id
        assert restored.project_id == trace.project_id
        assert restored.source == trace.source
        assert restored.status == trace.status

    def test_trace_with_llm_call_span_round_trip(self) -> None:
        span = Span(
            span_id=str(uuid.uuid4()),
            parent_span_id=None,
            type=SpanType.llm_call,
            name="chat",
            started_at=_now(),
            ended_at=_now(),
            input=SpanInput(
                messages=[
                    Message(role="system", content="You are helpful."),
                    Message(role="user", content="Explain gravity."),
                ],
                model="gpt-4o",
                params={"temperature": 0.5, "max_tokens": 512},
                tools=[ToolDefinition(name="search", schema={"q": "string"})],
            ),
            output=SpanOutput(content="Gravity is a force…"),
        )
        trace = _make_trace(spans=[span])
        d = trace.model_dump()
        restored = Trace.model_validate(d)

        assert len(restored.spans) == 1
        rs = restored.spans[0]
        assert rs.span_id == span.span_id
        assert rs.type == SpanType.llm_call
        assert len(rs.input.messages) == 2
        assert rs.input.messages[0].role == "system"
        assert rs.input.model == "gpt-4o"
        assert rs.output.content == "Gravity is a force…"

    def test_trace_with_retrieved_context_round_trip(self) -> None:
        span = Span(
            span_id=str(uuid.uuid4()),
            type=SpanType.retrieval,
            name="retrieve",
            started_at=_now(),
            ended_at=_now(),
            input=SpanInput(
                messages=[Message(role="user", content="What is AI?")],
                retrieved_context=[
                    RetrievedContext(source="wiki", content="AI is...", score=0.88),
                    RetrievedContext(source="blog", content="Another chunk"),
                ],
            ),
            output=SpanOutput(content="AI is artificial intelligence."),
        )
        trace = _make_trace(spans=[span])
        d = trace.model_dump()
        restored = Trace.model_validate(d)

        rs = restored.spans[0]
        assert len(rs.input.retrieved_context) == 2
        assert rs.input.retrieved_context[0].score == pytest.approx(0.88)
        assert rs.input.retrieved_context[1].score is None

    def test_trace_with_tool_call_span_round_trip(self) -> None:
        span = Span(
            span_id=str(uuid.uuid4()),
            type=SpanType.tool_call,
            name="search",
            started_at=_now(),
            ended_at=_now(),
            output=SpanOutput(
                tool_calls=[
                    ToolCall(name="search", arguments={"query": "Paris"}),
                ]
            ),
        )
        trace = _make_trace(spans=[span])
        d = trace.model_dump()
        restored = Trace.model_validate(d)

        rs = restored.spans[0]
        assert rs.output.tool_calls[0].name == "search"
        assert rs.output.tool_calls[0].arguments == {"query": "Paris"}

    def test_error_span_round_trip(self) -> None:
        span = Span(
            span_id=str(uuid.uuid4()),
            type=SpanType.llm_call,
            name="chat",
            started_at=_now(),
            ended_at=_now(),
            status=TraceStatus.error,
            error=SpanError(message="Timeout", type="TimeoutError"),
        )
        trace = _make_trace(spans=[span])
        d = trace.model_dump()
        restored = Trace.model_validate(d)

        rs = restored.spans[0]
        assert rs.status == TraceStatus.error
        assert rs.error is not None
        assert rs.error.message == "Timeout"
        assert rs.error.type == "TimeoutError"

    def test_fifty_spans_round_trip_lossless(self) -> None:
        """Acceptance criteria: a Trace with 50 spans serializes without data loss."""
        spans = []
        root_id = str(uuid.uuid4())
        root_span = Span(
            span_id=root_id,
            parent_span_id=None,
            type=SpanType.agent_step,
            name="agent-root",
            started_at=_now(),
            ended_at=_now(),
        )
        spans.append(root_span)

        for i in range(49):
            span = Span(
                span_id=str(uuid.uuid4()),
                parent_span_id=root_id,
                type=SpanType.llm_call,
                name=f"step-{i}",
                started_at=_now(),
                ended_at=_now(),
                input=SpanInput(
                    messages=[Message(role="user", content=f"prompt {i}")],
                    model="gpt-4o-mini",
                ),
                output=SpanOutput(content=f"response {i}"),
            )
            spans.append(span)

        assert len(spans) == 50
        trace = _make_trace(spans=spans)
        d = trace.model_dump()
        restored = Trace.model_validate(d)

        assert len(restored.spans) == 50
        # Spot-check first and last
        assert restored.spans[0].span_id == root_id
        assert restored.spans[0].parent_span_id is None
        assert restored.spans[49].input.messages[0].content == "prompt 48"
        assert restored.spans[49].output.content == "response 48"

    def test_model_dump_mode_json_produces_string_datetimes(self) -> None:
        """Datetimes serialize as ISO 8601 strings in JSON mode."""
        trace = _make_trace()
        d = trace.model_dump(mode="json")
        assert isinstance(d["started_at"], str)
        assert isinstance(d["ended_at"], str)

    def test_all_optional_fields_omitted(self) -> None:
        """A span with no optional fields set serializes and validates cleanly."""
        span = Span(
            span_id="s1",
            type=SpanType.agent_step,
            name="step",
            started_at=_now(),
            ended_at=_now(),
        )
        d = span.model_dump()
        restored = Span.model_validate(d)
        assert restored.span_id == "s1"
        assert restored.error is None
        assert restored.parent_span_id is None

    def test_flat_spans_with_parent_references(self) -> None:
        """Spans are stored as a flat list; parent/child via parent_span_id refs."""
        root_id = str(uuid.uuid4())
        child_id = str(uuid.uuid4())

        root = Span(
            span_id=root_id,
            parent_span_id=None,
            type=SpanType.agent_step,
            name="root",
            started_at=_now(),
            ended_at=_now(),
        )
        child = Span(
            span_id=child_id,
            parent_span_id=root_id,
            type=SpanType.llm_call,
            name="llm",
            started_at=_now(),
            ended_at=_now(),
        )

        trace = _make_trace(spans=[root, child])
        d = trace.model_dump()
        restored = Trace.model_validate(d)

        span_map = {s.span_id: s for s in restored.spans}
        assert span_map[child_id].parent_span_id == root_id
        assert span_map[root_id].parent_span_id is None
