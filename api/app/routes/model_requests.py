from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_admin
from app.core.config import Settings, get_settings
from app.db.database import get_db
from app.models.user import User

from app.repositories.audit_repository import AuditRepository
from app.repositories.model_request_repository import (
    ModelRequestNotFound,
    ModelRequestRepository,
    ModelRequestRepositoryError,
)

from app.schemas.model_request import (
    ModelImportRequest,
    ModelRequestRecord,
    ModelRequestStatusUpdate,
)

from app.services.model_ingestion_service import (
    ModelIngestionError,
    ModelIngestionJobAlreadyExists,
    ModelIngestionService,
)

from app.services.model_promotion_service import (
    ModelPromotionError,
    ModelPromotionJobAlreadyExists,
    ModelPromotionService,
)


router = APIRouter(
    prefix="/api/v1/model-requests",
    tags=["model-management"],
)


# ============================================================
# AUTHORIZATION
# ============================================================


def require_platform_admin(
    current_user: User = Depends(require_admin),
) -> User:
    """
    Restrict model-management operations to platform admins.
    """
    return current_user


# ============================================================
# CREATE MODEL REQUEST
# ============================================================


@router.post(
    "",
    response_model=ModelRequestRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_model_request(
    payload: ModelImportRequest,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> ModelRequestRecord:
    """
    Create a model import request.

    This operation only registers the request.
    It does not download the model.
    """

    repository = ModelRequestRepository(db)

    try:
        model_request = repository.create(
            provider=payload.provider,
            repository=payload.repository,
            revision=payload.revision,
            requested_profile=payload.requested_profile,
            purpose=payload.purpose,
            requested_by_user_id=current_user.id,
        )

    except ModelRequestRepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    AuditRepository(db).create(
        actor_user_id=current_user.id,
        action="CREATE_MODEL_REQUEST",
        resource_type="model_request",
        resource_name=payload.repository,
        details={
            "request_id": model_request.id,
            "provider": payload.provider,
            "repository": payload.repository,
            "revision": payload.revision,
            "requested_profile": payload.requested_profile,
            "purpose": payload.purpose,
        },
    )

    return model_request


# ============================================================
# LIST MODEL REQUESTS
# ============================================================


@router.get(
    "",
    response_model=list[ModelRequestRecord],
)
def list_model_requests(
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> list[ModelRequestRecord]:
    """
    List all model import requests.
    """

    del current_user

    repository = ModelRequestRepository(db)

    try:
        return repository.list()

    except ModelRequestRepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


# ============================================================
# GET MODEL REQUEST
# ============================================================


@router.get(
    "/{request_id}",
    response_model=ModelRequestRecord,
)
def get_model_request(
    request_id: int,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> ModelRequestRecord:
    """
    Return one model import request.
    """

    del current_user

    repository = ModelRequestRepository(db)

    try:
        return repository.get(request_id)

    except ModelRequestNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except ModelRequestRepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


# ============================================================
# UPDATE MODEL REQUEST STATUS
# ============================================================


@router.patch(
    "/{request_id}/status",
    response_model=ModelRequestRecord,
)
def update_model_request_status(
    request_id: int,
    payload: ModelRequestStatusUpdate,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> ModelRequestRecord:
    """
    Administrative model-request status update.
    """

    repository = ModelRequestRepository(db)

    try:
        model_request = repository.update_status(
            request_id,
            status=payload.status,
            message=payload.status_message,
        )

    except ModelRequestNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except ModelRequestRepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    AuditRepository(db).create(
        actor_user_id=current_user.id,
        action="UPDATE_MODEL_REQUEST_STATUS",
        resource_type="model_request",
        resource_name=model_request.repository,
        details={
            "request_id": request_id,
            "status": payload.status,
            "status_message": payload.status_message,
        },
    )

    return model_request


# ============================================================
# INGEST MODEL
# ============================================================


@router.post(
    "/{request_id}/ingest",
    status_code=status.HTTP_202_ACCEPTED,
)
def ingest_model_request(
    request_id: int,
    current_user: User = Depends(require_platform_admin),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict:
    """
    Start the Kubernetes model-ingestion Job.

    Lifecycle:

        pending
          |
          v
        quarantined
          |
          v
        scanning
          |
          +------> rejected
          |
          v
        approved
    """

    repository = ModelRequestRepository(db)

    # --------------------------------------------------------
    # LOAD REQUEST
    # --------------------------------------------------------

    try:
        model_request = repository.get(request_id)

    except ModelRequestNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except ModelRequestRepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    # --------------------------------------------------------
    # STATE GATE
    # --------------------------------------------------------

    allowed_statuses = {
        "pending",
        "rejected",
        "failed",
    }

    if model_request.status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Model request cannot be ingested "
                f"from status '{model_request.status}'"
            ),
        )

    # --------------------------------------------------------
    # INGESTION SERVICE
    # --------------------------------------------------------

    ingestion = ModelIngestionService(
        namespace=settings.kubernetes_namespace,
        kubernetes_mode=settings.kubernetes_mode,
        ingestion_image=(
            "registry.secure-ai.local:5000/"
            "ai-platform/model-ingestion:v1.0.0"
        ),
        ingestion_secret_name="model-ingestion-secrets",
        workspace_pvc_name="model-ingestion-workspace",
        image_pull_secret_name="zot-regcred",
    )

    # --------------------------------------------------------
    # CREATE JOB
    # --------------------------------------------------------

    try:
        job = ingestion.create_job(
            request_id=model_request.id,
            provider=model_request.provider,
            repository=model_request.repository,
            revision=model_request.revision,
        )

    except ModelIngestionJobAlreadyExists as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except ModelIngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    # --------------------------------------------------------
    # UPDATE STATUS
    # --------------------------------------------------------

    try:
        repository.update_status(
            request_id,
            status="quarantined",
            message="Model ingestion Kubernetes Job submitted",
        )

    except ModelRequestRepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    # --------------------------------------------------------
    # AUDIT
    # --------------------------------------------------------

    AuditRepository(db).create(
        actor_user_id=current_user.id,
        action="START_MODEL_INGESTION",
        resource_type="model_request",
        resource_name=model_request.repository,
        details={
            "request_id": request_id,
            "provider": model_request.provider,
            "repository": model_request.repository,
            "revision": model_request.revision,
            "job_name": job["job_name"],
            "namespace": job["namespace"],
        },
    )

    return {
        "request_id": request_id,
        "status": "quarantined",
        "job": job,
    }


# ============================================================
# PROMOTE MODEL
# ============================================================


@router.post(
    "/{request_id}/promote",
    status_code=status.HTTP_202_ACCEPTED,
)
def promote_model_request(
    request_id: int,
    current_user: User = Depends(require_platform_admin),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict:
    """
    Promote an approved model from quarantine into the
    trusted OCI model registry.

    Lifecycle:

        approved
          |
          v
        promoting
          |
          v
        OCI package creation
          |
          v
        ORAS push
          |
          v
        Cosign signature
          |
          v
        published

    The promotion worker uses the internal Kubernetes
    Zot service:

        zot.registry.svc.cluster.local:5000

    This avoids sending large model blobs through
    ingress-nginx.
    """

    repository = ModelRequestRepository(db)

    # --------------------------------------------------------
    # LOAD REQUEST
    # --------------------------------------------------------

    try:
        model_request = repository.get(request_id)

    except ModelRequestNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except ModelRequestRepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    # --------------------------------------------------------
    # SECURITY STATE GATE
    # --------------------------------------------------------

    if model_request.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Model request cannot be promoted "
                f"from status '{model_request.status}'"
            ),
        )

    # --------------------------------------------------------
    # REQUIRE IMMUTABLE REVISION
    # --------------------------------------------------------

    if not model_request.revision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Model request has no resolved "
                "immutable revision"
            ),
        )

    # --------------------------------------------------------
    # PROMOTION SERVICE
    # --------------------------------------------------------

    promotion = ModelPromotionService(
        namespace=settings.kubernetes_namespace,
        kubernetes_mode=settings.kubernetes_mode,

        promotion_image=(
            "registry.secure-ai.local:5000/"
            "ai-platform/model-promotion:v1.0.3"
        ),

        ingestion_secret_name="model-ingestion-secrets",

        signing_secret_name="model-signing-key",

        workspace_pvc_name="model-ingestion-workspace",

        image_pull_secret_name="zot-regcred",
    )

    # --------------------------------------------------------
    # CREATE PROMOTION JOB
    # --------------------------------------------------------

    try:
        job = promotion.create_job(
            request_id=model_request.id,
            repository=model_request.repository,
            revision=model_request.revision,
        )

    except ModelPromotionJobAlreadyExists as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except ModelPromotionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    # --------------------------------------------------------
    # UPDATE DATABASE STATUS
    # --------------------------------------------------------

    try:
        repository.update_status(
            request_id,
            status="promoting",
            message=(
                "Trusted OCI promotion "
                "Kubernetes Job submitted"
            ),
        )

    except ModelRequestRepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    # --------------------------------------------------------
    # AUDIT
    # --------------------------------------------------------

    AuditRepository(db).create(
        actor_user_id=current_user.id,

        action="START_MODEL_PROMOTION",

        resource_type="model_request",

        resource_name=model_request.repository,

        details={
            "request_id": request_id,
            "repository": model_request.repository,
            "revision": model_request.revision,

            "promotion_image": (
                "registry.secure-ai.local:5000/"
                "ai-platform/model-promotion:v1.0.3"
            ),

            "registry": (
                "zot.registry.svc.cluster.local:5000"
            ),

            "job_name": job["job_name"],
            "namespace": job["namespace"],
        },
    )

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return {
        "request_id": request_id,
        "status": "promoting",
        "job": job,
    }
