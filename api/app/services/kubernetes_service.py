from __future__ import annotations

from typing import Any

from kubernetes import client, config
from kubernetes.client.rest import ApiException


class KubernetesService:
    def __init__(
        self,
        namespace: str,
        mode: str = "kubeconfig",
        model_puller_image: str | None = None,
    ) -> None:
        self.namespace = namespace
        self.mode = mode
        self.model_puller_image = model_puller_image
        if mode == "incluster":
            config.load_incluster_config()
        elif mode == "kubeconfig":
            config.load_kube_config()
        else:
            raise RuntimeError(f"Unsupported Kubernetes mode: {mode}")
        self.apps_api = client.AppsV1Api()
        self.core_api = client.CoreV1Api()

    def check_nvidia_gpu_available(self, required: int = 1) -> dict[str, Any]:
        try:
            nodes = self.core_api.list_node()
        except ApiException as exc:
            raise RuntimeError(
                f"Could not query Kubernetes nodes for GPU capacity: {exc}"
            ) from exc

        total = 0
        with_gpu: list[dict[str, Any]] = []
        for node in nodes.items:
            alloc = node.status.allocatable or {}
            try:
                count = int(alloc.get("nvidia.com/gpu", "0"))
            except (TypeError, ValueError):
                count = 0
            total += count
            if count:
                with_gpu.append(
                    {"name": node.metadata.name, "allocatable": count}
                )
        return {
            "required": required,
            "allocatable": total,
            "available": total >= required,
            "nodes": with_gpu,
        }

    def _model_puller(
        self,
        *,
        artifact: str,
        mount_path: str,
        secret_name: str,
        plain_http: bool,
        insecure: bool,
    ) -> client.V1Container:
        registry = artifact.split("/", 1)[0]
        flag = "--plain-http" if plain_http else "--insecure" if insecure else ""

        if not self.model_puller_image:
            raise RuntimeError(
                "Model puller image is not configured"
            )

        script = f"""
set -eu
mkdir -p "$DOCKER_CONFIG" "$OCI_DOWNLOAD" "$MODEL_OUTPUT"

printf '%s' "$REGISTRY_PASSWORD" | oras login \
  {flag} "$REGISTRY_HOST" \
  --username "$REGISTRY_USERNAME" \
  --password-stdin

oras pull {flag} \
  --output "$OCI_DOWNLOAD" \
  "$MODEL_ARTIFACT_REFERENCE"

MODEL_TAR="$OCI_DOWNLOAD/promotion/model.tar"
REPORT="$OCI_DOWNLOAD/reports/security-report.json"

test -f "$MODEL_TAR"
test -f "$REPORT"
# Treat archive structure as untrusted input even after
# OCI trust verification.
#
# secure_extract.py rejects traversal, absolute paths,
# symlinks, hardlinks, devices, FIFOs and special entries.
python3 /usr/local/lib/ai-platform/secure_extract.py "$MODEL_OUTPUT" < "$MODEL_TAR"

SAFETENSORS_FILE="$(
  find "$MODEL_OUTPUT"     -type f     -name '*.safetensors'     -print -quit
)"

GGUF_FILE="$(
  find "$MODEL_OUTPUT"     -type f     -name '*.gguf'     -print -quit
)"

if [ -z "$SAFETENSORS_FILE" ] && [ -z "$GGUF_FILE" ]; then
  echo "No supported model weights found after OCI extraction" >&2
  exit 1
fi

if [ -n "$SAFETENSORS_FILE" ]; then
  test -f "$MODEL_OUTPUT/config.json"
  echo "Detected Safetensors OCI model"
fi

if [ -n "$GGUF_FILE" ]; then
  echo "Detected GGUF OCI model: $GGUF_FILE"
fi

rm -f "$MODEL_TAR"
"""
        def from_secret(env_name: str, key: str) -> client.V1EnvVar:
            return client.V1EnvVar(
                name=env_name,
                value_from=client.V1EnvVarSource(
                    secret_key_ref=client.V1SecretKeySelector(
                        name=secret_name, key=key
                    )
                ),
            )

        return client.V1Container(
            name="model-puller",
            image=self.model_puller_image,
            image_pull_policy="IfNotPresent",
            command=["/bin/sh", "-c"],
            args=[script],
            env=[
                client.V1EnvVar(
                    name="MODEL_ARTIFACT_REFERENCE", value=artifact
                ),
                client.V1EnvVar(name="MODEL_OUTPUT", value=mount_path),
                client.V1EnvVar(name="OCI_DOWNLOAD", value="/tmp/oci"),
                client.V1EnvVar(name="REGISTRY_HOST", value=registry),
                client.V1EnvVar(name="HOME", value="/tmp/oras-home"),
                client.V1EnvVar(
                    name="DOCKER_CONFIG", value="/tmp/oras-home/.docker"
                ),
                from_secret("REGISTRY_USERNAME", "ACP_REGISTRY_USERNAME"),
                from_secret("REGISTRY_PASSWORD", "ACP_REGISTRY_PASSWORD"),
            ],
            volume_mounts=[
                client.V1VolumeMount(
                    name="model-storage", mount_path=mount_path
                ),
                client.V1VolumeMount(
                    name="oras-home", mount_path="/tmp/oras-home"
                ),
                client.V1VolumeMount(name="oci", mount_path="/tmp/oci"),
            ],
            security_context=client.V1SecurityContext(
                allow_privilege_escalation=False,
                run_as_non_root=True,
                run_as_user=10001,
                run_as_group=10001,
                read_only_root_filesystem=True,
                capabilities=client.V1Capabilities(drop=["ALL"]),
            ),
        )

    @staticmethod
    def _runtime_container(
        *,
        image: str,
        served_model_name: str,
        port: int,
        max_model_len: int,
        mount_path: str,
        gpu_count: int,
        cpu_request: str,
        memory_request: str,
        cpu_limit: str,
        memory_limit: str,
    ) -> client.V1Container:
        limits = {"cpu": cpu_limit, "memory": memory_limit}
        if gpu_count > 0:
            limits["nvidia.com/gpu"] = str(gpu_count)

        return client.V1Container(
            name="runtime",
            image=image,
            image_pull_policy="IfNotPresent",
            args=[
                "--model", mount_path,
                "--served-model-name", served_model_name,
                "--host", "0.0.0.0",
                "--port", str(port),
                "--max-model-len", str(max_model_len),
            ],
            env=[
                client.V1EnvVar(name="HF_HUB_OFFLINE", value="1"),
                client.V1EnvVar(name="TRANSFORMERS_OFFLINE", value="1"),
            ],
            ports=[client.V1ContainerPort(container_port=port, name="http")],
            volume_mounts=[
                client.V1VolumeMount(
                    name="model-storage", mount_path=mount_path, read_only=True
                )
            ],
            resources=client.V1ResourceRequirements(
                requests={"cpu": cpu_request, "memory": memory_request},
                limits=limits,
            ),
        )

    def build_ai_deployment(
        self,
        name: str,
        image: str,
        repository: str,
        served_model_name: str,
        model_artifact_reference: str,
        port: int,
        replicas: int,
        cpu_request: str,
        memory_request: str,
        cpu_limit: str,
        memory_limit: str,
        gpu_count: int,
        max_model_len: int,
        node_selector: dict[str, str] | None = None,
        model_mount_path: str = "/models/model",
        registry_secret_name: str = "model-ingestion-secrets",
        registry_insecure: bool = True,
        registry_plain_http: bool = True,
        model_storage_size: str = "70Gi",
    ) -> client.V1Deployment:
        labels = {
            "app": name,
            "managed-by": "ai-control-plane",
            "ai-model": served_model_name,
        }

        puller = self._model_puller(
            artifact=model_artifact_reference,
            mount_path=model_mount_path,
            secret_name=registry_secret_name,
            plain_http=registry_plain_http,
            insecure=registry_insecure,
        )
        runtime = self._runtime_container(
            image=image,
            served_model_name=served_model_name,
            port=port,
            max_model_len=max_model_len,
            mount_path=model_mount_path,
            gpu_count=gpu_count,
            cpu_request=cpu_request,
            memory_request=memory_request,
            cpu_limit=cpu_limit,
            memory_limit=memory_limit,
        )

        pod = client.V1PodSpec(
            init_containers=[puller],
            containers=[runtime],
            restart_policy="Always",
            service_account_name="ai-runtime",
            automount_service_account_token=False,
            node_selector=node_selector or {},
            volumes=[
                client.V1Volume(
                    name="model-storage",
                    empty_dir=client.V1EmptyDirVolumeSource(
                        size_limit=model_storage_size
                    ),
                ),
                client.V1Volume(
                    name="oras-home",
                    empty_dir=client.V1EmptyDirVolumeSource(),
                ),
                client.V1Volume(
                    name="oci",
                    empty_dir=client.V1EmptyDirVolumeSource(),
                ),
            ],
        )

        return client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(
                name=name,
                namespace=self.namespace,
                labels=labels,
                annotations={
                    "ai.platform/model-repository": repository,
                    "ai.platform/model-artifact": model_artifact_reference,
                },
            ),
            spec=client.V1DeploymentSpec(
                replicas=replicas,
                selector=client.V1LabelSelector(match_labels={"app": name}),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(labels=labels),
                    spec=pod,
                ),
            ),
        )

    def build_ai_service(self, name: str, port: int) -> client.V1Service:
        return client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(
                name=name, namespace=self.namespace
            ),
            spec=client.V1ServiceSpec(
                selector={"app": name},
                ports=[
                    client.V1ServicePort(
                        name="http", port=port, target_port=port
                    )
                ],
                type="ClusterIP",
            ),
        )

    def dry_run_ai_deployment(self, **kwargs: Any) -> dict[str, Any]:
        deployment = self.build_ai_deployment(**kwargs)
        try:
            result = self.apps_api.create_namespaced_deployment(
                namespace=self.namespace,
                body=deployment,
                dry_run="All",
            )
        except ApiException as exc:
            raise RuntimeError(
                f"Kubernetes deployment dry-run failed: {exc.reason}: {exc.body}"
            ) from exc
        return {
            "validated": True,
            "name": result.metadata.name,
            "namespace": result.metadata.namespace,
        }

    def create_ai_deployment(self, **kwargs: Any) -> dict[str, Any]:
        deployment = self.build_ai_deployment(**kwargs)
        name = str(kwargs["name"])
        port = int(kwargs["port"])
        service = self.build_ai_service(name, port)
        created_deployment = None

        try:
            created_deployment = self.apps_api.create_namespaced_deployment(
                namespace=self.namespace, body=deployment
            )
            created_service = self.core_api.create_namespaced_service(
                namespace=self.namespace, body=service
            )
        except ApiException as exc:
            if created_deployment is not None:
                try:
                    self.apps_api.delete_namespaced_deployment(
                        name=name, namespace=self.namespace
                    )
                except ApiException:
                    pass
            raise RuntimeError(
                f"Kubernetes deployment failed: {exc.reason}: {exc.body}"
            ) from exc

        return {
            "deployment": created_deployment.metadata.name,
            "service": created_service.metadata.name,
            "endpoint": (
                f"http://{created_service.metadata.name}."
                f"{self.namespace}.svc.cluster.local:{port}"
            ),
        }

    def delete_ai_deployment(self, *, name: str) -> None:
        try:
            self.core_api.delete_namespaced_service(
                name=name, namespace=self.namespace
            )
        except ApiException as exc:
            if exc.status != 404:
                raise RuntimeError(f"Could not delete Service '{name}': {exc}")
        try:
            self.apps_api.delete_namespaced_deployment(
                name=name, namespace=self.namespace
            )
        except ApiException as exc:
            if exc.status != 404:
                raise RuntimeError(f"Could not delete Deployment '{name}': {exc}")
