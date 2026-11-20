# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Stored target documents and dependency manifests fail closed after corruption."""

import json
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from dscat.intake.limits import IntakeError
from dscat.models.catalog import Catalog
from dscat.public_projection import project_public
from dscat.storage import flatfiles, projections, publication, target_codecs
from dscat.storage.models import (
    CanonicalManifest,
    ExportEntry,
    ProjectionEntry,
    ProjectionManifest,
    export_path,
)
from dscat.storage.targets import PreparedInternal, prepare_targets
from tests.test_dcat_us_3 import catalog, configuration
from tests.test_publication_bindings import approved_fixture

if TYPE_CHECKING:
    from pathlib import Path


def public_artifacts() -> tuple[ProjectionManifest, dict[str, bytes]]:
    """Provide both fully approved public target documents."""
    record, configured = approved_fixture()
    return projections.prepare_projection(
        project_public(
            Catalog(schema_version="1.0", datasets=[record]),
            configured,
            ["dcat-us-3", "odcs-3.2"],
        )
    )


@pytest.mark.parametrize("mutation", ["invalid", "encoding", "hash", "association"])
def test_internal_document_corruption(mutation: str) -> None:
    """Reject invalid schemas, alternate bytes, wrong hashes and swapped records."""
    prepared = prepare_targets(catalog(), configuration(), ["dcat-us-3", "odcs-3.2"])
    for artifact in prepared.artifacts:
        raw, entry = artifact.content, artifact.entry
        source = catalog()
        if mutation == "invalid":
            raw = b'{"unsupported":"synthetic-private"}\n'
        elif mutation == "encoding":
            raw = json.dumps(json.loads(raw), separators=(",", ":")).encode()
        elif mutation == "hash":
            entry = entry.model_copy(update={"sha256": "0" * 64})
        else:
            values = source.model_dump(exclude_none=True)
            values["datasets"][0]["id"] = "another-record"
            source = Catalog.model_validate(values)
            if entry.target == "odcs-3.2":
                entry = ExportEntry(
                    target="odcs-3.2",
                    dataset_id="another-record",
                    path=export_path("odcs-3.2", "another-record"),
                    sha256=entry.sha256,
                )
        with pytest.raises(IntakeError, match="PUBLICATION_FAILURE"):
            target_codecs.validate_internal(raw, entry, source)


@pytest.mark.parametrize("mutation", ["invalid", "encoding", "hash", "association"])
def test_public_document_corruption(mutation: str) -> None:
    """Reject private children, alternate bytes, wrong hashes and filename aliases."""
    manifest, artifacts = public_artifacts()
    for original in manifest.artifacts:
        raw, entry = artifacts[original.path], original
        if mutation == "invalid":
            raw = b'{"unsupported":"synthetic-private"}\n'
        elif mutation == "encoding":
            raw = json.dumps(json.loads(raw), separators=(",", ":")).encode()
        elif mutation == "hash":
            entry = entry.model_copy(update={"sha256": "0" * 64})
        else:
            if "odcs" not in entry.path:
                continue
            entry = ProjectionEntry(
                path=export_path("odcs-3.2", "another-contract"), sha256=entry.sha256
            )
        with pytest.raises(IntakeError, match="PUBLICATION_FAILURE"):
            target_codecs.validate_public(raw, entry)


@pytest.mark.parametrize("mutation", ["version", "extra", "encoding"])
def test_public_manifest_contract(mutation: str) -> None:
    """Reject unsupported manifest versions, private children and alternate encoding."""
    manifest, _ = public_artifacts()
    values = manifest.model_dump()
    if mutation == "version":
        values["schema_version"] = "2.0"
    elif mutation == "extra":
        values["private_report"] = "synthetic-private"
    raw = json.dumps(values).encode()
    with pytest.raises(
        IntakeError,
        match="UNSUPPORTED_VERSION" if mutation == "version" else "PUBLICATION_FAILURE",
    ):
        projections.parse_projection_manifest(raw)


