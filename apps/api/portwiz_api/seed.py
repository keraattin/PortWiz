"""Idempotent startup seeding (first admin user)."""

from __future__ import annotations

import logging

from sqlalchemy import func, select

from .core.audit import append_audit
from .core.config import get_settings
from .core.db import async_session_maker
from .core.security import hash_password
from .models.user import User, UserRole

logger = logging.getLogger("portwiz.seed")


async def seed_first_admin() -> None:
    """Create the first admin user from settings if the table is empty.

    No-op when credentials are not configured or any user already exists.
    """
    settings = get_settings()
    if not settings.first_admin_email or not settings.first_admin_password:
        logger.info("First-admin seeding skipped (no credentials configured).")
        return

    async with async_session_maker() as session:
        user_count = (
            await session.execute(select(func.count()).select_from(User))
        ).scalar_one()
        if user_count and user_count > 0:
            return

        admin = User(
            email=settings.first_admin_email,
            hashed_password=hash_password(settings.first_admin_password),
            full_name=settings.first_admin_full_name,
            role=UserRole.admin,
        )
        session.add(admin)
        await session.flush()

        await append_audit(
            session,
            action="user.seeded_admin",
            actor_id=admin.id,
            actor_email=admin.email,
            target_type="user",
            target_id=str(admin.id),
            payload={"email": admin.email},
        )
        await session.commit()
        logger.info("Seeded first admin user: %s", admin.email)
