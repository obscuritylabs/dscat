# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Source identity, private IPC, serial orchestration and process cleanup acceptance."""

import io
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

import dscat.intake.worker as workers
from dscat.cli import validation_result
from dscat.intake.discovery import DiscoveryRequest, SourceDescriptor, discover
from dscat.intake.limits import ArchiveStatistics, Budget, IntakeError, Limits, fail
from dscat.models.catalog import Catalog
from dscat.models.diagnostics import Diagnostic, ValidationAssessment

OPERATIONAL_ERROR = 3
FIXTURE = Path(__file__).parent / "fixtures" / "workbook-1.0" / "template.xlsx"


def source_at(path: Path) -> SourceDescriptor:
    """Bind a real selected file to its observed physical identity."""
    selection = discover(DiscoveryRequest(input=path))
    assert not selection.has_errors
    return selection.sources[0]


def request_at(path: Path) -> workers.CoordinatorRequest:
    """Create an explicit coordinator request."""
    return workers.CoordinatorRequest(
        schema_version="1.0", role="coordinator", discovery=DiscoveryRequest(input=path)
    )


def safe_reply(source_token: int = 1) -> workers.WorkerReply:
    """Provide protocol data without claiming actual archive inspection."""
    outcome = workers.ArchiveOutcome(
        source_token=source_token, archive_state="safe", statistics=ArchiveStatistics()
    )
    return workers.WorkerReply(
        schema_version="1.0",
        role="archive",
        outcomes=[outcome],
        has_errors=False,
        selection_complete=True,
    )


def test_read_identity_size_and_readonly_preservation(tmp_path: Path) -> None:
    """Read the selected regular identity within explicit byte bounds."""
    path = tmp_path / "source.xlsx"
    original = b"synthetic bytes"
    path.write_bytes(original)
    source = source_at(path)
    assert workers.read_source(source, Budget()) == original
    assert path.read_bytes() == original
    with pytest.raises(IntakeError) as limit:
        workers.read_source(source, Budget(limits=Limits(compressed=len(original) - 1)))
    assert limit.value.diagnostic.limit == "compressed"
    path.write_bytes(original + b"changed")
    with pytest.raises(IntakeError, match="UNSAFE_INPUT"):
        workers.read_source(source, Budget())


def test_identity_change_while_open_and_during_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refuse changed descriptors and final path identities."""
    path = tmp_path / "source.xlsx"
    path.write_bytes(b"synthetic")
    source = source_at(path)
    changed = source.identity.model_copy(
        update={"modified_ns": source.identity.modified_ns + 1}
    )
    observed = [0]

    def identity(_attributes: os.stat_result) -> object:
        observed[0] += 1
        return changed if observed[0] > 1 else source.identity

    monkeypatch.setattr(workers, "file_identity", identity)
    with pytest.raises(IntakeError, match="UNSAFE_INPUT"):
        workers.read_source(source, Budget())


def test_archive_inspection_success_and_known_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expected failures never become success or emit raw contents."""
    path = tmp_path / "private-synthetic-name.xlsx"
    path.write_bytes(FIXTURE.read_bytes())
    request = workers.ArchiveRequest(
        schema_version="1.0",
        role="archive",
        source=source_at(path),
        remaining_expanded=256 * 1024**2,
    )
    good = workers.inspect_archive(request)
    assert not good.has_errors
    assert good.outcomes[0].archive_state == "safe"
    assert "private-synthetic-name" not in good.model_dump_json(exclude_none=True)
    path.write_bytes(b"invalid zip synthetic-sensitive-sentinel")
    request = workers.ArchiveRequest(
        schema_version="1.0",
        role="archive",
        source=source_at(path),
        remaining_expanded=256 * 1024**2,
    )
    bad = workers.inspect_archive(request)
    assert bad.outcomes[0].archive_state == "rejected"
    assert bad.outcomes[0].diagnostics[0].source_token == 1
    assert "sensitive-sentinel" not in bad.model_dump_json(exclude_none=True)
    for error in (OSError, MemoryError):

        def refused(
            _source: SourceDescriptor, _budget: Budget, _error: type[Exception] = error
        ) -> bytes:
            msg = "Synthetic inaccessible input"
            raise _error(msg)

        monkeypatch.setattr(workers, "read_source", refused)
        reply = workers.inspect_archive(request)
        assert reply.outcomes[0].archive_state == "unexamined"
        assert reply.has_errors


@pytest.mark.parametrize(
    "raw",
    [
        b'{"same":1,"same":2}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":-Infinity}',
        b"",
        b"\xff",
        b"[",
        b"1" * 5000,
    ],
)
def test_private_json_rejects_duplicates_nonfinite_and_malformed(raw: bytes) -> None:
    """Malformed IPC cannot overwrite fields or expose parser errors."""
    with pytest.raises(IntakeError):
        workers.check_json(raw, 65536)


