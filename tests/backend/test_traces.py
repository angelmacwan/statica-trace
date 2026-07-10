"""
tests/backend/test_traces.py — Integration tests for GET /v1/traces
and GET /v1/traces/{id}.

Backlog: 2.5.3
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from tests.backend.conftest import make_project, make_trace


@pytest.mark.asyncio
class TestListTraces:

    async def test_list_returns_only_own_project_traces(self, client, db_session):
        """A project can only see its own traces."""
        proj_a = await make_project(db_session, api_key="list-key-a1")
        proj_b = await make_project(db_session, api_key="list-key-b1")

        await make_trace(db_session, proj_a.id, source="openai")
        await make_trace(db_session, proj_b.id, source="langchain")

        resp = await client.get(
            "/v1/traces",
            headers={"Authorization": "Bearer list-key-a1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["source"] == "openai"

    async def test_status_error_filter(self, client, db_session):
        """?status=error returns only error traces."""
        proj = await make_project(db_session, api_key="list-key-e1")
        await make_trace(db_session, proj.id, status="success")
        await make_trace(db_session, proj.id, status="error")

        resp = await client.get(
            "/v1/traces?status=error",
            headers={"Authorization": "Bearer list-key-e1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(item["status"] == "error" for item in data["items"])
        assert data["total"] == 1

    async def test_status_success_filter(self, client, db_session):
        """?status=success returns only success traces."""
        proj = await make_project(db_session, api_key="list-key-s1")
        await make_trace(db_session, proj.id, status="success")
        await make_trace(db_session, proj.id, status="error")

        resp = await client.get(
            "/v1/traces?status=success",
            headers={"Authorization": "Bearer list-key-s1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(item["status"] == "success" for item in data["items"])
        assert data["total"] == 1

    async def test_pagination_limit_and_offset(self, client, db_session):
        """Pagination: limit=2&offset=0 returns 2 items; offset=2 returns the rest."""
        proj = await make_project(db_session, api_key="list-key-p1")
        base_time = datetime.now(tz=UTC)
        for i in range(4):
            await make_trace(
                db_session,
                proj.id,
                created_at=base_time - timedelta(seconds=i),
            )

        resp1 = await client.get(
            "/v1/traces?limit=2&offset=0",
            headers={"Authorization": "Bearer list-key-p1"},
        )
        assert resp1.status_code == 200
        page1 = resp1.json()
        assert len(page1["items"]) == 2
        assert page1["limit"] == 2
        assert page1["offset"] == 0

        resp2 = await client.get(
            "/v1/traces?limit=2&offset=2",
            headers={"Authorization": "Bearer list-key-p1"},
        )
        assert resp2.status_code == 200
        page2 = resp2.json()
        assert len(page2["items"]) == 2

        # IDs must not overlap
        ids1 = {item["trace_id"] for item in page1["items"]}
        ids2 = {item["trace_id"] for item in page2["items"]}
        assert ids1.isdisjoint(ids2)

    async def test_default_sort_newest_first(self, client, db_session):
        """Default sort is created_at DESC (newest first)."""
        proj = await make_project(db_session, api_key="list-key-sort1")
        base = datetime.now(tz=UTC)
        await make_trace(db_session, proj.id, created_at=base - timedelta(hours=1))
        new_trace = await make_trace(db_session, proj.id, created_at=base)

        resp = await client.get(
            "/v1/traces",
            headers={"Authorization": "Bearer list-key-sort1"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 2
        assert items[0]["trace_id"] == new_trace.id

    async def test_missing_auth_returns_401(self, client, db_session):
        resp = await client.get("/v1/traces")
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestTraceDetail:

    async def test_detail_returns_full_raw_payload(self, client, db_session):
        """Detail endpoint returns the full raw payload including all spans."""
        proj = await make_project(db_session, api_key="detail-key-001")
        trace = await make_trace(db_session, proj.id)

        resp = await client.get(
            f"/v1/traces/{trace.id}",
            headers={"Authorization": "Bearer detail-key-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "spans" in data
        assert isinstance(data["spans"], list)

    async def test_detail_404_for_other_projects_trace(self, client, db_session):
        """Trace belonging to another project returns 404."""
        proj_a = await make_project(db_session, api_key="detail-key-a2")
        await make_project(db_session, api_key="detail-key-b2")
        trace_a = await make_trace(db_session, proj_a.id)

        resp = await client.get(
            f"/v1/traces/{trace_a.id}",
            headers={"Authorization": "Bearer detail-key-b2"},
        )
        assert resp.status_code == 404

    async def test_detail_404_for_nonexistent_trace(self, client, db_session):
        """A nonexistent trace ID returns 404."""
        await make_project(db_session, api_key="detail-key-003")

        resp = await client.get(
            f"/v1/traces/{uuid.uuid4()}",
            headers={"Authorization": "Bearer detail-key-003"},
        )
        assert resp.status_code == 404

    async def test_detail_spans_are_flat_list(self, client, db_session):
        """Spans are returned as a flat list (tree built client-side)."""
        proj = await make_project(db_session, api_key="detail-key-004")
        parent_id = str(uuid.uuid4())
        child_id = str(uuid.uuid4())
        raw = {
            "trace_id": str(uuid.uuid4()),
            "project_id": proj.id,
            "source": "langchain",
            "status": "success",
            "started_at": "2024-01-01T00:00:00Z",
            "ended_at": "2024-01-01T00:00:10Z",
            "spans": [
                {
                    "span_id": parent_id,
                    "parent_span_id": None,
                    "type": "llm_call",
                    "name": "parent",
                    "started_at": "2024-01-01T00:00:00Z",
                    "ended_at": "2024-01-01T00:00:10Z",
                    "status": "success",
                    "input": {
                        "messages": [],
                        "model": "gpt-4o",
                        "params": {},
                        "tools": [],
                        "retrieved_context": [],
                    },
                    "output": {"content": "ok", "tool_calls": []},
                    "error": None,
                },
                {
                    "span_id": child_id,
                    "parent_span_id": parent_id,
                    "type": "tool_call",
                    "name": "child",
                    "started_at": "2024-01-01T00:00:02Z",
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
                },
            ],
        }
        trace = await make_trace(db_session, proj.id, raw=raw)

        resp = await client.get(
            f"/v1/traces/{trace.id}",
            headers={"Authorization": "Bearer detail-key-004"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Flat list — not nested
        assert isinstance(data["spans"], list)
        assert len(data["spans"]) == 2
        span_ids = {s["span_id"] for s in data["spans"]}
        assert parent_id in span_ids
        assert child_id in span_ids
