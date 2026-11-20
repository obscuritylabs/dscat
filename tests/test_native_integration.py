# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Real native macOS stalls, orphan cleanup, resident observation and retry."""

import json
import sys
import threading
import time
from typing import TYPE_CHECKING

import pytest

from dscat.intake import worker
from dscat.intake.discovery import DiscoveryRequest
from dscat.intake.limits import IntakeError, Limits
from dscat.models.configuration import AssessmentConfiguration, LocalRule
from dscat.platform import observation, supervision
from dscat.platform.darwin import NativeProcesses
from tests.test_workers import launch_script

if TYPE_CHECKING:
    import subprocess
    from collections.abc import Callable
    from pathlib import Path

MAX_TEST_SECONDS = 5

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin", reason="Real native macOS supervision evidence."
)


def request(path: Path, *, large: bool = False) -> worker.CoordinatorRequest:
    """Create a valid comparison operand exceeding pipe buffering capacity."""
    configuration = AssessmentConfiguration()
    if large:
        configuration = AssessmentConfiguration(
            rules=[
                LocalRule(
                    id="check", path="title", operator="equals", operand="x" * 1024**2
                )
            ]
        )
    return worker.CoordinatorRequest(
        schema_version="1.0",
        role="coordinator",
        discovery=DiscoveryRequest(input=path),
        assessment=configuration,
    )


def assert_quiescent_before_reap(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    """Bind real group liveness and main-thread ownership to the actual wait call."""
    original_launch = worker.launch_process
    observed: list[bool] = []

    def launch(*, coordinator: bool) -> subprocess.Popen[bytes]:
        process = original_launch(coordinator=coordinator)
        original_wait = process.wait

        def wait(timeout: float | None = None) -> int:
            assert threading.current_thread() is threading.main_thread()
            native = NativeProcesses()
            assert all(
                native.process_exited(pid) for pid in native.group_members(process.pid)
            )
            observed.append(True)
            return original_wait(timeout=timeout)

        monkeypatch.setattr(process, "wait", wait)
        return process

    monkeypatch.setattr(worker, "launch_process", launch)
    return observed


@pytest.mark.parametrize("large", [False, True])
def test_native_gil_and_blocked_request_cannot_suppress_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, large: bool
) -> None:
    """The outer owner can stop a GIL-held receiver even while its writer blocks."""
    processes = launch_script(monkeypatch, "import ctypes;ctypes.PyDLL(None).sleep(60)")
    reaps = assert_quiescent_before_reap(monkeypatch)
    started = time.monotonic()
    with pytest.raises(IntakeError) as caught:
        worker.invoke(request(tmp_path, large=large), 0.2)
    assert caught.value.diagnostic.limit == "invocation_time"
    assert time.monotonic() - started < MAX_TEST_SECONDS
    assert processes[0].returncode is not None
    assert reaps == [True]


@pytest.mark.parametrize("scenario", ["worker_gil", "parent_exit"])
def test_native_group_cleanup_handles_live_orphan_before_reap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str
) -> None:
    """A dying coordinator does not leave a worker holding its reply pipe open."""
    marker = tmp_path / "spawned.json"
    leaf = "import ctypes;ctypes.PyDLL(None).sleep(60)"
    tail = (
        "os._exit(7)" if scenario == "parent_exit" else "ctypes.PyDLL(None).sleep(60)"
    )
    script = (
        "import ctypes,json,os,subprocess,sys;from pathlib import Path;"
        "sys.stdin.buffer.read();"
        f"p=subprocess.Popen([sys.executable,'-I','-c',{leaf!r}]);"
        f"Path({str(marker)!r}).write_text(json.dumps({{'spawned':True}}));" + tail
    )
    processes = launch_script(monkeypatch, script)
    reaps = assert_quiescent_before_reap(monkeypatch)
    with pytest.raises(IntakeError) as caught:
        worker.invoke(request(tmp_path), 0.5 if scenario == "worker_gil" else 5)
    if scenario == "worker_gil":
        assert caught.value.diagnostic.limit == "invocation_time"
    else:
        assert caught.value.diagnostic.code == "WORKER_FAILURE"
    assert json.loads(marker.read_bytes()) == {"spawned": True}
    assert processes[0].returncode is not None
    assert reaps == [True]


def test_native_resident_counter_triggers_bounded_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    """A conservative test threshold exercises real resident sampling safely."""
    budget = 32 * 1024**2
    monkeypatch.setattr(observation, "DEFAULT_LIMITS", Limits(memory=budget))
    original = supervision.ResidentObserver
    observers: list[observation.ResidentObserver] = []

    def monitored(process: subprocess.Popen[bytes]) -> observation.ResidentObserver:
        result = original(process)
        observers.append(result)
        return result

    monkeypatch.setattr(supervision, "ResidentObserver", monitored)
    # The controlled process allocates only 64 MiB, below the production budget.
    processes = launch_script(
        monkeypatch,
        (
            "import sys,time;sys.stdin.buffer.read();"
            "x=bytearray(64*1024**2);time.sleep(60)"
        ),
    )
    reaps = assert_quiescent_before_reap(monkeypatch)
    with pytest.raises(IntakeError) as caught:
        worker.invoke(request(tmp_path), 5)
    assert caught.value.diagnostic.limit == "memory"
    assert processes[0].returncode is not None
    assert reaps == [True]
    peak = max(observers[0].peak_coordinator, observers[0].peak_worker)
    assert peak > budget
    record_property("resident_threshold_bytes", budget)
    record_property("observed_peak_bytes", peak)
    record_property("observed_overshoot_bytes", peak - budget)
    record_property(
        "maximum_observation_interval_seconds", observers[0].maximum_interval
    )


def test_native_terminal_group_and_child_enumeration_are_real(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kernel child counts and zombie-only group cleanup cannot use byte units."""
    outcome = worker.WorkerReply(
        schema_version="1.0",
        role="coordinator",
        catalog=worker.Catalog(schema_version="1.0", datasets=[]),
        assessment=worker.ValidationAssessment(validity="valid"),
        has_errors=False,
        selection_complete=True,
    )
    script = (
        "import sys;sys.stdin.buffer.read();sys.stdout.buffer.write("
        + repr(outcome.model_dump_json(exclude_none=True).encode())
        + ")"
    )
    processes = launch_script(monkeypatch, script)
    reaps = assert_quiescent_before_reap(monkeypatch)
    assert not worker.invoke(request(tmp_path), 5).has_errors
    assert processes[0].returncode == 0
    assert reaps == [True]