def test_private_json_byte_depth_and_escaped_strings() -> None:
    """Accept inclusive limits without counting quoted brackets as containers."""
    workers.check_json(b"[]", 2)
    with pytest.raises(IntakeError) as size:
        workers.check_json(b"[] ", 2)
    assert size.value.diagnostic.limit == "json_bytes"
    workers.check_json(b"[" * 64 + b"]" * 64, 65536)
    with pytest.raises(IntakeError) as depth:
        workers.check_json(b"[" * 65 + b"]" * 65, 65536)
    assert depth.value.diagnostic.limit == "depth"
    workers.check_json(
        json.dumps({"quoted": 'brackets [ { and escaped " and \\'}).encode(), 65536
    )


def test_inconsistent_or_unsupported_worker_output_is_rejected() -> None:
    """Output cannot claim success for failed, unexamined or incomplete work."""
    base = safe_reply().model_dump(exclude_none=True)
    for change in (
        {"schema_version": "2.0"},
        {"extra": "synthetic"},
        {"selection_complete": False},
        {"unexamined_sources": 1},
        {"diagnostics": [fail(code="INVALID_METADATA").diagnostic]},
        {
            "outcomes": [
                workers.ArchiveOutcome(
                    source_token=1,
                    archive_state="unexamined",
                    statistics=ArchiveStatistics(),
                )
            ]
        },
    ):
        with pytest.raises(ValidationError):
            workers.WorkerReply.model_validate(base | change)
    with pytest.raises(ValidationError):
        workers.ArchiveRequest.model_validate(
            {"schema_version": "1.0", "role": "archive", "remaining_expanded": True}
        )


def test_archive_outcome_matching_and_known_guard_refusal() -> None:
    """A child refusal retains its fixed code; wrong response identity fails closed."""
    assert workers.archive_outcome(safe_reply(), 1).source_token == 1
    for reply in (
        safe_reply(2),
        workers.WorkerReply(
            schema_version="1.0",
            role="coordinator",
            catalog=Catalog(schema_version="1.0", datasets=[]),
            assessment=ValidationAssessment(validity="valid"),
            has_errors=False,
            selection_complete=True,
        ),
    ):
        with pytest.raises(IntakeError, match="INTERNAL_FAILURE"):
            workers.archive_outcome(reply, 1)
    refused = workers.WorkerReply(
        schema_version="1.0",
        role="unassigned",
        diagnostics=[fail(code="RESOURCE_GUARD_UNAVAILABLE").diagnostic],
        has_errors=True,
        selection_complete=False,
    )
    with pytest.raises(IntakeError, match="RESOURCE_GUARD_UNAVAILABLE"):
        workers.archive_outcome(refused, 1)


def test_serial_selection_continue_errors_and_alias_accounting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Continue independent sources without rereading physical aliases."""
    for name in ("a.xlsx", "b.xlsx", "c.xlsx"):
        (tmp_path / name).write_bytes(b"synthetic")
    os.link(tmp_path / "c.xlsx", tmp_path / "d.xlsx")
    requested: list[int] = []

    def execute(
        request: workers.CoordinatorRequest | workers.ArchiveRequest, _timeout: float
    ) -> workers.WorkerReply:
        assert isinstance(request, workers.ArchiveRequest)
        requested.append(request.source.source_token)
        if request.source.source_token == 1:
            raise fail(code="UNREADABLE_INPUT")
        return safe_reply(request.source.source_token)

    monkeypatch.setattr(workers, "invoke", execute)
    reply = workers.inspect_selection(request_at(tmp_path))
    assert requested == [1, 2, 3]
    assert reply.has_errors
    assert reply.unexamined_sources == 1
    assert [o.source_token for o in reply.outcomes] == [2, 3]


def test_aggregate_expansion_exhaustion_and_spawn_io_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Charge unknown child work and leave exhausted sources unexamined."""
    for index in range(3):
        (tmp_path / f"{index}.xlsx").touch()

    def rejected(
        _request: workers.CoordinatorRequest | workers.ArchiveRequest, _timeout: float
    ) -> workers.WorkerReply:
        raise fail(code="INPUT_LIMIT", limit="memory")

    monkeypatch.setattr(workers, "invoke", rejected)
    reply = workers.inspect_selection(request_at(tmp_path))
    assert reply.has_errors
    assert reply.unexamined_sources == len([0, 1, 2])

    assert any(item.limit == "expanded" for item in reply.diagnostics)

    def unavailable(
        _request: workers.CoordinatorRequest | workers.ArchiveRequest, _timeout: float
    ) -> workers.WorkerReply:
        msg = "Synthetic process creation failure"
        raise OSError(msg)

    monkeypatch.setattr(workers, "invoke", unavailable)
    reply = workers.inspect_selection(request_at(tmp_path))
    assert all(
        d.code == "IO_FAILURE" for d in reply.diagnostics if d.severity == "error"
    )
    assert reply.unexamined_sources == len([0, 1, 2])


