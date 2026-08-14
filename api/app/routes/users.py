from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.core.auth import (
    require_admin,
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
from app.repositories.user_repository import (
    UserNotFound,
    UserRepository,
    UserRepositoryError,
)
from app.schemas.user import (
    UserCreateRequest,
    UserRecord,
    UserStatusUpdate,
)
from app.services.auth_service import (
    AuthService,
    UserAlreadyExists,
)


router = APIRouter(
    prefix="/api/v1/users",
    tags=["users"],
)


@router.get(
    "",
    response_model=list[UserRecord],
)
def list_users(
    current_user: User = Depends(
        require_admin
    ),

    db: Session = Depends(
        get_db
    ),
) -> list[UserRecord]:

    repository = UserRepository(
        db
    )

    return repository.list()


@router.post(
    "",
    response_model=UserRecord,
    status_code=(
        status.HTTP_201_CREATED
    ),
)
def create_user(
    request: UserCreateRequest,

    current_user: User = Depends(
        require_admin
    ),

    settings: Settings = Depends(
        get_settings
    ),

    db: Session = Depends(
        get_db
    ),
) -> UserRecord:

    # Only platform_admin can create
    # another platform_admin.
    if (
        request.role
        == "platform_admin"
        and current_user.role
        != "platform_admin"
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Only a platform administrator "
                "can create another "
                "platform administrator"
            ),
        )

    auth = AuthService(
        db,
        jwt_secret_key=(
            settings.jwt_secret_key
        ),
        jwt_algorithm=(
            settings.jwt_algorithm
        ),
        access_token_minutes=(
            settings
            .jwt_access_token_minutes
        ),
    )

    try:
        user = auth.create_user(
            email=str(
                request.email
            ),
            password=request.password,
            role=request.role,
        )

    except UserAlreadyExists as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    audit = AuditRepository(
        db
    )

    audit.create(
        actor_user_id=(
            current_user.id
        ),

        action="CREATE_USER",

        resource_type="user",

        resource_name=user.email,

        details={
            "user_id": user.id,
            "role": user.role,
        },
    )

    return UserRecord(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.patch(
    "/{user_id}/status",
    response_model=UserRecord,
)
def update_user_status(
    user_id: int,

    request: UserStatusUpdate,

    current_user: User = Depends(
        require_admin
    ),

    db: Session = Depends(
        get_db
    ),
) -> UserRecord:

    if (
        user_id == current_user.id
        and request.is_active is False
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "You cannot disable "
                "your own account"
            ),
        )

    repository = UserRepository(
        db
    )

    try:
        updated = (
            repository.update_status(
                user_id,
                is_active=(
                    request.is_active
                ),
            )
        )

    except UserNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except UserRepositoryError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    AuditRepository(
        db
    ).create(
        actor_user_id=(
            current_user.id
        ),

        action=(
            "ENABLE_USER"
            if request.is_active
            else "DISABLE_USER"
        ),

        resource_type="user",

        resource_name=(
            updated.email
        ),

        details={
            "user_id": updated.id,
        },
    )

    return updated
