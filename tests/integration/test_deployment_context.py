from pathlib import Path
from pprint import pprint

from app.core.config import get_settings
from app.schemas.deployment import DeploymentCreate
from app.services.catalog_service import CatalogService
from app.services.deployment_service import DeploymentService
from app.services.trusted_model_service import TrustedModelService


settings = get_settings()

catalog = CatalogService(
    settings.catalog_path
)

trusted_models = TrustedModelService(
    project_root=Path("..")
)

service = DeploymentService(
    catalog=catalog,
    trusted_models=trusted_models,
)

request = DeploymentCreate(
    name="qwen-context-test",
    model="qwen3-0.6b",
    profile="interactive",
    runtime="vllm-cuda",
)

context = service.create_context(
    request
)

pprint(
    context.model_dump()
)
