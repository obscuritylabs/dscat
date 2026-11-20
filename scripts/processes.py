# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Run explicit developer tools with bounded waits and private, exclusive logs."""

import hashlib
import re
import subprocess
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

LOG_BYTES = 32 * 1024**2
CHUNK_BYTES = 65536
LOG_LIMIT = "log-limit"
INVALID_LABEL = "invalid-check-label"


class ToolExecutionError(Exception):
    """A tool boundary failure exposes only its fixed caller-selected check label."""

    def __init__(self, label: str) -> None:
        """Do not retain raw output, paths, command arguments or exception text."""
        super().__init__("A required verification tool failed.")
        self.label = label


@dataclass(frozen=True)
class Execution:
    """Hashed outputs preserve evidence identity without publishing private logs."""

    check: str
    returncode: int
    stdout_sha256: str
    stderr_sha256: str
    elapsed_seconds: float

    def record(self) -> dict[str, object]:
        """Export only the fixed label, outcome, elapsed time and output digests."""
        return {
            "check": self.check,
            "returncode": self.returncode,
            "stdout_sha256": self.stdout_sha256,
            "stderr_sha256": self.stderr_sha256,
            "elapsed_seconds": self.elapsed_seconds,
        }


def log_digest(path: Path) -> str:
    """Hash an owned completed log without retaining its contents in memory."""
    if path.stat().st_size > LOG_BYTES:
        raise ToolExecutionError(LOG_LIMIT)
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_BYTES):
            total += len(chunk)
            if total > LOG_BYTES:
                raise ToolExecutionError(LOG_LIMIT)
            digest.update(chunk)
    return digest.hexdigest()


def run_tool(  # noqa: PLR0913 -- One explicit subprocess boundary owns its safeguards.
    argv: list[str],
    *,
    label: str,
    directory: Path,
    logs: Path,
    accepted: frozenset[int] = frozenset({0}),
    timeout: float = 300.0,
    environment: dict[str, str] | None = None,
) -> Execution:
    """Execute an argv array without a shell, accepting only declared exit statuses."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", label):
        raise ToolExecutionError(INVALID_LABEL)
    started = time.monotonic()
    stdout = logs / f"{label}.stdout"
    stderr = logs / f"{label}.stderr"
    try:
        with stdout.open("xb") as output, stderr.open("xb") as errors:
            result = subprocess.run(  # noqa: S603 -- Caller-owned tool argv; never a shell.
                argv,
                cwd=directory,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=errors,
                timeout=timeout,
                check=False,
            )
    except OSError, subprocess.TimeoutExpired:
        raise ToolExecutionError(label) from None
    execution = Execution(
        check=label,
        returncode=result.returncode,
        stdout_sha256=log_digest(stdout),
        stderr_sha256=log_digest(stderr),
        elapsed_seconds=round(time.monotonic() - started, 6),
    )
    if result.returncode not in accepted:
        raise ToolExecutionError(label)
    return execution
