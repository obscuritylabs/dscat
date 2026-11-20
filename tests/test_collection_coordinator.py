# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Candidate coordination binds observations and refuses source identity changes."""

import json
from typing import TYPE_CHECKING

import pytest
from scripts import candidate_collection as collection
from scripts.sbom_reconciliation import enrich_sbom

from tests.test_collection_boundaries import PROJECT
from tests.test_dependency_graph import LOCK, inventory
from tests.test_release_evidence import candidate
from tests.test_sbom import payload

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("source_changed", [True, False])
def test_candidate_collection_binds_observations_without_inventing_acceptance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, source_changed: bool
) -> None:
    """Coordinated evidence stays pending and cannot certify a changed source tree."""
    project = tmp_path / "source"
    project.mkdir()
    output = tmp_path / "candidate"
    existing, _ = candidate()
    raw, runtime, _, _ = payload()
    source = {"uv.lock": LOCK, "pyproject.toml": PROJECT}
    monkeypatch.setattr(
        collection,
        "check_tools",
        lambda *_args: {"cyclonedx-bom": "7.6.0", "pip-audit": "2.10.1"},
    )

    def state(context: collection.Collection, phase: str) -> collection.SourceState:
        del context
        return collection.SourceState(
            commit="c" * 40 if source_changed and phase == "after" else "a" * 40,
            tree="f" * 40,
            dirty=False,
            verified_main=False,
        )

    monkeypatch.setattr(collection, "source_state", state)
    monkeypatch.setattr(collection, "source_snapshot", lambda *_args: source)
    development = inventory(development=True).model_dump(exclude_none=True)
    monkeypatch.setattr(collection, "observe", lambda: development)
    monkeypatch.setattr(
        collection, "build_artifacts", lambda *_args: (existing.wheel, existing.sdist)
    )
    monkeypatch.setattr(
        collection,
        "export_requirements",
        lambda *_args: {"runtime": tmp_path / "requirements"},
    )
    monkeypatch.setattr(
        collection, "install_runtime", lambda *_args: (tmp_path / "python", runtime)
    )
    monkeypatch.setattr(collection, "installed_acceptance", lambda *_args: None)

    def sbom(
        context: collection.Collection,
        python: Path,
        installed: collection.Inventory,
        provenance: collection.ArtifactProvenance,
    ) -> bytes:
        del context, python
        document = collection.validate_sbom(raw)
        return json.dumps(enrich_sbom(document, installed, provenance)).encode()

    monkeypatch.setattr(collection, "collect_sbom", sbom)
    monkeypatch.setattr(
        collection,
        "collect_advisories",
        lambda *_args: (existing.feeds, [], set()),
    )
    claims = collection.Claims(schema_version="1.0")
    if source_changed:
        with pytest.raises(ValueError, match="Source identity changed"):
            collection.collect_candidate(project, output, "uv", claims)
        assert not (output / "assets/release-evidence.json").exists()
    else:
        observed = collection.collect_candidate(project, output, "uv", claims)
        recorded = collection.ReleaseEvidence.model_validate_json(
            (output / "assets/release-evidence.json").read_bytes()
        )
        assert recorded == observed.evidence
        assert recorded.source_sha == observed.actual.source_sha == "a" * 40
        assert recorded.source_dirty is False
        assert all(gate.state == "pending" for gate in recorded.gates)
        assert not observed.actual.verified_main
        assert (output / "assets/application-requirements.txt").read_text() == (
            f"./{existing.wheel.name} --hash=sha256:{existing.wheel.sha256}\n"
        )
        assert recorded.findings == []
