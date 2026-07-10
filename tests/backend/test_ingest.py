"""
tests/backend/test_ingest.py — Integration tests for POST /v1/ingest.

Uses FastAPI TestClient + in-memory SQLite.

Backlog: 2.5.2
"""

from __future__ import annotations

import uuid

import pytest

from tests.backend.conftest import make_project

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_trace_payload(project_id: str = "proj-123") -> dict:
    return {
        "trace_id": str(uuid.uuid4()),
        "project_id": project_id,
        "source": "openai",
        "started_at": "2024-01-01T00:00:00Z",
        "ended_at": "2024-01-01T00:00:05Z",
        "status": "success",
        "spans": [],
    }


def _full_trace_payload(project_id: str = "proj-123") -> dict:
    span_id = str(uuid.uuid4())
    return {
        "trace_id": str(uuid.uuid4()),
        "project_id": project_id,
        "source": "langchain",
        "started_at": "2024-01-01T00:00:00Z",
        "ended_at": "2024-01-01T00:00:10Z",
        "status": "success",
        "spans": [
            {
                "span_id": span_id,
                "parent_span_id": None,
                "type": "llm_call",
                "name": "chat",
                "started_at": "2024-01-01T00:00:00Z",
                "ended_at": "2024-01-01T00:00:10Z",
                "status": "success",
                "input": {
                    "messages": [
                        {"role": "system", "content": "You are helpful."},
                        {"role": "user", "content": "Hello"},
                    ],
                    "model": "gpt-4o",
                    "params": {"temperature": 0.5, "max_tokens": 512},
                    "tools": [{"name": "search", "schema": {"query": "string"}}],
                    "retrieved_context": [
                        {
                            "source": "wiki",
                            "content": "Paris is the capital of France.",
                            "score": 0.95,
                        }
                    ],
                },
                "output": {
                    "content": "Paris!",
                    "tool_calls": [{"name": "search", "arguments": {"query": "Paris"}}],
                },
                "error": None,
            }
        ],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestIngestEndpoint:

    async def test_valid_minimal_trace_returns_202(self, client, db_session):
        """A minimal valid trace returns HTTP 202."""
        project = await make_project(db_session, api_key="ingest-key-001")
        payload = _minimal_trace_payload(project.id)

        resp = await client.post(
            "/v1/ingest",
            json=payload,
            headers={"Authorization": "Bearer ingest-key-001"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "trace_id" in data
        assert data["status"] == "accepted"

    async def test_valid_full_trace_stores_correctly(self, client, db_session):
        """A trace with all optional fields (tools, retrieved_context) returns 202."""
        project = await make_project(db_session, api_key="ingest-key-002")
        payload = _full_trace_payload(project.id)

        resp = await client.post(
            "/v1/ingest",
            json=payload,
            headers={"Authorization": "Bearer ingest-key-002"},
        )
        assert resp.status_code == 202

    async def test_malformed_payload_returns_422(self, client, db_session):
        """Posting a payload missing required fields returns HTTP 422."""
        project = await make_project(db_session, api_key="ingest-key-003")  # noqa: F841

        resp = await client.post(
            "/v1/ingest",
            json={"not": "a trace"},
            headers={"Authorization": "Bearer ingest-key-003"},
        )
        assert resp.status_code == 422

    async def test_missing_api_key_returns_401(self, client, db_session):
        """Posting without an API key returns HTTP 401."""
        resp = await client.post(
            "/v1/ingest",
            json=_minimal_trace_payload(),
        )
        assert resp.status_code == 401

    async def test_two_projects_traces_stored_independently(self, client, db_session):
        """Traces from two different projects are stored independently."""
        proj_a = await make_project(db_session, api_key="proj-a-key")
        proj_b = await make_project(db_session, api_key="proj-b-key")

        payload_a = _minimal_trace_payload(proj_a.id)
        payload_b = _minimal_trace_payload(proj_b.id)

        resp_a = await client.post(
            "/v1/ingest",
            json=payload_a,
            headers={"Authorization": "Bearer proj-a-key"},
        )
        resp_b = await client.post(
            "/v1/ingest",
            json=payload_b,
            headers={"Authorization": "Bearer proj-b-key"},
        )

        assert resp_a.status_code == 202
        assert resp_b.status_code == 202

        trace_id_a = resp_a.json()["trace_id"]
        trace_id_b = resp_b.json()["trace_id"]
        assert trace_id_a != trace_id_b

        # Project B cannot retrieve Project A's trace.
        detail_resp = await client.get(
            f"/v1/traces/{trace_id_a}",
            headers={"Authorization": "Bearer proj-b-key"},
        )
        assert detail_resp.status_code == 404

    async def test_invalid_source_enum_returns_422(self, client, db_session):
        """A trace with an invalid source enum value returns HTTP 422."""
        project = await make_project(db_session, api_key="ingest-key-005")
        payload = _minimal_trace_payload(project.id)
        payload["source"] = "unknown_framework"

        resp = await client.post(
            "/v1/ingest",
            json=payload,
            headers={"Authorization": "Bearer ingest-key-005"},
        )
        assert resp.status_code == 422
