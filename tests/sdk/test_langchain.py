"""
tests/sdk/test_langchain.py — Unit tests for AgentReplayCallbackHandler.

Matches backlog item 3.4.2.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
from langchain_core.language_models import LLM
from langchain_core.language_models.fake import FakeListLLM
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from langchain_core.prompts import PromptTemplate

from agentreplay.client import AgentReplayClient
from agentreplay.langchain import AgentReplayCallbackHandler
from agentreplay.schema import SpanType, Trace, TraceStatus


# ---------------------------------------------------------------------------
# Helpers & Custom Classes
# ---------------------------------------------------------------------------
class ExceptionThrowingLLM(LLM):
    """A custom LLM that always throws an error for testing error callbacks."""

    def _call(
        self,
        prompt: str,
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> str:
        raise ValueError("Simulated LLM API failure")

    @property
    def _llm_type(self) -> str:
        return "exception_throwing_llm"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_langchain_callback_success() -> None:
    """Running a chain with the handler captures a complete Trace with LLM spans."""
    mock_client = MagicMock(spec=AgentReplayClient)
    handler = AgentReplayCallbackHandler(client=mock_client)

    prompt = PromptTemplate.from_template("Summarize: {input_text}")
    llm = FakeListLLM(responses=["This is a mock summary."])
    chain = prompt | llm

    # Run the chain with the handler attached
    result = chain.invoke(
        {"input_text": "LangChain callbacks are nice."},
        config={"callbacks": [handler]},
    )

    # 1. Assert return value is unaltered
    assert result == "This is a mock summary."

    # 2. Assert client.send was called with the assembled Trace
    assert mock_client.send.call_count == 1
    trace = mock_client.send.call_args[0][0]
    assert isinstance(trace, Trace)
    assert trace.status == TraceStatus.success

    # 3. Assert correct spans are present
    assert len(trace.spans) >= 2
    llm_spans = [s for s in trace.spans if s.type == SpanType.llm_call]
    assert len(llm_spans) == 1
    llm_span = llm_spans[0]

    # Verify input / output mappings
    assert len(llm_span.input.messages) == 1
    assert llm_span.input.messages[0].role == "user"
    assert (
        llm_span.input.messages[0].content == "Summarize: LangChain callbacks are nice."
    )
    assert llm_span.output.content == "This is a mock summary."


def test_langchain_callback_llm_error() -> None:
    """An LLM exception sets error status and records error details on the span."""
    mock_client = MagicMock(spec=AgentReplayClient)
    handler = AgentReplayCallbackHandler(client=mock_client)

    prompt = PromptTemplate.from_template("Say hello to {name}")
    llm = ExceptionThrowingLLM()
    chain = prompt | llm

    # Run the chain and expect the exception to bubble up
    with pytest.raises(ValueError, match="Simulated LLM API failure"):
        chain.invoke({"name": "World"}, config={"callbacks": [handler]})

    # Assert trace was sent even on error
    assert mock_client.send.call_count == 1
    trace = mock_client.send.call_args[0][0]
    assert isinstance(trace, Trace)
    assert trace.status == TraceStatus.error

    # Assert error spans are formatted correctly
    llm_spans = [s for s in trace.spans if s.type == SpanType.llm_call]
    assert len(llm_spans) == 1
    llm_span = llm_spans[0]
    assert llm_span.status == TraceStatus.error
    assert llm_span.error is not None
    assert "Simulated LLM API failure" in llm_span.error.message
    assert llm_span.error.type == "ValueError"


def test_langchain_callback_nested_with_tool_manual() -> None:
    """Calling handler hooks manually with nested tool creates a Trace."""
    mock_client = MagicMock(spec=AgentReplayClient)
    handler = AgentReplayCallbackHandler(client=mock_client)

    root_run_id = uuid.uuid4()
    llm_run_id = uuid.uuid4()
    tool_run_id = uuid.uuid4()

    # 1. Start root chain
    handler.on_chain_start(
        {"name": "root_chain"}, {"input": "test"}, run_id=root_run_id
    )

    # 2. Start LLM call under root
    handler.on_chat_model_start(
        {"name": "gpt-4o"},
        [[BaseMessage(content="hello", type="human")]],
        run_id=llm_run_id,
        parent_run_id=root_run_id,
    )

    # 3. End LLM call with a tool call output
    ai_msg = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "mock_search_tool",
                "args": {"query": "Paris"},
                "id": "call_1",
            }
        ],
    )
    gen = ChatGeneration(message=ai_msg, text="")
    llm_result = LLMResult(generations=[[gen]])
    handler.on_llm_end(llm_result, run_id=llm_run_id)

    # 4. Start tool call under root
    handler.on_tool_start(
        {"name": "mock_search_tool"},
        '{"query": "Paris"}',
        run_id=tool_run_id,
        parent_run_id=root_run_id,
    )
    handler.on_tool_end("Results for Paris", run_id=tool_run_id)

    # 5. End root chain
    handler.on_chain_end({"output": "done"}, run_id=root_run_id)

    # Assert trace is constructed and sent
    assert mock_client.send.call_count == 1
    trace = mock_client.send.call_args[0][0]
    assert isinstance(trace, Trace)
    assert len(trace.spans) == 3

    # Check span relations
    spans_by_type = {s.type: s for s in trace.spans}
    assert SpanType.agent_step in spans_by_type
    assert SpanType.llm_call in spans_by_type
    assert SpanType.tool_call in spans_by_type

    llm_span = spans_by_type[SpanType.llm_call]
    assert llm_span.parent_span_id == str(root_run_id)
    assert len(llm_span.output.tool_calls) == 1
    assert llm_span.output.tool_calls[0].name == "mock_search_tool"

    tool_span = spans_by_type[SpanType.tool_call]
    assert tool_span.parent_span_id == str(root_run_id)
    assert tool_span.output.content == "Results for Paris"
