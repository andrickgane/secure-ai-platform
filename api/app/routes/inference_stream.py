from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Generator
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from fastapi.responses import (
    StreamingResponse,
)
from sqlalchemy.orm import Session

from app.core.auth import (
    get_current_user,
)
from app.core.config import (
    Settings,
    get_settings,
)
from app.db.database import (
    SessionLocal,
    get_db,
)
from app.models.user import User
from app.repositories.audit_repository import (
    AuditRepository,
)
from app.repositories.deployment_repository import (
    DeploymentNotFound,
    DeploymentRepository,
    DeploymentRepositoryError,
)
from app.repositories.profile_repository import (
    ProfileNotFound,
)
from app.schemas.inference import (
    ChatCompletionRequest,
)
from app.services.attachment_context_service import (
    AttachmentContextError,
    AttachmentContextInvalid,
    AttachmentContextNotFound,
    AttachmentContextService,
    attachment_context_messages,
)
from app.services.catalog_service import (
    CatalogService,
)
from app.services.profile_engine_service import (
    ProfileEngineError,
    ProfileEngineService,
)
from app.services.profile_policy_service import (
    ProfileLimitExceeded,
    ProfileOverrideNotAllowed,
    ProfilePolicyError,
    ProfilePolicyService,
)


router = APIRouter(
    prefix="/api/v1/deployments",
    tags=["inference"],
)


# ==========================================================
# HELPERS
# ==========================================================


def _is_admin(
    user: User,
) -> bool:
    return user.role in {
        "admin",
        "platform_admin",
    }


def _sse(
    event: str,
    data: dict[str, Any],
) -> str:
    return (
        f"event: {event}\n"
        f"data: {json.dumps(data)}\n\n"
    )


# ==========================================================
# THINKING FILTER
# ==========================================================


class ThinkingStreamFilter:
    """
    Streaming-safe filter for:

        <think>...</think>

    Tags may be split across several runtime chunks.
    """

    OPEN_TAG = "<think>"
    CLOSE_TAG = "</think>"

    def __init__(
        self,
    ) -> None:
        self.buffer = ""
        self.inside_think = False

    @staticmethod
    def _partial_tag_length(
        text: str,
        tag: str,
    ) -> int:
        lowered = text.lower()
        lowered_tag = tag.lower()

        maximum = min(
            len(lowered),
            len(lowered_tag) - 1,
        )

        for length in range(
            maximum,
            0,
            -1,
        ):
            if (
                lowered[-length:]
                == lowered_tag[:length]
            ):
                return length

        return 0

    def feed(
        self,
        content: str,
    ) -> str:
        self.buffer += content

        output: list[str] = []

        while self.buffer:
            lowered = (
                self.buffer.lower()
            )

            if self.inside_think:
                position = lowered.find(
                    self.CLOSE_TAG
                )

                if position >= 0:
                    self.buffer = (
                        self.buffer[
                            position
                            + len(
                                self.CLOSE_TAG
                            ):
                        ]
                    )

                    self.inside_think = (
                        False
                    )

                    continue

                keep = (
                    self._partial_tag_length(
                        self.buffer,
                        self.CLOSE_TAG,
                    )
                )

                if keep:
                    self.buffer = (
                        self.buffer[
                            -keep:
                        ]
                    )

                else:
                    self.buffer = ""

                break

            position = lowered.find(
                self.OPEN_TAG
            )

            if position >= 0:
                output.append(
                    self.buffer[
                        :position
                    ]
                )

                self.buffer = (
                    self.buffer[
                        position
                        + len(
                            self.OPEN_TAG
                        ):
                    ]
                )

                self.inside_think = True

                continue

            keep = (
                self._partial_tag_length(
                    self.buffer,
                    self.OPEN_TAG,
                )
            )

            if keep:
                output.append(
                    self.buffer[
                        :-keep
                    ]
                )

                self.buffer = (
                    self.buffer[
                        -keep:
                    ]
                )

            else:
                output.append(
                    self.buffer
                )

                self.buffer = ""

            break

        return "".join(
            output
        )

    def finish(
        self,
    ) -> str:
        if self.inside_think:
            self.buffer = ""

            return ""

        remaining = self.buffer

        self.buffer = ""

        return remaining


# ==========================================================
# UPSTREAM RUNTIME
# ==========================================================


