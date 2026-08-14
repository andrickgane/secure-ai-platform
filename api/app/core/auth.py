from __future__ import annotations

import jwt
from fastapi import (
    Depends,
    HTTPException,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.orm import Session

from app.core.config import (
    Settings,
    get_settings,
)
from app.db.database import get_db
from app.models.user import User


bearer_scheme = HTTPBearer(
    auto_error=False
)


def get_current_user(
    credentials: (
        HTTPAuthorizationCredentials
        | None
    ) = Depends(
        bearer_scheme
    ),

    settings: Settings = Depends(
        get_settings
    ),

    db: Session = Depends(
        get_db
    ),
) -> User:

    if credentials is None:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Authentication required"
            ),
        )

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[
                settings.jwt_algorithm
            ],
        )

    except jwt.ExpiredSignatureError as exc:

        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Access token expired"
            ),
        ) from exc

    except jwt.InvalidTokenError as exc:

        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Invalid access token"
            ),
        ) from exc

    user_id = payload.get(
        "sub"
    )

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail=(
                "Invalid access token"
            ),
        )

    try:
        user_id_int = int(
            user_id
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail=(
                "Invalid access token"
            ),
        ) from exc

    user = db.get(
        User,
        user_id_int,
    )

    if (
        user is None
        or not user.is_active
    ):
        raise HTTPException(
            status_code=401,
            detail=(
                "User is not active"
            ),
        )

    return user


def require_admin(
    user: User = Depends(
        get_current_user
    ),
) -> User:

    if user.role not in {
        "admin",
        "platform_admin",
    }:

        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "Administrator role required"
            ),
        )

    return user


def require_platform_admin(
    user: User = Depends(
        get_current_user
    ),
) -> User:

    if (
        user.role
        != "platform_admin"
    ):

        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "Platform administrator "
                "role required"
            ),
        )

    return user
