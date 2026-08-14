from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from huggingface_hub import HfApi, snapshot_download
from huggingface_hub.errors import (
    RepositoryNotFoundError,
    RevisionNotFoundError,
)


class QuarantineError(Exception):
    pass


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise QuarantineError(
            f"File not found: {path}"
        )

    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)

    if not isinstance(data, dict):
        raise QuarantineError(
            f"{path} must contain a YAML object"
        )

    return data


def get_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def validate_relative_path(filename: str) -> None:
    path = Path(filename)

    if path.is_absolute():
        raise QuarantineError(
            f"Absolute path forbidden: {filename}"
        )

    if ".." in path.parts:
        raise QuarantineError(
            f"Path traversal detected: {filename}"
        )


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def inspect_repository(
    repository: str,
    revision: str,
    policy: dict[str, Any],
) -> dict[str, Any]:

    api = HfApi()

    try:
        info = api.model_info(
            repo_id=repository,
            revision=revision,
            files_metadata=True,
            token=False,
        )

    except RepositoryNotFoundError as exc:
        raise QuarantineError(
            f"Repository not found: {repository}"
        ) from exc

    except RevisionNotFoundError as exc:
        raise QuarantineError(
            f"Revision not found: {revision}"
        ) from exc

    immutable_revision = info.sha

    if not immutable_revision:
        raise QuarantineError(
            "Hugging Face did not return a commit SHA"
        )

    policy_spec = policy["spec"]

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

    files: list[dict[str, Any]] = []
    denied_files: list[str] = []
    review_files: list[str] = []

    for sibling in info.siblings or []:
        filename = sibling.rfilename

        validate_relative_path(filename)

        extension = get_extension(filename)

        files.append(
            {
                "name": filename,
                "extension": extension,
                "expected_size": getattr(
                    sibling,
                    "size",
                    None,
                ),
            }
        )

        if extension in forbidden_extensions:
            denied_files.append(filename)

        elif extension in review_extensions:
            review_files.append(filename)

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
        "files": files,
        "denied_files": denied_files,
        "review_files": review_files,
    }


