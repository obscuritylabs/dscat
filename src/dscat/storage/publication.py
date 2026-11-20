# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Exclusive writers publish complete immutable generations at one commit point."""

import os
import uuid
from contextlib import contextmanager
from typing import TYPE_CHECKING

from dscat.intake.discovery import file_identity, reject_links
from dscat.intake.limits import DEFAULT_LIMITS, fail
from dscat.storage.filesystems import require_local
from dscat.storage.flatfiles import (
    generation_hash,
    load_snapshot,
    members,
    prepare,
    read_generation,
)
from dscat.storage.io import directory, flush_directory, read_file, write_file

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from dscat.models.catalog import Catalog
    from dscat.storage.models import Snapshot


@contextmanager
def writer_lock(root: Path) -> Generator[None]:
    """Never steal another writer's lock, even when its process may have ended."""
    lock = root / ".writer.lock"
    reject_links(lock)
    descriptor = os.open(
        lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600
    )
    try:
        identity = file_identity(os.fstat(descriptor))
    finally:
        os.close(descriptor)
    try:
        yield
    finally:
        reject_links(lock)
        if file_identity(lock.lstat()) != identity:
            raise fail(code="PUBLICATION_FAILURE")
        lock.unlink()


def check_root(root: Path, *, replace: bool) -> bytes | None:
    """Refuse existing destinations without authorization before any writes."""
    reject_links(root)
    directory(root.parent)
    require_local(root.parent)
    if not root.exists():
        return None
    directory(root, root.parent.stat().st_dev)
    require_local(root)
    if (root / ".writer.lock").exists():
        raise fail(code="PUBLICATION_LOCKED")
    if not replace:
        raise fail(code="PUBLICATION_FAILURE")
    snapshot = load_snapshot(root)
    return (snapshot.generation + "\n").encode("ascii")


def stage_generation(root: Path, artifacts: dict[str, bytes], digest: str) -> Snapshot:
    """Write, flush and independently reload a generation before naming it final."""
    stage = root / f".stage-{uuid.uuid4().hex}"
    stage.mkdir(mode=0o700)
    directory(stage, root.stat().st_dev)
    (stage / "datasets").mkdir(mode=0o700)
    for relative, raw in sorted(artifacts.items()):
        write_file(stage / relative, raw)
    flush_directory(stage / "datasets")
    flush_directory(stage)
    snapshot = read_generation(stage, digest)
    destination = root / "generations" / digest
    if destination.exists():
        existing = read_generation(destination, digest)
        if existing != snapshot:
            raise fail(code="PUBLICATION_FAILURE")
        # Remove only the fully verified private stage created by this invocation.
        for relative in artifacts:
            (stage / relative).unlink()
        (stage / "datasets").rmdir()
        stage.rmdir()
    else:
        stage.rename(destination)
    flush_directory(root / "generations")
    return snapshot


def publish(root: Path, catalog: Catalog, *, replace: bool = False) -> Snapshot:
    """Switch CURRENT only after serialized, flushed and revalidated local bytes."""
    root = root.absolute()
    previous = check_root(root, replace=replace)
    _manifest, artifacts = prepare(catalog)
    digest = generation_hash(artifacts)
    if previous is None:
        root.mkdir(mode=0o700)
    directory(root, root.parent.stat().st_dev)
    root_identity = root.stat().st_dev, root.stat().st_ino
    with writer_lock(root):
        if previous is None:
            (root / "generations").mkdir(mode=0o700)
        elif read_file(root / "CURRENT", 65) != previous:
            raise fail(code="PUBLICATION_FAILURE")
        directory(root / "generations", root.stat().st_dev)
        snapshot = stage_generation(root, artifacts, digest)
        snapshot = snapshot.model_copy(
            update={
                "orphan_count": sum(
                    name.startswith((".stage-", ".pointer-"))
                    for name in members(root, DEFAULT_LIMITS.datasets + 4)
                ),
                "retained_generation_count": len(
                    members(root / "generations", DEFAULT_LIMITS.datasets + 1)
                    - {digest}
                ),
            }
        )
        pointer = root / f".pointer-{uuid.uuid4().hex}"
        write_file(pointer, (digest + "\n").encode("ascii"))
        flush_directory(root)
        reject_links(root / "CURRENT")
        if (root.stat().st_dev, root.stat().st_ino) != root_identity:
            raise fail(code="PUBLICATION_FAILURE")
        if previous is not None and read_file(root / "CURRENT", 65) != previous:
            raise fail(code="PUBLICATION_FAILURE")
        pointer.replace(root / "CURRENT")
    return snapshot
