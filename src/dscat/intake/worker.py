# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Serial bounded coordinator/workbook processes with closed private JSON IPC."""

import os
import signal
import subprocess
import sys
import threading
import time
from contextlib import suppress
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated, Literal, Self

from pydantic import Field, TypeAdapter, ValidationError, model_validator

from dscat.intake.archive import read_archive
from dscat.intake.discovery import (
    DiscoveryRequest,
    SourceDescriptor,
    discover,
    file_identity,
    reject_links,
)
from dscat.intake.limits import (
    CHUNK_BYTES,
    DEFAULT_LIMITS,
    MAX_REPLY_BYTES,
    MAX_REQUEST_BYTES,
    ArchiveStatistics,
    Budget,
    DiagnosticCollector,
    IntakeError,
    fail,
)
from dscat.intake.normalize import LocatedRecord, normalize_batch
from dscat.json_guard import check_json
from dscat.models.base import StrictModel
from dscat.models.catalog import Catalog
from dscat.models.configuration import AssessmentConfiguration
from dscat.models.diagnostics import (
    Diagnostic,
    ExitCode,
    OutputReceipt,
    ValidationAssessment,
)
from dscat.platform import install_guard
from dscat.serialization import canonical_bytes
from dscat.storage.flatfiles import save_snapshot
from dscat.validation import validate_catalog
from dscat.workbook.parse import parse_workbook

if TYPE_CHECKING:
    from types import FrameType


class CoordinatorRequest(StrictModel):
    """Explicit private request to one bounded discovery/coordinator process."""

    schema_version: Literal["1.0"]
    role: Literal["coordinator"]
    discovery: DiscoveryRequest
    replace: bool = False
    assessment: AssessmentConfiguration = Field(default_factory=AssessmentConfiguration)


class ArchiveRequest(StrictModel):
    """One source and remaining invocation budget, supplied only by the coordinator."""

    schema_version: Literal["1.0"]
    role: Literal["archive"]
    source: SourceDescriptor
    remaining_expanded: Annotated[int, Field(ge=0, le=256 * 1024**2)]


REQUESTS = TypeAdapter(
    Annotated[CoordinatorRequest | ArchiveRequest, Field(discriminator="role")]
)


class ArchiveOutcome(StrictModel):
    """Archive safety is distinct from later semantic intake validity."""

    source_token: Annotated[int, Field(ge=1)]
    archive_state: Literal["safe", "rejected", "unexamined"]
    statistics: ArchiveStatistics
    records: list[LocatedRecord] = Field(default_factory=list, max_length=100000)
    diagnostics: list[Diagnostic] = Field(
        default_factory=list, max_length=DEFAULT_LIMITS.diagnostics
    )


def outcome_failed(outcome: ArchiveOutcome) -> bool:
    """Keep explicit failure diagnostics independent of the archive safety state."""
    return outcome.archive_state != "safe" or any(
        item.severity == "error" for item in outcome.diagnostics
    )


class WorkerReply(StrictModel):
    """Private typed facts and fixed diagnostics; never render this IPC publicly."""

    schema_version: Literal["1.0"]
    role: Literal["coordinator", "archive", "unassigned"]
    outcomes: list[ArchiveOutcome] = Field(default_factory=list, max_length=1000)
    diagnostics: list[Diagnostic] = Field(default_factory=list, max_length=10000)
    has_errors: bool
    failure_exit: ExitCode = 0
    selection_complete: bool
    unexamined_sources: Annotated[int, Field(ge=0)] = 0
    receipt: OutputReceipt | None = None
    catalog: Catalog | None = None
    assessment: ValidationAssessment | None = None

    @model_validator(mode="after")
    def truthful_status(self) -> Self:
        """Reject false success for errors, incomplete scope or unexamined sources."""
        retained = len(self.diagnostics) + sum(
            len(outcome.diagnostics) for outcome in self.outcomes
        )
        if retained > DEFAULT_LIMITS.diagnostics:
            msg = "Worker result exceeds the invocation diagnostic limit."
            raise ValueError(msg)
        if self.failure_exit != 0 and not self.has_errors:
            msg = "Failure status cannot claim an error-free result."
            raise ValueError(msg)
        incomplete = not self.selection_complete or self.unexamined_sources > 0
        failed = any(item.severity == "error" for item in self.diagnostics) or any(
            outcome_failed(item) for item in self.outcomes
        )
        if not self.has_errors and (incomplete or failed):
            msg = "Worker result cannot claim success for incomplete or failed work."
            raise ValueError(msg)
        if (self.role == "unassigned" and (not self.has_errors or self.outcomes)) or (
            self.role == "archive" and len(self.outcomes) != 1
        ):
            msg = "Worker result does not match its protocol role."
            raise ValueError(msg)
        self.semantic_status()
        return self

    def semantic_status(self) -> None:
        """Require validated catalog facts and assessment for coordinator success."""
        if self.receipt is not None and (self.has_errors or self.catalog is None):
            msg = "Published receipt requires a complete valid catalog."
            raise ValueError(msg)
        present = self.catalog is not None and self.assessment is not None
        valid = self.assessment is not None and self.assessment.validity == "valid"
        if (
            self.role == "coordinator"
            and not self.has_errors
            and not (present and valid)
        ):
            msg = "Successful coordinator requires valid canonical results."
            raise ValueError(msg)
        if self.catalog is not None and (self.role != "coordinator" or not valid):
            msg = "Catalog facts require a valid coordinator assessment."
            raise ValueError(msg)
        if (
            self.assessment is not None
            and self.assessment.validity == "invalid"
            and not self.has_errors
        ):
            msg = "Invalid intake cannot claim an error-free result."
            raise ValueError(msg)


