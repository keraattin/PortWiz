"""Unit tests for the immutable hash-chained audit log.

These cover the core integrity guarantee: the chain grows correctly, verifies
intact, and any tampering is detected at the offending event.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

import portwiz_api.models  # noqa: F401  (registers tables)
from portwiz_api.core.audit import GENESIS_HASH, append_audit, verify_chain


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    # Shared in-memory SQLite (StaticPool) so every session sees the same DB.
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def test_chain_links_and_verifies(session: AsyncSession) -> None:
    first = await append_audit(session, action="test.one")
    second = await append_audit(session, action="test.two", payload={"x": 1})
    await session.commit()

    assert first.prev_hash == GENESIS_HASH
    assert second.prev_hash == first.hash
    assert first.hash != second.hash

    ok, broken_seq = await verify_chain(session)
    assert ok is True
    assert broken_seq is None


async def test_tampering_is_detected(session: AsyncSession) -> None:
    tampered = await append_audit(session, action="test.one")
    await append_audit(session, action="test.two")
    await session.commit()

    # Mutate a stored field without recomputing the hash.
    tampered.action = "test.tampered"
    session.add(tampered)
    await session.commit()

    ok, broken_seq = await verify_chain(session)
    assert ok is False
    assert broken_seq == tampered.seq
