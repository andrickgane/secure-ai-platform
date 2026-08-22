from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.model_request import ModelRequest
from app.repositories.profile_repository import (
    ProfileNotFound,
)
from app.schemas.deployment import (
    DeploymentContext,
    DeploymentCreate,
)
from app.services.catalog_service import (
    CatalogError,
    CatalogService,
)
from app.services.profile_engine_service import (
    ProfileEngineError,
    ProfileEngineService,
)
from app.services.runtime_selector_service import (
    RuntimeSelectorService,
)
from app.services.trusted_model_service import (
    TrustedModelService,
)


class DeploymentServiceError(Exception):
    """Deployment context resolution error."""


class DeploymentService:
    """
    Resolve a deployment request into a trusted,
    platform-controlled deployment context.

    Published database models override static catalog
    model definitions.

    Profiles are resolved through ProfileEngineService,
    allowing both:

    - immutable built-in YAML profiles
    - persistent custom PostgreSQL profiles
    """

    def __init__(
        self,
        *,
        catalog: CatalogService,
        trusted_models: TrustedModelService,
        runtime_selector: RuntimeSelectorService,
        db: Session,
    ) -> None:
        self.catalog = catalog
        self.trusted_models = trusted_models
        self.runtime_selector = (
            runtime_selector
        )
        self.db = db

        self.profile_engine = (
            ProfileEngineService(
                catalog=catalog,
                db=db,
            )
        )

    # ======================================================
    # MODEL RESOLUTION
    # ======================================================

    def _load_published_model(
        self,
        model_id: str,
    ) -> dict[str, Any] | None:
        statement = (
            select(ModelRequest)
            .where(
                ModelRequest.catalog_model_id
                == model_id
            )
            .where(
                ModelRequest.status
                == "published"
            )
            .where(
                ModelRequest.artifact_reference
                .is_not(None)
            )
            .where(
                ModelRequest.artifact_digest
                .is_not(None)
            )
            .order_by(
                ModelRequest.updated_at.desc()
            )
            .limit(1)
        )

        row = (
            self.db.execute(
                statement
            )
            .scalars()
            .first()
        )

        if row is None:
            return None

        reference = (
            row.artifact_reference
        )

        digest = (
            row.artifact_digest
        )

        if (
            not reference
            or not digest
        ):
            raise DeploymentServiceError(
                f"Published model "
                f"'{model_id}' has "
                "incomplete OCI metadata"
            )

        (
            ref_without_digest,
            separator,
            ref_digest,
        ) = reference.partition("@")

        if (
            not separator
            or ref_digest != digest
            or "/"
            not in ref_without_digest
        ):
            raise DeploymentServiceError(
                f"Published model "
                f"'{model_id}' has an "
                "invalid immutable OCI "
                "reference"
            )

        registry, oci_repository = (
            ref_without_digest.split(
                "/",
                1,
            )
        )

        return {
            "apiVersion": (
                "platform.secureai.io/"
                "v1alpha1"
            ),

            "kind": "AIModel",

            "metadata": {
                "name": model_id,
            },

            "spec": {
                "displayName": (
                    row.repository
                    .rsplit(
                        "/",
                        1,
                    )[-1]
                    .replace(
                        "-",
                        " ",
                    )
                ),

                "description": (
                    "Trusted model published "
                    "by the AI supply chain"
                ),

                "provider": (
                    row.provider
                ),

                "repository": (
                    row.repository
                ),

                "revision": (
                    row.revision
                ),

                "capabilities": [
                    "chat",
                    "text-generation",
                ],

                "defaultProfile": (
                    row.requested_profile
                    or "interactive"
                ),

                # Compatibility is resolved
                # dynamically from AIRuntime
                # definitions.
                "supportedRuntimes": [],

                "artifactFormat": (
                    row.artifact_format
                ),

                "architecture": (
                    row.architecture
                ),

                "quantization": (
                    row.quantization
                ),

                "security": {
                    "approved": True,
                },

                "artifact": {
                    "source": (
                        "oci-registry"
                    ),

                    "registry": registry,

                    "repository": (
                        oci_repository
                    ),

                    "digest": digest,

                    "sourceRevision": (
                        row.revision
                    ),


                    "signature": {
                        "required": True,
                    },
                },
            },
        }

    def _load_model_definition(
        self,
        model_id: str,
    ) -> dict[str, Any]:
        published = (
            self._load_published_model(
                model_id
            )
        )

        if published is not None:
            return published

        return (
            self.catalog
            .load_approved_model(
                model_id
            )
        )

    # ======================================================
    # PROFILE RESOLUTION
    # ======================================================

    def _load_profile_definition(
        self,
        profile_id: str,
    ) -> dict[str, Any]:
        """
        Resolve a built-in or custom profile into
        its effective AIProfile definition.
        """

        try:
            return (
                self.profile_engine
                .resolve(
                    profile_id
                )
            )

        except ProfileNotFound as exc:
            raise DeploymentServiceError(
                f"Profile "
                f"'{profile_id}' "
                "was not found"
            ) from exc

        except ProfileEngineError as exc:
            raise DeploymentServiceError(
                f"Profile "
                f"'{profile_id}' "
                "could not be resolved: "
                f"{exc}"
            ) from exc

    # ======================================================
    # CONTEXT
    # ======================================================

    def create_context(
        self,
        request: DeploymentCreate,
    ) -> DeploymentContext:
        model_definition = (
            self._load_model_definition(
                request.model
            )
        )

        model_spec = (
            model_definition.get(
                "spec",
                {},
            )
        )

        if not isinstance(
            model_spec,
            dict,
        ):
            raise CatalogError(
                f"Model "
                f"'{request.model}' "
                "has invalid spec"
            )

        repository = (
            model_spec.get(
                "repository"
            )
        )

        if not repository:
            raise DeploymentServiceError(
                f"Model "
                f"'{request.model}' "
                "does not define repository"
            )

        # ==================================================
        # TRUSTED MODEL ARTIFACT
        # ==================================================

        artifact = (
            model_spec.get(
                "artifact"
            )
        )

        if not isinstance(
            artifact,
            dict,
        ):
            raise DeploymentServiceError(
                f"Model "
                f"'{request.model}' "
                "does not define a valid "
                "trusted artifact"
            )

        trusted = (
            self.trusted_models
            .verify(
                artifact
            )
        )

        artifact_reference = (
            trusted.get(
                "reference"
            )
        )

        artifact_digest = (
            trusted.get(
                "digest"
            )
        )

        if (
            not artifact_reference
            or not artifact_digest
        ):
            raise DeploymentServiceError(
                "Trusted model verification "
                "returned incomplete "
                "OCI metadata"
            )

        # ==================================================
        # EFFECTIVE PROFILE
        # ==================================================

        profile_definition = (
            self._load_profile_definition(
                request.profile
            )
        )

        profile_spec = (
            profile_definition.get(
                "spec",
                {},
            )
        )

        if not isinstance(
            profile_spec,
            dict,
        ):
            raise DeploymentServiceError(
                f"Profile "
                f"'{request.profile}' "
                "has invalid spec"
            )

        # ==================================================
        # RUNTIME CAPACITY
        # ==================================================

        defaults = (
            profile_spec.get(
                "defaults",
                {},
            )
        )

        if not isinstance(
            defaults,
            dict,
        ):
            raise DeploymentServiceError(
                f"Profile "
                f"'{request.profile}' "
                "has invalid defaults"
            )

        profile_default_capacity = int(
            defaults.get(
                "maxModelLen",
                4096,
            )
        )

        max_model_len = (
            profile_default_capacity
        )

        if (
            request.runtime_capacity
            is not None
        ):
            security = (
                profile_spec.get(
                    "security",
                    {},
                )
            )

            if not isinstance(
                security,
                dict,
            ):
                raise DeploymentServiceError(
                    f"Profile "
                    f"'{request.profile}' "
                    "has invalid security policy"
                )

            allow_overrides = (
                security.get(
                    "allowUserOverrides",
                    False,
                )
                is True
            )

            overridable_raw = (
                security.get(
                    "overridableParameters",
                    [],
                )
            )

            if not isinstance(
                overridable_raw,
                list,
            ):
                raise DeploymentServiceError(
                    f"Profile "
                    f"'{request.profile}' "
                    "has invalid "
                    "overridableParameters"
                )

            overridable = {
                str(item)
                for item
                in overridable_raw
            }

            if (
                not allow_overrides
                or "runtimeCapacity"
                not in overridable
            ):
                raise DeploymentServiceError(
                    "Runtime capacity override "
                    "is not allowed by profile "
                    f"'{request.profile}'"
                )

            requested_capacity = int(
                request.runtime_capacity
            )

            if (
                requested_capacity
                < profile_default_capacity
            ):
                raise DeploymentServiceError(
                    f"Runtime capacity "
                    f"{requested_capacity} "
                    "is below profile default "
                    f"{profile_default_capacity}"
                )

            profile_limits = (
                profile_spec.get(
                    "limits",
                    {},
                )
            )

            if not isinstance(
                profile_limits,
                dict,
            ):
                raise DeploymentServiceError(
                    f"Profile "
                    f"'{request.profile}' "
                    "has invalid limits"
                )

            maximum_capacity = int(
                profile_limits.get(
                    "maxModelLen",
                    profile_default_capacity,
                )
            )

            if (
                requested_capacity
                > maximum_capacity
            ):
                raise DeploymentServiceError(
                    f"Runtime capacity "
                    f"{requested_capacity} "
                    "exceeds profile maximum "
                    f"{maximum_capacity}"
                )

            max_model_len = (
                requested_capacity
            )

        # Runtime selection must evaluate the
        # effective deployment capacity, not only
        # the original profile default.
        selection_profile_spec = dict(
            profile_spec
        )

        selection_defaults = dict(
            defaults
        )

        selection_defaults[
            "maxModelLen"
        ] = max_model_len

        selection_profile_spec[
            "defaults"
        ] = selection_defaults

        # ==================================================
        # RUNTIME SELECTION
        # ==================================================

        runtime_name = (
            self.runtime_selector
            .select(
                requested_runtime=(
                    request.runtime
                ),

                model_name=(
                    request.model
                ),

                model_spec=(
                    model_spec
                ),

                profile_spec=(
                    selection_profile_spec
                ),
            )
        )

        runtime_definition = (
            self.catalog.load(
                "runtimes",
                runtime_name,
            )
        )

        runtime_spec = (
            runtime_definition.get(
                "spec",
                {},
            )
        )

        if not isinstance(
            runtime_spec,
            dict,
        ):
            raise CatalogError(
                f"Runtime "
                f"'{runtime_name}' "
                "has invalid spec"
            )

        # ==================================================
        # PROFILE RESOURCES
        # ==================================================

        resources = (
            profile_spec.get(
                "resources",
                {},
            )
        )

        if not isinstance(
            resources,
            dict,
        ):
            resources = {}

        requests = (
            resources.get(
                "requests",
                {},
            )
        )

        limits = (
            resources.get(
                "limits",
                {},
            )
        )

        if not isinstance(
            requests,
            dict,
        ):
            requests = {}

        if not isinstance(
            limits,
            dict,
        ):
            limits = {}

        cpu_request = str(
            requests.get(
                "cpu",
                "500m",
            )
        )

        memory_request = str(
            requests.get(
                "memory",
                "1Gi",
            )
        )

        cpu_limit = str(
            limits.get(
                "cpu",
                "2",
            )
        )

        memory_limit = str(
            limits.get(
                "memory",
                "4Gi",
            )
        )

        # ==================================================
        # PROFILE STORAGE
        # ==================================================

        storage = (
            profile_spec.get(
                "storage",
                {},
            )
        )

        if not isinstance(
            storage,
            dict,
        ):
            storage = {}

        model_cache = (
            storage.get(
                "modelCache",
                {},
            )
        )

        if not isinstance(
            model_cache,
            dict,
        ):
            model_cache = {}

        model_cache_enabled = bool(
            model_cache.get(
                "enabled",
                True,
            )
        )

        model_cache_size = str(
            model_cache.get(
                "size",
                "70Gi",
            )
        )

        model_cache_mount_path = str(
            model_cache.get(
                "mountPath",
                "/models/model",
            )
        )

        # ==================================================
        # RUNTIME ENDPOINT
        # ==================================================

        deployment_mode = str(
            runtime_spec.get(
                "deploymentMode",
                "unknown",
            )
        )

        external_endpoint = (
            self.runtime_selector
            ._normalize_endpoint(
                runtime_spec.get(
                    "endpoint"
                )
            )
        )

        if (
            deployment_mode
            == "external"
            and not external_endpoint
        ):
            raise DeploymentServiceError(
                f"External runtime "
                f"'{runtime_name}' "
                "has no valid inference "
                "endpoint"
            )

        # ==================================================
        # RUNTIME CONTAINER
        # ==================================================

        container = (
            runtime_spec.get(
                "container",
                {},
            )
        )

        if not isinstance(
            container,
            dict,
        ):
            container = {}

        image = (
            runtime_spec.get(
                "image"
            )
            or container.get(
                "image"
            )
        )

        if image is not None:
            image = str(
                image
            )

        raw_port = (
            runtime_spec.get(
                "port"
            )
        )

        if raw_port is None:
            raw_port = (
                container.get(
                    "port"
                )
            )

        port = (
            int(raw_port)
            if raw_port is not None
            else None
        )

        # ==================================================
        # PROFILE REPLICAS
        # ==================================================

        replicas = int(
            profile_spec.get(
                "replicas",
                1,
            )
        )

        # ==================================================
        # HARDWARE
        # ==================================================

        hardware = (
            runtime_spec.get(
                "hardware",
                {},
            )
        )

        if not isinstance(
            hardware,
            dict,
        ):
            hardware = {}

        accelerator = (
            hardware.get(
                "accelerator"
            )
        )

        accelerator = (
            str(accelerator)
            if accelerator is not None
            else None
        )

        gpu_count = int(
            hardware.get(
                "gpuCount",
                0,
            )
        )

        # ==================================================
        # SCHEDULING
        # ==================================================

        scheduling = (
            runtime_spec.get(
                "scheduling",
                {},
            )
        )

        if not isinstance(
            scheduling,
            dict,
        ):
            scheduling = {}

        node_selector = (
            scheduling.get(
                "nodeSelector",
                {},
            )
        )

        if not isinstance(
            node_selector,
            dict,
        ):
            node_selector = {}

        normalized_selector = {
            str(key): str(value)
            for key, value
            in node_selector.items()
        }

        # ==================================================
        # FINAL CONTEXT
        # ==================================================

        return DeploymentContext(
            name=request.name,

            model=request.model,

            repository=str(
                repository
            ),

            profile=request.profile,

            runtime=runtime_name,

            deployment_mode=(
                deployment_mode
            ),

            external_endpoint=(
                external_endpoint
            ),

            model_artifact_reference=str(
                artifact_reference
            ),

            model_artifact_digest=str(
                artifact_digest
            ),

            image=image,

            port=port,

            replicas=replicas,

            cpu_request=cpu_request,

            memory_request=(
                memory_request
            ),

            cpu_limit=cpu_limit,

            memory_limit=(
                memory_limit
            ),

            accelerator=accelerator,

            gpu_count=gpu_count,

            node_selector=(
                normalized_selector
            ),

            max_model_len=(
                max_model_len
            ),

            model_cache_enabled=(
                model_cache_enabled
            ),

            model_cache_size=(
                model_cache_size
            ),

            model_cache_mount_path=(
                model_cache_mount_path
            ),
        )
