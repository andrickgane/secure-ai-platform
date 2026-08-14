from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    Field,
)


class ChatMessage(BaseModel):
    role: Literal[
        "system",
        "user",
        "assistant",
    ]

    content: str = Field(
        ...,
        min_length=1,
    )


class ChatCompletionRequest(BaseModel):
    messages: list[
        ChatMessage
    ] = Field(
        ...,
        min_length=1,
    )

    # Advanced profile-governed overrides.

    temperature: float | None = None

    max_tokens: int | None = Field(
        default=None,
        ge=1,
    )

    top_p: float | None = None


class EffectiveInferenceParameters(
    BaseModel
):
    temperature: float

    max_tokens: int

    top_p: float

    max_model_len: int


class ChatCompletionResponse(BaseModel):
    deployment: str

    model: str

    profile: str

    runtime: str

    content: str

    finish_reason: str | None = None

    prompt_tokens: int | None = None

    completion_tokens: int | None = None

    total_tokens: int | None = None

    parameters: (
        EffectiveInferenceParameters
    )
