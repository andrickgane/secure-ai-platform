from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from huggingface_hub import (
    HfApi,
    snapshot_download,
)
from sqlalchemy import (
    create_engine,
    text,
)


# ==========================================================
# CONFIGURATION
# ==========================================================

REQUEST_ID = int(
    os.environ["MODEL_REQUEST_ID"]
)

PROVIDER = os.environ[
    "MODEL_PROVIDER"
]

REPOSITORY = os.environ[
    "MODEL_REPOSITORY"
]

REQUESTED_REVISION = os.environ.get(
    "MODEL_REVISION",
    "main",
)

DATABASE_URL = os.environ[
    "ACP_DATABASE_URL"
]

HF_TOKEN = os.environ.get(
    "HF_TOKEN"
)


WORKSPACE_ROOT = Path(
    "/workspace/requests"
)

REQUEST_ROOT = (
    WORKSPACE_ROOT
    / str(REQUEST_ID)
)

QUARANTINE_DIR = (
    REQUEST_ROOT
    / "quarantine"
)

REPORT_DIR = (
    REQUEST_ROOT
    / "reports"
)

REPORT_FILE = (
    REPORT_DIR
    / "security-report.json"
)


# ==========================================================
# SECURITY POLICY
# ==========================================================

# File types capable of introducing executable code
# or unsafe deserialisation are rejected in this V1.

FORBIDDEN_SUFFIXES = {
    ".py",
    ".pyc",
    ".pyo",
    ".so",
    ".dylib",
    ".dll",
    ".exe",
    ".sh",
    ".bash",
    ".bat",
    ".cmd",
    ".ps1",
    ".jar",
    ".whl",

    # Unsafe model serialisation formats
    ".pkl",
    ".pickle",
    ".pt",
    ".pth",
    ".ckpt",
}


# Hugging Face repositories may contain tokenizer/config
# files in addition to Safetensors.

REQUIRED_WEIGHT_SUFFIX = (
    ".safetensors"
)


# Prevent an accidental ingestion from exhausting
# the quarantine storage.

MAX_FILE_COUNT = int(
    os.environ.get(
        "MODEL_MAX_FILE_COUNT",
        "10000",
    )
)

