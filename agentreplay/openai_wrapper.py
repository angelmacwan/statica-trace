"""
openai_wrapper.py — Transparent wrapper for the OpenAI Python SDK client.

Intercepts all chat.completions.create calls to capture model parameters,
prompts, tools, outputs, and errors as a Statica Trace.

Matches backlog item 3.2.2.
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
) -> OpenAIClientWrapper:
    """Wrap an OpenAI client to capture completions calls automatically."""
    return OpenAIClientWrapper(original_client, client)


class OpenAIClientWrapper:
    """Wrapper around openai.OpenAI client."""

    def __init__(
        self, original_client: Any, client: AgentReplayClient | None = None
    ) -> None:
        self._client = original_client
        self._replay_client = client or AgentReplayClient()

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._client, name)
        if name == "chat":
            return OpenAIChatWrapper(attr, self._replay_client)
        return attr


class OpenAIChatWrapper:
    """Wrapper around client.chat."""

    def __init__(self, chat: Any, replay_client: AgentReplayClient) -> None:
        self._chat = chat
        self._replay_client = replay_client

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._chat, name)
        if name == "completions":
            return OpenAICompletionsWrapper(attr, self._replay_client)
        return attr


class OpenAICompletionsWrapper:
    """Wrapper around client.chat.completions."""

    def __init__(self, completions: Any, replay_client: AgentReplayClient) -> None:
        self._completions = completions
        self._replay_client = replay_client

    def create(self, *args: Any, **kwargs: Any) -> Any:
        """Intercept completions.create and record trace."""
        started_at = datetime.now(tz=UTC)

        model = kwargs.get("model")
        messages = kwargs.get("messages") or []
        temperature = kwargs.get("temperature")
        max_tokens = kwargs.get("max_tokens")
        tools = kwargs.get("tools") or []

        # Convert input messages
        span_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content") or ""
                span_messages.append(Message(role=role, content=content))
            else:
                role = getattr(msg, "role", "user")
                content = getattr(msg, "content", "") or ""
                span_messages.append(Message(role=role, content=content))

        # Convert tool definitions
        span_tools = []
        for tool in tools:
            if isinstance(tool, dict):
                func = tool.get("function") or {}
                name = func.get("name") or tool.get("name") or "tool"
                schema = func.get("parameters") or tool.get("schema") or {}
                span_tools.append(ToolDefinition(name=name, schema=schema))

        # Build parameters dict
        params: dict[str, Any] = {}
        if temperature is not None:
            params["temperature"] = temperature
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        for k, v in kwargs.items():
            if k not in ["model", "messages", "tools", "temperature", "max_tokens"]:
                try:
                    json.dumps(v)
                    params[k] = v
                except Exception:
                    params[k] = str(v)

        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())

        try:
            response = self._completions.create(*args, **kwargs)
            ended_at = datetime.now(tz=UTC)

            content = None
            tool_calls = []
            if hasattr(response, "choices") and len(response.choices) > 0:
                choice = response.choices[0]
                if hasattr(choice, "message"):
                    msg = choice.message
                    content = getattr(msg, "content", None)
                    tcs = getattr(msg, "tool_calls", None)
                    if tcs:
                        for tc in tcs:
                            func = getattr(tc, "function", None)
                            tc_name = (
                                getattr(func, "name", None)
                                if func
                                else getattr(tc, "name", None)
                            )
                            tc_args_str = (
                                getattr(func, "arguments", "{}")
                                if func
                                else getattr(tc, "arguments", "{}")
                            )
                            try:
                                tc_args = (
                                    json.loads(tc_args_str)
                                    if isinstance(tc_args_str, str)
                                    else tc_args_str
                                )
                            except Exception:
                                tc_args = {"raw": tc_args_str}
                            if tc_name:
                                tool_calls.append(
                                    ToolCall(name=tc_name, arguments=tc_args)
                                )

            # Build success span and trace
            span = Span(
                span_id=span_id,
                parent_span_id=None,
                type=SpanType.llm_call,
                name="chat_completion",
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
                    content=content,
                    tool_calls=tool_calls,
                ),
            )

            trace = Trace(
                trace_id=trace_id,
                project_id="dummy",
                source=TraceSource.openai,
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
                name="chat_completion",
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
                source=TraceSource.openai,
                started_at=started_at,
                ended_at=ended_at,
                status=TraceStatus.error,
                spans=[span],
            )
            self._replay_client.send(trace)
            raise e
