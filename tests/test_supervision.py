# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Non-reaping ownership, bounded deadlines and truthful group cleanup failures."""

import os
import signal
import subprocess
import sys
import time
from contextlib import suppress
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from dscat.intake.limits import IntakeError, fail
from dscat.platform import supervision

if TYPE_CHECKING:
    from collections.abc import Generator


@dataclass
class ModelObservation:
    """Model observation failures while real wait/signal ownership is exercised."""

    samples: int = 0
    error: IntakeError | None = None
    is_terminal: bool = False

    def terminal(self) -> bool:
        """Model a confirmed BSD zombie independently of waitid visibility."""
        return self.is_terminal

    def observe(self) -> None:
        """Count independent wait-loop progress or inject a fixed safe failure."""
        self.samples += 1
        if self.error is not None:
            raise self.error


@dataclass
class ModelGroup:
    """Model group membership only; these IDs are never individually signaled."""

    members: list[int] = field(default_factory=list)
    terminal: bool = True

    def group_members(self, _group: int) -> list[int]:
        """Return bounded test-owned group facts."""
        return self.members

    def process_exited(self, _pid: int) -> bool:
        """Distinguish a terminal adopted child from still-live group work."""
        return self.terminal


@dataclass
class OwnerCase:
    """A real disposable child with controlled observation/group backends."""

    process: subprocess.Popen[bytes]
    owner: supervision.NativeOwner
    observation: ModelObservation
    group: ModelGroup


