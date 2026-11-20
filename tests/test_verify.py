# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Verification fails closed without turning bounded CI into release acceptance."""

import argparse
from typing import TYPE_CHECKING

import pytest
from scripts import verify
from scripts.processes import Execution, ToolExecutionError

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("mode", ["ci", "full"])
@pytest.mark.parametrize("outcome", [0, 1])
def test_gate_scope_and_release_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mode: str,
    outcome: int,
) -> None:
    """CI stays bounded; full verification propagates missing release gates."""
    output = verify.workspace(tmp_path / "owned")
    calls: list[str] = []

    def run(argv: list[str], **options: object) -> Execution:
        label = str(options["label"])
        calls.append(label)
        if label == "uv-version":
            (output / "logs/uv-version.stdout").write_text("uv 0.13.6\n")
        if label == "release-evidence":
            assert argv[argv.index("--claims") + 1] == str(tmp_path / "claims.json")
        code = outcome if label == "release-evidence" else 0
        accepted = options["accepted"]
        assert isinstance(accepted, frozenset)
        assert code in accepted
        assert "--fix" not in argv
        return Execution(label, code, "a" * 64, "b" * 64, 0.1)

    monkeypatch.setattr(verify, "run_tool", run)
    claims = tmp_path / "claims.json" if mode == "full" else None
    result = verify.verify(
        argparse.Namespace(ci=mode == "ci", uv="uv", claims=claims), output
    )
    message = capsys.readouterr().out
    if mode == "ci":
        assert result == 0
        assert "release-evidence" not in calls
        assert "tests" not in calls
        assert "cli-package-smoke" in calls
        assert "release acceptance" not in message
    else:
        assert result == outcome
        assert calls[-1] == "release-evidence"
        assert calls.index("tests") < calls.index("coverage")
        assert ("BLOCKED" in message) == bool(outcome)


def test_failed_check_stops_later_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A static failure stops package generation and release checks."""
    output = tmp_path / "owned"
    calls: list[str] = []

    def run(argv: list[str], **options: object) -> Execution:
        del argv
        label = str(options["label"])
        calls.append(label)
        if label == "uv-version":
            (output / "logs/uv-version.stdout").write_text("uv 0.13.6\n")
            return Execution(label, 0, "a" * 64, "b" * 64, 0.1)
        raise ToolExecutionError(label)

    monkeypatch.setattr(verify, "run_tool", run)
    assert verify.main(["--full", "--evidence-dir", str(output)]) == verify.FAILED
    assert calls == ["uv-version", "frozen-sync"]
    observed = capsys.readouterr()
    assert not observed.out
    assert observed.err == "FAIL: frozen-sync.\n"


def test_workspace_preserves_existing_files_and_refuses_source(
    tmp_path: Path,
) -> None:
    """Verification never adopts an existing directory or writes logs into source."""
    existing = tmp_path / "existing"
    existing.mkdir()
    retained = existing / "sentinel"
    retained.write_text("synthetic existing bytes")
    with pytest.raises(FileExistsError):
        verify.workspace(existing)
    assert retained.read_text() == "synthetic existing bytes"
    with pytest.raises(ValueError, match="separate"):
        verify.workspace(verify.PROJECT / "verification-test-output")
    link = tmp_path / "link"
    link.symlink_to(existing, target_is_directory=True)
    with pytest.raises(ValueError, match="linked"):
        verify.workspace(link / "output")


@pytest.mark.parametrize("failure", ["python", "uv", "io", "interrupted"])
def test_setup_and_interruption_never_report_a_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    """Missing selected tools, failed evidence I/O and interruption stay nonzero."""
    output = tmp_path / "owned"
    if failure == "python":
        monkeypatch.setattr(verify.platform, "python_version", lambda: "3.14.0")
    elif failure == "io":
        output.mkdir()
    elif failure == "interrupted":

        def interrupted(*_args: object) -> None:
            raise KeyboardInterrupt

        monkeypatch.setattr(verify, "verify", interrupted)
    else:

        def wrong_version(argv: list[str], **options: object) -> Execution:
            del argv, options
            (output / "logs/uv-version.stdout").write_text("uv 0.0.0\n")
            return Execution("uv-version", 0, "a" * 64, "b" * 64, 0.1)

        monkeypatch.setattr(verify, "run_tool", wrong_version)
    result = verify.main(["--full", "--evidence-dir", str(output)])
    assert result == (130 if failure == "interrupted" else verify.FAILED)
    observed = capsys.readouterr()
    assert not observed.out
    assert "FAIL" in observed.err or "interrupted" in observed.err
    assert str(tmp_path) not in observed.err


def test_default_workspace_owns_a_fresh_private_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default temporary output cannot adopt a preexisting evidence directory."""
    monkeypatch.setattr(verify.tempfile, "mkdtemp", lambda **_options: str(tmp_path))
    result = verify.workspace(None)
    assert result == tmp_path / "evidence"
    assert (result / "logs").is_dir()
