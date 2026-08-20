from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    JSON,
    LargeBinary,
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


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    owner_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="New chat",
    )

    deployment_name: Mapped[str | None] = mapped_column(
        String(63),
        nullable=True,
        index=True,
    )

    model: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    profile: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    runtime: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )

    messages = relationship(
        "ConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ConversationMessage.id",
    )

    attachments = relationship(
        "ConversationAttachment",
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ConversationAttachment.id",
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey(
            "conversations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    model: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    profile: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    runtime: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    parameters: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    prompt_tokens: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    completion_tokens: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    total_tokens: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    latency_ms: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    first_token_latency_ms: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    generation_duration_ms: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    generation_tokens_per_second: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    output_tokens_per_second: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="completed",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    conversation = relationship(
        "Conversation",
        back_populates="messages",
    )

    attachments = relationship(
        "ConversationAttachment",
        back_populates="message",
        passive_deletes=True,
        order_by="ConversationAttachment.id",
    )


class ConversationAttachment(Base):
    __tablename__ = "conversation_attachments"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey(
            "conversations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    message_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "conversation_messages.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    media_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    content: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    conversation = relationship(
        "Conversation",
        back_populates="attachments",
    )

    message = relationship(
        "ConversationMessage",
        back_populates="attachments",
    )