def read_source(source: SourceDescriptor, budget: Budget) -> bytes:
    """Refuse links, changed/nonregular files and excess bytes before parsing."""
    reject_links(source.path)
    before = file_identity(source.path.lstat())
    if before != source.identity:
        raise fail(code="UNSAFE_INPUT")
    budget.check("compressed", before.size, budget.limits.compressed)
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor = os.open(source.path, flags)
    data = bytearray()
    with os.fdopen(descriptor, "rb") as stream:
        if file_identity(os.fstat(stream.fileno())) != before:
            raise fail(code="UNSAFE_INPUT")
        while chunk := stream.read(CHUNK_BYTES):
            budget.compressed += len(chunk)
            budget.check("compressed", budget.compressed, budget.limits.compressed)
            data.extend(chunk)
        budget.check_time()
        if (
            file_identity(os.fstat(stream.fileno())) != before
            or file_identity(source.path.lstat()) != before
        ):
            raise fail(code="UNSAFE_INPUT")
    return bytes(data)


def inspect_archive(request: ArchiveRequest) -> WorkerReply:
    """Read and inspect exactly one file inside an already guarded process."""
    budget = Budget(remaining_expanded=request.remaining_expanded)
    diagnostics: list[Diagnostic] = []
    state = "safe"
    records: list[LocatedRecord] = []
    semantic_errors = False
    try:
        archive = read_archive(read_source(request.source, budget), budget)
        semantic_budget = Budget()
        semantic_budget.started = budget.started
        batch = normalize_batch(
            parse_workbook(archive, request.source.source_token, semantic_budget)
        )
        records = batch.records
        diagnostics.extend(batch.diagnostics)
        semantic_errors = batch.has_errors
    except IntakeError as error:
        diagnostics.append(
            error.diagnostic.model_copy(
                update={"source_token": request.source.source_token}
            )
        )
        state = "rejected"
    except OSError:
        diagnostics.append(
            fail(
                code="UNREADABLE_INPUT", source_token=request.source.source_token
            ).diagnostic
        )
        state = "unexamined"
    except MemoryError:
        diagnostics.append(
            fail(
                code="INPUT_LIMIT",
                source_token=request.source.source_token,
                limit="memory",
            ).diagnostic
        )
        state = "unexamined"
    outcome = ArchiveOutcome.model_validate(
        {
            "source_token": request.source.source_token,
            "archive_state": state,
            "statistics": budget.statistics(),
            "records": records,
            "diagnostics": diagnostics,
        }
    )
    return WorkerReply(
        schema_version="1.0",
        role="archive",
        outcomes=[outcome],
        has_errors=semantic_errors
        or any(item.severity == "error" for item in diagnostics),
        selection_complete=True,
        unexamined_sources=1 if state == "unexamined" else 0,
    )


def stop_process(process: subprocess.Popen[bytes], *, coordinator: bool) -> None:
    """Give a coordinator time to reap its worker, then terminate the complete group."""
    if process.poll() is not None:
        return
    if coordinator:
        if os.name == "posix":
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        else:
            return
    try:
        if coordinator and os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass
    process.wait(timeout=2)


