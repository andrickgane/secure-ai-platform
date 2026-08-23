from __future__ import annotations

import hmac

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Response,
    status,
)
from sqlalchemy import (
    BigInteger,
    Float,
    cast,
    func,
    select,
)
from sqlalchemy.orm import Session

from app.core.config import (
    Settings,
    get_settings,
)
from app.db.database import get_db
from app.models.audit_event import (
    AuditEvent,
)
from app.models.deployment import (
    Deployment,
)


router = APIRouter(
    tags=["observability"],
    include_in_schema=False,
)


# ==========================================================
# AUTHENTICATION
# ==========================================================


def _require_metrics_token(
    authorization: str | None = Header(
        default=None
    ),
    settings: Settings = Depends(
        get_settings
    ),
) -> None:
    """
    Protect Prometheus metrics with the existing
    internal runtime callback credential.

    The ServiceMonitor obtains the same token from
    runtime-callback-secret inside ai-system.

    This prevents /metrics from becoming an
    unauthenticated public endpoint through api.ai.local.
    """

    expected = (
        settings.runtime_callback_token
    )

    if not expected:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Metrics authentication "
                "is not configured"
            ),
        )

    prefix = "Bearer "

    if (
        not authorization
        or not authorization.startswith(
            prefix
        )
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail="Unauthorized",
            headers={
                "WWW-Authenticate": (
                    "Bearer"
                ),
            },
        )

    supplied = authorization[
        len(prefix):
    ]

    if not hmac.compare_digest(
        supplied,
        expected,
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail="Unauthorized",
            headers={
                "WWW-Authenticate": (
                    "Bearer"
                ),
            },
        )


# ==========================================================
# PROMETHEUS HELPERS
# ==========================================================


def _escape_label(
    value: object,
) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace('"', '\\"')
    )


def _labels(
    **values: object,
) -> str:
    rendered = ",".join(
        (
            f'{key}="'
            f'{_escape_label(value)}'
            f'"'
        )
        for key, value
        in values.items()
    )

    return (
        "{"
        + rendered
        + "}"
    )


def _json_bigint(
    key: str,
):
    return cast(
        func.coalesce(
            func.nullif(
                AuditEvent
                .details[key]
                .as_string(),
                "",
            ),
            "0",
        ),
        BigInteger,
    )


def _json_float(
    key: str,
):
    return cast(
        func.nullif(
            AuditEvent
            .details[key]
            .as_string(),
            "",
        ),
        Float,
    )


# ==========================================================
# METRICS
# ==========================================================


