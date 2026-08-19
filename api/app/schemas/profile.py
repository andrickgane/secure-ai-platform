from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import (
    BaseModel,
    Field,
)


PROFILE_NAME_PATTERN = (
    r"^[a-z0-9]"
    r"([-a-z0-9]*[a-z0-9])?$"
)


class CustomProfileCreate(BaseModel):
    name: str = Field(
        min_length=3,
        max_length=63,
        pattern=PROFILE_NAME_PATTERN,
    )

    display_name: str = Field(
        min_length=1,
        max_length=120,
    )

    description: str | None = Field(
        default=None,
        max_length=4000,
    )

    category: str = Field(
        default="custom",
        min_length=1,
        max_length=64,
    )

    base_profile: str = Field(
        min_length=1,
        max_length=63,
    )

    overrides: dict[str, Any] = Field(
        default_factory=dict
    )


class CustomProfileUpdate(BaseModel):
    display_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
    )

    description: str | None = Field(
        default=None,
        max_length=4000,
    )

    category: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )

    base_profile: str | None = Field(
        default=None,
        min_length=1,
        max_length=63,
    )

    overrides: dict[str, Any] | None = None


class CustomProfileRecord(BaseModel):
    id: int

    name: str

    display_name: str

    description: str | None

    category: str

    base_profile: str

    overrides: dict[str, Any]

    owner_id: int | None

    source: str = "custom"

    immutable: bool = False

    created_at: datetime

    updated_at: datetime


class EffectiveProfileResponse(BaseModel):
    profile_id: str

    source: str

    base_profile: str | None

    immutable: bool

    definition: dict[str, Any]
