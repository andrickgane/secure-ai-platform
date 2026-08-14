from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


class YaraScanError(Exception):
    pass


def find_yara() -> str:
    executable = shutil.which("yara")

    if executable is None:
        raise YaraScanError(
            "yara was not found in PATH"
        )

    return executable


def scan_directory(
    quarantine_dir: Path,
    rules_file: Path,
) -> dict:

    if not quarantine_dir.is_dir():
        raise YaraScanError(
            f"Directory not found: {quarantine_dir}"
        )

    if not rules_file.is_file():
        raise YaraScanError(
            f"YARA rules not found: {rules_file}"
        )

    yara = find_yara()

    command = [
        yara,
        "-r",
        str(rules_file),
        str(quarantine_dir),
    ]

    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    # YARA:
    # 0 = scan completed
    # non-zero = execution/error condition
    if process.returncode != 0:
        raise YaraScanError(
            "YARA execution failed: "
            f"{process.stderr.strip() or process.stdout.strip()}"
        )

    matches = []

    for line in process.stdout.splitlines():
        line = line.strip()

        if not line:
            continue

        parts = line.split(maxsplit=1)

        if len(parts) == 2:
            rule, target = parts
        else:
            rule = parts[0]
            target = ""

        matches.append(
            {
                "rule": rule,
                "target": target,
            }
        )

    status = (
        "DENY"
        if matches
        else "PASS"
    )

    return {
        "scanner": {
            "name": "yara",
            "type": "pattern-matching",
        },
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": status,
        "matches": matches,
        "rules": str(rules_file),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run YARA rules against a "
            "quarantined AI model."
        )
    )

    parser.add_argument(
        "--quarantine-dir",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--rules",
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
            rules_file=args.rules,
        )

    except YaraScanError as exc:
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
            / "yara-report.json"
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
                "scanner": "yara",
                "matches": len(
                    result["matches"]
                ),
                "report": str(output),
            },
            indent=2,
        )
    )

    if result["status"] == "DENY":
        raise SystemExit(10)


if __name__ == "__main__":
    main()
