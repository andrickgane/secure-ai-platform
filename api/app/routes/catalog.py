from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import (
    get_current_user,
)
from app.core.config import (
    Settings,
    get_settings,
)
from app.db.database import get_db
from app.models.deployment import Deployment
from app.models.model_request import (
    ModelRequest,
)
from app.models.user import User
from app.schemas.catalog import (
    ModelCatalogItem,
    ProfileCatalogItem,
    ProfileInference,
    ProfileLimits,
    ProfileSecurity,
    RuntimeCatalogItem,
)
from app.services.catalog_service import (
    CatalogError,
    CatalogService,
)
from app.services.kubernetes_service import (
    KubernetesService,
)
from app.services.runtime_selector_service import (
    RuntimeSelectorService,
)
from app.services.trusted_model_service import (
    TrustedModelError,
    TrustedModelService,
)


router = APIRouter(
    prefix="/api/v1",
    tags=["catalog"],
)


# ============================================================
# HELPERS
# ============================================================


def _display_name_from_repository(
    repository: str,
) -> str:
    return (
        repository
        .rsplit("/", 1)[-1]
        .replace("-", " ")
        .replace("_", " ")
    )


# ============================================================
# MODELS
# ============================================================


@router.get(
    "/models",
    response_model=list[
        ModelCatalogItem
    ],
)
def list_models(
    response: Response,
    current_user: User = Depends(
        get_current_user
    ),
    settings: Settings = Depends(
        get_settings
    ),
    db: Session = Depends(
        get_db
    ),
) -> list[ModelCatalogItem]:
    """
    Effective Web UI model catalog.

    Published database models override static catalog
    entries with the same ID.
    """

    response.headers[
        "Cache-Control"
    ] = (
        "no-store, no-cache, "
        "must-revalidate"
    )

    catalog = CatalogService(
        settings.catalog_path
    )

    effective: dict[
        str,
        ModelCatalogItem,
    ] = {}

    # --------------------------------------------------------
    # Static catalog
    # --------------------------------------------------------

    for definition in (
        catalog.list_models(
            approved_only=True
        )
    ):
        metadata = definition.get(
            "metadata",
            {},
        )

        spec = definition.get(
            "spec",
            {},
        )

        if (
            not isinstance(
                metadata,
                dict,
            )
            or not isinstance(
                spec,
                dict,
            )
        ):
            continue

        model_id = metadata.get(
            "name"
        )

        if not model_id:
            continue

        security = spec.get(
            "security",
            {},
        )

        if not isinstance(
            security,
            dict,
        ):
            security = {}

        artifact = spec.get(
            "artifact",
            {},
        )

        if not isinstance(
            artifact,
            dict,
        ):
            artifact = {}

        artifact_digest = (
            artifact.get(
                "digest"
            )
        )

        registry = artifact.get(
            "registry"
        )

        oci_repository = (
            artifact.get(
                "repository"
            )
        )

        artifact_reference = None

        if (
            isinstance(
                registry,
                str,
            )
            and registry
            and isinstance(
                oci_repository,
                str,
            )
            and oci_repository
            and isinstance(
                artifact_digest,
                str,
            )
            and artifact_digest
        ):
            artifact_reference = (
                f"{registry}/"
                f"{oci_repository}"
                f"@{artifact_digest}"
            )

        effective[
            str(model_id)
        ] = ModelCatalogItem(
            id=str(
                model_id
            ),

            display_name=str(
                spec.get(
                    "displayName",
                    model_id,
                )
            ),

            description=(
                spec.get(
                    "description"
                )
            ),

            capabilities=[
                str(item)
                for item in spec.get(
                    "capabilities",
                    [],
                )
            ],

            default_profile=(
                str(
                    spec[
                        "defaultProfile"
                    ]
                )
                if spec.get(
                    "defaultProfile"
                )
                else None
            ),

            # Legacy static catalog declaration.
            supported_runtimes=[
                str(item)
                for item in spec.get(
                    "supportedRuntimes",
                    [],
                )
            ],

            approved=(
                security.get(
                    "approved"
                )
                is True
            ),

            source="static",

            provider=(
                str(
                    spec[
                        "provider"
                    ]
                )
                if spec.get(
                    "provider"
                )
                else None
            ),

            repository=(
                str(
                    spec[
                        "repository"
                    ]
                )
                if spec.get(
                    "repository"
                )
                else None
            ),

            revision=(
                str(
                    spec[
                        "revision"
                    ]
                )
                if spec.get(
                    "revision"
                )
                else None
            ),

            artifact_reference=(
                artifact_reference
            ),

            artifact_digest=(
                str(
                    artifact_digest
                )
                if artifact_digest
                else None
            ),
        )

    # --------------------------------------------------------
    # Dynamic trusted models
    # --------------------------------------------------------

    statement = (
        select(ModelRequest)
        .where(
            ModelRequest.status
            == "published"
        )
        .where(
            ModelRequest.catalog_model_id
            .is_not(None)
        )
        .where(
            ModelRequest.artifact_reference
            .is_not(None)
        )
        .where(
            ModelRequest.artifact_digest
            .is_not(None)
        )
        .order_by(
            ModelRequest.updated_at.asc()
        )
    )

    for item in (
        db.execute(
            statement
        )
        .scalars()
        .all()
    ):
        model_id = (
            item.catalog_model_id
        )

        if not model_id:
            continue

        effective[
            model_id
        ] = ModelCatalogItem(
            id=model_id,

            display_name=(
                _display_name_from_repository(
                    item.repository
                )
            ),

            description=(
                "Trusted model imported and "
                "published by the AI supply chain "
                f"from {item.repository}"
            ),

            capabilities=[
                "chat",
                "text-generation",
            ],

            default_profile=(
                item.requested_profile
                or "interactive"
            ),

            # Dynamic model compatibility is now calculated
            # from catalog/runtimes/*.yaml.
            supported_runtimes=[],

            approved=True,

            source=(
                "trusted-registry"
            ),

            provider=item.provider,

            repository=(
                item.repository
            ),

            revision=item.revision,

            artifact_reference=(
                item.artifact_reference
            ),

            artifact_digest=(
                item.artifact_digest
            ),
        )

    return list(
        effective.values()
    )


