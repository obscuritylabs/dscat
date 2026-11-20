# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Atomic target bundles, partial internal behavior and minimal public persistence."""

import errno
import hashlib
import json
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from dscat.intake.limits import IntakeError
from dscat.models.catalog import Catalog
from dscat.models.configuration import ExportConfiguration
from dscat.public_projection import project_public
from dscat.serialization import canonical_bytes
from dscat.storage import publication
from dscat.storage.flatfiles import load_snapshot, prepare
from dscat.storage.models import (
    CanonicalManifest,
    ExportEntry,
    ProjectionManifest,
    export_path,
)
from dscat.storage.projections import load_projection_snapshot, prepare_projection
from dscat.storage.targets import InternalArtifact, PublicArtifact, prepare_targets
from tests.test_dcat_us_3 import catalog, configuration
from tests.test_publication_bindings import approved_fixture

if TYPE_CHECKING:
    from pathlib import Path

TARGET_COUNT = 2


@pytest.mark.parametrize("detailed", [False, True])
def test_internal_both_targets_roundtrip_and_identical_replace(
    tmp_path: Path, *, detailed: bool
) -> None:
    """All canonical and successful target bytes belong to one verified generation."""
    source = catalog(detailed=detailed)
    configured = configuration()
    projection = prepare_targets(source, configured, ["odcs-3.2", "dcat-us-3"])
    root = tmp_path / "bundle"
    first = publication.publish_targets(root, source, configured, projection)
    loaded = load_snapshot(root)
    assert loaded.catalog == source
    assert loaded.generation == first.generation
    assert loaded.manifest.requested_targets == ["dcat-us-3", "odcs-3.2"]
    assert loaded.manifest.successful_targets == ["dcat-us-3", "odcs-3.2"]
    assert loaded.manifest.exports is not None
    assert len(loaded.manifest.exports) == TARGET_COUNT
    before = {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file()
    }
    with pytest.raises(IntakeError):
        publication.publish_targets(root, source, configured, projection)
    assert before == {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file()
    }
    repeated = publication.publish_targets(
        root, source, configured, projection, replace=True
    )
    assert repeated.generation == first.generation
    assert repeated.retained_generation_count == 0
    assert before == {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file()
    }


def test_partial_internal_omits_failed_target_and_retains_history(
    tmp_path: Path,
) -> None:
    """Persist canonical facts without stale files for blocked targets."""
    source = catalog()
    configured = configuration()
    root = tmp_path / "bundle"
    first = publication.publish_targets(
        root,
        source,
        configured,
        prepare_targets(source, configured, ["dcat-us-3", "odcs-3.2"]),
    )
    previous = {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in (root / "generations").rglob("*")
        if p.is_file()
    }
    values = configured.model_dump(exclude_none=True)
    values["odcs_3_2"] = {}
    configured = ExportConfiguration.model_validate(values)
    projection = prepare_targets(source, configured, ["dcat-us-3", "odcs-3.2"])
    assert [item.state for item in projection.readiness] == ["ready", "blocked"]
    second = publication.publish_targets(
        root, source, configured, projection, replace=True
    )
    assert second.catalog == source
    assert second.generation != first.generation
    assert second.manifest.successful_targets == ["dcat-us-3"]
    current = root / "generations" / second.generation
    assert {p.name for p in (current / "exports").iterdir()} == {"dcat-us-3"}
    assert all((root / name).read_bytes() == raw for name, raw in previous.items())
    blocked = ExportConfiguration(schema_version="1.0")
    third = publication.publish_targets(
        root,
        source,
        blocked,
        prepare_targets(source, blocked, ["dcat-us-3", "odcs-3.2"]),
        replace=True,
    )
    assert third.manifest.successful_targets == []
    assert not (root / "generations" / third.generation / "exports").exists()
    assert load_snapshot(root).catalog == source


def test_canonical_only_bytes_keep_original_manifest_shape() -> None:
    """Optional target metadata does not change existing canonical-only generations."""
    manifest, artifacts = prepare(catalog())
    assert set(json.loads(artifacts["manifest.json"])) == {
        "schema_version",
        "kind",
        "datasets",
        "resource_fingerprints",
        "configuration_fingerprints",
    }
    assert manifest.exports is None
    assert manifest.requested_targets is None
    assert manifest.resource_fingerprints == {}


def test_public_bundle_contains_only_minimal_public_artifacts(tmp_path: Path) -> None:
    """Keep private data and reports outside public generations."""
    record, configured = approved_fixture(detailed=True)
    source = Catalog(schema_version="1.0", datasets=[record])
    projection = project_public(source, configured, ["dcat-us-3", "odcs-3.2"])
    root = tmp_path / "public"
    first = publication.publish_projection(root, projection)
    loaded = load_projection_snapshot(root)
    assert loaded.generation == first.generation
    generation = root / "generations" / first.generation
    assert {p.name for p in generation.iterdir()} == {"manifest.json", "exports"}
    raw = (generation / "manifest.json").read_bytes()
    manifest = json.loads(raw)
    assert set(manifest) == {"schema_version", "kind", "targets", "artifacts"}
    assert all(set(entry) == {"path", "sha256"} for entry in manifest["artifacts"])
    combined = b"".join(p.read_bytes() for p in generation.rglob("*") if p.is_file())
    assert b"configuration_fingerprints" not in combined
    assert b"approved_value_sha256" not in combined
    assert b"Synthetic publication authority" not in combined
    assert b'"losses"' not in combined
    assert b'"datasets"' not in combined
    assert b'"records"' not in combined
    odcs_entry = next(
        entry for entry in loaded.manifest.artifacts if "odcs-3.2" in entry.path
    )
    assert odcs_entry.path == export_path("odcs-3.2", record.contract_id)
    before = (root / "CURRENT").read_bytes()
    with pytest.raises(IntakeError):
        publication.publish_projection(root, projection)
    assert (root / "CURRENT").read_bytes() == before
    assert (
        publication.publish_projection(root, projection, replace=True).generation
        == first.generation
    )
    one = project_public(source, configured, ["dcat-us-3"])
    second = publication.publish_projection(root, one, replace=True)
    assert second.generation != first.generation
    assert second.retained_generation_count == 1
    assert (
        root / "generations" / first.generation / "manifest.json"
    ).read_bytes() == raw


