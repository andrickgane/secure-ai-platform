from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import (
    get_current_user,
)
from app.core.config import (
    Settings,
    get_settings,
)
from app.db.database import get_db
from app.models.deployment import Deployment
from app.models.profile import Profile
from app.models.user import User
from app.repositories.profile_repository import (
    ProfileAlreadyExists,
    ProfileNotFound,
    ProfileRepositoryError,
)
from app.schemas.catalog import (
    ProfileCatalogItem,
    ProfileInference,
    ProfileLimits,
    ProfileSecurity,
)
from app.schemas.profile import (
    CustomProfileCreate,
    CustomProfileRecord,
    CustomProfileUpdate,
    EffectiveProfileResponse,
)
from app.services.catalog_service import (
    CatalogError,
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


# ==========================================================
# RBAC
# ==========================================================


def _require_platform_admin(
    current_user: User,
) -> None:
    if (
        current_user.role
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


# ==========================================================
# SERVICES
# ==========================================================


def _engine(
    *,
    settings: Settings,
    db: Session,
) -> ProfileEngineService:
    return ProfileEngineService(
        catalog=CatalogService(
            settings.catalog_path
        ),
        db=db,
    )


# ==========================================================
# CUSTOM RECORD MAPPING
# ==========================================================


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


# ==========================================================
# EFFECTIVE PROFILE -> CATALOG MAPPING
# ==========================================================


def _dict(
    value: Any,
) -> dict[str, Any]:
    if isinstance(
        value,
        dict,
    ):
        return value

    return {}


def _string_list(
    value: Any,
) -> list[str]:
    if not isinstance(
        value,
        list,
    ):
        return []

    return [
        str(item)
        for item in value
        if isinstance(
            item,
            str,
        )
        and item
    ]


def _catalog_item(
    *,
    definition: dict[str, Any],
    source: str,
    immutable: bool,
    base_profile: str | None,
) -> ProfileCatalogItem:
    metadata = _dict(
        definition.get(
            "metadata"
        )
    )

    spec = _dict(
        definition.get(
            "spec"
        )
    )

    profile_id = str(
        metadata.get(
            "name",
            "",
        )
    )

    if not profile_id:
        raise ProfileDefinitionInvalid(
            "Profile metadata.name "
            "is required"
        )

    defaults = _dict(
        spec.get(
            "defaults"
        )
    )

    limits = _dict(
        spec.get(
            "limits"
        )
    )

    resources = _dict(
        spec.get(
            "resources"
        )
    )

    requests = _dict(
        resources.get(
            "requests"
        )
    )

    resource_limits = _dict(
        resources.get(
            "limits"
        )
    )

    runtime_policy = _dict(
        spec.get(
            "runtimePolicy"
        )
    )

    inference = _dict(
        spec.get(
            "inference"
        )
    )

    concurrency = _dict(
        inference.get(
            "concurrency"
        )
    )

    security = _dict(
        spec.get(
            "security"
        )
    )

    temperature_limits = _dict(
        limits.get(
            "temperature"
        )
    )

    top_p_limits = _dict(
        limits.get(
            "topP"
        )
    )

    return ProfileCatalogItem(
        id=profile_id,

        display_name=str(
            spec.get(
                "displayName",
                profile_id,
            )
        ),

        description=(
            str(
                spec.get(
                    "description"
                )
            )
            if spec.get(
                "description"
            )
            is not None
            else None
        ),

        category=str(
            spec.get(
                "category",
                "general",
            )
        ),

        source=source,

        immutable=immutable,

        base_profile=(
            base_profile
        ),

        max_model_len=int(
            defaults.get(
                "maxModelLen",
                4096,
            )
        ),

        max_tokens=int(
            defaults.get(
                "maxTokens",
                512,
            )
        ),

        temperature=float(
            defaults.get(
                "temperature",
                0.2,
            )
        ),

        top_p=float(
            defaults.get(
                "topP",
                0.9,
            )
        ),

        replicas=int(
            spec.get(
                "replicas",
                1,
            )
        ),

        cpu_request=str(
            requests.get(
                "cpu",
                "500m",
            )
        ),

        memory_request=str(
            requests.get(
                "memory",
                "1Gi",
            )
        ),

        cpu_limit=str(
            resource_limits.get(
                "cpu",
                "2",
            )
        ),

        memory_limit=str(
            resource_limits.get(
                "memory",
                "4Gi",
            )
        ),

        allowed_runtimes=(
            _string_list(
                runtime_policy.get(
                    "allowedRuntimes"
                )
            )
        ),

        preferred_runtimes=(
            _string_list(
                runtime_policy.get(
                    "preferredRuntimes"
                )
            )
        ),

        limits=ProfileLimits(
            max_model_len=int(
                limits.get(
                    "maxModelLen",
                    defaults.get(
                        "maxModelLen",
                        4096,
                    ),
                )
            ),

            max_tokens=int(
                limits.get(
                    "maxTokens",
                    defaults.get(
                        "maxTokens",
                        512,
                    ),
                )
            ),

            temperature_min=float(
                temperature_limits.get(
                    "min",
                    0.0,
                )
            ),

            temperature_max=float(
                temperature_limits.get(
                    "max",
                    1.0,
                )
            ),

            top_p_min=float(
                top_p_limits.get(
                    "min",
                    0.0,
                )
            ),

            top_p_max=float(
                top_p_limits.get(
                    "max",
                    1.0,
                )
            ),
        ),

        inference=(
            ProfileInference(
                streaming=(
                    inference.get(
                        "streaming",
                        False,
                    )
                    is True
                ),

                max_requests=int(
                    concurrency.get(
                        "maxRequests",
                        1,
                    )
                ),

                timeout_seconds=int(
                    inference.get(
                        "timeoutSeconds",
                        120,
                    )
                ),
            )
        ),

        security=(
            ProfileSecurity(
                allow_user_overrides=(
                    security.get(
                        "allowUserOverrides",
                        False,
                    )
                    is True
                ),

                overridable_parameters=(
                    _string_list(
                        security.get(
                            "overridableParameters"
                        )
                    )
                ),
            )
        ),
    )


# ==========================================================
# DEPLOYMENT USAGE
# ==========================================================


def _deployment_names_using_profile(
    *,
    db: Session,
    profile_id: str,
) -> list[str]:
    statement = (
        select(
            Deployment.name
        )
        .where(
            Deployment.profile
            == profile_id
        )
        .order_by(
            Deployment.created_at.asc()
        )
    )

    return list(
        db.execute(
            statement
        )
        .scalars()
        .all()
    )


# ==========================================================
# ERRORS
# ==========================================================


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
        ProfileAlreadyExists,
    ):
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    if isinstance(
        exc,
        BuiltinProfileImmutable,
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
            CatalogError,
        ),
    ):
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    raise exc


