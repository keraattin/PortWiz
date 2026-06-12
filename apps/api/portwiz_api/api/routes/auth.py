"""Authentication routes: login and current-user lookup."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.audit import append_audit
from ...core.db import get_session
from ...core.security import create_access_token, verify_password
from ...models.user import User, UserRole
from ...schemas.auth import Token
from ...schemas.user import UserRead
from ..deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
) -> Token:
    user = (
        await session.execute(select(User).where(User.email == form.username))
    ).scalar_one_or_none()

    if user is None or not user.is_active or not verify_password(
        form.password, user.hashed_password
    ):
        await append_audit(
            session,
            action="auth.login.failed",
            target_type="user",
            target_id=form.username,
            payload={"email": form.username},
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token(subject=str(user.id), role=UserRole(user.role).value)
    await append_audit(
        session,
        action="auth.login.success",
        actor_id=user.id,
        actor_email=user.email,
        target_type="user",
        target_id=str(user.id),
    )
    await session.commit()
    return Token(access_token=token)


@router.get("/me", response_model=UserRead)
async def read_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
