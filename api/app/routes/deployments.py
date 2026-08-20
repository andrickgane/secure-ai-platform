from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import (
    get_current_user,
)
from app.core.config import (
    Settings,
    get_settings,
)
from app.db.database import get_db
from app.models.user import User
from app.repositories.audit_repository import (
    AuditRepository,
)
from app.repositories.deployment_repository import (
    DeploymentAlreadyExists,
    DeploymentNotFound,
    DeploymentRepository,
    DeploymentRepositoryError,
)
from app.schemas.deployment import (
    DeploymentCreate,
    DeploymentRecord,
)
from app.services.catalog_service import (
    CatalogError,
    CatalogItemNotApproved,
    CatalogItemNotFound,
    CatalogService,
)
from app.services.deployment_service import (
    DeploymentService,
    DeploymentServiceError,
)
from app.services.kubernetes_service import (
    KubernetesService,
)
from app.services.runtime_activation_service import (
    RuntimeActivationError,
    RuntimeActivationService,
)
from app.services.runtime_selector_service import (
    RuntimeCompatibilityError,
    RuntimeSelectorService,
    RuntimeUnavailableError,
)
from app.services.trusted_model_service import (
    TrustedModelError,
    TrustedModelService,
)


router = APIRouter(
    prefix="/api/v1/deployments",
    tags=["deployments"],
)


def _is_admin(
    user: User,
) -> bool:
    return user.role in {
        "admin",
        "platform_admin",
    }


def _build_services(
    *,
    settings: Settings,
    db: Session,
) -> tuple[
    DeploymentService,
    KubernetesService,
    RuntimeActivationService,
]:

    catalog = CatalogService(
        settings.catalog_path
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
        model_puller_image=settings.model_promotion_image,
    )

    selector = RuntimeSelectorService(
        catalog=catalog,

        kubernetes=kubernetes,

        vllm_api_key=(
            settings.vllm_api_key
        ),
    )

    trusted = TrustedModelService(
        project_root=(
            settings.project_root
        ),

        registry_username=(
            settings.registry_username
            or None
        ),

        registry_password=(
            settings.registry_password
            or None
        ),

        registry_ca_file=(
            settings.registry_ca_file
        ),

        cosign_public_key=(
            settings.cosign_public_key
        ),

        allow_insecure_registry=(
            settings.registry_insecure
        ),

        registry_plain_http=(
            settings
            .registry_plain_http
        ),
    )

    deployment_service = (
        DeploymentService(
            catalog=catalog,

            trusted_models=trusted,

            runtime_selector=selector,

            db=db,
        )
    )

    activation = (
        RuntimeActivationService(
            namespace=(
                settings
                .kubernetes_namespace
            ),

            kubernetes_mode=(
                settings
                .kubernetes_mode
            ),

            image=(
                settings
                .runtime_activation_image
            ),
        )
    )

    return (
        deployment_service,
        kubernetes,
        activation,
    )


# ==========================================================
# CREATE
# ==========================================================