# ============================================================
# RUNTIME COMPATIBILITY MATRIX
# ============================================================


@router.get(
    "/models/{model_id}/runtime-compatibility"
)
def get_model_runtime_compatibility(
    model_id: str,
    profile: str | None = None,
    current_user: User = Depends(
        get_current_user
    ),
    settings: Settings = Depends(
        get_settings
    ),
    db: Session = Depends(
        get_db
    ),
) -> dict[str, object]:
    """
    Explain runtime compatibility and availability without
    deploying or activating a model.
    """

    catalog = CatalogService(
        settings.catalog_path
    )

    # --------------------------------------------------------
    # Dynamic model first
    # --------------------------------------------------------

    statement = (
        select(ModelRequest)
        .where(
            ModelRequest.catalog_model_id
            == model_id
        )
        .where(
            ModelRequest.status
            == "published"
        )
        .order_by(
            ModelRequest.updated_at.desc()
        )
        .limit(1)
    )

    model_request = (
        db.execute(
            statement
        )
        .scalars()
        .first()
    )

    if model_request is not None:
        model_spec: dict[
            str,
            object,
        ] = {
            "artifactFormat":
                model_request.artifact_format,

            "architecture":
                model_request.architecture,

            "quantization":
                model_request.quantization,

            "defaultProfile":
                model_request.requested_profile
                or "interactive",

            "supportedRuntimes": [],
        }

    # --------------------------------------------------------
    # Static catalog fallback
    # --------------------------------------------------------

    else:
        try:
            definition = (
                catalog.load_approved_model(
                    model_id
                )
            )

        except CatalogError as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code":
                        "MODEL_NOT_FOUND",

                    "message":
                        str(exc),
                },
            ) from exc

        raw_model_spec = (
            definition.get(
                "spec",
                {},
            )
        )

        if not isinstance(
            raw_model_spec,
            dict,
        ):
            raise HTTPException(
                status_code=500,
                detail={
                    "code":
                        "MODEL_SPEC_INVALID",

                    "message":
                        "Model definition "
                        "has an invalid spec.",
                },
            )

        model_spec = raw_model_spec

    profile_name = str(
        profile
        or model_spec.get(
            "defaultProfile"
        )
        or "interactive"
    )

    try:
        profile_definition = (
            catalog.load(
                "profiles",
                profile_name,
            )
        )

        profile_spec = (
            profile_definition.get(
                "spec",
                {},
            )
        )

        if not isinstance(
            profile_spec,
            dict,
        ):
            raise CatalogError(
                "Profile spec must "
                "be an object"
            )

        kubernetes = KubernetesService(
            namespace=(
                settings
                .kubernetes_namespace
            ),
            mode=(
                settings
                .kubernetes_mode
            ),
        )

        selector = (
            RuntimeSelectorService(
                catalog=catalog,
                kubernetes=kubernetes,
                vllm_api_key=(
                    settings.vllm_api_key
                ),
            )
        )

        result = (
            selector
            .inspect_compatibility(
                model_name=model_id,
                model_spec=model_spec,
                profile_spec=profile_spec,
            )
        )

    except CatalogError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code":
                    "RUNTIME_COMPATIBILITY_ERROR",

                "message":
                    str(exc),
            },
        ) from exc

    result["profile"] = (
        profile_name
    )

    return result


