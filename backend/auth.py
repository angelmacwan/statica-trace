"""
auth.py — API key authentication dependency for FastAPI.

Reads `Authorization: Bearer <key>` from the request, validates it against
the projects table, and injects the resolved project_id into the endpoint.

Backlog: 2.1.3
"""

from __future__ import annotations

import logging

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Project

logger = logging.getLogger(__name__)


async def get_current_project_id(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> str:
    """
    FastAPI dependency.

    - Reads the ``Authorization: Bearer <key>`` header.
    - Looks up the key in the projects table.
    - Returns the project's ``id`` string on success.
    - Raises HTTP 401 for any invalid / missing / malformed token.

    The API key is *never* logged.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not authorization:
        raise credentials_exception

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise credentials_exception

    raw_key = parts[1].strip()
    if not raw_key:
        raise credentials_exception

    result = await db.execute(select(Project.id).where(Project.api_key == raw_key))
    project_id: str | None = result.scalar_one_or_none()

    if project_id is None:
        raise credentials_exception

    return project_id
