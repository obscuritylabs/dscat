# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Private pipe failures, precedence and cleanup never become successful replies."""

import io
import os
import signal
import subprocess
import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

import pytest

from dscat.intake import native, worker
from dscat.intake.limits import IntakeError, fail

if TYPE_CHECKING:
    from collections.abc import Callable, Generator


@dataclass
class ModelOwner:
    """Transport unit backend; native identity/cleanup has separate OS tests."""

    process: subprocess.Popen[bytes]
    active: bool = True
    wait_error: BaseException | None = None
    cleanup_error: BaseException | None = None

    def begin(self) -> bool:
        """Model either a live request receiver or an already completed refusal."""
        if not self.active:
            self.process.wait(timeout=2)
        return self.active

    def wait(self, deadline: float, check: Callable[[], None]) -> None:
        """Exercise real pipes while allowing controlled transport failure timing."""
        if self.wait_error is not None:
            raise self.wait_error
        while self.process.poll() is None:
            check()
            if time.monotonic() >= deadline:
                raise fail(code="INPUT_LIMIT", limit="invocation_time")
            time.sleep(0.001)

    def cleanup(self) -> None:
        """Release the test child even when modelling a cleanup failure."""
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=2)
        if self.cleanup_error is not None:
            raise self.cleanup_error


@pytest.fixture
def process() -> Generator[subprocess.Popen[bytes]]:
    """Use only a fixed disposable receiver; preserve original handles for cleanup."""
    child = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys;sys.stdin.buffer.read();print('reply')",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    original_in, original_out = child.stdin, child.stdout
    wait = child.wait
    kill = os.killpg
    try:
        yield child
    finally:
        with suppress(ProcessLookupError, PermissionError):
            kill(child.pid, signal.SIGKILL)
        wait(timeout=2)
        for stream in (original_in, original_out):
            if stream is not None:
                stream.close()


def exchange(
    process: subprocess.Popen[bytes], monkeypatch: pytest.MonkeyPatch
) -> tuple[native.NativeExchange, ModelOwner]:
    """Keep production transport helpers and substitute only the native wait backend."""
    owner = ModelOwner(process)
    monkeypatch.setattr(native, "NativeOwner", lambda _process: owner)
    return native.NativeExchange(
        process=process,
        encoded=b"request",
        reader=worker.PipeReader(process, coordinator=True),
        timeout=2,
        started=time.monotonic(),
        sender=worker.send_request,
        start_thread=worker.start_reader,
    ), owner


def test_transport_drains_and_closes_owned_handles(
    process: subprocess.Popen[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    """One bounded request and reply complete without a helper reaping its owner."""
    operation, _owner = exchange(process, monkeypatch)
    operation.run()
    assert operation.reader.complete
    assert operation.reader.content == b"reply\n"
    assert operation.reader.managed
    assert process.stdin is not None
    assert process.stdin.closed
    assert process.stdout is not None
    assert process.stdout.closed


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (MemoryError, "INPUT_LIMIT"),
        (OSError, "IO_FAILURE"),
        (RuntimeError, "INTERNAL_FAILURE"),
    ],
)
def test_writer_errors_are_private_fixed_failures(
    process: subprocess.Popen[bytes],
    monkeypatch: pytest.MonkeyPatch,
    error: type[Exception],
    expected: str,
) -> None:
    """Background exceptions contain no arbitrary message or thread traceback."""
    operation, _owner = exchange(process, monkeypatch)

    def refuse(_process: subprocess.Popen[bytes], _raw: bytes) -> None:
        msg = "synthetic-sensitive-writer-error"
        raise error(msg)

    operation.sender = refuse
    with pytest.raises(IntakeError) as caught:
        operation.run()
    assert caught.value.diagnostic.code == expected
    assert "sensitive" not in str(caught.value)


