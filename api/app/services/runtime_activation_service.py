from __future__ import annotations

import re
from typing import Any

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException


class RuntimeActivationError(Exception):
    pass


class RuntimeActivationService:
    """Submit Kubernetes Jobs that orchestrate an external vLLM runtime through SSH."""

    def __init__(
        self,
        *,
        namespace: str,
        kubernetes_mode: str,
        image: str,
    ) -> None:
        self.namespace = namespace
        self.kubernetes_mode = kubernetes_mode
        self.image = image
        if kubernetes_mode == "incluster":
            config.load_incluster_config()
        else:
            config.load_kube_config()
        self.batch = client.BatchV1Api()

    @staticmethod
    def _slug(value: str) -> str:
        return (
            re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")[:40]
            or "runtime"
        )

    def _common_env(self) -> list[client.V1EnvVar]:
        def secret_env(name: str, secret: str, key: str) -> client.V1EnvVar:
            return client.V1EnvVar(
                name=name,
                value_from=client.V1EnvVarSource(
                    secret_key_ref=client.V1SecretKeySelector(
                        name=secret,
                        key=key,
                    )
                ),
            )

        return [
            secret_env(
                "REGISTRY_USERNAME",
                "model-ingestion-secrets",
                "ACP_REGISTRY_USERNAME",
            ),
            secret_env(
                "REGISTRY_PASSWORD",
                "model-ingestion-secrets",
                "ACP_REGISTRY_PASSWORD",
            ),
            secret_env("RUNTIME_SSH_USER", "runtime-activation-config", "MAC_SSH_USER"),
            secret_env("RUNTIME_SSH_HOST", "runtime-activation-config", "MAC_SSH_HOST"),
            secret_env("RUNTIME_SSH_PORT", "runtime-activation-config", "MAC_SSH_PORT"),
            secret_env("VLLM_BIN", "runtime-activation-config", "VLLM_BIN"),
            secret_env(
                "LLAMA_CPP_BIN",
                "runtime-activation-config",
                "LLAMA_CPP_BIN",
            ),
            secret_env(
                "REMOTE_MODELS_ROOT",
                "runtime-activation-config",
                "REMOTE_MODELS_ROOT",
            ),
            secret_env("VLLM_API_KEY", "runtime-activation-config", "VLLM_API_KEY"),
            secret_env(
                "LLAMA_CPP_API_KEY",
                "runtime-activation-config",
                "LLAMA_CPP_API_KEY",
            ),
            secret_env(
                "LEGACY_MODEL_ARTIFACT_TYPE",
                "runtime-activation-config",
                "LEGACY_MODEL_ARTIFACT_TYPE",
            ),
            secret_env(
                "LEGACY_MODEL_LAYER_TYPE",
                "runtime-activation-config",
                "LEGACY_MODEL_LAYER_TYPE",
            ),
            secret_env(
                "CALLBACK_TOKEN",
                "runtime-callback-secret",
                "ACP_RUNTIME_CALLBACK_TOKEN",
            ),
            client.V1EnvVar(
                name="CALLBACK_URL",
                value=(
                    "http://ai-control-plane-internal."
                    "ai-system.svc.cluster.local:8080"
                ),
            ),
        ]

    def _job(
        self,
        *,
        generate_name: str,
        command: str,
        env: list[client.V1EnvVar],
        labels: dict[str, str],
    ) -> client.V1Job:
        container = client.V1Container(
            name="runtime-activation",
            image=self.image,
            image_pull_policy="IfNotPresent",
            command=[command],
            env=self._common_env() + env,
            volume_mounts=[
                client.V1VolumeMount(
                    name="verification-key",
                    mount_path="/keys",
                    read_only=True,
                ),
                client.V1VolumeMount(
                    name="ssh-key",
                    mount_path="/ssh-secret",
                    read_only=True,
                ),
                client.V1VolumeMount(name="tmp", mount_path="/tmp"),
            ],
            security_context=client.V1SecurityContext(
                allow_privilege_escalation=False,
                run_as_non_root=True,
                run_as_user=10001,
                run_as_group=10001,
                read_only_root_filesystem=True,
                capabilities=client.V1Capabilities(drop=["ALL"]),
            ),
            resources=client.V1ResourceRequirements(
                requests={"cpu": "100m", "memory": "128Mi"},
                limits={"cpu": "1", "memory": "512Mi"},
            ),
        )

        pod = client.V1PodSpec(
            service_account_name="runtime-activation",
            restart_policy="Never",
            automount_service_account_token=False,
            containers=[container],
            volumes=[
                client.V1Volume(
                    name="verification-key",
                    secret=client.V1SecretVolumeSource(
                        secret_name="model-verification-key"
                    ),
                ),
                client.V1Volume(
                    name="ssh-key",
                    secret=client.V1SecretVolumeSource(
                        secret_name="runtime-activation-ssh"
                    ),
                ),
                client.V1Volume(
                    name="tmp",
                    empty_dir=client.V1EmptyDirVolumeSource(),
                ),
            ],
            security_context=client.V1PodSecurityContext(
                run_as_non_root=True,
                seccomp_profile=client.V1SeccompProfile(type="RuntimeDefault"),
            ),
        )

        return client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(
                generate_name=generate_name,
                namespace=self.namespace,
                labels=labels,
            ),
            spec=client.V1JobSpec(
                backoff_limit=0,
                active_deadline_seconds=3600,
                ttl_seconds_after_finished=3600,
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(labels=labels),
                    spec=pod,
                ),
            ),
        )

    def submit_activation(
        self,
        *,
        deployment_name: str,
        model_id: str,
        artifact_reference: str,
        artifact_digest: str,
        max_model_len: int,
        inference_endpoint: str,
        runtime_name: str,
    ) -> dict[str, Any]:
        labels = {
            "app.kubernetes.io/name": "runtime-activation",
            "app.kubernetes.io/part-of": "ai-platform",
            "platform.secureai.io/action": "activate",
            "platform.secureai.io/deployment": self._slug(deployment_name),
        }
        env = [
            client.V1EnvVar(name="DEPLOYMENT_NAME", value=deployment_name),
            client.V1EnvVar(name="MODEL_ID", value=model_id),
            client.V1EnvVar(name="ARTIFACT_REFERENCE", value=artifact_reference),
            client.V1EnvVar(name="ARTIFACT_DIGEST", value=artifact_digest),
            client.V1EnvVar(name="MAX_MODEL_LEN", value=str(max_model_len)),
            client.V1EnvVar(name="INFERENCE_ENDPOINT", value=inference_endpoint),
            client.V1EnvVar(name="RUNTIME_NAME", value=runtime_name),
        ]
        job = self._job(
            generate_name=f"runtime-activate-{self._slug(deployment_name)}-",
            command="/usr/local/bin/activate-model",
            env=env,
            labels=labels,
        )
        try:
            created = self.batch.create_namespaced_job(
                namespace=self.namespace, body=job
            )
        except ApiException as exc:
            raise RuntimeActivationError(
                f"Could not create runtime activation Job: "
                f"{exc.reason}: {exc.body}"
            ) from exc
        return {
            "job_name": created.metadata.name,
            "namespace": self.namespace,
            "status": "submitted",
        }

    def submit_deactivation(self, *, model_id: str) -> dict[str, Any]:
        labels = {
            "app.kubernetes.io/name": "runtime-activation",
            "app.kubernetes.io/part-of": "ai-platform",
            "platform.secureai.io/action": "deactivate",
        }
        job = self._job(
            generate_name="runtime-deactivate-",
            command="/usr/local/bin/deactivate-runtime",
            env=[client.V1EnvVar(name="MODEL_ID", value=model_id)],
            labels=labels,
        )
        try:
            created = self.batch.create_namespaced_job(
                namespace=self.namespace, body=job
            )
        except ApiException as exc:
            raise RuntimeActivationError(
                f"Could not create runtime deactivation Job: "
                f"{exc.reason}: {exc.body}"
            ) from exc
        return {
            "job_name": created.metadata.name,
            "namespace": self.namespace,
            "status": "submitted",
        }
