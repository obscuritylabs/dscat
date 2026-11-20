# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Complete CLI publication contract and private-report separation."""

import errno
import json
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from dscat import cli
from dscat.intake import worker
from dscat.models.catalog import Catalog
from dscat.models.configuration import ExportConfiguration
from dscat.models.diagnostics import CommandResult
from dscat.reporting import PrivateReport
from dscat.storage import singlefile
from dscat.storage.flatfiles import load_snapshot, save_snapshot
from dscat.storage.projections import load_projection_snapshot
from tests.test_dcat_us_3 import catalog, configuration
from tests.test_publication_bindings import approved_fixture

if TYPE_CHECKING:
    from pathlib import Path

RUNNER = CliRunner()
OPERATIONAL = 3
INVOCATION = 2


@pytest.fixture
def direct_coordinator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise export logic directly; installed tests cover process supervision."""
    monkeypatch.setattr(
        cli, "invoke", lambda request, _: worker.inspect_selection(request)
    )


def test_template_explicit_atomic_replacement_and_report(tmp_path: Path) -> None:
    """Generate complete bytes and refuse unauthorized workbook or report overwrites."""
    path = tmp_path / "intake.xlsx"
    report = tmp_path / "report.json"
    args = ["template", "--output", str(path), "--diagnostics", str(report)]
    first = RUNNER.invoke(cli.app, args)
    assert first.exit_code == 0, first.output
    content = path.read_bytes()
    assert content.startswith(b"PK")
    parsed = PrivateReport.model_validate_json(report.read_bytes())
    assert parsed.losses == []
    assert "receipt" not in json.loads(report.read_bytes())
    assert RUNNER.invoke(cli.app, args).exit_code == OPERATIONAL
    assert path.read_bytes() == content
    assert RUNNER.invoke(cli.app, [*args, "--replace"]).exit_code == 0
    assert path.read_bytes() == content


@pytest.mark.usefixtures("direct_coordinator")
@pytest.mark.parametrize("audience", ["internal", "public"])
def test_export_saved_canonical_both_targets_and_separate_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, audience: str
) -> None:
    """Export never needs original workbooks and never puts reports in a public root."""
    record, configured = approved_fixture(detailed=True)
    source = Catalog(schema_version="1.0", datasets=[record])
    root = tmp_path / "source"
    save_snapshot(root, source)
    original = (root / "CURRENT").read_bytes()
    output = tmp_path / "export"
    report = tmp_path / "private.json"
    monkeypatch.setattr(cli, "load_explicit_configuration", lambda _: configured)
    args = [
        "export",
        str(root),
        "--output",
        str(output),
        "--target",
        "odcs-3.2",
        "--target",
        "dcat-us-3",
        "--audience",
        audience,
        "--diagnostics",
        str(report),
        "--format",
        "json",
    ]
    result = RUNNER.invoke(cli.app, args)
    assert result.exit_code == 0, result.output
    parsed = CommandResult.model_validate_json(result.stdout)
    assert parsed.receipt is not None
    assert parsed.receipt.targets == ["dcat-us-3", "odcs-3.2"]
    assert source.datasets[0].title not in result.output
    private = PrivateReport.model_validate_json(report.read_bytes())
    assert private.losses
    assert "receipt" not in json.loads(report.read_bytes())
    loaded = (
        load_projection_snapshot(output)
        if audience == "public"
        else load_snapshot(output)
    )
    assert loaded.generation == parsed.receipt.sha256
    assert parsed.receipt.kind == (
        "projection" if audience == "public" else "canonical"
    )
    assert (root / "CURRENT").read_bytes() == original
    assert RUNNER.invoke(cli.app, args).exit_code == OPERATIONAL
    repeated = RUNNER.invoke(cli.app, [*args, "--replace"])
    assert repeated.exit_code == 0
    assert CommandResult.model_validate_json(repeated.stdout).receipt == parsed.receipt


@pytest.mark.usefixtures("direct_coordinator")
@pytest.mark.parametrize("audience", ["internal", "public"])
def test_blocked_targets_partial_internal_and_absent_public(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, audience: str
) -> None:
    """Keep valid canonical facts for internal failures; withhold every public file."""
    root = tmp_path / "source"
    save_snapshot(root, catalog())
    configured_values = configuration().model_dump(exclude_none=True)
    configured_values.pop("odcs_3_2")
    configured = ExportConfiguration.model_validate(configured_values)
    monkeypatch.setattr(cli, "load_explicit_configuration", lambda _: configured)
    output = tmp_path / "export"
    report = tmp_path / "private.json"
    result = RUNNER.invoke(
        cli.app,
        [
            "export",
            str(root),
            "--output",
            str(output),
            "--target",
            "dcat-us-3",
            "--target",
            "odcs-3.2",
            "--audience",
            audience,
            "--diagnostics",
            str(report),
            "--format",
            "json",
        ],
    )
    parsed = CommandResult.model_validate_json(result.stdout)
    if audience == "internal":
        assert result.exit_code == 1
        assert parsed.receipt is not None
    else:
        assert result.exit_code == 1
        assert parsed.receipt is None
        assert not output.exists()
    assert PrivateReport.model_validate_json(report.read_bytes()).assessment is not None


@pytest.mark.usefixtures("direct_coordinator")
def test_partial_target_exit_and_report_failure_preserve_current(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A report write error blocks bundle replacement; blocked targets have no files."""
    root = tmp_path / "source"
    save_snapshot(root, catalog())
    configured_values = configuration().model_dump(exclude_none=True)
    configured_values.pop("odcs_3_2")
    configured = ExportConfiguration.model_validate(configured_values)
    monkeypatch.setattr(cli, "load_explicit_configuration", lambda _: configured)
    output = tmp_path / "export"
    args = [
        "export",
        str(root),
        "--output",
        str(output),
        "--target",
        "dcat-us-3",
        "--target",
        "odcs-3.2",
        "--format",
        "json",
    ]
    result = RUNNER.invoke(cli.app, args)
    assert result.exit_code == 1, result.output
    parsed = CommandResult.model_validate_json(result.stdout)
    assert parsed.receipt is not None
    assert parsed.receipt.targets == ["dcat-us-3"]
    snapshot = load_snapshot(output)
    assert snapshot.manifest.successful_targets == ["dcat-us-3"]
    before = (output / "CURRENT").read_bytes()

    def disk_full(*_args: object, **_kwargs: object) -> None:
        raise OSError(errno.ENOSPC, "Synthetic private failure")

    monkeypatch.setattr(singlefile, "write_file", disk_full)
    failed = RUNNER.invoke(
        cli.app, [*args, "--replace", "--diagnostics", str(tmp_path / "report.json")]
    )
    assert failed.exit_code == OPERATIONAL
    assert CommandResult.model_validate_json(failed.stdout).receipt is None
    assert "Synthetic private" not in failed.output
    assert (output / "CURRENT").read_bytes() == before


