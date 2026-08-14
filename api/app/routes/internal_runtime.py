from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import get_db


router = APIRouter(
    prefix="/api/v1/internal/runtime",
    tags=["internal-runtime"],
    include_in_schema=False,
)


class RuntimeStatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(ready|failed)$")
    endpoint: str | None = None
    runtime: str


def _require_internal_token(
    x_internal_token: str | None = Header(default=None),
) -> None:
    expected = os.getenv("ACP_RUNTIME_CALLBACK_TOKEN")
    if not expected or x_internal_token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/deployments/{deployment_name}/status")
def update_runtime_status(
    deployment_name: str,
    request: RuntimeStatusUpdate,
    _: None = Depends(_require_internal_token),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    # One native Metal vLLM process => one active ready model.
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
            {"runtime": request.runtime, "name": deployment_name},
        )

    result = db.execute(
        text(
            """
            UPDATE deployments
            SET status = :status,
                endpoint = COALESCE(:endpoint, endpoint)
            WHERE name = :name
            """
        ),
        {
            "status": request.status,
            "endpoint": request.endpoint,
            "name": deployment_name,
        },
    )

    if result.rowcount == 0:
        db.rollback()
        raise HTTPException(
            status_code=404,
            detail=f"Deployment '{deployment_name}' does not exist",
        )

    db.commit()
    return {"deployment": deployment_name, "status": request.status}
