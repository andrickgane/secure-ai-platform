from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    Query,
)
from sqlalchemy.orm import Session

from app.core.auth import (
    get_current_user,
)
from app.db.database import get_db
from app.models.user import User
from app.repositories.audit_repository import (
    AuditRepository,
)
from app.schemas.audit import (
    AuditEventRecord,
)


router = APIRouter(
    prefix="/api/v1/audit",
    tags=["audit"],
)


@router.get(
    "",
    response_model=list[
        AuditEventRecord
    ],
)
def list_audit_events(
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
) -> list[AuditEventRecord]:

    repository = AuditRepository(
        db
    )

    if current_user.role in {
        "admin",
        "platform_admin",
    }:
        return repository.list(
            limit=limit
        )

    return repository.list_for_user(
        current_user.id,
        limit=limit,
    )
