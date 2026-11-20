# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Run the bounded CI gate or the complete local verification sequence."""

import argparse
import os
import platform
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Literal

# The documented direct-script command needs the trusted checkout package root.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.processes import (
    ToolExecutionError,
    run_tool,
)

if TYPE_CHECKING:
    from scripts.processes import Execution

PROJECT = Path(__file__).resolve().parent.parent
PYTHON_VERSION = "3.15.2"
UV_VERSION = "0.13.6"
BLOCKED = 1
FAILED = 2


def workspace(requested: Path | None) -> Path:
    """Own a new private directory outside source without adopting existing files."""
    output = (
        Path(tempfile.mkdtemp(prefix="dscat-verification-")).resolve() / "evidence"
        if requested is None
        else requested
    )
    if any(path.is_symlink() for path in (output, *output.parents)):
        msg = "Verification evidence cannot use linked paths."
        raise ValueError(msg)
    output = output.resolve()
    if output.is_relative_to(PROJECT) or PROJECT.is_relative_to(output):
        msg = "Verification evidence must be separate from source."
        raise ValueError(msg)
    output.mkdir(mode=0o700)
    (output / "logs").mkdir(mode=0o700)
    return output


def environment(output: Path) -> dict[str, str]:
    """Avoid inherited source/tool overrides and keep coverage outside source."""
    result = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("UV_", "PIP_AUDIT_"))
        and key not in {"PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE"}
    }
    result["COVERAGE_FILE"] = str(output / "coverage")
    result["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return result


def commands(uv: str, mode: Literal["ci", "full"]) -> list[tuple[str, list[str]]]:
    """Select the full suite or bounded CI static and CLI checks."""
    run = [uv, "run", "--frozen"]
    result = [
        ("frozen-sync", [uv, "sync", "--frozen", "--all-groups"]),
        ("ruff", [*run, "ruff", "check", ".", "--output-format", "concise"]),
        ("format", [*run, "ruff", "format", "--check", "."]),
        ("typing", [*run, "ty", "check", "--error-on-warning"]),
        (
            "documents",
            [*run, "python", "docs/evidence/architecture/verify_documents.py"],
        ),
    ]
    if mode == "ci":
        result.append(
            (
                "cli-package-smoke",
                [*run, "pytest", "-q", "tests/test_package.py", "tests/test_cli.py"],
            )
        )
    else:
        result.extend(
            [
                (
                    "tests",
                    [*run, "coverage", "run", "--branch", "-m", "pytest", "-q"],
                ),
                ("coverage", [*run, "coverage", "report", "--fail-under=100"]),
            ]
        )
    return result


def verify(arguments: argparse.Namespace, output: Path) -> int:
    """Fail fast on automated checks and preserve the separate readiness decision."""
    if platform.python_version() != PYTHON_VERSION:
        msg = "Verification requires the selected interpreter."
        raise ValueError(msg)
    child_environment = environment(output)

    def execute(
        label: str, argv: list[str], accepted: frozenset[int] = frozenset({0})
    ) -> Execution:
        return run_tool(
            argv,
            label=label,
            directory=PROJECT,
            logs=output / "logs",
            environment=child_environment,
            accepted=accepted,
            timeout=600,
        )

    execute("uv-version", [arguments.uv, "--version"])
    if (output / "logs/uv-version.stdout").read_text().split()[:2] != [
        "uv",
        UV_VERSION,
    ]:
        msg = "Verification requires the selected uv version."
        raise ValueError(msg)
    mode = "ci" if arguments.ci else "full"
    for label, argv in commands(arguments.uv, mode):
        execute(label, argv)
        sys.stdout.write(f"PASS: {label}\n")
        sys.stdout.flush()
    if arguments.ci:
        sys.stdout.write("PASS: bounded CI verification.\n")
        return 0
    command = [
        arguments.uv,
        "run",
        "--frozen",
        "python",
        "-m",
        "scripts.release_evidence",
        "--output",
        str(output / "candidate"),
        "--uv",
        arguments.uv,
    ]
    if arguments.claims is not None:
        command.extend(["--claims", str(arguments.claims.resolve())])
    observed = execute("release-evidence", command, frozenset({0, BLOCKED}))
    if observed.returncode == BLOCKED:
        sys.stdout.write("BLOCKED: release acceptance; inspect candidate readiness.\n")
        return BLOCKED
    sys.stdout.write("PASS: full local verification and release acceptance.\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Keep failures nonzero and report only the selected check, never raw output."""
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--ci", action="store_true")
    modes.add_argument("--full", action="store_true")
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--claims", type=Path)
    parser.add_argument("--uv", default=os.environ.get("UV", "uv"))
    arguments = parser.parse_args(argv)
    try:
        return verify(arguments, workspace(arguments.evidence_dir))
    except ToolExecutionError as error:
        sys.stderr.write(f"FAIL: {error.label}.\n")
    except OSError, ValueError:
        sys.stderr.write("FAIL: verification setup or evidence I/O.\n")
    except KeyboardInterrupt:
        sys.stderr.write("Verification interrupted.\n")
        return 130
    return FAILED


if __name__ == "__main__":
    raise SystemExit(main())
