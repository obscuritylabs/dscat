# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Bounded pipe helpers keep native observation in the outer owner's main loop."""

import threading
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING

from dscat.intake.limits import (
    Failure,
    IntakeError,
    classify_failure,
    fail,
    prefer_failure,
)
from dscat.platform.supervision import NativeOwner

if TYPE_CHECKING:
    import subprocess
    from collections.abc import Callable

    from dscat.intake.worker import PipeReader


@dataclass
class PipeWriter:
    """Forward bounded private bytes without blocking independent observation."""

    process: subprocess.Popen[bytes]
    encoded: bytes
    sender: Callable[[subprocess.Popen[bytes], bytes], None]
    failure: Failure | None = None

    def run(self) -> None:
        """Store only a classified exception, never print a background traceback."""
        try:
            self.sender(self.process, self.encoded)
        except BaseException as error:  # noqa: BLE001 -- transfer interruption to the owning main thread.
            self.failure = classify_failure(error)


@dataclass
class NativeExchange:
    """Own one coordinator, two bounded transport helpers and native cleanup."""

    process: subprocess.Popen[bytes]
    encoded: bytes
    reader: PipeReader
    timeout: float
    started: float
    sender: Callable[[subprocess.Popen[bytes], bytes], None]
    start_thread: Callable[[threading.Thread], None]

    def check(self, writer: PipeWriter) -> None:
        """Merge private transport flags before selecting one safe failure."""
        failure: Failure | None = None
        for error in (self.reader.failure(), writer.failure):
            if error is not None:
                failure = prefer_failure(failure, error)
        if failure is not None:
            raise failure

    def finish_threads(self, threads: list[threading.Thread]) -> None:
        """Join helpers only after processing children have been stopped/reaped."""
        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=2)
        self.reader.complete = not threads[0].is_alive()
        if self.process.stdout is not None and self.reader.complete:
            self.process.stdout.close()
        if threads[1].is_alive():
            raise fail(code="IO_FAILURE")
        if self.process.stdin is not None:
            with suppress(BrokenPipeError):
                self.process.stdin.close()

    def finish(
        self,
        owner: NativeOwner,
        threads: list[threading.Thread],
        failure: Failure | None,
    ) -> Failure | None:
        """Attempt all cleanup while retaining truthful original failure precedence."""
        try:
            owner.cleanup()
        except BaseException as error:  # noqa: BLE001 -- cleanup must retain interruption and original failure.
            failure = prefer_failure(failure, error)
        try:
            self.finish_threads(threads)
        except BaseException as error:  # noqa: BLE001 -- never lose an earlier failure to transport cleanup.
            failure = prefer_failure(failure, error)
        return failure

    def run(self) -> None:
        """Keep the independent wait active even when a child or request pipe stalls."""
        self.reader.managed = True
        owner = NativeOwner(self.process)
        writer = PipeWriter(self.process, self.encoded, self.sender)
        threads = [
            threading.Thread(target=self.reader.read, daemon=True),
            threading.Thread(target=writer.run, daemon=True),
        ]
        failure: Failure | None = None
        try:
            active = owner.begin()
            self.start_thread(threads[0])
            if active:
                self.start_thread(threads[1])
                owner.wait(self.started + self.timeout, lambda: self.check(writer))
            elif self.process.stdin is not None:
                with suppress(BrokenPipeError):
                    self.process.stdin.close()
        except BaseException as error:  # noqa: BLE001 -- clean the owned group before returning any failure.
            failure = classify_failure(error)
        failure = self.finish(owner, threads, failure)
        try:
            self.check(writer)
        except (IntakeError, KeyboardInterrupt) as error:
            failure = prefer_failure(failure, error)
        if failure is not None:
            raise failure
