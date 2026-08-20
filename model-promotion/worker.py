from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    create_engine,
    text,
)


# ==========================================================
# ENVIRONMENT
# ==========================================================

REQUEST_ID = int(
    os.environ["MODEL_REQUEST_ID"]
)

REPOSITORY = os.environ[
    "MODEL_REPOSITORY"
]

REVISION = os.environ[
    "MODEL_REVISION"
]

DATABASE_URL = os.environ[
    "ACP_DATABASE_URL"
]

REGISTRY = os.environ.get(
    "ACP_REGISTRY",
    "zot.registry.svc.cluster.local:5000",
)

REGISTRY_USERNAME = os.environ[
    "ACP_REGISTRY_USERNAME"
]

REGISTRY_PASSWORD = os.environ[
    "ACP_REGISTRY_PASSWORD"
]


# ==========================================================
# PATHS
# ==========================================================

REQUEST_ROOT = (
    Path("/workspace/requests")
    / str(REQUEST_ID)
)

QUARANTINE_DIR = (
    REQUEST_ROOT
    / "quarantine"
)

REPORT_FILE = (
    REQUEST_ROOT
    / "reports"
    / "security-report.json"
)

PACKAGE_DIR = (
    REQUEST_ROOT
    / "promotion"
)

PACKAGE_FILE = (
    PACKAGE_DIR
    / "model.tar"
)

COSIGN_KEY = Path(
    "/keys/cosign.key"
)


# ==========================================================
# DATABASE
# ==========================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


def update_request(
    *,
    status: str,
    message: str,
    artifact_reference: str | None = None,
    artifact_digest: str | None = None,
    catalog_model_id: str | None = None,
) -> None:

    fields = [
        "status = :status",
        "status_message = :message",
        "updated_at = :updated_at",
    ]

    values = {
        "request_id": REQUEST_ID,
        "status": status,
        "message": message,
        "updated_at": datetime.now(
            timezone.utc
        ),
    }

    if artifact_reference is not None:

        fields.append(
            "artifact_reference = "
            ":artifact_reference"
        )

        values[
            "artifact_reference"
        ] = artifact_reference

    if artifact_digest is not None:

        fields.append(
            "artifact_digest = "
            ":artifact_digest"
        )

        values[
            "artifact_digest"
        ] = artifact_digest

    if catalog_model_id is not None:

        fields.append(
            "catalog_model_id = "
            ":catalog_model_id"
        )

        values[
            "catalog_model_id"
        ] = catalog_model_id

    statement = text(
        f"""
        UPDATE model_requests
        SET {", ".join(fields)}
        WHERE id = :request_id
        """
    )

    with engine.begin() as connection:

        result = connection.execute(
            statement,
            values,
        )

        if result.rowcount != 1:

            raise RuntimeError(
                f"Model request "
                f"{REQUEST_ID} "
                "was not found"
            )


# ==========================================================
# COMMAND EXECUTION
# ==========================================================

