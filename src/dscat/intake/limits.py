# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Fixed production ceilings, safe failures and bounded accounting."""

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated

from pydantic import Field

from dscat.models.base import StrictModel
from dscat.models.diagnostics import Diagnostic

if TYPE_CHECKING:
    from collections.abc import Callable

    from dscat.models.diagnostics import Code, Limit

CHUNK_BYTES = 65536
MAX_REQUEST_BYTES = 32 * 1024**2
MAX_REPLY_BYTES = 32 * 1024**2
MESSAGE_KEYS = {
    "INVALID_CONFIGURATION": "check_configuration",
    "INVALID_INVOCATION": "check_configuration",
    "INPUT_LIMIT": "review_scope",
    "UNEXAMINED_INPUT": "review_scope",
    "DIAGNOSTICS_TRUNCATED": "review_scope",
    "UNREADABLE_INPUT": "retry_operation",
    "WORKER_FAILURE": "retry_operation",
    "RESOURCE_GUARD_UNAVAILABLE": "retry_operation",
    "IO_FAILURE": "retry_operation",
    "PUBLICATION_FAILURE": "retry_operation",
    "INTERNAL_FAILURE": "retry_operation",
    "INTERRUPTED": "retry_operation",
}


class Limits(StrictModel):
    """Internal test seams do not create CLI or configuration overrides."""

    files: int = 1000
    compressed: int = 32 * 1024**2
    members: int = 4096
    expanded: int = 128 * 1024**2
    ratio: int = 100
    xml: int = 16 * 1024**2
    depth: int = 64
    sheets: int = 32
    cells: int = 200000
    text: int = 32767
    invocation_expanded: int = 256 * 1024**2
    datasets: int = 100000
    snapshot: int = 256 * 1024**2
    diagnostics: int = 10000
    workbook_time: float = 30.0
    invocation_time: float = 300.0
    memory: int = 512 * 1024**2


DEFAULT_LIMITS = Limits()


class IntakeError(Exception):
    """An expected fixed-code failure, without raw values or exception messages."""

    def __init__(
        self, diagnostic: Diagnostic, *, expanded_upper_bound: int | None = None
    ) -> None:
        """Retain only the validated diagnostic for safe rendering."""
        self.diagnostic = diagnostic
        if expanded_upper_bound is not None and expanded_upper_bound < 0:
            msg = "Expansion reservation cannot be negative."
            raise ValueError(msg)
        self.expanded_upper_bound = expanded_upper_bound
        super().__init__(diagnostic.code)


def fail(
    *,
    code: Code,
    source_token: int | None = None,
    limit: Limit | None = None,
    expanded_upper_bound: int | None = None,
) -> IntakeError:
    """Construct an error without reflecting arbitrary untrusted content."""
    fields: dict[str, object] = {
        "code": code,
        "severity": "error",
        "message_key": MESSAGE_KEYS.get(code, "correct_metadata"),
    }
    if source_token is not None:
        fields["source_token"] = source_token
    if limit is not None:
        fields["limit"] = limit
    return IntakeError(
        Diagnostic.model_validate(fields), expanded_upper_bound=expanded_upper_bound
    )


class ArchiveStatistics(StrictModel):
    """Counts describe observed processing, including work before a safe failure."""

    compressed_bytes: Annotated[int, Field(ge=0)] = 0
    expanded_bytes: Annotated[int, Field(ge=0)] = 0
    members: Annotated[int, Field(ge=0)] = 0
    worksheets: Annotated[int, Field(ge=0)] = 0
    cells: Annotated[int, Field(ge=0)] = 0
    max_depth: Annotated[int, Field(ge=0)] = 0
    max_text: Annotated[int, Field(ge=0)] = 0


@dataclass
class Budget:
    """Mutable per-workbook counters remain internal to a bounded worker."""

    limits: Limits = DEFAULT_LIMITS
    clock: Callable[[], float] = time.monotonic
    remaining_expanded: int = DEFAULT_LIMITS.invocation_expanded
    expanded: int = 0
    compressed: int = 0
    members: int = 0
    worksheets: int = 0
    cells: int = 0
    declared_sheets: int = 0
    max_depth: int = 0
    max_text: int = 0
    started: float = field(init=False)

    def __post_init__(self) -> None:
        """Start the monotonic deadline before preflight."""
        self.started = self.clock()

    def check_time(self) -> None:
        """Never equate elapsed-time exhaustion with validated content."""
        if self.clock() - self.started > self.limits.workbook_time:
            raise fail(code="INPUT_LIMIT", limit="workbook_time")

    def check(self, name: Limit, value: int, maximum: int) -> None:
        """Apply inclusive count/byte/depth ceilings with a fixed limit identifier."""
        self.check_time()
        if value > maximum:
            raise fail(code="INPUT_LIMIT", limit=name)

    def expand(self, count: int) -> None:
        """Count actual emitted decompression bytes before retaining them."""
        self.expanded += count
        self.check("expanded", self.expanded, self.limits.expanded)
        self.check("expanded", self.expanded, self.remaining_expanded)

    def statistics(self) -> ArchiveStatistics:
        """Return observed counts without exposing input names or content."""
        return ArchiveStatistics(
            compressed_bytes=self.compressed,
            expanded_bytes=self.expanded,
            members=self.members,
            worksheets=self.worksheets,
            cells=self.cells,
            max_depth=self.max_depth,
            max_text=self.max_text,
        )


@dataclass
class DiagnosticCollector:
    """Keep error state even when diagnostics must be truncated."""

    maximum: int = DEFAULT_LIMITS.diagnostics
    items: list[Diagnostic] = field(default_factory=list)
    suppressed: int = 0
    has_errors: bool = False

    def add(self, diagnostic: Diagnostic) -> None:
        """Bound retained diagnostics and preserve a fixed truncation summary."""
        self.has_errors |= diagnostic.severity == "error"
        if len(self.items) < self.maximum:
            self.items.append(diagnostic)
        elif not self.suppressed:
            self.items[-1] = Diagnostic(
                code="DIAGNOSTICS_TRUNCATED",
                severity="warning",
                message_key="review_scope",
                check_state="unperformed",
            )
            self.suppressed = 2
        else:
            self.suppressed += 1
