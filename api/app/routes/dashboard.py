from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
)
from sqlalchemy.orm import Session

from app.core.auth import (
    require_admin,
)
from app.db.database import get_db
from app.models.user import User
from app.schemas.dashboard import (
    DashboardSummary,
)
from app.services.dashboard_service import (
    DashboardService,
)


router = APIRouter(
    prefix="/api/v1/dashboard",
    tags=["dashboard"],
)


@router.get(
    "/summary",
    response_model=DashboardSummary,
)
def dashboard_summary(
    current_user: User = Depends(
        require_admin
    ),

    db: Session = Depends(
        get_db
    ),
) -> DashboardSummary:

    service = DashboardService(
        db
    )

    return service.summary()
