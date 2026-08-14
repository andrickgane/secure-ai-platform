from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


# ==========================================================
# PROJECT PATHS
# ==========================================================

#
# config.py
# └── core/
#     └── app/
#         └── api/
#             └── PROJECT_ROOT
#

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

API_ROOT = (
    PROJECT_ROOT
    / "api"
)


# ==========================================================
# SETTINGS
# ==========================================================


class Settings(BaseSettings):
    """
    AI Control Plane configuration.

    Environment variables use the ACP_ prefix.

    Example:

        ACP_API_KEY=...
        ACP_DATABASE_URL=...
        ACP_VLLM_API_KEY=...
    """

    model_config = SettingsConfigDict(
        env_prefix="ACP_",

        env_file=(
            PROJECT_ROOT / ".env",
            API_ROOT / ".env",
        ),

        env_file_encoding="utf-8",

        case_sensitive=False,

        extra="ignore",
    )

    # ======================================================
    # APPLICATION
    # ======================================================

    app_name: str = (
        "AI Control Plane"
    )

    environment: str = (
        "development"
    )

    debug: bool = False

    # ======================================================
    # PROJECT PATHS
    # ======================================================

    project_root: Path = (
        PROJECT_ROOT
    )

    catalog_path: Path = (
        PROJECT_ROOT
        / "catalog"
    )

    # ======================================================
    # CONTROL PLANE API
    # ======================================================

    api_key: str = Field(
        default=(
            "dev-control-plane-key-2026"
        ),
        min_length=8,
    )

    # ======================================================
    # PostgreSQL
    # ======================================================

    database_url: str = Field(
        default=(
            "postgresql+psycopg://"
            "ai_platform:"
            "CHANGE_ME@"
            "127.0.0.1:"
            "5432/"
            "ai_platform"
        )
    )

    # ======================================================
    # JWT AUTHENTICATION
    # ======================================================

    jwt_secret_key: str = Field(
        default=(
            "CHANGE_ME_WITH_A_LONG_RANDOM_SECRET"
        ),
        min_length=32,
    )

    jwt_algorithm: str = (
        "HS256"
    )

    jwt_access_token_minutes: int = Field(
        default=60,
        ge=1,
        le=1440,
    )

    # ======================================================
    # vLLM
    # ======================================================

    vllm_api_key: str = Field(
        default="",
    )

    # ======================================================
    # OCI / ZOT REGISTRY
    # ======================================================

    registry_username: str = (
        ""
    )

    registry_password: str = (
        ""
    )

    registry_insecure: bool = (
        False
    )

    # ======================================================
    # KUBERNETES
    # ======================================================

    kubernetes_namespace: str = (
        "ai-workloads"
    )

    kubernetes_mode: str = (
        "kubeconfig"
    )


# ==========================================================
# SETTINGS SINGLETON
# ==========================================================


@lru_cache
def get_settings() -> Settings:
    return Settings()