@pytest.fixture
def owned(monkeypatch: pytest.MonkeyPatch) -> Generator[OwnerCase]:
    """Keep every unit failure tied to a child that the fixture can finally reap."""
    child = subprocess.Popen(
        [sys.executable, "-I", "-c", "import time;time.sleep(60)"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    original_wait = child.wait
    original_kill = os.killpg
    monitor = ModelObservation()
    group = ModelGroup([child.pid])
    monkeypatch.setattr(supervision, "ResidentObserver", lambda _process: monitor)
    monkeypatch.setattr(supervision, "NativeProcesses", lambda: group)
    try:
        yield OwnerCase(child, supervision.NativeOwner(child), monitor, group)
    finally:
        with suppress(ProcessLookupError, PermissionError):
            original_kill(child.pid, signal.SIGKILL)
        original_wait(timeout=2)
        for stream in (child.stdin, child.stdout):
            if stream is not None:
                stream.close()


def make_terminal(case: OwnerCase) -> None:
    """Stop a known child but deliberately preserve its unreaped identity."""
    os.kill(case.process.pid, signal.SIGKILL)
    deadline = time.monotonic() + 2
    while not case.owner.exited():
        if time.monotonic() > deadline:
            pytest.fail("Disposable child did not reach terminal state.")
        time.sleep(0.001)


@pytest.mark.parametrize("missing", ["waitid", "WNOWAIT"])
def test_missing_nonreaping_api_refuses_before_launch(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    """A platform without the required ownership primitive cannot run this path."""
    monkeypatch.delattr(supervision.os, missing)
    with pytest.raises(IntakeError) as caught:
        supervision.require_waiting()
    assert caught.value.expanded_upper_bound == 0


def test_live_wait_observes_and_times_out_without_reaping(owned: OwnerCase) -> None:
    """The outer wait remains active independently of a child interpreter."""
    assert owned.owner.begin()
    with pytest.raises(IntakeError) as caught:
        owned.owner.wait(time.monotonic() + 0.03, lambda: None)
    assert caught.value.diagnostic.limit == "invocation_time"
    assert owned.observation.samples > 0
    assert owned.process.returncode is None
    owned.owner.cleanup()
    assert owned.process.returncode is not None


def test_already_exited_owner_keeps_identity_until_cleanup(owned: OwnerCase) -> None:
    """WNOWAIT is not equivalent to an early Popen.poll/wait reap."""
    make_terminal(owned)
    assert not owned.owner.begin()
    assert owned.process.returncode is None
    owned.owner.cleanup()
    assert owned.process.returncode is not None
    assert not owned.owner.has_anchor()


def test_failed_isolation_cleans_only_owned_startup_child(
    owned: OwnerCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No unverified group may be signaled when startup isolation is absent."""
    monkeypatch.setattr(supervision.os, "getpgid", lambda _pid: owned.process.pid + 1)
    with pytest.raises(IntakeError, match="RESOURCE_GUARD_UNAVAILABLE"):
        owned.owner.begin()
    assert not owned.owner.isolated
    owned.owner.cleanup()
    assert owned.process.returncode is not None


@pytest.mark.parametrize("terminal", [False, True])
def test_bootstrap_observer_error_checks_exit_race(
    owned: OwnerCase, monkeypatch: pytest.MonkeyPatch, *, terminal: bool
) -> None:
    """An exited refusal is distinguished from failed access to a live receiver."""

    def refuse(_process: subprocess.Popen[bytes]) -> None:
        if terminal:
            make_terminal(owned)
        raise fail(code="RESOURCE_GUARD_UNAVAILABLE")

    monkeypatch.setattr(supervision, "ResidentObserver", refuse)
    if terminal:
        assert not owned.owner.begin()
    else:
        with pytest.raises(IntakeError):
            owned.owner.begin()
    owned.owner.cleanup()


def test_live_observation_failure_is_not_success(owned: OwnerCase) -> None:
    """Failed native measurement stops the operation even when the child is alive."""
    assert owned.owner.begin()
    owned.observation.error = fail(code="RESOURCE_GUARD_UNAVAILABLE")
    with pytest.raises(IntakeError):
        owned.owner.wait(time.monotonic() + 2, lambda: None)
    owned.owner.cleanup()


def test_wait_cannot_run_without_observation(owned: OwnerCase) -> None:
    """A missing observer is not treated as permission to continue unmonitored."""
    with pytest.raises(IntakeError):
        owned.owner.wait(time.monotonic() + 2, lambda: None)


def test_lost_anchor_never_signals_numeric_group(
    owned: OwnerCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """External-reap failure cannot turn a recycled PID into a cleanup target."""

    def reaped(*_args: object) -> None:
        raise ChildProcessError

    monkeypatch.setattr(supervision.os, "waitid", reaped)
    with pytest.raises(IntakeError):
        owned.owner.exited()
    assert not owned.owner.has_anchor()
    with pytest.raises(IntakeError, match="IO_FAILURE"):
        owned.owner.signal_group(signal.SIGKILL)
    with pytest.raises(IntakeError, match="IO_FAILURE"):
        owned.owner.cleanup()


def test_foreign_wait_result_is_refused(
    owned: OwnerCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the selected direct-child wait identity may complete observation."""
    wrong = os.waitid_result(
        (owned.process.pid + 1, 1, signal.SIGCHLD, 0, os.CLD_EXITED)
    )
    monkeypatch.setattr(supervision.os, "waitid", lambda *_args: wrong)
    with pytest.raises(IntakeError):
        owned.owner.exited()


@pytest.mark.parametrize("terminal", [False, True])
def test_permission_error_requires_terminal_group_proof(
    owned: OwnerCase, monkeypatch: pytest.MonkeyPatch, *, terminal: bool
) -> None:
    """A live signaling failure is fatal; Darwin's terminal-only case is verified."""
    assert owned.owner.begin()
    if terminal:
        make_terminal(owned)

    def denied(_group: int, _signal: int) -> None:
        raise PermissionError

    monkeypatch.setattr(supervision.os, "killpg", denied)
    if terminal:
        owned.owner.signal_group(signal.SIGKILL)
    else:
        with pytest.raises(PermissionError):
            owned.owner.signal_group(signal.SIGKILL)


@pytest.mark.parametrize("terminal", [False, True])
def test_orphan_state_is_distinct_from_coordinator_reap(
    owned: OwnerCase, *, terminal: bool
) -> None:
    """A zombie adopted worker is quiescent; a live one still needs termination."""
    make_terminal(owned)
    owned.group.members.append(1234567)
    owned.group.terminal = terminal
    assert owned.owner.quiescent_group() is terminal


@pytest.mark.parametrize(
    "error",
    [subprocess.TimeoutExpired("fixture", 2), RuntimeError("synthetic wait error")],
)
def test_failed_reap_is_not_claimed_success(
    owned: OwnerCase, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    """All cleanup failures retain a nonzero fixed classification."""
    assert owned.owner.begin()

    def refused(*_args: object, **_kwargs: object) -> None:
        raise error

    monkeypatch.setattr(owned.process, "wait", refused)
    with pytest.raises(IntakeError):
        owned.owner.cleanup()
    assert not owned.owner.has_anchor()


def test_unterminated_group_has_bounded_failure(
    owned: OwnerCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unchanged live group cannot be reported stopped indefinitely."""
    observations = iter([0.0, supervision.REAP_SECONDS + 1])
    monkeypatch.setattr(supervision.time, "monotonic", lambda: next(observations))
    with pytest.raises(IntakeError, match="IO_FAILURE"):
        owned.owner.await_quiescence()


def test_exit_during_isolation_check_is_a_terminal_refusal(
    owned: OwnerCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A process disappearing during startup is handled before forwarding input."""

    def disappeared(_pid: int) -> int:
        make_terminal(owned)
        return owned.process.pid + 1

    monkeypatch.setattr(supervision.os, "getpgid", disappeared)
    assert not owned.owner.begin()
    owned.owner.cleanup()


def test_exit_during_observation_ends_wait(
    owned: OwnerCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A final missing sample is accepted only after non-reaping exit proof."""
    assert owned.owner.begin()

    def exited() -> None:
        make_terminal(owned)
        raise fail(code="RESOURCE_GUARD_UNAVAILABLE")

    monkeypatch.setattr(owned.observation, "observe", exited)
    owned.owner.wait(time.monotonic() + 2, lambda: None)
    owned.owner.cleanup()


@pytest.mark.parametrize("phase", ["stop_group", "await_quiescence"])
def test_cleanup_retains_errors_and_still_reaps(
    owned: OwnerCase, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    """Failure to prove cleanup cannot suppress the bounded direct-child reap."""
    assert owned.owner.begin()
    make_terminal(owned)

    def refused() -> None:
        msg = "synthetic cleanup failure"
        raise RuntimeError(msg)

    monkeypatch.setattr(owned.owner, phase, refused)
    with pytest.raises(IntakeError, match="INTERNAL_FAILURE"):
        owned.owner.cleanup()
    assert owned.process.returncode is not None


def test_quiescence_rechecks_after_live_group(
    owned: OwnerCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An initially live group is checked again before releasing ownership."""
    answers = iter([False, True])
    monkeypatch.setattr(owned.owner, "quiescent_group", lambda: next(answers))
    owned.owner.await_quiescence()


def test_terminal_measurement_waits_for_nonreaping_exit_visibility(
    owned: OwnerCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BSD terminal state may precede the waitid event; ownership stays anchored."""
    assert owned.owner.begin()
    make_terminal(owned)
    answers = iter([False, False, False, True])
    monkeypatch.setattr(owned.owner, "exited", lambda: next(answers))
    owned.observation.error = fail(code="RESOURCE_GUARD_UNAVAILABLE")
    owned.observation.is_terminal = True
    owned.owner.wait(time.monotonic() + 2, lambda: None)
    assert owned.process.returncode is None


def test_terminal_transition_wait_is_bounded(
    owned: OwnerCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing wait event still fails without releasing the ownership anchor."""
    monkeypatch.setattr(owned.owner, "exited", lambda: False)
    with pytest.raises(IntakeError, match="RESOURCE_GUARD_UNAVAILABLE"):
        owned.owner.await_exit(time.monotonic() - 1)
    assert owned.owner.has_anchor()
