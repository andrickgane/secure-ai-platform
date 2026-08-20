from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.auth import (
    get_current_user,
)
from app.db.database import (
    get_db,
)
from app.models.user import User
from app.services.attachment_security_service import (
    AttachmentSecurityError,
    AttachmentSecurityService,
)
from app.repositories.conversation_repository import (
    AttachmentNotFound,
    ConversationNotFound,
    ConversationRepository,
    ConversationRepositoryError,
)
from app.repositories.deployment_repository import (
    DeploymentNotFound,
    DeploymentRepository,
    DeploymentRepositoryError,
)
from app.schemas.conversation import (
    ConversationAttachmentRecord,
    ConversationCreate,
    ConversationDetail,
    ConversationMessageCreate,
    ConversationMessageRecord,
    ConversationRecord,
    ConversationUpdate,
)


router = APIRouter(
    prefix="/api/v1/conversations",
    tags=["conversations"],
)


MAX_ATTACHMENT_SIZE = (
    10 * 1024 * 1024
)


ALLOWED_ATTACHMENT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".html",
    ".css",

    ".py",
    ".sh",
    ".bash",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".sql",

    ".tf",
    ".tfvars",
    ".hcl",
    ".ini",
    ".conf",
    ".log",

    ".pdf",

    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
}


def _is_admin(
    user: User,
) -> bool:
    return user.role in {
        "admin",
        "platform_admin",
    }


def _raise_repository_error(
    exc: Exception,
) -> None:
    if isinstance(
        exc,
        (
            ConversationNotFound,
            AttachmentNotFound,
        ),
    ):
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    if isinstance(
        exc,
        ConversationRepositoryError,
    ):
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    raise exc


def _deployment_snapshot(
    *,
    deployment_name: str | None,
    current_user: User,
    db: Session,
) -> tuple[
    str | None,
    str | None,
    str | None,
    str | None,
]:
    if not deployment_name:
        return (
            None,
            None,
            None,
            None,
        )

    repository = (
        DeploymentRepository(
            db
        )
    )

    try:
        if _is_admin(
            current_user
        ):
            deployment = (
                repository.get(
                    deployment_name
                )
            )

        else:
            deployment = (
                repository.get_for_owner(
                    deployment_name,
                    current_user.id,
                )
            )

    except DeploymentNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except DeploymentRepositoryError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    return (
        deployment.name,
        deployment.model,
        deployment.profile,
        deployment.runtime,
    )


@router.post(
    "",
    response_model=ConversationRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    payload: ConversationCreate,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
) -> ConversationRecord:
    (
        deployment_name,
        model,
        profile,
        runtime,
    ) = _deployment_snapshot(
        deployment_name=(
            payload.deployment_name
        ),

        current_user=current_user,
        db=db,
    )

    repository = (
        ConversationRepository(
            db
        )
    )

    try:
        conversation = (
            repository.create(
                owner_id=(
                    current_user.id
                ),

                title=(
                    payload.title.strip()
                ),

                deployment_name=(
                    deployment_name
                ),

                model=model,
                profile=profile,
                runtime=runtime,
            )
        )

    except Exception as exc:
        _raise_repository_error(
            exc
        )

        raise

    return ConversationRecord.model_validate(
        conversation
    )


@router.get(
    "",
    response_model=list[
        ConversationRecord
    ],
)
def list_conversations(
    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
) -> list[ConversationRecord]:
    repository = (
        ConversationRepository(
            db
        )
    )

    try:
        conversations = (
            repository.list_for_owner(
                current_user.id
            )
        )

    except Exception as exc:
        _raise_repository_error(
            exc
        )

        raise

    return [
        ConversationRecord.model_validate(
            item
        )
        for item in conversations
    ]


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetail,
)
def get_conversation(
    conversation_id: int,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
) -> ConversationDetail:
    repository = (
        ConversationRepository(
            db
        )
    )

    try:
        conversation = (
            repository.get_for_owner(
                conversation_id,
                current_user.id,
                with_children=True,
            )
        )

    except Exception as exc:
        _raise_repository_error(
            exc
        )

        raise

    return ConversationDetail.model_validate(
        conversation
    )


