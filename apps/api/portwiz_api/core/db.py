"""Async database engine and session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    # Never echo SQL (statements + bound parameters) in production, even if debug
    # was left on; that would leak data into logs. Access logs come from uvicorn,
    # not this flag, so nothing observability-related is lost.
    echo=settings.debug and settings.environment != "production",
    pool_pre_ping=True,
    future=True,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session."""
    async with async_session_maker() as session:
        yield session
