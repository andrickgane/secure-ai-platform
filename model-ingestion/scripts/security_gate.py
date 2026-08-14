from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SecurityGateError(Exception):
    pass


REQUIRED_REPORTS = {
    "static": "security-attestation.json",
    "clamav": "clamav-report.json",
    "yara": "yara-report.json",
    "detect_secrets": "detect-secrets-report.json",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SecurityGateError(
            f"Required report not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as stream:
        data = json.load(stream)

    if not isinstance(data, dict):
        raise SecurityGateError(
            f"Invalid JSON object: {path}"
        )

    return data


def extract_status(
    scanner_name: str,
    report: dict[str, Any],
) -> str:

    if scanner_name == "static":
        try:
            return report["scan"]["status"]
        except KeyError as exc:
            raise SecurityGateError(
                "Static security report has no scan.status"
            ) from exc

    status = report.get("status")

    if not isinstance(status, str):
        raise SecurityGateError(
            f"{scanner_name} report has no valid status"
        )

    return status


def evaluate_gate(
    quarantine_dir: Path,
) -> dict[str, Any]:

    reports: dict[str, dict[str, Any]] = {}

    for scanner_name, filename in REQUIRED_REPORTS.items():
        path = quarantine_dir / filename

        reports[scanner_name] = load_json(
            path
        )

    results = []

    for scanner_name, report in reports.items():

        status = extract_status(
            scanner_name,
            report,
        ).upper()

        if status not in {
            "PASS",
            "REVIEW",
            "DENY",
            "ERROR",
        }:
            raise SecurityGateError(
                f"Unsupported status '{status}' "
                f"from scanner '{scanner_name}'"
            )

        results.append(
            {
                "scanner": scanner_name,
                "status": status,
            }
        )

    statuses = {
        item["status"]
        for item in results
    }

    # Fail closed.
    if "ERROR" in statuses:
        final_status = "ERROR"

    elif "DENY" in statuses:
        final_status = "DENY"

    elif "REVIEW" in statuses:
        final_status = "REVIEW"

    else:
        final_status = "PASS"

    static_report = reports[
        "static"
    ]

    model = static_report.get(
        "model"
    )

    source = static_report.get(
        "source",
        {},
    )

    return {
        "schemaVersion": 1,

        "model": model,

        "source": source,

        "gate": {
            "status": final_status,

            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),

            "policy": (
                "default-model-security"
            ),
        },

        "checks": results,

        "promotionAllowed": (
            final_status == "PASS"
        ),
    }


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Aggregate AI model security reports "
            "and decide whether promotion is allowed."
        )
    )

    parser.add_argument(
        "--quarantine-dir",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--output",
        type=Path,
    )

    args = parser.parse_args()

    try:
        result = evaluate_gate(
            args.quarantine_dir
        )

    except (
        SecurityGateError,
        json.JSONDecodeError,
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
            / "security-gate.json"
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
                "status": result[
                    "gate"
                ]["status"],

                "promotionAllowed": result[
                    "promotionAllowed"
                ],

                "checks": result[
                    "checks"
                ],

                "report": str(
                    output
                ),
            },
            indent=2,
        )
    )

    final_status = result[
        "gate"
    ]["status"]

    if final_status == "ERROR":
        raise SystemExit(2)

    if final_status == "DENY":
        raise SystemExit(10)

    if final_status == "REVIEW":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
