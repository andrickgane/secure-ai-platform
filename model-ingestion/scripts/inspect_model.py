from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml
from huggingface_hub import HfApi
from huggingface_hub.errors import (
    RepositoryNotFoundError,
    RevisionNotFoundError,
)


class ModelInspectionError(Exception):
    pass


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ModelInspectionError(
            f"File not found: {path}"
        )

    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)

    if not isinstance(data, dict):
        raise ModelInspectionError(
            f"{path} must contain a YAML object"
        )

    return data


def get_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def inspect_model(
    request_path: Path,
    policy_path: Path,
) -> dict[str, Any]:

    request = load_yaml(request_path)
    policy = load_yaml(policy_path)

    request_spec = request["spec"]
    source = request_spec["source"]

    provider = source["provider"]
    repository = source["repository"]
    revision = source.get("revision", "main")

    policy_spec = policy["spec"]

    allowed_providers = (
        policy_spec
        .get("source", {})
        .get("allowedProviders", [])
    )

    if provider not in allowed_providers:
        return {
            "status": "DENY",
            "reason": f"Provider '{provider}' is not allowed",
        }

    if provider != "huggingface":
        return {
            "status": "DENY",
            "reason": "Only Hugging Face is implemented in V1",
        }

    api = HfApi()

    try:
        info = api.model_info(
            repo_id=repository,
            revision=revision,
            files_metadata=True,
            token=False,
        )

    except RepositoryNotFoundError as exc:
        raise ModelInspectionError(
            f"Repository not found: {repository}"
        ) from exc

    except RevisionNotFoundError as exc:
        raise ModelInspectionError(
            f"Revision not found: {revision}"
        ) from exc

    immutable_revision = info.sha

    if not immutable_revision:
        raise ModelInspectionError(
            "Hugging Face did not return an immutable commit SHA"
        )

    serialization = policy_spec.get(
        "serialization",
        {},
    )

    forbidden_extensions = set(
        serialization.get(
            "forbiddenExtensions",
            [],
        )
    )

    review_extensions = set(
        serialization.get(
            "reviewRequiredExtensions",
            [],
        )
    )

    files = []
    denied_files = []
    review_files = []

    for sibling in info.siblings or []:
        filename = sibling.rfilename
        extension = get_extension(filename)

        file_record = {
            "name": filename,
            "extension": extension,
            "size": getattr(
                sibling,
                "size",
                None,
            ),
        }

        files.append(file_record)

        if extension in forbidden_extensions:
            denied_files.append(file_record)

        elif extension in review_extensions:
            review_files.append(file_record)

    request_security = request_spec.get(
        "security",
        {},
    )

    allow_remote_code = request_security.get(
        "allowRemoteCode",
        False,
    )

    remote_code_allowed_by_policy = (
        policy_spec
        .get("remoteCode", {})
        .get("allowed", False)
    )

    if allow_remote_code and not remote_code_allowed_by_policy:
        return {
            "status": "DENY",
            "repository": repository,
            "requested_revision": revision,
            "resolved_revision": immutable_revision,
            "reason": "Remote code is forbidden by policy",
        }

    if denied_files:
        status = "DENY"
    elif review_files:
        status = "REVIEW"
    else:
        status = "PASS"

    return {
        "status": status,
        "repository": repository,
        "requested_revision": revision,
        "resolved_revision": immutable_revision,
        "private": bool(info.private),
        "gated": info.gated,
        "files_count": len(files),
        "files": files,
        "denied_files": denied_files,
        "review_files": review_files,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect a Hugging Face model without "
            "downloading or loading its weights."
        )
    )

    parser.add_argument(
        "--request",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--policy",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    try:
        result = inspect_model(
            request_path=args.request,
            policy_path=args.policy,
        )

    except (
        ModelInspectionError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            yaml.safe_dump(
                {
                    "status": "ERROR",
                    "reason": str(exc),
                },
                sort_keys=False,
            )
        )
        raise SystemExit(2) from exc

    print(
        yaml.safe_dump(
            result,
            sort_keys=False,
            allow_unicode=True,
        )
    )

    if result["status"] == "DENY":
        raise SystemExit(10)

    if result["status"] == "REVIEW":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
