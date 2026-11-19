# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Guard refusal, allocation verification and native API wiring contracts."""

import ctypes
import sys
from dataclasses import dataclass, field

import pytest

import dscat.platform as guards
from dscat.intake.limits import DEFAULT_LIMITS, IntakeError
from dscat.platform.posix import ResourceGuard as PosixGuard
from dscat.platform.windows import (
    KILL_ON_JOB_CLOSE,
    PROCESS_MEMORY,
    BasicLimits,
    ExtendedLimits,
    load_kernel,
)
from dscat.platform.windows import (
    ResourceGuard as WindowsGuard,
)

ABI_BASIC_BYTES = 64
ABI_EXTENDED_BYTES = 144
EXPECTED_HANDLE = 7


def test_posix_limit_installation_and_readback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both native limits are hard-set and an ignored/readback mismatch is refused."""
    resource = pytest.importorskip(
        "resource", reason="POSIX adapter; Windows uses Job Objects."
    )
    calls: list[tuple[int, tuple[int, int]]] = []

    def install(kind: int, values: tuple[int, int]) -> None:
        calls.append((kind, values))

    monkeypatch.setattr(resource, "setrlimit", install)
    monkeypatch.setattr(
        resource,
        "getrlimit",
        lambda _kind: (DEFAULT_LIMITS.memory, DEFAULT_LIMITS.memory),
    )
    PosixGuard().install()
    assert calls == [
        (resource.RLIMIT_AS, (DEFAULT_LIMITS.memory, DEFAULT_LIMITS.memory))
    ]
    monkeypatch.setattr(resource, "getrlimit", lambda _kind: (-1, -1))
    with pytest.raises(IntakeError, match="RESOURCE_GUARD_UNAVAILABLE"):
        PosixGuard().install()


@pytest.mark.parametrize("system", ["linux", "darwin", "win32"])
def test_enforcement_receipt_requires_actual_refusal(
    monkeypatch: pytest.MonkeyPatch, system: str
) -> None:
    """Unit wiring produces a receipt only after the allocation check refuses."""
    monkeypatch.setattr(guards, "_guard", None)
    monkeypatch.setattr(guards, "_windows_guard", None)
    monkeypatch.setattr(sys, "platform", system)
    monkeypatch.setattr(PosixGuard, "install", lambda _self: None)
    monkeypatch.setattr(WindowsGuard, "__init__", lambda _self: None)
    monkeypatch.setattr(WindowsGuard, "install", lambda _self: None)

    def refuse() -> bytearray:
        msg = "Synthetic allocation refusal"
        raise MemoryError(msg)

    monkeypatch.setattr(guards, "allocate_probe", refuse)
    receipt = guards.install_guard()
    assert receipt.enforcement_verified
    assert receipt.budget_bytes == 512 * 1024**2
    assert receipt.platform == system
    assert guards.install_guard() is receipt


def test_ignored_enforcement_and_unsupported_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refuse nominal guards that accept an oversized allocation."""
    monkeypatch.setattr(guards, "allocate_probe", bytearray)
    with pytest.raises(IntakeError, match="RESOURCE_GUARD_UNAVAILABLE"):
        guards.verify_enforcement()
    monkeypatch.setattr(guards, "_guard", None)
    monkeypatch.setattr(sys, "platform", "unsupported")
    with pytest.raises(IntakeError, match="RESOURCE_GUARD_UNAVAILABLE"):
        guards.install_guard()


