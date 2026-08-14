from pathlib import Path

import yaml

from kubernetes.client import ApiClient

from app.core.config import get_settings
from app.schemas.deployment import DeploymentCreate
from app.services.catalog_service import CatalogService
from app.services.deployment_service import DeploymentService
from app.services.kubernetes_service import KubernetesService
from app.services.trusted_model_service import TrustedModelService


settings = get_settings()

catalog = CatalogService(
    settings.catalog_path
)

trusted_models = TrustedModelService(
    project_root=Path("..")
)

deployment_service = DeploymentService(
    catalog=catalog,
    trusted_models=trusted_models,
)

request = DeploymentCreate(
    name="qwen-manifest-test",
    model="qwen3-0.6b",
    profile="interactive",
    runtime="vllm-cuda",
)

context = deployment_service.create_context(
    request
)

kubernetes_service = KubernetesService(
    namespace=settings.kubernetes_namespace,
    mode=settings.kubernetes_mode,
)

deployment = kubernetes_service.build_ai_deployment(
    name=context.name,
    image=context.image,
    repository=context.repository,
    served_model_name=context.model,
    model_artifact_reference=(
        context.model_artifact_reference
    ),
    port=context.port,
    replicas=context.replicas,
    cpu_request=context.cpu_request,
    memory_request=context.memory_request,
    cpu_limit=context.cpu_limit,
    memory_limit=context.memory_limit,
    gpu_count=context.gpu_count,
    max_model_len=context.max_model_len,
    node_selector=context.node_selector,
    model_mount_path=(
        context.model_cache_mount_path
    ),
    registry_secret_name=(
        "ai-model-registry-credentials"
    ),
    registry_insecure=True,
)

api_client = ApiClient()

manifest = api_client.sanitize_for_serialization(
    deployment
)

print(
    yaml.safe_dump(
        manifest,
        sort_keys=False,
    )
)
