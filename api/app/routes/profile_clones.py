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
from app.models.profile import Profile
from app.models.user import User
from app.repositories.profile_repository import (
    ProfileAlreadyExists,
    ProfileNotFound,
    ProfileRepositoryError,
)
from app.schemas.profile import (
    CustomProfileCreate,
    CustomProfileRecord,
)
from app.schemas.profile_clone import (
    ProfileCloneRequest,
)
from app.services.catalog_service import (
    CatalogService,
)
from app.services.profile_engine_service import (
    BuiltinProfileImmutable,
    ProfileDefinitionInvalid,
    ProfileEngineError,
    ProfileEngineService,
    ProfileInheritanceError,
)


router = APIRouter(
    prefix="/api/v1/profiles",
    tags=["profile-management"],
)


def _require_platform_admin(
    current_user: User,
) -> None:
    if (
        current_user.role
        != "platform_admin"
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Platform administrator "
                "role required"
            ),
        )


def _record(
    profile: Profile,
) -> CustomProfileRecord:
    return CustomProfileRecord(
        id=profile.id,

        name=profile.name,

        display_name=(
            profile.display_name
        ),

        description=(
            profile.description
        ),

        category=(
            profile.category
        ),

        base_profile=(
            profile.base_profile
        ),

        overrides=(
            profile.overrides
        ),

        owner_id=(
            profile.owner_id
        ),

        created_at=(
            profile.created_at
        ),

        updated_at=(
            profile.updated_at
        ),
    )


def _handle_error(
    exc: Exception,
) -> None:
    if isinstance(
        exc,
        ProfileNotFound,
    ):
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    if isinstance(
        exc,
        (
            ProfileAlreadyExists,
            BuiltinProfileImmutable,
        ),
    ):
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    if isinstance(
        exc,
        (
            ProfileDefinitionInvalid,
            ProfileInheritanceError,
        ),
    ):
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    if isinstance(
        exc,
        (
            ProfileRepositoryError,
            ProfileEngineError,
        ),
    ):
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    raise exc


@router.post(
    "/{profile_id}/clone",
    response_model=(
        CustomProfileRecord
    ),
    status_code=(
        status.HTTP_201_CREATED
    ),
)
def clone_profile(
    profile_id: str,

    payload: ProfileCloneRequest,

    current_user: User = Depends(
        get_current_user
    ),

    settings: Settings = Depends(
        get_settings
    ),

    db: Session = Depends(
        get_db
    ),
) -> CustomProfileRecord:
    """
    Clone a built-in or custom profile.

    The source profile becomes the base profile.
    Only the supplied overrides are stored.
    """

    _require_platform_admin(
        current_user
    )

    catalog = CatalogService(
        settings.catalog_path
    )

    engine = ProfileEngineService(
        catalog=catalog,
        db=db,
    )

    try:
        (
            source_definition,
            _,
            _,
        ) = (
            engine.resolve_with_metadata(
                profile_id
            )
        )

        source_spec = (
            source_definition.get(
                "spec",
                {},
            )
        )

        if not isinstance(
            source_spec,
            dict,
        ):
            raise ProfileDefinitionInvalid(
                f"Source profile "
                f"'{profile_id}' "
                "has invalid spec"
            )

        source_display_name = str(
            source_spec.get(
                "displayName",
                profile_id,
            )
        )

        source_category = str(
            source_spec.get(
                "category",
                "custom",
            )
        )

        display_name = (
            payload.display_name
            or (
                source_display_name
                + " Clone"
            )
        )

        category = (
            payload.category
            or source_category
        )

        profile = engine.create(
            payload=CustomProfileCreate(
                name=payload.name,

                display_name=(
                    display_name
                ),

                description=(
                    payload.description
                ),

                category=category,

                base_profile=(
                    profile_id
                ),

                overrides=(
                    payload.overrides
                ),
            ),

            owner_id=(
                current_user.id
            ),
        )

        return _record(
            profile
        )

    except Exception as exc:
        _handle_error(
            exc
        )

        raise
