from __future__ import annotations

import re
from typing import Any

from kubernetes import (
    client,
    config,
)
from kubernetes.client.exceptions import (
    ApiException,
)


class ModelIngestionError(Exception):
    pass


class ModelIngestionJobAlreadyExists(
    ModelIngestionError
):
    pass


class ModelIngestionService:
    """
    Create isolated Kubernetes Jobs responsible
    for model ingestion.

    The API Control Plane does not download
    or scan model weights itself.
    """

    def __init__(
        self,
        *,
        namespace: str,
        kubernetes_mode: str,
        ingestion_image: str,
        ingestion_secret_name: str,
        workspace_pvc_name: str,
        image_pull_secret_name: str,
    ) -> None:

        self.namespace = namespace

        self.kubernetes_mode = (
            kubernetes_mode
        )

        self.ingestion_image = (
            ingestion_image
        )

        self.ingestion_secret_name = (
            ingestion_secret_name
        )

        self.workspace_pvc_name = (
            workspace_pvc_name
        )

        self.image_pull_secret_name = (
            image_pull_secret_name
        )

        self._configure_kubernetes()

        self.batch = (
            client.BatchV1Api()
        )

    # ======================================================
    # KUBERNETES CONFIGURATION
    # ======================================================

    def _configure_kubernetes(
        self,
    ) -> None:

        if (
            self.kubernetes_mode
            == "incluster"
        ):
            config.load_incluster_config()

        else:
            config.load_kube_config()

    # ======================================================
    # JOB NAME
    # ======================================================

    @staticmethod
    def _job_name(
        *,
        request_id: int,
        repository: str,
    ) -> str:

        model_name = (
            repository
            .split("/")[-1]
            .lower()
        )

        model_name = re.sub(
            r"[^a-z0-9-]+",
            "-",
            model_name,
        )

        model_name = (
            model_name
            .strip("-")[:30]
        )

        return (
            f"model-ingest-"
            f"{request_id}-"
            f"{model_name}"
        )

    # ======================================================
    # CREATE JOB
    # ======================================================

    def create_job(
        self,
        *,
        request_id: int,
        provider: str,
        repository: str,
        revision: str,
        artifact_patterns: list[str] | None = None,
        allow_full_snapshot: bool = False,
    ) -> dict[str, Any]:

        job_name = self._job_name(
            request_id=request_id,
            repository=repository,
        )

        pod_spec = client.V1PodSpec(
            restart_policy="Never",

            service_account_name=(
                "model-ingestion"
            ),
            automount_service_account_token=False,
            image_pull_secrets=[
                client.V1LocalObjectReference(
                    name=(
                        self
                        .image_pull_secret_name
                    )
                )
            ],

            security_context=(
                client.V1PodSecurityContext(
                    run_as_non_root=True,
                    run_as_user=10001,
                    run_as_group=10001,
                    fs_group=10001,
                )
            ),

            containers=[
                client.V1Container(
                    name="ingestion",

                    image=(
                        self.ingestion_image
                    ),

                    image_pull_policy=(
                        "Always"
                    ),

                    env=[
                        client.V1EnvVar(
                            name=(
                                "MODEL_REQUEST_ID"
                            ),
                            value=str(
                                request_id
                            ),
                        ),

                        client.V1EnvVar(
                            name=(
                                "MODEL_PROVIDER"
                            ),
                            value=provider,
                        ),

                        client.V1EnvVar(
                            name=(
                                "MODEL_REPOSITORY"
                            ),
                            value=repository,
                        ),

                        client.V1EnvVar(
                            name=(
                                "MODEL_REVISION"
                            ),
                            value=revision,
                        ),

                        client.V1EnvVar(
                            name=(
                                "MODEL_ARTIFACT_PATTERNS"
                            ),
                            value="\n".join(
                                artifact_patterns or []
                            ),
                        ),

                        client.V1EnvVar(
                            name=(
                                "MODEL_ALLOW_FULL_SNAPSHOT"
                            ),
                            value=(
                                "true"
                                if allow_full_snapshot
                                else "false"
                            ),
                        ),

                        client.V1EnvVar(
                            name=(
                                "MODEL_MAX_TOTAL_BYTES"
                            ),
                            value=str(
                                100 * 1024**3
                            ),
                        ),

                        client.V1EnvVar(
                            name=(
                                "MODEL_MAX_FILE_COUNT"
                            ),
                            value="10000",
                        ),
                    ],

                    env_from=[
                        client.V1EnvFromSource(
                            secret_ref=(
                                client
                                .V1SecretEnvSource(
                                    name=(
                                        self
                                        .ingestion_secret_name
                                    )
                                )
                            )
                        )
                    ],

                    resources=(
                        client
                        .V1ResourceRequirements(
                            requests={
                                "cpu": "500m",
                                "memory": "2Gi",
                            },

                            limits={
                                "cpu": "2",
                                "memory": "8Gi",
                            },
                        )
                    ),

                    security_context=(
                        client
                        .V1SecurityContext(
                            allow_privilege_escalation=(
                                False
                            ),

                            read_only_root_filesystem=(
                                True
                            ),

                            capabilities=(
                                client
                                .V1Capabilities(
                                    drop=[
                                        "ALL"
                                    ]
                                )
                            ),
                        )
                    ),

                    volume_mounts=[
                        client.V1VolumeMount(
                            name="workspace",

                            mount_path=(
                                "/workspace"
                            ),
                        ),

                        client.V1VolumeMount(
                            name="tmp",

                            mount_path="/tmp",
                        ),
                    ],
                )
            ],

            volumes=[
                client.V1Volume(
                    name="workspace",

                    persistent_volume_claim=(
                        client
                        .V1PersistentVolumeClaimVolumeSource(
                            claim_name=(
                                self
                                .workspace_pvc_name
                            )
                        )
                    ),
                ),

                client.V1Volume(
                    name="tmp",

                    empty_dir=(
                        client
                        .V1EmptyDirVolumeSource()
                    ),
                ),
            ],
        )

        job = client.V1Job(
            metadata=client.V1ObjectMeta(
                name=job_name,

                labels={
                    "app.kubernetes.io/name":
                        "model-ingestion",

                    "app.kubernetes.io/component":
                        "model-security-pipeline",

                    "app.kubernetes.io/part-of":
                        "ai-platform",

                    "platform.secureai.io/"
                    "model-request-id":
                        str(request_id),
                },
            ),

            spec=client.V1JobSpec(
                backoff_limit=0,

                ttl_seconds_after_finished=3600,

                template=(
                    client.V1PodTemplateSpec(
                        metadata=(
                            client.V1ObjectMeta(
                                labels={
                                    "app.kubernetes.io/name":
                                        "model-ingestion",

                                    "app.kubernetes.io/component":
                                        "model-security-pipeline",

                                    "app.kubernetes.io/part-of":
                                        "ai-platform",

                                    "platform.secureai.io/"
                                    "model-request-id":
                                        str(request_id),
                                }
                            )
                        ),

                        spec=pod_spec,
                    )
                ),
            ),
        )

        try:
            created = (
                self.batch
                .create_namespaced_job(
                    namespace=(
                        self.namespace
                    ),

                    body=job,
                )
            )

        except ApiException as exc:

            if exc.status == 409:

                raise (
                    ModelIngestionJobAlreadyExists(
                        f"Ingestion job "
                        f"'{job_name}' "
                        "already exists"
                    )
                ) from exc

            raise ModelIngestionError(
                "Could not create "
                f"ingestion job: {exc}"
            ) from exc

        return {
            "job_name": (
                created.metadata.name
            ),

            "namespace": (
                self.namespace
            ),

            "status": "submitted",
        }
