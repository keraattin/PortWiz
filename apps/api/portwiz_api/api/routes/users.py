"""User management routes (admin/auditor)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.audit import append_audit
from ...core.db import get_session
from ...core.security import hash_password
from ...models.user import User, UserRole
from ...schemas.user import UserCreate, UserRead
from ..deps import require_roles

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    current_user: User = Depends(require_roles(UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> User:
    existing = (
        await session.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
    )
    session.add(user)
    await session.flush()

    await append_audit(
        session,
        action="user.created",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="user",
        target_id=str(user.id),
        payload={"email": user.email, "role": UserRole(user.role).value},
    )
    await session.commit()
    await session.refresh(user)
    return user


@router.get("", response_model=list[UserRead])
async def list_users(
    _: User = Depends(require_roles(UserRole.admin, UserRole.auditor)),
    session: AsyncSession = Depends(get_session),
) -> list[User]:
    result = await session.execute(select(User).order_by(User.created_at))
    return list(result.scalars().all())
