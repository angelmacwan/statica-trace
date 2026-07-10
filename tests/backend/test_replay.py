"""
tests/backend/test_replay.py — Integration tests for POST /v1/replay.

Outbound calls to the OpenAI and Anthropic APIs are mocked using
pytest-httpx so no real network traffic occurs.

Backlog: 2.5.4
"""

from __future__ import annotations

import json
import uuid

import pytest
from pytest_httpx import HTTPXMock

from tests.backend.conftest import make_project, make_trace

# ---------------------------------------------------------------------------
# Helpers: canned provider payloads
# ---------------------------------------------------------------------------


def _openai_chat_response(content: str = "Replayed answer") -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": None,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _anthropic_messages_response(content: str = "Replayed Anthropic answer") -> dict:
    return {
        "id": "msg-test",
        "type": "message",
        "role": "assistant",
        "model": "claude-3-5-haiku-20241022",
        "content": [{"type": "text", "text": content}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 10, "output_tokens": 8},
    }


def _openai_trace_raw(project_id: str, span_id: str) -> dict:
    return {
        "trace_id": str(uuid.uuid4()),
        "project_id": project_id,
        "source": "openai",
        "status": "success",
        "started_at": "2024-01-01T00:00:00Z",
        "ended_at": "2024-01-01T00:00:05Z",
        "spans": [
            {
                "span_id": span_id,
                "parent_span_id": None,
                "type": "llm_call",
                "name": "chat",
                "started_at": "2024-01-01T00:00:00Z",
                "ended_at": "2024-01-01T00:00:05Z",
                "status": "success",
                "input": {
                    "messages": [{"role": "user", "content": "What is 2+2?"}],
                    "model": "gpt-4o-mini",
                    "params": {"temperature": 0.0},
                    "tools": [],
                    "retrieved_context": [],
                },
                "output": {"content": "4", "tool_calls": []},
                "error": None,
            }
        ],
    }


def _anthropic_trace_raw(project_id: str, span_id: str) -> dict:
    return {
        "trace_id": str(uuid.uuid4()),
        "project_id": project_id,
        "source": "anthropic",
        "status": "success",
        "started_at": "2024-01-01T00:00:00Z",
        "ended_at": "2024-01-01T00:00:05Z",
        "spans": [
            {
                "span_id": span_id,
                "parent_span_id": None,
                "type": "llm_call",
                "name": "messages",
                "started_at": "2024-01-01T00:00:00Z",
                "ended_at": "2024-01-01T00:00:05Z",
                "status": "success",
                "input": {
                    "messages": [
                        {"role": "system", "content": "You are helpful."},
                        {"role": "user", "content": "Hello"},
                    ],
                    "model": "claude-3-5-haiku-20241022",
                    "params": {"temperature": 0.5, "max_tokens": 512},
                    "tools": [],
                    "retrieved_context": [],
                },
                "output": {"content": "Hi!", "tool_calls": []},
                "error": None,
            }
        ],
    }