def test_truncated_child_error_state_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep truncated child failures even when retained notices are warnings."""
    (tmp_path / "one.xlsx").touch()
    notice = Diagnostic(
        code="DIAGNOSTICS_TRUNCATED",
        severity="warning",
        message_key="review_scope",
        check_state="unperformed",
    )
    outcome = workers.ArchiveOutcome(
        source_token=1,
        archive_state="safe",
        statistics=ArchiveStatistics(),
        diagnostics=[notice],
    )
    reply = workers.WorkerReply(
        schema_version="1.0",
        role="archive",
        outcomes=[outcome],
        has_errors=True,
        selection_complete=True,
    )
    monkeypatch.setattr(workers, "invoke", lambda _request, _timeout: reply)
    assert workers.inspect_selection(request_at(tmp_path)).has_errors


def test_coordinator_deadline_and_discovery_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The invocation deadline and unavailable selections are explicit failures."""
    missing = workers.inspect_selection(request_at(tmp_path / "missing.xlsx"))
    assert missing.has_errors
    (tmp_path / "one.xlsx").touch()
    selection = discover(DiscoveryRequest(input=tmp_path))
    monkeypatch.setattr(workers, "discover", lambda _request: selection)
    ticks = iter([0.0, 301.0])
    monkeypatch.setattr(workers.time, "monotonic", lambda: next(ticks))
    reply = workers.inspect_selection(request_at(tmp_path))
    assert reply.diagnostics[0].limit == "invocation_time"
    assert reply.unexamined_sources == 1


