from __future__ import annotations

from pydantic import (
    BaseModel,
    Field,
)


class ModelCatalogItem(BaseModel):
    id: str

    display_name: str

    description: str | None = None

    capabilities: list[str] = Field(
        default_factory=list
    )

    default_profile: str | None = None

    supported_runtimes: list[str] = Field(
        default_factory=list
    )

    approved: bool = False

    source: str = "static"

    provider: str | None = None

    repository: str | None = None

    revision: str | None = None

    artifact_reference: str | None = None

    artifact_digest: str | None = None


class ProfileLimits(BaseModel):
    max_model_len: int

    max_tokens: int

    temperature_min: float

    temperature_max: float

    top_p_min: float

    top_p_max: float


class ProfileInference(BaseModel):
    streaming: bool

    max_requests: int

    timeout_seconds: int


class ProfileSecurity(BaseModel):
    allow_user_overrides: bool

    overridable_parameters: list[str]


class ProfileCatalogItem(BaseModel):
    id: str

    display_name: str

    description: str | None = None

    category: str

    # ======================================================
    # GOVERNANCE
    # ======================================================

    source: str = "builtin"

    immutable: bool = True

    base_profile: str | None = None

    # ======================================================
    # EFFECTIVE DEFAULTS
    # ======================================================

    max_model_len: int

    max_tokens: int

    temperature: float

    top_p: float

    replicas: int

    # ======================================================
    # RESOURCES
    # ======================================================

    cpu_request: str

    memory_request: str

    cpu_limit: str

    memory_limit: str

    # ======================================================
    # RUNTIME POLICY
    # ======================================================

    allowed_runtimes: list[str] = Field(
        default_factory=list
    )

    preferred_runtimes: list[str] = Field(
        default_factory=list
    )

    # ======================================================
    # POLICY
    # ======================================================

    limits: ProfileLimits

    inference: ProfileInference

    security: ProfileSecurity


class RuntimeCatalogItem(BaseModel):
    id: str

    display_name: str

    description: str | None = None

    deployment_mode: str

    accelerator: str | None = None

    capabilities: list[str] = Field(
        default_factory=list
    )
