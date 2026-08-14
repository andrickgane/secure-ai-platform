from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
)


UserRole = Literal[
    "user",
    "admin",
    "platform_admin",
]


class UserCreateRequest(BaseModel):
    email: EmailStr

    password: str = Field(
        ...,
        min_length=12,
        max_length=128,
    )

    role: UserRole = "user"


class UserStatusUpdate(BaseModel):
    is_active: bool


class UserRecord(BaseModel):
    id: int

    email: EmailStr

    role: UserRole

    is_active: bool

    created_at: datetime

    updated_at: datetime