# ============================================================
# MODEL DELETE
# ============================================================


@router.delete(
    "/models/{model_id}",
    status_code=204,
)
def delete_model(
    model_id: str,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(
        get_db
    ),
) -> Response:
    """
    Remove a published trusted model.

    Static catalog models cannot be deleted through this
    endpoint.

    The OCI manifest is removed from the trusted registry.
    The ModelRequest record remains for audit history.
    """

    statement = (
        select(ModelRequest)
        .where(
            ModelRequest.catalog_model_id
            == model_id
        )
        .where(
            ModelRequest.status
            == "published"
        )
        .limit(1)
    )

    model_request = (
        db.execute(
            statement
        )
        .scalars()
        .first()
    )

    if model_request is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code":
                    "MODEL_NOT_FOUND",

                "message": (
                    "Published trusted model was "
                    "not found or is not managed "
                    "by the dynamic catalog."
                ),
            },
        )

    # --------------------------------------------------------
    # Prevent deletion while referenced
    # --------------------------------------------------------

    deployment_statement = (
        select(Deployment)
        .where(
            Deployment.model
            == model_id
        )
        .limit(1)
    )

    deployment = (
        db.execute(
            deployment_statement
        )
        .scalars()
        .first()
    )

    if deployment is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code":
                    "MODEL_IN_USE",

                "message": (
                    "Model cannot be deleted "
                    "while a deployment still "
                    "references it."
                ),

                "deployment":
                    deployment.name,
            },
        )

    artifact_reference = (
        model_request
        .artifact_reference
    )

    artifact_digest = (
        model_request
        .artifact_digest
    )

    if (
        not artifact_reference
        or not artifact_digest
        or "@"
        not in artifact_reference
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code":
                    "MODEL_ARTIFACT_INVALID",

                "message": (
                    "Published model does not "
                    "contain a valid immutable "
                    "OCI reference."
                ),
            },
        )

    (
        reference_without_digest,
        reference_digest,
    ) = artifact_reference.rsplit(
        "@",
        1,
    )

    if (
        reference_digest
        != artifact_digest
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code":
                    "MODEL_ARTIFACT_DIGEST_MISMATCH",

                "message": (
                    "Stored OCI reference and "
                    "artifact digest do not match."
                ),
            },
        )

    if (
        "/"
        not in reference_without_digest
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code":
                    "MODEL_ARTIFACT_INVALID",

                "message": (
                    "Stored OCI reference "
                    "does not contain a "
                    "registry repository."
                ),
            },
        )

    registry, repository = (
        reference_without_digest
        .split(
            "/",
            1,
        )
    )

    trusted_models = (
        TrustedModelService()
    )

    try:
        trusted_models.delete_manifest(
            registry=registry,
            repository=repository,
            digest=artifact_digest,
        )

    except TrustedModelError as exc:
        db.rollback()

        raise HTTPException(
            status_code=502,
            detail={
                "code":
                    "TRUSTED_REGISTRY_DELETE_FAILED",

                "message":
                    str(exc),
            },
        ) from exc

    model_request.status = (
        "deleted"
    )

    model_request.status_message = (
        "Trusted model removed from "
        "active catalog and OCI registry."
    )

    db.commit()

    return Response(
        status_code=204
    )