@pytest.mark.parametrize("kind", ["public", "internal"])
@pytest.mark.parametrize("location", ["root", "exports", "target", "digest"])
def test_generation_member_corruption(tmp_path: Path, kind: str, location: str) -> None:
    """Reject extra files at each boundary and a changed aggregate digest."""
    root = tmp_path / "bundle"
    if kind == "public":
        record, configured = approved_fixture()
        snapshot = publication.publish_projection(
            root,
            project_public(
                Catalog(schema_version="1.0", datasets=[record]),
                configured,
                ["dcat-us-3"],
            ),
        )
    else:
        snapshot = publication.publish_targets(
            root,
            catalog(),
            configuration(),
            prepare_targets(catalog(), configuration(), ["dcat-us-3"]),
        )
    path = root / "generations" / snapshot.generation
    if location != "digest":
        folder = {
            "root": path,
            "exports": path / "exports",
            "target": path / "exports/dcat-us-3",
        }[location]
        (folder / "unexpected").write_bytes(b"synthetic")
    reader = (
        projections.read_projection_generation
        if kind == "public"
        else flatfiles.read_generation
    )
    with pytest.raises(IntakeError, match="PUBLICATION_FAILURE"):
        reader(path, "0" * 64 if location == "digest" else snapshot.generation)


@pytest.mark.parametrize("dependency", ["resource_fingerprints", "mapping_versions"])
def test_internal_dependency_versions_are_verified(
    tmp_path: Path, dependency: str
) -> None:
    """Refuse unsupported resolver and mapping versions."""
    source, configured = catalog(), configuration()
    snapshot = publication.publish_targets(
        tmp_path / "bundle",
        source,
        configured,
        prepare_targets(source, configured, ["dcat-us-3"]),
    )
    path = tmp_path / "bundle/generations" / snapshot.generation
    values = snapshot.manifest.model_dump(exclude_none=True)
    values[dependency]["dcat-us-3"] = "0" * 64
    (path / "manifest.json").write_bytes(
        flatfiles.canonical_bytes(CanonicalManifest.model_validate(values))
    )
    with pytest.raises(IntakeError, match="UNSUPPORTED_VERSION"):
        flatfiles.read_generation(path, snapshot.generation)


@pytest.mark.parametrize(
    "mutation",
    [
        "empty",
        "duplicate",
        "blocked_file",
        "missing_file",
        "missing_dataset",
        "extra_canonical",
    ],
)
def test_internal_manifest_selection_contract(mutation: str) -> None:
    """Require complete artifacts and dependencies for every successful target."""
    source, configured = catalog(), configuration()
    prepared = prepare_targets(source, configured, ["dcat-us-3", "odcs-3.2"])
    manifest, _ = flatfiles.prepare_exports(source, configured, prepared)
    values = manifest.model_dump(exclude_none=True)
    if mutation == "empty":
        values["requested_targets"] = []
    elif mutation == "duplicate":
        values["exports"] *= 2
    elif mutation == "blocked_file":
        values["successful_targets"] = []
    elif mutation == "missing_file":
        values["exports"] = [
            item for item in values["exports"] if item["target"] != "dcat-us-3"
        ]
    elif mutation == "missing_dataset":
        values["exports"] = [
            item for item in values["exports"] if item["target"] != "odcs-3.2"
        ]
    else:
        values.pop("requested_targets")
    with pytest.raises(ValidationError):
        CanonicalManifest.model_validate(values)


def test_public_and_prepared_selection_duplicates() -> None:
    """Duplicate targets/artifacts and blocked artifacts are refused before staging."""
    manifest, _ = public_artifacts()
    values = manifest.model_dump()
    values["targets"] *= 2
    with pytest.raises(ValidationError):
        ProjectionManifest.model_validate(values)
    prepared = prepare_targets(catalog(), configuration(), ["dcat-us-3"])
    for changed in (
        {"requested": []},
        {"artifacts": prepared.artifacts * 2},
        {"readiness": [prepared.readiness[0].model_copy(update={"state": "blocked"})]},
    ):
        with pytest.raises(ValidationError):
            PreparedInternal.model_validate(
                prepared.model_dump(exclude_none=True) | changed
            )
