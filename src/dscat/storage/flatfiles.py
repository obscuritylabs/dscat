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
from dscat.publication_bindings import mapping_version, value_hash
from dscat.resources.registry import MANIFEST_SHA256
from dscat.serialization import canonical_bytes
from dscat.storage.io import directory, read_file
from dscat.storage.models import (
    CanonicalManifest,
    DatasetEntry,
    ProjectionSnapshot,
    Snapshot,
    dataset_path,
)
from dscat.storage.target_codecs import validate_internal
from dscat.storage.targets import PreparedInternal

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from dscat.models.configuration import ExportConfiguration

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
                schema_version=catalog.schema_version,
            )
        )
    manifest = CanonicalManifest(
        schema_version=catalog.schema_version, kind="canonical", datasets=entries
    )
    artifacts["manifest.json"] = canonical_bytes(manifest)
    check_json(artifacts["manifest.json"], MAX_REQUEST_BYTES)
    if sum(map(len, artifacts.values())) > DEFAULT_LIMITS.snapshot:
        raise fail(code="INPUT_LIMIT", limit="snapshot")
    return manifest, artifacts


def prepare_exports(
    catalog: Catalog, configuration: ExportConfiguration, projection: PreparedInternal
) -> tuple[CanonicalManifest, dict[str, bytes]]:
    """Bind complete ready target bytes and input fingerprints before any writes."""
    projection = PreparedInternal.model_validate(
        projection.model_dump(exclude_none=True)
    )
    manifest, artifacts = prepare(catalog)
    if not projection.requested:
        return manifest, artifacts
    fingerprint = value_hash(configuration.model_dump(mode="json", exclude_none=True))
    manifest = CanonicalManifest.model_validate(
        manifest.model_dump(exclude_none=True)
        | {
            "requested_targets": projection.requested,
            "successful_targets": [
                item.target for item in projection.readiness if item.state == "ready"
            ],
            "exports": [artifact.entry for artifact in projection.artifacts],
            "resource_fingerprints": dict.fromkeys(
                projection.requested, MANIFEST_SHA256
            ),
            "configuration_fingerprints": dict.fromkeys(
                projection.requested, fingerprint
            ),
            "mapping_versions": {
                target: mapping_version(target) for target in projection.requested
            },
        }
    )
    for artifact in projection.artifacts:
        validate_internal(artifact.content, artifact.entry, catalog)
        artifacts[artifact.entry.path] = artifact.content
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
    if entry.schema_version == "1.0" and (
        record.description is None
        or record.core_party is None
        or record.collection_intake is not None
    ):
        raise fail(code="PUBLICATION_FAILURE")
    if (
        entry.schema_version != "1.2"
        and record.collection_intake is not None
        and record.collection_intake.retention is not None
        and record.collection_intake.retention.authorized_by is not None
    ):
        raise fail(code="PUBLICATION_FAILURE")
    if (
        record.id != entry.id
        or hashlib.sha256(raw).hexdigest() != entry.sha256
        or canonical_bytes(record) != raw
    ):
        raise fail(code="PUBLICATION_FAILURE")
    return record


def read_exports(
    path: Path,
    manifest: CanonicalManifest,
    catalog: Catalog,
    artifacts: dict[str, bytes],
    device: int,
) -> int:
    """Require exact target directories, bytes, schema and dataset associations."""
    size = sum(map(len, artifacts.values()))
    successful = manifest.successful_targets or []
    if not successful:
        return size
    directory(path / "exports", device)
    if members(path / "exports", 3) != set(successful):
        raise fail(code="PUBLICATION_FAILURE")
    entries = manifest.exports or []
    for target in successful:
        target_directory = path / "exports" / target
        directory(target_directory, device)
        selected = [entry for entry in entries if entry.target == target]
        expected = {entry.path.rsplit("/", 1)[-1] for entry in selected}
        if members(target_directory, DEFAULT_LIMITS.datasets + 2) != expected:
            raise fail(code="PUBLICATION_FAILURE")
        for entry in selected:
            attributes = (path / entry.path).lstat()
            if attributes.st_dev != device:
                raise fail(code="PUBLICATION_FAILURE")
            if size + attributes.st_size > DEFAULT_LIMITS.snapshot:
                raise fail(code="INPUT_LIMIT", limit="snapshot")
            raw = read_file(path / entry.path, MAX_REQUEST_BYTES)
            size += len(raw)
            if size > DEFAULT_LIMITS.snapshot:
                raise fail(code="INPUT_LIMIT", limit="snapshot")
            validate_internal(raw, entry, catalog)
            artifacts[entry.path] = raw
    return size


def check_generation_members(path: Path, manifest: CanonicalManifest) -> None:
    """Require exact generation roots and supported projection dependency versions."""
    expected_members = {"manifest.json", "datasets"}
    if bool(manifest.successful_targets):
        expected_members.add("exports")
    if members(path, 4) != expected_members:
        raise fail(code="PUBLICATION_FAILURE")
    if manifest.requested_targets is not None and (
        any(
            value != MANIFEST_SHA256
            for value in manifest.resource_fingerprints.values()
        )
        or manifest.mapping_versions
        != {target: mapping_version(target) for target in manifest.requested_targets}
    ):
        raise fail(code="UNSUPPORTED_VERSION")


def read_generation(path: Path, expected: str) -> Snapshot:
    """Validate exact members, hashes, encoding, identities and target resources."""
    directory(path)
    device = path.stat().st_dev
    raw = read_file(path / "manifest.json", MAX_REQUEST_BYTES)
    manifest = parse_manifest(raw)
    check_generation_members(path, manifest)
    directory(path / "datasets", device)
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
    try:
        catalog = Catalog(schema_version=manifest.schema_version, datasets=records)
    except ValidationError:
        raise fail(code="PUBLICATION_FAILURE") from None
    read_exports(path, manifest, catalog, artifacts, device)
    if generation_hash(artifacts) != expected:
        raise fail(code="PUBLICATION_FAILURE")
    return Snapshot(generation=expected, catalog=catalog, manifest=manifest)


def load_current[Loaded: Snapshot | ProjectionSnapshot](
    root: Path, reader: Callable[[Path, str], Loaded]
) -> Loaded:
    """Read CURRENT once; ignore other generations and report orphan stages."""
    directory(root)
    pointer = read_file(root / "CURRENT", 65)
    if not re.fullmatch(rb"[0-9a-f]{64}\n", pointer):
        raise fail(code="PUBLICATION_FAILURE")
    generation = pointer[:-1].decode("ascii")
    directory(root / "generations", root.stat().st_dev)
    directory(root / "generations" / generation, root.stat().st_dev)
    snapshot = reader(root / "generations" / generation, generation)
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


def load_snapshot(root: Path) -> Snapshot:
    """Load canonical facts and optional validated targets from one CURRENT value."""
    return load_current(root, read_generation)


def save_snapshot(root: Path, catalog: Catalog, *, replace: bool = False) -> Snapshot:
    """Persist validated facts through the transactional publication adapter."""
    # Local import keeps the reader independent of the writer's transaction machinery.
    from dscat.storage.publication import publish  # noqa: PLC0415 -- adapter dependency.

    try:
        return publish(root, catalog, replace=replace)
    except ValidationError, ValueError:
        raise fail(code="PUBLICATION_FAILURE") from None
