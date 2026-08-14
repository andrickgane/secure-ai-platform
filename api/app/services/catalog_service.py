from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class CatalogError(Exception):
    """Base error for catalog operations."""


class CatalogItemNotFound(CatalogError):
    """Raised when a catalog item does not exist."""


class CatalogItemNotApproved(CatalogError):
    """Raised when a model exists but is not approved."""


class CatalogService:
    def __init__(
        self,
        catalog_path: str | Path,
    ) -> None:
        self.catalog_path = Path(
            catalog_path
        )

    # =========================================================
    # GENERIC LOAD
    # =========================================================

    def load(
        self,
        category: str,
        name: str,
    ) -> dict[str, Any]:
        """
        Load one YAML item from the catalog.

        Example:

        catalog/models/qwen3-0.6b.yaml
        catalog/profiles/interactive.yaml
        catalog/runtimes/vllm-metal.yaml
        """

        path = (
            self.catalog_path
            / category
            / f"{name}.yaml"
        )

        if not path.exists():
            raise CatalogItemNotFound(
                f"Catalog item "
                f"'{category}/{name}' "
                "does not exist"
            )

        if not path.is_file():
            raise CatalogError(
                f"Catalog path "
                f"'{path}' "
                "is not a file"
            )

        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as file:
                definition = yaml.safe_load(
                    file
                )

        except OSError as exc:
            raise CatalogError(
                f"Could not read catalog file "
                f"'{path}': {exc}"
            ) from exc

        except yaml.YAMLError as exc:
            raise CatalogError(
                f"Invalid YAML in "
                f"catalog file '{path}': "
                f"{exc}"
            ) from exc

        if not isinstance(
            definition,
            dict,
        ):
            raise CatalogError(
                f"Catalog file "
                f"'{path}' "
                "does not contain "
                "a YAML object"
            )

        metadata = definition.get(
            "metadata"
        )

        if not isinstance(
            metadata,
            dict,
        ):
            raise CatalogError(
                f"Catalog item "
                f"'{category}/{name}' "
                "does not define metadata"
            )

        catalog_name = metadata.get(
            "name"
        )

        if catalog_name != name:
            raise CatalogError(
                f"Catalog filename "
                f"'{name}' does not match "
                f"metadata.name "
                f"'{catalog_name}'"
            )

        spec = definition.get(
            "spec"
        )

        if not isinstance(
            spec,
            dict,
        ):
            raise CatalogError(
                f"Catalog item "
                f"'{category}/{name}' "
                "does not define spec"
            )

        return definition

    # =========================================================
    # MODEL LOAD + APPROVAL
    # =========================================================

    def load_approved_model(
        self,
        name: str,
    ) -> dict[str, Any]:
        """
        Load a model and ensure it is approved
        before it can be used by the platform.
        """

        definition = self.load(
            "models",
            name,
        )

        spec = definition["spec"]

        security = spec.get(
            "security",
            {},
        )

        if not isinstance(
            security,
            dict,
        ):
            raise CatalogError(
                f"Model '{name}' has "
                "an invalid security section"
            )

        approved = security.get(
            "approved",
            False,
        )

        if approved is not True:
            raise CatalogItemNotApproved(
                f"Model '{name}' "
                "is not approved"
            )

        return definition

    # =========================================================
    # LIST CATEGORY
    # =========================================================

    def list_items(
        self,
        category: str,
    ) -> list[dict[str, Any]]:
        """
        Load every YAML item from a catalog category.

        Example categories:

        models
        profiles
        runtimes
        """

        directory = (
            self.catalog_path
            / category
        )

        if not directory.exists():
            raise CatalogError(
                f"Catalog category "
                f"'{category}' "
                "does not exist"
            )

        if not directory.is_dir():
            raise CatalogError(
                f"Catalog category "
                f"'{category}' "
                "is not a directory"
            )

        results: list[
            dict[str, Any]
        ] = []

        for path in sorted(
            directory.glob("*.yaml")
        ):
            try:
                with path.open(
                    "r",
                    encoding="utf-8",
                ) as file:
                    definition = (
                        yaml.safe_load(
                            file
                        )
                    )

            except OSError as exc:
                raise CatalogError(
                    f"Could not read "
                    f"catalog file "
                    f"'{path}': {exc}"
                ) from exc

            except yaml.YAMLError as exc:
                raise CatalogError(
                    f"Invalid YAML in "
                    f"catalog file "
                    f"'{path}': {exc}"
                ) from exc

            if not isinstance(
                definition,
                dict,
            ):
                raise CatalogError(
                    f"Catalog file "
                    f"'{path}' "
                    "does not contain "
                    "a YAML object"
                )

            metadata = definition.get(
                "metadata"
            )

            spec = definition.get(
                "spec"
            )

            if not isinstance(
                metadata,
                dict,
            ):
                raise CatalogError(
                    f"Catalog file "
                    f"'{path}' "
                    "does not define metadata"
                )

            if not isinstance(
                spec,
                dict,
            ):
                raise CatalogError(
                    f"Catalog file "
                    f"'{path}' "
                    "does not define spec"
                )

            if not metadata.get(
                "name"
            ):
                raise CatalogError(
                    f"Catalog file "
                    f"'{path}' "
                    "does not define "
                    "metadata.name"
                )

            results.append(
                definition
            )

        return results

    # =========================================================
    # CONVENIENCE METHODS
    # =========================================================

    def list_models(
        self,
        approved_only: bool = True,
    ) -> list[dict[str, Any]]:
        """
        List catalog models.

        By default, only approved models are returned.
        """

        models = self.list_items(
            "models"
        )

        if not approved_only:
            return models

        approved_models: list[
            dict[str, Any]
        ] = []

        for model in models:
            spec = model.get(
                "spec",
                {},
            )

            security = spec.get(
                "security",
                {},
            )

            if (
                isinstance(
                    security,
                    dict,
                )
                and security.get(
                    "approved"
                )
                is True
            ):
                approved_models.append(
                    model
                )

        return approved_models

    def list_profiles(
        self,
    ) -> list[dict[str, Any]]:
        return self.list_items(
            "profiles"
        )

    def list_runtimes(
        self,
    ) -> list[dict[str, Any]]:
        return self.list_items(
            "runtimes"
        )
