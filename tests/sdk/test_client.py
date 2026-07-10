"""
tests/sdk/test_client.py — Unit tests for AgentReplayClient.

Matches backlog item 3.4.1 (client.py requirements).
"""

from __future__ import annotations

import json
import logging
import os
import time
from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock

from agentreplay.client import AgentReplayClient
from agentreplay.schema import Trace


def test_client_init_api_key_resolution() -> None:
    """AgentReplayClient resolves API key from constructor or env var."""
    # 1. From constructor
    client = AgentReplayClient(api_key="const-key")
    assert client.api_key == "const-key"
    client.close()

    # 2. From environment
    with patch.dict(os.environ, {"AGENTREPLAY_API_KEY": "env-key"}):
        client2 = AgentReplayClient()
        assert client2.api_key == "env-key"
        client2.close()

    # 3. Missing API key raises ValueError
    with patch.dict(os.environ, {}):
        if "AGENTREPLAY_API_KEY" in os.environ:
            del os.environ["AGENTREPLAY_API_KEY"]
        with pytest.raises(ValueError):
            AgentReplayClient()


def test_client_send_success(httpx_mock: HTTPXMock, sample_trace: Trace) -> None:
    """Successfully sending a trace sends POST request with correct headers."""
    httpx_mock.add_response(
        method="POST",
        url="https://api.staticatrace.com/v1/ingest",
        status_code=202,
        json={"trace_id": sample_trace.trace_id, "status": "accepted"},
    )

    client = AgentReplayClient(api_key="test-key", flush_interval=10.0, batch_size=10)
    try:
        client.send(sample_trace)
        client.flush()

        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.headers["Content-Type"] == "application/json"

        payload = json.loads(request.read())
        assert payload["trace_id"] == sample_trace.trace_id
        assert payload["project_id"] == sample_trace.project_id
    finally:
        client.close()


def test_client_send_dict_success(httpx_mock: HTTPXMock, sample_trace: Trace) -> None:
    """Successfully sending a dict representation of a Trace."""
    httpx_mock.add_response(
        method="POST",
        url="https://api.staticatrace.com/v1/ingest",
        status_code=202,
    )

    client = AgentReplayClient(api_key="test-key", flush_interval=10.0, batch_size=10)
    try:
        client.send(sample_trace.model_dump(mode="json"))
        client.flush()

        request = httpx_mock.get_request()
        assert request is not None
        payload = json.loads(request.read())
        assert payload["trace_id"] == sample_trace.trace_id
    finally:
        client.close()


def test_client_send_invalid_type() -> None:
    """Sending an invalid type raises a TypeError."""
    client = AgentReplayClient(api_key="test-key")
    try:
        with pytest.raises(TypeError):
            client.send("not-a-trace-or-dict")  # type: ignore
    finally:
        client.close()


def test_client_send_non_blocking(sample_trace: Trace) -> None:
    """Calling send() returns immediately and does not block the caller thread."""
    client = AgentReplayClient(api_key="test-key", flush_interval=10.0, batch_size=10)
    try:
        start_time = time.time()
        client.send(sample_trace)
        duration = time.time() - start_time
        # Thread queue insert should be virtually instantaneous
        assert duration < 0.05
    finally:
        client.close()


def test_client_retry_and_swallow_warning(
    httpx_mock: HTTPXMock, sample_trace: Trace, caplog: pytest.LogCaptureFixture
) -> None:
    """On network failure, client retries, then logs a warning and does not raise."""
    # Register 3 consecutive failure responses
    for _ in range(3):
        httpx_mock.add_response(
            method="POST",
            url="https://api.staticatrace.com/v1/ingest",
            status_code=500,
        )

    client = AgentReplayClient(
        api_key="test-key",
        flush_interval=10.0,
        batch_size=10,
        max_retries=3,
        backoff_factor=0.01,  # Short backoff for tests
    )
    try:
        client.send(sample_trace)
        with caplog.at_level(logging.WARNING):
            client.flush()

        # Verify exactly 3 attempts were made
        requests = httpx_mock.get_requests()
        assert len(requests) == 3

        # Verify a warning was logged and no exception was raised to the caller
        assert any(
            "Failed to send trace" in record.message for record in caplog.records
        )
    finally:
        client.close()
