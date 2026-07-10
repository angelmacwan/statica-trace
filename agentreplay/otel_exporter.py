"""
otel_exporter.py — OpenTelemetry Span Exporter for Statica Trace.

Maps incoming OpenTelemetry spans conforming to GenAI semantic conventions
to the Statica Trace schema and forwards them to the ingest backend.

Matches backlog item 3.3.1.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import StatusCode

from agentreplay.client import AgentReplayClient
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

logger = logging.getLogger("agentreplay")


class AgentReplayOTelExporter(SpanExporter):
    """
    OpenTelemetry SpanExporter that translates OTel GenAI spans into
    Statica Trace objects and posts them to the ingest API.
    """

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str | None = None,
        client: AgentReplayClient | None = None,
    ) -> None:
        self.client = client or AgentReplayClient(api_key=api_key, endpoint=endpoint)
        # Store accumulated spans by trace_id to support incremental updates
        self._traces: dict[str, list[Span]] = {}

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Translate OTel spans and send them to the Statica Trace backend."""
        try:
            # Group spans in this export batch by trace_id
            affected_trace_ids = set()

            for otel_span in spans:
                trace_id_hex = f"{otel_span.context.trace_id:032x}"
                affected_trace_ids.add(trace_id_hex)

                mapped_span = self._map_span(otel_span)

                if trace_id_hex not in self._traces:
                    self._traces[trace_id_hex] = []

                # Avoid duplicates if the same span is exported multiple times
                existing_spans = self._traces[trace_id_hex]
                for idx, s in enumerate(existing_spans):
                    if s.span_id == mapped_span.span_id:
                        existing_spans[idx] = mapped_span
                        break
                else:
                    existing_spans.append(mapped_span)

            # Reconstruct and send traces for all affected trace_ids
            for trace_id_hex in affected_trace_ids:
                all_spans = self._traces[trace_id_hex]
                if not all_spans:
                    continue

                # Determine timing across all spans in the trace
                started_at = min(s.started_at for s in all_spans)
                ended_at = max(s.ended_at for s in all_spans)

                # Determine overall trace status (error if any span is error)
                status = TraceStatus.success
                if any(s.status == TraceStatus.error for s in all_spans):
                    status = TraceStatus.error

                trace = Trace(
                    trace_id=trace_id_hex,
                    project_id="dummy",  # Overridden by backend
                    source=TraceSource.otel,
                    started_at=started_at,
                    ended_at=ended_at,
                    status=status,
                    spans=all_spans,
                )

                self.client.send(trace)

            return SpanExportResult.SUCCESS
        except Exception as e:
            logger.warning("AgentReplayOTelExporter failed to export spans: %s", e)
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        """Shutdown the exporter and close the underlying client."""
        self.client.close()

    def _map_span(self, otel_span: ReadableSpan) -> Span:
        """Map a single OTel ReadableSpan to our Span Pydantic model."""
        span_id_hex = f"{otel_span.context.span_id:016x}"
        parent_span_id_hex = None
        if otel_span.parent and otel_span.parent.span_id:
            parent_span_id_hex = f"{otel_span.parent.span_id:016x}"

        started_at = datetime.fromtimestamp(otel_span.start_time / 1e9, tz=UTC)
        ended_at = datetime.fromtimestamp(
            (otel_span.end_time or otel_span.start_time) / 1e9, tz=UTC
        )

        attrs = otel_span.attributes or {}

        # Determine Span Type based on attributes and conventions
        span_type = SpanType.agent_step
        if "gen_ai.system" in attrs or "gen_ai.request.model" in attrs:
            span_type = SpanType.llm_call
        elif (
            "tool" in otel_span.name.lower()
            or "tool.name" in attrs
            or "gen_ai.tool" in attrs
        ):
            span_type = SpanType.tool_call
        elif (
            "retrieve" in otel_span.name.lower()
            or "db.system" in attrs
            or "retrieval" in attrs
        ):
            span_type = SpanType.retrieval

        # 1. Parse Input
        messages: list[Message] = []
        model = attrs.get("gen_ai.request.model") or attrs.get("gen_ai.response.model")

        # Parse message content if it is standard prompt
        prompt = attrs.get("gen_ai.prompt") or attrs.get("gen_ai.request.prompt")
        if prompt:
            messages.append(Message(role="user", content=str(prompt)))

        # Handle serialized messages (OpenLLMetry format)
        raw_msgs = attrs.get("gen_ai.request.messages")
        if raw_msgs:
            try:
                parsed = json.loads(raw_msgs) if isinstance(raw_msgs, str) else raw_msgs
                if isinstance(parsed, list):
                    for m in parsed:
                        role = m.get("role", "user")
                        content = m.get("content") or ""
                        messages.append(Message(role=role, content=str(content)))
            except Exception:
                pass

        # Parse tool definitions
        tools: list[ToolDefinition] = []
        raw_tools = attrs.get("gen_ai.request.tools")
        if raw_tools:
            try:
                parsed_tools = (
                    json.loads(raw_tools) if isinstance(raw_tools, str) else raw_tools
                )
                if isinstance(parsed_tools, list):
                    for t in parsed_tools:
                        name = t.get("name") or "tool"
                        schema = t.get("schema") or t.get("parameters") or {}
                        tools.append(ToolDefinition(name=name, schema=schema))
            except Exception:
                pass

        # Parse retrieved context
        retrieved_context: list[RetrievedContext] = []
        raw_chunks = attrs.get("rag.chunks") or attrs.get("retrieval.documents")
        if raw_chunks:
            try:
                parsed_chunks = (
                    json.loads(raw_chunks)
                    if isinstance(raw_chunks, str)
                    else raw_chunks
                )
                if isinstance(parsed_chunks, list):
                    for c in parsed_chunks:
                        source = c.get("source") or "retrieval"
                        content = c.get("content") or c.get("text") or ""
                        score = c.get("score")
                        retrieved_context.append(
                            RetrievedContext(
                                source=source, content=content, score=score
                            )
                        )
            except Exception:
                pass

        params: dict[str, Any] = {}
        for k, v in attrs.items():
            if k.startswith("gen_ai.request.") and k not in [
                "gen_ai.request.model",
                "gen_ai.request.messages",
                "gen_ai.request.tools",
            ]:
                # Strip prefix
                param_key = k[len("gen_ai.request.") :]
                params[param_key] = v

        span_input = SpanInput(
            messages=messages,
            model=str(model) if model else None,
            params=params,
            tools=tools,
            retrieved_context=retrieved_context,
        )

        # 2. Parse Output
        content = attrs.get("gen_ai.completion") or attrs.get(
            "gen_ai.response.completion"
        )
        if not content:
            # Check for serialized response messages
            raw_resp = attrs.get("gen_ai.response.messages")
            if raw_resp:
                try:
                    parsed_resp = (
                        json.loads(raw_resp) if isinstance(raw_resp, str) else raw_resp
                    )
                    if isinstance(parsed_resp, list) and parsed_resp:
                        first = parsed_resp[0]
                        if isinstance(first, dict):
                            content = first.get("content")
                except Exception:
                    pass

        tool_calls: list[ToolCall] = []
        raw_calls = attrs.get("gen_ai.response.tool_calls")
        if raw_calls:
            try:
                parsed_calls = (
                    json.loads(raw_calls) if isinstance(raw_calls, str) else raw_calls
                )
                if isinstance(parsed_calls, list):
                    for call in parsed_calls:
                        name = call.get("name")
                        args = call.get("args") or call.get("arguments") or {}
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                pass
                        if name:
                            tool_calls.append(ToolCall(name=name, arguments=args))
            except Exception:
                pass

        span_output = SpanOutput(
            content=str(content) if content else None, tool_calls=tool_calls
        )

        # 3. Parse Error & Status
        status = TraceStatus.success
        error = None
        if otel_span.status.status_code == StatusCode.ERROR:
            status = TraceStatus.error
            error_msg = otel_span.status.description or "OTel Span Error"
            error_type = "OTelError"

            # Check event logs for python exceptions
            for event in otel_span.events or []:
                if event.name == "exception":
                    msg = event.attributes.get("exception.message")
                    typ = event.attributes.get("exception.type")
                    if msg:
                        error_msg = str(msg)
                    if typ:
                        error_type = str(typ)
                    break

            error = SpanError(message=error_msg, type=error_type)

        return Span(
            span_id=span_id_hex,
            parent_span_id=parent_span_id_hex,
            type=span_type,
            name=otel_span.name,
            started_at=started_at,
            ended_at=ended_at,
            status=status,
            input=span_input,
            output=span_output,
            error=error,
        )