def run(
    command: list[str],
    *,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:

    print(
        "RUN:",
        " ".join(command),
        flush=True,
    )

    result = subprocess.run(
        command,
        cwd=(
            str(cwd)
            if cwd is not None
            else None
        ),
        capture_output=True,
        text=True,
        check=False,
    )

    if result.stdout:

        print(
            result.stdout,
            flush=True,
        )

    if result.stderr:

        print(
            result.stderr,
            file=sys.stderr,
            flush=True,
        )

    if result.returncode != 0:

        raise RuntimeError(
            "Command failed: "
            + " ".join(command)
            + "\n"
            + result.stderr.strip()
        )

    return result


# ==========================================================
# MODEL NAME
# ==========================================================

def safe_model_name(
    repository: str,
) -> str:

    name = (
        repository
        .split("/")[-1]
        .lower()
    )

    return re.sub(
        r"[^a-z0-9._-]+",
        "-",
        name,
    ).strip("-")


# ==========================================================
# PACKAGE CREATION
# ==========================================================

def create_package() -> None:

    if not QUARANTINE_DIR.exists():

        raise RuntimeError(
            "Quarantine directory "
            "does not exist"
        )

    PACKAGE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if PACKAGE_FILE.exists():

        PACKAGE_FILE.unlink()

    run(
        [
            "tar",
            "-C",
            str(
                QUARANTINE_DIR
            ),
            "-cf",
            str(
                PACKAGE_FILE
            ),
            ".",
        ]
    )


# ==========================================================
# REGISTRY LOGIN
# ==========================================================

def registry_login() -> None:

    result = subprocess.run(
        [
            "oras",
            "login",

            "--plain-http",

            REGISTRY,

            "--username",
            REGISTRY_USERNAME,

            "--password-stdin",
        ],
        input=(
            REGISTRY_PASSWORD
            + "\n"
        ),
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:

        raise RuntimeError(
            "ORAS registry login failed: "
            + result.stderr.strip()
        )

    print(
        "ORAS login successful",
        flush=True,
    )


# ==========================================================
# OCI PUSH
# ==========================================================

def push_artifact(
    *,
    artifact_reference: str,
) -> str:

    package_relative = (
        PACKAGE_FILE
        .relative_to(
            REQUEST_ROOT
        )
    )

    report_relative = (
        REPORT_FILE
        .relative_to(
            REQUEST_ROOT
        )
    )

    command = [
        "oras",
        "push",

        "--plain-http",

        "--artifact-type",
        (
            "application/vnd."
            "secureai.model.v1"
        ),

        artifact_reference,

        (
            str(package_relative)
            + ":application/vnd."
            "secureai.model.tar"
        ),
    ]

    if REPORT_FILE.exists():

        command.append(
            str(report_relative)
            + ":application/json"
        )

    result = run(
        command,
        cwd=REQUEST_ROOT,
    )

    digest: str | None = None

    for line in (
        result.stdout.splitlines()
    ):

        clean_line = (
            line.strip()
        )

        if clean_line.startswith(
            "Digest:"
        ):

            digest = (
                clean_line
                .split(
                    "Digest:",
                    1,
                )[1]
                .strip()
            )

            break

    if not digest:

        result = run(
            [
                "oras",
                "manifest",
                "fetch",

                "--plain-http",

                "--descriptor",

                artifact_reference,
            ]
        )

        descriptor = json.loads(
            result.stdout
        )

        digest = descriptor[
            "digest"
        ]

    if not digest.startswith(
        "sha256:"
    ):

        raise RuntimeError(
            "Invalid OCI digest returned "
            f"by ORAS: {digest}"
        )

    return digest


# ==========================================================
# COSIGN
# ==========================================================

def sign_artifact(
    reference_with_digest: str,
) -> None:

    if not COSIGN_KEY.exists():

        raise RuntimeError(
            "Cosign private key "
            "was not mounted"
        )

    if not os.environ.get(
        "COSIGN_PASSWORD"
    ):

        raise RuntimeError(
            "COSIGN_PASSWORD "
            "is not available"
        )

    run(
        [
            "cosign",
            "sign",

            "--yes",

            "--allow-insecure-registry",

            "--key",
            str(
                COSIGN_KEY
            ),

            reference_with_digest,
        ]
    )

    print(
        "Cosign signature successful",
        flush=True,
    )


# ==========================================================
# MAIN
# ==========================================================

def main() -> int:

    try:

        update_request(
            status="promoting",
            message=(
                "Packaging approved model "
                "for trusted OCI promotion"
            ),
        )

        model_name = safe_model_name(
            REPOSITORY
        )

        short_revision = (
            REVISION[:12]
        )

        tag = (
            f"{model_name}-"
            f"{short_revision}"
        )

        repository_reference = (
            f"{REGISTRY}/"
            "ai-models-trusted/"
            f"{model_name}"
        )

        artifact_reference = (
            f"{repository_reference}:"
            f"{tag}"
        )

        # --------------------------------------------------
        # PACKAGE
        # --------------------------------------------------

        print(
            "Creating model package...",
            flush=True,
        )

        create_package()

        # --------------------------------------------------
        # LOGIN
        # --------------------------------------------------

        print(
            "Logging into Zot...",
            flush=True,
        )

        registry_login()

        # --------------------------------------------------
        # PUSH
        # --------------------------------------------------

        update_request(
            status="promoting",
            message=(
                "Pushing trusted model "
                "artifact directly to Zot"
            ),
        )

        print(
            "Pushing OCI artifact...",
            flush=True,
        )

        digest = push_artifact(
            artifact_reference=(
                artifact_reference
            )
        )

        immutable_reference = (
            f"{repository_reference}"
            f"@{digest}"
        )

        print(
            "OCI artifact pushed:",
            immutable_reference,
            flush=True,
        )

        # --------------------------------------------------
        # SIGN
        # --------------------------------------------------

        update_request(
            status="promoting",
            message=(
                "Signing trusted OCI "
                "artifact with Cosign"
            ),
            artifact_reference=(
                immutable_reference
            ),
            artifact_digest=(
                digest
            ),
        )

        print(
            "Signing OCI artifact...",
            flush=True,
        )

        sign_artifact(
            immutable_reference
        )

        # --------------------------------------------------
        # PUBLISHED
        # --------------------------------------------------

        update_request(
            status="published",

            message=(
                "Model successfully "
                "published to trusted "
                "OCI registry"
            ),

            artifact_reference=(
                immutable_reference
            ),

            artifact_digest=(
                digest
            ),

            catalog_model_id=(
                model_name
            ),
        )

        print(
            json.dumps(
                {
                    "request_id":
                        REQUEST_ID,

                    "status":
                        "published",

                    "repository":
                        REPOSITORY,

                    "revision":
                        REVISION,

                    "artifact_reference":
                        immutable_reference,

                    "artifact_digest":
                        digest,

                    "catalog_model_id":
                        model_name,
                },
                indent=2,
            ),
            flush=True,
        )

        return 0

    except Exception as exc:

        try:

            update_request(
                status="failed",
                message=str(exc),
            )

        except Exception as db_exc:

            print(
                "Could not update failure "
                f"status: {db_exc}",
                file=sys.stderr,
                flush=True,
            )

        print(
            f"Promotion failed: {exc}",
            file=sys.stderr,
            flush=True,
        )

        return 1


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
