from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
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

    artifact_patterns: list[str] = Field(
        default_factory=list,
        max_length=50,
    )

    download_complete_repository: bool = False

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


    @field_validator("artifact_patterns")
    @classmethod
    def validate_artifact_patterns(
        cls,
        value: list[str],
    ) -> list[str]:
        cleaned: list[str] = []

        for pattern in value:
            pattern = pattern.strip()

            if not pattern:
                continue

            if len(pattern) > 255:
                raise ValueError(
                    "Artifact pattern exceeds 255 characters"
                )

            if pattern not in cleaned:
                cleaned.append(pattern)

        return cleaned

    @model_validator(mode="after")
    def validate_ingestion_selection(
        self,
    ) -> "ModelImportRequest":
        if (
            not self.artifact_patterns
            and not self.download_complete_repository
        ):
            raise ValueError(
                "Select at least one artifact pattern or "
                "explicitly enable complete repository download"
            )

        return self


class ModelRequestRecord(BaseModel):
    id: int

    provider: str

    repository: str

    revision: str

    requested_profile: str | None

    purpose: str | None

    artifact_patterns: list[str]

    download_complete_repository: bool

    artifact_format: str | None

    architecture: str | None

    quantization: str | None

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