def test_probe_requests_an_oversized_bounded_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Request an oversized allocation rather than an allowed amount."""
    requested: list[int] = []

    def allocation(size: int) -> bytearray:
        requested.append(size)
        return bytearray()

    monkeypatch.setattr(guards, "bytearray", allocation, raising=False)
    guards.allocate_probe()
    assert requested == [512 * 1024**2 + 1]


@pytest.mark.parametrize(
    "error", [OSError, ValueError, MemoryError, ImportError, AttributeError]
)
def test_native_setup_errors_fail_closed(
    monkeypatch: pytest.MonkeyPatch, error: type[Exception]
) -> None:
    """Unavailable/refused native APIs are not silently replaced with a weaker guard."""
    monkeypatch.setattr(guards, "_guard", None)
    monkeypatch.setattr(sys, "platform", "linux")

    def unavailable(_self: PosixGuard) -> None:
        msg = "Synthetic native failure"
        raise error(msg)

    monkeypatch.setattr(PosixGuard, "install", unavailable)
    with pytest.raises(IntakeError, match="RESOURCE_GUARD_UNAVAILABLE"):
        guards.install_guard()


@dataclass
class NativeCall:
    """Test-owned native calls; these do not establish Windows acceptance."""

    name: str
    fail_at: str
    calls: list[str]
    handle: int | None = 7
    observed_flags: int = PROCESS_MEMORY | KILL_ON_JOB_CLOSE
    observed_memory: int = DEFAULT_LIMITS.memory
    argtypes: list[object] = field(default_factory=list)
    restype: object = None

    def __call__(self, *arguments: object) -> int | None:
        """Record setup, emulate readback and selectively fail one native operation."""
        self.calls.append(self.name)
        if self.name == self.fail_at:
            return 0
        if self.name == "CreateJobObjectW":
            return self.handle
        if self.name == "QueryInformationJobObject":
            observed = getattr(arguments[2], "_obj", None)
            assert isinstance(observed, ExtendedLimits)
            observed.basic.limit_flags = self.observed_flags
            observed.process_memory = self.observed_memory
        return 1


def fake_kernel(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fail_at: str = "",
    handle: int | None = 7,
    flags: int = PROCESS_MEMORY | KILL_ON_JOB_CLOSE,
    memory: int = DEFAULT_LIMITS.memory,
) -> list[str]:
    """Exercise native bridge wiring without executing Windows calls on another OS."""
    library = ctypes.CDLL(None)
    calls: list[str] = []
    for name in (
        "CreateJobObjectW",
        "SetInformationJobObject",
        "AssignProcessToJobObject",
        "GetCurrentProcess",
        "QueryInformationJobObject",
        "CloseHandle",
    ):
        monkeypatch.setattr(
            library,
            name,
            NativeCall(name, fail_at, calls, handle, flags, memory),
            raising=False,
        )
    monkeypatch.setattr("dscat.platform.windows.load_kernel", lambda: library)
    return calls


def test_windows_struct_layout_and_successful_wiring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Check native flag wiring and ABI field widths."""
    assert ctypes.sizeof(BasicLimits) == ABI_BASIC_BYTES
    assert ctypes.sizeof(ExtendedLimits) == ABI_EXTENDED_BYTES
    calls = fake_kernel(monkeypatch)
    guard = WindowsGuard()
    guard.install()
    assert guard.handle == EXPECTED_HANDLE
    assert calls == [
        "CreateJobObjectW",
        "SetInformationJobObject",
        "GetCurrentProcess",
        "AssignProcessToJobObject",
        "QueryInformationJobObject",
    ]
    assert "CloseHandle" not in calls


@pytest.mark.parametrize(
    "fail_at",
    [
        "CreateJobObjectW",
        "SetInformationJobObject",
        "AssignProcessToJobObject",
        "QueryInformationJobObject",
    ],
)
def test_windows_native_call_refusal(
    monkeypatch: pytest.MonkeyPatch, fail_at: str
) -> None:
    """No failed native operation can yield a verified guard receipt."""
    calls = fake_kernel(monkeypatch, fail_at=fail_at)
    with pytest.raises(IntakeError, match="RESOURCE_GUARD_UNAVAILABLE"):
        WindowsGuard().install()
    if fail_at in {"SetInformationJobObject", "AssignProcessToJobObject"}:
        assert calls[-1] == "CloseHandle"


@pytest.mark.parametrize(
    ("handle", "flags", "memory"),
    [
        (None, PROCESS_MEMORY | KILL_ON_JOB_CLOSE, DEFAULT_LIMITS.memory),
        (7, 0, DEFAULT_LIMITS.memory),
        (7, PROCESS_MEMORY | KILL_ON_JOB_CLOSE, 1),
    ],
)
def test_windows_missing_handle_and_wrong_readback(
    monkeypatch: pytest.MonkeyPatch, handle: int | None, flags: int, memory: int
) -> None:
    """Refuse missing handles, ignored limit flags and incorrect byte budgets."""
    fake_kernel(monkeypatch, handle=handle, flags=flags, memory=memory)
    with pytest.raises(IntakeError, match="RESOURCE_GUARD_UNAVAILABLE"):
        WindowsGuard().install()


def test_windows_loader_unavailable_and_wrong_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refuse missing native loaders instead of substituting another platform."""
    monkeypatch.setattr(ctypes, "WinDLL", None, raising=False)
    with pytest.raises(IntakeError, match="RESOURCE_GUARD_UNAVAILABLE"):
        load_kernel()
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: object())
    with pytest.raises(IntakeError, match="RESOURCE_GUARD_UNAVAILABLE"):
        load_kernel()
    library = ctypes.CDLL(None)
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: library)
    assert load_kernel() is library
