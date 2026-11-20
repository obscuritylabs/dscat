# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Acceptance harness failures cannot masquerade as installed offline success."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import tomli_w
from scripts import installed_acceptance as acceptance
from scripts.evidence_models import InstalledAcceptance

from dscat.models.catalog import Catalog
from dscat.serialization import canonical_bytes
from tests.test_publication_bindings import approved_fixture

EXPECTED_CLI_CASES = 9


@pytest.mark.parametrize("condition", [True, False])
def test_explicit_acceptance_checks_remain_active(*, condition: bool) -> None:
    """Harness assertions remain enforced independently of Python optimize mode."""
    if condition:
        acceptance.require(condition, "Synthetic assertion")
    else:
        with pytest.raises(ValueError, match="Synthetic assertion"):
            acceptance.require(condition, "Synthetic assertion")


def test_missing_receipt_cannot_prove_publication() -> None:
    """A missing result or result without a receipt cannot establish written output."""
    for result in [
        None,
        acceptance.CommandResult.model_validate(
            {
                "schema_version": "1.0",
                "command": "build",
                "exit_code": 0,
                "diagnostics": [],
                "summary": {},
            }
        ),
    ]:
        with pytest.raises(ValueError, match="omitted its receipt"):
            acceptance.require_receipt(result)


@pytest.mark.parametrize("denied", [True, False])
def test_network_probe_requires_actual_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, denied: bool
) -> None:
    """The probe fails when a socket can be created, regardless of workflow results."""
    log = tmp_path / "probe"
    log.write_bytes(b"synthetic probe event\n")

    def socket() -> SimpleNamespace:
        if denied:
            msg = "Synthetic guard refusal"
            raise RuntimeError(msg)
        return SimpleNamespace()

    if denied:
        monkeypatch.setattr(acceptance.socket, "socket", socket)
        assert acceptance.confirm_network_guard(log) == log.read_bytes()
    else:
        # A real local descriptor does not connect to a host or send data.
        with pytest.raises(ValueError, match="real denying network guard"):
            acceptance.confirm_network_guard(log)


@pytest.mark.parametrize(
    "case",
    [
        (1, "", "", "outcome mismatch"),
        (0, "", "synthetic stderr", "unexpected stderr"),
        (0, "Synthetic measurements", "", "exposed a value"),
    ],
)
def test_unexpected_cli_outcomes_refuse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: tuple[int, str, str, str],
) -> None:
    """Harness failures retain the command's required exit and privacy conditions."""
    returncode, stdout, stderr, message = case

    def run(argv: list[str], **options: object) -> subprocess.CompletedProcess[str]:
        del options
        return subprocess.CompletedProcess(argv, returncode, stdout, stderr)

    monkeypatch.setattr(acceptance.subprocess, "run", run)
    with pytest.raises(ValueError, match=message):
        acceptance.invoke(tmp_path, ["template"], 0)


def test_real_synthetic_cli_workflow_exercises_harness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exercise harness logic with actual CLI processes; installed proof is separate."""
    materials = tmp_path / "materials"
    materials.mkdir()
    record, configuration = approved_fixture(detailed=True)
    (materials / "approved.json").write_bytes(
        canonical_bytes(Catalog(schema_version="1.0", datasets=[record]))
    )
    (materials / "settings.toml").write_text(
        tomli_w.dumps(configuration.model_dump(mode="json", exclude_none=True))
    )
    log = tmp_path / "network-events"
    log.write_bytes(b"synthetic probe event\n")
    monkeypatch.setenv("DSCAT_NETWORK_LOG", str(log))
    # This is a harness test using the source installation. The collector's
    # separate clean-environment execution proves the genuine installed path.
    monkeypatch.setattr(
        acceptance,
        "dscat",
        SimpleNamespace(__file__=str(Path(acceptance.sys.prefix) / "synthetic.py")),
    )

    def denied_socket() -> None:
        msg = "Synthetic socket refusal"
        raise RuntimeError(msg)

    monkeypatch.setattr(acceptance.socket, "socket", denied_socket)
    monkeypatch.setattr(
        acceptance.sys,
        "argv",
        [
            "installed-acceptance",
            "--materials",
            str(materials),
            "--workspace",
            str(tmp_path / "work"),
        ],
    )
    acceptance.main()
    observed = InstalledAcceptance.model_validate_json(capsys.readouterr().out)
    assert observed.cli_cases == EXPECTED_CLI_CASES
    assert observed.state == "pass"
    assert observed.canonical_generation != observed.public_generation
    assert log.read_bytes() == b"synthetic probe event\n"
    assert not (tmp_path / "work/intake.xlsx").exists()
    assert json.loads((tmp_path / "work/private-report.json").read_bytes())["losses"]