def _open_runtime_stream(
    *,
    endpoint: str,
    api_key: str,
    runtime: str,
    model: str,
    messages: list[
        dict[str, str]
    ],
    parameters: dict[str, Any],
):
    payload: dict[str, Any] = {
        "model": model,

        "messages": messages,

        "temperature": (
            parameters[
                "temperature"
            ]
        ),

        "max_tokens": (
            parameters[
                "max_tokens"
            ]
        ),

        "top_p": (
            parameters[
                "top_p"
            ]
        ),

        "stream": True,
    }

    # ======================================================
    # STREAMING USAGE
    # ======================================================
    #
    # Both vLLM and llama.cpp can return token usage
    # information in the final streamed event when
    # stream_options.include_usage is enabled.
    if runtime.startswith(
        (
            "vllm",
            "llama-cpp",
        )
    ):
        payload[
            "stream_options"
        ] = {
            "include_usage": True,
        }

    # llama.cpp-specific chat template behavior.
    if runtime.startswith(
        "llama-cpp"
    ):
        payload[
            "chat_template_kwargs"
        ] = {
            "enable_thinking": False,
        }

    upstream_request = (
        urllib.request.Request(
            url=(
                f"{endpoint.rstrip('/')}"
                "/v1/chat/completions"
            ),

            method="POST",

            data=json.dumps(
                payload
            ).encode(
                "utf-8"
            ),

            headers={
                "Content-Type": (
                    "application/json"
                ),

                "Accept": (
                    "text/event-stream"
                ),

                "Authorization": (
                    f"Bearer {api_key}"
                ),
            },
        )
    )

    try:
        return urllib.request.urlopen(
            upstream_request,

            timeout=int(
                parameters.get(
                    "timeout_seconds",
                    120,
                )
            ),
        )

    except urllib.error.HTTPError as exc:
        try:
            body = (
                exc.read()
                .decode(
                    "utf-8"
                )
            )

        except Exception:
            body = ""

        raise HTTPException(
            status_code=502,

            detail=(
                "Inference runtime "
                f"returned HTTP "
                f"{exc.code}: {body}"
            ),
        ) from exc

    except urllib.error.URLError as exc:
        raise HTTPException(
            status_code=502,

            detail=(
                "Inference runtime "
                "is unreachable: "
                f"{exc.reason}"
            ),
        ) from exc

    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,

            detail=(
                "Inference runtime "
                "connection timed out"
            ),
        ) from exc


# ==========================================================
# STREAM GENERATOR
# ==========================================================


