from __future__ import annotations

import asyncio
from contextlib import (
    asynccontextmanager,
    suppress,
)

from fastapi import (
    FastAPI,
    Request,
)

from app.core.config import (
    get_settings,
)
from app.routes import audit
from app.routes import auth
from app.routes import catalog
from app.routes import conversations
from app.routes import dashboard
from app.routes import deployments
from app.routes import health
from app.routes import inference
from app.routes import inference_stream
from app.routes import internal_runtime
from app.routes import metrics
from app.routes import model_requests
from app.routes import profile_clones
from app.routes import profiles
from app.routes import users
from app.services.runtime_reconciliation_service import (
    RuntimeReconciliationService,
)


settings = get_settings()


# ==========================================================
# LIFESPAN
# ==========================================================


@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    del app

    reconciliation_task = (
        asyncio.create_task(
            RuntimeReconciliationService
            .run_forever(
                settings=settings,
                interval_seconds=15,
            )
        )
    )

    try:
        yield

    finally:
        reconciliation_task.cancel()

        with suppress(
            asyncio.CancelledError
        ):
            await reconciliation_task


# ==========================================================
# FASTAPI
# ==========================================================


app = FastAPI(
    title=settings.app_name,

    description=(
        "Secure AI platform control plane "
        "for trusted model management, "
        "workload profiles, runtime "
        "orchestration, inference "
        "and auditing."
    ),

    version="1.2.0",

    debug=settings.debug,

    docs_url=(
        "/docs"
        if settings.expose_api_docs
        else None
    ),

    redoc_url=(
        "/redoc"
        if settings.expose_api_docs
        else None
    ),

    openapi_url=(
        "/openapi.json"
        if settings.expose_api_docs
        else None
    ),

    lifespan=lifespan,
)


# ==========================================================
# SECURITY HEADERS
# ==========================================================


@app.middleware("http")
async def add_security_headers(
    request: Request,
    call_next,
):
    response = await call_next(
        request
    )

    if (
        settings
        .security_headers_enabled
    ):
        response.headers.setdefault(
            "X-Content-Type-Options",
            "nosniff",
        )

        response.headers.setdefault(
            "X-Frame-Options",
            "DENY",
        )

        response.headers.setdefault(
            "Referrer-Policy",
            "no-referrer",
        )

        response.headers.setdefault(
            "Permissions-Policy",
            (
                "camera=(), "
                "microphone=(), "
                "geolocation=(), "
                "payment=(), "
                "usb=()"
            ),
        )

        response.headers.setdefault(
            "Cross-Origin-Opener-Policy",
            "same-origin",
        )

        response.headers.setdefault(
            "Cross-Origin-Resource-Policy",
            "same-origin",
        )

        if (
            request.url.path
            .startswith(
                "/api/"
            )
            or request.url.path
            == "/metrics"
        ):
            response.headers.setdefault(
                "Cache-Control",
                "no-store",
            )

        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security",
                (
                    "max-age=31536000; "
                    "includeSubDomains"
                ),
            )

    return response


# ==========================================================
# ROUTERS
# ==========================================================


app.include_router(
    health.router
)

app.include_router(
    metrics.router
)

app.include_router(
    auth.router
)

app.include_router(
    catalog.router
)

app.include_router(
    conversations.router
)

app.include_router(
    model_requests.router
)


# ==========================================================
# PROFILE MANAGEMENT
# ==========================================================


app.include_router(
    profiles.router
)

app.include_router(
    profile_clones.router
)

app.include_router(
    deployments.router
)

app.include_router(
    inference.router
)

app.include_router(
    inference_stream.router
)

app.include_router(
    users.router
)

app.include_router(
    audit.router
)

app.include_router(
    dashboard.router
)

app.include_router(
    internal_runtime.router
)


# ==========================================================
# FRONTEND
# ==========================================================


from app.frontend import (
    mount_frontend,
)

mount_frontend(
    app
)
