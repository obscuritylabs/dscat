# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Transaction failures preserve the accepted pointer and prior generation bytes."""

import errno
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from dscat.intake.limits import IntakeError
from dscat.storage import publication
from dscat.storage.flatfiles import load_snapshot, save_snapshot

if TYPE_CHECKING:
    from dscat.storage.models import Snapshot
from tests.test_storage import catalog


def inventory(root: Path) -> dict[str, bytes]:
    """Capture only immutable accepted artifacts plus the pointer for comparison."""
    snapshot = load_snapshot(root)
    generation = root / "generations" / snapshot.generation
    return {
        "CURRENT": (root / "CURRENT").read_bytes(),
        **{
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in generation.rglob("*")
            if path.is_file()
        },
    }


def test_replace_omission_history_determinism_and_refusal(tmp_path: Path) -> None:
    """Replace changes only CURRENT/new generation; omission never edits history."""
    root = tmp_path / "bundle"
    first = save_snapshot(root, catalog("a", "b"))
    original = inventory(root)
    before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
    with pytest.raises(IntakeError, match="PUBLICATION_FAILURE"):
        save_snapshot(root, first.catalog)
    assert before == sorted(
        path.relative_to(root).as_posix() for path in root.rglob("*")
    )
    assert inventory(root) == original
    repeated = save_snapshot(root, first.catalog, replace=True)
    assert repeated == first
    assert inventory(root) == original
    second = save_snapshot(root, catalog("a"), replace=True)
    assert second.generation != first.generation
    assert load_snapshot(root).catalog == catalog("a")
    assert all(
        (root / relative).read_bytes() == raw
        for relative, raw in original.items()
        if relative != "CURRENT"
    )
    assert (root / "generations" / first.generation).is_dir()
    # Going back to a previously retained immutable generation is deterministic.
    assert (
        save_snapshot(root, first.catalog, replace=True).generation == first.generation
    )


@pytest.mark.parametrize(
    "phase",
    [
        "serialize",
        "mkdir",
        "write",
        "flush",
        "reload",
        "rename",
        "pointer_write",
        "pointer_switch",
    ],
)
@pytest.mark.parametrize("error_number", [errno.EACCES, errno.ENOSPC, errno.EXDEV])
def test_each_precommit_failure_preserves_previous_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str, error_number: int
) -> None:
    """Permission, disk-full and cross-device failures cannot select partial bytes."""
    root = tmp_path / "bundle"
    first = save_snapshot(root, catalog("a"))
    original = inventory(root)

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError(error_number, "synthetic private error")

    if phase in {"serialize", "write", "flush", "reload"}:
        target = {
            "serialize": "prepare",
            "write": "write_file",
            "flush": "flush_directory",
            "reload": "read_generation",
        }[phase]
        monkeypatch.setattr(publication, target, refuse)
    elif phase in {"mkdir", "rename", "pointer_switch"}:
        method = "replace" if phase == "pointer_switch" else phase
        monkeypatch.setattr(Path, method, refuse)
    else:
        write = publication.write_file

        def fail_pointer(path: Path, raw: bytes) -> None:
            if path.name.startswith(".pointer-"):
                refuse()
            write(path, raw)

        monkeypatch.setattr(publication, "write_file", fail_pointer)
    with pytest.raises(OSError, match="synthetic"):
        save_snapshot(root, catalog("b"), replace=True)
    assert inventory(root) == original
    assert load_snapshot(root).generation == first.generation
    assert not (root / ".writer.lock").exists()
    # Explicit retry may leave unreferenced stages; it never needs automatic deletion.
    monkeypatch.undo()
    assert save_snapshot(root, catalog("b"), replace=True).catalog == catalog("b")
    assert (root / "generations" / first.generation).exists()


def test_interruption_and_abandoned_stage_are_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SIGINT-style interruption retains old CURRENT and permits explicit retry."""
    root = tmp_path / "bundle"
    save_snapshot(root, catalog("a"))
    original = inventory(root)

    def interrupted(*_args: object, **_kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(Path, "replace", interrupted)
    with pytest.raises(KeyboardInterrupt):
        save_snapshot(root, catalog("b"), replace=True)
    assert inventory(root) == original
    assert load_snapshot(root).orphan_count == 1
    assert load_snapshot(root).retained_generation_count == 1
    monkeypatch.undo()
    save_snapshot(root, catalog("b"), replace=True)
    assert load_snapshot(root).orphan_count == 1


def test_lock_contention_stale_lock_and_explicit_recovery(tmp_path: Path) -> None:
    """All writers respect locks; stale locks need explicit operator recovery."""
    root = tmp_path / "bundle"
    save_snapshot(root, catalog("a"))
    original = inventory(root)
    with publication.writer_lock(root):
        with pytest.raises(FileExistsError), publication.writer_lock(root):
            pytest.fail("Second writer must not enter.")
        with pytest.raises(IntakeError):
            save_snapshot(root, catalog("b"), replace=True)
    stale = root / ".writer.lock"
    stale.write_bytes(b"synthetic abandoned writer")
    with pytest.raises(IntakeError):
        save_snapshot(root, catalog("b"), replace=True)
    assert stale.read_bytes() == b"synthetic abandoned writer"
    assert inventory(root) == original
    stale.unlink()  # Test operator explicitly verifies exclusive access and recovers.
    save_snapshot(root, catalog("b"), replace=True)


def test_initial_failure_has_no_accepted_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failed initial creation cannot be silently adopted as a valid bundle."""
    root = tmp_path / "bundle"

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError(errno.ENOSPC, "synthetic full volume")

    monkeypatch.setattr(publication, "write_file", refuse)
    with pytest.raises(OSError, match="synthetic"):
        save_snapshot(root, catalog("a"))
    assert not (root / "CURRENT").exists()
    assert not (root / ".writer.lock").exists()
    monkeypatch.undo()
    with pytest.raises(IntakeError):
        save_snapshot(root, catalog("a"))
    with pytest.raises(FileNotFoundError):
        save_snapshot(root, catalog("a"), replace=True)


