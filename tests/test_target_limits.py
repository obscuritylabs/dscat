# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Target preparation and reload enforce size/device boundaries before acceptance."""

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from dscat.intake.limits import IntakeError
from dscat.models.catalog import Catalog
from dscat.public_projection import project_public
from dscat.storage import flatfiles, projections, publication, targets
from dscat.storage.models import export_path
from dscat.storage.targets import prepare_targets
from tests.test_dcat_us_3 import catalog, configuration
from tests.test_publication_bindings import approved_fixture

if TYPE_CHECKING:
    from dscat.models.base import Target


@pytest.mark.parametrize("kind", ["public", "internal"])
def test_export_preparation_snapshot_budget(
    kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Serialized targets count toward the same snapshot ceiling as canonical facts."""
    if kind == "internal":
        source = catalog()
        _, canonical = flatfiles.prepare(source)
        ceiling = sum(map(len, canonical.values())) + 1
        monkeypatch.setattr(
            flatfiles,
            "DEFAULT_LIMITS",
            flatfiles.DEFAULT_LIMITS.model_copy(update={"snapshot": ceiling}),
        )
        prepared = prepare_targets(source, configuration(), ["dcat-us-3"])
        with pytest.raises(IntakeError, match="INPUT_LIMIT"):
            flatfiles.prepare_exports(source, configuration(), prepared)
    else:
        record, configured = approved_fixture()
        public = project_public(
            Catalog(schema_version="1.0", datasets=[record]), configured, ["dcat-us-3"]
        )
        monkeypatch.setattr(
            projections,
            "DEFAULT_LIMITS",
            projections.DEFAULT_LIMITS.model_copy(update={"snapshot": 1}),
        )
        with pytest.raises(IntakeError, match="INPUT_LIMIT"):
            projections.prepare_projection(public)


@pytest.mark.parametrize("kind", ["public", "internal"])
@pytest.mark.parametrize("failure", ["size", "growth", "device"])
def test_target_reload_size_growth_and_device(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, failure: str
) -> None:
    """A changed mount or file growing between stat and read cannot escape limits."""
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
        module = projections
        reader = projections.read_projection_generation
    else:
        source, configured = catalog(), configuration()
        snapshot = publication.publish_targets(
            root, source, configured, prepare_targets(source, configured, ["dcat-us-3"])
        )
        module = flatfiles
        reader = flatfiles.read_generation
    path = root / "generations" / snapshot.generation
    target = path / "exports/dcat-us-3/catalog.json"
    size = sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
    if failure == "device":
        original_stat = Path.lstat

        def other_device(selected: Path) -> os.stat_result:
            observed = original_stat(selected)
            if selected == target:
                changed = list(observed)
                changed[2] += 1
                return os.stat_result(changed)
            return observed

        monkeypatch.setattr(Path, "lstat", other_device)
    else:
        monkeypatch.setattr(
            module,
            "DEFAULT_LIMITS",
            module.DEFAULT_LIMITS.model_copy(
                update={"snapshot": size - 1 if failure == "size" else size}
            ),
        )
        if failure == "growth":
            original_read = module.read_file

            def growing_read(selected: Path, maximum: int) -> bytes:
                if selected == target:
                    selected.write_bytes(selected.read_bytes() + b" ")
                return original_read(selected, maximum)

            monkeypatch.setattr(module, "read_file", growing_read)
    with pytest.raises(
        IntakeError,
        match="PUBLICATION_FAILURE" if failure == "device" else "INPUT_LIMIT",
    ):
        reader(path, snapshot.generation)


def test_duplicate_target_and_missing_identity_refusal() -> None:
    """Refuse duplicate target requests and absent ODCS identities."""
    with pytest.raises(IntakeError, match="INVALID_INVOCATION"):
        prepare_targets(catalog(), configuration(), ["dcat-us-3", "dcat-us-3"])
    with pytest.raises(ValueError, match="requires its dataset identity"):
        export_path("odcs-3.2")


@pytest.mark.parametrize("target", ["dcat-us-3", "odcs-3.2"])
def test_inconsistent_exporter_reply_prevents_publication(
    monkeypatch: pytest.MonkeyPatch, target: Target
) -> None:
    """A faulty exporter claiming readiness without complete documents must fail."""
    source, configured = catalog(), configuration()
    if target == "dcat-us-3":
        projected = targets.project_dcat(source, configured).model_copy(
            update={"document": None}
        )
        monkeypatch.setattr(targets, "project_dcat", lambda *_: projected)
    else:
        odcs = targets.project_odcs(source, configured).model_copy(
            update={"documents": []}
        )
        monkeypatch.setattr(targets, "project_odcs", lambda *_: odcs)
    with pytest.raises(IntakeError, match="INTERNAL_FAILURE"):
        prepare_targets(source, configured, [target])


def test_loss_report_budget_and_blocked_public_preparation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refuse excessive omissions and blocked public target preparation."""
    monkeypatch.setattr(
        targets,
        "DEFAULT_LIMITS",
        targets.DEFAULT_LIMITS.model_copy(update={"diagnostics": 1}),
    )
    with pytest.raises(IntakeError, match="INPUT_LIMIT"):
        prepare_targets(catalog(detailed=True), configuration(), ["dcat-us-3"])
    public = project_public(catalog(), configuration(), ["dcat-us-3"])
    with pytest.raises(IntakeError, match="PUBLIC_PROJECTION_DENIED"):
        targets.prepare_public_targets(public)


def test_public_odcs_only_and_duplicate_contract_path() -> None:
    """Keep ODCS-only output separate and refuse duplicate contract paths."""
    record, configured = approved_fixture()
    public = project_public(
        Catalog(schema_version="1.0", datasets=[record]), configured, ["odcs-3.2"]
    )
    artifacts = targets.prepare_public_targets(public)
    assert len(artifacts) == 1
    assert artifacts[0].entry.path.startswith("exports/odcs-3.2/")
    duplicate = public.model_copy(update={"odcs": public.odcs * 2})
    with pytest.raises(IntakeError, match="PUBLICATION_FAILURE"):
        targets.prepare_public_targets(duplicate)


def test_public_lock_and_unsafe_stage_paths(tmp_path: Path) -> None:
    """A public writer respects existing locks and refuses arbitrary stage paths."""
    root = tmp_path / "bundle"
    record, configured = approved_fixture()
    public = project_public(
        Catalog(schema_version="1.0", datasets=[record]), configured, ["dcat-us-3"]
    )
    publication.publish_projection(root, public)
    (root / ".writer.lock").write_bytes(b"synthetic abandoned lock")
    with pytest.raises(IntakeError, match="PUBLICATION_LOCKED"):
        publication.publish_projection(root, public, replace=True)
    with pytest.raises(IntakeError, match="PUBLICATION_FAILURE"):
        publication.stage_artifacts(
            root,
            {"../escape": b"data"},
            "a" * 64,
            reader=flatfiles.read_generation,
            folders=[],
        )
    assert not (tmp_path / "escape").exists()