@router.patch(
    "/{conversation_id}",
    response_model=ConversationRecord,
)
def update_conversation(
    conversation_id: int,

    payload: ConversationUpdate,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
) -> ConversationRecord:
    repository = (
        ConversationRepository(
            db
        )
    )

    try:
        conversation = (
            repository.get_for_owner(
                conversation_id,
                current_user.id,
            )
        )

        deployment_changed = (
            "deployment_name"
            in payload.model_fields_set
        )

        deployment_name = (
            conversation.deployment_name
        )

        model = conversation.model
        profile = conversation.profile
        runtime = conversation.runtime

        if deployment_changed:
            (
                deployment_name,
                model,
                profile,
                runtime,
            ) = _deployment_snapshot(
                deployment_name=(
                    payload.deployment_name
                ),

                current_user=(
                    current_user
                ),

                db=db,
            )

        conversation = (
            repository.update(
                conversation,

                title=(
                    payload.title
                    if (
                        "title"
                        in payload.model_fields_set
                    )
                    else None
                ),

                deployment_name=(
                    deployment_name
                ),

                deployment_changed=(
                    deployment_changed
                ),

                model=model,
                profile=profile,
                runtime=runtime,
            )
        )

    except Exception as exc:
        _raise_repository_error(
            exc
        )

        raise

    return ConversationRecord.model_validate(
        conversation
    )


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_conversation(
    conversation_id: int,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
) -> Response:
    repository = (
        ConversationRepository(
            db
        )
    )

    try:
        conversation = (
            repository.get_for_owner(
                conversation_id,
                current_user.id,
            )
        )

        repository.delete(
            conversation
        )

    except Exception as exc:
        _raise_repository_error(
            exc
        )

        raise

    return Response(
        status_code=204
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=ConversationMessageRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    conversation_id: int,

    payload: ConversationMessageCreate,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
) -> ConversationMessageRecord:
    repository = (
        ConversationRepository(
            db
        )
    )

    try:
        conversation = (
            repository.get_for_owner(
                conversation_id,
                current_user.id,
            )
        )

        message = (
            repository.add_message(
                conversation,
                payload,
            )
        )

    except Exception as exc:
        _raise_repository_error(
            exc
        )

        raise

    return ConversationMessageRecord.model_validate(
        message
    )


@router.post(
    "/{conversation_id}/attachments",
    response_model=ConversationAttachmentRecord,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    conversation_id: int,

    file: UploadFile = File(...),

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
) -> ConversationAttachmentRecord:
    repository = (
        ConversationRepository(
            db
        )
    )

    try:
        conversation = (
            repository.get_for_owner(
                conversation_id,
                current_user.id,
            )
        )

    except Exception as exc:
        _raise_repository_error(
            exc
        )

        raise

    original_name = (
        file.filename or
        "attachment"
    )

    try:
        filename = AttachmentSecurityService.sanitize_filename(
            original_name
        )
    except AttachmentSecurityError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    extension = (
        Path(filename)
        .suffix
        .lower()
    )

    if (
        extension
        not in ALLOWED_ATTACHMENT_EXTENSIONS
    ):
        raise HTTPException(
            status_code=415,

            detail=(
                "Attachment type is not allowed: "
                f"'{extension or 'no extension'}'"
            ),
        )

    content = await file.read(
        MAX_ATTACHMENT_SIZE + 1
    )

    await file.close()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Attachment is empty",
        )

    if len(content) > MAX_ATTACHMENT_SIZE:
        raise HTTPException(
            status_code=413,

            detail=(
                "Attachment exceeds "
                "the 10 MiB limit"
            ),
        )

    digest = hashlib.sha256(
        content
    ).hexdigest()

    try:
        media_type = AttachmentSecurityService.validate(
            filename=filename,
            content=content,
        )
    except AttachmentSecurityError as exc:
        raise HTTPException(
            status_code=415,
            detail=str(exc),
        ) from exc

    try:
        attachment = (
            repository.add_attachment(
                conversation,

                filename=filename,
                media_type=media_type,
                size_bytes=len(
                    content
                ),
                sha256=digest,
                content=content,
            )
        )

    except Exception as exc:
        _raise_repository_error(
            exc
        )

        raise

    return (
        ConversationAttachmentRecord
        .model_validate(
            attachment
        )
    )


@router.get(
    "/{conversation_id}/attachments/{attachment_id}/content",
)
def download_attachment(
    conversation_id: int,
    attachment_id: int,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
) -> Response:
    repository = (
        ConversationRepository(
            db
        )
    )

    try:
        attachment = (
            repository
            .get_attachment_for_owner(
                conversation_id=(
                    conversation_id
                ),

                attachment_id=(
                    attachment_id
                ),

                owner_id=(
                    current_user.id
                ),
            )
        )

    except Exception as exc:
        _raise_repository_error(
            exc
        )

        raise

    encoded_filename = quote(
        attachment.filename
    )

    return Response(
        content=attachment.content,

        media_type=(
            attachment.media_type
        ),

        headers={
            "Content-Disposition": (
                "attachment; "
                "filename*=UTF-8''"
                f"{encoded_filename}"
            ),

            "X-Content-Type-Options": (
                "nosniff"
            ),
        },
    )


@router.delete(
    "/{conversation_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_attachment(
    conversation_id: int,
    attachment_id: int,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
) -> Response:
    repository = (
        ConversationRepository(
            db
        )
    )

    try:
        attachment = (
            repository
            .get_attachment_for_owner(
                conversation_id=(
                    conversation_id
                ),

                attachment_id=(
                    attachment_id
                ),

                owner_id=(
                    current_user.id
                ),
            )
        )

        repository.delete_attachment(
            attachment
        )

    except Exception as exc:
        _raise_repository_error(
            exc
        )

        raise

    return Response(
        status_code=204
    )
