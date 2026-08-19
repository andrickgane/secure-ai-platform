from __future__ import annotations

import socket
from typing import Any

from app.services.catalog_service import (
    CatalogError,
    CatalogService,
)
from app.services.kubernetes_service import (
    KubernetesService,
)


class RuntimeSelectionError(Exception):
    pass


class RuntimeCompatibilityError(
    RuntimeSelectionError
):
    pass


class RuntimeUnavailableError(
    RuntimeSelectionError
):
    pass


class RuntimeSelectorService:
    """
    Runtime compatibility, availability and automatic
    selection engine.

    Compatibility is declared by catalog/runtimes/*.yaml.

    Availability is evaluated separately:
      - external runtimes: SSH management channel
      - Kubernetes NVIDIA runtimes: GPU capacity

    Static legacy models without artifactFormat may still
    use supportedRuntimes during the V2 transition.
    """

    def __init__(
        self,
        *,
        catalog: CatalogService,
        kubernetes: KubernetesService,
        vllm_api_key: str,
    ) -> None:
        self.catalog = catalog
        self.kubernetes = kubernetes
        self.vllm_api_key = vllm_api_key

    # =========================================================
    # PUBLIC SELECTION
    # =========================================================

    def select(
        self,
        *,
        requested_runtime: str,
        model_name: str,
        model_spec: dict[str, Any],
        profile_spec: dict[str, Any],
    ) -> str:
        compatible = self._compatible_runtimes(
            model_name=model_name,
            model_spec=model_spec,
            profile_spec=profile_spec,
        )

        if requested_runtime != "auto":
            if requested_runtime not in compatible:
                raise RuntimeCompatibilityError(
                    f"Runtime '{requested_runtime}' "
                    f"is not compatible with model "
                    f"'{model_name}' and the selected profile"
                )

            definition = self.catalog.load(
                "runtimes",
                requested_runtime,
            )

            runtime_spec = definition.get(
                "spec",
                {},
            )

            if (
                not isinstance(runtime_spec, dict)
                or not self._is_available(
                    runtime_spec
                )
            ):
                raise RuntimeUnavailableError(
                    f"Runtime '{requested_runtime}' "
                    "is compatible but currently unavailable"
                )

            return requested_runtime

        runtime_policy = self._runtime_policy(
            profile_spec
        )

        preferred = runtime_policy.get(
            "preferredRuntimes",
            [],
        )

        if not isinstance(preferred, list):
            raise CatalogError(
                "Profile preferredRuntimes "
                "must be a list"
            )

        definitions = (
            self._runtime_definitions()
        )

        preferred_order = [
            str(name)
            for name in preferred
            if str(name) in compatible
        ]

        remaining = sorted(
            (
                name
                for name in compatible
                if name not in preferred_order
            ),
            key=lambda name: (
                -self._runtime_priority(
                    definitions.get(
                        name,
                        {},
                    )
                ),
                name,
            ),
        )

        order = (
            preferred_order
            + remaining
        )

        checked: list[str] = []

        for name in order:
            runtime_spec = definitions.get(
                name
            )

            if runtime_spec is None:
                definition = self.catalog.load(
                    "runtimes",
                    name,
                )

                runtime_spec = definition.get(
                    "spec",
                    {},
                )

            if (
                isinstance(runtime_spec, dict)
                and self._is_available(
                    runtime_spec
                )
            ):
                return name

            checked.append(name)

        raise RuntimeUnavailableError(
            "No compatible runtime is currently "
            "available. Compatible runtimes checked: "
            + ", ".join(checked)
        )

    # =========================================================
    # COMPATIBILITY ENGINE
    # =========================================================

    def _compatible_runtimes(
        self,
        *,
        model_name: str,
        model_spec: dict[str, Any],
        profile_spec: dict[str, Any],
    ) -> set[str]:
        artifact_format = self._normalize(
            model_spec.get(
                "artifactFormat"
            )
        )

        quantization = self._normalize(
            model_spec.get(
                "quantization"
            )
        )

        architecture = self._normalize(
            model_spec.get(
                "architecture"
            )
        )

        compatible: set[str] = set()

        # -----------------------------------------------------
        # V2 dynamic compatibility engine
        # -----------------------------------------------------

        if artifact_format:
            for definition in (
                self.catalog.list_items(
                    "runtimes"
                )
            ):
                metadata = definition.get(
                    "metadata",
                    {},
                )

                runtime_spec = definition.get(
                    "spec",
                    {},
                )

                if (
                    not isinstance(
                        metadata,
                        dict,
                    )
                    or not isinstance(
                        runtime_spec,
                        dict,
                    )
                ):
                    continue

                runtime_name = metadata.get(
                    "name"
                )

                if not runtime_name:
                    continue

                security = runtime_spec.get(
                    "security",
                    {},
                )

                if not isinstance(
                    security,
                    dict,
                ):
                    security = {}

                if (
                    security.get(
                        "approved",
                        True,
                    )
                    is not True
                ):
                    continue

                if self._runtime_matches_model(
                    runtime_spec=runtime_spec,
                    artifact_format=artifact_format,
                    quantization=quantization,
                    architecture=architecture,
                ):
                    compatible.add(
                        str(runtime_name)
                    )

        # -----------------------------------------------------
        # Legacy/static model compatibility
        # -----------------------------------------------------

        else:
            declared = model_spec.get(
                "supportedRuntimes",
                [],
            )

            if not isinstance(
                declared,
                list,
            ):
                raise CatalogError(
                    "Model supportedRuntimes "
                    "must be a list"
                )

            compatible = {
                str(name)
                for name in declared
            }

        if not compatible:
            raise RuntimeCompatibilityError(
                "No catalog runtime is compatible "
                f"with model '{model_name}' "
                f"(format={artifact_format or 'unknown'}, "
                f"quantization={quantization or 'unknown'}, "
                f"architecture={architecture or 'unknown'})"
            )

        runtime_policy = self._runtime_policy(
            profile_spec
        )

        allowed = runtime_policy.get(
            "allowedRuntimes",
            [],
        )

        if not isinstance(
            allowed,
            list,
        ):
            raise CatalogError(
                "Profile allowedRuntimes "
                "must be a list"
            )

        if allowed:
            allowed_set = {
                str(name)
                for name in allowed
            }

            compatible &= allowed_set

        if not compatible:
            raise RuntimeCompatibilityError(
                "No runtime is compatible with both "
                f"model '{model_name}' "
                "and the selected profile"
            )

        return compatible

    @classmethod
    def _runtime_matches_model(
        cls,
        *,
        runtime_spec: dict[str, Any],
        artifact_format: str,
        quantization: str | None,
        architecture: str | None,
    ) -> bool:
        compatibility = runtime_spec.get(
            "compatibility",
            {},
        )

        if not isinstance(
            compatibility,
            dict,
        ):
            return False

        formats = cls._normalized_set(
            compatibility.get(
                "artifactFormats",
                [],
            )
        )

        if (
            not formats
            or artifact_format not in formats
        ):
            return False

        quantizations = cls._normalized_set(
            compatibility.get(
                "quantizations",
                [],
            )
        )

        if (
            quantization
            and quantizations
            and quantization
            not in quantizations
        ):
            return False

        architectures = cls._normalized_set(
            compatibility.get(
                "architectures",
                [],
            )
        )

        if (
            architecture
            and architectures
            and architecture
            not in architectures
        ):
            return False

        return True

    # =========================================================
    # COMPATIBILITY EXPLANATION API
    # =========================================================

    def inspect_compatibility(
        self,
        *,
        model_name: str,
        model_spec: dict[str, Any],
        profile_spec: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Explain compatibility and availability without
        deploying or activating any runtime.
        """

        artifact_format = self._normalize(
            model_spec.get(
                "artifactFormat"
            )
        )

        quantization = self._normalize(
            model_spec.get(
                "quantization"
            )
        )

        architecture = self._normalize(
            model_spec.get(
                "architecture"
            )
        )

        legacy_runtimes = model_spec.get(
            "supportedRuntimes",
            [],
        )

        if not isinstance(
            legacy_runtimes,
            list,
        ):
            raise CatalogError(
                "Model supportedRuntimes "
                "must be a list"
            )

        legacy_set = {
            str(name)
            for name in legacy_runtimes
        }

        runtime_policy = self._runtime_policy(
            profile_spec
        )

        allowed = runtime_policy.get(
            "allowedRuntimes",
            [],
        )

        if not isinstance(
            allowed,
            list,
        ):
            raise CatalogError(
                "Profile allowedRuntimes "
                "must be a list"
            )

        allowed_set = {
            str(name)
            for name in allowed
        }

        preferred = runtime_policy.get(
            "preferredRuntimes",
            [],
        )

        if not isinstance(
            preferred,
            list,
        ):
            raise CatalogError(
                "Profile preferredRuntimes "
                "must be a list"
            )

        preferred_set = {
            str(name)
            for name in preferred
        }

        results: list[
            dict[str, Any]
        ] = []

        for definition in (
            self.catalog.list_items(
                "runtimes"
            )
        ):
            metadata = definition.get(
                "metadata",
                {},
            )

            runtime_spec = definition.get(
                "spec",
                {},
            )

            if (
                not isinstance(
                    metadata,
                    dict,
                )
                or not isinstance(
                    runtime_spec,
                    dict,
                )
            ):
                continue

            runtime_name = str(
                metadata.get(
                    "name",
                    "",
                )
            )

            if not runtime_name:
                continue

            display_name = str(
                runtime_spec.get(
                    "displayName",
                    runtime_name,
                )
            )

            compatibility = runtime_spec.get(
                "compatibility",
                {},
            )

            if not isinstance(
                compatibility,
                dict,
            ):
                compatibility = {}

            formats = self._normalized_set(
                compatibility.get(
                    "artifactFormats",
                    [],
                )
            )

            quantizations = (
                self._normalized_set(
                    compatibility.get(
                        "quantizations",
                        [],
                    )
                )
            )

            architectures = (
                self._normalized_set(
                    compatibility.get(
                        "architectures",
                        [],
                    )
                )
            )

            reasons: list[str] = []

            # -------------------------------------------------
            # Artifact format
            # -------------------------------------------------

            if artifact_format:
                format_compatible = (
                    artifact_format
                    in formats
                )

                if not format_compatible:
                    reasons.append(
                        "Artifact format "
                        f"'{artifact_format}' "
                        "is not supported"
                    )

            else:
                # Legacy catalog model
                format_compatible = (
                    runtime_name
                    in legacy_set
                )

                if not format_compatible:
                    reasons.append(
                        "Runtime is not declared "
                        "by the legacy model catalog"
                    )

            # -------------------------------------------------
            # Quantization
            # -------------------------------------------------

            quantization_compatible = True

            if (
                quantization
                and quantizations
                and quantization
                not in quantizations
            ):
                quantization_compatible = (
                    False
                )

                reasons.append(
                    "Quantization "
                    f"'{quantization}' "
                    "is not supported"
                )

            # -------------------------------------------------
            # Architecture
            # -------------------------------------------------

            architecture_compatible = True

            if (
                architecture
                and architectures
                and architecture
                not in architectures
            ):
                architecture_compatible = (
                    False
                )

                reasons.append(
                    "Architecture "
                    f"'{architecture}' "
                    "is not supported"
                )

            # -------------------------------------------------
            # Profile policy
            # -------------------------------------------------

            profile_allowed = (
                not allowed_set
                or runtime_name
                in allowed_set
            )

            if not profile_allowed:
                reasons.append(
                    "Runtime is blocked "
                    "by profile policy"
                )

            # -------------------------------------------------
            # Security approval
            # -------------------------------------------------

            security = runtime_spec.get(
                "security",
                {},
            )

            if not isinstance(
                security,
                dict,
            ):
                security = {}

            approved = (
                security.get(
                    "approved",
                    True,
                )
                is True
            )

            if not approved:
                reasons.append(
                    "Runtime is not approved"
                )

            compatible = all(
                (
                    format_compatible,
                    quantization_compatible,
                    architecture_compatible,
                    profile_allowed,
                    approved,
                )
            )

            # -------------------------------------------------
            # Availability
            # -------------------------------------------------

            available = (
                self._is_available(
                    runtime_spec
                )
                if compatible
                else False
            )

            hardware = runtime_spec.get(
                "hardware",
                {},
            )

            if not isinstance(
                hardware,
                dict,
            ):
                hardware = {}

            accelerator = hardware.get(
                "accelerator"
            )

            try:
                gpu_count = int(
                    hardware.get(
                        "gpuCount",
                        0,
                    )
                )
            except (
                TypeError,
                ValueError,
            ):
                gpu_count = 0

            if (
                compatible
                and not available
            ):
                mode = str(
                    runtime_spec.get(
                        "deploymentMode",
                        "",
                    )
                )

                if (
                    mode
                    == "kubernetes"
                    and (
                        accelerator
                        == "nvidia"
                        or gpu_count > 0
                    )
                ):
                    reasons.append(
                        "Required NVIDIA GPU "
                        "capacity is unavailable"
                    )

                elif mode == "external":
                    reasons.append(
                        "External runtime "
                        "management endpoint "
                        "is unreachable"
                    )

                else:
                    reasons.append(
                        "Runtime is currently "
                        "unavailable"
                    )

            if (
                compatible
                and available
            ):
                reasons.append(
                    "Compatible and available"
                )

            results.append(
                {
                    "name":
                        runtime_name,

                    "display_name":
                        display_name,

                    "engine":
                        runtime_spec.get(
                            "engine"
                        ),

                    "deployment_mode":
                        runtime_spec.get(
                            "deploymentMode"
                        ),

                    "accelerator":
                        accelerator,

                    "gpu_count":
                        gpu_count,

                    "compatible":
                        compatible,

                    "available":
                        available,

                    "preferred":
                        runtime_name
                        in preferred_set,

                    "priority":
                        self._runtime_priority(
                            runtime_spec
                        ),

                    "reason":
                        "; ".join(
                            reasons
                        ),

                    "supported_formats":
                        sorted(
                            formats
                        ),

                    "supported_quantizations":
                        sorted(
                            quantizations
                        ),
                }
            )

        candidates = [
            item
            for item in results
            if (
                item["compatible"]
                and item["available"]
            )
        ]

        candidates.sort(
            key=lambda item: (
                0
                if item["preferred"]
                else 1,
                -int(
                    item["priority"]
                ),
                str(
                    item["name"]
                ),
            )
        )

        selected_runtime = (
            candidates[0]["name"]
            if candidates
            else None
        )

        for item in results:
            item["selected"] = (
                item["name"]
                == selected_runtime
            )

        results.sort(
            key=lambda item: (
                0
                if item["selected"]
                else 1,

                0
                if item["compatible"]
                else 1,

                0
                if item["available"]
                else 1,

                -int(
                    item["priority"]
                ),

                str(
                    item["name"]
                ),
            )
        )

        return {
            "model_id":
                model_name,

            "artifact_format":
                artifact_format,

            "quantization":
                quantization,

            "architecture":
                architecture,

            "selected_runtime":
                selected_runtime,

            "runtimes":
                results,
        }

    # =========================================================
    # RUNTIME DEFINITIONS
    # =========================================================

    def _runtime_definitions(
        self,
    ) -> dict[
        str,
        dict[str, Any],
    ]:
        results: dict[
            str,
            dict[str, Any],
        ] = {}

        for definition in (
            self.catalog.list_items(
                "runtimes"
            )
        ):
            metadata = definition.get(
                "metadata",
                {},
            )

            runtime_spec = definition.get(
                "spec",
                {},
            )

            if (
                not isinstance(
                    metadata,
                    dict,
                )
                or not isinstance(
                    runtime_spec,
                    dict,
                )
            ):
                continue

            name = metadata.get(
                "name"
            )

            if not name:
                continue

            results[
                str(name)
            ] = runtime_spec

        return results

    # =========================================================
    # PROFILE POLICY
    # =========================================================

    @staticmethod
    def _runtime_policy(
        profile_spec: dict[str, Any],
    ) -> dict[str, Any]:
        runtime_policy = (
            profile_spec.get(
                "runtimePolicy",
                {},
            )
        )

        if not isinstance(
            runtime_policy,
            dict,
        ):
            raise CatalogError(
                "Profile runtimePolicy "
                "must be an object"
            )

        return runtime_policy

    # =========================================================
    # PRIORITY
    # =========================================================

    @staticmethod
    def _runtime_priority(
        runtime_spec: dict[str, Any],
    ) -> int:
        try:
            return int(
                runtime_spec.get(
                    "priority",
                    0,
                )
            )

        except (
            TypeError,
            ValueError,
        ):
            return 0

    # =========================================================
    # AVAILABILITY
    # =========================================================

    def _is_available(
        self,
        runtime_spec: dict[str, Any],
    ) -> bool:
        mode = str(
            runtime_spec.get(
                "deploymentMode",
                "",
            )
        )

        # -----------------------------------------------------
        # External runtime
        # -----------------------------------------------------

        if mode == "external":
            management = runtime_spec.get(
                "management",
                {},
            )

            if not isinstance(
                management,
                dict,
            ):
                return False

            host = management.get(
                "host"
            )

            port = management.get(
                "port",
                22,
            )

            if not host:
                return False

            try:
                with socket.create_connection(
                    (
                        str(host),
                        int(port),
                    ),
                    timeout=3,
                ):
                    return True

            except (
                OSError,
                ValueError,
            ):
                return False

        # -----------------------------------------------------
        # Kubernetes runtime
        # -----------------------------------------------------

        if mode == "kubernetes":
            hardware = runtime_spec.get(
                "hardware",
                {},
            )

            if not isinstance(
                hardware,
                dict,
            ):
                hardware = {}

            accelerator = hardware.get(
                "accelerator"
            )

            try:
                gpu_count = int(
                    hardware.get(
                        "gpuCount",
                        0,
                    )
                )
            except (
                TypeError,
                ValueError,
            ):
                gpu_count = 0

            if (
                accelerator == "nvidia"
                or gpu_count > 0
            ):
                result = (
                    self.kubernetes
                    .check_nvidia_gpu_available(
                        required=max(
                            gpu_count,
                            1,
                        )
                    )
                )

                return bool(
                    result.get(
                        "available",
                        False,
                    )
                )

            return True

        return False

    # =========================================================
    # NORMALIZATION
    # =========================================================

    @staticmethod
    def _normalize(
        value: Any,
    ) -> str | None:
        if value is None:
            return None

        normalized = (
            str(value)
            .strip()
            .lower()
        )

        return (
            normalized
            if normalized
            else None
        )

    @classmethod
    def _normalized_set(
        cls,
        values: Any,
    ) -> set[str]:
        if values is None:
            return set()

        if not isinstance(
            values,
            list,
        ):
            raise CatalogError(
                "Runtime compatibility "
                "values must be lists"
            )

        result: set[str] = set()

        for value in values:
            normalized = (
                cls._normalize(
                    value
                )
            )

            if normalized:
                result.add(
                    normalized
                )

        return result

    # =========================================================
    # ENDPOINT
    # =========================================================

    @staticmethod
    def _normalize_endpoint(
        endpoint: Any,
    ) -> str | None:
        if isinstance(
            endpoint,
            str,
        ):
            value = endpoint.strip()

            return (
                value
                if value
                else None
            )

        if isinstance(
            endpoint,
            dict,
        ):
            host = endpoint.get(
                "host"
            )

            port = endpoint.get(
                "port"
            )

            scheme = endpoint.get(
                "scheme",
                "http",
            )

            if not host:
                return None

            if port is None:
                return (
                    f"{scheme}://{host}"
                )

            return (
                f"{scheme}://"
                f"{host}:{int(port)}"
            )

        return None