@dataclass
class PipeReader:
    """Retain a bounded child response; never retain its stderr or exception text."""

    process: subprocess.Popen[bytes]
    coordinator: bool
    content: bytearray = field(default_factory=bytearray)
    overflow: bool = False
    failed: bool = False
    memory_failure: bool = False
    complete: bool = False

    def read(self) -> None:
        """Drain stdout concurrently to avoid pipe deadlock while enforcing its cap."""
        stream = self.process.stdout
        if stream is None:
            self.failed = True
            return
        try:
            while chunk := stream.read(CHUNK_BYTES):
                if len(self.content) + len(chunk) > MAX_REPLY_BYTES:
                    self.overflow = True
                    stop_process(self.process, coordinator=self.coordinator)
                    return
                self.content.extend(chunk)
        except OSError:
            self.failed = True
            stop_process(self.process, coordinator=self.coordinator)
        except MemoryError:
            self.memory_failure = True
            stop_process(self.process, coordinator=self.coordinator)


def send_request(process: subprocess.Popen[bytes], encoded: bytes) -> None:
    """Send one bounded request and close stdin even if the guard already refused."""
    if process.stdin is None:
        raise fail(code="INTERNAL_FAILURE")
    try:
        process.stdin.write(encoded)
    except BrokenPipeError:
        pass
    finally:
        with suppress(BrokenPipeError):
            process.stdin.close()


def invoke(request: CoordinatorRequest | ArchiveRequest, timeout: float) -> WorkerReply:
    """Launch a fixed interpreter/module with bounded private request/response bytes."""
    try:
        encoded = request.model_dump_json(exclude_none=True).encode("utf-8")
    except ValueError:
        raise fail(code="UNREADABLE_INPUT", expanded_upper_bound=0) from None
    if len(encoded) > MAX_REQUEST_BYTES:
        raise fail(code="INPUT_LIMIT", limit="json_bytes", expanded_upper_bound=0)
    coordinator = isinstance(request, CoordinatorRequest)
    started = time.monotonic()
    process = launch_process(coordinator=coordinator)
    reader = PipeReader(process, coordinator)
    thread = threading.Thread(target=reader.read, daemon=True)
    try:
        start_reader(thread)
        send_request(process, encoded)
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        stop_process(process, coordinator=coordinator)
        raise fail(
            code="INPUT_LIMIT",
            limit="invocation_time" if coordinator else "workbook_time",
        ) from None
    except OSError:
        stop_process(process, coordinator=coordinator)
        raise fail(code="IO_FAILURE") from None
    except BaseException:
        stop_process(process, coordinator=coordinator)
        raise
    finally:
        if thread.is_alive():
            thread.join(timeout=2)
        reader.complete = not thread.is_alive()
        if process.stdout is not None and reader.complete:
            process.stdout.close()
    return decode_reply(
        reader,
        process.returncode,
        time.monotonic() - started,
        timeout,
        coordinator=coordinator,
    )


def decode_reply(
    reader: PipeReader,
    returncode: int | None,
    elapsed: float,
    timeout: float,
    *,
    coordinator: bool,
) -> WorkerReply:
    """Validate bounded response shape and retain truthful failure categories."""
    if reader.overflow:
        raise fail(code="INPUT_LIMIT", limit="json_bytes")
    if reader.memory_failure:
        raise fail(code="INPUT_LIMIT", limit="memory")
    if reader.failed:
        raise fail(code="IO_FAILURE")
    if not reader.complete or elapsed > timeout:
        raise fail(
            code="INPUT_LIMIT",
            limit="invocation_time" if coordinator else "workbook_time",
        )
    if returncode != 0:
        raise fail(code="WORKER_FAILURE")
    raw = bytes(reader.content)
    try:
        check_json(raw, MAX_REPLY_BYTES)
        reply = WorkerReply.model_validate_json(raw)
    except ValidationError, IntakeError:
        raise fail(code="INTERNAL_FAILURE") from None
    if reply.role not in {"coordinator" if coordinator else "archive", "unassigned"}:
        raise fail(code="INTERNAL_FAILURE")
    return reply


def archive_outcome(reply: WorkerReply, source_token: int) -> ArchiveOutcome:
    """Require a single matching response, preserving known worker refusal codes."""
    if (
        reply.role == "unassigned"
        and reply.diagnostics
        and reply.diagnostics[0].severity == "error"
    ):
        diagnostic = reply.diagnostics[0]
        unstarted = diagnostic.code in {
            "RESOURCE_GUARD_UNAVAILABLE",
            "INVALID_INVOCATION",
            "IO_FAILURE",
        }
        raise IntakeError(diagnostic, expanded_upper_bound=0 if unstarted else None)
    if (
        reply.role != "archive"
        or len(reply.outcomes) != 1
        or reply.outcomes[0].source_token != source_token
    ):
        raise fail(code="INTERNAL_FAILURE")
    return reply.outcomes[0]


