from __future__ import annotations

from typing import Any

from pydantic import (
    BaseModel,
    Field,
)


PROFILE_NAME_PATTERN = (
    r"^[a-z0-9]"
    r"([-a-z0-9]*[a-z0-9])?$"
)


class ProfileCloneRequest(BaseModel):
    """
    Clone an existing built-in or custom profile.

    Only the new profile overrides are persisted.
    The source profile becomes base_profile.
    """

    name: str = Field(
        ...,
        min_length=3,
        max_length=63,
        pattern=PROFILE_NAME_PATTERN,
    )

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

    overrides: dict[str, Any] = Field(
        default_factory=dict
    )
