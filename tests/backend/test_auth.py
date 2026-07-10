"""
tests/backend/test_auth.py — Unit tests for the API key auth dependency.

Tests run without a real Postgres instance (SQLite in-memory via conftest).

Backlog: 2.5.1
"""

from __future__ import annotations

import pytest

from tests.backend.conftest import make_project


@pytest.mark.asyncio
class TestAuthMiddleware:
    """Tests for the auth dependency via the /v1/projects/me endpoint."""

    async def test_valid_key_resolves_project(self, client, db_session):
        """A valid Bearer token returns 200 and the correct project info."""
        project = await make_project(
            db_session, name="Auth Test", api_key="valid-key-001"
        )

        resp = await client.get(
            "/v1/projects/me",
            headers={"Authorization": "Bearer valid-key-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == project.id
        assert data["name"] == "Auth Test"
        # api_key must NOT appear in the response
        assert "api_key" not in data

    async def test_missing_authorization_header_returns_401(self, client, db_session):
        """No Authorization header → 401."""
        resp = await client.get("/v1/projects/me")
        assert resp.status_code == 401

    async def test_invalid_key_returns_401(self, client, db_session):
        """Authorization: Bearer <nonexistent-key> → 401."""
        resp = await client.get(
            "/v1/projects/me",
            headers={"Authorization": "Bearer this-key-does-not-exist"},
        )
        assert resp.status_code == 401

    async def test_malformed_header_not_bearer_returns_401(self, client, db_session):
        """Authorization: Token <key> (wrong scheme) → 401."""
        await make_project(db_session, api_key="good-key-002")
        resp = await client.get(
            "/v1/projects/me",
            headers={"Authorization": "Token good-key-002"},
        )
        assert resp.status_code == 401

    async def test_empty_bearer_token_returns_401(self, client, db_session):
        """Authorization: Bearer (empty token) → 401."""
        resp = await client.get(
            "/v1/projects/me",
            headers={"Authorization": "Bearer "},
        )
        assert resp.status_code == 401

    async def test_public_endpoint_requires_no_auth(self, client, db_session):
        """POST /v1/projects is not protected — no auth header needed."""
        resp = await client.post(
            "/v1/projects",
            json={"name": "No-auth project"},
        )
        assert resp.status_code == 201
