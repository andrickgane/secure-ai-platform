from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


class ClamAVScanError(Exception):
    pass


def find_clamscan() -> str:
    executable = shutil.which("clamscan")

    if executable is None:
        raise ClamAVScanError(
            "clamscan was not found in PATH"
        )

    return executable


def scan_directory(
    quarantine_dir: Path,
) -> dict:

    if not quarantine_dir.is_dir():
        raise ClamAVScanError(
            f"Directory not found: {quarantine_dir}"
        )

    clamscan = find_clamscan()

    command = [
        clamscan,
        "--recursive=yes",
        "--infected",
        "--no-summary",
        str(quarantine_dir),
    ]

    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    # ClamAV:
    # 0 = clean
    # 1 = malware found
    # >1 = scanner error

    if process.returncode == 0:
        status = "PASS"

    elif process.returncode == 1:
        status = "DENY"

    else:
        raise ClamAVScanError(
            "ClamAV execution failed: "
            f"{process.stderr.strip() or process.stdout.strip()}"
        )

    detections = []

    if process.returncode == 1:
        for line in process.stdout.splitlines():
            line = line.strip()

            if not line:
                continue

            if line.endswith(" FOUND"):
                detections.append(line)

    return {
        "scanner": {
            "name": "clamav",
            "type": "antimalware",
        },
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": status,
        "detections": detections,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run ClamAV against a quarantined "
            "AI model."
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

    except ClamAVScanError as exc:
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
            / "clamav-report.json"
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
                "scanner": "clamav",
                "detections": len(
                    result["detections"]
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
