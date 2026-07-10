#!/usr/bin/env python3
"""
send_test_trace.py — Test script to ingest a mock multi-span trace into Statica Trace.

Usage:
  python scripts/send_test_trace.py <api_key> [endpoint_url]
Or set environment variables:
  export AGENTREPLAY_API_KEY="your_api_key"
  python scripts/send_test_trace.py
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import UTC, datetime, timedelta

from agentreplay.client import AgentReplayClient
from agentreplay.schema import (
    Message,
    RetrievedContext,
    Span,
    SpanInput,
    SpanOutput,
    SpanType,
    ToolCall,
    ToolDefinition,
    Trace,
    TraceSource,
    TraceStatus,
)


def main() -> None:
    # Resolve API Key
    api_key = os.environ.get("AGENTREPLAY_API_KEY")
    if len(sys.argv) > 1:
        api_key = sys.argv[1]

    if not api_key:
        print("[-] Error: API key is required.", file=sys.stderr)
        print("Usage: python scripts/send_test_trace.py <api_key> [endpoint_url]", file=sys.stderr)
        print("Or set AGENTREPLAY_API_KEY environment variable.", file=sys.stderr)
        sys.exit(1)

    # Resolve Ingest Endpoint
    endpoint = os.environ.get("AGENTREPLAY_ENDPOINT")
    if len(sys.argv) > 2:
        endpoint = sys.argv[2]
    if not endpoint:
        endpoint = "http://localhost:8000/v1/ingest"

    print(f"[*] Initializing AgentReplayClient...")
    print(f"    Endpoint: {endpoint}")
    print(f"    API Key:  {api_key[:8]}...{api_key[-4:] if len(api_key) > 12 else ''}")

    try:
        client = AgentReplayClient(
            api_key=api_key,
            endpoint=endpoint,
        )
    except Exception as e:
        print(f"[-] Client initialization failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Timestamps
    t0 = datetime.now(tz=UTC) - timedelta(seconds=12)
    t1 = t0 + timedelta(seconds=2)
    t2 = t1 + timedelta(seconds=4)
    t3 = t2 + timedelta(seconds=2)
    t4 = t3 + timedelta(seconds=3)
    t5 = t4 + timedelta(seconds=1)

    # Generate IDs
    trace_id = str(uuid.uuid4())
    root_span_id = str(uuid.uuid4())
    retrieval_span_id = str(uuid.uuid4())
    llm_span_id = str(uuid.uuid4())
    tool_span_id = str(uuid.uuid4())

    print(f"[*] Constructing test trace ID: {trace_id}")

    # Build spans representing a typical RAG Agent flow
    spans = [
        # 1. Root Agent Step
        Span(
            span_id=root_span_id,
            parent_span_id=None,
            type=SpanType.agent_step,
            name="RAG QA Assistant",
            started_at=t0,
            ended_at=t5,
            status=TraceStatus.success,
            input=SpanInput(
                messages=[
                    Message(role="user", content="Where was Albert Einstein born and what was his Nobel Prize for?")
                ]
            ),
            output=SpanOutput(
                content="Albert Einstein was born in Ulm, Germany. He won the Nobel Prize in Physics in 1921 for his explanation of the photoelectric effect."
            ),
        ),
        # 2. Vector DB Retrieval
        Span(
            span_id=retrieval_span_id,
            parent_span_id=root_span_id,
            type=SpanType.retrieval,
            name="Knowledge base lookup",
            started_at=t0 + timedelta(milliseconds=100),
            ended_at=t1,
            status=TraceStatus.success,
            input=SpanInput(
                messages=[
                    Message(role="user", content="Albert Einstein birth Ulm Nobel Prize photoelectric")
                ]
            ),
            output=SpanOutput(
                content="Retrieved 2 context chunks from DB.",
            ),
        ),
        # 3. LLM Call (incorporating retrieved context)
        Span(
            span_id=llm_span_id,
            parent_span_id=root_span_id,
            type=SpanType.llm_call,
            name="Generate Response",
            started_at=t1 + timedelta(milliseconds=200),
            ended_at=t2,
            status=TraceStatus.success,
            input=SpanInput(
                model="gpt-4o",
                messages=[
                    Message(role="system", content="You are a precise facts-only assistant. Answer the user prompt using the provided retrieved context."),
                    Message(role="user", content="Where was Albert Einstein born and what was his Nobel Prize for?")
                ],
                params={
                    "temperature": 0.2,
                    "max_tokens": 256,
                },
                tools=[
                    ToolDefinition(
                        name="log_event",
                        schema={
                            "type": "object",
                            "properties": {
                                "status": {"type": "string"},
                                "category": {"type": "string"}
                            },
                            "required": ["status"]
                        }
                    )
                ],
                retrieved_context=[
                    RetrievedContext(
                        source="einstein_bio.txt",
                        content="Albert Einstein (14 March 1879 - 18 April 1955) was born in Ulm, in the Kingdom of Württemberg in the German Empire. He later moved to Switzerland and then the United States.",
                        score=0.92,
                    ),
                    RetrievedContext(
                        source="nobel_database.json",
                        content="The Nobel Prize in Physics 1921 was awarded to Albert Einstein for his services to Theoretical Physics, and especially for his discovery of the law of the photoelectric effect.",
                        score=0.89,
                    ),
                ]
            ),
            output=SpanOutput(
                content="Albert Einstein was born in Ulm, Germany. He won the Nobel Prize in Physics in 1921 for his explanation of the photoelectric effect.",
                tool_calls=[
                    ToolCall(
                        name="log_event",
                        arguments={"status": "answer_generated", "category": "nobel_physics"}
                    )
                ]
            ),
        ),
        # 4. Tool Execution (logging event)
        Span(
            span_id=tool_span_id,
            parent_span_id=root_span_id,
            type=SpanType.tool_call,
            name="log_event",
            started_at=t2 + timedelta(milliseconds=100),
            ended_at=t3,
            status=TraceStatus.success,
            input=SpanInput(
                params={"status": "answer_generated", "category": "nobel_physics"}
            ),
            output=SpanOutput(
                content="Event logged successfully (id: log-99812)."
            ),
        ),
    ]

    trace = Trace(
        trace_id=trace_id,
        project_id="dummy",  # Replaced by backend auth project
        source=TraceSource.openai,
        started_at=t0,
        ended_at=t5,
        status=TraceStatus.success,
        spans=spans,
    )

    print("[*] Queueing trace payload to AgentReplayClient...")
    try:
        client.send(trace)
        print("[*] Flushing buffer to upload traces...")
        client.flush()
        print("[+] Success! Trace sent successfully.")
        print(f"    View your trace on the dashboard at: http://localhost:5173/ (Trace ID: {trace_id})")
    except Exception as e:
        print(f"[-] Failed to send trace: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