# ============================================================
# PROFILES
# ============================================================


@router.get(
    "/profiles/builtin",
    response_model=list[
        ProfileCatalogItem
    ],
)
def list_profiles(
    current_user: User = Depends(
        get_current_user
    ),
    settings: Settings = Depends(
        get_settings
    ),
) -> list[ProfileCatalogItem]:
    catalog = CatalogService(
        settings.catalog_path
    )

    results: list[
        ProfileCatalogItem
    ] = []

    try:
        for definition in (
            catalog.list_profiles()
        ):
            metadata = definition.get(
                "metadata",
                {},
            )

            spec = definition.get(
                "spec",
                {},
            )

            if (
                not isinstance(
                    metadata,
                    dict,
                )
                or not isinstance(
                    spec,
                    dict,
                )
            ):
                continue

            profile_id = (
                metadata.get(
                    "name"
                )
            )

            if not profile_id:
                continue

            defaults = spec.get(
                "defaults",
                {},
            )

            limits = spec.get(
                "limits",
                {},
            )

            resources = spec.get(
                "resources",
                {},
            )

            runtime_policy = spec.get(
                "runtimePolicy",
                {},
            )

            inference = spec.get(
                "inference",
                {},
            )

            security = spec.get(
                "security",
                {},
            )

            if not isinstance(
                defaults,
                dict,
            ):
                defaults = {}

            if not isinstance(
                limits,
                dict,
            ):
                limits = {}

            if not isinstance(
                resources,
                dict,
            ):
                resources = {}

            if not isinstance(
                runtime_policy,
                dict,
            ):
                runtime_policy = {}

            if not isinstance(
                inference,
                dict,
            ):
                inference = {}

            if not isinstance(
                security,
                dict,
            ):
                security = {}

            requests = resources.get(
                "requests",
                {},
            )

            resource_limits = (
                resources.get(
                    "limits",
                    {},
                )
            )

            temperature_limits = (
                limits.get(
                    "temperature",
                    {},
                )
            )

            top_p_limits = limits.get(
                "topP",
                {},
            )

            concurrency = inference.get(
                "concurrency",
                {},
            )

            if not isinstance(
                requests,
                dict,
            ):
                requests = {}

            if not isinstance(
                resource_limits,
                dict,
            ):
                resource_limits = {}

            if not isinstance(
                temperature_limits,
                dict,
            ):
                temperature_limits = {}

            if not isinstance(
                top_p_limits,
                dict,
            ):
                top_p_limits = {}

            if not isinstance(
                concurrency,
                dict,
            ):
                concurrency = {}

            results.append(
                ProfileCatalogItem(
                    id=str(
                        profile_id
                    ),

                    display_name=str(
                        spec.get(
                            "displayName",
                            profile_id,
                        )
                    ),

                    description=(
                        spec.get(
                            "description"
                        )
                    ),

                    category=str(
                        spec.get(
                            "category",
                            "general",
                        )
                    ),

                    max_model_len=int(
                        defaults.get(
                            "maxModelLen",
                            4096,
                        )
                    ),

                    max_tokens=int(
                        defaults.get(
                            "maxTokens",
                            512,
                        )
                    ),

                    temperature=float(
                        defaults.get(
                            "temperature",
                            0.2,
                        )
                    ),

                    top_p=float(
                        defaults.get(
                            "topP",
                            0.9,
                        )
                    ),

                    replicas=int(
                        spec.get(
                            "replicas",
                            1,
                        )
                    ),

                    cpu_request=str(
                        requests.get(
                            "cpu",
                            "500m",
                        )
                    ),

                    memory_request=str(
                        requests.get(
                            "memory",
                            "1Gi",
                        )
                    ),

                    cpu_limit=str(
                        resource_limits.get(
                            "cpu",
                            "2",
                        )
                    ),

                    memory_limit=str(
                        resource_limits.get(
                            "memory",
                            "4Gi",
                        )
                    ),

                    allowed_runtimes=[
                        str(item)
                        for item in (
                            runtime_policy.get(
                                "allowedRuntimes",
                                [],
                            )
                        )
                    ],

                    limits=ProfileLimits(
                        max_model_len=int(
                            limits.get(
                                "maxModelLen",
                                8192,
                            )
                        ),

                        max_tokens=int(
                            limits.get(
                                "maxTokens",
                                2048,
                            )
                        ),

                        temperature_min=float(
                            temperature_limits.get(
                                "min",
                                0.0,
                            )
                        ),

                        temperature_max=float(
                            temperature_limits.get(
                                "max",
                                1.0,
                            )
                        ),

                        top_p_min=float(
                            top_p_limits.get(
                                "min",
                                0.1,
                            )
                        ),

                        top_p_max=float(
                            top_p_limits.get(
                                "max",
                                1.0,
                            )
                        ),
                    ),

                    inference=ProfileInference(
                        streaming=(
                            inference.get(
                                "streaming",
                                False,
                            )
                            is True
                        ),

                        max_requests=int(
                            concurrency.get(
                                "maxRequests",
                                1,
                            )
                        ),

                        timeout_seconds=int(
                            inference.get(
                                "timeoutSeconds",
                                120,
                            )
                        ),
                    ),

                    security=ProfileSecurity(
                        allow_user_overrides=(
                            security.get(
                                "allowUserOverrides",
                                False,
                            )
                            is True
                        ),

                        overridable_parameters=[
                            str(item)
                            for item in (
                                security.get(
                                    "overridableParameters",
                                    [],
                                )
                            )
                        ],
                    ),
                )
            )

    except (
        CatalogError,
        TypeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    return results


# ============================================================
# RUNTIMES
# ============================================================


@router.get(
    "/runtimes",
    response_model=list[
        RuntimeCatalogItem
    ],
)
def list_runtimes(
    current_user: User = Depends(
        get_current_user
    ),
    settings: Settings = Depends(
        get_settings
    ),
) -> list[RuntimeCatalogItem]:
    catalog = CatalogService(
        settings.catalog_path
    )

    results: list[
        RuntimeCatalogItem
    ] = []

    for definition in (
        catalog.list_runtimes()
    ):
        metadata = definition.get(
            "metadata",
            {},
        )

        spec = definition.get(
            "spec",
            {},
        )

        if (
            not isinstance(
                metadata,
                dict,
            )
            or not isinstance(
                spec,
                dict,
            )
        ):
            continue

        runtime_id = metadata.get(
            "name"
        )

        if not runtime_id:
            continue

        hardware = spec.get(
            "hardware",
            {},
        )

        if not isinstance(
            hardware,
            dict,
        ):
            hardware = {}

        results.append(
            RuntimeCatalogItem(
                id=str(
                    runtime_id
                ),

                display_name=str(
                    spec.get(
                        "displayName",
                        runtime_id,
                    )
                ),

                description=(
                    spec.get(
                        "description"
                    )
                ),

                deployment_mode=str(
                    spec.get(
                        "deploymentMode",
                        "unknown",
                    )
                ),

                accelerator=(
                    str(
                        hardware[
                            "accelerator"
                        ]
                    )
                    if hardware.get(
                        "accelerator"
                    )
                    else None
                ),

                capabilities=[
                    str(item)
                    for item in spec.get(
                        "capabilities",
                        [],
                    )
                ],
            )
        )

    return results
