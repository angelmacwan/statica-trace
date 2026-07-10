"""
anthropic_wrapper.py — Transparent wrapper for the Anthropic Python SDK client.

Intercepts all messages.create calls to capture model parameters,
prompts, system prompt, tools, outputs, and errors as a Statica Trace.

Matches backlog item 3.2.3.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from agentreplay.client import AgentReplayClient
from agentreplay.schema import (
    Message,
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


def wrap(
    original_client: Any, client: AgentReplayClient | None = None
) -> AnthropicClientWrapper:
    """Wrap an Anthropic client to capture messages calls automatically."""
    return AnthropicClientWrapper(original_client, client)


class AnthropicClientWrapper:
    """Wrapper around Anthropic client."""

    def __init__(
        self, original_client: Any, client: AgentReplayClient | None = None
    ) -> None:
        self._client = original_client
        self._replay_client = client or AgentReplayClient()

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._client, name)
        if name == "messages":
            return AnthropicMessagesWrapper(attr, self._replay_client)
        return attr


class AnthropicMessagesWrapper:
    """Wrapper around client.messages."""

    def __init__(self, messages: Any, replay_client: AgentReplayClient) -> None:
        self._messages = messages
        self._replay_client = replay_client

    def create(self, *args: Any, **kwargs: Any) -> Any:
        """Intercept messages.create and record trace."""
        started_at = datetime.now(tz=UTC)

        model = kwargs.get("model")
        messages = kwargs.get("messages") or []
        temperature = kwargs.get("temperature")
        max_tokens = kwargs.get("max_tokens")
        tools = kwargs.get("tools") or []
        system = kwargs.get("system")

        # Convert input messages
        span_messages = []

        # Handle system prompt if provided
        if system:
            if isinstance(system, str):
                span_messages.append(Message(role="system", content=system))
            elif isinstance(system, list):
                content_parts = []
                for b in system:
                    if isinstance(b, dict):
                        content_parts.append(b.get("text", ""))
                    elif hasattr(b, "text"):
                        content_parts.append(b.text)
                    else:
                        content_parts.append(str(b))
                span_messages.append(
                    Message(role="system", content="".join(content_parts))
                )

        # Handle user/assistant messages
        for msg in messages:
            if isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content")
                if isinstance(content, list):
                    content_str = "".join(
                        [
                            b.get("text", "") if isinstance(b, dict) else str(b)
                            for b in content
                        ]
                    )
                else:
                    content_str = content or ""
                span_messages.append(Message(role=role, content=content_str))
            else:
                role = getattr(msg, "role", "user")
                content = getattr(msg, "content", "")
                if isinstance(content, list):
                    content_str = "".join(
                        [b.text if hasattr(b, "text") else str(b) for b in content]
                    )
                else:
                    content_str = content or ""
                span_messages.append(Message(role=role, content=content_str))

        # Convert tool definitions
        span_tools = []
        for tool in tools:
            if isinstance(tool, dict):
                name = tool.get("name") or "tool"
                schema = tool.get("input_schema") or {}
                span_tools.append(ToolDefinition(name=name, schema=schema))
            else:
                name = getattr(tool, "name", "tool")
                schema = getattr(tool, "input_schema", {})
                span_tools.append(ToolDefinition(name=name, schema=schema))

        # Build parameters dict
        params: dict[str, Any] = {}
        if temperature is not None:
            params["temperature"] = temperature
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        for k, v in kwargs.items():
            if k not in [
                "model",
                "messages",
                "tools",
                "temperature",
                "max_tokens",
                "system",
            ]:
                try:
                    json.dumps(v)
                    params[k] = v
                except Exception:
                    params[k] = str(v)

        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())

        try:
            response = self._messages.create(*args, **kwargs)
            ended_at = datetime.now(tz=UTC)

            content_parts = []
            tool_calls = []
            if hasattr(response, "content") and isinstance(response.content, list):
                for block in response.content:
                    block_type = getattr(block, "type", "")
                    if block_type == "text":
                        content_parts.append(getattr(block, "text", ""))
                    elif block_type == "tool_use":
                        tc_name = getattr(block, "name", None)
                        tc_args = getattr(block, "input", {})
                        if tc_name:
                            tool_calls.append(ToolCall(name=tc_name, arguments=tc_args))

            # Build success span and trace
            span = Span(
                span_id=span_id,
                parent_span_id=None,
                type=SpanType.llm_call,
                name="messages_create",
                started_at=started_at,
                ended_at=ended_at,
                status=TraceStatus.success,
                input=SpanInput(
                    messages=span_messages,
                    model=model,
                    params=params,
                    tools=span_tools,
                ),
                output=SpanOutput(
                    content="\n".join(content_parts) if content_parts else None,
                    tool_calls=tool_calls,
                ),
            )

            trace = Trace(
                trace_id=trace_id,
                project_id="dummy",
                source=TraceSource.anthropic,
                started_at=started_at,
                ended_at=ended_at,
                status=TraceStatus.success,
                spans=[span],
            )
            self._replay_client.send(trace)

            return response

        except Exception as e:
            ended_at = datetime.now(tz=UTC)
            span = Span(
                span_id=span_id,
                parent_span_id=None,
                type=SpanType.llm_call,
                name="messages_create",
                started_at=started_at,
                ended_at=ended_at,
                status=TraceStatus.error,
                input=SpanInput(
                    messages=span_messages,
                    model=model,
                    params=params,
                    tools=span_tools,
                ),
                error=SpanError(message=str(e), type=type(e).__name__),
            )

            trace = Trace(
                trace_id=trace_id,
                project_id="dummy",
                source=TraceSource.anthropic,
                started_at=started_at,
                ended_at=ended_at,
                status=TraceStatus.error,
                spans=[span],
            )
            self._replay_client.send(trace)
            raise e