@router.get(
    "/metrics",
    dependencies=[
        Depends(
            _require_metrics_token
        ),
    ],
)
def metrics(
    db: Session = Depends(
        get_db
    ),
) -> Response:
    """
    Prometheus text exposition endpoint.

    Metrics are calculated from PostgreSQL rather than
    process-local counters. This is deliberate because
    the Control Plane currently runs multiple Uvicorn
    workers.

    PostgreSQL therefore remains the single source of
    truth and no prometheus-client multiprocess state
    is required.
    """

    lines: list[str] = []

    # ======================================================
    # PLATFORM
    # ======================================================

    lines.extend(
        [
            (
                "# HELP "
                "plateform_ai_control_plane_info "
                "Plateform AI Control Plane information."
            ),
            (
                "# TYPE "
                "plateform_ai_control_plane_info "
                "gauge"
            ),
            (
                "plateform_ai_control_plane_info "
                "1"
            ),
        ]
    )

    # ======================================================
    # DEPLOYMENTS
    # ======================================================

    deployments = (
        db.execute(
            select(
                Deployment.name,
                Deployment.runtime,
                Deployment.status,
                Deployment.deployment_mode,
            )
            .order_by(
                Deployment.name
            )
        )
        .all()
    )

    lines.extend(
        [
            (
                "# HELP "
                "plateform_ai_deployment_info "
                "Current deployment state."
            ),
            (
                "# TYPE "
                "plateform_ai_deployment_info "
                "gauge"
            ),
        ]
    )

    for (
        name,
        runtime,
        deployment_status,
        deployment_mode,
    ) in deployments:
        lines.append(
            (
                "plateform_ai_deployment_info"
                + _labels(
                    name=name,
                    runtime=runtime,
                    status=(
                        deployment_status
                    ),
                    mode=deployment_mode,
                )
                + " 1"
            )
        )

    deployment_counts = (
        db.execute(
            select(
                Deployment.runtime,
                Deployment.status,
                Deployment.deployment_mode,
                func.count(
                    Deployment.id
                ),
            )
            .group_by(
                Deployment.runtime,
                Deployment.status,
                Deployment.deployment_mode,
            )
            .order_by(
                Deployment.runtime,
                Deployment.status,
                Deployment.deployment_mode,
            )
        )
        .all()
    )

    lines.extend(
        [
            (
                "# HELP "
                "plateform_ai_deployments "
                "Number of deployments by "
                "runtime, status and mode."
            ),
            (
                "# TYPE "
                "plateform_ai_deployments "
                "gauge"
            ),
        ]
    )

    for (
        runtime,
        deployment_status,
        deployment_mode,
        count,
    ) in deployment_counts:
        lines.append(
            (
                "plateform_ai_deployments"
                + _labels(
                    runtime=runtime,
                    status=(
                        deployment_status
                    ),
                    mode=deployment_mode,
                )
                + f" {int(count)}"
            )
        )

    # ======================================================
    # INFERENCE
    # ======================================================

    runtime_expr = (
        AuditEvent
        .details["runtime"]
        .as_string()
    )

    prompt_tokens_expr = (
        _json_bigint(
            "prompt_tokens"
        )
    )

    completion_tokens_expr = (
        _json_bigint(
            "completion_tokens"
        )
    )

    total_tokens_expr = (
        _json_bigint(
            "total_tokens"
        )
    )

    inference_rows = (
        db.execute(
            select(
                AuditEvent.action,
                runtime_expr,
                func.count(
                    AuditEvent.id
                ),
                func.sum(
                    prompt_tokens_expr
                ),
                func.sum(
                    completion_tokens_expr
                ),
                func.sum(
                    total_tokens_expr
                ),
            )
            .where(
                AuditEvent.action.in_(
                    (
                        "CHAT_COMPLETION",
                        "CHAT_COMPLETION_STREAM",
                    )
                )
            )
            .group_by(
                AuditEvent.action,
                runtime_expr,
            )
            .order_by(
                AuditEvent.action,
                runtime_expr,
            )
        )
        .all()
    )

    lines.extend(
        [
            (
                "# HELP "
                "plateform_ai_inference_requests_total "
                "Completed inference requests."
            ),
            (
                "# TYPE "
                "plateform_ai_inference_requests_total "
                "counter"
            ),
            (
                "# HELP "
                "plateform_ai_prompt_tokens_total "
                "Prompt tokens processed."
            ),
            (
                "# TYPE "
                "plateform_ai_prompt_tokens_total "
                "counter"
            ),
            (
                "# HELP "
                "plateform_ai_completion_tokens_total "
                "Completion tokens generated."
            ),
            (
                "# TYPE "
                "plateform_ai_completion_tokens_total "
                "counter"
            ),
            (
                "# HELP "
                "plateform_ai_tokens_total "
                "Total tokens processed."
            ),
            (
                "# TYPE "
                "plateform_ai_tokens_total "
                "counter"
            ),
        ]
    )

    for (
        action,
        runtime,
        request_count,
        prompt_tokens,
        completion_tokens,
        total_tokens,
    ) in inference_rows:
        runtime_name = (
            runtime or "unknown"
        )

        streaming = (
            "true"
            if action
            == "CHAT_COMPLETION_STREAM"
            else "false"
        )

        metric_labels = _labels(
            runtime=runtime_name,
            streaming=streaming,
        )

        lines.append(
            (
                "plateform_ai_inference_requests_total"
                + metric_labels
                + f" {int(request_count or 0)}"
            )
        )

        lines.append(
            (
                "plateform_ai_prompt_tokens_total"
                + metric_labels
                + f" {int(prompt_tokens or 0)}"
            )
        )

        lines.append(
            (
                "plateform_ai_completion_tokens_total"
                + metric_labels
                + f" {int(completion_tokens or 0)}"
            )
        )

        lines.append(
            (
                "plateform_ai_tokens_total"
                + metric_labels
                + f" {int(total_tokens or 0)}"
            )
        )

    # ======================================================
    # STREAM PERFORMANCE
    # ======================================================

    latency_expr = _json_bigint(
        "latency_ms"
    )

    ttft_expr = _json_bigint(
        "first_token_latency_ms"
    )

    generation_rate_expr = (
        _json_float(
            "generation_tokens_per_second"
        )
    )

    output_rate_expr = (
        _json_float(
            "output_tokens_per_second"
        )
    )

    stream_rows = (
        db.execute(
            select(
                runtime_expr,
                func.count(
                    AuditEvent.id
                ),
                func.sum(
                    latency_expr
                ),
                func.sum(
                    ttft_expr
                ),
                func.avg(
                    generation_rate_expr
                ),
                func.avg(
                    output_rate_expr
                ),
            )
            .where(
                AuditEvent.action
                == "CHAT_COMPLETION_STREAM"
            )
            .group_by(
                runtime_expr
            )
            .order_by(
                runtime_expr
            )
        )
        .all()
    )

    lines.extend(
        [
            (
                "# HELP "
                "plateform_ai_stream_latency_milliseconds_sum "
                "Total streaming inference latency."
            ),
            (
                "# TYPE "
                "plateform_ai_stream_latency_milliseconds_sum "
                "counter"
            ),
            (
                "# HELP "
                "plateform_ai_stream_latency_milliseconds_count "
                "Number of streaming latency observations."
            ),
            (
                "# TYPE "
                "plateform_ai_stream_latency_milliseconds_count "
                "counter"
            ),
            (
                "# HELP "
                "plateform_ai_stream_ttft_milliseconds_sum "
                "Total first-token latency."
            ),
            (
                "# TYPE "
                "plateform_ai_stream_ttft_milliseconds_sum "
                "counter"
            ),
            (
                "# HELP "
                "plateform_ai_stream_ttft_milliseconds_count "
                "Number of first-token latency observations."
            ),
            (
                "# TYPE "
                "plateform_ai_stream_ttft_milliseconds_count "
                "counter"
            ),
            (
                "# HELP "
                "plateform_ai_generation_tokens_per_second "
                "Average runtime generation throughput."
            ),
            (
                "# TYPE "
                "plateform_ai_generation_tokens_per_second "
                "gauge"
            ),
            (
                "# HELP "
                "plateform_ai_output_tokens_per_second "
                "Average end-to-end output throughput."
            ),
            (
                "# TYPE "
                "plateform_ai_output_tokens_per_second "
                "gauge"
            ),
        ]
    )

    for (
        runtime,
        observation_count,
        latency_sum,
        ttft_sum,
        generation_rate,
        output_rate,
    ) in stream_rows:
        metric_labels = _labels(
            runtime=(
                runtime
                or "unknown"
            )
        )

        count = int(
            observation_count
            or 0
        )

        lines.append(
            (
                "plateform_ai_stream_latency_milliseconds_sum"
                + metric_labels
                + f" {int(latency_sum or 0)}"
            )
        )

        lines.append(
            (
                "plateform_ai_stream_latency_milliseconds_count"
                + metric_labels
                + f" {count}"
            )
        )

        lines.append(
            (
                "plateform_ai_stream_ttft_milliseconds_sum"
                + metric_labels
                + f" {int(ttft_sum or 0)}"
            )
        )

        lines.append(
            (
                "plateform_ai_stream_ttft_milliseconds_count"
                + metric_labels
                + f" {count}"
            )
        )

        lines.append(
            (
                "plateform_ai_generation_tokens_per_second"
                + metric_labels
                + " "
                + str(
                    float(
                        generation_rate
                        or 0.0
                    )
                )
            )
        )

        lines.append(
            (
                "plateform_ai_output_tokens_per_second"
                + metric_labels
                + " "
                + str(
                    float(
                        output_rate
                        or 0.0
                    )
                )
            )
        )

    body = (
        "\n".join(lines)
        + "\n"
    )

    return Response(
        content=body,
        media_type=(
            "text/plain; "
            "version=0.0.4; "
            "charset=utf-8"
        ),
    )
