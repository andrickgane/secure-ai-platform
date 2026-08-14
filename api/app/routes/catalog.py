from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.db.database import get_db
from app.models.model_request import ModelRequest
from app.models.user import User
from app.schemas.catalog import (
    ModelCatalogItem,
    ProfileCatalogItem,
    ProfileInference,
    ProfileLimits,
    ProfileSecurity,
    RuntimeCatalogItem,
)
from app.services.catalog_service import CatalogError, CatalogService


router = APIRouter(prefix="/api/v1", tags=["catalog"])


def _display_name_from_repository(repository: str) -> str:
    return repository.rsplit("/", 1)[-1].replace("-", " ").replace("_", " ")


@router.get("/models", response_model=list[ModelCatalogItem])
def list_models(
    response: Response,
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> list[ModelCatalogItem]:
    """
    Effective Web UI catalog.

    Published DB models override static catalog entries with the
    same ID. No rebuild is needed when a model becomes published.
    """
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

    catalog = CatalogService(settings.catalog_path)
    effective: dict[str, ModelCatalogItem] = {}

    for definition in catalog.list_models(approved_only=True):
        metadata = definition.get("metadata", {})
        spec = definition.get("spec", {})
        if not isinstance(metadata, dict) or not isinstance(spec, dict):
            continue

        model_id = metadata.get("name")
        if not model_id:
            continue

        security = spec.get("security", {})
        if not isinstance(security, dict):
            security = {}

        artifact = spec.get("artifact", {})
        if not isinstance(artifact, dict):
            artifact = {}

        artifact_digest = artifact.get("digest")
        registry = artifact.get("registry")
        oci_repository = artifact.get("repository")
        artifact_reference = None

        if (
            isinstance(registry, str)
            and registry
            and isinstance(oci_repository, str)
            and oci_repository
            and isinstance(artifact_digest, str)
            and artifact_digest
        ):
            artifact_reference = f"{registry}/{oci_repository}@{artifact_digest}"

        effective[str(model_id)] = ModelCatalogItem(
            id=str(model_id),
            display_name=str(spec.get("displayName", model_id)),
            description=spec.get("description"),
            capabilities=[str(x) for x in spec.get("capabilities", [])],
            default_profile=(
                str(spec["defaultProfile"]) if spec.get("defaultProfile") else None
            ),
            supported_runtimes=[
                str(x) for x in spec.get("supportedRuntimes", [])
            ],
            approved=security.get("approved") is True,
            source="static",
            provider=str(spec["provider"]) if spec.get("provider") else None,
            repository=(
                str(spec["repository"]) if spec.get("repository") else None
            ),
            revision=str(spec["revision"]) if spec.get("revision") else None,
            artifact_reference=artifact_reference,
            artifact_digest=(
                str(artifact_digest) if artifact_digest else None
            ),
        )

    statement = (
        select(ModelRequest)
        .where(ModelRequest.status == "published")
        .where(ModelRequest.catalog_model_id.is_not(None))
        .where(ModelRequest.artifact_reference.is_not(None))
        .where(ModelRequest.artifact_digest.is_not(None))
        .order_by(ModelRequest.updated_at.asc())
    )

    for item in db.execute(statement).scalars().all():
        model_id = item.catalog_model_id
        if not model_id:
            continue

        effective[model_id] = ModelCatalogItem(
            id=model_id,
            display_name=_display_name_from_repository(item.repository),
            description=(
                "Trusted model imported and published by the AI supply chain "
                f"from {item.repository}"
            ),
            capabilities=["chat", "text-generation"],
            default_profile=item.requested_profile or "interactive",
            supported_runtimes=["vllm-metal", "vllm-cuda"],
            approved=True,
            source="trusted-registry",
            provider=item.provider,
            repository=item.repository,
            revision=item.revision,
            artifact_reference=item.artifact_reference,
            artifact_digest=item.artifact_digest,
        )

    return list(effective.values())


@router.get("/profiles", response_model=list[ProfileCatalogItem])
def list_profiles(
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[ProfileCatalogItem]:
    catalog = CatalogService(settings.catalog_path)
    results: list[ProfileCatalogItem] = []

    try:
        for definition in catalog.list_profiles():
            metadata = definition.get("metadata", {})
            spec = definition.get("spec", {})
            profile_id = metadata.get("name")
            if not profile_id:
                continue

            defaults = spec.get("defaults", {})
            limits = spec.get("limits", {})
            resources = spec.get("resources", {})
            requests = resources.get("requests", {})
            resource_limits = resources.get("limits", {})
            temperature_limits = limits.get("temperature", {})
            top_p_limits = limits.get("topP", {})
            runtime_policy = spec.get("runtimePolicy", {})
            inference = spec.get("inference", {})
            concurrency = inference.get("concurrency", {})
            security = spec.get("security", {})

            results.append(
                ProfileCatalogItem(
                    id=profile_id,
                    display_name=spec.get("displayName", profile_id),
                    description=spec.get("description"),
                    category=spec.get("category", "general"),
                    max_model_len=int(defaults.get("maxModelLen", 4096)),
                    max_tokens=int(defaults.get("maxTokens", 512)),
                    temperature=float(defaults.get("temperature", 0.2)),
                    top_p=float(defaults.get("topP", 0.9)),
                    replicas=int(spec.get("replicas", 1)),
                    cpu_request=str(requests.get("cpu", "500m")),
                    memory_request=str(requests.get("memory", "1Gi")),
                    cpu_limit=str(resource_limits.get("cpu", "2")),
                    memory_limit=str(resource_limits.get("memory", "4Gi")),
                    allowed_runtimes=[
                        str(x)
                        for x in runtime_policy.get("allowedRuntimes", [])
                    ],
                    limits=ProfileLimits(
                        max_model_len=int(limits.get("maxModelLen", 8192)),
                        max_tokens=int(limits.get("maxTokens", 2048)),
                        temperature_min=float(
                            temperature_limits.get("min", 0.0)
                        ),
                        temperature_max=float(
                            temperature_limits.get("max", 1.0)
                        ),
                        top_p_min=float(top_p_limits.get("min", 0.1)),
                        top_p_max=float(top_p_limits.get("max", 1.0)),
                    ),
                    inference=ProfileInference(
                        streaming=inference.get("streaming", False) is True,
                        max_requests=int(concurrency.get("maxRequests", 1)),
                        timeout_seconds=int(
                            inference.get("timeoutSeconds", 120)
                        ),
                    ),
                    security=ProfileSecurity(
                        allow_user_overrides=(
                            security.get("allowUserOverrides", False) is True
                        ),
                        overridable_parameters=[
                            str(x)
                            for x in security.get("overridableParameters", [])
                        ],
                    ),
                )
            )
    except (CatalogError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return results


@router.get("/runtimes", response_model=list[RuntimeCatalogItem])
def list_runtimes(
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[RuntimeCatalogItem]:
    catalog = CatalogService(settings.catalog_path)
    results: list[RuntimeCatalogItem] = []

    for definition in catalog.list_runtimes():
        metadata = definition.get("metadata", {})
        spec = definition.get("spec", {})
        runtime_id = metadata.get("name")
        if not runtime_id:
            continue

        hardware = spec.get("hardware", {})
        if not isinstance(hardware, dict):
            hardware = {}

        results.append(
            RuntimeCatalogItem(
                id=runtime_id,
                display_name=spec.get("displayName", runtime_id),
                description=spec.get("description"),
                deployment_mode=spec.get("deploymentMode", "unknown"),
                accelerator=hardware.get("accelerator"),
                capabilities=[str(x) for x in spec.get("capabilities", [])],
            )
        )

    return results
