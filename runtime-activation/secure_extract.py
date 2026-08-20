#!/usr/bin/env python3

from __future__ import annotations

import os
import shutil
import stat
import sys
import tarfile
from pathlib import Path, PurePosixPath


MAX_MEMBERS = 200_000


class UnsafeArchiveError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise UnsafeArchiveError(message)


def validate_name(name: str) -> tuple[str, ...]:
    if not name:
        fail("archive contains an empty path")

    if "\x00" in name:
        fail("archive path contains NUL")

    if name.startswith("/"):
        fail(f"absolute archive path rejected: {name!r}")

    # Reject Windows-style absolute paths as well.
    if len(name) >= 2 and name[0].isalpha() and name[1] == ":":
        fail(f"drive-qualified archive path rejected: {name!r}")

    posix = PurePosixPath(name)

    if posix.is_absolute():
        fail(f"absolute archive path rejected: {name!r}")

    raw_parts = name.split("/")

    if any(part == ".." for part in raw_parts):
        fail(f"path traversal rejected: {name!r}")

    parts = tuple(
        part
        for part in raw_parts
        if part not in {"", "."}
    )

    if not parts:
        fail(f"invalid archive path rejected: {name!r}")

    return parts


def ensure_directory(
    root: Path,
    relative_parts: tuple[str, ...],
) -> Path:
    current = root

    for part in relative_parts:
        current = current / part

        try:
            info = os.lstat(current)
        except FileNotFoundError:
            os.mkdir(current, 0o750)
            continue

        if not stat.S_ISDIR(info.st_mode):
            fail(
                f"non-directory path component rejected: {current}"
            )

    return current


def secure_extract(
    stream,
    destination: Path,
) -> None:
    destination.mkdir(
        parents=True,
        exist_ok=True,
        mode=0o750,
    )

    root = destination.resolve()

    root_info = os.lstat(root)

    if not stat.S_ISDIR(root_info.st_mode):
        fail("destination is not a directory")

    member_count = 0

    with tarfile.open(
        fileobj=stream,
        mode="r|*",
    ) as archive:

        for member in archive:
            member_count += 1

            if member_count > MAX_MEMBERS:
                fail(
                    "archive contains too many members"
                )

            parts = validate_name(member.name)

            target = root.joinpath(*parts)

            # Defense in depth in addition to explicit '..'
            # and absolute-path rejection.
            try:
                common = os.path.commonpath(
                    (
                        str(root),
                        str(target.resolve(strict=False)),
                    )
                )
            except ValueError as exc:
                raise UnsafeArchiveError(
                    f"invalid archive path: {member.name!r}"
                ) from exc

            if common != str(root):
                fail(
                    f"archive path escapes destination: "
                    f"{member.name!r}"
                )

            # Model packages only need normal directories and
            # regular files.
            #
            # Explicitly reject:
            # - symbolic links
            # - hard links
            # - devices
            # - FIFOs
            # - sockets / special entries
            if member.isdir():
                ensure_directory(
                    root,
                    parts,
                )
                continue

            if not member.isfile():
                fail(
                    "non-regular archive member rejected: "
                    f"{member.name!r}"
                )

            if member.size < 0:
                fail(
                    f"negative file size rejected: "
                    f"{member.name!r}"
                )

            parent = ensure_directory(
                root,
                parts[:-1],
            )

            target = parent / parts[-1]

            flags = (
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
            )

            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW

            try:
                fd = os.open(
                    target,
                    flags,
                    0o640,
                )
            except OSError as exc:
                raise UnsafeArchiveError(
                    f"could not create archive member "
                    f"{member.name!r}: {exc}"
                ) from exc

            source = archive.extractfile(member)

            if source is None:
                os.close(fd)
                try:
                    target.unlink()
                except FileNotFoundError:
                    pass

                fail(
                    f"could not read archive member: "
                    f"{member.name!r}"
                )

            try:
                with os.fdopen(
                    fd,
                    "wb",
                    closefd=True,
                ) as output:
                    shutil.copyfileobj(
                        source,
                        output,
                        length=1024 * 1024,
                    )
            except Exception:
                try:
                    target.unlink()
                except FileNotFoundError:
                    pass
                raise

    if member_count == 0:
        fail("model archive is empty")


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "usage: secure_extract.py DESTINATION",
            file=sys.stderr,
        )
        return 64

    destination = Path(sys.argv[1])

    try:
        secure_extract(
            sys.stdin.buffer,
            destination,
        )
    except (
        UnsafeArchiveError,
        tarfile.TarError,
        OSError,
    ) as exc:
        print(
            f"SECURE EXTRACTION FAILED: {exc}",
            file=sys.stderr,
        )
        return 1

    print(
        "SECURE MODEL EXTRACTION PASSED",
        file=sys.stderr,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