def test_publication_never_converts_canonical_history_to_public(tmp_path: Path) -> None:
    """Explicit replacement cannot expose retained private canonical generations."""
    record, configured = approved_fixture()
    source = Catalog(schema_version="1.0", datasets=[record])
    root = tmp_path / "bundle"
    publication.publish(root, source)
    before = {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file()
    }
    with pytest.raises(IntakeError):
        publication.publish_projection(
            root, project_public(source, configured, ["dcat-us-3"]), replace=True
        )
    assert before == {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file()
    }


@pytest.mark.parametrize("unexpected", ["file", "orphan", "canonical_history"])
def test_public_replacement_refuses_private_or_unverified_retained_content(
    tmp_path: Path, unexpected: str
) -> None:
    """Public destination reuse cannot silently retain foreign/private artifacts."""
    record, configured = approved_fixture()
    source = Catalog(schema_version="1.0", datasets=[record])
    root = tmp_path / "public"
    projection = project_public(source, configured, ["dcat-us-3"])
    publication.publish_projection(root, projection)
    if unexpected == "file":
        (root / "private.json").write_bytes(b"synthetic-sensitive")
    elif unexpected == "orphan":
        (root / ".stage-synthetic").mkdir()
        (root / ".stage-synthetic" / "private.json").write_bytes(b"synthetic-sensitive")
    else:
        private = tmp_path / "private"
        snapshot = publication.publish(private, source)
        (private / "generations" / snapshot.generation).rename(
            root / "generations" / snapshot.generation
        )
    before = (root / "CURRENT").read_bytes()
    assert load_projection_snapshot(root).generation == before[:-1].decode()
    with pytest.raises(IntakeError):
        publication.publish_projection(root, projection, replace=True)
    assert (root / "CURRENT").read_bytes() == before


def test_target_write_failure_preserves_previous_current(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even a failure during target serialization/write cannot publish a partial set."""
    source = catalog()
    configured = configuration()
    root = tmp_path / "bundle"
    publication.publish(root, source)
    before = (root / "CURRENT").read_bytes()
    original = publication.write_file

    def refused(path: Path, raw: bytes) -> None:
        if "exports" in path.parts:
            raise OSError(errno.ENOSPC, "synthetic write refusal")
        original(path, raw)

    monkeypatch.setattr(publication, "write_file", refused)
    with pytest.raises(OSError, match="synthetic write refusal"):
        publication.publish_targets(
            root,
            source,
            configured,
            prepare_targets(source, configured, ["dcat-us-3", "odcs-3.2"]),
            replace=True,
        )
    assert (root / "CURRENT").read_bytes() == before
    assert load_snapshot(root).catalog == source
    monkeypatch.undo()
    corrected = publication.publish_targets(
        root,
        source,
        configured,
        prepare_targets(source, configured, ["dcat-us-3", "odcs-3.2"]),
        replace=True,
    )
    assert corrected.orphan_count > 0
    assert load_snapshot(root).manifest.successful_targets == ["dcat-us-3", "odcs-3.2"]


def test_target_artifact_models_reject_mismatched_or_escaping_content() -> None:
    """Check artifact identities and prescribed relative paths before writes."""
    raw = b"{}\n"
    digest = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValidationError):
        ExportEntry(
            target="dcat-us-3",
            dataset_id="item",
            path=export_path("dcat-us-3"),
            sha256=digest,
        )
    with pytest.raises(ValidationError):
        ExportEntry(
            target="odcs-3.2", dataset_id="item", path="../private", sha256=digest
        )
    entry = ExportEntry(
        target="dcat-us-3", path=export_path("dcat-us-3"), sha256=digest
    )
    with pytest.raises(ValidationError):
        InternalArtifact(entry=entry, content=b"changed")
    with pytest.raises(ValidationError):
        PublicArtifact.model_validate(
            {
                "entry": {"path": export_path("dcat-us-3"), "sha256": digest},
                "content": b"changed",
            }
        )
    with pytest.raises(ValidationError):
        ProjectionManifest.model_validate(
            {
                "schema_version": "1.0",
                "kind": "projection",
                "targets": ["dcat-us-3"],
                "artifacts": [],
            }
        )
    with pytest.raises(ValidationError):
        CanonicalManifest.model_validate(
            {
                "schema_version": "1.0",
                "kind": "canonical",
                "datasets": [],
                "requested_targets": ["dcat-us-3"],
            }
        )


def test_public_manifest_bytes_depend_only_on_public_documents() -> None:
    """Keep public generation identity independent of excluded private values."""
    record, configured = approved_fixture(detailed=True)
    source = Catalog(schema_version="1.0", datasets=[record])
    first = project_public(source, configured, ["dcat-us-3", "odcs-3.2"])
    manifest, artifacts = prepare_projection(first)
    assert canonical_bytes(manifest) == artifacts["manifest.json"]
    values = record.model_dump(exclude_none=True)
    values["records"]["authority"] = "synthetic-sensitive-changed"
    changed = Catalog(
        schema_version="1.0", datasets=[type(record).model_validate(values)]
    )
    assert prepare_projection(
        project_public(changed, configured, ["dcat-us-3", "odcs-3.2"])
    ) == (manifest, artifacts)
