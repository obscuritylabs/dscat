# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Strict bounded canonical generation loading without original workbooks."""

import hashlib
import os
import re
from typing import TYPE_CHECKING

from pydantic import ValidationError

from dscat.intake.limits import DEFAULT_LIMITS, MAX_REQUEST_BYTES, fail
from dscat.json_guard import check_json
from dscat.models.catalog import Catalog, DatasetRecord
from dscat.serialization import canonical_bytes
from dscat.storage.io import directory, read_file
from dscat.storage.models import CanonicalManifest, DatasetEntry, Snapshot, dataset_path

if TYPE_CHECKING:
    from pathlib import Path

GENERATION = re.compile(r"[0-9a-f]{64}")


def generation_hash(artifacts: dict[str, bytes]) -> str:
    """Bind every relative artifact name and byte, excluding its parent digest."""
    digest = hashlib.sha256()
    for name, raw in sorted(artifacts.items()):
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(raw)
        digest.update(b"\0")
    return digest.hexdigest()


def prepare(catalog: Catalog) -> tuple[CanonicalManifest, dict[str, bytes]]:
    """Revalidate mutable collections, then serialize every artifact before writes."""
    catalog = Catalog.model_validate_json(catalog.model_dump_json(exclude_none=True))
    entries: list[DatasetEntry] = []
    artifacts: dict[str, bytes] = {}
    for record in catalog.datasets:
        raw = canonical_bytes(record)
        check_json(raw, MAX_REQUEST_BYTES)
        path = dataset_path(record.id)
        artifacts[path] = raw
        entries.append(
            DatasetEntry(
                id=record.id,
                path=path,
                sha256=hashlib.sha256(raw).hexdigest(),
                schema_version="1.0",
            )
        )
    manifest = CanonicalManifest(
        schema_version="1.0", kind="canonical", datasets=entries
    )
    artifacts["manifest.json"] = canonical_bytes(manifest)
    check_json(artifacts["manifest.json"], MAX_REQUEST_BYTES)
    if sum(map(len, artifacts.values())) > DEFAULT_LIMITS.snapshot:
        raise fail(code="INPUT_LIMIT", limit="snapshot")
    return manifest, artifacts


def members(path: Path, maximum: int) -> set[str]:
    """Enumerate only immediate entries, bounded before retaining hostile names."""
    result: set[str] = set()
    with os.scandir(path) as entries:
        for entry in entries:
            if len(result) >= maximum:
                raise fail(code="INPUT_LIMIT", limit="datasets")
            result.add(entry.name)
    return result


def parse_manifest(raw: bytes) -> CanonicalManifest:
    """Check JSON syntax, duplicates and version before the closed manifest DTO."""
    check_json(raw, MAX_REQUEST_BYTES)
    try:
        manifest = CanonicalManifest.model_validate_json(raw)
    except ValidationError as error:
        if any(
            item["loc"][-1:] == ("schema_version",) and item["type"] == "literal_error"
            for item in error.errors(include_input=False)
        ):
            raise fail(code="UNSUPPORTED_VERSION") from None
        raise fail(code="PUBLICATION_FAILURE") from None
    if canonical_bytes(manifest) != raw:
        raise fail(code="PUBLICATION_FAILURE")
    return manifest


def parse_record(raw: bytes, entry: DatasetEntry) -> DatasetRecord:
    """Require the declared identity/hash and canonical record encoding."""
    check_json(raw, MAX_REQUEST_BYTES)
    try:
        record = DatasetRecord.model_validate_json(raw)
    except ValidationError:
        raise fail(code="PUBLICATION_FAILURE") from None
    if (
        record.id != entry.id
        or hashlib.sha256(raw).hexdigest() != entry.sha256
        or canonical_bytes(record) != raw
    ):
        raise fail(code="PUBLICATION_FAILURE")
    return record


def read_generation(path: Path, expected: str) -> Snapshot:
    """Validate exact members, hashes, encoding, identities and catalog relations."""
    directory(path)
    device = path.stat().st_dev
    if members(path, 3) != {"manifest.json", "datasets"}:
        raise fail(code="PUBLICATION_FAILURE")
    directory(path / "datasets", device)
    raw = read_file(path / "manifest.json", MAX_REQUEST_BYTES)
    manifest = parse_manifest(raw)
    names = members(path / "datasets", DEFAULT_LIMITS.datasets + 1)
    if names != {entry.path.removeprefix("datasets/") for entry in manifest.datasets}:
        raise fail(code="PUBLICATION_FAILURE")
    artifacts = {"manifest.json": raw}
    records: list[DatasetRecord] = []
    size = len(raw)
    for entry in manifest.datasets:
        attributes = (path / entry.path).lstat()
        if attributes.st_dev != device:
            raise fail(code="PUBLICATION_FAILURE")
        if size + attributes.st_size > DEFAULT_LIMITS.snapshot:
            raise fail(code="INPUT_LIMIT", limit="snapshot")
        raw = read_file(path / entry.path, MAX_REQUEST_BYTES)
        size += len(raw)
        if size > DEFAULT_LIMITS.snapshot:
            raise fail(code="INPUT_LIMIT", limit="snapshot")
        record = parse_record(raw, entry)
        artifacts[entry.path] = raw
        records.append(record)
    if generation_hash(artifacts) != expected:
        raise fail(code="PUBLICATION_FAILURE")
    try:
        catalog = Catalog(schema_version="1.0", datasets=records)
    except ValidationError:
        raise fail(code="PUBLICATION_FAILURE") from None
    return Snapshot(generation=expected, catalog=catalog, manifest=manifest)


def load_snapshot(root: Path) -> Snapshot:
    """Read CURRENT once; ignore other generations and report orphan stages."""
    directory(root)
    pointer = read_file(root / "CURRENT", 65)
    if not re.fullmatch(rb"[0-9a-f]{64}\n", pointer):
        raise fail(code="PUBLICATION_FAILURE")
    generation = pointer[:-1].decode("ascii")
    directory(root / "generations", root.stat().st_dev)
    directory(root / "generations" / generation, root.stat().st_dev)
    snapshot = read_generation(root / "generations" / generation, generation)
    # Previous immutable generations are retained history, not cleanup candidates.
    orphan_count = 0
    for name in members(root, DEFAULT_LIMITS.datasets + 4):
        if name.startswith((".stage-", ".pointer-")):
            orphan_count += 1
    retained = members(root / "generations", DEFAULT_LIMITS.datasets + 1) - {generation}
    for name in retained:
        if not GENERATION.fullmatch(name):
            raise fail(code="PUBLICATION_FAILURE")
    snapshot = snapshot.model_copy(update={"retained_generation_count": len(retained)})
    return snapshot.model_copy(update={"orphan_count": orphan_count})


def save_snapshot(root: Path, catalog: Catalog, *, replace: bool = False) -> Snapshot:
    """Persist validated facts through the transactional publication adapter."""
    # Local import keeps the reader independent of the writer's transaction machinery.
    from dscat.storage.publication import publish  # noqa: PLC0415 -- adapter dependency.

    try:
        return publish(root, catalog, replace=replace)
    except ValidationError, ValueError:
        raise fail(code="PUBLICATION_FAILURE") from None
