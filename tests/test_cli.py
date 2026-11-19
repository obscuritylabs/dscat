# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Acceptance checks for the initial command-line surface."""

import pytest
from typer.testing import CliRunner

from dscat.cli import app

runner = CliRunner()
INVOCATION_ERROR = 2


@pytest.mark.parametrize("arguments", [["--help"], ["--no-color", "--help"], []])
def test_help(arguments: list[str]) -> None:
    """Help describes the package and includes its proprietary notice."""
    result = runner.invoke(app, arguments)
    assert result.exit_code == 0
    assert "Dataset Catalog" in result.stdout
    assert "Obscurity Labs" in result.stdout
    assert "Proprietary License" in result.stdout
    assert "\x1b" not in result.stdout


@pytest.mark.parametrize("arguments", [["--version"], ["--no-color", "--version"]])
def test_version(arguments: list[str]) -> None:
    """Version output is plain and does not include help."""
    result = runner.invoke(app, arguments)
    assert result.exit_code == 0
    assert result.stdout == "dscat 0.1.0\n"


@pytest.mark.parametrize("arguments", [["--unsupported"], ["unsupported"]])
def test_invalid_invocation(arguments: list[str]) -> None:
    """Unknown options and commands fail with the invocation exit code."""
    result = runner.invoke(app, arguments)
    assert result.exit_code == INVOCATION_ERROR
    assert "Traceback" not in result.output
    assert "dscat 0.1.0" not in result.stdout
