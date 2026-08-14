from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class PromotionError(Exception):
    pass


GENERATED_REPORTS = {
    "integrity-manifest.json",
    "security-attestation.json",
    "clamav-report.json",
    "yara-report.json",
    "detect-secrets-report.json",
    "security-gate.json",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PromotionError(
            f"Required file not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as stream:
        data = json.load(stream)

    if not isinstance(data, dict):
        raise PromotionError(
            f"{path} must contain a JSON object"
        )

    return data


def calculate_sha256(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        while chunk := stream.read(
            1024 * 1024
        ):
            digest.update(chunk)

    return digest.hexdigest()


def verify_gate(
    quarantine_dir: Path,
) -> dict[str, Any]:

    gate_path = (
        quarantine_dir
        / "security-gate.json"
    )

    gate = load_json(
        gate_path
    )

    try:
        status = gate["gate"]["status"]
        promotion_allowed = gate[
            "promotionAllowed"
        ]

    except KeyError as exc:
        raise PromotionError(
            "Invalid security-gate.json"
        ) from exc

    if status != "PASS":
        raise PromotionError(
            f"Security gate status is '{status}', "
            "promotion is forbidden"
        )

    if promotion_allowed is not True:
        raise PromotionError(
            "promotionAllowed is not true"
        )

    return gate


def verify_integrity(
    quarantine_dir: Path,
) -> dict[str, Any]:

    manifest_path = (
        quarantine_dir
        / "integrity-manifest.json"
    )

    manifest = load_json(
        manifest_path
    )

    for file_record in manifest["files"]:

        relative_path = file_record[
            "path"
        ]

        source_file = (
            quarantine_dir
            / relative_path
        )

        if not source_file.is_file():
            raise PromotionError(
                f"Missing artifact: {relative_path}"
            )

        if source_file.is_symlink():
            raise PromotionError(
                f"Symlink forbidden: {relative_path}"
            )

        actual_size = (
            source_file.stat().st_size
        )

        if actual_size != file_record["size"]:
            raise PromotionError(
                f"Size mismatch: {relative_path}"
            )

        actual_sha256 = calculate_sha256(
            source_file
        )

        if (
            actual_sha256
            != file_record["sha256"]
        ):
            raise PromotionError(
                f"SHA-256 mismatch: {relative_path}"
            )

    return manifest


def copy_model_artifacts(
    quarantine_dir: Path,
    trusted_dir: Path,
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:

    promoted_files = []

    for file_record in manifest["files"]:

        relative_path = Path(
            file_record["path"]
        )

        if relative_path.is_absolute():
            raise PromotionError(
                f"Absolute path forbidden: {relative_path}"
            )

        if ".." in relative_path.parts:
            raise PromotionError(
                f"Path traversal forbidden: {relative_path}"
            )

        source = (
            quarantine_dir
            / relative_path
        )

        destination = (
            trusted_dir
            / relative_path
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source,
            destination,
        )

        promoted_files.append(
            {
                "path": str(
                    relative_path
                ),
                "size": (
                    destination.stat().st_size
                ),
                "sha256": calculate_sha256(
                    destination
                ),
            }
        )

    return promoted_files


def write_promotion_manifest(
    trusted_dir: Path,
    gate: dict[str, Any],
    manifest: dict[str, Any],
    promoted_files: list[dict[str, Any]],
) -> Path:

    promotion_manifest = {
        "schemaVersion": 1,

        "model": manifest["model"],

        "source": manifest["source"],

        "promotion": {
            "status": "TRUSTED",

            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),

            "securityGate": {
                "status": gate[
                    "gate"
                ]["status"],

                "checks": gate[
                    "checks"
                ],
            },
        },

        "files": promoted_files,
    }

    promotion_manifest_path = (
        trusted_dir
        / "trusted-manifest.json"
    )

    with promotion_manifest_path.open(
        "w",
        encoding="utf-8",
    ) as stream:

        json.dump(
            promotion_manifest,
            stream,
            indent=2,
            ensure_ascii=False,
        )

        stream.write("\n")

    return promotion_manifest_path


def calculate_manifest_digest(
    manifest_path: Path,
) -> str:

    return calculate_sha256(
        manifest_path
    )


def promote_model(
    quarantine_dir: Path,
    trusted_root: Path,
) -> dict[str, Any]:

    gate = verify_gate(
        quarantine_dir
    )

    integrity_manifest = verify_integrity(
        quarantine_dir
    )

    model_name = integrity_manifest[
        "model"
    ]

    revision = integrity_manifest[
        "source"
    ]["resolvedRevision"]

    trusted_dir = (
        trusted_root
        / model_name
        / revision
    )

    if trusted_dir.exists():
        raise PromotionError(
            f"Trusted destination already exists: "
            f"{trusted_dir}"
        )

    trusted_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    try:
        promoted_files = copy_model_artifacts(
            quarantine_dir=quarantine_dir,
            trusted_dir=trusted_dir,
            manifest=integrity_manifest,
        )

        trusted_manifest = (
            write_promotion_manifest(
                trusted_dir=trusted_dir,
                gate=gate,
                manifest=integrity_manifest,
                promoted_files=promoted_files,
            )
        )

        trusted_manifest_digest = (
            calculate_manifest_digest(
                trusted_manifest
            )
        )

        digest_file = (
            trusted_dir
            / "trusted-manifest.sha256"
        )

        digest_file.write_text(
            (
                f"{trusted_manifest_digest}  "
                "trusted-manifest.json\n"
            ),
            encoding="utf-8",
        )

    except Exception:
        if trusted_dir.exists():
            shutil.rmtree(
                trusted_dir
            )

        raise

    return {
        "status": "TRUSTED",
        "model": model_name,
        "revision": revision,
        "directory": str(
            trusted_dir
        ),
        "manifest": str(
            trusted_manifest
        ),
        "manifest_sha256": (
            trusted_manifest_digest
        ),
        "files_count": len(
            promoted_files
        ),
    }


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Promote a quarantined AI model "
            "into the trusted model store "
            "after successful security gates."
        )
    )

    parser.add_argument(
        "--quarantine-dir",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--trusted-root",
        default=Path(
            "artifacts/trusted"
        ),
        type=Path,
    )

    args = parser.parse_args()

    try:
        result = promote_model(
            quarantine_dir=(
                args.quarantine_dir
            ),
            trusted_root=(
                args.trusted_root
            ),
        )

    except (
        PromotionError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:

        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "reason": str(
                        exc
                    ),
                },
                indent=2,
            )
        )

        raise SystemExit(
            2
        ) from exc

    print(
        json.dumps(
            result,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
