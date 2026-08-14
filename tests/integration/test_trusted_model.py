from pathlib import Path
from pprint import pprint

import yaml

from app.services.trusted_model_service import (
    TrustedModelService,
)


project_root = Path("..").resolve()

catalog_file = (
    project_root
    / "catalog"
    / "models"
    / "qwen3-0.6b.yaml"
)

with catalog_file.open(
    "r",
    encoding="utf-8",
) as stream:
    model = yaml.safe_load(stream)


artifact = model["spec"]["artifact"]


service = TrustedModelService(
    project_root=project_root,
)


result = service.verify(
    artifact
)


pprint(result)
