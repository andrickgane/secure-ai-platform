from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from detect_secrets import SecretsCollection
from detect_secrets.settings import transient_settings


class DetectSecretsScanError(Exception):
    pass


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


PLUGIN_CONFIG = [
    {"name": "ArtifactoryDetector"},
    {"name": "AWSKeyDetector"},
    {"name": "AzureStorageKeyDetector"},
    {"name": "Base64HighEntropyString", "limit": 4.5},
    {"name": "BasicAuthDetector"},
    {"name": "GitHubTokenDetector"},
    {"name": "GitLabTokenDetector"},
    {"name": "HexHighEntropyString", "limit": 3.0},
    {"name": "JwtTokenDetector"},
    {"name": "KeywordDetector"},
    {"name": "OpenAIDetector"},
    {"name": "PrivateKeyDetector"},
    {"name": "SlackDetector"},
    {"name": "StripeDetector"},
]


ENTROPY_TYPES = {
    "Base64 High Entropy String",
    "Hex High Entropy String",
}


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise DetectSecretsScanError(
            f"Policy not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as stream:
        data = yaml.safe_load(stream)

    if not isinstance(data, dict):
        raise DetectSecretsScanError(
            "Policy must contain a YAML object"
        )

    return data


def run_self_test() -> None:
    test_file = Path(
        "/tmp/detect-secrets-ai-platform-selftest.txt"
    )

    test_file.write_text(
        'api_key = "n7Qp4Xz9Lm2Va8Ks5Rt3Wy6Bc1Hd9Jf7"\n',
        encoding="utf-8",
    )

    secrets = SecretsCollection()

    with transient_settings(
        {
            "plugins_used": PLUGIN_CONFIG,
            "filters_used": [],
        }
    ):
        secrets.scan_file(
            str(test_file)
        )

    findings = list(
        secrets.data.get(
            str(test_file),
            [],
        )
    )

    try:
        test_file.unlink()
    except FileNotFoundError:
        pass

    if not findings:
        raise DetectSecretsScanError(
            "detect-secrets self-test failed: "
            "the canary secret was not detected"
        )


def get_line_content(
    path: Path,
    line_number: int,
) -> str:
    try:
        with path.open(
            "r",
            encoding="utf-8",
            errors="replace",
        ) as stream:
            for current, line in enumerate(
                stream,
                start=1,
            ):
                if current == line_number:
                    return line.strip()

    except OSError:
        return ""

    return ""


def scan_file(
    path: Path,
) -> list[dict[str, Any]]:
    secrets = SecretsCollection()

    with transient_settings(
        {
            "plugins_used": PLUGIN_CONFIG,
            "filters_used": [],
        }
    ):
        secrets.scan_file(
            str(path)
        )

    findings = []

    for secret in secrets.data.get(
        str(path),
        [],
    ):
        findings.append(
            {
                "type": secret.type,
                "line_number": secret.line_number,
                "filename": str(path),
                "line": get_line_content(
                    path,
                    secret.line_number,
                ),
            }
        )

    return findings


def classify_finding(
    finding: dict[str, Any],
    quarantine_dir: Path,
    policy: dict[str, Any],
) -> dict[str, Any]:

    policy_spec = policy["spec"]

    secret_policy = policy_spec.get(
        "secretScanning",
        {},
    )

    excluded_generated_files = set(
        secret_policy.get(
            "excludedGeneratedFiles",
            [],
        )
    )

    entropy_exceptions = set(
        secret_policy.get(
            "entropyExceptions",
            [],
        )
    )

    allowed_placeholders = [
        value.lower()
        for value in secret_policy.get(
            "allowedPlaceholders",
            [],
        )
    ]

    allowed_environment_references = [
        value.lower()
        for value in secret_policy.get(
            "allowedEnvironmentReferences",
            [],
        )
    ]

    file_path = Path(
        finding["filename"]
    )

    relative_path = file_path.relative_to(
        quarantine_dir
    )

    filename = relative_path.name
    finding_type = finding["type"]
    line = finding.get(
        "line",
        "",
    )

    line_lower = line.lower()

    classification = "actionable"
    reason = None

    # Generated reports are not part of the upstream model.
    if filename in excluded_generated_files:
        classification = "ignored"
        reason = "generated pipeline artifact"

    # Tokenizers naturally contain many high-entropy strings.
    elif (
        filename in entropy_exceptions
        and finding_type in ENTROPY_TYPES
    ):
        classification = "ignored"
        reason = (
            "expected entropy in tokenizer/vocabulary artifact"
        )

    # Known harmless placeholder values.
    elif any(
        placeholder in line_lower
        for placeholder in allowed_placeholders
    ):
        classification = "ignored"
        reason = "allowed placeholder value"

    # Documentation referring to environment variables.
    elif any(
        reference in line_lower
        for reference in allowed_environment_references
    ):
        classification = "ignored"
        reason = "environment variable reference"

    return {
        **finding,
        "relative_file": str(
            relative_path
        ),
        "classification": classification,
        "classification_reason": reason,
    }


def scan_directory(
    quarantine_dir: Path,
    policy_path: Path,
) -> dict[str, Any]:

    if not quarantine_dir.is_dir():
        raise DetectSecretsScanError(
            f"Directory not found: {quarantine_dir}"
        )

    policy = load_yaml(
        policy_path
    )

    run_self_test()

    raw_findings = []
    scanned_files = 0

    for path in quarantine_dir.rglob("*"):

        if not path.is_file():
            continue

        if path.is_symlink():
            continue

        if (
            path.suffix.lower()
            not in TEXT_EXTENSIONS
        ):
            continue

        scanned_files += 1

        raw_findings.extend(
            scan_file(
                path
            )
        )

    classified_findings = [
        classify_finding(
            finding=finding,
            quarantine_dir=quarantine_dir,
            policy=policy,
        )
        for finding in raw_findings
    ]

    actionable = [
        finding
        for finding in classified_findings
        if finding["classification"] == "actionable"
    ]

    ignored = [
        finding
        for finding in classified_findings
        if finding["classification"] == "ignored"
    ]

    status = (
        "REVIEW"
        if actionable
        else "PASS"
    )

    return {
        "scanner": {
            "name": "detect-secrets",
            "type": "secret-detection",
        },

        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),

        "self_test": "PASS",

        "status": status,

        "scanned_files": scanned_files,

        "summary": {
            "raw_findings": len(
                raw_findings
            ),
            "actionable": len(
                actionable
            ),
            "ignored": len(
                ignored
            ),
        },

        "actionable_findings": actionable,

        "ignored_findings": ignored,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run detect-secrets against "
            "a quarantined AI model "
            "and classify findings using policy."
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
        result = scan_directory(
            quarantine_dir=args.quarantine_dir,
            policy_path=args.policy,
        )

    except (
        DetectSecretsScanError,
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

    output = args.output

    if output is None:
        output = (
            args.quarantine_dir
            / "detect-secrets-report.json"
        )

    with output.open(
        "w",
        encoding="utf-8",
    ) as stream:

        json.dump(
            result,
            stream,
            indent=2,
            ensure_ascii=False,
        )

        stream.write("\n")

    print(
        json.dumps(
            {
                "status": result["status"],
                "scanner": "detect-secrets",
                "self_test": result["self_test"],
                "scanned_files": result["scanned_files"],
                "raw_findings": result[
                    "summary"
                ]["raw_findings"],
                "actionable": result[
                    "summary"
                ]["actionable"],
                "ignored": result[
                    "summary"
                ]["ignored"],
                "report": str(output),
            },
            indent=2,
        )
    )

    if result["status"] == "REVIEW":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