def launch_script(
    monkeypatch: pytest.MonkeyPatch, script: str
) -> list[subprocess.Popen[bytes]]:
    """Use real pipes with a test-owned child program."""
    original = subprocess.Popen
    processes: list[subprocess.Popen[bytes]] = []

    def launch(*_args: object, **options: object) -> subprocess.Popen[bytes]:
        process = original(
            [sys.executable, "-I", "-c", script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=bool(options.get("start_new_session")),
        )
        processes.append(process)
        return process

    monkeypatch.setattr(workers.subprocess, "Popen", launch)
    return processes


def test_real_pipe_reply_and_malformed_child_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject malformed/contradictory child output."""
    raw = (
        workers.WorkerReply(
            schema_version="1.0",
            role="coordinator",
            catalog=Catalog(schema_version="1.0", datasets=[]),
            assessment=ValidationAssessment(validity="valid"),
            outcomes=safe_reply().outcomes,
            has_errors=False,
            selection_complete=True,
        )
        .model_dump_json(exclude_none=True)
        .encode()
    )
    launch_script(
        monkeypatch,
        "import sys;sys.stdin.buffer.read();sys.stdout.buffer.write(" + repr(raw) + ")",
    )
    reply = workers.invoke(request_at(tmp_path), 5.0)
    assert not reply.has_errors
    monkeypatch.undo()
    launch_script(monkeypatch, "import sys;sys.stdin.buffer.read();print('not-json')")
    with pytest.raises(IntakeError, match="INTERNAL_FAILURE"):
        workers.invoke(request_at(tmp_path), 5.0)


def test_actual_timeout_kills_and_reaps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Terminate and reap timed-out child processes."""
    processes = launch_script(monkeypatch, "import time;time.sleep(60)")
    with pytest.raises(IntakeError) as caught:
        workers.invoke(request_at(tmp_path), 0.05)
    assert caught.value.diagnostic.limit == "invocation_time"
    assert processes[0].poll() is not None


def test_child_nonzero_exit_and_response_overflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail safely on process failure and excess response bytes."""
    launch_script(monkeypatch, "raise SystemExit(7)")
    with pytest.raises(IntakeError, match="WORKER_FAILURE"):
        workers.invoke(request_at(tmp_path), 5.0)
    monkeypatch.undo()
    launch_script(
        monkeypatch,
        "import sys;sys.stdin.buffer.read();sys.stdout.buffer.write(b'x'*256)",
    )
    monkeypatch.setattr(workers, "MAX_REPLY_BYTES", 128)
    with pytest.raises(IntakeError) as overflow:
        workers.invoke(request_at(tmp_path), 5.0)
    assert overflow.value.diagnostic.limit == "json_bytes"


def test_entry_never_reads_input_when_guard_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refuse before private request decoding or workbook reads."""
    output = io.BytesIO()

    class Output:
        """Capture byte output from the private entrypoint."""

        buffer = output

    def refused() -> None:
        raise fail(code="RESOURCE_GUARD_UNAVAILABLE")

    monkeypatch.setattr(workers, "install_guard", refused)
    monkeypatch.setattr(sys, "stdout", Output())
    workers.main()
    reply = workers.WorkerReply.model_validate_json(output.getvalue())
    assert reply.diagnostics[0].code == "RESOURCE_GUARD_UNAVAILABLE"
    assert reply.outcomes == []


@pytest.mark.skipif(
    sys.platform != "linux",
    reason="Requires actual Linux hard address-space enforcement.",
)
def test_native_linux_guarded_archive_with_network_denied(tmp_path: Path) -> None:
    """Exercise real bounded Linux coordinator and worker processes."""
    path = tmp_path / "synthetic.xlsx"
    original = FIXTURE.read_bytes()
    path.write_bytes(original)
    reply = workers.invoke(request_at(path), 30.0)
    assert not reply.has_errors
    assert reply.outcomes[0].archive_state == "safe"
    assert reply.outcomes[0].statistics.compressed_bytes == len(original)
    assert path.read_bytes() == original


@pytest.mark.skipif(
    sys.platform != "darwin",
    reason="Observed macOS guard refusal is platform-specific.",
)
def test_native_macos_refuses_unavailable_guard(tmp_path: Path) -> None:
    """The observed unsupported hard limit cannot silently run unbounded intake."""
    reply = workers.invoke(
        request_at(tmp_path / "synthetic-sensitive-filename.xlsx"), 10.0
    )
    assert reply.has_errors
    assert reply.diagnostics[0].code == "RESOURCE_GUARD_UNAVAILABLE"
    assert "sensitive-filename" not in reply.model_dump_json(exclude_none=True)


@pytest.mark.parametrize("role", ["coordinator", "archive"])
def test_entry_dispatches_guarded_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    """Private entry dispatches only validated requests after installing the guard."""
    path = tmp_path / "synthetic.xlsx"
    path.write_bytes(FIXTURE.read_bytes())
    request = (
        request_at(path)
        if role == "coordinator"
        else workers.ArchiveRequest(
            schema_version="1.0",
            role="archive",
            source=source_at(path),
            remaining_expanded=256 * 1024**2,
        )
    )
    output = io.BytesIO()
    monkeypatch.setattr(workers, "install_guard", lambda: None)
    monkeypatch.setattr(workers.signal, "signal", lambda *_args: None)
    monkeypatch.setattr(workers, "invoke", lambda *_args: safe_reply())
    monkeypatch.setattr(
        sys,
        "stdin",
        io.TextIOWrapper(
            io.BytesIO(request.model_dump_json(exclude_none=True).encode())
        ),
    )
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(output))
    workers.main()
    reply = workers.WorkerReply.model_validate_json(output.getvalue())
    assert reply.role == role
    assert not reply.has_errors


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (OSError, "IO_FAILURE"),
        (MemoryError, "INPUT_LIMIT"),
        (KeyboardInterrupt, "INTERRUPTED"),
        (RuntimeError, "INTERNAL_FAILURE"),
    ],
)
def test_entry_fixed_failure_categories(
    monkeypatch: pytest.MonkeyPatch, error: type[BaseException], code: str
) -> None:
    """Unexpected worker failures emit fixed diagnostics without exception details."""
    output = io.BytesIO()

    def refused() -> None:
        msg = "synthetic-sensitive-exception"
        raise error(msg)

    monkeypatch.setattr(workers, "install_guard", refused)
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(output))
    workers.main()
    reply = workers.WorkerReply.model_validate_json(output.getvalue())
    assert reply.diagnostics[0].code == code
    assert "sensitive" not in reply.model_dump_json(exclude_none=True)


def test_entry_rejects_invalid_request_and_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valid JSON with the wrong request schema fails before dispatch."""
    output = io.BytesIO()
    monkeypatch.setattr(workers, "install_guard", lambda: None)
    monkeypatch.setattr(workers.signal, "signal", lambda *_args: None)
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"{}")))
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(output))
    workers.main()
    reply = workers.WorkerReply.model_validate_json(output.getvalue())
    assert reply.diagnostics[0].code == "INVALID_INVOCATION"
    with pytest.raises(KeyboardInterrupt):
        workers.interrupted(15, None)


def test_request_too_large_never_launches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Oversized requests are known to have consumed no archive expansion."""
    monkeypatch.setattr(workers, "MAX_REQUEST_BYTES", 1)
    with pytest.raises(IntakeError) as caught:
        workers.invoke(request_at(tmp_path), 5.0)
    assert caught.value.expanded_upper_bound == 0