# ==========================================================
# UNIFIED CATALOG
# ==========================================================


@router.get(
    "",
    response_model=list[
        ProfileCatalogItem
    ],
)
def list_profiles(
    current_user: User = Depends(
        get_current_user
    ),
    settings: Settings = Depends(
        get_settings
    ),
    db: Session = Depends(
        get_db
    ),
) -> list[ProfileCatalogItem]:
    """
    Unified effective profile catalog.

    Returns:
    - built-in YAML profiles
    - custom PostgreSQL profiles

    Custom profiles are returned after inheritance
    has been resolved.
    """

    engine = _engine(
        settings=settings,
        db=db,
    )

    catalog = engine.catalog

    results: list[
        ProfileCatalogItem
    ] = []

    try:
        # --------------------------------------------------
        # BUILT-IN
        # --------------------------------------------------

        for definition in (
            catalog.list_profiles()
        ):
            results.append(
                _catalog_item(
                    definition=definition,
                    source="builtin",
                    immutable=True,
                    base_profile=None,
                )
            )

        # --------------------------------------------------
        # CUSTOM
        # --------------------------------------------------

        for profile in (
            engine.list_custom()
        ):
            definition = (
                engine.resolve(
                    profile.name
                )
            )

            results.append(
                _catalog_item(
                    definition=(
                        definition
                    ),
                    source="custom",
                    immutable=False,
                    base_profile=(
                        profile.base_profile
                    ),
                )
            )

        # Built-ins first, then custom;
        # alphabetical inside each group.
        results.sort(
            key=lambda item: (
                0
                if item.source
                == "builtin"
                else 1,
                item.id,
            )
        )

        return results

    except Exception as exc:
        _handle_error(
            exc
        )

        raise


# ==========================================================
# CREATE CUSTOM PROFILE
# ==========================================================


