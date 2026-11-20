# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Collection reconciles actual tool output with source and distribution identities."""

import hashlib
from typing import TYPE_CHECKING

import pytest
from scripts import candidate_collection as collection
from scripts.processes import Execution

from tests.test_artifacts import METADATA, SOURCE, tarred, wheel_files, zipped

if TYPE_CHECKING:
    from pathlib import Path


PROJECT = b"""[project]
version = "0.1.0"
requires-python = ">=3.15,<3.16"
dependencies = ["foo==1"]
"""


def context(tmp_path: Path) -> collection.Collection:
    """Own disposable source and evidence paths with the ordinary initializer."""
    source = tmp_path / "source"
    source.mkdir()
    return collection.initialize(source, tmp_path / "evidence", "selected-uv")


@pytest.mark.parametrize("dirty", [True, False])
@pytest.mark.parametrize("remote_matches", [True, False])
def test_actual_git_state_controls_dirty_and_main_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    dirty: bool,
    remote_matches: bool,
) -> None:
    """Remote disagreement and untracked changes cannot inherit a clean-main claim."""
    candidate = context(tmp_path)
    commit = "a" * 40
    tree = "b" * 40
    values = {
        "commit": commit,
        "tree": tree,
        "status": "?? synthetic-untracked" if dirty else "",
        "remote": f"{commit if remote_matches else 'c' * 40}\trefs/heads/main",
    }

    def run(argv: list[str], **options: object) -> Execution:
        del argv
        label = str(options["label"])
        (candidate.work / "logs" / f"{label}.stdout").write_text(
            values[label.rsplit("-", 1)[1]] + "\n"
        )
        return Execution(label, 0, "d" * 64, "e" * 64, 0.1)

    monkeypatch.setattr(collection, "run_tool", run)
    observed = collection.source_state(candidate, "before")
    assert observed.commit == commit
    assert observed.tree == tree
    assert observed.dirty == dirty
    assert observed.verified_main == remote_matches
    assert len(candidate.executions) == len(values)
    assert str(tmp_path) not in str(candidate.arguments)


@pytest.mark.parametrize("mutation", ["none", "extra", "source"])
def test_built_archives_must_match_expected_outputs_and_reviewed_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    """A successful builder exit cannot certify extra files or changed package bytes."""
    candidate = context(tmp_path)
    source = SOURCE | {"pyproject.toml": PROJECT}
    contents = wheel_files()
    if mutation == "source":
        contents["dscat/__init__.py"] = b"synthetic unexpected source"
    wheel = zipped(contents)
    sdist = tarred(
        {
            f"dscat-0.1.0/{name}": raw
            for name, raw in (source | {"PKG-INFO": METADATA}).items()
        }
    )

    def run(argv: list[str], **options: object) -> Execution:
        del argv
        label = str(options["label"])
        (candidate.assets / "dscat-0.1.0-py3-none-any.whl").write_bytes(wheel)
        (candidate.assets / "dscat-0.1.0.tar.gz").write_bytes(sdist)
        if mutation == "extra":
            (candidate.assets / "unexpected").write_bytes(b"synthetic extra")
        return Execution(label, 0, "d" * 64, "e" * 64, 0.1)

    monkeypatch.setattr(collection, "run_tool", run)
    if mutation != "none":
        with pytest.raises(ValueError, match=r"Build outputs|Wheel source"):
            collection.build_artifacts(candidate, source)
    else:
        actual_wheel, actual_sdist = collection.build_artifacts(candidate, source)
        assert actual_wheel.sha256 == hashlib.sha256(wheel).hexdigest()
        assert actual_sdist.sha256 == hashlib.sha256(sdist).hexdigest()
