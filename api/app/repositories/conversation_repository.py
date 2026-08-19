from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    select,
)
from sqlalchemy.exc import (
    SQLAlchemyError,
)
from sqlalchemy.orm import (
    Session,
    selectinload,
)

from app.models.conversation import (
    Conversation,
    ConversationAttachment,
    ConversationMessage,
)
from app.schemas.conversation import (
    ConversationMessageCreate,
)


class ConversationRepositoryError(
    RuntimeError
):
    pass


class ConversationNotFound(
    ConversationRepositoryError
):
    pass


class AttachmentNotFound(
    ConversationRepositoryError
):
    pass


class ConversationRepository:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db


    def list_for_owner(
        self,
        owner_id: int,
    ) -> list[Conversation]:
        try:
            return list(
                self.db.scalars(
                    select(
                        Conversation
                    )
                    .where(
                        Conversation.owner_id
                        == owner_id
                    )
                    .order_by(
                        Conversation.updated_at.desc(),
                        Conversation.id.desc(),
                    )
                )
            )

        except SQLAlchemyError as exc:
            raise ConversationRepositoryError(
                str(exc)
            ) from exc


    def get_for_owner(
        self,
        conversation_id: int,
        owner_id: int,
        *,
        with_children: bool = False,
    ) -> Conversation:
        statement = (
            select(
                Conversation
            )
            .where(
                Conversation.id
                == conversation_id,
                Conversation.owner_id
                == owner_id,
            )
        )

        if with_children:
            statement = (
                statement.options(
                    selectinload(
                        Conversation.messages
                    ),
                    selectinload(
                        Conversation.attachments
                    ),
                )
            )

        try:
            conversation = (
                self.db.scalar(
                    statement
                )
            )

        except SQLAlchemyError as exc:
            raise ConversationRepositoryError(
                str(exc)
            ) from exc

        if conversation is None:
            raise ConversationNotFound(
                f"Conversation '{conversation_id}' not found"
            )

        return conversation


    def create(
        self,
        *,
        owner_id: int,
        title: str,
        deployment_name: str | None,
        model: str | None,
        profile: str | None,
        runtime: str | None,
    ) -> Conversation:
        conversation = Conversation(
            owner_id=owner_id,
            title=title,
            deployment_name=deployment_name,
            model=model,
            profile=profile,
            runtime=runtime,
        )

        try:
            self.db.add(
                conversation
            )

            self.db.commit()

            self.db.refresh(
                conversation
            )

            return conversation

        except SQLAlchemyError as exc:
            self.db.rollback()

            raise ConversationRepositoryError(
                str(exc)
            ) from exc


    def update(
        self,
        conversation: Conversation,
        *,
        title: str | None = None,
        deployment_name: str | None = None,
        deployment_changed: bool = False,
        model: str | None = None,
        profile: str | None = None,
        runtime: str | None = None,
    ) -> Conversation:
        if title is not None:
            conversation.title = (
                title.strip()
            )

        if deployment_changed:
            conversation.deployment_name = (
                deployment_name
            )

            conversation.model = model
            conversation.profile = profile
            conversation.runtime = runtime

        conversation.updated_at = (
            datetime.now(
                timezone.utc
            )
        )

        try:
            self.db.commit()

            self.db.refresh(
                conversation
            )

            return conversation

        except SQLAlchemyError as exc:
            self.db.rollback()

            raise ConversationRepositoryError(
                str(exc)
            ) from exc


    def delete(
        self,
        conversation: Conversation,
    ) -> None:
        try:
            self.db.delete(
                conversation
            )

            self.db.commit()

        except SQLAlchemyError as exc:
            self.db.rollback()

            raise ConversationRepositoryError(
                str(exc)
            ) from exc


    def add_message(
        self,
        conversation: Conversation,
        payload: ConversationMessageCreate,
    ) -> ConversationMessage:
        message = ConversationMessage(
            conversation_id=conversation.id,

            role=payload.role,
            content=payload.content,

            model=payload.model,
            profile=payload.profile,
            runtime=payload.runtime,

            parameters=payload.parameters,

            prompt_tokens=payload.prompt_tokens,
            completion_tokens=payload.completion_tokens,
            total_tokens=payload.total_tokens,

            latency_ms=payload.latency_ms,

            first_token_latency_ms=(
                payload.first_token_latency_ms
            ),

            generation_duration_ms=(
                payload.generation_duration_ms
            ),

            generation_tokens_per_second=(
                payload.generation_tokens_per_second
            ),

            output_tokens_per_second=(
                payload.output_tokens_per_second
            ),

            status=payload.status,
        )

        if (
            payload.role == "user"
            and conversation.title == "New chat"
        ):
            normalized = " ".join(
                payload.content.split()
            )

            if normalized:
                conversation.title = (
                    normalized[:72]
                    + (
                        "…"
                        if len(normalized) > 72
                        else ""
                    )
                )

        conversation.updated_at = (
            datetime.now(
                timezone.utc
            )
        )

        try:
            self.db.add(
                message
            )

            # We need the generated message ID before
            # assigning pending attachments to it.
            self.db.flush()

            attachment_ids = list(
                dict.fromkeys(
                    payload.attachment_ids
                )
            )

            if attachment_ids:
                attachments = list(
                    self.db.scalars(
                        select(
                            ConversationAttachment
                        )
                        .where(
                            ConversationAttachment.id.in_(
                                attachment_ids
                            ),

                            ConversationAttachment.conversation_id
                            == conversation.id,

                            ConversationAttachment.message_id
                            .is_(None),
                        )
                    )
                )

                found_ids = {
                    attachment.id
                    for attachment
                    in attachments
                }

                missing_ids = [
                    attachment_id
                    for attachment_id
                    in attachment_ids
                    if attachment_id
                    not in found_ids
                ]

                if missing_ids:
                    raise ConversationRepositoryError(
                        "One or more attachments are "
                        "missing, already assigned to a "
                        "message, or belong to another "
                        "conversation"
                    )

                for attachment in attachments:
                    attachment.message_id = (
                        message.id
                    )

            self.db.commit()

            self.db.refresh(
                message
            )

            return message

        except ConversationRepositoryError:
            self.db.rollback()
            raise

        except SQLAlchemyError as exc:
            self.db.rollback()

            raise ConversationRepositoryError(
                str(exc)
            ) from exc


    def add_attachment(
        self,
        conversation: Conversation,
        *,
        filename: str,
        media_type: str,
        size_bytes: int,
        sha256: str,
        content: bytes,
    ) -> ConversationAttachment:
        attachment = (
            ConversationAttachment(
                conversation_id=(
                    conversation.id
                ),

                filename=filename,
                media_type=media_type,
                size_bytes=size_bytes,
                sha256=sha256,
                content=content,
            )
        )

        conversation.updated_at = (
            datetime.now(
                timezone.utc
            )
        )

        try:
            self.db.add(
                attachment
            )

            self.db.commit()

            self.db.refresh(
                attachment
            )

            return attachment

        except SQLAlchemyError as exc:
            self.db.rollback()

            raise ConversationRepositoryError(
                str(exc)
            ) from exc


    def get_attachment_for_owner(
        self,
        *,
        conversation_id: int,
        attachment_id: int,
        owner_id: int,
    ) -> ConversationAttachment:
        try:
            attachment = (
                self.db.scalar(
                    select(
                        ConversationAttachment
                    )
                    .join(
                        Conversation,
                        Conversation.id
                        == ConversationAttachment.conversation_id,
                    )
                    .where(
                        ConversationAttachment.id
                        == attachment_id,

                        ConversationAttachment.conversation_id
                        == conversation_id,

                        Conversation.owner_id
                        == owner_id,
                    )
                )
            )

        except SQLAlchemyError as exc:
            raise ConversationRepositoryError(
                str(exc)
            ) from exc

        if attachment is None:
            raise AttachmentNotFound(
                f"Attachment '{attachment_id}' not found"
            )

        return attachment


    def delete_attachment(
        self,
        attachment: ConversationAttachment,
    ) -> None:
        try:
            self.db.delete(
                attachment
            )

            self.db.commit()

        except SQLAlchemyError as exc:
            self.db.rollback()

            raise ConversationRepositoryError(
                str(exc)
            ) from exc
