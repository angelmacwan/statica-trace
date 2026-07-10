"""
langchain.py — LangChain/LangGraph callback handler for Statica Trace.

Captures LLM calls, tool calls, and chain steps as spans, and flushes
the complete trace on root execution completion.

Matches backlog item 3.2.1.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

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

logger = logging.getLogger("agentreplay")


class AgentReplayCallbackHandler(BaseCallbackHandler):
    """
    Callback handler that hooks into the LangChain execution lifecycle
    to build and record execution traces.
    """

    # Tell LangChain to not ignore these runs
    raise_error: bool = True

    def __init__(
        self,
        api_key: str | None = None,
        client: AgentReplayClient | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.client = client or AgentReplayClient(api_key=api_key)

        self._lock = threading.Lock()
        self._spans: dict[str, Span] = {}
        self._parent_map: dict[str, str] = {}
        self._root_runs: set[str] = set()
        self._run_sources: dict[str, TraceSource] = {}

    def on_chain_start(
        self,
        serialized: dict[str, Any] | None,
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        run_id_str = str(run_id)
        parent_run_id_str = str(parent_run_id) if parent_run_id else None

        with self._lock:
            if parent_run_id_str:
                self._parent_map[run_id_str] = parent_run_id_str
            else:
                self._root_runs.add(run_id_str)
                # Detect if this is a LangGraph execution
                name = (serialized or {}).get("name") or ""
                is_graph = (
                    "langgraph" in (tags or [])
                    or "graph" in name.lower()
                    or (metadata and "langgraph" in metadata)
                )
                self._run_sources[run_id_str] = (
                    TraceSource.langgraph if is_graph else TraceSource.langchain
                )

        chain_name = (serialized or {}).get("name") or "chain"

        # Safely convert inputs to params
        params: dict[str, Any] = {}
        if isinstance(inputs, dict):
            for k, v in inputs.items():
                try:
                    # Ensure it is JSON serializable
                    json.dumps(v)
                    params[k] = v
                except Exception:
                    params[k] = str(v)

        span = Span(
            span_id=run_id_str,
            parent_span_id=parent_run_id_str,
            type=SpanType.agent_step,
            name=chain_name,
            started_at=datetime.now(tz=UTC),
            ended_at=datetime.now(tz=UTC),
            input=SpanInput(params=params),
        )

        with self._lock:
            self._spans[run_id_str] = span

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        run_id_str = str(run_id)
        with self._lock:
            span = self._spans.get(run_id_str)
        if not span:
            return

        span.ended_at = datetime.now(tz=UTC)
        span.status = TraceStatus.success

        # Safely convert outputs to string or content
        content = None
        if outputs:
            try:
                content = json.dumps(outputs)
            except Exception:
                content = str(outputs)
        span.output = SpanOutput(content=content)

        self._check_and_send_trace(run_id_str)

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        run_id_str = str(run_id)
        with self._lock:
            span = self._spans.get(run_id_str)
        if not span:
            return

        span.ended_at = datetime.now(tz=UTC)
        span.status = TraceStatus.error
        span.error = SpanError(message=str(error), type=type(error).__name__)

        self._check_and_send_trace(run_id_str)

    def on_llm_start(
        self,
        serialized: dict[str, Any] | None,
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        run_id_str = str(run_id)
        parent_run_id_str = str(parent_run_id) if parent_run_id else None

        with self._lock:
            if parent_run_id_str:
                self._parent_map[run_id_str] = parent_run_id_str

        model_name = self._extract_model_name(serialized, kwargs, metadata)
        params = self._extract_params(serialized, kwargs)
        messages = [Message(role="user", content=p) for p in prompts]

        span = Span(
            span_id=run_id_str,
            parent_span_id=parent_run_id_str,
            type=SpanType.llm_call,
            name=(serialized or {}).get("name") or "llm",
            started_at=datetime.now(tz=UTC),
            ended_at=datetime.now(tz=UTC),
            input=SpanInput(
                messages=messages,
                model=model_name,
                params=params,
            ),
        )

        with self._lock:
            self._spans[run_id_str] = span

    def on_chat_model_start(
        self,
        serialized: dict[str, Any] | None,
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        run_id_str = str(run_id)
        parent_run_id_str = str(parent_run_id) if parent_run_id else None

        with self._lock:
            if parent_run_id_str:
                self._parent_map[run_id_str] = parent_run_id_str

        model_name = self._extract_model_name(serialized, kwargs, metadata)
        params = self._extract_params(serialized, kwargs)

        flat_messages: list[Message] = []
        for msg_list in messages:
            for msg in msg_list:
                role = self._map_message_role(msg)
                content = getattr(msg, "content", "")
                if not isinstance(content, str):
                    content = str(content)
                flat_messages.append(Message(role=role, content=content))

        tools = self._extract_tools(kwargs)

        span = Span(
            span_id=run_id_str,
            parent_span_id=parent_run_id_str,
            type=SpanType.llm_call,
            name=(serialized or {}).get("name") or "chat_model",
            started_at=datetime.now(tz=UTC),
            ended_at=datetime.now(tz=UTC),
            input=SpanInput(
                messages=flat_messages,
                model=model_name,
                params=params,
                tools=tools,
            ),
        )

        with self._lock:
            self._spans[run_id_str] = span

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        run_id_str = str(run_id)
        with self._lock:
            span = self._spans.get(run_id_str)
        if not span:
            return

        span.ended_at = datetime.now(tz=UTC)
        span.status = TraceStatus.success

        content_parts = []
        tool_calls: list[ToolCall] = []

        for generations in response.generations:
            for gen in generations:
                if gen.text:
                    content_parts.append(gen.text)

                msg = getattr(gen, "message", None)
                if msg:
                    # Extract tool calls from AIMessage
                    tc = getattr(msg, "tool_calls", None)
                    if tc and isinstance(tc, list):
                        for call in tc:
                            if isinstance(call, dict):
                                name = call.get("name")
                                args = call.get("args") or call.get("arguments") or {}
                                if name:
                                    tool_calls.append(
                                        ToolCall(name=name, arguments=args)
                                    )
                    elif hasattr(msg, "additional_kwargs"):
                        raw_tc = msg.additional_kwargs.get("tool_calls")
                        if raw_tc and isinstance(raw_tc, list):
                            for call in raw_tc:
                                if isinstance(call, dict):
                                    func = call.get("function", {})
                                    name = func.get("name")
                                    args_str = func.get("arguments", "{}")
                                    try:
                                        args = (
                                            json.loads(args_str)
                                            if isinstance(args_str, str)
                                            else args_str
                                        )
                                    except Exception:
                                        args = {"raw": args_str}
                                    if name:
                                        tool_calls.append(
                                            ToolCall(name=name, arguments=args)
                                        )

        span.output = SpanOutput(
            content="\n".join(content_parts) if content_parts else None,
            tool_calls=tool_calls,
        )

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        run_id_str = str(run_id)
        with self._lock:
            span = self._spans.get(run_id_str)
        if not span:
            return

        span.ended_at = datetime.now(tz=UTC)
        span.status = TraceStatus.error
        span.error = SpanError(message=str(error), type=type(error).__name__)

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        run_id_str = str(run_id)
        parent_run_id_str = str(parent_run_id) if parent_run_id else None

        with self._lock:
            if parent_run_id_str:
                self._parent_map[run_id_str] = parent_run_id_str

        tool_name = serialized.get("name") or kwargs.get("name") or "tool"

        params = {"input": input_str}
        try:
            parsed = json.loads(input_str)
            if isinstance(parsed, dict):
                params = parsed
        except Exception:
            pass

        span = Span(
            span_id=run_id_str,
            parent_span_id=parent_run_id_str,
            type=SpanType.tool_call,
            name=tool_name,
            started_at=datetime.now(tz=UTC),
            ended_at=datetime.now(tz=UTC),
            input=SpanInput(params=params),
        )

        with self._lock:
            self._spans[run_id_str] = span

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        run_id_str = str(run_id)
        with self._lock:
            span = self._spans.get(run_id_str)
        if not span:
            return

        span.ended_at = datetime.now(tz=UTC)
        span.status = TraceStatus.success
        span.output = SpanOutput(content=str(output))

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        run_id_str = str(run_id)
        with self._lock:
            span = self._spans.get(run_id_str)
        if not span:
            return

        span.ended_at = datetime.now(tz=UTC)
        span.status = TraceStatus.error
        span.error = SpanError(message=str(error), type=type(error).__name__)

    def _check_and_send_trace(self, run_id_str: str) -> None:
        """Constructs and sends the trace if the root run has finished."""
        is_root = False
        with self._lock:
            if run_id_str in self._root_runs:
                is_root = True
                self._root_runs.remove(run_id_str)

        if not is_root:
            return

        # Gather all child spans
        spans_to_keep: list[Span] = []
        with self._lock:
            for rid, span in list(self._spans.items()):
                curr = rid
                is_descendant = False
                if curr == run_id_str:
                    is_descendant = True
                else:
                    while curr in self._parent_map:
                        parent = self._parent_map[curr]
                        if parent == run_id_str:
                            is_descendant = True
                            break
                        curr = parent

                if is_descendant:
                    spans_to_keep.append(span)
                    self._spans.pop(rid, None)
                    self._parent_map.pop(rid, None)

            source = self._run_sources.pop(run_id_str, TraceSource.langchain)

        if not spans_to_keep:
            return

        # Find the root span among these to get timing/status
        root_span = next((s for s in spans_to_keep if s.span_id == run_id_str), None)
        if not root_span:
            # Fallback if root span is somehow missing
            started_at = datetime.now(tz=UTC)
            ended_at = datetime.now(tz=UTC)
            status = TraceStatus.success
        else:
            started_at = root_span.started_at
            ended_at = root_span.ended_at
            status = root_span.status

        # Create and send the trace
        trace = Trace(
            trace_id=run_id_str,
            project_id="dummy",  # Backend overrides this anyway
            source=source,
            started_at=started_at,
            ended_at=ended_at,
            status=status,
            spans=spans_to_keep,
        )
        self.client.send(trace)

    def _map_message_role(self, msg: Any) -> str:
        msg_type = getattr(msg, "type", "")
        if msg_type == "human":
            return "user"
        elif msg_type == "system":
            return "system"
        elif msg_type == "ai":
            return "assistant"
        elif msg_type == "tool":
            return "tool"
        elif msg_type == "function":
            return "function"
        return msg_type or "user"

    def _extract_model_name(
        self,
        serialized: dict[str, Any] | None,
        kwargs: dict[str, Any],
        metadata: dict[str, Any] | None,
    ) -> str | None:
        if metadata and "ls_model_name" in metadata:
            return metadata["ls_model_name"]

        invocation_params = kwargs.get("invocation_params")
        if invocation_params and isinstance(invocation_params, dict):
            model = invocation_params.get("model_name") or invocation_params.get(
                "model"
            )
            if model:
                return model

        ser_kwargs = (serialized or {}).get("kwargs", {})
        if isinstance(ser_kwargs, dict):
            model = ser_kwargs.get("model_name") or ser_kwargs.get("model")
            if model:
                return model

        return kwargs.get("model_name") or kwargs.get("model")

    def _extract_params(
        self, serialized: dict[str, Any] | None, kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        invocation_params = kwargs.get("invocation_params")
        if invocation_params and isinstance(invocation_params, dict):
            params.update(invocation_params)

        ser_kwargs = (serialized or {}).get("kwargs", {})
        if isinstance(ser_kwargs, dict):
            for k, v in ser_kwargs.items():
                if k not in ["model", "model_name", "messages", "prompts"]:
                    params[k] = v

        for k in ["model", "model_name", "messages", "prompts"]:
            params.pop(k, None)

        return params

    def _extract_tools(self, kwargs: dict[str, Any]) -> list[ToolDefinition]:
        tools: list[ToolDefinition] = []
        raw_tools = kwargs.get("tools") or kwargs.get("invocation_params", {}).get(
            "tools"
        )
        if raw_tools and isinstance(raw_tools, list):
            for t in raw_tools:
                if isinstance(t, dict):
                    name = t.get("name") or t.get("function", {}).get("name")
                    schema = (
                        t.get("schema") or t.get("function", {}).get("parameters") or {}
                    )
                    if name:
                        tools.append(ToolDefinition(name=name, schema=schema))
        return tools
