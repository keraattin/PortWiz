"""Liveness and readiness endpoints (mounted at the root, outside /api/v1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: the process is up."""
    return {"status": "ok"}


@router.get("/health/db")
async def health_db(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    """Readiness: the database is reachable."""
    await session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}
