# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Kernel-scoped resident observation of the owned coordinator and serial worker."""

import os
import time
from typing import TYPE_CHECKING

from dscat.intake.limits import DEFAULT_LIMITS, IntakeError, fail
from dscat.platform.darwin import NativeProcesses

if TYPE_CHECKING:
    import subprocess

    from dscat.platform.darwin import ProcessIdentity, ProcessMemory


class ResidentObserver:
    """Observe only known kernel children; never signal sampled numeric worker PIDs."""

    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        """Establish native access and lifecycle identity before forwarding input."""
        try:
            self.native = NativeProcesses()
        except OSError, AttributeError:
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE") from None
        identity = self.native.identity(process.pid)
        if identity is None or (
            identity.parent != os.getpid() or identity.group != process.pid
        ):
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
        self.coordinator = identity
        self.peak_coordinator = 0
        self.peak_worker = 0
        self.samples = 0
        self.last_observed: float | None = None
        self.maximum_interval = 0.0
        self.observe()

    def sample(self, expected: ProcessIdentity) -> ProcessMemory | None:
        """Validate both sides of each sample instead of trusting a cached PID."""
        before = self.native.identity(expected.pid)
        if before is None:
            return None
        if before != expected:
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
        try:
            memory = self.native.memory(expected.pid)
        except IntakeError:
            if self.native.identity(expected.pid) is None:
                return None
            raise
        after = self.native.identity(expected.pid)
        if memory is None or after is None:
            return None
        if after != expected:
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
        if expected.pid == self.coordinator.pid:
            self.peak_coordinator = max(self.peak_coordinator, memory.resident_bytes)
        else:
            self.peak_worker = max(self.peak_worker, memory.resident_bytes)
        if memory.resident_bytes > DEFAULT_LIMITS.memory:
            raise fail(code="INPUT_LIMIT", limit="memory")
        return memory

    def children(self) -> list[int]:
        """Require at most one live worker for the serial coordinator."""
        children = self.native.children(self.coordinator.pid)
        if len(children) > 1:
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
        return children

    def worker_sample(self) -> int:
        """Discard vanished workers and re-enumerate without signaling their PIDs."""
        children = self.children()
        if not children:
            return 0
        identity = self.native.identity(children[0])
        if identity is None:
            self.children()
            return 0
        if (
            identity.parent != self.coordinator.pid
            or identity.group != self.coordinator.pid
        ):
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
        memory = self.sample(identity)
        if memory is None:
            self.children()
            return 0
        if self.native.children(identity.pid):
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
        return memory.resident_bytes

    def observe(self) -> None:
        """Record bounded peaks; sampling is detection and can overshoot its target."""
        observed = time.monotonic()
        if self.last_observed is not None:
            self.maximum_interval = max(
                self.maximum_interval, observed - self.last_observed
            )
        self.last_observed = observed
        coordinator = self.sample(self.coordinator)
        if coordinator is None:
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
        self.worker_sample()
        self.samples += 1
