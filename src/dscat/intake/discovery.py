# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Deterministic regular-file selection with symlink and overlap refusal."""

import os
import stat
import time
import unicodedata
from pathlib import Path
from typing import Annotated

from pydantic import Field

from dscat.intake.limits import DEFAULT_LIMITS, DiagnosticCollector, IntakeError, fail
from dscat.models.base import StrictModel
from dscat.models.diagnostics import Diagnostic


class FileIdentity(StrictModel):
    """An observed filesystem identity, separate from canonical content."""

    device: int
    inode: int
    size: Annotated[int, Field(ge=0)]
    modified_ns: int


class SourceDescriptor(StrictModel):
    """Private source association retained in process/IPC, never diagnostic output."""

    source_token: Annotated[int, Field(ge=1)]
    path: Path
    identity: FileIdentity


class DiscoveryRequest(StrictModel):
    """Only explicitly selected paths and recursion affect discovery."""

    input: Path
    recursive: bool = False
    output: Path | None = None


class DiscoveryResult(StrictModel):
    """Readable selections and fixed diagnostics, with incomplete scope explicit."""

    sources: list[SourceDescriptor]
    diagnostics: list[Diagnostic]
    selected_count: int
    selection_complete: bool
    has_errors: bool
    ignored_aliases: Annotated[int, Field(ge=0)] = 0


def reject_links(path: Path) -> None:
    """Inspect every existing ancestor before using a resolved path."""
    for component in (*reversed(path.absolute().parents), path.absolute()):
        try:
            attributes = component.lstat()
        except FileNotFoundError:
            continue
        if (
            stat.S_ISLNK(attributes.st_mode)
            or getattr(attributes, "st_file_attributes", 0) & 0x400
        ):
            raise fail(code="UNSAFE_INPUT")


def file_identity(attributes: os.stat_result) -> FileIdentity:
    """Bind size and timestamp checks to a regular physical file."""
    if not stat.S_ISREG(attributes.st_mode):
        raise fail(code="UNSAFE_INPUT")
    return FileIdentity(
        device=attributes.st_dev,
        inode=attributes.st_ino,
        size=attributes.st_size,
        modified_ns=attributes.st_mtime_ns,
    )


def check_destinations(request: DiscoveryRequest) -> None:
    """Refuse ancestor links and input/output overlap before discovery."""
    reject_links(request.input)
    if request.output is not None:
        reject_links(request.output)
        source = request.input.resolve(strict=False)
        destination = request.output.resolve(strict=False)
        if source.is_relative_to(destination) or destination.is_relative_to(source):
            raise fail(code="UNSAFE_INPUT")


def collect_entry(
    entry: os.DirEntry[str],
    request: DiscoveryRequest,
    candidates: list[Path],
    pending: list[Path],
    collector: DiagnosticCollector,
) -> bool:
    """Classify one entry without following links or stopping on read errors."""
    try:
        path = Path(entry.path)
        if entry.is_symlink() and not path.name.startswith("~$"):
            candidates.append(path)
        elif entry.is_dir(follow_symlinks=False):
            if request.recursive:
                pending.append(path)
        elif path.suffix.lower() == ".xlsx" and not path.name.startswith("~$"):
            candidates.append(path)
    except OSError:
        collector.add(fail(code="UNREADABLE_INPUT").diagnostic)
        return False
    if len(candidates) > DEFAULT_LIMITS.files:
        raise fail(code="INPUT_LIMIT", limit="files")
    return True


def walk_directory(
    root: Path,
    request: DiscoveryRequest,
    candidates: list[Path],
    collector: DiagnosticCollector,
) -> bool:
    """Enumerate without following links or retaining irrelevant file entries."""
    pending = [root]
    complete = True
    started = time.monotonic()
    while pending:
        directory = pending.pop()
        try:
            reject_links(directory)
            with os.scandir(directory) as entries:
                for entry in entries:
                    if time.monotonic() - started > DEFAULT_LIMITS.invocation_time:
                        raise fail(code="INPUT_LIMIT", limit="invocation_time")
                    complete &= collect_entry(
                        entry, request, candidates, pending, collector
                    )

        except OSError:
            collector.add(fail(code="UNREADABLE_INPUT").diagnostic)
            complete = False
        except IntakeError as error:
            if error.diagnostic.code == "INPUT_LIMIT":
                raise
            collector.add(error.diagnostic)
            complete = False
    return complete


def collect_candidates(
    request: DiscoveryRequest, candidates: list[Path], collector: DiagnosticCollector
) -> bool:
    """Select an explicit supported regular file or enumerate a directory."""
    root = request.input.absolute()
    attributes = root.lstat()
    if stat.S_ISREG(attributes.st_mode):
        if root.suffix.lower() != ".xlsx" or root.name.startswith("~$"):
            raise fail(code="INVALID_WORKBOOK")
        candidates.append(root)
        return True
    if stat.S_ISDIR(attributes.st_mode):
        return walk_directory(root, request, candidates, collector)
    raise fail(code="UNSAFE_INPUT")


def compile_sources(
    candidates: list[Path], parent: Path, collector: DiagnosticCollector
) -> tuple[list[SourceDescriptor], int]:
    """Assign ordinals after deterministic ordering; deduplicate physical selections."""
    candidates.sort(
        key=lambda path: (
            unicodedata.normalize("NFC", path.relative_to(parent).as_posix()),
            path.as_posix(),
        )
    )
    seen: set[tuple[int, int]] = set()
    sources: list[SourceDescriptor] = []
    aliases = 0
    for ordinal, path in enumerate(candidates, start=1):
        try:
            reject_links(path)
            identity = file_identity(path.lstat())
            physical = identity.device, identity.inode
            if physical not in seen:
                seen.add(physical)
                sources.append(
                    SourceDescriptor(source_token=ordinal, path=path, identity=identity)
                )
            else:
                aliases += 1
        except IntakeError as error:
            collector.add(error.diagnostic.model_copy(update={"source_token": ordinal}))
        except OSError:
            collector.add(
                fail(code="UNREADABLE_INPUT", source_token=ordinal).diagnostic
            )
    return sources, aliases


def discover(request: DiscoveryRequest) -> DiscoveryResult:
    """Select supported regular files without reading workbook content."""
    collector = DiagnosticCollector()
    candidates: list[Path] = []
    complete = True
    abort = False
    try:
        check_destinations(request)
        complete = collect_candidates(request, candidates, collector)
    except IntakeError as error:
        collector.add(error.diagnostic)
        complete = False
        abort = True
    except OSError:
        collector.add(fail(code="UNREADABLE_INPUT").diagnostic)
        complete = False
        abort = True
    parent = (
        request.input.absolute()
        if request.input.is_dir()
        else request.input.absolute().parent
    )
    sources, aliases = (
        ([], 0) if abort else compile_sources(candidates, parent, collector)
    )
    return DiscoveryResult(
        sources=sources,
        diagnostics=collector.items,
        selected_count=len(candidates),
        selection_complete=complete,
        has_errors=collector.has_errors,
        ignored_aliases=aliases,
    )
