"""
tests/sdk/test_anthropic_wrapper.py — Unit tests for the Anthropic SDK client wrapper.

Matches backlog item 3.4.4.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import anthropic
import pytest
from pytest_httpx import HTTPXMock

from agentreplay.anthropic_wrapper import wrap
from agentreplay.client import AgentReplayClient
from agentreplay.schema import SpanType, Trace, TraceStatus


def test_anthropic_wrap_success(httpx_mock: HTTPXMock) -> None:
    """Wrapped client behaves identically and sends Trace on success."""
    # Mock the outbound call to Anthropic API
    anthropic_response_data = {
        "id": "msg_123",
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "text",
                "text": "Hello from mock Anthropic!",
            }
        ],
        "model": "claude-3-5-sonnet",
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 12},
    }
    httpx_mock.add_response(
        method="POST",
        url="https://api.anthropic.com/v1/messages",
        status_code=200,
        json=anthropic_response_data,
    )

    mock_replay_client = MagicMock(spec=AgentReplayClient)
    anthropic_client = anthropic.Anthropic(api_key="mock-key")
    wrapped_client = wrap(anthropic_client, mock_replay_client)

    # Call the wrapped messages endpoint
    response = wrapped_client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=1024,
        system="You are Claude.",
        messages=[
            {"role": "user", "content": "Hi!"},
        ],
        temperature=0.5,
    )

    # 1. Assert return value is identical in structure/content
    assert response.content[0].text == "Hello from mock Anthropic!"

    # 2. Assert trace is captured and sent
    assert mock_replay_client.send.call_count == 1
    trace = mock_replay_client.send.call_args[0][0]
    assert isinstance(trace, Trace)
    assert trace.status == TraceStatus.success

    # 3. Verify span details
    assert len(trace.spans) == 1
    span = trace.spans[0]
    assert span.type == SpanType.llm_call
    assert span.name == "messages_create"
    assert span.input.model == "claude-3-5-sonnet"
    assert span.input.params["temperature"] == 0.5
    assert span.input.params["max_tokens"] == 1024
    assert len(span.input.messages) == 2
    assert span.input.messages[0].role == "system"
    assert span.input.messages[0].content == "You are Claude."
    assert span.input.messages[1].role == "user"
    assert span.input.messages[1].content == "Hi!"
    assert span.output.content == "Hello from mock Anthropic!"


def test_anthropic_wrap_tool_call(httpx_mock: HTTPXMock) -> None:
    """Wrapped client captures tool definitions and tool calls."""
    anthropic_response_data = {
        "id": "msg_tool",
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_abc",
                "name": "get_weather",
                "input": {"location": "Seattle"},
            }
        ],
        "model": "claude-3-5-sonnet",
        "stop_reason": "tool_use",
        "stop_sequence": None,
        "usage": {"input_tokens": 40, "output_tokens": 20},
    }
    httpx_mock.add_response(
        method="POST",
        url="https://api.anthropic.com/v1/messages",
        status_code=200,
        json=anthropic_response_data,
    )

    mock_replay_client = MagicMock(spec=AgentReplayClient)
    anthropic_client = anthropic.Anthropic(api_key="mock-key")
    wrapped_client = wrap(anthropic_client, mock_replay_client)

    tools = [
        {
            "name": "get_weather",
            "description": "Get weather",
            "input_schema": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
            },
        }
    ]

    wrapped_client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=100,
        messages=[{"role": "user", "content": "Weather in Seattle?"}],
        tools=tools,
    )

    assert mock_replay_client.send.call_count == 1
    trace = mock_replay_client.send.call_args[0][0]
    span = trace.spans[0]

    # Verify tool definition was captured
    assert len(span.input.tools) == 1
    assert span.input.tools[0].name == "get_weather"

    # Verify tool call was captured
    assert len(span.output.tool_calls) == 1
    assert span.output.tool_calls[0].name == "get_weather"
    assert span.output.tool_calls[0].arguments == {"location": "Seattle"}


def test_anthropic_wrap_error(httpx_mock: HTTPXMock) -> None:
    """API errors are re-raised to caller and captured as error traces."""
    httpx_mock.add_response(
        method="POST",
        url="https://api.anthropic.com/v1/messages",
        status_code=401,
        json={
            "type": "error",
            "error": {
                "type": "authentication_error",
                "message": "Invalid API key",
            },
        },
    )

    mock_replay_client = MagicMock(spec=AgentReplayClient)
    anthropic_client = anthropic.Anthropic(api_key="mock-key")
    wrapped_client = wrap(anthropic_client, mock_replay_client)

    # Call should raise AuthenticationError
    with pytest.raises(anthropic.AuthenticationError):
        wrapped_client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=100,
            messages=[{"role": "user", "content": "Hello"}],
        )

    # Trace must still be captured and sent with status error
    assert mock_replay_client.send.call_count == 1
    trace = mock_replay_client.send.call_args[0][0]
    assert trace.status == TraceStatus.error

    span = trace.spans[0]
    assert span.status == TraceStatus.error
    assert span.error is not None
    assert "Invalid API key" in span.error.message
    assert span.error.type == "AuthenticationError"