def test_writer_interruption_is_delivered_to_owning_thread(
    process: subprocess.Popen[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A captured interruption retains exit130 after all cleanup is attempted."""
    operation, owner = exchange(process, monkeypatch)

    def interrupt(_process: subprocess.Popen[bytes], _raw: bytes) -> None:
        raise KeyboardInterrupt

    operation.sender = interrupt
    owner.cleanup_error = OSError("synthetic cleanup error")
    with pytest.raises(KeyboardInterrupt):
        operation.run()


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        (KeyboardInterrupt(), RuntimeError(), "INTERNAL_FAILURE"),
        (OSError(), MemoryError(), "IO_FAILURE"),
        (None, KeyboardInterrupt(), "interrupt"),
    ],
)
def test_failure_precedence_is_retained(
    first: BaseException | None, second: BaseException, expected: str
) -> None:
    """Unexpected failure outranks interruption; operational ties retain the first."""
    initial = None if first is None else native.classify_failure(first)
    chosen = native.prefer_failure(initial, second)
    if expected == "interrupt":
        assert isinstance(chosen, KeyboardInterrupt)
    else:
        assert isinstance(chosen, IntakeError)
        assert chosen.diagnostic.code == expected


def test_cleanup_error_is_not_success(
    process: subprocess.Popen[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A complete reply cannot hide a failed cleanup observation."""
    operation, owner = exchange(process, monkeypatch)
    owner.cleanup_error = OSError("synthetic cleanup failure")
    with pytest.raises(IntakeError, match="IO_FAILURE"):
        operation.run()


def test_thread_cleanup_error_does_not_hide_internal_failure(
    process: subprocess.Popen[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An original unexpected failure stays dominant during helper shutdown."""
    operation, owner = exchange(process, monkeypatch)
    owner.wait_error = RuntimeError("synthetic internal failure")

    def refuse(_threads: list[worker.threading.Thread]) -> None:
        msg = "synthetic join failure"
        raise OSError(msg)

    monkeypatch.setattr(operation, "finish_threads", refuse)
    with pytest.raises(IntakeError, match="INTERNAL_FAILURE"):
        operation.run()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (MemoryError, "INPUT_LIMIT"),
        (OSError, "IO_FAILURE"),
        (RuntimeError, "INTERNAL_FAILURE"),
    ],
)
def test_managed_reader_reports_flags_without_stopping_owner(
    process: subprocess.Popen[bytes],
    monkeypatch: pytest.MonkeyPatch,
    error: type[Exception],
    expected: str,
) -> None:
    """A reader may request failure but never reap a native coordinator."""

    class BrokenStream:
        """Test-owned stream with a controlled failure instead of raw input."""

        def read(self, _size: int) -> bytes:
            raise error

    monkeypatch.setattr(process, "stdout", BrokenStream())
    reader = worker.PipeReader(process, coordinator=True, managed=True)
    reader.read()
    failure = reader.failure()
    assert failure is not None
    assert failure.diagnostic.code == expected
    assert process.returncode is None


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (OSError(), "IO_FAILURE"),
        (subprocess.TimeoutExpired("fixture", 2), "IO_FAILURE"),
        (RuntimeError(), "INTERNAL_FAILURE"),
    ],
)
def test_portable_reader_cleanup_failure_is_reported(
    process: subprocess.Popen[bytes],
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected: str,
) -> None:
    """Cleanup exceptions do not escape a background reader as arbitrary traces."""

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise error

    monkeypatch.setattr(worker, "stop_process", refuse)
    reader = worker.PipeReader(process, coordinator=True)
    reader.request_stop()
    failure = reader.failure()
    assert failure is not None
    assert failure.diagnostic.code == expected


class ShortInput(io.BytesIO):
    """Test-owned stream deliberately reporting an incomplete request write."""

    @override
    def write(self, _buffer: object, /) -> int:
        """Refuse to account a short pipe write as a complete request."""
        return 0


def test_short_request_write_is_operational_failure(
    process: subprocess.Popen[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Incomplete private requests fail before any successful result is accepted."""
    stream = ShortInput()
    monkeypatch.setattr(process, "stdin", stream)
    with pytest.raises(IntakeError, match="IO_FAILURE"):
        worker.send_request(process, b"request")
    assert stream.closed


@pytest.mark.parametrize("missing", [False, True])
def test_completed_refusal_never_forwards_request(
    process: subprocess.Popen[bytes], monkeypatch: pytest.MonkeyPatch, *, missing: bool
) -> None:
    """Already exited children need no request writer or fabricated successful input."""
    operation, owner = exchange(process, monkeypatch)
    assert process.stdin is not None
    process.stdin.close()
    owner.active = False
    if missing:
        monkeypatch.setattr(process, "stdin", None)

    def forbidden(_process: subprocess.Popen[bytes], _raw: bytes) -> None:
        pytest.fail("Completed receiver must not receive a request.")

    operation.sender = forbidden
    operation.run()
    assert operation.reader.complete


def test_stalled_writer_does_not_block_cleanup_forever(
    process: subprocess.Popen[bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stuck helper is bounded and cannot turn an internal failure into success."""
    operation, owner = exchange(process, monkeypatch)
    owner.wait_error = RuntimeError("synthetic internal error")
    release = worker.threading.Event()
    done = worker.threading.Event()

    def stalled(child: subprocess.Popen[bytes], raw: bytes) -> None:
        try:
            release.wait(timeout=5)
            worker.send_request(child, raw)
        finally:
            done.set()

    operation.sender = stalled
    try:
        with pytest.raises(IntakeError, match="INTERNAL_FAILURE"):
            operation.run()
    finally:
        release.set()
        assert done.wait(timeout=2)
