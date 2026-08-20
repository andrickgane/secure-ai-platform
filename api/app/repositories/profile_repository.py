from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.profile import Profile


class ProfileRepositoryError(Exception):
    """Base profile repository error."""


class ProfileNotFound(ProfileRepositoryError):
    """Custom profile does not exist."""


class ProfileAlreadyExists(ProfileRepositoryError):
    """Custom profile name already exists."""


class ProfileRepository:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def get_by_name(
        self,
        name: str,
    ) -> Profile | None:
        return (
            self.db.execute(
                select(Profile).where(
                    Profile.name == name
                )
            )
            .scalars()
            .first()
        )

    def get_required(
        self,
        name: str,
    ) -> Profile:
        profile = self.get_by_name(
            name
        )

        if profile is None:
            raise ProfileNotFound(
                f"Custom profile '{name}' "
                "was not found"
            )

        return profile

    def list(
        self,
    ) -> list[Profile]:
        return list(
            self.db.execute(
                select(Profile)
                .order_by(
                    Profile.name.asc()
                )
            )
            .scalars()
            .all()
        )

    def create(
        self,
        *,
        name: str,
        display_name: str,
        description: str | None,
        category: str,
        base_profile: str,
        overrides: dict[str, Any],
        owner_id: int | None,
    ) -> Profile:
        profile = Profile(
            name=name,
            display_name=display_name,
            description=description,
            category=category,
            base_profile=base_profile,
            overrides=overrides,
            owner_id=owner_id,
        )

        self.db.add(
            profile
        )

        try:
            self.db.commit()

        except IntegrityError as exc:
            self.db.rollback()

            raise ProfileAlreadyExists(
                f"Custom profile '{name}' "
                "already exists"
            ) from exc

        self.db.refresh(
            profile
        )

        return profile

    def update(
        self,
        profile: Profile,
        *,
        display_name: str | None = None,
        description: str | None = None,
        description_supplied: bool = False,
        category: str | None = None,
        base_profile: str | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> Profile:
        if display_name is not None:
            profile.display_name = (
                display_name
            )

        if description_supplied:
            profile.description = (
                description
            )

        if category is not None:
            profile.category = category

        if base_profile is not None:
            profile.base_profile = (
                base_profile
            )

        if overrides is not None:
            profile.overrides = overrides

        try:
            self.db.commit()

        except IntegrityError as exc:
            self.db.rollback()

            raise ProfileRepositoryError(
                "Could not update custom "
                "profile"
            ) from exc

        self.db.refresh(
            profile
        )

        return profile

    def delete(
        self,
        profile: Profile,
    ) -> None:
        self.db.delete(
            profile
        )

        self.db.commit()
