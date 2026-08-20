from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


# ==========================================================
# PROJECT PATHS
# ==========================================================

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

    Security policy:

    - development/kubernetes lab environments may use
      explicitly configured insecure registry settings.
    - production forbids insecure/plain HTTP registries.
    - production forbids default development secrets.
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

    docs_enabled: bool = True

    security_headers_enabled: bool = True

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
    # POSTGRESQL
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

    jwt_algorithm: Literal[
        "HS256"
    ] = "HS256"

    jwt_access_token_minutes: int = Field(
        default=60,
        ge=1,
        le=1440,
    )

    jwt_issuer: str = (
        "plateform-ai-control-plane"
    )

    jwt_audience: str = (
        "plateform-ai"
    )

    jwt_leeway_seconds: int = Field(
        default=10,
        ge=0,
        le=120,
    )

    # ======================================================
    # INTERNAL RUNTIME CALLBACK
    # ======================================================

    runtime_callback_token: str = ""

    # ======================================================
    # INFERENCE RUNTIMES
    # ======================================================

    vllm_api_key: str = Field(
        default="",
    )

    llama_cpp_api_key: str = Field(
        default="",
    )

    # ======================================================
    # OCI / ZOT REGISTRY
    # ======================================================

    registry_username: str = ""

    registry_password: str = ""

    registry_insecure: bool = False

    registry_plain_http: bool = False

    registry_ca_file: Path | None = None

    cosign_public_key: Path | None = None

    # ======================================================
    # PLATFORM WORKER IMAGES
    # ======================================================

    model_ingestion_image: str = (
        "registry.andrick.local:31039/"
        "ai-platform/model-ingestion:v2.1.0-dev.2"
    )

    model_promotion_image: str = (
        "registry.andrick.local:31039/"
        "ai-platform/model-promotion:v2.1.0-dev.5"
    )

    runtime_activation_image: str = (
        "registry.andrick.local:31039/"
        "ai-platform/runtime-activation:v2.1.0-dev.7"
    )

    # ======================================================
    # KUBERNETES
    # ======================================================

    kubernetes_namespace: str = (
        "ai-workloads"
    )

    kubernetes_mode: Literal[
        "kubeconfig",
        "incluster",
    ] = "kubeconfig"

    # ======================================================
    # ENVIRONMENT HELPERS
    # ======================================================

    @property
    def is_production(
        self,
    ) -> bool:
        return (
            self.environment
            .strip()
            .lower()
            in {
                "production",
                "prod",
            }
        )

    @property
    def expose_api_docs(
        self,
    ) -> bool:
        return (
            self.docs_enabled
            and not self.is_production
        )

    # ======================================================
    # SECURITY VALIDATION
    # ======================================================

    @model_validator(
        mode="after"
    )
    def validate_security_configuration(
        self,
    ) -> "Settings":

        if not self.is_production:
            return self

        errors: list[str] = []

        if self.debug:
            errors.append(
                "ACP_DEBUG must be false "
                "in production"
            )

        if (
            self.api_key
            == "dev-control-plane-key-2026"
            or len(self.api_key) < 32
        ):
            errors.append(
                "ACP_API_KEY must contain "
                "a production secret of at "
                "least 32 characters"
            )

        if (
            "CHANGE_ME"
            in self.jwt_secret_key
            or len(
                self.jwt_secret_key
            ) < 48
        ):
            errors.append(
                "ACP_JWT_SECRET_KEY must "
                "contain a production secret "
                "of at least 48 characters"
            )

        if len(
            self.runtime_callback_token
        ) < 32:
            errors.append(
                "ACP_RUNTIME_CALLBACK_TOKEN "
                "must contain at least "
                "32 characters"
            )

        if (
            "CHANGE_ME"
            in self.database_url
        ):
            errors.append(
                "ACP_DATABASE_URL contains "
                "a default password"
            )

        if self.registry_insecure:
            errors.append(
                "ACP_REGISTRY_INSECURE "
                "cannot be enabled "
                "in production"
            )

        if self.registry_plain_http:
            errors.append(
                "ACP_REGISTRY_PLAIN_HTTP "
                "cannot be enabled "
                "in production"
            )

        if errors:
            raise ValueError(
                "Unsafe production "
                "configuration:\n- "
                + "\n- ".join(
                    errors
                )
            )

        return self


# ==========================================================
# SETTINGS SINGLETON
# ==========================================================


@lru_cache
def get_settings() -> Settings:
    return Settings()
