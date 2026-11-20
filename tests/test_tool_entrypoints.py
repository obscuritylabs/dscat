# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Developer entrypoints expose help without collecting or publishing anything."""

import runpy
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "script", ["verify.py", "installed_acceptance.py", "release_evidence.py"]
)
def test_direct_entrypoint_help_has_no_collection_side_effects(
    script: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Help exits successfully before workspaces, builds or network collection."""
    path = Path(__file__).parents[1] / "scripts" / script
    monkeypatch.setattr(sys, "argv", [script, "--help"])
    monkeypatch.setattr(sys, "path", list(sys.path))
    with pytest.raises(SystemExit) as result:
        runpy.run_path(str(path), run_name="__main__")
    assert result.value.code == 0
    output = capsys.readouterr()
    assert "usage:" in output.out
    assert not output.err