def _stream_events(
    *,
    upstream,
    deployment_id: int,
    deployment_name: str,
    model: str,
    profile: str,
    runtime: str,
    actor_user_id: int,
    parameters: dict[str, Any],
) -> Generator[
    str,
    None,
    None,
]:
    started = (
        time.perf_counter()
    )

    first_token_at: (
        float | None
    ) = None

    finish_reason: (
        str | None
    ) = None

    usage: dict[str, Any] = {}

    emitted_characters = 0

    thinking_filter = (
        ThinkingStreamFilter()
    )

    completed = False

    yield _sse(
        "meta",
        {
            "deployment": (
                deployment_name
            ),

            "model": model,

            "profile": profile,

            "runtime": runtime,

            "parameters": {
                "temperature": (
                    parameters[
                        "temperature"
                    ]
                ),

                "max_tokens": (
                    parameters[
                        "max_tokens"
                    ]
                ),

                "top_p": (
                    parameters[
                        "top_p"
                    ]
                ),

                "max_model_len": (
                    parameters[
                        "max_model_len"
                    ]
                ),
            },
        },
    )

    try:
        for raw_line in upstream:
            line = (
                raw_line
                .decode(
                    "utf-8",
                    errors="replace",
                )
                .strip()
            )

            if not line:
                continue

            if not line.startswith(
                "data:"
            ):
                continue

            raw_data = (
                line[5:]
                .strip()
            )

            if (
                raw_data
                == "[DONE]"
            ):
                completed = True

                break

            try:
                chunk = json.loads(
                    raw_data
                )

            except json.JSONDecodeError:
                continue

            chunk_usage = (
                chunk.get(
                    "usage"
                )
            )

            if isinstance(
                chunk_usage,
                dict,
            ):
                usage = chunk_usage

            choices = (
                chunk.get(
                    "choices",
                    [],
                )
            )

            if not choices:
                continue

            first_choice = (
                choices[0]
            )

            reason = (
                first_choice.get(
                    "finish_reason"
                )
            )

            if reason is not None:
                finish_reason = str(
                    reason
                )

            delta = (
                first_choice.get(
                    "delta",
                    {},
                )
            )

            if not isinstance(
                delta,
                dict,
            ):
                continue

            content = (
                delta.get(
                    "content"
                )
            )

            if not isinstance(
                content,
                str,
            ):
                continue

            filtered = (
                thinking_filter.feed(
                    content
                )
            )

            if not filtered:
                continue

            if first_token_at is None:
                first_token_at = (
                    time.perf_counter()
                )

            emitted_characters += len(
                filtered
            )

            yield _sse(
                "delta",
                {
                    "content": (
                        filtered
                    ),
                },
            )

        remaining = (
            thinking_filter.finish()
        )

        if remaining:
            if first_token_at is None:
                first_token_at = (
                    time.perf_counter()
                )

            emitted_characters += len(
                remaining
            )

            yield _sse(
                "delta",
                {
                    "content": (
                        remaining
                    ),
                },
            )

        completed = True

    except GeneratorExit:
        raise

    except Exception as exc:
        yield _sse(
            "error",
            {
                "message": (
                    "Streaming inference "
                    f"failed: {exc}"
                ),
            },
        )

        return

    finally:
        try:
            upstream.close()

        except Exception:
            pass

    ended = (
        time.perf_counter()
    )

    latency_ms = int(
        (
            ended
            - started
        )
        * 1000
    )

    first_token_latency_ms = (
        int(
            (
                first_token_at
                - started
            )
            * 1000
        )
        if first_token_at
        is not None
        else None
    )

    prompt_tokens = (
        usage.get(
            "prompt_tokens"
        )
    )

    completion_tokens = (
        usage.get(
            "completion_tokens"
        )
    )

    total_tokens = (
        usage.get(
            "total_tokens"
        )
    )


    # ======================================================
    # DERIVED PERFORMANCE METRICS
    # ======================================================

    generation_duration_ms = None

    if (
        first_token_latency_ms
        is not None
    ):
        generation_duration_ms = max(
            latency_ms
            - first_token_latency_ms,
            0,
        )

    generation_tokens_per_second = None

    if (
        isinstance(
            completion_tokens,
            int,
        )
        and generation_duration_ms
        and generation_duration_ms > 0
    ):
        generation_tokens_per_second = round(
            completion_tokens
            / (
                generation_duration_ms
                / 1000
            ),
            2,
        )

    output_tokens_per_second = None

    if (
        isinstance(
            completion_tokens,
            int,
        )
        and latency_ms > 0
    ):
        output_tokens_per_second = round(
            completion_tokens
            / (
                latency_ms
                / 1000
            ),
            2,
        )

    if completed:
        audit_db = (
            SessionLocal()
        )

        try:
            AuditRepository(
                audit_db
            ).create(
                actor_user_id=(
                    actor_user_id
                ),

                action=(
                    "CHAT_COMPLETION_STREAM"
                ),

                resource_type=(
                    "deployment"
                ),

                resource_name=(
                    deployment_name
                ),

                details={
                    "deployment_id": (
                        deployment_id
                    ),

                    "model": model,

                    "profile": profile,

                    "runtime": runtime,

                    "effective_parameters": {
                        "temperature": (
                            parameters[
                                "temperature"
                            ]
                        ),

                        "max_tokens": (
                            parameters[
                                "max_tokens"
                            ]
                        ),

                        "top_p": (
                            parameters[
                                "top_p"
                            ]
                        ),

                        "max_model_len": (
                            parameters[
                                "max_model_len"
                            ]
                        ),
                    },

                    "streaming": True,

                    "latency_ms": (
                        latency_ms
                    ),

                    "first_token_latency_ms": (
                        first_token_latency_ms
                    ),

                    "generation_duration_ms": (
                        generation_duration_ms
                    ),

                    "generation_tokens_per_second": (
                        generation_tokens_per_second
                    ),

                    "output_tokens_per_second": (
                        output_tokens_per_second
                    ),

                    "emitted_characters": (
                        emitted_characters
                    ),

                    "prompt_tokens": (
                        prompt_tokens
                    ),

                    "completion_tokens": (
                        completion_tokens
                    ),

                    "total_tokens": (
                        total_tokens
                    ),
                },
            )

        finally:
            audit_db.close()

    yield _sse(
        "done",
        {
            "finish_reason": (
                finish_reason
            ),

            "prompt_tokens": (
                prompt_tokens
            ),

            "completion_tokens": (
                completion_tokens
            ),

            "total_tokens": (
                total_tokens
            ),

            "latency_ms": (
                latency_ms
            ),

            "first_token_latency_ms": (
                first_token_latency_ms
            ),

            "generation_duration_ms": (
                generation_duration_ms
            ),

            "generation_tokens_per_second": (
                generation_tokens_per_second
            ),

            "output_tokens_per_second": (
                output_tokens_per_second
            ),
        },
    )


