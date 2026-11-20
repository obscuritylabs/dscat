# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Canonical-only build transactions expose only a safe output identity."""

from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from dscat import cli
from dscat.intake import worker
from dscat.intake.discovery import DiscoveryRequest
from dscat.intake.limits import DEFAULT_LIMITS, IntakeError
from dscat.models.diagnostics import CommandResult, Diagnostic, OutputReceipt
from dscat.models.requests import CommandRequest
from dscat.storage.flatfiles import load_snapshot, save_snapshot
from tests.test_cli_validation import successful_reply
from tests.test_storage import catalog

RUNNER = CliRunner()
OPERATIONAL = 3
INVOCATION = 2
INTERNAL = 4


def test_empty_build_save_load_replace_and_safe_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty directory is valid canonical input; replacement still needs intent."""
    source = tmp_path / "input"
    source.mkdir()
    root = tmp_path / "bundle"
    monkeypatch.setattr(
        cli, "invoke", lambda request, _timeout: worker.inspect_selection(request)
    )
    arguments = ["build", str(source), "--output", str(root), "--format", "json"]
    first = RUNNER.invoke(cli.app, arguments)
    assert first.exit_code == 0
    result = CommandResult.model_validate_json(first.stdout)
    assert result.command == "build"
    assert result.receipt is not None
    assert result.receipt.kind == "canonical"
    assert result.receipt.sha256 == load_snapshot(root).generation
    assert load_snapshot(root).catalog.datasets == []
    assert str(tmp_path) not in first.stdout
    refused = RUNNER.invoke(cli.app, arguments)
    assert refused.exit_code == OPERATIONAL
    assert CommandResult.model_validate_json(refused.stdout).receipt is None
    repeated = RUNNER.invoke(cli.app, [*arguments, "--replace"])
    assert repeated.exit_code == 0
    assert CommandResult.model_validate_json(repeated.stdout).receipt == result.receipt
    text = RUNNER.invoke(
        cli.app, ["build", str(source), "--output", str(root), "--replace"]
    )
    assert text.exit_code == 0
    assert f"Published canonical: {result.receipt.sha256}" in text.stdout


def test_build_blocks_overlapping_and_invalid_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Input failures leave a destination absent, including output-under-input."""
    source = tmp_path / "input"
    source.mkdir()
    monkeypatch.setattr(
        cli, "invoke", lambda request, _timeout: worker.inspect_selection(request)
    )
    result = RUNNER.invoke(
        cli.app,
        [
            "build",
            str(source),
            "--output",
            str(source / "output"),
            "--recursive",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 1
    assert not (source / "output").exists()
    assert (
        CommandResult.model_validate_json(result.stdout).diagnostics[0].code
        == "UNSAFE_INPUT"
    )
    source.joinpath("invalid.xlsx").write_bytes(b"synthetic invalid")
    monkeypatch.setattr(worker, "invoke", lambda *_args: successful_reply())
    # A wrong private archive role is invalid; it cannot become a published catalog.
    result = RUNNER.invoke(
        cli.app,
        ["build", str(source), "--output", str(tmp_path / "other"), "--format", "json"],
    )
    assert result.exit_code == INTERNAL
    assert not (tmp_path / "other").exists()


def test_missing_receipt_and_configuration_rejection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mocked coordinator cannot claim build success without a publication receipt."""
    monkeypatch.setattr(cli, "invoke", lambda *_args: successful_reply())
    arguments = [
        "build",
        "synthetic.xlsx",
        "--output",
        str(tmp_path / "bundle"),
        "--format",
        "json",
    ]
    missing = RUNNER.invoke(cli.app, arguments)
    assert missing.exit_code == INTERNAL
    assert CommandResult.model_validate_json(missing.stdout).receipt is None
    config = tmp_path / "config.toml"
    config.write_text('schema_version="9.0"')
    invalid = RUNNER.invoke(cli.app, [*arguments, "--config", str(config)])
    assert invalid.exit_code == INVOCATION
    bad_format = RUNNER.invoke(
        cli.app,
        [
            "build",
            "synthetic.xlsx",
            "--output",
            str(tmp_path / "bundle"),
            "--format",
            "unsafe-value",
        ],
    )
    assert bad_format.exit_code == INVOCATION
    assert "unsafe-value" not in bad_format.stdout
    assert not (tmp_path / "bundle").exists()


def test_private_reply_receipt_needs_valid_intake() -> None:
    """The receipt boundary rejects a success identity on failed or absent facts."""
    reply = successful_reply().model_dump(exclude_none=True)
    receipt = OutputReceipt(kind="canonical", sha256="a" * 64)
    for changed in ({"has_errors": True}, {"catalog": None}):
        data = reply | changed | {"receipt": receipt}
        data = {key: value for key, value in data.items() if value is not None}
        with pytest.raises(ValidationError):
            worker.WorkerReply.model_validate(data)


def test_prepublication_ipc_budget_refuses_before_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A result too large to acknowledge must fail before any output is created."""
    source = tmp_path / "input"
    source.mkdir()
    root = tmp_path / "bundle"
    monkeypatch.setattr(worker, "MAX_REPLY_BYTES", 512)
    request = worker.CoordinatorRequest(
        schema_version="1.0",
        role="coordinator",
        discovery=DiscoveryRequest(input=source, output=root),
    )
    with pytest.raises(IntakeError, match="INPUT_LIMIT"):
        worker.inspect_selection(request)
    assert not root.exists()


def test_missing_private_input_is_not_invoked() -> None:
    """The execution helper still checks the optional typed shape independently."""
    request = CommandRequest(command="template", output=Path("synthetic.xlsx"))
    with pytest.raises(IntakeError, match="INVALID_INVOCATION"):
        cli.execute_catalog(request)


def test_retained_output_and_lock_have_explicit_recovery_guidance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Operators can distinguish retained history from a blocking writer lock."""
    source = tmp_path / "input"
    source.mkdir()
    root = tmp_path / "bundle"
    save_snapshot(root, catalog("a"))
    monkeypatch.setattr(
        cli, "invoke", lambda request, _timeout: worker.inspect_selection(request)
    )
    arguments = ["build", str(source), "--output", str(root), "--replace"]
    result = RUNNER.invoke(cli.app, arguments)
    assert result.exit_code == 0
    assert "RETAINED_OUTPUT" in result.stdout
    assert "no automatic cleanup" in result.stdout
    (root / ".writer.lock").write_bytes(b"abandoned")
    locked = RUNNER.invoke(cli.app, arguments)
    assert locked.exit_code == OPERATIONAL
    assert "PUBLICATION_LOCKED" in locked.stdout
    assert "Confirm all writers have stopped" in locked.stdout
    assert (root / ".writer.lock").read_bytes() == b"abandoned"


def test_publication_notice_cannot_exceed_diagnostic_limit(tmp_path: Path) -> None:
    """A full report stays valid when publication adds a retained-output notice."""
    root = tmp_path / "bundle"
    save_snapshot(root, catalog("other"))
    base = successful_reply().model_dump(exclude_none=True)
    base["diagnostics"] = [
        Diagnostic(
            code="DUPLICATE_IDENTICAL", severity="warning", message_key="review_scope"
        )
    ] * DEFAULT_LIMITS.diagnostics
    reply = worker.WorkerReply.model_validate(base)
    request = worker.CoordinatorRequest(
        schema_version="1.0",
        role="coordinator",
        discovery=DiscoveryRequest(input=tmp_path / "input", output=root),
        replace=True,
    )
    published = worker.publish_selection(reply, request)
    assert published.receipt is not None
    assert len(published.diagnostics) == DEFAULT_LIMITS.diagnostics
    assert published.diagnostics[-1].code == "DIAGNOSTICS_TRUNCATED"
