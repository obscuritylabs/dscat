# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Selection, path, source identity and diagnostic-accounting acceptance."""

import os
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from dscat.intake.discovery import (
    DiscoveryRequest,
    collect_entry,
    discover,
    file_identity,
    walk_directory,
)
from dscat.intake.limits import (
    ArchiveStatistics,
    DiagnosticCollector,
    IntakeError,
    fail,
)
from dscat.models.diagnostics import Diagnostic

if TYPE_CHECKING:
    from collections.abc import Iterator


FILE_LIMIT = 1000


def test_file_directory_sorting_recursion_and_lock_ignore(tmp_path: Path) -> None:
    """Select metadata with explicit recursion and stable relative order."""
    for name in ("b.XLSX", "a.xlsx", "~$locked.xlsx", "other.txt"):
        (tmp_path / name).write_bytes(b"Not parsed during discovery")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "c.xlsx").write_bytes(b"Not parsed")
    one = discover(DiscoveryRequest(input=tmp_path / "a.xlsx"))
    assert len(one.sources) == 1
    assert one.sources[0].source_token == 1
    flat = discover(DiscoveryRequest(input=tmp_path))
    assert [s.path.name for s in flat.sources] == ["a.xlsx", "b.XLSX"]
    assert not flat.has_errors
    recursive = discover(DiscoveryRequest(input=tmp_path, recursive=True))
    assert [s.path.name for s in recursive.sources] == ["a.xlsx", "b.XLSX", "c.xlsx"]
    assert recursive.selection_complete
    assert discover(DiscoveryRequest(input=tmp_path / "other.txt")).has_errors
    assert discover(DiscoveryRequest(input=tmp_path / "~$locked.xlsx")).has_errors


def test_empty_directory_and_missing_input(tmp_path: Path) -> None:
    """Keep empty selection separate from inaccessible explicit inputs."""
    empty = discover(DiscoveryRequest(input=tmp_path))
    assert empty.sources == []
    assert empty.selection_complete
    missing = discover(DiscoveryRequest(input=tmp_path / "missing.xlsx"))
    assert missing.sources == []
    assert missing.has_errors
    assert not missing.selection_complete
    assert missing.diagnostics[0].code == "UNREADABLE_INPUT"


def test_symlinks_loops_and_ancestor_links_are_refused(tmp_path: Path) -> None:
    """No directory link is traversed and no source link becomes content input."""
    real = tmp_path / "real"
    real.mkdir()
    (real / "input.xlsx").write_bytes(b"x")
    (tmp_path / "linked.xlsx").symlink_to(real / "input.xlsx")
    (tmp_path / "loop").symlink_to(tmp_path, target_is_directory=True)
    (tmp_path / "~$ignored.xlsx").symlink_to(real / "input.xlsx")
    direct = discover(DiscoveryRequest(input=tmp_path / "linked.xlsx"))
    assert direct.has_errors
    assert not direct.sources
    linked_directory = tmp_path / "alias"
    linked_directory.symlink_to(real, target_is_directory=True)
    assert discover(DiscoveryRequest(input=linked_directory / "input.xlsx")).has_errors
    tree = discover(DiscoveryRequest(input=tmp_path, recursive=True))
    assert [s.path.name for s in tree.sources] == ["input.xlsx"]
    assert tree.has_errors
    assert len(tree.diagnostics) == len(["alias", "linked.xlsx", "loop"])


def test_overlaps_and_destination_links(tmp_path: Path) -> None:
    """Both containment directions and destination ancestor links are refused."""
    source = tmp_path / "input"
    source.mkdir()
    (source / "one.xlsx").write_bytes(b"x")
    for output in (source, source / "output", tmp_path):
        result = discover(DiscoveryRequest(input=source, output=output))
        assert result.has_errors
        assert result.sources == []
    output = tmp_path / "output"
    assert not discover(DiscoveryRequest(input=source, output=output)).has_errors
    output.symlink_to(source, target_is_directory=True)
    assert discover(DiscoveryRequest(input=source, output=output / "nested")).has_errors


def test_hardlinked_physical_selection_deduplicates(tmp_path: Path) -> None:
    """Aliases are imported once and do not become falsely unexamined sources."""
    first = tmp_path / "a.xlsx"
    first.write_bytes(b"x")
    os.link(first, tmp_path / "b.xlsx")
    result = discover(DiscoveryRequest(input=tmp_path))
    assert len(result.sources) == 1
    assert result.ignored_aliases == 1
    assert result.selected_count == len(result.sources) + result.ignored_aliases


def test_selected_file_count_boundary(tmp_path: Path) -> None:
    """Exactly 1,000 selected paths are allowed; excess selection is incomplete."""
    for index in range(1000):
        (tmp_path / f"input-{index:04d}.xlsx").touch()
    allowed = discover(DiscoveryRequest(input=tmp_path))
    assert not allowed.has_errors
    assert len(allowed.sources) == FILE_LIMIT
    (tmp_path / "one-more.xlsx").touch()
    refused = discover(DiscoveryRequest(input=tmp_path))
    assert refused.has_errors
    assert refused.sources == []
    assert refused.diagnostics[0].limit == "files"
    assert not refused.selection_complete


