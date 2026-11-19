# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""The initial validate command emits only safe versioned assessment output."""

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from dscat import cli
from dscat.intake.limits import ArchiveStatistics, fail
from dscat.intake.worker import ArchiveOutcome, WorkerReply
from dscat.models.catalog import Catalog, DatasetRecord, PartyReference
from dscat.models.diagnostics import CommandResult, ValidationAssessment

if TYPE_CHECKING:
    from pathlib import Path

    from dscat.models.diagnostics import Code


INVOCATION_ERROR = 2
RUNNER = CliRunner()


def successful_reply() -> WorkerReply:
    """Provide explicit typed test data without claiming real worker execution."""
    record = DatasetRecord(
        id="asset-001",
        title="Synthetic private title",
        description="Synthetic private description",
        core_party=PartyReference(label="Metadata support"),
    )
    return WorkerReply(
        schema_version="1.0",
        role="coordinator",
        outcomes=[
            ArchiveOutcome(
                source_token=1, archive_state="safe", statistics=ArchiveStatistics()
            )
        ],
        has_errors=False,
        selection_complete=True,
        catalog=Catalog(schema_version="1.0", datasets=[record]),
        assessment=ValidationAssessment(validity="valid"),
    )


def test_json_is_one_safe_result_without_help_or_canonical_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI projects IPC into diagnostics without private catalog facts."""
    monkeypatch.setattr(cli, "invoke", lambda *_args: successful_reply())
    result = RUNNER.invoke(
        cli.app,
        ["--no-color", "validate", "synthetic-sensitive-name.xlsx", "--format", "json"],
    )
    assert result.exit_code == 0
    output = CommandResult.model_validate_json(result.stdout)
    assert output.command == "validate"
    assert output.summary.examined_sources == 1
    assert output.summary.valid_records == 1
    assert output.assessment is not None
    assert output.assessment.validity == "valid"
    assert "Synthetic private" not in result.stdout
    assert "sensitive-name" not in result.stdout
    assert "\x1b" not in result.stdout


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("INVALID_METADATA", 1),
        ("RESOURCE_GUARD_UNAVAILABLE", 3),
        ("INPUT_LIMIT", 3),
        ("INVALID_CONFIGURATION", 2),
        ("INTERNAL_FAILURE", 4),
        ("INTERRUPTED", 130),
    ],
)
def test_fixed_failure_exit_and_no_source_echo(
    monkeypatch: pytest.MonkeyPatch, code: Code, expected: int
) -> None:
    """Expected failures retain categories and never echo private request paths."""

    def refused(*_args: object) -> WorkerReply:
        raise fail(code=code)

    monkeypatch.setattr(cli, "invoke", refused)
    result = RUNNER.invoke(
        cli.app, ["validate", "synthetic-sensitive.xlsx", "--format", "json"]
    )
    assert result.exit_code == expected
    output = CommandResult.model_validate_json(result.stdout)
    assert output.diagnostics[0].code == code
    assert "sensitive" not in result.stdout
    assert output.assessment is not None
    assert output.assessment.validity == "unexamined"


@pytest.mark.parametrize(
    ("error", "expected"), [(OSError, 3), (KeyboardInterrupt, 130), (RuntimeError, 4)]
)
def test_unexpected_operational_text_is_minimized(
    monkeypatch: pytest.MonkeyPatch, error: type[BaseException], expected: int
) -> None:
    """No exception message or traceback escapes the command boundary."""

    def refused(*_args: object) -> WorkerReply:
        msg = "synthetic-sensitive-exception"
        raise error(msg)

    monkeypatch.setattr(cli, "invoke", refused)
    result = RUNNER.invoke(cli.app, ["validate", "synthetic.xlsx", "--format", "json"])
    assert result.exit_code == expected
    assert "sensitive" not in result.stdout
    assert "Traceback" not in result.stdout
    CommandResult.model_validate_json(result.stdout)


def test_invalid_explicit_configuration_precedes_any_intake(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invalid config does not launch discovery and does not expose TOML contents."""
    config = tmp_path / "configuration.toml"
    config.write_text('schema_version="1.0"\nunknown="synthetic-sensitive-value"')
    requested: list[object] = []
    monkeypatch.setattr(cli, "invoke", lambda *args: requested.append(args))
    result = RUNNER.invoke(
        cli.app,
        ["validate", "synthetic.xlsx", "--config", str(config), "--format", "json"],
    )
    assert result.exit_code == INVOCATION_ERROR
    assert requested == []
    assert "sensitive" not in result.stdout
    assert (
        CommandResult.model_validate_json(result.stdout).diagnostics[0].code
        == "INVALID_CONFIGURATION"
    )


def test_invalid_format_and_text_location_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unsupported formats fail safely; ordinary text supplies corrections."""
    invalid = RUNNER.invoke(
        cli.app,
        ["validate", "synthetic.xlsx", "--format", "synthetic-sensitive-format"],
    )
    assert invalid.exit_code == INVOCATION_ERROR
    assert "sensitive-format" not in invalid.stdout
    reply = WorkerReply(
        schema_version="1.0",
        role="coordinator",
        diagnostics=[
            fail(code="INVALID_METADATA", source_token=1).diagnostic.model_copy(
                update={"sheet": "Datasets", "row": 2, "column": 3}
            )
        ],
        has_errors=True,
        selection_complete=True,
    )
    monkeypatch.setattr(cli, "invoke", lambda *_args: reply)
    result = RUNNER.invoke(cli.app, ["validate", "synthetic.xlsx"])
    assert result.exit_code == 1
    assert "source 1 Datasets row 2 column 3" in result.stdout
    assert "Correct the metadata" in result.stdout
