# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Kernel-scoped identity/race and resident-threshold observation contracts."""

import os
import signal
import subprocess
import sys
from contextlib import suppress
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from dscat.intake.limits import DEFAULT_LIMITS, IntakeError
from dscat.platform import observation
from dscat.platform.darwin import ProcessIdentity, ProcessMemory

if TYPE_CHECKING:
    from collections.abc import Generator

WORKER = 1234567
SMALL_RSS = 4096


@dataclass
class ModelKernel:
    """Typed test-owned kernel facts; no model PID is queried on the host."""

    identities: dict[int, ProcessIdentity | None] = field(default_factory=dict)
    memories: dict[int, ProcessMemory | None] = field(default_factory=dict)
    links: dict[int, list[int]] = field(default_factory=dict)
    identity_sequence: dict[int, list[ProcessIdentity | None]] = field(
        default_factory=dict
    )
    memory_queries: list[int] = field(default_factory=list)
    enumerations: list[int] = field(default_factory=list)

    def identity(self, pid: int) -> ProcessIdentity | None:
        """Model disappearance or identity changes across a memory sample."""
        pending = self.identity_sequence.get(pid)
        return pending.pop(0) if bool(pending) else self.identities.get(pid)

    def memory(self, pid: int) -> ProcessMemory | None:
        """Record which already-validated process identities are sampled."""
        self.memory_queries.append(pid)
        return self.memories.get(pid)

    def children(self, pid: int) -> list[int]:
        """Model only direct children of an explicitly selected owner."""
        self.enumerations.append(pid)
        return self.links.get(pid, [])


@dataclass
class Tree:
    """One real disposable owner and modelled kernel observations for fault tests."""

    process: subprocess.Popen[bytes]
    kernel: ModelKernel
    observer: observation.ResidentObserver
    coordinator: ProcessIdentity
    worker: ProcessIdentity