def test_nonregular_explicit_file(tmp_path: Path) -> None:
    """A FIFO cannot block discovery or become an eligible regular source."""
    fifo = tmp_path / "pipe.xlsx"
    os.mkfifo(fifo)
    result = discover(DiscoveryRequest(input=fifo))
    assert result.diagnostics[0].code == "UNSAFE_INPUT"
    with pytest.raises(IntakeError, match="UNSAFE_INPUT"):
        file_identity(tmp_path.stat())


def test_lstat_failure_continues_other_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Report raced-away files while continuing independent sources."""
    bad = tmp_path / "a.xlsx"
    good = tmp_path / "b.xlsx"
    bad.touch()
    good.touch()
    original = Path.lstat
    calls = [0]

    def changed(path: Path) -> os.stat_result:
        if path == bad:
            calls[0] += 1
            if calls[0] > 1:
                msg = "Synthetic source disappeared"
                raise FileNotFoundError(msg)
        return original(path)

    monkeypatch.setattr(Path, "lstat", changed)
    result = discover(DiscoveryRequest(input=tmp_path))
    assert [s.path for s in result.sources] == [good]
    assert result.diagnostics[0].source_token == 1
    assert result.has_errors


def test_discovery_deadline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An expired invocation stops selection without claiming examined content."""
    (tmp_path / "one.xlsx").touch()
    ticks = iter([0.0, 301.0])
    monkeypatch.setattr("dscat.intake.discovery.time.monotonic", lambda: next(ticks))
    result = discover(DiscoveryRequest(input=tmp_path))
    assert result.diagnostics[0].limit == "invocation_time"
    assert result.sources == []


def test_listing_failure_and_entry_failure_are_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unreadable listings are separate from validated empty directories."""

    def denied(_path: object) -> Iterator[os.DirEntry[str]]:
        msg = "Synthetic denied directory"
        raise PermissionError(msg)

    monkeypatch.setattr("dscat.intake.discovery.os.scandir", denied)
    result = discover(DiscoveryRequest(input=tmp_path))
    assert not result.selection_complete
    assert result.diagnostics[0].code == "UNREADABLE_INPUT"


def test_diagnostic_cap_keeps_error_state() -> None:
    """Replacing the last slot with a truncation notice cannot clear invalidity."""
    collector = DiagnosticCollector(maximum=2)
    collector.add(
        Diagnostic(
            code="DUPLICATE_IDENTICAL", severity="info", message_key="review_scope"
        )
    )
    collector.add(fail(code="INVALID_METADATA").diagnostic)
    collector.add(
        Diagnostic(
            code="DUPLICATE_IDENTICAL", severity="info", message_key="review_scope"
        )
    )
    collector.add(fail(code="INVALID_METADATA").diagnostic)
    assert collector.has_errors
    assert collector.suppressed == len([1, 2, 3])
    assert len(collector.items) == len([1, 2])
    assert collector.items[-1].code == "DIAGNOSTICS_TRUNCATED"
    assert collector.items[-1].check_state == "unperformed"
    with pytest.raises(ValidationError):
        ArchiveStatistics(expanded_bytes=-1)


def test_entry_metadata_failure_is_not_empty_selection(tmp_path: Path) -> None:
    """An entry classification error is retained as incomplete discovery."""
    entry = Mock(spec=os.DirEntry)
    entry.path = str(tmp_path / "one.xlsx")
    entry.is_symlink.side_effect = OSError("synthetic entry metadata refusal")
    collector = DiagnosticCollector()
    assert not collect_entry(entry, DiscoveryRequest(input=tmp_path), [], [], collector)
    assert collector.has_errors


def test_directory_link_race_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A directory becoming a link before enumeration is not followed."""
    collector = DiagnosticCollector()

    def changed(_path: Path) -> None:
        raise fail(code="UNSAFE_INPUT")

    monkeypatch.setattr("dscat.intake.discovery.reject_links", changed)
    assert not walk_directory(tmp_path, DiscoveryRequest(input=tmp_path), [], collector)
    assert collector.items[0].code == "UNSAFE_INPUT"


def test_actual_diagnostic_limit_retains_invalidity() -> None:
    """Exactly 10,000 diagnostics fit; overflow replaces a slot with a safe notice."""
    maximum = 10000
    collector = DiagnosticCollector()
    diagnostic = fail(code="INVALID_METADATA").diagnostic
    for _index in range(maximum):
        collector.add(diagnostic)
    assert len(collector.items) == maximum
    assert collector.suppressed == 0
    collector.add(diagnostic)
    assert len(collector.items) == maximum
    assert collector.items[-1].code == "DIAGNOSTICS_TRUNCATED"
    assert collector.has_errors
