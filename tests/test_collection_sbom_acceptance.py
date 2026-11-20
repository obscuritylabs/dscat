# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Generated SBOM bindings and acceptance-hook ownership are explicit."""

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest
from scripts import candidate_collection as collection
from scripts.evidence_models import InstalledAcceptance
from scripts.processes import Execution, ToolExecutionError
from scripts.sbom_reconciliation import reconcile_sbom

from tests.test_collection_boundaries import context
from tests.test_dependency_graph import LOCK
from tests.test_sbom import payload

OBSERVATION = {
    "schema_version": "1.0",
    "state": "pass",
    "cli_cases": 9,
    "guard_probe_denied": True,
    "workflow_network_attempts": 0,
    "unknown_reference_denied": True,
    "template_sha256": "a" * 64,
    "canonical_generation": "b" * 64,
    "public_generation": "c" * 64,
}


def test_generated_sbom_binds_actual_source_and_archive_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The generated asset validates against pinned closure and the verified graph."""
    candidate = context(tmp_path)
    (candidate.project / "uv.lock").write_bytes(LOCK)
    raw, installed, graph, provenance = payload()

    def run(argv: list[str], **options: object) -> Execution:
        label = str(options["label"])
        assert argv[argv.index("--spec-version") + 1] == "1.6"
        assert "-E" in argv
        assert "-S" not in argv
        Path(argv[argv.index("--output-file") + 1]).write_bytes(raw)
        return Execution(label, 0, "a" * 64, "b" * 64, 0.1)

    monkeypatch.setattr(collection, "run_tool", run)
    observed = collection.collect_sbom(
        candidate, tmp_path / "python", installed, provenance
    )
    reconcile_sbom(
        observed,
        installed,
        graph,
        provenance.model_copy(
            update={"sbom_sha256": hashlib.sha256(observed).hexdigest()}
        ),
    )
    assert (candidate.assets / "sbom.cdx.json").read_bytes() == observed
    report = json.loads((candidate.assets / "sbom-reconciliation.json").read_bytes())
    assert report["generator_sha256"] == hashlib.sha256(raw).hexdigest()
    assert report["corrections"] == []
    assert str(tmp_path) not in observed.decode()


@pytest.mark.parametrize("outcome", ["pass", "failure", "unprotected"])
def test_acceptance_hook_cleanup_and_truthful_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    """Only this invocation's startup files are removed after success or failure."""
    candidate = context(tmp_path)
    runtime = candidate.work / "runtime"
    python = runtime / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    site = runtime / (
        "Lib/site-packages" if os.name == "nt" else f"lib/python{version}/site-packages"
    )
    site.mkdir(parents=True)
    existing = site / "sitecustomize.py"
    existing.write_text("# Synthetic existing host customization.\n")
    hook = site / "_dscat_acceptance_network_guard.py"
    startup = site / "_dscat_acceptance_network_guard.pth"

    def run(argv: list[str], **options: object) -> Execution:
        label = str(options["label"])
        assert "-I" in argv
        assert hook.is_file()
        assert startup.is_file()
        assert "sys.addaudithook" in hook.read_text()
        assert "import _dscat_acceptance_network_guard" in startup.read_text()
        environment = options["environment"]
        assert isinstance(environment, dict)
        assert environment["HOME"] != os.environ.get("HOME")
        if outcome == "failure":
            raise ToolExecutionError(label)
        observed = OBSERVATION | {"guard_probe_denied": outcome != "unprotected"}
        (candidate.work / "logs/installed-acceptance.stdout").write_text(
            json.dumps(observed)
        )
        return Execution(label, 0, "a" * 64, "b" * 64, 0.1)

    monkeypatch.setattr(collection, "run_tool", run)
    if outcome == "failure":
        with pytest.raises(ToolExecutionError):
            collection.installed_acceptance(candidate, python)
    elif outcome == "unprotected":
        with pytest.raises(ValueError, match="guard_probe_denied"):
            collection.installed_acceptance(candidate, python)
    else:
        collection.installed_acceptance(candidate, python)
        result = InstalledAcceptance.model_validate_json(
            (candidate.assets / "installed-acceptance.json").read_bytes()
        )
        assert result.guard_probe_denied
    assert not hook.exists()
    assert not startup.exists()
    assert existing.read_text() == "# Synthetic existing host customization.\n"
    if outcome != "pass":
        assert not (candidate.assets / "installed-acceptance.json").exists()
