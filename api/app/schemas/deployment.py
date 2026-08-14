from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


# ==========================================================
# TYPES
# ==========================================================


DeploymentStatus = Literal[
    "planned",
    "validated",
    "deploying",
    "ready",
    "deployed",
    "stopped",
    "failed",
]


DeploymentMode = Literal[
    "external",
    "kubernetes",
]


# ==========================================================
# DEPLOYMENT REQUEST
# ==========================================================


class DeploymentCreate(BaseModel):
    """
    User request for an AI model deployment.

    The user selects:
    - deployment name
    - model
    - profile
    - runtime preference

    Runtime "auto" lets the Control Plane select
    the best currently available compatible runtime.
    """

    name: str = Field(
        ...,
        min_length=3,
        max_length=63,
        pattern=(
            r"^[a-z0-9]"
            r"([-a-z0-9]*[a-z0-9])?$"
        ),
    )

    model: str = Field(
        ...,
        min_length=1,
    )

    profile: str = Field(
        default="interactive",
        min_length=1,
    )

    runtime: str = Field(
        default="auto",
        min_length=1,
    )


# ==========================================================
# RESOLVED DEPLOYMENT CONTEXT
# ==========================================================


class DeploymentContext(BaseModel):
    """
    Internal trusted deployment context.

    This object is built by DeploymentService after:

    - catalog validation
    - model approval validation
    - runtime selection
    - trusted artifact resolution
    - compute/profile resolution

    It must never contain user-controlled artifact
    references that have not passed platform validation.
    """

    name: str

    model: str

    repository: str

    profile: str

    runtime: str

    deployment_mode: DeploymentMode

    external_endpoint: str | None = None

    model_artifact_reference: str

    model_artifact_digest: str

    image: str | None = None

    port: int | None = None

    replicas: int = 1

    cpu_request: str | None = None

    memory_request: str | None = None

    cpu_limit: str | None = None

    memory_limit: str | None = None

    accelerator: str | None = None

    gpu_count: int = 0

    node_selector: dict[str, str] = Field(
        default_factory=dict
    )

    max_model_len: int | None = None

    model_cache_enabled: bool = False

    model_cache_size: str | None = None

    model_cache_mount_path: str = (
        "/models/model"
    )


# ==========================================================
# DEPLOYMENT API RECORD
# ==========================================================


class DeploymentRecord(BaseModel):
    """
    Deployment representation returned by the API.

    The status values represent the complete V1 lifecycle:

        planned
            ↓
        validated
            ↓
        deploying
            ↓
        ready / deployed

    A previously active external runtime may transition to:

        stopped

    Any orchestration failure transitions to:

        failed
    """

    model_config = ConfigDict(
        from_attributes=True
    )

    id: int

    owner_id: int | None = None

    name: str

    model: str

    repository: str

    profile: str

    runtime: str

    deployment_mode: DeploymentMode

    status: DeploymentStatus

    endpoint: str | None = None

    model_artifact_reference: str | None = None

    model_artifact_digest: str | None = None

    created_at: datetime

    updated_at: datetime
