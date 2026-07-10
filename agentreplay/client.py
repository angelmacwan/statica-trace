"""
client.py — Core networking client for Statica Trace.

Handles API key resolution, trace payload serialization/validation,
and asynchronous background delivery via TraceBuffer.

Matches backlog item 3.1.1.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from agentreplay.buffer import TraceBuffer
from agentreplay.schema import Trace

logger = logging.getLogger("agentreplay")


class AgentReplayClient:
    """
    Client for interacting with the Statica Trace ingestion API.
    """

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str | None = None,
        flush_interval: float = 2.0,
        batch_size: int = 10,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        self.api_key = api_key or os.environ.get("AGENTREPLAY_API_KEY")
        if not self.api_key:
            raise ValueError(
                "AGENTREPLAY_API_KEY must be provided via constructor or env variable."
            )

        self.endpoint = endpoint or os.environ.get(
            "AGENTREPLAY_ENDPOINT", "https://api.staticatrace.com/v1/ingest"
        )

        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        self._http_client = httpx.Client(timeout=10.0)

        # Initialize the buffer which runs the background worker
        self.buffer = TraceBuffer(
            send_fn=self._send_payload,
            flush_interval=flush_interval,
            batch_size=batch_size,
        )

    def send(self, trace: Trace | dict[str, Any]) -> None:
        """
        Serialize and queue a trace to be sent asynchronously.

        Accepts either a Trace Pydantic model or a dict representing a Trace.
        """
        if isinstance(trace, Trace):
            payload = trace.model_dump(mode="json")
        elif isinstance(trace, dict):
            # Validate schema early to catch issues on caller thread
            validated = Trace.model_validate(trace)
            payload = validated.model_dump(mode="json")
        else:
            raise TypeError("trace must be Trace or a dict matching Trace schema.")

        self.buffer.add(payload)

    def flush(self) -> None:
        """Synchronously flush all pending traces in the buffer."""
        self.buffer.flush()

    def close(self) -> None:
        """Shut down the client and the background buffer worker."""
        self.buffer.shutdown()
        self._http_client.close()

    def __enter__(self) -> AgentReplayClient:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def _send_payload(self, payload: dict[str, Any]) -> None:
        """
        Performs the synchronous HTTP POST to the ingest endpoint.
        Retries with exponential backoff on network failures.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(self.max_retries):
            try:
                response = self._http_client.post(
                    self.endpoint,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                # Successfully sent
                return
            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.warning(
                        "Failed to send trace to %s after %d attempts: %s",
                        self.endpoint,
                        self.max_retries,
                        e,
                    )
                    # Swallow exception, do not crash worker
                    return

                sleep_time = self.backoff_factor * (2**attempt)
                time.sleep(sleep_time)
