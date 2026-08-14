from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.deployment import Deployment
from app.schemas.deployment import (
    DeploymentContext,
    DeploymentRecord,
    DeploymentStatus,
)


class DeploymentRepositoryError(Exception):
    pass


class DeploymentNotFound(
    DeploymentRepositoryError
):
    pass


class DeploymentAlreadyExists(
    DeploymentRepositoryError
):
    pass


class DeploymentRepository:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    # ======================================================
    # CREATE
    # ======================================================

    def create(
        self,
        context: DeploymentContext,
        *,
        owner_id: int,
        status: DeploymentStatus,
        endpoint: str | None,
    ) -> DeploymentRecord:

        deployment = Deployment(
            owner_id=owner_id,

            name=context.name,
            model=context.model,

            repository=(
                context.repository
            ),

            profile=context.profile,
            runtime=context.runtime,

            deployment_mode=(
                context.deployment_mode
            ),

            status=status,
            endpoint=endpoint,

            model_artifact_reference=(
                context.model_artifact_reference
            ),

            model_artifact_digest=(
                context.model_artifact_digest
            ),
        )

        self.db.add(
            deployment
        )

        try:
            self.db.commit()

        except IntegrityError as exc:
            self.db.rollback()

            raise DeploymentAlreadyExists(
                f"Deployment "
                f"'{context.name}' "
                "already exists"
            ) from exc

        except Exception as exc:
            self.db.rollback()

            raise DeploymentRepositoryError(
                f"Could not create "
                f"deployment '{context.name}'"
            ) from exc

        self.db.refresh(
            deployment
        )

        return self._to_record(
            deployment
        )

    # ======================================================
    # GET
    # ======================================================

    def get(
        self,
        name: str,
    ) -> DeploymentRecord:

        deployment = self._get_model(
            name
        )

        return self._to_record(
            deployment
        )

    def get_for_owner(
        self,
        name: str,
        owner_id: int,
    ) -> DeploymentRecord:

        statement = (
            select(Deployment)
            .where(
                Deployment.name == name,
                Deployment.owner_id == owner_id,
            )
        )

        deployment = (
            self.db
            .execute(statement)
            .scalar_one_or_none()
        )

        if deployment is None:
            raise DeploymentNotFound(
                f"Deployment "
                f"'{name}' "
                "does not exist"
            )

        return self._to_record(
            deployment
        )

    def _get_model(
        self,
        name: str,
    ) -> Deployment:

        statement = (
            select(Deployment)
            .where(
                Deployment.name == name
            )
        )

        deployment = (
            self.db
            .execute(statement)
            .scalar_one_or_none()
        )

        if deployment is None:
            raise DeploymentNotFound(
                f"Deployment "
                f"'{name}' "
                "does not exist"
            )

        return deployment

    def _get_model_for_owner(
        self,
        name: str,
        owner_id: int,
    ) -> Deployment:

        statement = (
            select(Deployment)
            .where(
                Deployment.name == name,
                Deployment.owner_id == owner_id,
            )
        )

        deployment = (
            self.db
            .execute(statement)
            .scalar_one_or_none()
        )

        if deployment is None:
            raise DeploymentNotFound(
                f"Deployment "
                f"'{name}' "
                "does not exist"
            )

        return deployment

    # ======================================================
    # LIST
    # ======================================================

    def list(
        self,
    ) -> list[DeploymentRecord]:

        statement = (
            select(Deployment)
            .order_by(
                Deployment.created_at.desc()
            )
        )

        deployments = (
            self.db
            .execute(statement)
            .scalars()
            .all()
        )

        return [
            self._to_record(item)
            for item in deployments
        ]

    def list_for_owner(
        self,
        owner_id: int,
    ) -> list[DeploymentRecord]:

        statement = (
            select(Deployment)
            .where(
                Deployment.owner_id
                == owner_id
            )
            .order_by(
                Deployment.created_at.desc()
            )
        )

        deployments = (
            self.db
            .execute(statement)
            .scalars()
            .all()
        )

        return [
            self._to_record(item)
            for item in deployments
        ]

    # ======================================================
    # UPDATE
    # ======================================================

    def update_status(
        self,
        name: str,
        *,
        status: DeploymentStatus,
        endpoint: str | None = None,
    ) -> DeploymentRecord:

        deployment = self._get_model(
            name
        )

        deployment.status = status

        if endpoint is not None:
            deployment.endpoint = endpoint

        try:
            self.db.commit()
            self.db.refresh(
                deployment
            )

        except Exception as exc:
            self.db.rollback()

            raise DeploymentRepositoryError(
                f"Could not update "
                f"deployment '{name}'"
            ) from exc

        return self._to_record(
            deployment
        )

    # ======================================================
    # DELETE
    # ======================================================

    def delete(
        self,
        name: str,
    ) -> None:

        deployment = self._get_model(
            name
        )

        self._delete_model(
            deployment
        )

    def delete_for_owner(
        self,
        name: str,
        owner_id: int,
    ) -> None:

        deployment = (
            self._get_model_for_owner(
                name,
                owner_id,
            )
        )

        self._delete_model(
            deployment
        )

    def _delete_model(
        self,
        deployment: Deployment,
    ) -> None:

        try:
            self.db.delete(
                deployment
            )

            self.db.commit()

        except Exception as exc:
            self.db.rollback()

            raise DeploymentRepositoryError(
                f"Could not delete deployment "
                f"'{deployment.name}'"
            ) from exc

    # ======================================================
    # MAPPING
    # ======================================================

    @staticmethod
    def _to_record(
        deployment: Deployment,
    ) -> DeploymentRecord:

        return DeploymentRecord(
            id=deployment.id,

            owner_id=(
                deployment.owner_id
            ),

            name=deployment.name,
            model=deployment.model,

            repository=(
                deployment.repository
            ),

            profile=deployment.profile,
            runtime=deployment.runtime,

            deployment_mode=(
                deployment.deployment_mode
            ),

            status=deployment.status,

            endpoint=deployment.endpoint,

            model_artifact_reference=(
                deployment
                .model_artifact_reference
            ),

            model_artifact_digest=(
                deployment
                .model_artifact_digest
            ),

            created_at=(
                deployment.created_at
            ),

            updated_at=(
                deployment.updated_at
            ),
        )