def test_spawn_refusal_and_reader_start_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pre-request startup failures retain zero-work accounting and reap the child."""

    def refused(*_args: object, **_options: object) -> None:
        msg = "synthetic spawn refusal"
        raise OSError(msg)

    monkeypatch.setattr(workers.subprocess, "Popen", refused)
    with pytest.raises(IntakeError) as spawn:
        workers.invoke(request_at(tmp_path), 5.0)
    assert spawn.value.expanded_upper_bound == 0
    monkeypatch.undo()
    processes = launch_script(monkeypatch, "import time;time.sleep(60)")

    def no_thread(_thread: object) -> None:
        msg = "synthetic reader startup refusal"
        raise RuntimeError(msg)

    monkeypatch.setattr(workers.threading.Thread, "start", no_thread)
    with pytest.raises(IntakeError) as reader:
        workers.invoke(request_at(tmp_path), 5.0)
    assert reader.value.expanded_upper_bound == 0
    assert processes[0].poll() is not None


def test_request_pipe_failure_and_interruption_reap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failures after spawning cannot leave a child consuming resources."""
    for error in (OSError, KeyboardInterrupt):
        processes = launch_script(monkeypatch, "import time;time.sleep(60)")

        def refused(
            _process: subprocess.Popen[bytes],
            _encoded: bytes,
            _error: type[BaseException] = error,
        ) -> None:
            raise _error

        monkeypatch.setattr(workers, "send_request", refused)
        with pytest.raises(IntakeError if error is OSError else KeyboardInterrupt):
            workers.invoke(request_at(tmp_path), 5.0)
        assert processes[0].poll() is not None
        monkeypatch.undo()


@pytest.mark.parametrize(
    "flag",
    ["memory_failure", "failed", "incomplete", "late", "wrong_role", "bad_schema"],
)
def test_reply_failure_states(monkeypatch: pytest.MonkeyPatch, flag: str) -> None:
    """Bounded reply decoding rejects operational failures and wrong role/schema."""
    processes = launch_script(monkeypatch, "pass")
    process = workers.launch_process(coordinator=False)
    process.wait(timeout=5)
    reader = workers.PipeReader(process, coordinator=False, complete=True)
    reader.content.extend(safe_reply().model_dump_json(exclude_none=True).encode())
    if flag in {"memory_failure", "failed"}:
        setattr(reader, flag, True)
    elif flag == "incomplete":
        reader.complete = False
    elif flag == "bad_schema":
        reader.content = bytearray(b"{}")
    with pytest.raises(IntakeError):
        workers.decode_reply(
            reader,
            0,
            6.0 if flag == "late" else 0.0,
            5.0,
            coordinator=flag == "wrong_role",
        )
    assert processes[0].poll() is not None
    if process.stdin is not None:
        process.stdin.close()
    if process.stdout is not None:
        process.stdout.close()


def test_worker_role_cardinality_and_memory_reservation() -> None:
    """Invalid role cardinality and negative reservations cannot enter the protocol."""
    for role, outcomes in (("archive", []), ("unassigned", safe_reply().outcomes)):
        with pytest.raises(ValidationError):
            workers.WorkerReply.model_validate(
                {
                    "schema_version": "1.0",
                    "role": role,
                    "outcomes": outcomes,
                    "has_errors": True,
                    "selection_complete": False,
                }
            )
    with pytest.raises(ValueError, match="cannot be negative"):
        IntakeError(fail(code="IO_FAILURE").diagnostic, expanded_upper_bound=-1)
    outcome = workers.ArchiveOutcome(
        source_token=1,
        archive_state="unexamined",
        statistics=ArchiveStatistics(),
        diagnostics=[fail(code="INPUT_LIMIT", limit="memory").diagnostic],
    )
    remaining = 100
    assert workers.expansion_charge(outcome, remaining) == remaining


@pytest.mark.parametrize("phase", [2, 3, 4])
def test_identity_rechecked_at_each_read_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: int
) -> None:
    """Both descriptor checks and the final path identity detect changed inputs."""
    path = tmp_path / "source.xlsx"
    path.write_bytes(b"synthetic")
    source = source_at(path)
    changed = source.identity.model_copy(
        update={"modified_ns": source.identity.modified_ns + 1}
    )
    calls = [0]

    def identity(_attributes: os.stat_result) -> object:
        calls[0] += 1
        return changed if calls[0] == phase else source.identity

    monkeypatch.setattr(workers, "file_identity", identity)
    with pytest.raises(IntakeError, match="UNSAFE_INPUT"):
        workers.read_source(source, Budget())


