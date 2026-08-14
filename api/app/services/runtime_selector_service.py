from __future__ import annotations

import socket
from typing import Any

from app.services.catalog_service import CatalogError, CatalogService
from app.services.kubernetes_service import KubernetesService


class RuntimeSelectionError(Exception):
    pass


class RuntimeCompatibilityError(RuntimeSelectionError):
    pass


class RuntimeUnavailableError(RuntimeSelectionError):
    pass


class RuntimeSelectorService:
    """
    External runtime availability is based on the SSH management channel.
    The model does not have to be loaded before deployment.
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

    def select(
        self,
        *,
        requested_runtime: str,
        model_name: str,
        model_spec: dict[str, Any],
        profile_spec: dict[str, Any],
    ) -> str:
        compatible = self._compatible_runtimes(
            model_spec=model_spec,
            profile_spec=profile_spec,
        )

        if requested_runtime != "auto":
            if requested_runtime not in compatible:
                raise RuntimeCompatibilityError(
                    f"Runtime '{requested_runtime}' is not allowed by the "
                    "selected model/profile policy"
                )
            runtime = self.catalog.load("runtimes", requested_runtime)
            spec = runtime.get("spec", {})
            if not isinstance(spec, dict) or not self._is_available(spec):
                raise RuntimeUnavailableError(
                    f"Runtime '{requested_runtime}' is compatible but "
                    "currently unavailable"
                )
            return requested_runtime

        runtime_policy = profile_spec.get("runtimePolicy", {})
        preferred = runtime_policy.get("preferredRuntimes", [])
        if preferred and not isinstance(preferred, list):
            raise CatalogError("Profile preferredRuntimes must be a list")

        order: list[str] = []
        for name in list(preferred) + ["vllm-cuda", "vllm-metal"] + sorted(compatible):
            name = str(name)
            if name not in order:
                order.append(name)

        checked: list[str] = []
        for name in order:
            if name not in compatible:
                continue
            definition = self.catalog.load("runtimes", name)
            spec = definition.get("spec", {})
            if isinstance(spec, dict) and self._is_available(spec):
                return name
            checked.append(name)

        raise RuntimeUnavailableError(
            "No compatible runtime is currently available. "
            "Compatible runtimes checked: " + ", ".join(checked)
        )

    @staticmethod
    def _compatible_runtimes(
        *,
        model_spec: dict[str, Any],
        profile_spec: dict[str, Any],
    ) -> set[str]:
        model_runtimes = model_spec.get("supportedRuntimes", [])
        if not isinstance(model_runtimes, list):
            raise CatalogError("Model supportedRuntimes must be a list")
        model_set = {str(x) for x in model_runtimes}
        if not model_set:
            raise RuntimeCompatibilityError(
                "Model does not declare any supported runtime"
            )

        policy = profile_spec.get("runtimePolicy", {})
        if not isinstance(policy, dict):
            raise CatalogError("Profile runtimePolicy must be an object")
        profile_runtimes = policy.get("allowedRuntimes", [])
        if not isinstance(profile_runtimes, list):
            raise CatalogError("Profile allowedRuntimes must be a list")

        profile_set = {str(x) for x in profile_runtimes}
        result = model_set & profile_set if profile_set else model_set
        if not result:
            raise RuntimeCompatibilityError(
                "No runtime is compatible with both the selected model "
                "and profile"
            )
        return result

    def _is_available(self, runtime_spec: dict[str, Any]) -> bool:
        mode = str(runtime_spec.get("deploymentMode", ""))

        if mode == "external":
            management = runtime_spec.get("management", {})
            if not isinstance(management, dict):
                return False
            host = management.get("host")
            port = management.get("port", 22)
            if not host:
                return False
            try:
                with socket.create_connection((str(host), int(port)), timeout=3):
                    return True
            except (OSError, ValueError):
                return False

        if mode == "kubernetes":
            hardware = runtime_spec.get("hardware", {})
            if not isinstance(hardware, dict):
                hardware = {}
            accelerator = hardware.get("accelerator")
            gpu_count = int(hardware.get("gpuCount", 0))

            if accelerator == "nvidia" or gpu_count > 0:
                result = self.kubernetes.check_nvidia_gpu_available(
                    required=max(gpu_count, 1)
                )
                return bool(result.get("available", False))
            return True

        return False

    @staticmethod
    def _normalize_endpoint(endpoint: Any) -> str | None:
        if isinstance(endpoint, str):
            value = endpoint.strip()
            return value if value else None
        if isinstance(endpoint, dict):
            host = endpoint.get("host")
            port = endpoint.get("port")
            scheme = endpoint.get("scheme", "http")
            if not host:
                return None
            return (
                f"{scheme}://{host}"
                if port is None
                else f"{scheme}://{host}:{int(port)}"
            )
        return None
