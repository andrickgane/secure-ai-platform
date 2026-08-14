from __future__ import annotations

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


class UserCreate(BaseModel):
    email: EmailStr

    password: str = Field(
        ...,
        min_length=12,
        max_length=128,
    )

    role: UserRole = "user"


class UserResponse(BaseModel):
    id: int

    email: EmailStr

    role: UserRole

    is_active: bool


class LoginRequest(BaseModel):
    email: EmailStr

    password: str


class TokenResponse(BaseModel):
    access_token: str

    token_type: str = "bearer"

    expires_in: int