def test_empty_pipes_and_broken_request_pipe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing pipes and early child exit cannot produce a successful reply."""
    process = subprocess.Popen(
        [sys.executable, "-I", "-c", "pass"], stdout=subprocess.DEVNULL
    )
    process.wait(timeout=5)
    reader = workers.PipeReader(process, coordinator=False)
    reader.read()
    assert reader.failed
    with pytest.raises(IntakeError, match="INTERNAL_FAILURE"):
        workers.send_request(process, b"{}")
    processes = launch_script(monkeypatch, "pass")
    child = workers.launch_process(coordinator=False)
    child.wait(timeout=5)
    workers.send_request(child, b"{}")
    assert child.stdin is not None
    assert child.stdin.closed
    if child.stdout is not None:
        child.stdout.close()
    assert processes[0].poll() is not None


@pytest.mark.skipif(os.name != "posix", reason="Exercises POSIX process-group signals.")
def test_unresponsive_coordinator_requires_group_kill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A child ignoring graceful termination is killed and reaped."""
    processes = launch_script(
        monkeypatch,
        "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);"
        "print('ready',flush=True);time.sleep(60)",
    )
    process = workers.launch_process(coordinator=True)
    assert process.stdout is not None
    assert process.stdout.readline() == b"ready\n"
    workers.stop_process(process, coordinator=True)
    assert process.poll() is not None
    assert processes[0].poll() is not None
    if process.stdin is not None:
        process.stdin.close()
    process.stdout.close()


def test_serial_unexamined_outcome_counts_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unexamined worker results remain visible in aggregate completeness."""
    (tmp_path / "one.xlsx").touch()
    outcome = workers.ArchiveOutcome(
        source_token=1, archive_state="unexamined", statistics=ArchiveStatistics()
    )
    reply = workers.WorkerReply(
        schema_version="1.0",
        role="archive",
        outcomes=[outcome],
        has_errors=True,
        selection_complete=True,
        unexamined_sources=1,
    )
    monkeypatch.setattr(workers, "invoke", lambda *_args: reply)
    assert workers.inspect_selection(request_at(tmp_path)).unexamined_sources == 1


@pytest.mark.parametrize("error", [OSError, MemoryError])
def test_reader_stream_failure_stops_child(
    monkeypatch: pytest.MonkeyPatch, error: type[Exception]
) -> None:
    """Reader failures retain their category and stop the running process."""
    processes = launch_script(monkeypatch, "import time;time.sleep(60)")
    process = workers.launch_process(coordinator=False)
    original = process.stdout

    def refused(_size: int) -> bytes:
        raise error

    assert original is not None
    monkeypatch.setattr(original, "read", refused)
    reader = workers.PipeReader(process, coordinator=False)
    reader.read()
    assert reader.memory_failure if error is MemoryError else reader.failed
    assert processes[0].poll() is not None
    original.close()
    if process.stdin is not None:
        process.stdin.close()


def test_module_entrypoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """The installed module entrypoint emits a bounded protocol response."""
    output = io.BytesIO()

    def refused() -> None:
        raise fail(code="RESOURCE_GUARD_UNAVAILABLE")

    monkeypatch.setattr("dscat.platform.install_guard", refused)
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(output))
    with pytest.warns(RuntimeWarning, match="found in sys.modules"):
        runpy.run_module("dscat.intake.worker", run_name="__main__")
    reply = workers.WorkerReply.model_validate_json(output.getvalue())
    assert reply.has_errors


def test_source_actual_bytes_exceed_changed_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The read counter independently limits bytes despite smaller size metadata."""
    path = tmp_path / "source.xlsx"
    path.write_bytes(b"synthetic")
    source = source_at(path)
    small = source.identity.model_copy(update={"size": 1})
    monkeypatch.setattr(workers, "file_identity", lambda _attributes: small)
    with pytest.raises(IntakeError) as caught:
        workers.read_source(
            source.model_copy(update={"identity": small}),
            Budget(limits=Limits(compressed=1)),
        )
    assert caught.value.diagnostic.limit == "compressed"


def test_request_serialization_refusal_has_zero_work(tmp_path: Path) -> None:
    """Unrepresentable path characters fail before starting any worker."""
    with pytest.raises(IntakeError) as caught:
        workers.invoke(request_at(tmp_path / "\ud800.xlsx"), 5.0)
    assert caught.value.expanded_upper_bound == 0


