from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class ConversationCreate(BaseModel):
    title: str = Field(
        default="New chat",
        min_length=1,
        max_length=200,
    )

    deployment_name: str | None = Field(
        default=None,
        max_length=63,
    )


class ConversationUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    deployment_name: str | None = Field(
        default=None,
        max_length=63,
    )


class ConversationMessageCreate(BaseModel):
    role: Literal[
        "system",
        "user",
        "assistant",
    ]

    content: str = Field(
        ...,
        min_length=1,
    )

    attachment_ids: list[int] = Field(
        default_factory=list,
        max_length=8,
    )

    model: str | None = None
    profile: str | None = None
    runtime: str | None = None

    parameters: dict[str, Any] | None = None

    prompt_tokens: int | None = Field(
        default=None,
        ge=0,
    )

    completion_tokens: int | None = Field(
        default=None,
        ge=0,
    )

    total_tokens: int | None = Field(
        default=None,
        ge=0,
    )

    latency_ms: int | None = Field(
        default=None,
        ge=0,
    )

    first_token_latency_ms: int | None = Field(
        default=None,
        ge=0,
    )

    generation_duration_ms: int | None = Field(
        default=None,
        ge=0,
    )

    generation_tokens_per_second: float | None = Field(
        default=None,
        ge=0,
    )

    output_tokens_per_second: float | None = Field(
        default=None,
        ge=0,
    )

    status: Literal[
        "completed",
        "stopped",
        "error",
    ] = "completed"


class ConversationMessageRecord(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: int
    conversation_id: int

    role: str
    content: str

    model: str | None
    profile: str | None
    runtime: str | None

    parameters: dict[str, Any] | None

    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None

    latency_ms: int | None
    first_token_latency_ms: int | None
    generation_duration_ms: int | None

    generation_tokens_per_second: float | None
    output_tokens_per_second: float | None

    status: str
    created_at: datetime


class ConversationAttachmentRecord(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: int
    conversation_id: int

    message_id: int | None

    filename: str
    media_type: str
    size_bytes: int
    sha256: str

    created_at: datetime


class ConversationRecord(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: int
    owner_id: int

    title: str

    deployment_name: str | None
    model: str | None
    profile: str | None
    runtime: str | None

    created_at: datetime
    updated_at: datetime


class ConversationDetail(
    ConversationRecord
):
    messages: list[
        ConversationMessageRecord
    ] = Field(
        default_factory=list
    )

    attachments: list[
        ConversationAttachmentRecord
    ] = Field(
        default_factory=list
    )
