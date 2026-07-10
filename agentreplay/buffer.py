"""
buffer.py — In-memory trace queue and background flush mechanism.

Accumulates trace payloads and flushes them periodically or when the batch size
limit is reached. Ensures non-blocking sends for the main agent thread.

Matches backlog item 3.1.2.
"""

from __future__ import annotations

import atexit
import logging
import queue
import threading
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("agentreplay")


class TraceBuffer:
    """
    Thread-safe buffer that queues trace payloads in memory and flushes them
    using a background worker thread.
    """

    def __init__(
        self,
        send_fn: Callable[[dict[str, Any]], None],
        flush_interval: float = 2.0,
        batch_size: int = 10,
    ) -> None:
        self.send_fn = send_fn
        self.flush_interval = flush_interval
        self.batch_size = batch_size

        self._queue: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()

        # Register shutdown handler to flush remaining traces on exit
        atexit.register(self.shutdown)

    def add(self, trace_payload: dict[str, Any]) -> None:
        """Add a trace payload to the queue."""
        self._queue.put(trace_payload)

    def flush(self) -> None:
        """Synchronously flush all currently queued traces."""
        batch: list[dict[str, Any]] = []
        while not self._queue.empty():
            try:
                item = self._queue.get_nowait()
                if item is None:
                    continue
                batch.append(item)
                self._queue.task_done()
            except queue.Empty:
                break

        if batch:
            self._flush_batch(batch)

    def _worker(self) -> None:
        """Background thread worker loop."""
        while not self._stop_event.is_set():
            batch: list[dict[str, Any]] = []
            start_time = time.time()
            timeout = self.flush_interval

            while len(batch) < self.batch_size:
                elapsed = time.time() - start_time
                remaining = max(0.0, timeout - elapsed)
                try:
                    item = self._queue.get(timeout=remaining if batch else timeout)
                    if item is None:
                        # Sentinel received
                        self._queue.task_done()
                        break
                    batch.append(item)
                    self._queue.task_done()
                except queue.Empty:
                    break

            if batch:
                self._flush_batch(batch)

    def _flush_batch(self, batch: list[dict[str, Any]]) -> None:
        """Sends a batch of traces one by one via the client send function."""
        for payload in batch:
            try:
                self.send_fn(payload)
            except Exception as e:
                logger.warning("Failed to send trace: %s", e)

    def shutdown(self) -> None:
        """Shutdown the worker thread and flush any remaining traces."""
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        self._queue.put(None)  # Wake up worker thread

        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)

        # Final drain of any leftovers
        remaining: list[dict[str, Any]] = []
        while not self._queue.empty():
            try:
                item = self._queue.get_nowait()
                if item is not None:
                    remaining.append(item)
                self._queue.task_done()
            except queue.Empty:
                break

        if remaining:
            self._flush_batch(remaining)

        # Unregister from atexit to avoid memory leaks/repeated calls
        try:
            atexit.unregister(self.shutdown)
        except Exception:
            pass
