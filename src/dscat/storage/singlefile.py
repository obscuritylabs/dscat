# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Explicit single-file publication with complete staging before visibility."""

import os
import stat
import uuid
from typing import TYPE_CHECKING

from dscat.intake.discovery import reject_links
from dscat.intake.limits import fail
from dscat.storage.io import directory, flush_directory, write_file

if TYPE_CHECKING:
    from pathlib import Path


def check_disjoint(paths: list[Path]) -> None:
    """Reject linked ancestors and any equal or nested selected path pair."""
    resolved = []
    for path in paths:
        reject_links(path)
        selected = path.resolve(strict=False)
        if any(
            selected.is_relative_to(previous) or previous.is_relative_to(selected)
            for previous in resolved
        ):
            raise fail(code="UNSAFE_INPUT")
        resolved.append(selected)


def check_file_destination(path: Path, *, replace: bool) -> None:
    """Reject links, nonregular destinations and unauthorized replacement."""
    reject_links(path)
    directory(path.parent)
    try:
        observed = path.lstat()
    except FileNotFoundError:
        return
    if not replace or not stat.S_ISREG(observed.st_mode):
        raise fail(code="PUBLICATION_FAILURE")


def publish_file(path: Path, content: bytes, *, replace: bool = False) -> None:
    """Publish exact serialized bytes with an exclusive or authorized atomic switch."""
    path = path.absolute()
    check_file_destination(path, replace=replace)
    stage = path.parent / f".stage-{uuid.uuid4().hex}"
    try:
        write_file(stage, content)
        flush_directory(path.parent)
        check_file_destination(path, replace=replace)
        if replace:
            stage.replace(path)
        else:
            # Unlike rename, link cannot overwrite a concurrently created output.
            os.link(stage, path, follow_symlinks=False)
    finally:
        stage.unlink(missing_ok=True)
