from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.db.database import Base


class Deployment(Base):
    __tablename__ = "deployments"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(63),
        unique=True,
        nullable=False,
        index=True,
    )

    model: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    repository: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    profile: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    runtime: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    deployment_mode: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    endpoint: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )

    model_artifact_reference: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    model_artifact_digest: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    owner = relationship(
        "User",
        back_populates="deployments",
    )
