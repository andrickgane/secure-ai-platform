from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


class GitleaksScanError(Exception):
    pass


def find_gitleaks() -> str:
    executable = shutil.which("gitleaks")

    if executable is None:
        raise GitleaksScanError(
            "gitleaks was not found in PATH"
        )

    return executable


def scan_directory(
    quarantine_dir: Path,
) -> dict:

    if not quarantine_dir.is_dir():
        raise GitleaksScanError(
            f"Directory not found: {quarantine_dir}"
        )

    gitleaks = find_gitleaks()

    with tempfile.TemporaryDirectory() as tmpdir:
        report_path = (
            Path(tmpdir)
            / "gitleaks-report.json"
        )

        command = [
            gitleaks,
            "detect",
            "--no-git",
            "--source",
            str(quarantine_dir),
            "--redact",
            "--report-format",
            "json",
            "--report-path",
            str(report_path),
        ]

        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

        # Gitleaks:
        # 0 = no leaks
        # 1 = leaks found
        # >1 = execution error

        if process.returncode not in (0, 1):
            raise GitleaksScanError(
                "Gitleaks execution failed: "
                f"{process.stderr.strip() or process.stdout.strip()}"
            )

        findings = []

        if report_path.is_file():
            with report_path.open(
                "r",
                encoding="utf-8",
            ) as stream:
                data = json.load(stream)

            if isinstance(data, list):
                for item in data:
                    findings.append(
                        {
                            "rule_id": item.get(
                                "RuleID"
                            ),
                            "description": item.get(
                                "Description"
                            ),
                            "file": item.get(
                                "File"
                            ),
                            "start_line": item.get(
                                "StartLine"
                            ),
                            "end_line": item.get(
                                "EndLine"
                            ),
                        }
                    )

    status = (
        "REVIEW"
        if findings
        else "PASS"
    )

    return {
        "scanner": {
            "name": "gitleaks",
            "type": "secret-detection",
        },
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": status,
        "findings": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run Gitleaks against a "
            "quarantined AI model."
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
        result = scan_directory(
            args.quarantine_dir
        )

    except GitleaksScanError as exc:
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
            / "gitleaks-report.json"
        )

    with output.open(
        "w",
        encoding="utf-8",
    ) as stream:
        json.dump(
            result,
            stream,
            indent=2,
        )
        stream.write("\n")

    print(
        json.dumps(
            {
                "status": result["status"],
                "scanner": "gitleaks",
                "findings": len(
                    result["findings"]
                ),
                "report": str(output),
            },
            indent=2,
        )
    )

    if result["status"] == "REVIEW":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
