from __future__ import annotations

import secrets

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import (
    Settings,
    get_settings,
)
from app.db.database import get_db


# ==========================================================
# INTERNAL SERVICE BOUNDARY
# ==========================================================
#
# Internal callbacks must arrive through the Kubernetes
# ClusterIP Service and must never be reachable through the
# public api.ai.local ingress.
#
# The runtime-activation worker currently calls:
#
#   ai-control-plane-internal.ai-system.svc.cluster.local:8080
#
# Keep this allowlist intentionally narrow and fail closed.
# ==========================================================

_INTERNAL_SERVICE_HOSTS = frozenset(
    {
        "ai-control-plane-internal",
        "ai-control-plane-internal.ai-system",
        "ai-control-plane-internal.ai-system.svc",
        (
            "ai-control-plane-internal."
            "ai-system.svc.cluster.local"
        ),
    }
)


def _require_internal_host(
    request: Request,
) -> None:
    raw_host = (
        request.headers.get("host") or ""
    ).strip().lower()

    host = raw_host

    if host.startswith("["):
        # IPv6 literals are deliberately not accepted by the
        # current internal callback architecture.
        host = ""
    elif ":" in host:
        host = host.split(":", 1)[0]

    host = host.rstrip(".")

    if host not in _INTERNAL_SERVICE_HOSTS:
        # Deliberately return 404 instead of revealing that an
        # internal-only endpoint exists.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found",
        )


router = APIRouter(
    prefix="/api/v1/internal/runtime",
    tags=["internal-runtime"],
    include_in_schema=False,
    dependencies=[
        Depends(_require_internal_host),
    ],
)


class RuntimeStatusUpdate(BaseModel):
    status: str = Field(
        pattern=r"^(ready|failed)$"
    )

    endpoint: str | None = None

    runtime: str = Field(
        min_length=1,
        max_length=64,
    )


def _normalize_endpoint(
    endpoint: str,
) -> str:
    return endpoint.strip().rstrip("/")


def _require_internal_token(
    x_internal_token: str | None = Header(
        default=None
    ),

    settings: Settings = Depends(
        get_settings
    ),
) -> None:

    expected = (
        settings.runtime_callback_token
    )

    if (
        not expected
        or len(expected) < 32
    ):
        raise HTTPException(
            status_code=(
                status
                .HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Runtime callback "
                "authentication is not "
                "configured"
            ),
        )

    if x_internal_token is None:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail="Unauthorized",
        )

    if not secrets.compare_digest(
        x_internal_token,
        expected,
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail="Unauthorized",
        )


@router.post(
    "/deployments/{deployment_name}/status"
)
def update_runtime_status(
    deployment_name: str,

    request: RuntimeStatusUpdate,

    _: None = Depends(
        _require_internal_token
    ),

    db: Session = Depends(
        get_db
    ),
) -> dict[str, str]:

    # ======================================================
    # LOAD DEPLOYMENT
    # ======================================================

    deployment = (
        db.execute(
            text(
                """
                SELECT
                    name,
                    runtime,
                    endpoint,
                    status
                FROM deployments
                WHERE name = :name
                """
            ),
            {
                "name":
                    deployment_name,
            },
        )
        .mappings()
        .first()
    )

    if deployment is None:
        raise HTTPException(
            status_code=404,

            detail=(
                f"Deployment "
                f"'{deployment_name}' "
                "does not exist"
            ),
        )

    # ======================================================
    # RUNTIME INTEGRITY
    # ======================================================

    existing_runtime = str(
        deployment["runtime"]
    )

    if (
        existing_runtime
        != request.runtime
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),

            detail=(
                "Runtime callback does "
                "not match deployment "
                "runtime"
            ),
        )

    # ======================================================
    # ENDPOINT INTEGRITY
    # ======================================================

    existing_endpoint = (
        deployment["endpoint"]
    )

    callback_endpoint = (
        request.endpoint
    )

    if (
        callback_endpoint
        and existing_endpoint
        and _normalize_endpoint(
            callback_endpoint
        )
        != _normalize_endpoint(
            str(existing_endpoint)
        )
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),

            detail=(
                "Runtime callback attempted "
                "to change the deployment "
                "endpoint"
            ),
        )

    effective_endpoint = (
        str(existing_endpoint)
        if existing_endpoint
        else callback_endpoint
    )

    if (
        request.status == "ready"
        and not effective_endpoint
    ):
        raise HTTPException(
            status_code=422,

            detail=(
                "A ready deployment "
                "must have an inference "
                "endpoint"
            ),
        )

    # ======================================================
    # SINGLE EXTERNAL RUNTIME MODEL
    # ======================================================
    #
    # Current architecture:
    #
    # one native Metal runtime process
    # => one active ready model.
    #
    # This remains compatible with the existing
    # vLLM Metal / llama.cpp activation model.
    # ======================================================

    try:
        if request.status == "ready":
            db.execute(
                text(
                    """
                    UPDATE deployments
                    SET status = 'stopped'
                    WHERE runtime = :runtime
                      AND name <> :name
                      AND status = 'ready'
                    """
                ),
                {
                    "runtime":
                        request.runtime,

                    "name":
                        deployment_name,
                },
            )

        result = db.execute(
            text(
                """
                UPDATE deployments
                SET
                    status = :status,
                    endpoint = COALESCE(
                        :endpoint,
                        endpoint
                    )
                WHERE name = :name
                  AND runtime = :runtime
                """
            ),
            {
                "status":
                    request.status,

                "endpoint":
                    effective_endpoint,

                "name":
                    deployment_name,

                "runtime":
                    request.runtime,
            },
        )

        if result.rowcount == 0:
            db.rollback()

            raise HTTPException(
                status_code=409,

                detail=(
                    "Deployment runtime "
                    "changed while callback "
                    "was being processed"
                ),
            )

        db.commit()

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,

            detail=(
                "Could not update runtime "
                "deployment status"
            ),
        ) from exc

    return {
        "deployment":
            deployment_name,

        "status":
            request.status,
    }
