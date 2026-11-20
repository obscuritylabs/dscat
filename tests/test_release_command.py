# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Release command failures remain private and missing gates remain blocking."""

import hashlib
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError
from scripts import candidate_collection, release_evidence
from scripts.candidate_collection import CollectedCandidate
from scripts.evidence_models import InstalledAcceptance
from scripts.processes import ToolExecutionError

from tests.test_release_evidence import candidate

COLLECTION_FAILED = 2

if TYPE_CHECKING:
    from pathlib import Path


def observed() -> CollectedCandidate:
    """Use explicit synthetic observations with current feed retrieval times."""
    evidence, actual = candidate()
    evidence = evidence.model_copy(
        update={
            "feeds": [
                feed.model_copy(
                    update={
                        "retrieved_at": datetime.now(UTC)
                        .isoformat()
                        .replace("+00:00", "Z")
                    }
                )
                for feed in evidence.feeds
            ]
        }
    )
    return CollectedCandidate(evidence=evidence, actual=actual, kev_cves=set())


@pytest.mark.parametrize("pending", [True, False])
def test_command_preserves_decision_and_checksums(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *,
    pending: bool,
) -> None:
    """A completed collection still returns failure when release gates are missing."""
    collected = observed()
    if pending:
        collected = CollectedCandidate(
            evidence=collected.evidence.model_copy(update={"gates": []}),
            actual=collected.actual,
            kev_cves=set(),
        )
    assets = tmp_path / "assets"
    assets.mkdir()
    archive = assets / "synthetic-artifact"
    archive.write_bytes(b"synthetic archive")

    def collect(
        project: Path, output: Path, uv: str, claims: candidate_collection.Claims
    ) -> CollectedCandidate:
        assert project == tmp_path
        assert output == tmp_path
        assert uv == "selected-uv"
        assert claims.gates == []
        return collected

    monkeypatch.setattr(candidate_collection, "collect_candidate", collect)
    code = release_evidence.main(
        ["--project", str(tmp_path), "--output", str(tmp_path), "--uv", "selected-uv"]
    )
    output = capsys.readouterr()
    assert code == int(pending)
    assert not output.err
    assert json.loads(output.out)["state"] == ("blocked" if pending else "ready")
    assert json.loads((assets / "readiness.json").read_bytes()) == json.loads(
        output.out
    )
    expected = {
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in [archive, assets / "readiness.json"]
    }
    assert set((assets / "SHA256SUMS").read_text().splitlines()) == expected
    assert str(tmp_path) not in output.out


@pytest.mark.parametrize(
    "case",
    [
        (ToolExecutionError("audit-runtime"), 2, "audit-runtime"),
        (ValueError("synthetic-private-value"), 2, "invalid input or I/O"),
        (OSError("synthetic-private-value"), 2, "invalid input or I/O"),
        (TypeError("synthetic-private-value"), 2, "invalid input or I/O"),
        (KeyboardInterrupt(), 130, "interrupted"),
    ],
)
def test_command_failure_summary_excludes_raw_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    case: tuple[BaseException, int, str],
) -> None:
    """Failures cannot become a ready result or leak raw exception text."""
    error, expected, message = case

    def fail(arguments: object) -> None:
        del arguments
        raise error

    monkeypatch.setattr(release_evidence, "collect_command", fail)
    assert release_evidence.main(["--output", str(tmp_path)]) == expected
    output = capsys.readouterr()
    assert not output.out
    assert message in output.err
    assert "synthetic-private-value" not in output.err
    assert str(tmp_path) not in output.err
    assert not (tmp_path / "assets").exists()


def test_claims_are_validated_before_collection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Malformed supplied gate claims cannot create a candidate workspace."""
    claims = tmp_path / "claims.json"
    claims.write_text('{"schema_version":"1.0","gates":[{"state":"pass"}]}')
    output = tmp_path / "output"
    assert (
        release_evidence.main(["--output", str(output), "--claims", str(claims)])
        == COLLECTION_FAILED
    )
    assert not output.exists()
    assert "invalid input or I/O" in capsys.readouterr().err


def test_installed_observation_requires_active_denial_and_exact_workflow() -> None:
    """A nominal pass cannot substitute for network denial or completed CLI cases."""
    observation = {
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
    assert InstalledAcceptance.model_validate(observation).state == "pass"
    for mutation in [
        {"guard_probe_denied": False},
        {"workflow_network_attempts": 1},
        {"unknown_reference_denied": False},
        {"cli_cases": 8},
        {"unexpected": "synthetic-private-value"},
    ]:
        with pytest.raises(ValidationError):
            InstalledAcceptance.model_validate(observation | mutation)
