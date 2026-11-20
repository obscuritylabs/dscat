# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Minimal public bundles contain only closed approved target bytes and manifests."""

from typing import TYPE_CHECKING

from pydantic import ValidationError

from dscat.intake.limits import DEFAULT_LIMITS, MAX_REQUEST_BYTES, fail
from dscat.json_guard import check_json
from dscat.public_projection import PublicProjection
from dscat.serialization import canonical_bytes
from dscat.storage.flatfiles import generation_hash, load_current, members
from dscat.storage.io import directory, read_file
from dscat.storage.models import ProjectionManifest, ProjectionSnapshot
from dscat.storage.target_codecs import validate_public
from dscat.storage.targets import prepare_public_targets

if TYPE_CHECKING:
    from pathlib import Path


def prepare_projection(
    projection: PublicProjection,
) -> tuple[ProjectionManifest, dict[str, bytes]]:
    """Exclude all canonical/configuration/report values before any filesystem write."""
    projection = PublicProjection.model_validate(
        projection.model_dump(mode="json", by_alias=True, exclude_none=True)
    )
    prepared = prepare_public_targets(projection)
    manifest = ProjectionManifest(
        schema_version="1.0",
        kind="projection",
        targets=sorted(item.target for item in projection.readiness),
        artifacts=[item.entry for item in prepared],
    )
    artifacts = {"manifest.json": canonical_bytes(manifest)}
    for item in prepared:
        validate_public(item.content, item.entry)
        artifacts[item.entry.path] = item.content
    check_json(artifacts["manifest.json"], MAX_REQUEST_BYTES)
    if sum(map(len, artifacts.values())) > DEFAULT_LIMITS.snapshot:
        raise fail(code="INPUT_LIMIT", limit="snapshot")
    return manifest, artifacts


def parse_projection_manifest(raw: bytes) -> ProjectionManifest:
    """Enforce the minimal public shape, exact encoding and independent version."""
    check_json(raw, MAX_REQUEST_BYTES)
    try:
        manifest = ProjectionManifest.model_validate_json(raw)
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


def read_projection_generation(path: Path, expected: str) -> ProjectionSnapshot:
    """Reject canonical data, private fields, aliases, extra files and invalid bytes."""
    directory(path)
    device = path.stat().st_dev
    raw = read_file(path / "manifest.json", MAX_REQUEST_BYTES)
    manifest = parse_projection_manifest(raw)
    if members(path, 3) != {"manifest.json", "exports"}:
        raise fail(code="PUBLICATION_FAILURE")
    directory(path / "exports", device)
    if members(path / "exports", 3) != set(manifest.targets):
        raise fail(code="PUBLICATION_FAILURE")
    artifacts = {"manifest.json": raw}
    size = len(raw)
    for target in manifest.targets:
        target_path = path / "exports" / target
        directory(target_path, device)
        entries = [
            entry for entry in manifest.artifacts if entry.path.split("/")[1] == target
        ]
        if members(target_path, DEFAULT_LIMITS.datasets + 2) != {
            entry.path.rsplit("/", 1)[-1] for entry in entries
        }:
            raise fail(code="PUBLICATION_FAILURE")
        for entry in entries:
            attributes = (path / entry.path).lstat()
            if attributes.st_dev != device:
                raise fail(code="PUBLICATION_FAILURE")
            if size + attributes.st_size > DEFAULT_LIMITS.snapshot:
                raise fail(code="INPUT_LIMIT", limit="snapshot")
            raw = read_file(path / entry.path, MAX_REQUEST_BYTES)
            size += len(raw)
            if size > DEFAULT_LIMITS.snapshot:
                raise fail(code="INPUT_LIMIT", limit="snapshot")
            validate_public(raw, entry)
            artifacts[entry.path] = raw
    if generation_hash(artifacts) != expected:
        raise fail(code="PUBLICATION_FAILURE")
    return ProjectionSnapshot(generation=expected, manifest=manifest)


def load_projection_snapshot(root: Path) -> ProjectionSnapshot:
    """Read CURRENT once without loading or returning any canonical facts."""
    return load_current(root, read_projection_generation)
