from __future__ import annotations

from sqlalchemy import (
    Integer,
    cast,
    func,
    select,
)
from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent
from app.models.deployment import Deployment
from app.models.user import User
from app.schemas.dashboard import (
    DashboardSummary,
    ModelUsage,
    ProfileUsage,
    RecentActivity,
    UserUsage,
)


class DashboardService:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    # ======================================================
    # JSON HELPERS
    # ======================================================

    @staticmethod
    def _json_text(
        key: str,
    ):
        return (
            AuditEvent.details[key]
            .as_string()
        )

    @classmethod
    def _json_integer(
        cls,
        key: str,
    ):
        return cast(
            func.coalesce(
                func.nullif(
                    cls._json_text(key),
                    "",
                ),
                "0",
            ),
            Integer,
        )

    # ======================================================
    # USER COUNTERS
    # ======================================================

    def _total_users(
        self,
    ) -> int:

        statement = select(
            func.count(
                User.id
            )
        )

        return int(
            self.db.scalar(
                statement
            )
            or 0
        )

    def _active_users(
        self,
    ) -> int:

        statement = select(
            func.count(
                User.id
            )
        ).where(
            User.is_active.is_(
                True
            )
        )

        return int(
            self.db.scalar(
                statement
            )
            or 0
        )

    # ======================================================
    # DEPLOYMENT COUNTERS
    # ======================================================

    def _total_deployments(
        self,
    ) -> int:

        statement = select(
            func.count(
                Deployment.id
            )
        )

        return int(
            self.db.scalar(
                statement
            )
            or 0
        )

    def _active_deployments(
        self,
    ) -> int:

        statement = select(
            func.count(
                Deployment.id
            )
        ).where(
            Deployment.status.in_(
                [
                    "ready",
                    "deployed",
                ]
            )
        )

        return int(
            self.db.scalar(
                statement
            )
            or 0
        )

    # ======================================================
    # INFERENCE COUNTERS
    # ======================================================

    def _total_requests(
        self,
    ) -> int:

        statement = select(
            func.count(
                AuditEvent.id
            )
        ).where(
            AuditEvent.action
            == "CHAT_COMPLETION"
        )

        return int(
            self.db.scalar(
                statement
            )
            or 0
        )

    def _token_totals(
        self,
    ) -> tuple[
        int,
        int,
        int,
    ]:

        statement = select(
            func.coalesce(
                func.sum(
                    self._json_integer(
                        "prompt_tokens"
                    )
                ),
                0,
            ),

            func.coalesce(
                func.sum(
                    self._json_integer(
                        "completion_tokens"
                    )
                ),
                0,
            ),

            func.coalesce(
                func.sum(
                    self._json_integer(
                        "total_tokens"
                    )
                ),
                0,
            ),
        ).where(
            AuditEvent.action
            == "CHAT_COMPLETION"
        )

        row = (
            self.db
            .execute(statement)
            .one()
        )

        return (
            int(row[0] or 0),
            int(row[1] or 0),
            int(row[2] or 0),
        )

    # ======================================================
    # USAGE BY MODEL
    # ======================================================

    def _usage_by_model(
        self,
    ) -> list[ModelUsage]:

        model = self._json_text(
            "model"
        )

        total_tokens = (
            self._json_integer(
                "total_tokens"
            )
        )

        statement = (
            select(
                model.label(
                    "model"
                ),

                func.count(
                    AuditEvent.id
                ).label(
                    "requests"
                ),

                func.coalesce(
                    func.sum(
                        total_tokens
                    ),
                    0,
                ).label(
                    "total_tokens"
                ),
            )

            .where(
                AuditEvent.action
                == "CHAT_COMPLETION"
            )

            .group_by(
                model
            )

            .order_by(
                func.count(
                    AuditEvent.id
                ).desc()
            )
        )

        rows = (
            self.db
            .execute(statement)
            .all()
        )

        return [
            ModelUsage(
                model=(
                    row.model
                    or "unknown"
                ),

                requests=int(
                    row.requests
                    or 0
                ),

                total_tokens=int(
                    row.total_tokens
                    or 0
                ),
            )

            for row in rows
        ]

    # ======================================================
    # USAGE BY PROFILE
    # ======================================================

    def _usage_by_profile(
        self,
    ) -> list[ProfileUsage]:

        profile = self._json_text(
            "profile"
        )

        total_tokens = (
            self._json_integer(
                "total_tokens"
            )
        )

        statement = (
            select(
                profile.label(
                    "profile"
                ),

                func.count(
                    AuditEvent.id
                ).label(
                    "requests"
                ),

                func.coalesce(
                    func.sum(
                        total_tokens
                    ),
                    0,
                ).label(
                    "total_tokens"
                ),
            )

            .where(
                AuditEvent.action
                == "CHAT_COMPLETION"
            )

            .group_by(
                profile
            )

            .order_by(
                func.count(
                    AuditEvent.id
                ).desc()
            )
        )

        rows = (
            self.db
            .execute(statement)
            .all()
        )

        return [
            ProfileUsage(
                profile=(
                    row.profile
                    or "unknown"
                ),

                requests=int(
                    row.requests
                    or 0
                ),

                total_tokens=int(
                    row.total_tokens
                    or 0
                ),
            )

            for row in rows
        ]

    # ======================================================
    # USAGE BY USER
    # ======================================================

    def _usage_by_user(
        self,
    ) -> list[UserUsage]:

        total_tokens = (
            self._json_integer(
                "total_tokens"
            )
        )

        statement = (
            select(
                AuditEvent.actor_user_id
                .label(
                    "user_id"
                ),

                User.email.label(
                    "email"
                ),

                func.count(
                    AuditEvent.id
                ).label(
                    "requests"
                ),

                func.coalesce(
                    func.sum(
                        total_tokens
                    ),
                    0,
                ).label(
                    "total_tokens"
                ),
            )

            .join(
                User,
                User.id
                == AuditEvent.actor_user_id,
                isouter=True,
            )

            .where(
                AuditEvent.action
                == "CHAT_COMPLETION"
            )

            .group_by(
                AuditEvent.actor_user_id,
                User.email,
            )

            .order_by(
                func.count(
                    AuditEvent.id
                ).desc()
            )
        )

        rows = (
            self.db
            .execute(statement)
            .all()
        )

        return [
            UserUsage(
                user_id=(
                    row.user_id
                    or 0
                ),

                email=row.email,

                requests=int(
                    row.requests
                    or 0
                ),

                total_tokens=int(
                    row.total_tokens
                    or 0
                ),
            )

            for row in rows
        ]

    # ======================================================
    # RECENT ACTIVITY
    # ======================================================

    def _recent_activity(
        self,
        limit: int = 10,
    ) -> list[RecentActivity]:

        statement = (
            select(
                AuditEvent.id,

                AuditEvent.actor_user_id,

                User.email.label(
                    "actor_email"
                ),

                AuditEvent.action,

                AuditEvent.resource_type,

                AuditEvent.resource_name,

                AuditEvent.created_at,
            )

            .join(
                User,
                User.id
                == AuditEvent.actor_user_id,
                isouter=True,
            )

            .order_by(
                AuditEvent.created_at.desc()
            )

            .limit(
                limit
            )
        )

        rows = (
            self.db
            .execute(statement)
            .all()
        )

        return [
            RecentActivity(
                id=row.id,

                actor_user_id=(
                    row.actor_user_id
                ),

                actor_email=(
                    row.actor_email
                ),

                action=row.action,

                resource_type=(
                    row.resource_type
                ),

                resource_name=(
                    row.resource_name
                ),

                created_at=(
                    row.created_at
                ),
            )

            for row in rows
        ]

    # ======================================================
    # SUMMARY
    # ======================================================

    def summary(
        self,
    ) -> DashboardSummary:

        (
            prompt_tokens,
            completion_tokens,
            total_tokens,
        ) = self._token_totals()

        return DashboardSummary(
            total_users=(
                self._total_users()
            ),

            active_users=(
                self._active_users()
            ),

            total_deployments=(
                self._total_deployments()
            ),

            active_deployments=(
                self._active_deployments()
            ),

            total_requests=(
                self._total_requests()
            ),

            total_prompt_tokens=(
                prompt_tokens
            ),

            total_completion_tokens=(
                completion_tokens
            ),

            total_tokens=(
                total_tokens
            ),

            usage_by_model=(
                self._usage_by_model()
            ),

            usage_by_profile=(
                self._usage_by_profile()
            ),

            usage_by_user=(
                self._usage_by_user()
            ),

            recent_activity=(
                self._recent_activity()
            ),
        )