# ==========================================================
# ROUTE
# ==========================================================


@router.post(
    "/{deployment_name}/chat/completions/stream",
)
def chat_completion_stream(
    deployment_name: str,

    request: ChatCompletionRequest,

    current_user: User = Depends(
        get_current_user
    ),

    settings: Settings = Depends(
        get_settings
    ),

    db: Session = Depends(
        get_db
    ),
) -> StreamingResponse:
    repository = (
        DeploymentRepository(
            db
        )
    )

    # ======================================================
    # DEPLOYMENT / RBAC
    # ======================================================

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
                repository
                .get_for_owner(
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

    if deployment.status not in {
        "ready",
        "deployed",
    }:
        raise HTTPException(
            status_code=409,

            detail=(
                f"Deployment "
                f"'{deployment.name}' "
                "is not ready"
            ),
        )

    if not deployment.endpoint:
        raise HTTPException(
            status_code=409,

            detail=(
                "Deployment has no "
                "runtime endpoint"
            ),
        )

    # ======================================================
    # EFFECTIVE PROFILE
    # ======================================================

    catalog = CatalogService(
        settings.catalog_path
    )

    profile_engine = (
        ProfileEngineService(
            catalog=catalog,
            db=db,
        )
    )

    try:
        profile_definition = (
            profile_engine.resolve(
                deployment.profile
            )
        )

    except ProfileNotFound as exc:
        raise HTTPException(
            status_code=409,

            detail=(
                "Deployment references "
                f"profile "
                f"'{deployment.profile}', "
                "but that profile no "
                "longer exists"
            ),
        ) from exc

    except ProfileEngineError as exc:
        raise HTTPException(
            status_code=500,

            detail=(
                "Could not resolve "
                "deployment profile: "
                f"{exc}"
            ),
        ) from exc

    # ======================================================
    # PROFILE POLICY
    # ======================================================

    try:
        parameters = (
            ProfilePolicyService()
            .resolve_inference_parameters(
                profile_definition,

                temperature=(
                    request.temperature
                ),

                max_tokens=(
                    request.max_tokens
                ),

                top_p=(
                    request.top_p
                ),
            )
        )

    except (
        ProfileOverrideNotAllowed,
        ProfileLimitExceeded,
        ProfilePolicyError,
    ) as exc:
        raise HTTPException(
            status_code=(
                status
                .HTTP_422_UNPROCESSABLE_ENTITY
            ),

            detail=str(exc),
        ) from exc

    messages = [
        {
            "role": item.role,
            "content": item.content,
        }

        for item
        in request.messages
    ]


    # ======================================================
    # ATTACHMENT CONTEXT
    # ======================================================

    if request.attachment_ids:
        try:
            attachment_context = (
                AttachmentContextService(
                    db
                ).build(
                    owner_id=(
                        current_user.id
                    ),

                    conversation_id=(
                        request.conversation_id
                    ),

                    attachment_ids=(
                        request.attachment_ids
                    ),
                )
            )

        except AttachmentContextNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail=str(exc),
            ) from exc

        except AttachmentContextInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        except AttachmentContextError as exc:
            raise HTTPException(
                status_code=500,
                detail=str(exc),
            ) from exc

        if attachment_context:
            messages[0:0] = (
                attachment_context_messages(
                    attachment_context
                )
            )


    api_key = (
        settings.llama_cpp_api_key

        if deployment.runtime.startswith(
            "llama-cpp"
        )

        else settings.vllm_api_key
    )

    # Connect upstream BEFORE sending our HTTP 200.
    # Runtime connection errors therefore remain proper
    # HTTP 502 / 504 responses.
    upstream = (
        _open_runtime_stream(
            endpoint=(
                deployment.endpoint
            ),

            api_key=api_key,

            runtime=(
                deployment.runtime
            ),

            model=(
                deployment.model
            ),

            messages=messages,

            parameters=parameters,
        )
    )

    return StreamingResponse(
        _stream_events(
            upstream=upstream,

            deployment_id=(
                deployment.id
            ),

            deployment_name=(
                deployment.name
            ),

            model=(
                deployment.model
            ),

            profile=(
                deployment.profile
            ),

            runtime=(
                deployment.runtime
            ),

            actor_user_id=(
                current_user.id
            ),

            parameters=parameters,
        ),

        media_type=(
            "text/event-stream"
        ),

        headers={
            "Cache-Control": (
                "no-cache"
            ),

            "X-Accel-Buffering": (
                "no"
            ),
        },
    )
