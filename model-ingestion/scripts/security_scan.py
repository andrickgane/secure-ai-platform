from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


class SecurityScanError(Exception):
    pass


SECRET_PATTERNS = {
    "private_key": re.compile(
        rb"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
    "aws_access_key": re.compile(
        rb"\bAKIA[0-9A-Z]{16}\b"
    ),
    "generic_token": re.compile(
        rb"(?i)(api[_-]?key|access[_-]?token|secret)"
        rb"\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{16,}"
    ),
}


TEXT_EXTENSIONS = {
    ".json",
    ".txt",
    ".md",
    ".yaml",
    ".yml",
    ".py",
    ".sh",
    ".toml",
    ".ini",
    ".cfg",
}


EXECUTABLE_MAGIC = {
    b"\x7fELF": "ELF executable",
    b"MZ": "Windows PE executable",
}


def load_yaml(
    path: Path,
) -> dict[str, Any]:

    if not path.is_file():
        raise SecurityScanError(
            f"Policy not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as stream:
        data = yaml.safe_load(stream)

    if not isinstance(data, dict):
        raise SecurityScanError(
            "Policy must contain a YAML object"
        )

    return data


def load_json(
    path: Path,
) -> dict[str, Any]:

    if not path.is_file():
        raise SecurityScanError(
            f"JSON file not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as stream:
        data = json.load(stream)

    if not isinstance(data, dict):
        raise SecurityScanError(
            f"{path} must contain a JSON object"
        )

    return data


def calculate_sha256(
    path: Path,
) -> str:

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as stream:

        while chunk := stream.read(
            1024 * 1024
        ):
            digest.update(chunk)

    return digest.hexdigest()


def validate_integrity(
    quarantine_dir: Path,
    integrity_manifest: dict[str, Any],
) -> list[dict[str, Any]]:

    results = []

    for expected in integrity_manifest["files"]:

        relative_path = expected["path"]

        path = (
            quarantine_dir
            / relative_path
        )

        if not path.is_file():

            results.append(
                {
                    "file": relative_path,
                    "status": "DENY",
                    "reason": "missing file",
                }
            )

            continue

        if path.is_symlink():

            results.append(
                {
                    "file": relative_path,
                    "status": "DENY",
                    "reason": "symlink detected",
                }
            )

            continue

        actual_size = path.stat().st_size

        actual_hash = calculate_sha256(
            path
        )

        if actual_size != expected["size"]:

            results.append(
                {
                    "file": relative_path,
                    "status": "DENY",
                    "reason": "size mismatch",
                }
            )

            continue

        if actual_hash != expected["sha256"]:

            results.append(
                {
                    "file": relative_path,
                    "status": "DENY",
                    "reason": "SHA-256 mismatch",
                }
            )

            continue

        results.append(
            {
                "file": relative_path,
                "status": "PASS",
            }
        )

    return results


def inspect_magic_bytes(
    path: Path,
) -> list[str]:

    findings = []

    with path.open(
        "rb"
    ) as stream:

        header = stream.read(
            16
        )

    for (
        magic,
        description,
    ) in EXECUTABLE_MAGIC.items():

        if header.startswith(
            magic
        ):
            findings.append(
                description
            )

    return findings


def scan_secrets(
    path: Path,
) -> dict[str, Any]:

    if (
        path.suffix.lower()
        not in TEXT_EXTENSIONS
    ):

        return {
            "findings": [],
            "skipped": False,
        }

    findings = set()

    # Lecture par blocs de 1 MiB.
    chunk_size = (
        1024
        * 1024
    )

    # On conserve 4 KiB du bloc précédent.
    # Cela évite de rater un secret coupé
    # entre deux blocs.
    overlap_size = 4096

    previous_tail = b""

    with path.open(
        "rb"
    ) as stream:

        while True:

            chunk = stream.read(
                chunk_size
            )

            if not chunk:
                break

            data = (
                previous_tail
                + chunk
            )

            for (
                name,
                pattern,
            ) in SECRET_PATTERNS.items():

                if pattern.search(
                    data
                ):
                    findings.add(
                        name
                    )

            if (
                len(data)
                > overlap_size
            ):

                previous_tail = data[
                    -overlap_size:
                ]

            else:
                previous_tail = data

    return {
        "findings": sorted(
            findings
        ),
        "skipped": False,
    }


def inspect_safetensors(
    path: Path,
) -> dict[str, Any]:

    file_size = (
        path.stat().st_size
    )

    if file_size < 8:

        raise SecurityScanError(
            f"{path.name}: "
            "invalid safetensors file"
        )

    with path.open(
        "rb"
    ) as stream:

        first_eight = (
            stream.read(8)
        )

        header_size = struct.unpack(
            "<Q",
            first_eight,
        )[0]

        # Limite interne de sécurité.
        max_header_size = (
            16
            * 1024
            * 1024
        )

        if header_size == 0:

            raise SecurityScanError(
                f"{path.name}: "
                "empty safetensors header"
            )

        if (
            header_size
            > max_header_size
        ):

            raise SecurityScanError(
                f"{path.name}: "
                "safetensors header "
                f"too large "
                f"({header_size} bytes)"
            )

        if (
            8
            + header_size
            > file_size
        ):

            raise SecurityScanError(
                f"{path.name}: "
                "header exceeds file size"
            )

        header_bytes = stream.read(
            header_size
        )

    try:

        header = json.loads(
            header_bytes.decode(
                "utf-8"
            )
        )

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:

        raise SecurityScanError(
            f"{path.name}: "
            "invalid safetensors "
            "JSON header"
        ) from exc

    if not isinstance(
        header,
        dict,
    ):

        raise SecurityScanError(
            f"{path.name}: "
            "header must be an object"
        )

    tensor_count = 0
    highest_offset = 0

    data_area_size = (
        file_size
        - 8
        - header_size
    )

    for (
        tensor_name,
        metadata,
    ) in header.items():

        if (
            tensor_name
            == "__metadata__"
        ):
            continue

        if not isinstance(
            metadata,
            dict,
        ):

            raise SecurityScanError(
                f"{path.name}: "
                "invalid metadata "
                f"for tensor "
                f"{tensor_name}"
            )

        offsets = metadata.get(
            "data_offsets"
        )

        shape = metadata.get(
            "shape"
        )

        dtype = metadata.get(
            "dtype"
        )

        if (
            not isinstance(
                offsets,
                list,
            )
            or len(offsets) != 2
        ):

            raise SecurityScanError(
                f"{path.name}: "
                "invalid offsets "
                f"for tensor "
                f"{tensor_name}"
            )

        start, end = offsets

        if (
            not isinstance(
                start,
                int,
            )
            or not isinstance(
                end,
                int,
            )
        ):

            raise SecurityScanError(
                f"{path.name}: "
                "non-integer offsets"
            )

        if (
            start < 0
            or end < start
        ):

            raise SecurityScanError(
                f"{path.name}: "
                "invalid tensor offsets"
            )

        if (
            end
            > data_area_size
        ):

            raise SecurityScanError(
                f"{path.name}: "
                "tensor offsets "
                "exceed data area"
            )

        if not isinstance(
            shape,
            list,
        ):

            raise SecurityScanError(
                f"{path.name}: "
                "invalid tensor shape"
            )

        if not isinstance(
            dtype,
            str,
        ):

            raise SecurityScanError(
                f"{path.name}: "
                "invalid tensor dtype"
            )

        highest_offset = max(
            highest_offset,
            end,
        )

        tensor_count += 1

    return {
        "status": "PASS",
        "header_size": header_size,
        "tensor_count": tensor_count,
        "data_area_size": data_area_size,
        "highest_tensor_offset": (
            highest_offset
        ),
    }


def scan_quarantine(
    quarantine_dir: Path,
    policy_path: Path,
) -> dict[str, Any]:

    policy = load_yaml(
        policy_path
    )

    manifest_path = (
        quarantine_dir
        / "integrity-manifest.json"
    )

    integrity_manifest = (
        load_json(
            manifest_path
        )
    )

    integrity_results = (
        validate_integrity(
            quarantine_dir,
            integrity_manifest,
        )
    )

    findings = []

    safetensors_results = []

    policy_spec = (
        policy["spec"]
    )

    forbidden_extensions = set(
        policy_spec
        .get(
            "serialization",
            {},
        )
        .get(
            "forbiddenExtensions",
            [],
        )
    )

    review_extensions = set(
        policy_spec
        .get(
            "serialization",
            {},
        )
        .get(
            "reviewRequiredExtensions",
            [],
        )
    )

    for file_record in (
        integrity_manifest["files"]
    ):

        relative_path = (
            file_record["path"]
        )

        path = (
            quarantine_dir
            / relative_path
        )

        if not path.is_file():
            continue

        extension = (
            path.suffix.lower()
        )

        # --------------------------------------------------
        # Extension policy
        # --------------------------------------------------

        if (
            extension
            in forbidden_extensions
        ):

            findings.append(
                {
                    "severity": "DENY",
                    "file": relative_path,
                    "type": (
                        "forbidden_extension"
                    ),
                }
            )

        if (
            extension
            in review_extensions
        ):

            findings.append(
                {
                    "severity": "REVIEW",
                    "file": relative_path,
                    "type": (
                        "review_required_extension"
                    ),
                }
            )

        # --------------------------------------------------
        # Executable magic bytes
        # --------------------------------------------------

        magic_findings = (
            inspect_magic_bytes(
                path
            )
        )

        for finding in (
            magic_findings
        ):

            findings.append(
                {
                    "severity": "DENY",
                    "file": relative_path,
                    "type": (
                        "unexpected_executable"
                    ),
                    "detail": finding,
                }
            )

        # --------------------------------------------------
        # Secret scan
        # --------------------------------------------------

        secret_scan = (
            scan_secrets(
                path
            )
        )

        for finding in (
            secret_scan[
                "findings"
            ]
        ):

            findings.append(
                {
                    "severity": "REVIEW",
                    "file": relative_path,
                    "type": (
                        "possible_secret"
                    ),
                    "detail": finding,
                }
            )

        if secret_scan.get(
            "skipped"
        ):

            findings.append(
                {
                    "severity": "REVIEW",
                    "file": relative_path,
                    "type": (
                        "secret_scan_skipped"
                    ),
                    "detail": (
                        secret_scan.get(
                            "reason"
                        )
                    ),
                }
            )

        # --------------------------------------------------
        # Safetensors static validation
        # --------------------------------------------------

        if (
            extension
            == ".safetensors"
        ):

            try:

                result = (
                    inspect_safetensors(
                        path
                    )
                )

                safetensors_results.append(
                    {
                        "file": (
                            relative_path
                        ),
                        **result,
                    }
                )

            except (
                SecurityScanError
            ) as exc:

                findings.append(
                    {
                        "severity": "DENY",
                        "file": (
                            relative_path
                        ),
                        "type": (
                            "invalid_safetensors"
                        ),
                        "detail": str(
                            exc
                        ),
                    }
                )

    # ------------------------------------------------------
    # Integrity result
    # ------------------------------------------------------

    integrity_failed = any(
        item["status"]
        != "PASS"
        for item
        in integrity_results
    )

    # ------------------------------------------------------
    # Findings classification
    # ------------------------------------------------------

    deny_findings = [
        item
        for item
        in findings
        if item["severity"]
        == "DENY"
    ]

    review_findings = [
        item
        for item
        in findings
        if item["severity"]
        == "REVIEW"
    ]

    # ------------------------------------------------------
    # Final status
    # ------------------------------------------------------

    if (
        integrity_failed
        or deny_findings
    ):

        status = "DENY"

    elif review_findings:

        status = "REVIEW"

    else:

        status = "PASS"

    # ------------------------------------------------------
    # Attestation
    # ------------------------------------------------------

    return {
        "schemaVersion": 1,

        "model": integrity_manifest[
            "model"
        ],

        "source": integrity_manifest[
            "source"
        ],

        "scan": {
            "status": status,

            "timestamp": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),

            "scanner": {
                "name": (
                    "ai-control-plane-"
                    "static-scanner"
                ),
                "version": "0.1.2",
            },
        },

        "integrity": {
            "status": (
                "PASS"
                if not integrity_failed
                else "DENY"
            ),

            "files": (
                integrity_results
            ),
        },

        "safetensors": (
            safetensors_results
        ),

        "findings": findings,
    }


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Statically scan a "
            "quarantined AI model "
            "without loading or "
            "executing it."
        )
    )

    parser.add_argument(
        "--quarantine-dir",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--policy",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--output",
        type=Path,
    )

    args = parser.parse_args()

    try:

        result = scan_quarantine(
            quarantine_dir=(
                args.quarantine_dir
            ),
            policy_path=(
                args.policy
            ),
        )

    except (
        SecurityScanError,
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

    output_path = (
        args.output
    )

    if output_path is None:

        output_path = (
            args.quarantine_dir
            / "security-attestation.json"
        )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as stream:

        json.dump(
            result,
            stream,
            indent=2,
            ensure_ascii=False,
        )

        stream.write(
            "\n"
        )

    print(
        json.dumps(
            {
                "status": result[
                    "scan"
                ]["status"],

                "attestation": str(
                    output_path
                ),

                "findings": len(
                    result[
                        "findings"
                    ]
                ),
            },
            indent=2,
        )
    )

    status = result[
        "scan"
    ]["status"]

    if status == "DENY":

        raise SystemExit(
            10
        )

    if status == "REVIEW":

        raise SystemExit(
            20
        )


if __name__ == "__main__":
    main()
