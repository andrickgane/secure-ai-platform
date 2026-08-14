from __future__ import annotations

from fastapi import FastAPI

from app.routes import audit
from app.routes import auth
from app.routes import catalog
from app.routes import dashboard
from app.routes import deployments
from app.routes import health
from app.routes import inference
from app.routes import internal_runtime
from app.routes import model_requests
from app.routes import users


app = FastAPI(
    title="AI Control Plane",
    description=(
        "Secure AI platform control plane for trusted model management, "
        "workload profiles, runtime orchestration, inference and auditing."
    ),
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(model_requests.router)
app.include_router(deployments.router)
app.include_router(inference.router)
app.include_router(users.router)
app.include_router(audit.router)
app.include_router(dashboard.router)
app.include_router(internal_runtime.router)
