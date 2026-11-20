# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Bounded regular-file I/O and explicit local durability operations."""

import os
import stat
from typing import TYPE_CHECKING

from dscat.intake.discovery import file_identity, reject_links
from dscat.intake.limits import CHUNK_BYTES, fail

if TYPE_CHECKING:
    from pathlib import Path


def directory(path: Path, device: int | None = None) -> None:
    """Require an existing unlinked directory on the selected device."""
    reject_links(path)
    observed = path.lstat()
    if not stat.S_ISDIR(observed.st_mode) or (
        device is not None and observed.st_dev != device
    ):
        raise fail(code="PUBLICATION_FAILURE")


def read_file(path: Path, maximum: int) -> bytes:
    """Verify physical identity and bounds both before and after a streamed read."""
    reject_links(path)
    before = file_identity(path.lstat())
    if before.size > maximum:
        raise fail(code="INPUT_LIMIT", limit="json_bytes")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        if file_identity(os.fstat(stream.fileno())) != before:
            raise fail(code="UNSAFE_INPUT")
        result = bytearray()
        while chunk := stream.read(min(CHUNK_BYTES, maximum + 1 - len(result))):
            result.extend(chunk)
            if len(result) > maximum:
                raise fail(code="INPUT_LIMIT", limit="json_bytes")
        if (
            file_identity(os.fstat(stream.fileno())) != before
            or file_identity(path.lstat()) != before
        ):
            raise fail(code="UNSAFE_INPUT")
    return bytes(result)


def write_file(path: Path, raw: bytes) -> None:
    """Create once, reject short writes and flush before any visibility switch."""
    reject_links(path)
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        if stream.write(raw) != len(raw):
            raise fail(code="PUBLICATION_FAILURE")
        stream.flush()
        os.fsync(stream.fileno())


def flush_directory(path: Path) -> None:
    """Flush POSIX directory entries; Windows atomic replace uses closed handles."""
    directory(path)
    if os.name == "nt":
        # Windows has no portable directory fsync. File FlushFileBuffers is provided
        # by os.fsync; the promised guarantee is process failure, not power loss.
        return
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
