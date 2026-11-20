# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Native process-memory guards, verified before reading untrusted content."""

import sys
from typing import Literal

from dscat.intake.limits import DEFAULT_LIMITS, IntakeError, fail
from dscat.models.base import StrictModel
from dscat.platform.darwin import MapLimit, verify_growth
from dscat.platform.darwin import ResourceGuard as DarwinGuard
from dscat.platform.posix import ResourceGuard as PosixGuard
from dscat.platform.windows import ResourceGuard as WindowsGuard


class GuardReceipt(StrictModel):
    """Actual per-process enforcement evidence, distinct from platform acceptance."""

    platform: Literal["linux", "darwin", "win32"]
    mechanism: Literal[
        "rlimit_as", "darwin_rlimit_as_growth", "windows_job_process_memory"
    ]
    budget_bytes: int
    enforcement_verified: bool
    map_limit: MapLimit | None = None


_guard: GuardReceipt | None = None
_windows_guard: object | None = None


def allocate_probe() -> bytearray:
    """Attempt one bounded, known allocation before processing untrusted content."""
    return bytearray(DEFAULT_LIMITS.memory + 1)


def verify_enforcement() -> None:
    """Verify actual memory refusal without adding a third process to the topology."""
    try:
        allocation = allocate_probe()
    except MemoryError, OSError:
        return
    del allocation
    raise fail(code="RESOURCE_GUARD_UNAVAILABLE")


def install_guard() -> GuardReceipt:
    """Install and verify the native guard or fail before reading any input content."""
    global _guard, _windows_guard  # noqa: PLW0603 -- process-lifetime native guard ownership.
    if _guard is not None:
        return _guard
    selected: MapLimit | None = None
    try:
        if sys.platform == "darwin":
            selected = DarwinGuard().install()
            verify_growth(selected)
            mechanism = "darwin_rlimit_as_growth"
        elif sys.platform == "linux":
            PosixGuard().install()
            mechanism = "rlimit_as"
        elif sys.platform == "win32":
            _windows_guard = WindowsGuard()
            _windows_guard.install()
            mechanism = "windows_job_process_memory"
        else:
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
        if selected is None:
            verify_enforcement()
    except IntakeError:
        raise
    except OSError, ValueError, MemoryError, ImportError, AttributeError:
        raise fail(code="RESOURCE_GUARD_UNAVAILABLE") from None
    receipt = GuardReceipt.model_validate(
        {
            "platform": sys.platform,
            "mechanism": mechanism,
            "budget_bytes": DEFAULT_LIMITS.memory,
            "enforcement_verified": True,
            **({"map_limit": selected} if selected is not None else {}),
        }
    )
    _guard = receipt
    return receipt
