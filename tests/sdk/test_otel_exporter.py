"""
tests/sdk/test_otel_exporter.py — Unit tests for the OTel span exporter.

Matches backlog item 3.4.5.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import StatusCode

from agentreplay.client import AgentReplayClient
from agentreplay.otel_exporter import AgentReplayOTelExporter
from agentreplay.schema import SpanType, Trace, TraceStatus


def test_otel_exporter_llm_call_success() -> None:
    """A span with GenAI attributes maps to an llm_call span and Trace."""
    mock_client = MagicMock(spec=AgentReplayClient)
    exporter = AgentReplayOTelExporter(client=mock_client)

    provider = TracerProvider()
    processor = SimpleSpanProcessor(exporter)
    provider.add_span_processor(processor)
    tracer = provider.get_tracer("test-tracer")

    with tracer.start_as_current_span("chat_call") as span:
        span.set_attribute("gen_ai.system", "openai")
        span.set_attribute("gen_ai.request.model", "gpt-4o")
        span.set_attribute("gen_ai.request.temperature", 0.7)
        span.set_attribute("gen_ai.prompt", "Hello")
        span.set_attribute("gen_ai.completion", "Hi there")

    # Force flush and shutdown to ensure export is completed
    provider.shutdown()

    # Assert trace was constructed and sent
    assert mock_client.send.call_count == 1
    trace_obj = mock_client.send.call_args[0][0]
    assert isinstance(trace_obj, Trace)
    assert trace_obj.source == "otel"
    assert trace_obj.status == TraceStatus.success

    # Verify nested span
    assert len(trace_obj.spans) == 1
    span_obj = trace_obj.spans[0]
    assert span_obj.name == "chat_call"
    assert span_obj.type == SpanType.llm_call
    assert span_obj.input.model == "gpt-4o"
    assert span_obj.input.params == {"temperature": 0.7}
    assert len(span_obj.input.messages) == 1
    assert span_obj.input.messages[0].role == "user"
    assert span_obj.input.messages[0].content == "Hello"
    assert span_obj.output.content == "Hi there"


def test_otel_exporter_span_error() -> None:
    """A failed OTel span maps to an error trace with exception details."""
    mock_client = MagicMock(spec=AgentReplayClient)
    exporter = AgentReplayOTelExporter(client=mock_client)

    provider = TracerProvider()
    processor = SimpleSpanProcessor(exporter)
    provider.add_span_processor(processor)
    tracer = provider.get_tracer("test-tracer")

    with tracer.start_as_current_span("failed_call") as span:
        span.set_attribute("gen_ai.system", "anthropic")
        span.set_status(
            trace.Status(StatusCode.ERROR, "Anthropic API rate limit exceeded")
        )
        try:
            raise ValueError("Rate limit hit")
        except ValueError as e:
            span.record_exception(e)

    provider.shutdown()

    # Assert trace was constructed and sent
    assert mock_client.send.call_count == 1
    trace_obj = mock_client.send.call_args[0][0]
    assert isinstance(trace_obj, Trace)
    assert trace_obj.status == TraceStatus.error

    # Verify error span details
    assert len(trace_obj.spans) == 1
    span_obj = trace_obj.spans[0]
    assert span_obj.status == TraceStatus.error
    assert span_obj.error is not None
    assert span_obj.error.message == "Rate limit hit"
    assert span_obj.error.type == "ValueError"
