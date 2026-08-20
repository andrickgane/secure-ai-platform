from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.db.database import Base


class ModelRequest(Base):
    __tablename__ = "model_requests"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="huggingface",
    )

    repository: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    revision: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="main",
    )

    requested_profile: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    purpose: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    artifact_patterns: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    download_complete_repository: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    artifact_format: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    architecture: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    quantization: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        default="pending",
    )

    status_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    catalog_model_id: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        index=True,
    )

    artifact_reference: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )

    artifact_digest: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    requested_by_user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        ),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        ),
        onupdate=lambda: datetime.now(
            timezone.utc
        ),
    )
