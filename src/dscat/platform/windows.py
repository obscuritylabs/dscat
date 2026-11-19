# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Windows Job Object process memory and kill-on-close control."""

import ctypes

from dscat.intake.limits import DEFAULT_LIMITS, fail

PROCESS_MEMORY = 0x100
KILL_ON_JOB_CLOSE = 0x2000
EXTENDED_LIMIT_INFORMATION = 9


class BasicLimits(ctypes.Structure):
    """Native JOBOBJECT_BASIC_LIMIT_INFORMATION layout."""

    limit_flags: int
    _fields_ = [
        ("process_time", ctypes.c_int64),
        ("job_time", ctypes.c_int64),
        ("limit_flags", ctypes.c_uint32),
        ("minimum_working_set", ctypes.c_size_t),
        ("maximum_working_set", ctypes.c_size_t),
        ("active_processes", ctypes.c_uint32),
        ("affinity", ctypes.c_size_t),
        ("priority", ctypes.c_uint32),
        ("scheduling", ctypes.c_uint32),
    ]


class IoCounters(ctypes.Structure):
    """Native IO_COUNTERS layout; no filesystem reporting is retained."""

    _fields_ = [
        (name, ctypes.c_uint64)
        for name in (
            "read_operations",
            "write_operations",
            "other_operations",
            "read_bytes",
            "write_bytes",
            "other_bytes",
        )
    ]


class ExtendedLimits(ctypes.Structure):
    """Native JOBOBJECT_EXTENDED_LIMIT_INFORMATION layout."""

    basic: BasicLimits
    process_memory: int
    _fields_ = [
        ("basic", BasicLimits),
        ("io", IoCounters),
        ("process_memory", ctypes.c_size_t),
        ("job_memory", ctypes.c_size_t),
        ("peak_process_memory", ctypes.c_size_t),
        ("peak_job_memory", ctypes.c_size_t),
    ]


def load_kernel() -> ctypes.CDLL:
    """Load the Windows calling convention explicitly, never emulate another OS."""
    loader = getattr(ctypes, "WinDLL", None)
    if loader is None:
        raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
    library = loader("kernel32", use_last_error=True)
    if not isinstance(library, ctypes.CDLL):
        raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
    return library


class ResourceGuard:
    """Retain the job handle until process exit; closing it kills members."""

    def __init__(self) -> None:
        """Prepare native signatures before assigning the current process."""
        self.kernel = load_kernel()
        self.handle: int | None = None
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        self.kernel.CreateJobObjectW.restype = ctypes.c_void_p
        self.kernel.SetInformationJobObject.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint32,
        ]
        self.kernel.SetInformationJobObject.restype = ctypes.c_int
        self.kernel.AssignProcessToJobObject.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        self.kernel.AssignProcessToJobObject.restype = ctypes.c_int
        self.kernel.GetCurrentProcess.argtypes = []
        self.kernel.GetCurrentProcess.restype = ctypes.c_void_p
        self.kernel.QueryInformationJobObject.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_void_p,
        ]
        self.kernel.QueryInformationJobObject.restype = ctypes.c_int
        self.kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        self.kernel.CloseHandle.restype = ctypes.c_int

    def install(self) -> None:
        """Install verified limit flags; actual memory-refusal verification follows."""
        handle = self.kernel.CreateJobObjectW(None, None)
        if not isinstance(handle, int) or handle == 0:
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
        limits = ExtendedLimits()
        limits.basic.limit_flags = PROCESS_MEMORY | KILL_ON_JOB_CLOSE
        limits.process_memory = DEFAULT_LIMITS.memory
        size = ctypes.sizeof(limits)
        if not self.kernel.SetInformationJobObject(
            handle, EXTENDED_LIMIT_INFORMATION, ctypes.byref(limits), size
        ):
            self.kernel.CloseHandle(handle)
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
        if not self.kernel.AssignProcessToJobObject(
            handle, self.kernel.GetCurrentProcess()
        ):
            self.kernel.CloseHandle(handle)
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
        # This handle must survive every guarded operation and must not be closed early.
        self.handle = handle
        observed = ExtendedLimits()
        if not self.kernel.QueryInformationJobObject(
            handle, EXTENDED_LIMIT_INFORMATION, ctypes.byref(observed), size, None
        ):
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
        if (
            observed.basic.limit_flags != limits.basic.limit_flags
            or observed.process_memory != DEFAULT_LIMITS.memory
        ):
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