def test_termination_race_still_reaps(monkeypatch: pytest.MonkeyPatch) -> None:
    """A child exiting at group termination does not bypass reaping."""
    processes = launch_script(monkeypatch, "import time;time.sleep(60)")
    process = workers.launch_process(coordinator=True)

    def raced(_pid: int, _signal: int) -> None:
        process.kill()
        raise ProcessLookupError

    monkeypatch.setattr(workers.os, "killpg", raced)
    workers.stop_process(process, coordinator=True)
    assert processes[0].poll() is not None
    if process.stdin is not None:
        process.stdin.close()
    if process.stdout is not None:
        process.stdout.close()


def test_portable_terminate_path_uses_process_handle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the portable process-handle cleanup path without a native OS claim."""
    processes = launch_script(monkeypatch, "import time;time.sleep(60)")
    process = workers.launch_process(coordinator=True)
    with monkeypatch.context() as local:
        local.setattr(workers.os, "name", "nt")
        workers.stop_process(process, coordinator=True)
    assert processes[0].poll() is not None
    if process.stdin is not None:
        process.stdin.close()
    if process.stdout is not None:
        process.stdout.close()


def test_kill_exit_race_and_missing_child_response_pipe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A race at forced kill is reaped; a missing stdout pipe fails closed."""
    processes = launch_script(monkeypatch, "import time;time.sleep(60)")
    process = workers.launch_process(coordinator=False)
    kill = process.kill

    def raced() -> None:
        kill()
        raise ProcessLookupError

    monkeypatch.setattr(process, "kill", raced)
    workers.stop_process(process, coordinator=False)
    assert processes[0].poll() is not None
    if process.stdin is not None:
        process.stdin.close()
    if process.stdout is not None:
        process.stdout.close()
    monkeypatch.undo()
    original = subprocess.Popen

    def launch(*_args: object, **_options: object) -> subprocess.Popen[bytes]:
        return original(
            [sys.executable, "-I", "-c", "import sys;sys.stdin.buffer.read()"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
        )

    monkeypatch.setattr(workers.subprocess, "Popen", launch)
    with pytest.raises(IntakeError, match="IO_FAILURE"):
        workers.invoke(request_at(tmp_path), 5.0)


def test_reader_join_and_incomplete_drain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An incomplete response drain cannot become a successful worker result."""
    processes = launch_script(monkeypatch, "import sys;sys.stdin.buffer.read()")
    release = workers.threading.Event()
    done = workers.threading.Event()

    def waiting(_reader: workers.PipeReader) -> None:
        release.wait(timeout=10)
        done.set()

    monkeypatch.setattr(workers.PipeReader, "read", waiting)
    try:
        with pytest.raises(IntakeError) as caught:
            workers.invoke(request_at(tmp_path), 5.0)
        assert caught.value.diagnostic.limit == "invocation_time"
    finally:
        release.set()
        assert done.wait(timeout=2)
        if processes[0].stdout is not None:
            processes[0].stdout.close()
    assert processes[0].poll() is not None


def test_request_write_broken_pipe_is_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Early guard refusal can break the request write without leaking its pipe."""
    processes = launch_script(monkeypatch, "pass")
    process = workers.launch_process(coordinator=False)
    process.wait(timeout=5)
    assert process.stdin is not None

    def broken(_encoded: bytes) -> int:
        raise BrokenPipeError

    monkeypatch.setattr(process.stdin, "write", broken)
    workers.send_request(process, b"{}")
    assert process.stdin.closed
    if process.stdout is not None:
        process.stdout.close()
    assert processes[0].poll() is not None


def test_one_shared_diagnostic_budget_across_discovery_and_workers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Worker diagnostics share the discovery cap and retain truncation/error state."""
    path = tmp_path / "one.xlsx"
    path.touch()
    selection = discover(DiscoveryRequest(input=tmp_path))
    maximum = 10000
    selection = selection.model_copy(
        update={
            "diagnostics": [fail(code="UNREADABLE_INPUT").diagnostic] * maximum,
            "has_errors": True,
        }
    )
    monkeypatch.setattr(workers, "discover", lambda _request: selection)
    outcome = workers.ArchiveOutcome(
        source_token=1,
        archive_state="rejected",
        statistics=ArchiveStatistics(),
        diagnostics=[fail(code="INVALID_WORKBOOK", source_token=1).diagnostic],
    )
    reply = workers.WorkerReply(
        schema_version="1.0",
        role="archive",
        outcomes=[outcome],
        has_errors=True,
        selection_complete=True,
    )
    monkeypatch.setattr(workers, "invoke", lambda *_args: reply)
    result = workers.inspect_selection(request_at(tmp_path))
    retained = len(result.diagnostics) + sum(
        len(item.diagnostics) for item in result.outcomes
    )
    assert retained == maximum
    assert result.has_errors
    assert result.diagnostics[-1].code == "DIAGNOSTICS_TRUNCATED"
    assert result.diagnostics[-1].check_state == "unperformed"
    assert result.outcomes[0].archive_state == "rejected"
    assert result.outcomes[0].diagnostics == []


def test_worker_reply_cannot_bypass_aggregate_diagnostic_cap() -> None:
    """Nested diagnostic lists cannot independently consume full invocation budgets."""
    maximum = 10000
    diagnostic = fail(code="INVALID_WORKBOOK").diagnostic
    outcome = workers.ArchiveOutcome(
        source_token=1,
        archive_state="rejected",
        statistics=ArchiveStatistics(),
        diagnostics=[diagnostic],
    )
    with pytest.raises(ValidationError, match="invocation diagnostic limit"):
        workers.WorkerReply(
            schema_version="1.0",
            role="archive",
            outcomes=[outcome],
            diagnostics=[diagnostic] * maximum,
            has_errors=True,
            selection_complete=True,
        )
    with pytest.raises(ValidationError):
        workers.ArchiveOutcome(
            source_token=1,
            archive_state="rejected",
            statistics=ArchiveStatistics(),
            diagnostics=[diagnostic] * (maximum + 1),
        )


@pytest.mark.parametrize(
    "change",
    [
        {},
        {"assessment": ValidationAssessment(validity="valid")},
        {
            "catalog": Catalog(schema_version="1.0", datasets=[]),
            "assessment": ValidationAssessment(validity="unexamined"),
        },
        {
            "catalog": Catalog(schema_version="1.0", datasets=[]),
            "assessment": ValidationAssessment(validity="invalid"),
            "has_errors": True,
        },
    ],
)
def test_coordinator_cannot_claim_success_without_validated_facts(
    change: dict[str, object],
) -> None:
    """Incomplete and invalid semantic outputs cannot pass as successful validation."""
    with pytest.raises(ValidationError):
        workers.WorkerReply.model_validate(
            {
                "schema_version": "1.0",
                "role": "coordinator",
                "has_errors": False,
                "selection_complete": True,
            }
            | change
        )


def test_catalog_and_invalid_assessment_cannot_escape_their_protocol_role() -> None:
    """Wrong-role facts and a false error flag fail structured output validation."""
    base = safe_reply().model_dump(exclude_none=True)
    with pytest.raises(ValidationError, match="valid coordinator assessment"):
        workers.WorkerReply.model_validate(
            base
            | {
                "catalog": Catalog(schema_version="1.0", datasets=[]),
                "assessment": ValidationAssessment(validity="valid"),
            }
        )
    with pytest.raises(ValidationError, match="Invalid intake"):
        workers.WorkerReply.model_validate(
            base | {"assessment": ValidationAssessment(validity="invalid")}
        )


def test_operational_exit_survives_truncation_across_source_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The shared cap preserves failure category as well as the error flag."""
    for name in ("a.xlsx", "b.xlsx"):
        (tmp_path / name).touch()
    notice = Diagnostic(
        code="IGNORED_WORKSHEET",
        severity="warning",
        message_key="review_scope",
        check_state="unperformed",
    )
    selection = discover(DiscoveryRequest(input=tmp_path))
    selection = selection.model_copy(update={"diagnostics": [notice] * 9999})
    monkeypatch.setattr(workers, "discover", lambda _request: selection)

    def execute(
        request: workers.CoordinatorRequest | workers.ArchiveRequest, _timeout: float
    ) -> workers.WorkerReply:
        assert isinstance(request, workers.ArchiveRequest)
        failed = request.source.source_token == 1
        outcome = workers.ArchiveOutcome(
            source_token=request.source.source_token,
            archive_state="unexamined" if failed else "safe",
            statistics=ArchiveStatistics(),
            diagnostics=[fail(code="UNREADABLE_INPUT").diagnostic]
            if failed
            else [notice],
        )
        return workers.WorkerReply(
            schema_version="1.0",
            role="archive",
            outcomes=[outcome],
            has_errors=failed,
            selection_complete=True,
            unexamined_sources=1 if failed else 0,
        )

    monkeypatch.setattr(workers, "invoke", execute)
    result = workers.inspect_selection(request_at(tmp_path))
    assert result.has_errors
    assert not any(item.severity == "error" for item in result.diagnostics)
    assert result.diagnostics[-1].code == "DIAGNOSTICS_TRUNCATED"
    assert result.failure_exit == OPERATIONAL_ERROR
    assert validation_result(result).exit_code == OPERATIONAL_ERROR


def test_failure_category_cannot_accompany_a_success_flag() -> None:
    """The private typed result rejects a contradictory failure precedence flag."""
    with pytest.raises(ValidationError, match="Failure status"):
        workers.WorkerReply.model_validate(
            safe_reply().model_dump(exclude_none=True) | {"failure_exit": 3}
        )