@pytest.fixture
def tree(monkeypatch: pytest.MonkeyPatch) -> Generator[Tree]:
    """Keep cleanup tied to a real child while fake IDs stay inside the model."""
    process = subprocess.Popen(
        [sys.executable, "-I", "-c", "import time;time.sleep(60)"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    kill_group = os.killpg
    wait = process.wait
    coordinator = ProcessIdentity(
        pid=process.pid,
        parent=os.getpid(),
        group=process.pid,
        created_seconds=1,
        created_microseconds=0,
    )
    worker = ProcessIdentity(
        pid=WORKER,
        parent=process.pid,
        group=process.pid,
        created_seconds=1,
        created_microseconds=1,
    )
    kernel = ModelKernel(
        identities={process.pid: coordinator, WORKER: worker},
        memories={
            process.pid: ProcessMemory(virtual_bytes=1000000, resident_bytes=SMALL_RSS),
            WORKER: ProcessMemory(virtual_bytes=2000000, resident_bytes=SMALL_RSS * 2),
        },
    )
    monkeypatch.setattr(observation, "NativeProcesses", lambda: kernel)
    try:
        observer = observation.ResidentObserver(process)
        yield Tree(process, kernel, observer, coordinator, worker)
    finally:
        with suppress(ProcessLookupError, PermissionError):
            kill_group(process.pid, signal.SIGKILL)
        wait(timeout=2)
        if process.stdin is not None:
            process.stdin.close()
        if process.stdout is not None:
            process.stdout.close()


def test_only_owned_tree_is_observed_and_peaks_are_retained(tree: Tree) -> None:
    """Serial-worker replacement does not accumulate old process contents."""
    tree.kernel.links[tree.process.pid] = [WORKER]
    tree.observer.observe()
    assert tree.observer.peak_coordinator == SMALL_RSS
    assert tree.observer.peak_worker == SMALL_RSS * 2
    assert set(tree.kernel.memory_queries) == {tree.process.pid, WORKER}
    tree.kernel.links[tree.process.pid] = []
    tree.observer.observe()
    assert tree.observer.peak_worker == SMALL_RSS * 2
    assert tree.observer.samples > 0


@pytest.mark.parametrize("fault", ["missing", "parent", "group"])
def test_bootstrap_rejects_unowned_or_missing_coordinator(
    tree: Tree, fault: str
) -> None:
    """Input forwarding cannot begin from an unverified ownership/group claim."""
    changed = (
        {"parent": os.getpid() + 1}
        if fault == "parent"
        else {"group": tree.process.pid + 1}
    )
    tree.kernel.identities[tree.process.pid] = (
        None if fault == "missing" else tree.coordinator.model_copy(update=changed)
    )
    with pytest.raises(IntakeError, match="RESOURCE_GUARD_UNAVAILABLE"):
        observation.ResidentObserver(tree.process)


@pytest.mark.parametrize("error", [OSError, AttributeError])
def test_unavailable_native_access_fails_before_observation(
    tree: Tree, monkeypatch: pytest.MonkeyPatch, error: type[Exception]
) -> None:
    """An absent library/signature is not replaced with unobserved execution."""

    def refuse() -> None:
        raise error

    monkeypatch.setattr(observation, "NativeProcesses", refuse)
    with pytest.raises(IntakeError, match="RESOURCE_GUARD_UNAVAILABLE"):
        observation.ResidentObserver(tree.process)


@pytest.mark.parametrize("position", ["before", "after"])
def test_identity_change_around_sample_is_rejected(tree: Tree, position: str) -> None:
    """A reused PID or changed parent/group cannot inherit a previous sample."""
    changed = tree.coordinator.model_copy(update={"created_seconds": 2})
    tree.kernel.identity_sequence[tree.process.pid] = (
        [changed] if position == "before" else [tree.coordinator, changed]
    )
    with pytest.raises(IntakeError, match="RESOURCE_GUARD_UNAVAILABLE"):
        tree.observer.observe()


@pytest.mark.parametrize("position", ["before", "after", "memory"])
def test_missing_coordinator_is_not_success(tree: Tree, position: str) -> None:
    """The owner must separately prove exit instead of accepting an absent sample."""
    if position == "memory":
        tree.kernel.memories[tree.process.pid] = None
    else:
        tree.kernel.identity_sequence[tree.process.pid] = (
            [None] if position == "before" else [tree.coordinator, None]
        )
    with pytest.raises(IntakeError, match="RESOURCE_GUARD_UNAVAILABLE"):
        tree.observer.observe()


@pytest.mark.parametrize("target", ["coordinator", "worker"])
def test_rss_above_threshold_stops_whole_operation(tree: Tree, target: str) -> None:
    """Observed over-budget use is operational failure, with no hard-cap claim."""
    tree.kernel.links[tree.process.pid] = [WORKER]
    pid = tree.process.pid if target == "coordinator" else WORKER
    tree.kernel.memories[pid] = ProcessMemory(
        virtual_bytes=1000000, resident_bytes=DEFAULT_LIMITS.memory + 1
    )
    with pytest.raises(IntakeError) as caught:
        tree.observer.observe()
    assert caught.value.diagnostic.limit == "memory"


@pytest.mark.parametrize("position", ["discovery", "before", "after", "memory"])
def test_vanished_worker_discards_sample_and_reenumerates(
    tree: Tree, position: str
) -> None:
    """A normal short-lived worker race cannot cause PID-based signaling."""
    tree.kernel.links[tree.process.pid] = [WORKER]
    if position == "memory":
        tree.kernel.memories[WORKER] = None
    else:
        tree.kernel.identity_sequence[WORKER] = {
            "discovery": [None],
            "before": [tree.worker, None],
            "after": [tree.worker, tree.worker, None],
        }[position]
    count = len(tree.kernel.enumerations)
    tree.observer.observe()
    assert len(tree.kernel.enumerations) > count + 1
    assert tree.observer.peak_worker == 0


@pytest.mark.parametrize("fault", ["multiple", "parent", "group", "descendant"])
def test_unexpected_process_topology_is_refused(tree: Tree, fault: str) -> None:
    """Unrelated/reparented children are rejected before their memory is sampled."""
    tree.kernel.links[tree.process.pid] = [WORKER]
    if fault == "multiple":
        tree.kernel.links[tree.process.pid].append(WORKER + 1)
    elif fault == "descendant":
        tree.kernel.links[WORKER] = [WORKER + 1]
    else:
        change = (
            {"parent": tree.process.pid + 1}
            if fault == "parent"
            else {"group": tree.process.pid + 1}
        )
        tree.kernel.identities[WORKER] = tree.worker.model_copy(update=change)
    with pytest.raises(IntakeError, match="RESOURCE_GUARD_UNAVAILABLE"):
        tree.observer.observe()
    if fault in {"parent", "group", "multiple"}:
        assert WORKER not in tree.kernel.memory_queries


@pytest.mark.parametrize("vanished", [False, True])
def test_failed_memory_query_requires_confirmed_disappearance(
    tree: Tree, monkeypatch: pytest.MonkeyPatch, *, vanished: bool
) -> None:
    """A query error is discarded only when a subsequent identity confirms exit."""
    tree.kernel.identity_sequence[WORKER] = [
        tree.worker,
        None if vanished else tree.worker,
    ]

    def refused(_pid: int) -> None:
        raise observation.fail(code="RESOURCE_GUARD_UNAVAILABLE")

    monkeypatch.setattr(tree.kernel, "memory", refused)
    if vanished:
        assert tree.observer.sample(tree.worker) is None
    else:
        with pytest.raises(IntakeError):
            tree.observer.sample(tree.worker)