@pytest.mark.parametrize(
    "args",
    [
        ["export", "private-input", "--output", "private-output"],
        [
            "export",
            "private-input",
            "--output",
            "private-output",
            "--target",
            "private-target",
        ],
        [
            "build",
            "private-input",
            "--output",
            "private-output",
            "--audience",
            "public",
        ],
        [
            "build",
            "private-input",
            "--output",
            "private-output",
            "--target",
            "odcs-3.2",
            "--target",
            "odcs-3.2",
        ],
        ["validate", "private-input", "--private-option"],
        ["export", "private-input", "--target", "odcs-3.2"],
        ["validate"],
    ],
)
def test_invalid_invocations_are_one_safe_json_result(args: list[str]) -> None:
    """Unknown options, missing arguments and invalid selections cannot echo values."""
    result = RUNNER.invoke(cli.app, [*args, "--format", "json"])
    assert result.exit_code == INVOCATION, result.output
    parsed = CommandResult.model_validate_json(result.stdout)
    assert parsed.diagnostics[0].code == "INVALID_INVOCATION"
    assert "private-" not in result.output
    assert "Traceback" not in result.output


@pytest.mark.parametrize(
    "args", [["private-command"], ["--private-option"], ["template", "--output"]]
)
def test_parser_errors_without_json_are_fixed(args: list[str]) -> None:
    """Top-level failures and template parser failures expose no supplied token."""
    result = RUNNER.invoke(cli.app, args)
    assert result.exit_code == INVOCATION
    assert result.output == "Invalid command invocation.\n"


@pytest.mark.parametrize("destination", ["source", "output", "config"])
def test_report_must_be_separate_from_all_selected_paths(
    tmp_path: Path, destination: str
) -> None:
    """Reject equal and nested report paths before reading configuration or input."""
    source, output, config = (
        tmp_path / name for name in ("source", "output", "config")
    )
    paths = {"source": source, "output": output, "config": config}
    report = paths[destination] / "report.json"
    result = RUNNER.invoke(
        cli.app,
        [
            "export",
            str(source),
            "--output",
            str(output),
            "--config",
            str(config),
            "--target",
            "odcs-3.2",
            "--diagnostics",
            str(report),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 1
    assert (
        CommandResult.model_validate_json(result.stdout).diagnostics[0].code
        == "UNSAFE_INPUT"
    )
    assert not output.exists()
