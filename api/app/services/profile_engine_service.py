from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from app.models.profile import Profile
from app.repositories.profile_repository import (
    ProfileAlreadyExists,
    ProfileNotFound,
    ProfileRepository,
)
from app.schemas.profile import (
    CustomProfileCreate,
    CustomProfileUpdate,
)
from app.services.catalog_service import (
    CatalogError,
    CatalogService,
)


class ProfileEngineError(Exception):
    """Base profile engine error."""


class ProfileDefinitionInvalid(
    ProfileEngineError
):
    """Profile definition failed validation."""


class ProfileInheritanceError(
    ProfileEngineError
):
    """Invalid profile inheritance graph."""


class BuiltinProfileImmutable(
    ProfileEngineError
):
    """Built-in profiles cannot be modified."""


class ProfileEngineService:
    """
    Resolve built-in and custom AI profiles.

    Built-in profiles:
        catalog/profiles/*.yaml

    Custom profiles:
        PostgreSQL

    Custom profiles inherit a base profile and only
    persist their overrides.
    """

    ALLOWED_OVERRIDE_SECTIONS = {
        "defaults",
        "limits",
        "replicas",
        "resources",
        "storage",
        "runtimePolicy",
        "inference",
        "security",
    }

    def __init__(
        self,
        *,
        catalog: CatalogService,
        db: Session,
    ) -> None:
        self.catalog = catalog
        self.repository = (
            ProfileRepository(
                db
            )
        )

    # ======================================================
    # PUBLIC RESOLUTION API
    # ======================================================

    def resolve(
        self,
        profile_name: str,
    ) -> dict[str, Any]:
        definition, _, _ = (
            self.resolve_with_metadata(
                profile_name
            )
        )

        return definition

    def resolve_with_metadata(
        self,
        profile_name: str,
    ) -> tuple[
        dict[str, Any],
        str,
        str | None,
    ]:
        built_in = self._load_builtin(
            profile_name
        )

        if built_in is not None:
            definition = deepcopy(
                built_in
            )

            self._validate_definition(
                definition
            )

            return (
                definition,
                "builtin",
                None,
            )

        custom = (
            self.repository
            .get_by_name(
                profile_name
            )
        )

        if custom is None:
            raise ProfileNotFound(
                f"Profile '{profile_name}' "
                "was not found"
            )

        definition = (
            self._resolve_custom(
                custom,
                stack=set(),
            )
        )

        return (
            definition,
            "custom",
            custom.base_profile,
        )

    # ======================================================
    # CUSTOM PROFILE MANAGEMENT
    # ======================================================

    def create(
        self,
        *,
        payload: CustomProfileCreate,
        owner_id: int | None,
    ) -> Profile:
        if (
            self._load_builtin(
                payload.name
            )
            is not None
        ):
            raise BuiltinProfileImmutable(
                f"'{payload.name}' is a "
                "built-in profile name"
            )

        if (
            self.repository
            .get_by_name(
                payload.name
            )
            is not None
        ):
            raise ProfileAlreadyExists(
                f"Custom profile "
                f"'{payload.name}' "
                "already exists"
            )

        base_definition = (
            self.resolve(
                payload.base_profile
            )
        )

        candidate = (
            self._build_custom_definition(
                name=payload.name,
                display_name=(
                    payload.display_name
                ),
                description=(
                    payload.description
                ),
                category=(
                    payload.category
                ),
                base_definition=(
                    base_definition
                ),
                overrides=(
                    payload.overrides
                ),
            )
        )

        self._validate_definition(
            candidate
        )

        return self.repository.create(
            name=payload.name,
            display_name=(
                payload.display_name
            ),
            description=(
                payload.description
            ),
            category=payload.category,
            base_profile=(
                payload.base_profile
            ),
            overrides=deepcopy(
                payload.overrides
            ),
            owner_id=owner_id,
        )

    def update(
        self,
        *,
        profile_name: str,
        payload: CustomProfileUpdate,
    ) -> Profile:
        if (
            self._load_builtin(
                profile_name
            )
            is not None
        ):
            raise BuiltinProfileImmutable(
                "Built-in profiles are "
                "immutable"
            )

        current = (
            self.repository
            .get_required(
                profile_name
            )
        )

        new_display_name = (
            payload.display_name
            if payload.display_name
            is not None
            else current.display_name
        )

        new_description = (
            payload.description
            if "description"
            in payload.model_fields_set
            else current.description
        )

        new_category = (
            payload.category
            if payload.category
            is not None
            else current.category
        )

        new_base_profile = (
            payload.base_profile
            if payload.base_profile
            is not None
            else current.base_profile
        )

        new_overrides = (
            deepcopy(
                payload.overrides
            )
            if payload.overrides
            is not None
            else deepcopy(
                current.overrides
            )
        )

        if (
            new_base_profile
            == profile_name
        ):
            raise ProfileInheritanceError(
                "A profile cannot inherit "
                "from itself"
            )

        base_definition = (
            self.resolve(
                new_base_profile
            )
        )

        candidate = (
            self._build_custom_definition(
                name=profile_name,
                display_name=(
                    new_display_name
                ),
                description=(
                    new_description
                ),
                category=(
                    new_category
                ),
                base_definition=(
                    base_definition
                ),
                overrides=(
                    new_overrides
                ),
            )
        )

        self._validate_definition(
            candidate
        )

        return self.repository.update(
            current,
            display_name=(
                payload.display_name
            ),
            description=(
                payload.description
            ),
            description_supplied=(
                "description"
                in payload.model_fields_set
            ),
            category=payload.category,
            base_profile=(
                payload.base_profile
            ),
            overrides=(
                deepcopy(
                    payload.overrides
                )
                if payload.overrides
                is not None
                else None
            ),
        )

    def delete(
        self,
        profile_name: str,
    ) -> None:
        if (
            self._load_builtin(
                profile_name
            )
            is not None
        ):
            raise BuiltinProfileImmutable(
                "Built-in profiles are "
                "immutable"
            )

        profile = (
            self.repository
            .get_required(
                profile_name
            )
        )

        children = [
            item
            for item
            in self.repository.list()
            if (
                item.base_profile
                == profile_name
            )
        ]

        if children:
            names = ", ".join(
                item.name
                for item in children
            )

            raise ProfileInheritanceError(
                "Profile cannot be deleted "
                "because it is inherited by: "
                + names
            )

        self.repository.delete(
            profile
        )

    def list_custom(
        self,
    ) -> list[Profile]:
        return self.repository.list()

    # ======================================================
    # INHERITANCE
    # ======================================================

    def _resolve_custom(
        self,
        profile: Profile,
        *,
        stack: set[str],
    ) -> dict[str, Any]:
        if profile.name in stack:
            chain = " -> ".join(
                [
                    *sorted(stack),
                    profile.name,
                ]
            )

            raise ProfileInheritanceError(
                "Profile inheritance cycle "
                f"detected: {chain}"
            )

        next_stack = {
            *stack,
            profile.name,
        }

        built_in_base = (
            self._load_builtin(
                profile.base_profile
            )
        )

        if built_in_base is not None:
            base_definition = deepcopy(
                built_in_base
            )

        else:
            parent = (
                self.repository
                .get_by_name(
                    profile.base_profile
                )
            )

            if parent is None:
                raise ProfileInheritanceError(
                    f"Base profile "
                    f"'{profile.base_profile}' "
                    "does not exist"
                )

            base_definition = (
                self._resolve_custom(
                    parent,
                    stack=next_stack,
                )
            )

        definition = (
            self._build_custom_definition(
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
                base_definition=(
                    base_definition
                ),
                overrides=(
                    profile.overrides
                ),
            )
        )

        self._validate_definition(
            definition
        )

        return definition

    def _build_custom_definition(
        self,
        *,
        name: str,
        display_name: str,
        description: str | None,
        category: str,
        base_definition: dict[str, Any],
        overrides: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_overrides(
            overrides
        )

        base_spec = (
            base_definition.get(
                "spec",
                {},
            )
        )

        if not isinstance(
            base_spec,
            dict,
        ):
            raise ProfileDefinitionInvalid(
                "Base profile spec "
                "is invalid"
            )

        effective_spec = (
            self._deep_merge(
                deepcopy(
                    base_spec
                ),
                deepcopy(
                    overrides
                ),
            )
        )

        effective_spec[
            "displayName"
        ] = display_name

        effective_spec[
            "category"
        ] = category

        if description is not None:
            effective_spec[
                "description"
            ] = description

        return {
            "apiVersion": (
                "platform.secureai.io/"
                "v1alpha1"
            ),
            "kind": "AIProfile",
            "metadata": {
                "name": name,
            },
            "spec": effective_spec,
        }

    # ======================================================
    # VALIDATION
    # ======================================================

    def _validate_overrides(
        self,
        overrides: dict[str, Any],
    ) -> None:
        if not isinstance(
            overrides,
            dict,
        ):
            raise ProfileDefinitionInvalid(
                "Profile overrides must "
                "be an object"
            )

        unknown = (
            set(
                overrides.keys()
            )
            - self.ALLOWED_OVERRIDE_SECTIONS
        )

        if unknown:
            raise ProfileDefinitionInvalid(
                "Unsupported profile "
                "override section(s): "
                + ", ".join(
                    sorted(
                        unknown
                    )
                )
            )

    def _validate_definition(
        self,
        definition: dict[str, Any],
    ) -> None:
        metadata = definition.get(
            "metadata",
            {},
        )

        spec = definition.get(
            "spec",
            {},
        )

        if not isinstance(
            metadata,
            dict,
        ):
            raise ProfileDefinitionInvalid(
                "Profile metadata "
                "must be an object"
            )

        if not metadata.get(
            "name"
        ):
            raise ProfileDefinitionInvalid(
                "Profile metadata.name "
                "is required"
            )

        if not isinstance(
            spec,
            dict,
        ):
            raise ProfileDefinitionInvalid(
                "Profile spec "
                "must be an object"
            )

        defaults = self._dict(
            spec,
            "defaults",
        )

        limits = self._dict(
            spec,
            "limits",
        )

        runtime_policy = self._dict(
            spec,
            "runtimePolicy",
        )

        inference = self._dict(
            spec,
            "inference",
        )

        security = self._dict(
            spec,
            "security",
        )

        self._positive_integer(
            defaults,
            "maxModelLen",
        )

        self._positive_integer(
            defaults,
            "maxTokens",
        )

        self._positive_integer(
            limits,
            "maxModelLen",
        )

        self._positive_integer(
            limits,
            "maxTokens",
        )

        self._validate_float_range(
            limits.get(
                "temperature"
            ),
            "temperature",
        )

        self._validate_float_range(
            limits.get(
                "topP"
            ),
            "topP",
        )

        temperature = (
            defaults.get(
                "temperature"
            )
        )

        if temperature is not None:
            self._validate_number(
                temperature,
                "defaults.temperature",
            )

        top_p = defaults.get(
            "topP"
        )

        if top_p is not None:
            self._validate_number(
                top_p,
                "defaults.topP",
            )

            if not (
                0.0
                <= float(top_p)
                <= 1.0
            ):
                raise ProfileDefinitionInvalid(
                    "defaults.topP must "
                    "be between 0 and 1"
                )

        self._validate_default_limits(
            defaults,
            limits,
        )

        allowed = self._string_list(
            runtime_policy,
            "allowedRuntimes",
        )

        preferred = self._string_list(
            runtime_policy,
            "preferredRuntimes",
        )

        if (
            allowed
            and preferred
        ):
            invalid = [
                runtime
                for runtime
                in preferred
                if runtime
                not in allowed
            ]

            if invalid:
                raise ProfileDefinitionInvalid(
                    "preferredRuntimes must "
                    "be allowedRuntimes: "
                    + ", ".join(
                        invalid
                    )
                )

        streaming = inference.get(
            "streaming"
        )

        if (
            streaming is not None
            and not isinstance(
                streaming,
                bool,
            )
        ):
            raise ProfileDefinitionInvalid(
                "inference.streaming "
                "must be boolean"
            )

        timeout = inference.get(
            "timeoutSeconds"
        )

        if timeout is not None:
            if (
                not isinstance(
                    timeout,
                    int,
                )
                or timeout <= 0
            ):
                raise ProfileDefinitionInvalid(
                    "inference.timeoutSeconds "
                    "must be a positive integer"
                )

        concurrency = (
            inference.get(
                "concurrency",
                {},
            )
        )

        if not isinstance(
            concurrency,
            dict,
        ):
            raise ProfileDefinitionInvalid(
                "inference.concurrency "
                "must be an object"
            )

        max_requests = (
            concurrency.get(
                "maxRequests"
            )
        )

        if max_requests is not None:
            if (
                not isinstance(
                    max_requests,
                    int,
                )
                or max_requests <= 0
            ):
                raise ProfileDefinitionInvalid(
                    "inference.concurrency."
                    "maxRequests must be "
                    "a positive integer"
                )

        allow_overrides = (
            security.get(
                "allowUserOverrides"
            )
        )

        if (
            allow_overrides is not None
            and not isinstance(
                allow_overrides,
                bool,
            )
        ):
            raise ProfileDefinitionInvalid(
                "security.allowUserOverrides "
                "must be boolean"
            )

        self._string_list(
            security,
            "overridableParameters",
        )

    @staticmethod
    def _dict(
        parent: dict[str, Any],
        key: str,
    ) -> dict[str, Any]:
        value = parent.get(
            key,
            {},
        )

        if not isinstance(
            value,
            dict,
        ):
            raise ProfileDefinitionInvalid(
                f"spec.{key} "
                "must be an object"
            )

        return value

    @staticmethod
    def _positive_integer(
        parent: dict[str, Any],
        key: str,
    ) -> None:
        value = parent.get(
            key
        )

        if value is None:
            return

        if (
            not isinstance(
                value,
                int,
            )
            or value <= 0
        ):
            raise ProfileDefinitionInvalid(
                f"{key} must be "
                "a positive integer"
            )

    @staticmethod
    def _validate_number(
        value: Any,
        name: str,
    ) -> None:
        if (
            isinstance(
                value,
                bool,
            )
            or not isinstance(
                value,
                (int, float),
            )
        ):
            raise ProfileDefinitionInvalid(
                f"{name} must be numeric"
            )

    @classmethod
    def _validate_float_range(
        cls,
        value: Any,
        name: str,
    ) -> None:
        if value is None:
            return

        if not isinstance(
            value,
            dict,
        ):
            raise ProfileDefinitionInvalid(
                f"limits.{name} "
                "must be an object"
            )

        minimum = value.get(
            "min"
        )

        maximum = value.get(
            "max"
        )

        if minimum is not None:
            cls._validate_number(
                minimum,
                f"limits.{name}.min",
            )

        if maximum is not None:
            cls._validate_number(
                maximum,
                f"limits.{name}.max",
            )

        if (
            minimum is not None
            and maximum is not None
            and float(minimum)
            > float(maximum)
        ):
            raise ProfileDefinitionInvalid(
                f"limits.{name}.min "
                "cannot exceed max"
            )

    @staticmethod
    def _string_list(
        parent: dict[str, Any],
        key: str,
    ) -> list[str]:
        value = parent.get(
            key,
            [],
        )

        if value is None:
            return []

        if not isinstance(
            value,
            list,
        ):
            raise ProfileDefinitionInvalid(
                f"{key} must be a list"
            )

        if not all(
            isinstance(
                item,
                str,
            )
            and item
            for item in value
        ):
            raise ProfileDefinitionInvalid(
                f"{key} must contain "
                "non-empty strings"
            )

        return [
            str(item)
            for item in value
        ]

    @classmethod
    def _validate_default_limits(
        cls,
        defaults: dict[str, Any],
        limits: dict[str, Any],
    ) -> None:
        for key in (
            "maxModelLen",
            "maxTokens",
        ):
            default = defaults.get(
                key
            )

            maximum = limits.get(
                key
            )

            if (
                default is not None
                and maximum is not None
                and int(default)
                > int(maximum)
            ):
                raise ProfileDefinitionInvalid(
                    f"defaults.{key} "
                    "exceeds limits."
                    f"{key}"
                )

        for key in (
            "temperature",
            "topP",
        ):
            default = defaults.get(
                key
            )

            range_definition = (
                limits.get(
                    key,
                    {},
                )
            )

            if (
                default is None
                or not isinstance(
                    range_definition,
                    dict,
                )
            ):
                continue

            minimum = (
                range_definition.get(
                    "min"
                )
            )

            maximum = (
                range_definition.get(
                    "max"
                )
            )

            if (
                minimum is not None
                and float(default)
                < float(minimum)
            ):
                raise ProfileDefinitionInvalid(
                    f"defaults.{key} "
                    "is below profile limit"
                )

            if (
                maximum is not None
                and float(default)
                > float(maximum)
            ):
                raise ProfileDefinitionInvalid(
                    f"defaults.{key} "
                    "exceeds profile limit"
                )

    # ======================================================
    # UTILITIES
    # ======================================================

    def _load_builtin(
        self,
        profile_name: str,
    ) -> dict[str, Any] | None:
        try:
            return self.catalog.load(
                "profiles",
                profile_name,
            )

        except CatalogError:
            return None

    @classmethod
    def _deep_merge(
        cls,
        base: dict[str, Any],
        override: dict[str, Any],
    ) -> dict[str, Any]:
        result = deepcopy(
            base
        )

        for key, value in (
            override.items()
        ):
            current = result.get(
                key
            )

            if (
                isinstance(
                    current,
                    dict,
                )
                and isinstance(
                    value,
                    dict,
                )
            ):
                result[key] = (
                    cls._deep_merge(
                        current,
                        value,
                    )
                )

            else:
                result[key] = deepcopy(
                    value
                )

        return result
