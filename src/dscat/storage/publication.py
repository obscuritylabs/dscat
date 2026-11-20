# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Exclusive writers publish complete immutable generations at one commit point."""

import os
import re
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
    parse_manifest,
    prepare,
    prepare_exports,
    read_generation,
)
from dscat.storage.io import directory, flush_directory, read_file, write_file
from dscat.storage.models import ProjectionSnapshot, Snapshot
from dscat.storage.projections import (
    load_projection_snapshot,
    parse_projection_manifest,
    prepare_projection,
    read_projection_generation,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path

    from dscat.models.catalog import Catalog
    from dscat.models.configuration import ExportConfiguration
    from dscat.public_projection import PublicProjection
    from dscat.storage.targets import PreparedInternal


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


def stage_artifacts[Loaded: Snapshot | ProjectionSnapshot](
    root: Path,
    artifacts: dict[str, bytes],
    digest: str,
    *,
    reader: Callable[[Path, str], Loaded],
    folders: list[str],
) -> Loaded:
    """Flush and verify an owned stage before giving it an immutable final name."""
    if "manifest.json" not in artifacts or any(
        not re.fullmatch(
            r"manifest\.json|datasets/[0-9a-f]{64}\.json|exports/(dcat-us-3/catalog|odcs-3\.2/[0-9a-f]{64})\.json",
            path,
        )
        for path in artifacts
    ):
        raise fail(code="PUBLICATION_FAILURE")
    stage = root / f".stage-{uuid.uuid4().hex}"
    stage.mkdir(mode=0o700)
    directory(stage, root.stat().st_dev)
    ordered = sorted(folders, key=lambda folder: (folder.count("/"), folder))
    for folder in ordered:
        (stage / folder).mkdir(mode=0o700)
        directory(stage / folder, root.stat().st_dev)
    for relative, raw in sorted(artifacts.items()):
        write_file(stage / relative, raw)
    for folder in reversed(ordered):
        flush_directory(stage / folder)
    flush_directory(stage)
    snapshot = reader(stage, digest)
    destination = root / "generations" / digest
    reject_links(destination)
    if destination.exists():
        existing = reader(destination, digest)
        if existing != snapshot:
            raise fail(code="PUBLICATION_FAILURE")
        for relative in artifacts:
            (stage / relative).unlink()
        for folder in reversed(ordered):
            (stage / folder).rmdir()
        stage.rmdir()
    else:
        stage.rename(destination)
    flush_directory(root / "generations")
    return snapshot


def stage_generation(root: Path, artifacts: dict[str, bytes], digest: str) -> Snapshot:
    """Stage canonical data and only actual successful target directories."""
    manifest = parse_manifest(artifacts["manifest.json"])
    folders = ["datasets"]
    if bool(manifest.successful_targets):
        folders.extend(
            [
                "exports",
                *(f"exports/{target}" for target in manifest.successful_targets or []),
            ]
        )
    return stage_artifacts(
        root, artifacts, digest, reader=read_generation, folders=folders
    )


def stage_projection(
    root: Path, artifacts: dict[str, bytes], digest: str
) -> ProjectionSnapshot:
    """Stage only public target directories and a minimal projection manifest."""
    manifest = parse_projection_manifest(artifacts["manifest.json"])
    return stage_artifacts(
        root,
        artifacts,
        digest,
        reader=read_projection_generation,
        folders=["exports", *(f"exports/{target}" for target in manifest.targets)],
    )


def publish_prepared[Loaded: Snapshot | ProjectionSnapshot](
    root: Path,
    artifacts: dict[str, bytes],
    previous: bytes | None,
    stage: Callable[[Path, dict[str, bytes], str], Loaded],
) -> Loaded:
    """Use one CURRENT commit protocol for both typed bundle kinds."""
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
        snapshot = stage(root, artifacts, digest)
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


def publish(root: Path, catalog: Catalog, *, replace: bool = False) -> Snapshot:
    """Preserve the canonical-only adapter and its exact existing artifact bytes."""
    root = root.absolute()
    previous = check_root(root, replace=replace)
    _manifest, artifacts = prepare(catalog)
    return publish_prepared(root, artifacts, previous, stage_generation)


def publish_targets(
    root: Path,
    catalog: Catalog,
    configuration: ExportConfiguration,
    projection: PreparedInternal,
    *,
    replace: bool = False,
) -> Snapshot:
    """Publish canonical facts plus successful targets in one atomic generation."""
    root = root.absolute()
    previous = check_root(root, replace=replace)
    _manifest, artifacts = prepare_exports(catalog, configuration, projection)
    return publish_prepared(root, artifacts, previous, stage_generation)


def check_projection_root(root: Path, *, replace: bool) -> bytes | None:
    """Never convert retained private history into a public projection destination."""
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
    snapshot = load_projection_snapshot(root)
    if members(root, DEFAULT_LIMITS.datasets + 4) != {"CURRENT", "generations"}:
        raise fail(code="PUBLICATION_FAILURE")
    for name in members(root / "generations", DEFAULT_LIMITS.datasets + 1):
        read_projection_generation(root / "generations" / name, name)
    return (snapshot.generation + "\n").encode("ascii")


def publish_projection(
    root: Path, projection: PublicProjection, *, replace: bool = False
) -> ProjectionSnapshot:
    """Withhold a public transaction until only approved complete bytes remain."""
    root = root.absolute()
    previous = check_projection_root(root, replace=replace)
    _manifest, artifacts = prepare_projection(projection)
    return publish_prepared(root, artifacts, previous, stage_projection)
