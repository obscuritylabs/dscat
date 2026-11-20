# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Independent native waiting and process-group cleanup before coordinator reap."""

import os
import signal
import subprocess
import time
from contextlib import suppress
from typing import TYPE_CHECKING

from dscat.intake.limits import (
    Failure,
    IntakeError,
    classify_failure,
    fail,
    prefer_failure,
)
from dscat.platform.darwin import NativeProcesses
from dscat.platform.observation import ResidentObserver

if TYPE_CHECKING:
    from collections.abc import Callable

POLL_SECONDS = 0.02
GRACE_SECONDS = 1.0
REAP_SECONDS = 2.0


def require_waiting() -> None:
    """Refuse unsupported non-reaping observation before creating a child."""
    if not callable(getattr(os, "waitid", None)) or not all(
        hasattr(os, name)
        for name in ("waitid", "P_PID", "WEXITED", "WNOHANG", "WNOWAIT")
    ):
        raise fail(code="RESOURCE_GUARD_UNAVAILABLE", expanded_upper_bound=0)


class NativeOwner:
    """Keep the direct child unreaped until its isolated group has been stopped."""

    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        """Retain the Popen ownership anchor; no thread may call wait or poll."""
        self.process = process
        self.anchored = True
        self.isolated = False
        self.observer: ResidentObserver | None = None

    def has_anchor(self) -> bool:
        """Recheck ownership after helpers that can observe external reap failure."""
        return self.anchored

    def exited(self) -> bool:
        """Check only this owned child with WNOWAIT, preserving its PID identity."""
        try:
            result = os.waitid(
                os.P_PID, self.process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT
            )
        except ChildProcessError:
            self.anchored = False
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE") from None
        if result is not None and result.si_pid not in {0, self.process.pid}:
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
        return result is not None and result.si_pid == self.process.pid

    def begin(self) -> bool:
        """Establish kernel observation before a writer may forward request bytes."""
        exited = self.exited()
        with suppress(ProcessLookupError):
            self.isolated = os.getpgid(self.process.pid) == self.process.pid
        if exited:
            return False
        if not self.isolated:
            if self.exited():
                return False
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
        try:
            self.observer = ResidentObserver(self.process)
        except IntakeError:
            if self.exited():
                return False
            raise
        return True

    def wait(self, deadline: float, check_transport: Callable[[], None]) -> None:
        """Keep observation/deadlines in the owner's main thread, outside child GILs."""
        while not self.exited():
            check_transport()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise fail(code="INPUT_LIMIT", limit="invocation_time")
            if self.observer is None:
                raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
            try:
                self.observer.observe()
            except IntakeError:
                if self.exited():
                    return
                if self.observer.terminal():
                    self.await_exit(deadline)
                    return
                raise
            time.sleep(min(POLL_SECONDS, remaining))

    def await_exit(self, invocation_deadline: float) -> None:
        """Bound the kernel terminal-state to WNOWAIT visibility transition."""
        deadline = min(invocation_deadline, time.monotonic() + REAP_SECONDS)
        while not self.exited():
            if time.monotonic() >= deadline:
                raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
            time.sleep(POLL_SECONDS)

    def signal_group(self, signum: int) -> None:
        """Signal the owned anchored group, never an asynchronously sampled worker."""
        if not self.anchored or not self.isolated:
            raise fail(code="IO_FAILURE")
        with suppress(ProcessLookupError):
            try:
                os.killpg(self.process.pid, signum)
            except PermissionError:
                # XNU skips zombies when signaling a group and can return EPERM
                # when only terminal members remain. Never ignore a live failure.
                if not self.quiescent_group():
                    raise

    def quiescent_group(self) -> bool:
        """Prove that an anchored exited leader has no remaining live group work."""
        if not self.exited():
            return False
        native = NativeProcesses()
        return all(
            pid == self.process.pid or native.process_exited(pid)
            for pid in native.group_members(self.process.pid)
        )

    def cleanup(self) -> None:
        """Give normal reap a chance, then kill remaining group members before wait."""
        if not self.anchored:
            raise fail(code="IO_FAILURE")
        failure: Failure | None = None
        try:
            if self.isolated:
                self.stop_group()
            else:
                # Isolation failed before input. Only this unreaped direct child,
                # never an unverified group, may be signaled during startup unwind.
                with suppress(ProcessLookupError):
                    os.kill(self.process.pid, signal.SIGKILL)
        except BaseException as error:  # noqa: BLE001 -- attempt bounded final cleanup for every failure.
            failure = classify_failure(error)
        if self.isolated and self.has_anchor():
            try:
                self.await_quiescence()
            except BaseException as error:  # noqa: BLE001 -- preserve higher-priority interruption/internal errors.
                failure = prefer_failure(failure, error)
        try:
            self.process.wait(timeout=REAP_SECONDS)
        except subprocess.TimeoutExpired:
            failure = prefer_failure(failure, fail(code="IO_FAILURE"))
        except BaseException as error:  # noqa: BLE001 -- never claim a failed reap succeeded.
            failure = prefer_failure(failure, error)
        finally:
            self.anchored = False
        if failure is not None:
            raise failure

    def stop_group(self) -> None:
        """Stop the anchored isolated group, including orphaned processing workers."""
        try:
            self.signal_group(signal.SIGTERM)
            deadline = time.monotonic() + GRACE_SECONDS
            while not self.exited() and time.monotonic() < deadline:
                time.sleep(POLL_SECONDS)
        finally:
            # Even an exited coordinator may have orphaned group members. Force
            # the anchored group down even when graceful observation failed.
            self.signal_group(signal.SIGKILL)

    def await_quiescence(self) -> None:
        """Confirm terminal group state before releasing the owned leader's identity."""
        deadline = time.monotonic() + REAP_SECONDS
        while not self.quiescent_group():
            if time.monotonic() >= deadline:
                raise fail(code="IO_FAILURE")
            time.sleep(POLL_SECONDS)