def test_unknown_existing_directory_is_not_adopted(tmp_path: Path) -> None:
    """An arbitrary existing destination is never treated as an empty new bundle."""
    root = tmp_path / "bundle"
    root.mkdir()
    unrelated = root / "unrelated.json"
    unrelated.write_bytes(b"preserved")
    with pytest.raises(IntakeError):
        save_snapshot(root, catalog())
    with pytest.raises(FileNotFoundError):
        save_snapshot(root, catalog(), replace=True)
    assert unrelated.read_bytes() == b"preserved"
    assert sorted(path.name for path in root.iterdir()) == ["unrelated.json"]


def test_lock_identity_replacement_is_never_removed(tmp_path: Path) -> None:
    """Writer cleanup does not unlink a lock replaced by an independent actor."""
    root = tmp_path / "bundle"
    root.mkdir()
    with pytest.raises(IntakeError), publication.writer_lock(root):
        (root / ".writer.lock").write_bytes(b"other")
    assert (root / ".writer.lock").read_bytes() == b"other"


def test_pointer_changed_under_writer_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A noncooperating modification is detected before replacing CURRENT."""
    root = tmp_path / "bundle"
    save_snapshot(root, catalog("a"))
    stage = publication.stage_generation

    def changed(root_path: Path, artifacts: dict[str, bytes], digest: str) -> Snapshot:
        result = stage(root_path, artifacts, digest)
        (root / "CURRENT").write_bytes(b"b" * 64 + b"\n")
        return result

    monkeypatch.setattr(publication, "stage_generation", changed)
    with pytest.raises(IntakeError):
        save_snapshot(root, catalog("b"), replace=True)
    assert (root / "CURRENT").read_bytes() == b"b" * 64 + b"\n"


def test_reloaded_generation_identity_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A wrong reloaded typed snapshot cannot replace an existing generation."""
    root = tmp_path / "bundle"
    first = save_snapshot(root, catalog("a"))
    original = inventory(root)
    read = publication.read_generation

    def mismatch(path: Path, digest: str) -> Snapshot:
        result = read(path, digest)
        return (
            result.model_copy(update={"catalog": catalog("other")})
            if path.parent.name == "generations"
            else result
        )

    monkeypatch.setattr(publication, "read_generation", mismatch)
    with pytest.raises(IntakeError, match="PUBLICATION_FAILURE"):
        save_snapshot(root, first.catalog, replace=True)
    assert inventory(root) == original


@pytest.mark.parametrize("boundary", ["before_stage", "root_identity"])
def test_writer_rechecks_pointer_and_root_before_switch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    """Observed root/pointer replacement aborts instead of overwriting new state."""
    root = tmp_path / "bundle"
    save_snapshot(root, catalog("a"))
    if boundary == "before_stage":
        original_read = publication.read_file

        def replaced(path: Path, maximum: int) -> bytes:
            raw = original_read(path, maximum)
            return b"b" * 64 + b"\n" if path.name == "CURRENT" else raw

        monkeypatch.setattr(publication, "read_file", replaced)
    else:
        stage = publication.stage_generation
        original_stat = Path.stat

        def replaced_root(
            path: Path, *, follow_symlinks: bool = True
        ) -> os.stat_result:
            attributes = original_stat(path, follow_symlinks=follow_symlinks)
            if path == root:
                values = list(attributes)
                values[1] += 1
                return os.stat_result(values)
            return attributes

        def changed(
            root_path: Path, artifacts: dict[str, bytes], digest: str
        ) -> Snapshot:
            result = stage(root_path, artifacts, digest)
            monkeypatch.setattr(Path, "stat", replaced_root)
            return result

        monkeypatch.setattr(publication, "stage_generation", changed)
    previous = (root / "CURRENT").read_bytes()
    with pytest.raises(IntakeError, match="PUBLICATION_FAILURE"):
        save_snapshot(root, catalog("b"), replace=True)
    assert (root / "CURRENT").read_bytes() == previous
