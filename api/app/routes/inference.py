from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.core.auth import (
    get_current_user,
)
from app.core.config import (
    Settings,
    get_settings,
)
from app.db.database import get_db
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
    ChatCompletionResponse,
    EffectiveInferenceParameters,
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


def _is_admin(
    user: User,
) -> bool:
    return user.role in {
        "admin",
        "platform_admin",
    }


# ==========================================================
# THINKING FILTER
# ==========================================================


def _clean_model_content(
    content: str,
) -> str:
    """
    Prevent model reasoning blocks such as
    <think>...</think> from being exposed
    to the end-user UI.
    """

    cleaned = re.sub(
        r"<think>.*?</think>",
        "",
        content,
        flags=(
            re.DOTALL
            | re.IGNORECASE
        ),
    )

    return cleaned.strip()


# ==========================================================
# OPENAI-COMPATIBLE RUNTIME CLIENT
# ==========================================================


def _call_vllm(
    *,
    endpoint: str,
    api_key: str,
    runtime: str,
    model: str,
    messages: list[
        dict[str, str]
    ],
    parameters: dict,
) -> dict:
    """
    Call an OpenAI-compatible inference runtime.

    Currently supported:
    - vLLM
    - llama.cpp server

    Both expose /v1/chat/completions.
    """

    payload = {
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

        "stream": False,
    }

    if runtime == "llama-cpp-metal":
        payload[
            "chat_template_kwargs"
        ] = {
            "enable_thinking": False,
        }

    request = urllib.request.Request(
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
                "application/json"
            ),

            "Authorization": (
                f"Bearer {api_key}"
            ),
        },
    )

    try:
        with urllib.request.urlopen(
            request,

            timeout=int(
                parameters.get(
                    "timeout_seconds",
                    120,
                )
            ),
        ) as response:
            raw = response.read()

    except urllib.error.HTTPError as exc:
        try:
            error_body = (
                exc.read()
                .decode(
                    "utf-8"
                )
            )

        except Exception:
            error_body = ""

        raise RuntimeError(
            "Inference runtime returned "
            f"HTTP {exc.code}: "
            f"{error_body}"
        ) from exc

    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Inference runtime is "
            "unreachable: "
            f"{exc.reason}"
        ) from exc

    except TimeoutError as exc:
        raise RuntimeError(
            "Inference request timed out"
        ) from exc

    try:
        return json.loads(
            raw
        )

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Inference runtime returned "
            "invalid JSON"
        ) from exc


# ==========================================================
# CHAT COMPLETION
# ==========================================================


@router.post(
    "/{deployment_name}/chat/completions",
    response_model=(
        ChatCompletionResponse
    ),
)
def chat_completion(
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
) -> ChatCompletionResponse:
    repository = (
        DeploymentRepository(
            db
        )
    )

    catalog = CatalogService(
        settings.catalog_path
    )

    profile_engine = (
        ProfileEngineService(
            catalog=catalog,
            db=db,
        )
    )

    profile_policy = (
        ProfilePolicyService()
    )

    # ======================================================
    # DEPLOYMENT + RBAC
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
                "but that profile no longer "
                "exists"
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
    # PROFILE-GOVERNED INFERENCE PARAMETERS
    # ======================================================

    try:
        parameters = (
            profile_policy
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

    # ======================================================
    # MESSAGES
    # ======================================================

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


    # ======================================================
    # INFERENCE REQUEST
    # ======================================================

    try:
        result = _call_vllm(
            endpoint=(
                deployment.endpoint
            ),

            api_key=(
                (
                    settings
                    .llama_cpp_api_key
                )
                if (
                    deployment.runtime
                    == "llama-cpp-metal"
                )
                else (
                    settings
                    .vllm_api_key
                )
            ),

            runtime=(
                deployment.runtime
            ),

            model=(
                deployment.model
            ),

            messages=messages,

            parameters=parameters,
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    # ======================================================
    # RESPONSE VALIDATION
    # ======================================================

    choices = result.get(
        "choices",
        [],
    )

    if not choices:
        raise HTTPException(
            status_code=502,

            detail=(
                "Inference runtime "
                "returned no completion"
            ),
        )

    first_choice = (
        choices[0]
    )

    assistant_message = (
        first_choice.get(
            "message",
            {},
        )
    )

    content = (
        assistant_message.get(
            "content"
        )
    )

    if not isinstance(
        content,
        str,
    ):
        raise HTTPException(
            status_code=502,

            detail=(
                "Inference runtime "
                "returned invalid content"
            ),
        )

    content = (
        _clean_model_content(
            content
        )
    )

    # ======================================================
    # TOKEN USAGE
    # ======================================================

    usage = result.get(
        "usage",
        {},
    )

    if not isinstance(
        usage,
        dict,
    ):
        usage = {}

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
    # AUDIT
    # ======================================================

    AuditRepository(
        db
    ).create(
        actor_user_id=(
            current_user.id
        ),

        action=(
            "CHAT_COMPLETION"
        ),

        resource_type=(
            "deployment"
        ),

        resource_name=(
            deployment.name
        ),

        details={
            "deployment_id": (
                deployment.id
            ),

            "model": (
                deployment.model
            ),

            "profile": (
                deployment.profile
            ),

            "runtime": (
                deployment.runtime
            ),

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

    # ======================================================
    # API RESPONSE
    # ======================================================

    return ChatCompletionResponse(
        deployment=(
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

        content=content,

        finish_reason=(
            first_choice.get(
                "finish_reason"
            )
        ),

        prompt_tokens=(
            prompt_tokens
        ),

        completion_tokens=(
            completion_tokens
        ),

        total_tokens=(
            total_tokens
        ),

        parameters=(
            EffectiveInferenceParameters(
                temperature=(
                    parameters[
                        "temperature"
                    ]
                ),

                max_tokens=(
                    parameters[
                        "max_tokens"
                    ]
                ),

                top_p=(
                    parameters[
                        "top_p"
                    ]
                ),

                max_model_len=(
                    parameters[
                        "max_model_len"
                    ]
                ),
            )
        ),
    )
