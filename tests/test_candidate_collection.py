# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Candidate workspace ownership, private arguments and pending gates."""

import json
import os
import sys
from typing import TYPE_CHECKING

import pytest
from scripts import candidate_collection as collection

from tests.test_release_evidence import candidate

if TYPE_CHECKING:
    from pathlib import Path


def test_new_local_workspace_refuses_existing_and_source_overlap(
    tmp_path: Path,
) -> None:
    """Never adopt an existing evidence directory or write private files into source."""
    project = tmp_path / "source"
    project.mkdir()
    output = tmp_path / "evidence"
    created = collection.initialize(project, output, "uv")
    assert created.work.is_dir()
    assert created.assets.is_dir()
    assert created.executions == []
    with pytest.raises(FileExistsError):
        collection.initialize(project, output, "uv")
    for unsafe in [
        project / "inside",
        project.parent,
        tmp_path / "other/../source/inside",
    ]:
        with pytest.raises(ValueError, match="separate"):
            collection.initialize(project, unsafe, "uv")
    assert not (project / "inside").exists()


def test_command_records_keep_flags_but_remove_private_paths(tmp_path: Path) -> None:
    """Version evidence never contains actual interpreter, source or scratch paths."""
    context = collection.Collection(
        project=tmp_path / "source",
        output=tmp_path / "evidence",
        uv=str(tmp_path / "private-uv"),
    )
    arguments = [
        sys.executable,
        context.uv,
        str(context.project / "scripts/check.py"),
        str(context.output / "private/input"),
        str(tmp_path / "unrelated-private-file"),
        "file:///synthetic-private-file",
        "--format",
        "json",
    ]
    public = context.public_arguments(arguments)
    assert public == [
        "python",
        "uv",
        "{source}/scripts/check.py",
        "{candidate}/private/input",
        "{external-file}",
        "{local-file-uri}",
        "--format",
        "json",
    ]
    assert str(tmp_path) not in json.dumps(public)
    assert "synthetic-private" not in json.dumps(public)


def test_environment_removes_implicit_tool_and_python_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parent overrides cannot change scanner modes or dependency sources."""
    for name in [
        "PIP_AUDIT_FORMAT",
        "PIP_AUDIT_VULNERABILITY_SERVICE",
        "UV_PROJECT",
        "UV_SEED",
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONSTARTUP",
        "PYTHONUSERBASE",
    ]:
        monkeypatch.setenv(name, "synthetic-override")
    environment = collection.tool_environment()
    assert not any(
        environment.get(name) == "synthetic-override"
        for name in os.environ
        if name.startswith(("UV_", "PIP_AUDIT_", "PYTHON"))
    )
    assert environment["PIP_DISABLE_PIP_VERSION_CHECK"] == "1"


def test_missing_claims_remain_unassigned_pending_and_duplicates_refuse() -> None:
    """Absent human/independent observations never inherit an automated test's pass."""
    evidence, _ = candidate()
    state = collection.SourceState(
        commit=evidence.source_sha,
        tree=evidence.source_tree,
        dirty=False,
        verified_main=False,
    )
    pending = collection.candidate_gates(
        collection.Claims(schema_version="1.0"), state, evidence.wheel
    )
    assert all(
        gate.state == "pending" and gate.executor_role == "unassigned"
        for gate in pending
    )
    observed = evidence.gates[0]
    claims = collection.Claims(schema_version="1.0", gates=[observed])
    mixed = collection.candidate_gates(claims, state, evidence.wheel)
    assert next(gate for gate in mixed if gate.name == observed.name) == observed
    assert sum(gate.state == "pass" for gate in mixed) == 1
    with pytest.raises(ValueError, match="duplicate gate"):
        collection.candidate_gates(
            collection.Claims(schema_version="1.0", gates=[observed, observed]),
            state,
            evidence.wheel,
        )


def test_serialization_failure_and_overwrite_protection(tmp_path: Path) -> None:
    """Serialize before writing, then refuse overwriting accepted evidence bytes."""
    output = tmp_path / "report.json"
    with pytest.raises(ValueError, match="JSON compliant"):
        collection.write_json(output, {"invalid": float("nan")})
    assert not output.exists()
    raw = collection.write_json(output, {"state": "pending"})
    assert output.read_bytes() == raw
    with pytest.raises(FileExistsError):
        collection.write_json(output, {"state": "pass"})
    assert output.read_bytes() == raw
