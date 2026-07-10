"""
tests/sdk/test_buffer.py — Unit tests for TraceBuffer.

Matches backlog item 3.4.1 (buffer.py requirements).
"""

from __future__ import annotations

import logging
import time
from unittest.mock import MagicMock

import pytest

from agentreplay.buffer import TraceBuffer


def test_buffer_enqueue_and_batch_size() -> None:
    """Buffer flushes when queue size reaches batch_size."""
    send_mock = MagicMock()
    # Set flush_interval high so it only flushes on batch size threshold
    buffer = TraceBuffer(send_fn=send_mock, flush_interval=10.0, batch_size=3)
    try:
        buffer.add({"id": "1"})
        buffer.add({"id": "2"})
        # Should not have flushed yet
        time.sleep(0.05)
        assert send_mock.call_count == 0

        buffer.add({"id": "3"})
        # Wait a brief moment for the worker thread to process
        time.sleep(0.1)
        # Should have flushed the batch of 3
        assert send_mock.call_count == 3
        send_mock.assert_any_call({"id": "1"})
        send_mock.assert_any_call({"id": "2"})
        send_mock.assert_any_call({"id": "3"})
    finally:
        buffer.shutdown()


def test_buffer_flush_interval() -> None:
    """Buffer flushes when timer expires even if batch_size is not reached."""
    send_mock = MagicMock()
    # Set batch size high, but flush interval low
    buffer = TraceBuffer(send_fn=send_mock, flush_interval=0.1, batch_size=10)
    try:
        buffer.add({"id": "1"})
        assert send_mock.call_count == 0
        # Wait for the interval to elapse plus worker thread processing time
        time.sleep(0.2)
        assert send_mock.call_count == 1
        send_mock.assert_called_with({"id": "1"})
    finally:
        buffer.shutdown()


def test_buffer_manual_flush() -> None:
    """Manually calling flush() drains the queue and sends immediately."""
    send_mock = MagicMock()
    buffer = TraceBuffer(send_fn=send_mock, flush_interval=10.0, batch_size=10)
    try:
        buffer.add({"id": "1"})
        buffer.add({"id": "2"})
        assert send_mock.call_count == 0
        buffer.flush()
        assert send_mock.call_count == 2
        send_mock.assert_any_call({"id": "1"})
        send_mock.assert_any_call({"id": "2"})
    finally:
        buffer.shutdown()


def test_buffer_flush_failure_logged(caplog: pytest.LogCaptureFixture) -> None:
    """Flush failure logs a warning and does not raise."""
    send_mock = MagicMock(side_effect=Exception("Network error"))
    buffer = TraceBuffer(send_fn=send_mock, flush_interval=10.0, batch_size=10)
    try:
        buffer.add({"id": "1"})
        with caplog.at_level(logging.WARNING):
            buffer.flush()
        assert any(
            "Failed to send trace" in record.message for record in caplog.records
        )
    finally:
        buffer.shutdown()


def test_buffer_shutdown_flushes_remaining() -> None:
    """Calling shutdown() flushes any remaining traces in the queue."""
    send_mock = MagicMock()
    buffer = TraceBuffer(send_fn=send_mock, flush_interval=10.0, batch_size=10)
    buffer.add({"id": "1"})
    buffer.add({"id": "2"})
    assert send_mock.call_count == 0
    buffer.shutdown()
    assert send_mock.call_count == 2
    send_mock.assert_any_call({"id": "1"})
    send_mock.assert_any_call({"id": "2"})