@router.post(
    "",
    response_model=(
        DeploymentRecord
    ),
    status_code=(
        status.HTTP_201_CREATED
    ),
)
def create_deployment(
    request: DeploymentCreate,

    # Kept for backward API compatibility.
    dry_run: bool = Query(
        default=False
    ),

    current_user: User = Depends(
        get_current_user
    ),

    settings: Settings = Depends(
        get_settings
    ),

    db: Session = Depends(
        get_db
    ),
) -> DeploymentRecord:

    (
        deployment_service,
        kubernetes,
        activation,
    ) = _build_services(
        settings=settings,
        db=db,
    )

    repository = (
        DeploymentRepository(
            db
        )
    )

    try:
        context = (
            deployment_service
            .create_context(
                request
            )
        )

        # ==================================================
        # EXTERNAL RUNTIME
        # ==================================================

        if (
            context.deployment_mode
            == "external"
        ):
            if not context.external_endpoint:
                raise DeploymentServiceError(
                    "External runtime has "
                    "no endpoint"
                )

            # Prevent simultaneous switching of
            # one native Metal runtime.
            busy = (
                db.execute(
                    text(
                        """
                        SELECT name
                        FROM deployments
                        WHERE runtime = :runtime
                          AND status = 'deploying'
                        LIMIT 1
                        """
                    ),
                    {
                        "runtime":
                            context.runtime,
                    },
                )
                .first()
            )

            if busy is not None:
                raise RuntimeActivationError(
                    "Another activation is "
                    "already running on "
                    f"'{context.runtime}'"
                )

            if dry_run:
                created = (
                    repository.create(
                        context,

                        owner_id=(
                            current_user.id
                        ),

                        status=(
                            "validated"
                        ),

                        endpoint=(
                            context
                            .external_endpoint
                        ),
                    )
                )

            else:
                created = (
                    repository.create(
                        context,

                        owner_id=(
                            current_user.id
                        ),

                        status=(
                            "deploying"
                        ),

                        endpoint=(
                            context
                            .external_endpoint
                        ),
                    )
                )

                try:
                    activation.submit_activation(
                        deployment_name=(
                            context.name
                        ),

                        model_id=(
                            context.model
                        ),

                        artifact_reference=(
                            context
                            .model_artifact_reference
                        ),

                        artifact_digest=(
                            context
                            .model_artifact_digest
                        ),

                        max_model_len=(
                            context
                            .max_model_len
                        ),

                        inference_endpoint=(
                            context
                            .external_endpoint
                        ),

                        runtime_name=(
                            context.runtime
                        ),
                    )

                except Exception:
                    repository.delete(
                        context.name
                    )
                    raise

        # ==================================================
        # KUBERNETES RUNTIME
        # ==================================================

        elif (
            context.deployment_mode
            == "kubernetes"
        ):
            if context.image is None:
                raise DeploymentServiceError(
                    "Kubernetes runtime "
                    "has no image"
                )

            if context.port is None:
                raise DeploymentServiceError(
                    "Kubernetes runtime "
                    "has no container port"
                )

            kwargs = {
                "name":
                    context.name,

                "image":
                    context.image,

                "repository":
                    context.repository,

                "served_model_name":
                    context.model,

                "model_artifact_reference":
                    context
                    .model_artifact_reference,

                "port":
                    context.port,

                "replicas":
                    context.replicas,

                "cpu_request":
                    context.cpu_request,

                "memory_request":
                    context.memory_request,

                "cpu_limit":
                    context.cpu_limit,

                "memory_limit":
                    context.memory_limit,

                "gpu_count":
                    context.gpu_count,

                "max_model_len":
                    context.max_model_len,

                "node_selector":
                    context.node_selector,

                "model_mount_path":
                    context
                    .model_cache_mount_path,

                "registry_secret_name":
                    "model-ingestion-secrets",

                "registry_insecure":
                    settings
                    .registry_insecure,

                "registry_plain_http":
                    settings
                    .registry_plain_http,

                "model_storage_size":
                    context
                    .model_cache_size,
            }

            if dry_run:
                (
                    kubernetes
                    .dry_run_ai_deployment(
                        **kwargs
                    )
                )

                created = (
                    repository.create(
                        context,

                        owner_id=(
                            current_user.id
                        ),

                        status=(
                            "validated"
                        ),

                        endpoint=None,
                    )
                )

            else:
                result = (
                    kubernetes
                    .create_ai_deployment(
                        **kwargs
                    )
                )

                created = (
                    repository.create(
                        context,

                        owner_id=(
                            current_user.id
                        ),

                        status="ready",

                        endpoint=(
                            result[
                                "endpoint"
                            ]
                        ),
                    )
                )

        else:
            raise DeploymentServiceError(
                "Unsupported deployment "
                f"mode "
                f"'{context.deployment_mode}'"
            )

        # ==================================================
        # AUDIT
        # ==================================================

        AuditRepository(
            db
        ).create(
            actor_user_id=(
                current_user.id
            ),

            action=(
                "CREATE_DEPLOYMENT"
            ),

            resource_type=(
                "deployment"
            ),

            resource_name=(
                created.name
            ),

            details={
                "deployment_id":
                    created.id,

                "model":
                    created.model,

                "profile":
                    created.profile,

                "runtime":
                    created.runtime,

                "runtime_capacity":
                    context
                    .max_model_len,

                "runtime_capacity_source": (
                    "deployment_override"
                    if (
                        request
                        .runtime_capacity
                        is not None
                    )
                    else "profile"
                ),

                "deployment_mode":
                    created
                    .deployment_mode,

                "status":
                    created.status,

                "dry_run":
                    dry_run,

                "artifact_digest":
                    context
                    .model_artifact_digest,

                "registry_insecure":
                    settings
                    .registry_insecure,

                "registry_plain_http":
                    settings
                    .registry_plain_http,
            },
        )

        return created

    except RuntimeCompatibilityError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except RuntimeUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except (
        DeploymentAlreadyExists,
        RuntimeActivationError,
    ) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except CatalogItemNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except (
        CatalogItemNotApproved,
        TrustedModelError,
    ) as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except (
        CatalogError,
        DeploymentServiceError,
        ValueError,
        KeyError,
        RuntimeError,
    ) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except DeploymentRepositoryError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ==========================================================
