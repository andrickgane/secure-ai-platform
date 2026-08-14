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


class ModelPromotionError(Exception):
    pass


class ModelPromotionJobAlreadyExists(
    ModelPromotionError
):
    pass


class ModelPromotionService:
    """
    Create an isolated Kubernetes Job responsible
    for trusted OCI model promotion.
    """

    def __init__(
        self,
        *,
        namespace: str,
        kubernetes_mode: str,
        promotion_image: str,
        ingestion_secret_name: str,
        signing_secret_name: str,
        workspace_pvc_name: str,
        image_pull_secret_name: str,
    ) -> None:

        self.namespace = namespace

        self.kubernetes_mode = (
            kubernetes_mode
        )

        self.promotion_image = (
            promotion_image
        )

        self.ingestion_secret_name = (
            ingestion_secret_name
        )

        self.signing_secret_name = (
            signing_secret_name
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
            f"model-promote-"
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
        repository: str,
        revision: str,
    ) -> dict[str, Any]:

        job_name = self._job_name(
            request_id=request_id,
            repository=repository,
        )

        labels = {
            "app.kubernetes.io/name":
                "model-promotion",

            "app.kubernetes.io/component":
                "trusted-model-promotion",

            "app.kubernetes.io/part-of":
                "ai-platform",

            "platform.secureai.io/"
            "model-request-id":
                str(request_id),
        }

        # ==================================================
        # POD SPEC
        # ==================================================

        pod_spec = client.V1PodSpec(
            restart_policy="Never",

            service_account_name=(
                "model-ingestion"
            ),

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

                    seccomp_profile=(
                        client
                        .V1SeccompProfile(
                            type=(
                                "RuntimeDefault"
                            )
                        )
                    ),
                )
            ),

            containers=[
                client.V1Container(
                    name="promotion",

                    image=(
                        self.promotion_image
                    ),

                    image_pull_policy=(
                        "Always"
                    ),

                    # ======================================
                    # ENV
                    # ======================================

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

                        # ----------------------------------
                        # Direct internal Zot endpoint
                        # ----------------------------------

                        client.V1EnvVar(
                            name="ACP_REGISTRY",
                            value=(
                                "zot.registry."
                                "svc.cluster.local:"
                                "5000"
                            ),
                        ),

                        # ----------------------------------
                        # Writable runtime directories
                        # ----------------------------------

                        client.V1EnvVar(
                            name="DOCKER_CONFIG",
                            value="/tmp/docker",
                        ),

                        client.V1EnvVar(
                            name="HOME",
                            value="/tmp/home",
                        ),

                        client.V1EnvVar(
                            name=(
                                "XDG_CONFIG_HOME"
                            ),
                            value="/tmp/xdg",
                        ),

                        client.V1EnvVar(
                            name=(
                                "XDG_CACHE_HOME"
                            ),
                            value="/tmp/cache",
                        ),

                        # ----------------------------------
                        # Cosign password
                        # ----------------------------------

                        client.V1EnvVar(
                            name=(
                                "COSIGN_PASSWORD"
                            ),

                            value_from=(
                                client
                                .V1EnvVarSource(
                                    secret_key_ref=(
                                        client
                                        .V1SecretKeySelector(
                                            name=(
                                                self
                                                .signing_secret_name
                                            ),

                                            key=(
                                                "COSIGN_PASSWORD"
                                            ),
                                        )
                                    )
                                )
                            ),
                        ),
                    ],

                    # ======================================
                    # DATABASE + ZOT CREDENTIALS
                    # ======================================

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

                    # ======================================
                    # SECURITY
                    # ======================================

                    security_context=(
                        client
                        .V1SecurityContext(
                            allow_privilege_escalation=(
                                False
                            ),

                            privileged=False,

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

                    # ======================================
                    # RESOURCES
                    # ======================================

                    resources=(
                        client
                        .V1ResourceRequirements(
                            requests={
                                "cpu": "500m",
                                "memory": "1Gi",
                            },

                            limits={
                                "cpu": "2",
                                "memory": "4Gi",
                            },
                        )
                    ),

                    # ======================================
                    # MOUNTS
                    # ======================================

                    volume_mounts=[
                        client.V1VolumeMount(
                            name="workspace",
                            mount_path="/workspace",
                        ),

                        client.V1VolumeMount(
                            name="tmp",
                            mount_path="/tmp",
                        ),

                        client.V1VolumeMount(
                            name="signing-key",
                            mount_path="/keys",
                            read_only=True,
                        ),
                    ],
                )
            ],

            # ==================================================
            # VOLUMES
            # ==================================================

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

                client.V1Volume(
                    name="signing-key",

                    secret=(
                        client
                        .V1SecretVolumeSource(
                            secret_name=(
                                self
                                .signing_secret_name
                            ),

                            default_mode=0o400,
                        )
                    ),
                ),
            ],
        )

        # ==================================================
        # JOB
        # ==================================================

        job = client.V1Job(
            metadata=(
                client.V1ObjectMeta(
                    name=job_name,
                    labels=labels,
                )
            ),

            spec=(
                client.V1JobSpec(
                    backoff_limit=0,

                    ttl_seconds_after_finished=(
                        3600
                    ),

                    template=(
                        client
                        .V1PodTemplateSpec(
                            metadata=(
                                client
                                .V1ObjectMeta(
                                    labels=labels,
                                )
                            ),

                            spec=pod_spec,
                        )
                    ),
                )
            ),
        )

        # ==================================================
        # CREATE
        # ==================================================

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
                    ModelPromotionJobAlreadyExists(
                        f"Promotion job "
                        f"'{job_name}' "
                        "already exists"
                    )
                ) from exc

            raise ModelPromotionError(
                "Could not create "
                f"promotion job: {exc}"
            ) from exc

        return {
            "job_name":
                created.metadata.name,

            "namespace":
                self.namespace,

            "status":
                "submitted",
        }
