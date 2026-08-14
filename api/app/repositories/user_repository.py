from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserRecord


class UserRepositoryError(Exception):
    pass


class UserNotFound(
    UserRepositoryError
):
    pass


class UserRepository:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def get(
        self,
        user_id: int,
    ) -> User:

        user = self.db.get(
            User,
            user_id,
        )

        if user is None:
            raise UserNotFound(
                f"User '{user_id}' "
                "does not exist"
            )

        return user

    def list(
        self,
    ) -> list[UserRecord]:

        statement = (
            select(User)
            .order_by(
                User.created_at.desc()
            )
        )

        users = (
            self.db
            .execute(statement)
            .scalars()
            .all()
        )

        return [
            self._to_record(user)
            for user in users
        ]

    def update_status(
        self,
        user_id: int,
        *,
        is_active: bool,
    ) -> UserRecord:

        user = self.get(
            user_id
        )

        user.is_active = (
            is_active
        )

        try:
            self.db.commit()
            self.db.refresh(
                user
            )

        except Exception as exc:
            self.db.rollback()

            raise UserRepositoryError(
                f"Could not update "
                f"user '{user_id}'"
            ) from exc

        return self._to_record(
            user
        )

    @staticmethod
    def _to_record(
        user: User,
    ) -> UserRecord:

        return UserRecord(
            id=user.id,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
