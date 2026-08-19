from __future__ import annotations

from sqlalchemy import (
    desc,
    select,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.model_request import (
    ModelRequest,
)


class ModelRequestRepositoryError(
    Exception
):
    pass


class ModelRequestNotFound(
    ModelRequestRepositoryError
):
    pass


class ModelRequestRepository:

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def create(
        self,
        *,
        provider: str,
        repository: str,
        revision: str,
        requested_profile: str | None,
        purpose: str | None,
        artifact_patterns: list[str],
        download_complete_repository: bool,
        requested_by_user_id: int,
    ) -> ModelRequest:

        record = ModelRequest(
            provider=provider,

            repository=repository,

            revision=revision,

            requested_profile=(
                requested_profile
            ),

            purpose=purpose,

            artifact_patterns=(
                artifact_patterns
            ),

            download_complete_repository=(
                download_complete_repository
            ),

            status="pending",

            requested_by_user_id=(
                requested_by_user_id
            ),
        )

        try:
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)

        except SQLAlchemyError as exc:
            self.db.rollback()

            raise ModelRequestRepositoryError(
                "Could not create "
                "model request"
            ) from exc

        return record

    def get(
        self,
        request_id: int,
    ) -> ModelRequest:

        record = (
            self.db.execute(
                select(ModelRequest)
                .where(
                    ModelRequest.id
                    == request_id
                )
            )
            .scalar_one_or_none()
        )

        if record is None:
            raise ModelRequestNotFound(
                f"Model request "
                f"'{request_id}' "
                "was not found"
            )

        return record

    def list(
        self,
    ) -> list[ModelRequest]:

        return list(
            self.db.execute(
                select(ModelRequest)
                .order_by(
                    desc(
                        ModelRequest.created_at
                    )
                )
            )
            .scalars()
            .all()
        )

    def update_status(
        self,
        request_id: int,
        *,
        status: str,
        message: str | None = None,
    ) -> ModelRequest:

        record = self.get(
            request_id
        )

        record.status = status
        record.status_message = message

        try:
            self.db.commit()
            self.db.refresh(record)

        except SQLAlchemyError as exc:
            self.db.rollback()

            raise ModelRequestRepositoryError(
                "Could not update "
                "model request status"
            ) from exc

        return record

    def mark_published(
        self,
        request_id: int,
        *,
        catalog_model_id: str,
        artifact_reference: str,
        artifact_digest: str,
    ) -> ModelRequest:

        record = self.get(
            request_id
        )

        record.status = "published"

        record.status_message = (
            "Model successfully published "
            "to the trusted catalog"
        )

        record.catalog_model_id = (
            catalog_model_id
        )

        record.artifact_reference = (
            artifact_reference
        )

        record.artifact_digest = (
            artifact_digest
        )

        try:
            self.db.commit()
            self.db.refresh(record)

        except SQLAlchemyError as exc:
            self.db.rollback()

            raise ModelRequestRepositoryError(
                "Could not publish "
                "model request"
            ) from exc

        return record
