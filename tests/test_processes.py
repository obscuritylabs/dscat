# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Developer subprocess evidence excludes raw output and preserves existing logs."""

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest
from scripts import processes


def test_real_tool_result_is_value_free(tmp_path: Path) -> None:
    """Record real stdout/stderr identities without exposing their private contents."""
    result = processes.run_tool(
        [
            sys.executable,
            "-I",
            "-c",
            (
                'import sys;print("synthetic-private-output");'
                'sys.stderr.write("synthetic-private-error")'
            ),
        ],
        label="synthetic-check",
        directory=tmp_path,
        logs=tmp_path,
    )
    record = result.record()
    assert record["returncode"] == 0
    assert (
        record["stdout_sha256"]
        == hashlib.sha256(b"synthetic-private-output\n").hexdigest()
    )
    assert (
        record["stderr_sha256"]
        == hashlib.sha256(b"synthetic-private-error").hexdigest()
    )
    assert result.elapsed_seconds >= 0
    assert "synthetic-private" not in json.dumps(record)
    assert str(tmp_path) not in json.dumps(record)
    assert str(sys.executable) not in json.dumps(record)


@pytest.mark.parametrize("accepted", [False, True])
def test_explicit_exit_status_policy(tmp_path: Path, *, accepted: bool) -> None:
    """Only a caller explicitly expecting scanner findings may accept exit 1."""
    arguments = [sys.executable, "-I", "-c", "raise SystemExit(1)"]
    if accepted:
        result = processes.run_tool(
            arguments,
            label="audit",
            directory=tmp_path,
            logs=tmp_path,
            accepted=frozenset({0, 1}),
        )
        assert result.returncode == 1
    else:
        with pytest.raises(
            processes.ToolExecutionError, match="verification tool"
        ) as failure:
            processes.run_tool(
                arguments, label="audit", directory=tmp_path, logs=tmp_path
            )
        assert failure.value.label == "audit"


@pytest.mark.parametrize(
    "kind", ["missing", "timeout", "existing-log", "invalid-label"]
)
def test_failures_never_overwrite_or_expose_details(tmp_path: Path, kind: str) -> None:
    """Keep missing tools, deadlines and log overwrite refusal explicit."""
    arguments = [sys.executable, "-I", "-c", "import time;time.sleep(2)"]
    label = "synthetic-check"
    if kind == "missing":
        arguments = [str(tmp_path / "synthetic-private-missing")]
    elif kind == "existing-log":
        (tmp_path / "synthetic-check.stdout").write_bytes(b"accepted")
    elif kind == "invalid-label":
        label = "../synthetic-private-label"
    with pytest.raises(
        processes.ToolExecutionError, match="verification tool"
    ) as failure:
        processes.run_tool(
            arguments, label=label, directory=tmp_path, logs=tmp_path, timeout=0.05
        )
    assert "synthetic-private" not in str(failure.value)
    if kind == "existing-log":
        assert (tmp_path / "synthetic-check.stdout").read_bytes() == b"accepted"
    assert not (tmp_path.parent / "synthetic-private-label.stdout").exists()


@pytest.mark.parametrize("growing", [False, True])
def test_completed_log_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, growing: bool
) -> None:
    """Both initial size and observed growth count toward the finite log ceiling."""
    path = tmp_path / "log"
    path.write_bytes(b"12345")
    monkeypatch.setattr(processes, "LOG_BYTES", 4)
    if growing:
        original = Path.stat

        def before_growth(
            selected: Path, *, follow_symlinks: bool = True
        ) -> os.stat_result:
            observed = original(selected, follow_symlinks=follow_symlinks)
            if selected == path:
                values = list(observed)
                values[6] = 0
                return os.stat_result(values)
            return observed

        monkeypatch.setattr(Path, "stat", before_growth)
    with pytest.raises(
        processes.ToolExecutionError, match="verification tool"
    ) as failure:
        processes.log_digest(path)
    assert failure.value.label == "log-limit"