@router.post(
    "",
    response_model=(
        CustomProfileRecord
    ),
    status_code=(
        status.HTTP_201_CREATED
    ),
)
def create_profile(
    payload: CustomProfileCreate,

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
    _require_platform_admin(
        current_user
    )

    engine = _engine(
        settings=settings,
        db=db,
    )

    try:
        profile = engine.create(
            payload=payload,
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


# ==========================================================
# CUSTOM ONLY
# ==========================================================


@router.get(
    "/custom",
    response_model=list[
        CustomProfileRecord
    ],
)
def list_custom_profiles(
    current_user: User = Depends(
        get_current_user
    ),

    settings: Settings = Depends(
        get_settings
    ),

    db: Session = Depends(
        get_db
    ),
) -> list[CustomProfileRecord]:
    engine = _engine(
        settings=settings,
        db=db,
    )

    return [
        _record(
            profile
        )
        for profile
        in engine.list_custom()
    ]


# ==========================================================
# EFFECTIVE PROFILE
# ==========================================================


@router.get(
    "/{profile_id}/effective",
    response_model=(
        EffectiveProfileResponse
    ),
)
def effective_profile(
    profile_id: str,

    current_user: User = Depends(
        get_current_user
    ),

    settings: Settings = Depends(
        get_settings
    ),

    db: Session = Depends(
        get_db
    ),
) -> EffectiveProfileResponse:
    engine = _engine(
        settings=settings,
        db=db,
    )

    try:
        (
            definition,
            source,
            base_profile,
        ) = (
            engine
            .resolve_with_metadata(
                profile_id
            )
        )

        return EffectiveProfileResponse(
            profile_id=profile_id,

            source=source,

            base_profile=(
                base_profile
            ),

            immutable=(
                source
                == "builtin"
            ),

            definition=definition,
        )

    except Exception as exc:
        _handle_error(
            exc
        )

        raise


# ==========================================================
# CUSTOM PROFILE DETAIL
# ==========================================================


@router.get(
    "/{profile_id}",
    response_model=(
        CustomProfileRecord
    ),
)
def get_custom_profile(
    profile_id: str,

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
    engine = _engine(
        settings=settings,
        db=db,
    )

    try:
        profile = (
            engine.repository
            .get_required(
                profile_id
            )
        )

        return _record(
            profile
        )

    except Exception as exc:
        _handle_error(
            exc
        )

        raise


# ==========================================================
# UPDATE CUSTOM PROFILE
# ==========================================================


@router.patch(
    "/{profile_id}",
    response_model=(
        CustomProfileRecord
    ),
)
def update_profile(
    profile_id: str,

    payload: CustomProfileUpdate,

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
    _require_platform_admin(
        current_user
    )

    engine = _engine(
        settings=settings,
        db=db,
    )

    try:
        profile = engine.update(
            profile_name=profile_id,
            payload=payload,
        )

        return _record(
            profile
        )

    except Exception as exc:
        _handle_error(
            exc
        )

        raise


# ==========================================================
# DELETE CUSTOM PROFILE
# ==========================================================


@router.delete(
    "/{profile_id}",
    status_code=(
        status.HTTP_204_NO_CONTENT
    ),
)
def delete_profile(
    profile_id: str,

    current_user: User = Depends(
        get_current_user
    ),

    settings: Settings = Depends(
        get_settings
    ),

    db: Session = Depends(
        get_db
    ),
) -> Response:
    _require_platform_admin(
        current_user
    )

    engine = _engine(
        settings=settings,
        db=db,
    )

    try:
        # Resolve first so that built-in profiles
        # remain protected by ProfileEngineService.
        if (
            engine._load_builtin(
                profile_id
            )
            is not None
        ):
            raise BuiltinProfileImmutable(
                "Built-in profiles are "
                "immutable"
            )

        # The deployment table stores the profile
        # identifier as a string rather than a FK.
        # Enforce referential integrity here.
        deployments = (
            _deployment_names_using_profile(
                db=db,
                profile_id=(
                    profile_id
                ),
            )
        )

        if deployments:
            raise HTTPException(
                status_code=409,

                detail={
                    "message": (
                        f"Profile "
                        f"'{profile_id}' "
                        "is currently used "
                        "by one or more "
                        "deployments"
                    ),

                    "profile": (
                        profile_id
                    ),

                    "deployments": (
                        deployments
                    ),
                },
            )

        engine.delete(
            profile_id
        )

        return Response(
            status_code=204
        )

    except HTTPException:
        raise

    except Exception as exc:
        _handle_error(
            exc
        )

        raise