def _tool_call_trace_raw(project_id: str, span_id: str) -> dict:
    return {
        "trace_id": str(uuid.uuid4()),
        "project_id": project_id,
        "source": "openai",
        "status": "success",
        "started_at": "2024-01-01T00:00:00Z",
        "ended_at": "2024-01-01T00:00:05Z",
        "spans": [
            {
                "span_id": span_id,
                "parent_span_id": None,
                "type": "tool_call",  # NOT llm_call
                "name": "search",
                "started_at": "2024-01-01T00:00:00Z",
                "ended_at": "2024-01-01T00:00:05Z",
                "status": "success",
                "input": {
                    "messages": [],
                    "model": None,
                    "params": {},
                    "tools": [],
                    "retrieved_context": [],
                },
                "output": {"content": None, "tool_calls": []},
                "error": None,
            }
        ],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestReplayEndpoint:

    async def test_replay_openai_span_returns_diff(
        self, client, db_session, httpx_mock: HTTPXMock
    ):
        """Valid replay for an OpenAI span: mocked response.

        Returns original vs replayed output.
        """
        httpx_mock.add_response(
            method="POST",
            url="https://api.openai.com/v1/chat/completions",
            json=_openai_chat_response("Replayed answer"),
            status_code=200,
        )

        proj = await make_project(db_session, api_key="replay-oai-key-001")
        span_id = str(uuid.uuid4())
        trace = await make_trace(
            db_session,
            proj.id,
            raw=_openai_trace_raw(proj.id, span_id),
        )

        resp = await client.post(
            "/v1/replay",
            json={
                "trace_id": trace.id,
                "span_id": span_id,
                "edited_input": {
                    "messages": [{"role": "user", "content": "What is 3+3?"}]
                },
            },
            headers={
                "Authorization": "Bearer replay-oai-key-001",
                "X-Provider-Api-Key": "sk-fake-openai-key",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "original_output" in data
        assert "replayed_output" in data
        assert data["replayed_output"]["content"] == "Replayed answer"

    async def test_replay_anthropic_span_returns_diff(
        self, client, db_session, httpx_mock: HTTPXMock
    ):
        """Valid replay for an Anthropic span: mocked response."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.anthropic.com/v1/messages",
            json=_anthropic_messages_response("Replayed Anthropic answer"),
            status_code=200,
        )

        proj = await make_project(db_session, api_key="replay-ant-key-001")
        span_id = str(uuid.uuid4())
        trace = await make_trace(
            db_session,
            proj.id,
            raw=_anthropic_trace_raw(proj.id, span_id),
        )

        resp = await client.post(
            "/v1/replay",
            json={
                "trace_id": trace.id,
                "span_id": span_id,
                "edited_input": {},
            },
            headers={
                "Authorization": "Bearer replay-ant-key-001",
                "X-Provider-Api-Key": "sk-ant-fake-key",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["replayed_output"]["content"] == "Replayed Anthropic answer"

    async def test_edited_input_overrides_applied(
        self, client, db_session, httpx_mock: HTTPXMock
    ):
        """The edited system prompt appears in the mocked outbound request."""
        captured_requests = []

        def capture(request, *args, **kwargs):
            captured_requests.append(json.loads(request.content))

        httpx_mock.add_response(
            method="POST",
            url="https://api.openai.com/v1/chat/completions",
            json=_openai_chat_response("ok"),
            status_code=200,
        )

        proj = await make_project(db_session, api_key="replay-edit-key-001")
        span_id = str(uuid.uuid4())
        trace = await make_trace(
            db_session,
            proj.id,
            raw=_openai_trace_raw(proj.id, span_id),
        )

        edited_messages = [
            {"role": "system", "content": "You are a pirate."},
            {"role": "user", "content": "Hello"},
        ]
        resp = await client.post(
            "/v1/replay",
            json={
                "trace_id": trace.id,
                "span_id": span_id,
                "edited_input": {"messages": edited_messages},
            },
            headers={
                "Authorization": "Bearer replay-edit-key-001",
                "X-Provider-Api-Key": "sk-fake-edit-key",
            },
        )
        assert resp.status_code == 200
        # The outbound request to OpenAI should contain the edited messages.
        outbound = httpx_mock.get_requests()
        assert len(outbound) == 1
        outbound_body = json.loads(outbound[0].content)
        assert outbound_body["messages"] == edited_messages

    async def test_missing_provider_api_key_returns_400(self, client, db_session):
        """Missing X-Provider-Api-Key header returns 400."""
        proj = await make_project(db_session, api_key="replay-nokey-001")
        span_id = str(uuid.uuid4())
        trace = await make_trace(
            db_session,
            proj.id,
            raw=_openai_trace_raw(proj.id, span_id),
        )

        resp = await client.post(
            "/v1/replay",
            json={"trace_id": trace.id, "span_id": span_id, "edited_input": {}},
            headers={"Authorization": "Bearer replay-nokey-001"},
        )
        assert resp.status_code == 400
        assert "X-Provider-Api-Key" in resp.json()["detail"]

    async def test_provider_401_surfaces_clear_error(
        self, client, db_session, httpx_mock: HTTPXMock
    ):
        """Provider returning 401 → backend returns 400 with clear message (not 500)."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.openai.com/v1/chat/completions",
            json={"error": {"message": "Incorrect API key provided"}},
            status_code=401,
        )

        proj = await make_project(db_session, api_key="replay-prov-401-key")
        span_id = str(uuid.uuid4())
        trace = await make_trace(
            db_session,
            proj.id,
            raw=_openai_trace_raw(proj.id, span_id),
        )

        resp = await client.post(
            "/v1/replay",
            json={"trace_id": trace.id, "span_id": span_id, "edited_input": {}},
            headers={
                "Authorization": "Bearer replay-prov-401-key",
                "X-Provider-Api-Key": "sk-bad-key",
            },
        )
        assert resp.status_code == 400
        assert "rejected" in resp.json()["detail"].lower()

    async def test_tool_call_span_returns_400(self, client, db_session):
        """Attempting to replay a tool_call span returns HTTP 400."""
        proj = await make_project(db_session, api_key="replay-toolcall-key")
        span_id = str(uuid.uuid4())
        trace = await make_trace(
            db_session,
            proj.id,
            raw=_tool_call_trace_raw(proj.id, span_id),
        )

        resp = await client.post(
            "/v1/replay",
            json={"trace_id": trace.id, "span_id": span_id, "edited_input": {}},
            headers={
                "Authorization": "Bearer replay-toolcall-key",
                "X-Provider-Api-Key": "sk-fake-key",
            },
        )
        assert resp.status_code == 400
        assert "llm_call" in resp.json()["detail"]

    async def test_nonexistent_trace_returns_404(self, client, db_session):
        """Unknown trace_id returns 404."""
        await make_project(db_session, api_key="replay-404-trace-key")

        resp = await client.post(
            "/v1/replay",
            json={
                "trace_id": str(uuid.uuid4()),
                "span_id": str(uuid.uuid4()),
                "edited_input": {},
            },
            headers={
                "Authorization": "Bearer replay-404-trace-key",
                "X-Provider-Api-Key": "sk-fake-key",
            },
        )
        assert resp.status_code == 404

    async def test_nonexistent_span_returns_404(self, client, db_session):
        """Unknown span_id within a real trace returns 404."""
        proj = await make_project(db_session, api_key="replay-404-span-key")
        trace = await make_trace(db_session, proj.id)

        resp = await client.post(
            "/v1/replay",
            json={
                "trace_id": trace.id,
                "span_id": "span-does-not-exist",
                "edited_input": {},
            },
            headers={
                "Authorization": "Bearer replay-404-span-key",
                "X-Provider-Api-Key": "sk-fake-key",
            },
        )
        assert resp.status_code == 404

    async def test_replay_record_written_to_replays_table(
        self, client, db_session, httpx_mock: HTTPXMock
    ):
        """A successful replay creates a row in the replays table."""
        from sqlalchemy import select

        from backend.models import ReplayRecord

        httpx_mock.add_response(
            method="POST",
            url="https://api.openai.com/v1/chat/completions",
            json=_openai_chat_response("stored"),
            status_code=200,
        )

        proj = await make_project(db_session, api_key="replay-store-key-001")
        span_id = str(uuid.uuid4())
        trace = await make_trace(
            db_session,
            proj.id,
            raw=_openai_trace_raw(proj.id, span_id),
        )

        resp = await client.post(
            "/v1/replay",
            json={
                "trace_id": trace.id,
                "span_id": span_id,
                "edited_input": {"params": {"temperature": 1.0}},
            },
            headers={
                "Authorization": "Bearer replay-store-key-001",
                "X-Provider-Api-Key": "sk-fake-store-key",
            },
        )
        assert resp.status_code == 200

        replay_id = resp.json()["replay_id"]
        result = await db_session.execute(
            select(ReplayRecord).where(ReplayRecord.id == replay_id)
        )
        record = result.scalar_one_or_none()
        assert record is not None
        assert record.trace_id == trace.id
        assert record.span_id == span_id