def verify_downloaded_files(
    quarantine_dir: Path,
    expected_files: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    manifest_files = []

    for expected in expected_files:
        filename = expected["name"]

        validate_relative_path(filename)

        file_path = quarantine_dir / filename

        if not file_path.is_file():
            raise QuarantineError(
                f"Expected file missing after download: {filename}"
            )

        # Refuse symlinks in the promoted artifact tree.
        if file_path.is_symlink():
            raise QuarantineError(
                f"Symlink detected: {filename}"
            )

        actual_size = file_path.stat().st_size
        expected_size = expected.get(
            "expected_size"
        )

        if (
            expected_size is not None
            and actual_size != expected_size
        ):
            raise QuarantineError(
                f"Size mismatch for {filename}: "
                f"expected {expected_size}, "
                f"got {actual_size}"
            )

        manifest_files.append(
            {
                "path": filename,
                "size": actual_size,
                "sha256": calculate_sha256(
                    file_path
                ),
            }
        )

    return manifest_files


def write_integrity_manifest(
    quarantine_dir: Path,
    request_name: str,
    repository: str,
    requested_revision: str,
    resolved_revision: str,
    files: list[dict[str, Any]],
) -> Path:

    manifest = {
        "schemaVersion": 1,
        "model": request_name,
        "source": {
            "provider": "huggingface",
            "repository": repository,
            "requestedRevision": requested_revision,
            "resolvedRevision": resolved_revision,
        },
        "createdAt": (
            datetime.now(timezone.utc)
            .isoformat()
        ),
        "files": files,
    }

    manifest_path = (
        quarantine_dir
        / "integrity-manifest.json"
    )

    with manifest_path.open(
        "w",
        encoding="utf-8",
    ) as stream:
        json.dump(
            manifest,
            stream,
            indent=2,
            ensure_ascii=False,
        )

        stream.write("\n")

    return manifest_path


def download_to_quarantine(
    request_path: Path,
    policy_path: Path,
    artifacts_root: Path,
) -> dict[str, Any]:

    request = load_yaml(
        request_path
    )

    policy = load_yaml(
        policy_path
    )

    request_name = request[
        "metadata"
    ]["name"]

    request_spec = request["spec"]
    source = request_spec["source"]

    provider = source["provider"]
    repository = source["repository"]
    revision = source.get(
        "revision",
        "main",
    )

    if provider != "huggingface":
        raise QuarantineError(
            "Only Hugging Face is supported"
        )

    allowed_providers = (
        policy["spec"]
        .get("source", {})
        .get("allowedProviders", [])
    )

    if provider not in allowed_providers:
        raise QuarantineError(
            f"Provider '{provider}' is forbidden"
        )

    allow_remote_code = (
        request_spec
        .get("security", {})
        .get("allowRemoteCode", False)
    )

    policy_remote_code = (
        policy["spec"]
        .get("remoteCode", {})
        .get("allowed", False)
    )

    if (
        allow_remote_code
        and not policy_remote_code
    ):
        raise QuarantineError(
            "Remote code forbidden by policy"
        )

    inspection = inspect_repository(
        repository=repository,
        revision=revision,
        policy=policy,
    )

    if inspection["status"] != "PASS":
        raise QuarantineError(
            "Model inspection did not PASS. "
            f"Status={inspection['status']}"
        )

    resolved_revision = inspection[
        "resolved_revision"
    ]

    quarantine_dir = (
        artifacts_root
        / "quarantine"
        / request_name
        / resolved_revision
    )

    # Fail closed instead of mixing two revisions.
    if quarantine_dir.exists():
        raise QuarantineError(
            f"Quarantine directory already exists: "
            f"{quarantine_dir}"
        )

    quarantine_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    try:
        snapshot_download(
            repo_id=repository,

            # CRITICAL:
            # download the immutable SHA,
            # never "main".
            revision=resolved_revision,

            local_dir=quarantine_dir,

            # Public model:
            # don't reuse any local HF token.
            token=False,
        )

        # Hugging Face creates local metadata under
        # local_dir/.cache/huggingface when local_dir is used.
        hf_metadata = (
            quarantine_dir
            / ".cache"
            / "huggingface"
        )

        if hf_metadata.exists():
            shutil.rmtree(
                hf_metadata
            )

        # Refuse symlinks anywhere in quarantine.
        for path in quarantine_dir.rglob("*"):
            if path.is_symlink():
                raise QuarantineError(
                    f"Symlink found after download: {path}"
                )

        manifest_files = verify_downloaded_files(
            quarantine_dir=quarantine_dir,
            expected_files=inspection["files"],
        )

        manifest_path = write_integrity_manifest(
            quarantine_dir=quarantine_dir,
            request_name=request_name,
            repository=repository,
            requested_revision=revision,
            resolved_revision=resolved_revision,
            files=manifest_files,
        )

    except Exception:
        # Fail closed:
        # incomplete quarantine content is deleted.
        if quarantine_dir.exists():
            shutil.rmtree(
                quarantine_dir
            )

        raise

    return {
        "status": "QUARANTINED",
        "model": request_name,
        "repository": repository,
        "resolved_revision": resolved_revision,
        "directory": str(
            quarantine_dir
        ),
        "manifest": str(
            manifest_path
        ),
        "files_count": len(
            manifest_files
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Securely download an immutable "
            "Hugging Face model revision "
            "into quarantine."
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

    parser.add_argument(
        "--artifacts-root",
        default=Path("../artifacts"),
        type=Path,
    )

    args = parser.parse_args()

    try:
        result = download_to_quarantine(
            request_path=args.request,
            policy_path=args.policy,
            artifacts_root=args.artifacts_root,
        )

    except (
        QuarantineError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:

        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "reason": str(exc),
                },
                indent=2,
            )
        )

        raise SystemExit(2) from exc

    print(
        json.dumps(
            result,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
