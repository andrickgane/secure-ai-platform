from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_event import (
    AuditEvent,
)
from app.schemas.audit import (
    AuditEventRecord,
)


class AuditRepositoryError(Exception):
    pass


class AuditRepository:
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
        *,
        actor_user_id: int | None,
        action: str,
        resource_type: str,
        resource_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEventRecord:

        event = AuditEvent(
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_name=resource_name,
            details=details or {},
        )

        self.db.add(
            event
        )

        try:
            self.db.commit()
            self.db.refresh(
                event
            )

        except Exception as exc:
            self.db.rollback()

            raise AuditRepositoryError(
                "Could not create audit event"
            ) from exc

        return self._to_record(
            event
        )

    # ======================================================
    # LIST
    # ======================================================

    def list(
        self,
        *,
        limit: int = 100,
    ) -> list[AuditEventRecord]:

        statement = (
            select(AuditEvent)
            .order_by(
                AuditEvent.created_at.desc()
            )
            .limit(limit)
        )

        events = (
            self.db
            .execute(statement)
            .scalars()
            .all()
        )

        return [
            self._to_record(event)
            for event in events
        ]

    # ======================================================
    # USER EVENTS
    # ======================================================

    def list_for_user(
        self,
        user_id: int,
        *,
        limit: int = 100,
    ) -> list[AuditEventRecord]:

        statement = (
            select(AuditEvent)
            .where(
                AuditEvent.actor_user_id
                == user_id
            )
            .order_by(
                AuditEvent.created_at.desc()
            )
            .limit(limit)
        )

        events = (
            self.db
            .execute(statement)
            .scalars()
            .all()
        )

        return [
            self._to_record(event)
            for event in events
        ]

    @staticmethod
    def _to_record(
        event: AuditEvent,
    ) -> AuditEventRecord:

        return AuditEventRecord(
            id=event.id,
            actor_user_id=(
                event.actor_user_id
            ),
            action=event.action,
            resource_type=(
                event.resource_type
            ),
            resource_name=(
                event.resource_name
            ),
            details=event.details or {},
            created_at=event.created_at,
        )