# LIST
# ==========================================================


@router.get(
    "",
    response_model=list[
        DeploymentRecord
    ],
)
def list_deployments(
    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
) -> list[DeploymentRecord]:

    repository = (
        DeploymentRepository(
            db
        )
    )

    if _is_admin(
        current_user
    ):
        return repository.list()

    return (
        repository
        .list_for_owner(
            current_user.id
        )
    )


# ==========================================================
# GET
# ==========================================================


@router.get(
    "/{name}",
    response_model=(
        DeploymentRecord
    ),
)
def get_deployment(
    name: str,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
) -> DeploymentRecord:

    repository = (
        DeploymentRepository(
            db
        )
    )

    try:
        if _is_admin(
            current_user
        ):
            return repository.get(
                name
            )

        return (
            repository
            .get_for_owner(
                name,
                current_user.id,
            )
        )

    except DeploymentNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


# ==========================================================
# DELETE
# ==========================================================


@router.delete(
    "/{name}",
    status_code=204,
)
def delete_deployment(
    name: str,

    current_user: User = Depends(
        get_current_user
    ),

    settings: Settings = Depends(
        get_settings
    ),

    db: Session = Depends(
        get_db
    ),
) -> Response:

    repository = (
        DeploymentRepository(
            db
        )
    )

    try:
        deployment = (
            repository.get(
                name
            )
            if _is_admin(
                current_user
            )
            else (
                repository
                .get_for_owner(
                    name,
                    current_user.id,
                )
            )
        )

        (
            _,
            kubernetes,
            activation,
        ) = _build_services(
            settings=settings,
            db=db,
        )

        if (
            deployment.deployment_mode
            == "external"
            and deployment.status
            == "ready"
        ):
            activation.submit_deactivation(
                model_id=(
                    deployment.model
                )
            )

        elif (
            deployment.deployment_mode
            == "kubernetes"
        ):
            kubernetes.delete_ai_deployment(
                name=(
                    deployment.name
                )
            )

        if _is_admin(
            current_user
        ):
            repository.delete(
                name
            )

        else:
            repository.delete_for_owner(
                name,
                current_user.id,
            )

        AuditRepository(
            db
        ).create(
            actor_user_id=(
                current_user.id
            ),

            action=(
                "DELETE_DEPLOYMENT"
            ),

            resource_type=(
                "deployment"
            ),

            resource_name=(
                deployment.name
            ),

            details={
                "deployment_id":
                    deployment.id,

                "model":
                    deployment.model,

                "profile":
                    deployment.profile,

                "runtime":
                    deployment.runtime,
            },
        )

        return Response(
            status_code=204
        )

    except DeploymentNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except (
        RuntimeActivationError,
        RuntimeError,
    ) as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except DeploymentRepositoryError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc
