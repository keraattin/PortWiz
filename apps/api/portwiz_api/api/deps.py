"""Shared FastAPI dependencies: authentication and role checks."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..core.db import get_session
from ..core.security import decode_access_token
from ..models.user import User, UserRole

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")

_credentials_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if subject is None:
            raise _credentials_exc
        user_id = uuid.UUID(str(subject))
    except (jwt.PyJWTError, ValueError) as exc:
        raise _credentials_exc from exc

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise _credentials_exc
    return user


def require_roles(
    *roles: UserRole,
) -> Callable[[User], Coroutine[Any, Any, User]]:
    """Dependency factory enforcing that the current user has one of ``roles``."""

    async def checker(current_user: User = Depends(get_current_user)) -> User:
        # UserRole is a str-enum, so equality holds even if the ORM returned a
        # plain string for the role column.
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return checker
