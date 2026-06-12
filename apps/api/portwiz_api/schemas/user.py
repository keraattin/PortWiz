"""User request/response schemas.

Note on email validation: we deliberately use a light `str` check rather than
Pydantic's ``EmailStr``. PortWiz targets internal networks where Active
Directory domains commonly end in ``.local`` (and similar special-use TLDs),
which ``email-validator`` rejects. Over-strict validation would lock out exactly
our audience, so we only require a sane "local@domain" shape.
"""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models.user import UserRole


def _validate_email_shape(value: str) -> str:
    value = value.strip()
    local, _, domain = value.partition("@")
    if not local or not domain or "." not in domain and domain != "localhost":
        raise ValueError("email must look like local-part@domain")
    return value.lower()


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = None
    role: UserRole = UserRole.operator

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _validate_email_shape(v)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None
    role: UserRole
    is_active: bool
    created_at: dt.datetime
