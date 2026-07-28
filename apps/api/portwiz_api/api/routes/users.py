"""User management routes (admin/auditor)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.audit import append_audit, field_diff
from ...core.db import get_session
from ...core.security import hash_password
from ...models.user import User, UserRole
from ...schemas.user import UserCreate, UserRead, UserUpdate
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
    # All roles may read the user list (operators/auditors need owner names to
    # resolve asset ownership); only admins may create/update/delete users, and
    # the Users menu itself is admin-only in the UI.
    _: User = Depends(require_roles(UserRole.admin, UserRole.operator, UserRole.auditor)),
    session: AsyncSession = Depends(get_session),
) -> list[User]:
    result = await session.execute(select(User).order_by(User.created_at))
    return list(result.scalars().all())


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: uuid.UUID,
    _: User = Depends(require_roles(UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    current_user: User = Depends(require_roles(UserRole.admin)),
    session: AsyncSession = Depends(get_session),
) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    changes = payload.model_dump(exclude_unset=True)
    # Lockout guards: an admin must not demote or disable their own account, or
    # they could lock themselves (and possibly everyone) out of administration.
    if user.id == current_user.id:
        if "role" in changes and changes["role"] != UserRole.admin:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "You cannot change your own admin role."
            )
        if changes.get("is_active") is False:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "You cannot deactivate your own account."
            )

    before = {key: getattr(user, key) for key in changes}
    for key, value in changes.items():
        setattr(user, key, value)
    await append_audit(
        session,
        action="user.updated",
        actor_id=current_user.id,
        actor_email=current_user.email,
        target_type="user",
        target_id=str(user.id),
        payload={"email": user.email, "changes": field_diff(before, changes)},
    )
    await session.commit()
    await session.refresh(user)
    return user