def launch_process(*, coordinator: bool) -> subprocess.Popen[bytes]:
    """Mark process-creation failure as known zero input work."""
    try:
        return subprocess.Popen(
            [sys.executable, "-I", "-m", "dscat.intake.worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=coordinator and os.name == "posix",
        )
    except OSError:
        raise fail(code="IO_FAILURE", expanded_upper_bound=0) from None


def start_reader(thread: threading.Thread) -> None:
    """Classify reader allocation failure before any request bytes are sent."""
    try:
        thread.start()
    except RuntimeError, MemoryError:
        raise fail(code="INPUT_LIMIT", limit="memory", expanded_upper_bound=0) from None


def expansion_charge(outcome: ArchiveOutcome, remaining: int) -> int:
    """Reserve uncertain memory failures their full possible expansion budget."""
    unknown = any(
        item.code == "INPUT_LIMIT" and item.limit == "memory"
        for item in outcome.diagnostics
    )
    return (
        min(DEFAULT_LIMITS.expanded, remaining)
        if unknown
        else outcome.statistics.expanded_bytes
    )


@dataclass
class CandidateRecords:
    """Count canonical candidates before retaining them in the guarded coordinator."""

    records: list[LocatedRecord] = field(default_factory=list)
    serialized_bytes: int = 0

    def retain(
        self, records: list[LocatedRecord], collector: DiagnosticCollector
    ) -> bool:
        """Stop before dataset or deterministic byte limits are exceeded."""
        for item in records:
            payload = canonical_bytes(item.record)
            limit = (
                "datasets"
                if len(self.records) >= DEFAULT_LIMITS.datasets
                else "snapshot"
                if self.serialized_bytes + len(payload) > DEFAULT_LIMITS.snapshot
                else None
            )
            if limit is not None:
                collector.add(
                    fail(
                        code="INPUT_LIMIT",
                        limit=limit,
                        source_token=item.location.source_token,
                    ).diagnostic
                )
                return False
            self.serialized_bytes += len(payload)
            self.records.append(item)
        return True


def inspect_selection(request: CoordinatorRequest) -> WorkerReply:
    """Continue independent sources serially within aggregate bytes/time budgets."""
    started = time.monotonic()
    selection = discover(request.discovery)
    collector = DiagnosticCollector()
    for diagnostic in selection.diagnostics:
        collector.add(diagnostic)
    outcomes: list[ArchiveOutcome] = []
    child_errors = False
    candidates = CandidateRecords()
    remaining = DEFAULT_LIMITS.invocation_expanded
    skipped = (
        selection.selected_count - len(selection.sources) - selection.ignored_aliases
    )
    for index, source in enumerate(selection.sources):
        seconds = DEFAULT_LIMITS.invocation_time - (time.monotonic() - started)
        if seconds <= 0 or remaining <= 0:
            collector.add(
                fail(
                    code="INPUT_LIMIT",
                    limit="invocation_time" if seconds <= 0 else "expanded",
                ).diagnostic
            )
            skipped += len(selection.sources) - index
            break
        try:
            reply = invoke(
                ArchiveRequest(
                    schema_version="1.0",
                    role="archive",
                    source=source,
                    remaining_expanded=remaining,
                ),
                min(DEFAULT_LIMITS.workbook_time, seconds),
            )
            child_errors |= reply.has_errors
            collector.merge_exit(reply.failure_exit)
            outcome = archive_outcome(reply, source.source_token)
            remaining -= expansion_charge(outcome, remaining)
            for diagnostic in (*reply.diagnostics, *outcome.diagnostics):
                collector.add(diagnostic)
            accepted = candidates.retain(outcome.records, collector)
            outcomes.append(
                outcome.model_copy(update={"diagnostics": [], "records": []})
            )
            if not accepted:
                skipped += len(selection.sources) - index - 1
                break
            if outcome.archive_state == "unexamined":
                skipped += 1
        except IntakeError as error:
            collector.add(
                error.diagnostic.model_copy(
                    update={"source_token": source.source_token}
                )
            )
            # Unknown child work is conservatively charged its complete allowed budget.
            reservation = (
                DEFAULT_LIMITS.expanded
                if error.expanded_upper_bound is None
                else error.expanded_upper_bound
            )
            remaining -= min(reservation, remaining)
            skipped += 1
        except OSError:
            collector.add(
                fail(code="IO_FAILURE", source_token=source.source_token).diagnostic
            )
            skipped += 1
    validation = validate_catalog(
        candidates.records,
        request.assessment,
        collector.items,
        invalid=collector.has_errors
        or child_errors
        or skipped > 0
        or not selection.selection_complete,
    )
    reply = WorkerReply.model_validate(
        dict(
            schema_version="1.0",
            role="coordinator",
            outcomes=outcomes,
            diagnostics=validation.diagnostics,
            failure_exit=collector.exit_status(),
            **(
                {"catalog": validation.catalog}
                if validation.catalog is not None
                else {}
            ),
            assessment=validation.assessment,
            has_errors=validation.assessment.validity != "valid"
            or collector.has_errors
            or child_errors
            or any(outcome_failed(outcome) for outcome in outcomes),
            selection_complete=selection.selection_complete,
            unexamined_sources=skipped,
        )
    )
    return publish_selection(reply, request)


def publish_selection(reply: WorkerReply, request: CoordinatorRequest) -> WorkerReply:
    """Bound the acknowledgment before atomically saving a valid selected catalog."""
    if reply.catalog is not None and request.discovery.output is not None:
        # Reserve the bounded receipt before writing: a too-large private result must
        # fail without publishing a snapshot that cannot be acknowledged.
        check_json(
            reply.model_dump_json(exclude_none=True).encode("utf-8"),
            MAX_REPLY_BYTES - 512,
        )
        snapshot = save_snapshot(
            request.discovery.output, reply.catalog, replace=request.replace
        )
        receipt = OutputReceipt(kind="canonical", sha256=snapshot.generation)
        notices: list[Diagnostic] = []
        if snapshot.orphan_count or snapshot.retained_generation_count:
            notices.append(
                Diagnostic(
                    code="RETAINED_OUTPUT", severity="info", message_key="review_scope"
                )
            )
        collector = DiagnosticCollector()
        for diagnostic in [*reply.diagnostics, *notices]:
            collector.add(diagnostic)
        reply = WorkerReply.model_validate(
            reply.model_dump(exclude_none=True)
            | {"receipt": receipt, "diagnostics": collector.items}
        )
    return reply


def interrupted(_signum: int, _frame: FrameType | None) -> None:
    """Let the coordinator's normal exception cleanup reap a running worker."""
    raise KeyboardInterrupt


def main() -> None:
    """Enter a private worker protocol with a guard before any input processing."""
    try:
        install_guard()
        signal.signal(signal.SIGTERM, interrupted)
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        check_json(raw, MAX_REQUEST_BYTES)
        request = REQUESTS.validate_json(raw)
        reply = (
            inspect_selection(request)
            if isinstance(request, CoordinatorRequest)
            else inspect_archive(request)
        )
    except IntakeError as error:
        reply = WorkerReply(
            schema_version="1.0",
            role="unassigned",
            diagnostics=[error.diagnostic],
            has_errors=True,
            selection_complete=False,
        )
    except ValidationError:
        reply = WorkerReply(
            schema_version="1.0",
            role="unassigned",
            diagnostics=[fail(code="INVALID_INVOCATION").diagnostic],
            has_errors=True,
            selection_complete=False,
        )
    except OSError:
        reply = WorkerReply(
            schema_version="1.0",
            role="unassigned",
            diagnostics=[fail(code="IO_FAILURE").diagnostic],
            has_errors=True,
            selection_complete=False,
        )
    except MemoryError:
        reply = WorkerReply(
            schema_version="1.0",
            role="unassigned",
            diagnostics=[fail(code="INPUT_LIMIT", limit="memory").diagnostic],
            has_errors=True,
            selection_complete=False,
        )
    except KeyboardInterrupt:
        reply = WorkerReply(
            schema_version="1.0",
            role="unassigned",
            diagnostics=[fail(code="INTERRUPTED").diagnostic],
            has_errors=True,
            selection_complete=False,
        )
    except Exception:  # noqa: BLE001 -- fixed-code unexpected failure at private process entry.
        reply = WorkerReply(
            schema_version="1.0",
            role="unassigned",
            diagnostics=[fail(code="INTERNAL_FAILURE").diagnostic],
            has_errors=True,
            selection_complete=False,
        )
    sys.stdout.buffer.write(reply.model_dump_json(exclude_none=True).encode("utf-8"))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
