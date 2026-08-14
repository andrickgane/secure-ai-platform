from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


ModelRequestStatus = Literal[
    "pending",
    "quarantined",
    "scanning",
    "approved",
    "rejected",
    "promoting",
    "published",
    "failed",
]


class ModelImportRequest(BaseModel):
    provider: Literal[
        "huggingface"
    ] = "huggingface"

    repository: str = Field(
        ...,
        min_length=3,
        max_length=255,
        examples=[
            "mistralai/Mistral-7B-Instruct-v0.3"
        ],
    )

    revision: str = Field(
        default="main",
        min_length=1,
        max_length=255,
    )

    requested_profile: str | None = Field(
        default=None,
        max_length=100,
    )

    purpose: str | None = Field(
        default=None,
        max_length=2000,
    )

    @field_validator("repository")
    @classmethod
    def validate_repository(
        cls,
        value: str,
    ) -> str:

        value = value.strip()

        if "/" not in value:
            raise ValueError(
                "Hugging Face repository must "
                "use the format owner/model"
            )

        owner, model = value.split(
            "/",
            1,
        )

        if not owner or not model:
            raise ValueError(
                "Invalid Hugging Face repository"
            )

        return value


class ModelRequestRecord(BaseModel):
    id: int

    provider: str

    repository: str

    revision: str

    requested_profile: str | None

    purpose: str | None

    status: str

    status_message: str | None

    catalog_model_id: str | None

    artifact_reference: str | None

    artifact_digest: str | None

    requested_by_user_id: int

    created_at: datetime

    updated_at: datetime

    model_config = {
        "from_attributes": True
    }


class ModelRequestStatusUpdate(BaseModel):
    status: ModelRequestStatus

    message: str | None = Field(
        default=None,
        max_length=4000,
    )
