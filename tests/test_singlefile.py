# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Single-file staging refuses races and preserves accepted bytes on failure."""

import errno
from typing import TYPE_CHECKING

import pytest

from dscat.intake.limits import IntakeError, fail
from dscat.storage import singlefile

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("replace", [False, True])
def test_complete_publication_and_explicit_replacement(
    tmp_path: Path, *, replace: bool
) -> None:
    """Publish complete bytes and remove owned temporary files."""
    path = tmp_path / "artifact"
    if replace:
        path.write_bytes(b"previous")
    singlefile.publish_file(path, b"complete", replace=replace)
    assert path.read_bytes() == b"complete"
    assert list(tmp_path.iterdir()) == [path]
    with pytest.raises(IntakeError, match="PUBLICATION_FAILURE"):
        singlefile.publish_file(path, b"unauthorized")
    assert path.read_bytes() == b"complete"


@pytest.mark.parametrize("kind", ["link", "directory", "parent_link"])
def test_unsafe_single_file_destinations(tmp_path: Path, kind: str) -> None:
    """Refuse links and directories even with explicit replacement."""
    path = tmp_path / "output"
    if kind == "directory":
        path.mkdir()
    else:
        target = tmp_path / "target"
        if kind == "parent_link":
            target.mkdir()
        else:
            target.write_bytes(b"prior")
        path.symlink_to(target, target_is_directory=kind == "parent_link")
        if kind == "parent_link":
            path /= "output"
    with pytest.raises(IntakeError):
        singlefile.publish_file(path, b"new", replace=True)


@pytest.mark.parametrize("replace", [False, True])
def test_staging_write_failure_preserves_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, replace: bool
) -> None:
    """Keep a partially written stage from replacing accepted content."""
    path = tmp_path / "output"
    if replace:
        path.write_bytes(b"prior")

    def fail_write(stage: Path, _raw: bytes) -> None:
        stage.write_bytes(b"incomplete")
        raise OSError(errno.ENOSPC, "Synthetic disk failure")

    monkeypatch.setattr(singlefile, "write_file", fail_write)
    with pytest.raises(OSError, match="Synthetic disk failure"):
        singlefile.publish_file(path, b"complete", replace=replace)
    assert path.read_bytes() == b"prior" if replace else not path.exists()
    assert not list(tmp_path.glob(".stage-*"))


def test_concurrent_creation_cannot_be_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Preserve concurrent destination creation after both prechecks."""
    path = tmp_path / "output"
    original = singlefile.os.link

    def racing_link(source: Path, destination: Path, *, follow_symlinks: bool) -> None:
        destination.write_bytes(b"other writer")
        original(source, destination, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(singlefile.os, "link", racing_link)
    with pytest.raises(FileExistsError):
        singlefile.publish_file(path, b"complete")
    assert path.read_bytes() == b"other writer"
    assert list(tmp_path.iterdir()) == [path]


def test_disjoint_refuses_equal_and_ancestor_paths(tmp_path: Path) -> None:
    """Overlap is refused in either direction, including paths with dot components."""
    for paths in (
        [tmp_path, tmp_path],
        [tmp_path, tmp_path / "child"],
        [tmp_path / "child", tmp_path],
    ):
        with pytest.raises(IntakeError, match="UNSAFE_INPUT"):
            singlefile.check_disjoint(paths)
    singlefile.check_disjoint([tmp_path / "one", tmp_path / "two"])


def test_nonlocal_single_file_refusal_preserves_existing_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unknown/network filesystem refusal happens before any stage or replacement."""
    output = tmp_path / "output"
    output.write_bytes(b"accepted")

    def unsupported(path: Path) -> None:
        assert path == tmp_path
        raise fail(code="PUBLICATION_FAILURE")

    monkeypatch.setattr(singlefile, "require_local", unsupported)
    with pytest.raises(IntakeError, match="PUBLICATION_FAILURE"):
        singlefile.publish_file(output, b"new", replace=True)
    assert output.read_bytes() == b"accepted"
    assert list(tmp_path.iterdir()) == [output]
