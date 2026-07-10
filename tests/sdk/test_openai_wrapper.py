"""
tests/sdk/test_openai_wrapper.py — Unit tests for the OpenAI SDK client wrapper.

Matches backlog item 3.4.3.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import openai
import pytest
from pytest_httpx import HTTPXMock

from agentreplay.client import AgentReplayClient
from agentreplay.openai_wrapper import wrap
from agentreplay.schema import SpanType, Trace, TraceStatus


def test_openai_wrap_success(httpx_mock: HTTPXMock) -> None:
    """Wrapped client behaves identically and sends Trace on success."""
    # Mock the outbound call to OpenAI API
    openai_response_data = {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello from mock OpenAI!",
                },
                "finish_reason": "stop",
            }
        ],
    }
    httpx_mock.add_response(
        method="POST",
        url="https://api.openai.com/v1/chat/completions",
        status_code=200,
        json=openai_response_data,
    )

    mock_replay_client = MagicMock(spec=AgentReplayClient)
    openai_client = openai.OpenAI(api_key="mock-key")
    wrapped_client = wrap(openai_client, mock_replay_client)

    # Call the wrapped completions endpoint
    response = wrapped_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hi!"},
        ],
        temperature=0.7,
    )

    # 1. Assert return value is identical in structure/content
    assert response.choices[0].message.content == "Hello from mock OpenAI!"

    # 2. Assert trace is captured and sent
    assert mock_replay_client.send.call_count == 1
    trace = mock_replay_client.send.call_args[0][0]
    assert isinstance(trace, Trace)
    assert trace.status == TraceStatus.success

    # 3. Verify span details
    assert len(trace.spans) == 1
    span = trace.spans[0]
    assert span.type == SpanType.llm_call
    assert span.name == "chat_completion"
    assert span.input.model == "gpt-4o-mini"
    assert span.input.params["temperature"] == 0.7
    assert len(span.input.messages) == 2
    assert span.input.messages[0].role == "system"
    assert span.input.messages[0].content == "You are a helpful assistant."
    assert span.input.messages[1].role == "user"
    assert span.input.messages[1].content == "Hi!"
    assert span.output.content == "Hello from mock OpenAI!"


def test_openai_wrap_tool_call(httpx_mock: HTTPXMock) -> None:
    """Wrapped client captures tool definitions and generated tool calls."""
    openai_response_data = {
        "id": "chatcmpl-tool",
        "object": "chat.completion",
        "created": 1677652289,
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_abc",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": '{"location": "San Francisco"}',
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
    }
    httpx_mock.add_response(
        method="POST",
        url="https://api.openai.com/v1/chat/completions",
        status_code=200,
        json=openai_response_data,
    )

    mock_replay_client = MagicMock(spec=AgentReplayClient)
    openai_client = openai.OpenAI(api_key="mock-key")
    wrapped_client = wrap(openai_client, mock_replay_client)

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                },
            },
        }
    ]

    wrapped_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Weather in SF?"}],
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
    assert span.output.tool_calls[0].arguments == {"location": "San Francisco"}


def test_openai_wrap_error(httpx_mock: HTTPXMock) -> None:
    """API errors are re-raised to caller and captured as error traces."""
    # Mock a 401 Unauthorized response
    httpx_mock.add_response(
        method="POST",
        url="https://api.openai.com/v1/chat/completions",
        status_code=401,
        json={"error": {"message": "Invalid API key", "type": "invalid_request_error"}},
    )

    mock_replay_client = MagicMock(spec=AgentReplayClient)
    openai_client = openai.OpenAI(api_key="mock-key")
    wrapped_client = wrap(openai_client, mock_replay_client)

    # Call should raise AuthenticationError
    with pytest.raises(openai.AuthenticationError):
        wrapped_client.chat.completions.create(
            model="gpt-4o-mini",
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