MAX_TOTAL_BYTES = int(
    os.environ.get(
        "MODEL_MAX_TOTAL_BYTES",
        str(
            100 * 1024**3
        ),
    )
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
    revision: str | None = None,
) -> None:

    values: dict[str, Any] = {
        "request_id": REQUEST_ID,
        "status": status,
        "message": message,
        "updated_at": datetime.now(
            timezone.utc
        ),
    }

    revision_sql = ""

    if revision is not None:
        revision_sql = (
            ", revision = :revision"
        )

        values["revision"] = revision

    statement = text(
        f"""
        UPDATE model_requests
        SET
            status = :status,
            status_message = :message,
            updated_at = :updated_at
            {revision_sql}
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
                "Model request "
                f"{REQUEST_ID} "
                "was not found"
            )


# ==========================================================
# HELPERS
# ==========================================================

def sha256_file(
    path: Path,
) -> str:

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:

        while True:

            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def scan_filesystem() -> dict[str, Any]:

    files: list[dict[str, Any]] = []

    forbidden: list[str] = []

    safetensors: list[str] = []

    total_size = 0

    for path in sorted(
        QUARANTINE_DIR.rglob("*")
    ):

        if not path.is_file():
            continue

        # Ignore Hugging Face download metadata.

        if ".cache" in path.parts:
            continue

        relative = path.relative_to(
            QUARANTINE_DIR
        )

        size = path.stat().st_size

        total_size += size

        suffix = path.suffix.lower()

        if suffix in FORBIDDEN_SUFFIXES:
            forbidden.append(
                str(relative)
            )

        if suffix == REQUIRED_WEIGHT_SUFFIX:
            safetensors.append(
                str(relative)
            )

        files.append(
            {
                "path": str(relative),

                "size": size,

                "sha256": (
                    sha256_file(path)
                ),
            }
        )

        if len(files) > MAX_FILE_COUNT:
            raise RuntimeError(
                "Repository exceeds "
                f"maximum file count "
                f"({MAX_FILE_COUNT})"
            )

        if total_size > MAX_TOTAL_BYTES:
            raise RuntimeError(
                "Repository exceeds "
                "maximum allowed size "
                f"({MAX_TOTAL_BYTES} bytes)"
            )

    if not files:
        raise RuntimeError(
            "Downloaded repository "
            "contains no files"
        )

    if not safetensors:
        raise RuntimeError(
            "No Safetensors weights "
            "were found"
        )

    if forbidden:
        raise RuntimeError(
            "Forbidden or unsafe files "
            "detected: "
            + ", ".join(
                forbidden[:20]
            )
        )

    return {
        "file_count": len(files),

        "total_bytes": total_size,

        "safetensors": (
            safetensors
        ),

        "files": files,
    }


def run_gitleaks() -> dict[str, Any]:

    report_path = (
        REPORT_DIR
        / "gitleaks.json"
    )

    command = [
        "gitleaks",
        "detect",

        "--no-git",

        "--source",
        str(
            QUARANTINE_DIR
        ),

        "--report-format",
        "json",

        "--report-path",
        str(
            report_path
        ),

        "--exit-code",
        "10",
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    # 0 = clean
    # 10 = leaks detected
    # everything else = scanner error

    if result.returncode == 10:

        findings: Any = []

        if report_path.exists():

            try:
                findings = json.loads(
                    report_path.read_text()
                )

            except json.JSONDecodeError:
                findings = []

        raise RuntimeError(
            "Gitleaks detected "
            f"{len(findings)} "
            "potential secret(s)"
        )

    if result.returncode != 0:

        raise RuntimeError(
            "Gitleaks execution failed: "
            + (
                result.stderr.strip()
                or result.stdout.strip()
                or (
                    "exit code "
                    f"{result.returncode}"
                )
            )
        )

    return {
        "status": "clean",
        "return_code": (
            result.returncode
        ),
    }


def write_report(
    report: dict[str, Any],
) -> None:

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_FILE.write_text(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )


# ==========================================================
# INGESTION
# ==========================================================

def main() -> int:

    if PROVIDER != "huggingface":

        update_request(
            status="rejected",

            message=(
                "Unsupported provider: "
                f"{PROVIDER}"
            ),
        )

        return 2


    try:

        REQUEST_ROOT.mkdir(
            parents=True,
            exist_ok=True,
        )

        REPORT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Start from a clean quarantine directory
        # when retrying a failed request.

        if QUARANTINE_DIR.exists():
            shutil.rmtree(
                QUARANTINE_DIR
            )

        QUARANTINE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )


        # ==================================================
        # RESOLVE IMMUTABLE REVISION
        # ==================================================

        update_request(
            status="quarantined",

            message=(
                "Resolving Hugging Face "
                "repository revision"
            ),
        )

        api = HfApi(
            token=HF_TOKEN
        )

        info = api.model_info(
            repo_id=REPOSITORY,
            revision=REQUESTED_REVISION,
        )

        resolved_revision = info.sha

        if not resolved_revision:
            raise RuntimeError(
                "Hugging Face did not "
                "return a commit SHA"
            )


        # ==================================================
        # DOWNLOAD
        # ==================================================

        update_request(
            status="quarantined",

            revision=(
                resolved_revision
            ),

            message=(
                "Downloading immutable "
                "Hugging Face snapshot "
                f"{resolved_revision}"
            ),
        )

        snapshot_download(
            repo_id=REPOSITORY,

            revision=(
                resolved_revision
            ),

            local_dir=str(
                QUARANTINE_DIR
            ),

            token=HF_TOKEN,
        )


        # ==================================================
        # SECURITY SCANNING
        # ==================================================

        update_request(
            status="scanning",

            message=(
                "Running model "
                "security checks"
            ),
        )


        filesystem_report = (
            scan_filesystem()
        )


        gitleaks_report = (
            run_gitleaks()
        )


        report = {
            "request_id": (
                REQUEST_ID
            ),

            "provider": PROVIDER,

            "repository": REPOSITORY,

            "requested_revision": (
                REQUESTED_REVISION
            ),

            "resolved_revision": (
                resolved_revision
            ),

            "generated_at": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),

            "filesystem": (
                filesystem_report
            ),

            "gitleaks": (
                gitleaks_report
            ),

            "decision": "approved",
        }

        write_report(
            report
        )


        # ==================================================
        # APPROVED
        # ==================================================

        update_request(
            status="approved",

            revision=(
                resolved_revision
            ),

            message=(
                "Quarantine security "
                "gate passed; model is "
                "ready for trusted "
                "OCI promotion"
            ),
        )

        print(
            json.dumps(
                {
                    "status": "approved",

                    "request_id": (
                        REQUEST_ID
                    ),

                    "repository": (
                        REPOSITORY
                    ),

                    "revision": (
                        resolved_revision
                    ),

                    "report": str(
                        REPORT_FILE
                    ),
                },
                indent=2,
            )
        )

        return 0


    except Exception as exc:

        failure = {
            "request_id": (
                REQUEST_ID
            ),

            "provider": PROVIDER,

            "repository": (
                REPOSITORY
            ),

            "requested_revision": (
                REQUESTED_REVISION
            ),

            "generated_at": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),

            "decision": "rejected",

            "error": str(exc),
        }

        try:
            write_report(
                failure
            )

        except Exception:
            pass

        try:
            update_request(
                status="rejected",

                message=str(exc),
            )

        except Exception as db_exc:

            print(
                "Could not update "
                "model request status:",
                db_exc,
                file=sys.stderr,
            )

        print(
            f"Ingestion rejected: {exc}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
