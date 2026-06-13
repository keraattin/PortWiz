"""Shared pytest fixtures.

The ``client`` fixture runs the FastAPI app in-process against an in-memory
SQLite database (the ``get_session`` dependency is overridden), so API tests
need no PostgreSQL. They are skipped automatically when asyncpg or httpx are
absent, so the pure-logic unit tests still run in a minimal environment.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

# Keep tests hermetic: never send real notifications or hit external services,
# regardless of what the local .env configures.
os.environ["PORTWIZ_NOTIFICATION_RECIPIENTS"] = "[]"
os.environ["PORTWIZ_NOTIFICATIONS_ENABLED"] = "false"
os.environ["PORTWIZ_JIRA_ENABLED"] = "false"


@pytest_asyncio.fixture
async def db():
    # Importing the app pulls in core.db, which builds an asyncpg engine.
    pytest.importorskip("asyncpg")
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    from sqlalchemy.pool import StaticPool
    from sqlmodel import SQLModel

    import portwiz_api.models  # noqa: F401  (registers tables)

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db):
    httpx = pytest.importorskip("httpx")
    from portwiz_api.core.db import get_session
    from portwiz_api.main import app

    async def _override_get_session():
        async with db() as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_headers(client, db) -> dict[str, str]:
    from portwiz_api.core.security import hash_password
    from portwiz_api.models.user import User, UserRole

    async with db() as session:
        session.add(
            User(
                email="admin@test.local",
                hashed_password=hash_password("Secret123!"),
                full_name="Test Admin",
                role=UserRole.admin,
            )
        )
        await session.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "Secret123!"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}
