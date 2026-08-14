from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
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
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import (
    AuthService,
    InvalidCredentials,
    UserDisabled,
)


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["auth"],
)


# ==========================================================
# LOGIN
# ==========================================================


@router.post(
    "/login",
    response_model=(
        TokenResponse
    ),
)
def login(
    request: LoginRequest,

    settings: Settings = Depends(
        get_settings
    ),

    db: Session = Depends(
        get_db
    ),
) -> TokenResponse:

    service = AuthService(
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
        user = service.authenticate(
            email=request.email,
            password=request.password,
        )

    except (
        InvalidCredentials,
        UserDisabled,
    ) as exc:

        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=str(exc),
        ) from exc

    token, expires_in = (
        service.create_access_token(
            user
        )
    )

    # ======================================================
    # AUDIT LOGIN
    # ======================================================

    AuditRepository(
        db
    ).create(
        actor_user_id=(
            user.id
        ),

        action="LOGIN",

        resource_type="user",

        resource_name=(
            user.email
        ),

        details={
            "role": (
                user.role
            ),
        },
    )

    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
    )


# ==========================================================
# CURRENT USER
# ==========================================================


@router.get(
    "/me",
    response_model=(
        UserResponse
    ),
)
def current_user(
    user: User = Depends(
        get_current_user
    ),
) -> UserResponse:

    return UserResponse(
        id=user.id,

        email=user.email,

        role=user.role,

        is_active=(
            user.is_active
        ),
    )
