# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Native macOS process identities and inherited-limit-aware map growth control."""

import ctypes
import errno
import mmap
import os
from typing import Annotated, Self

from pydantic import ConfigDict, Field, TypeAdapter, ValidationError, model_validator

from dscat.intake.limits import DEFAULT_LIMITS, fail
from dscat.models.base import StrictModel

TASK_INFO = 4
BSD_INFO = 3
CHILD_CAPACITY = 4
ZOMBIE_STATE = 5
MAX_SIGNED = 2**63 - 1
MISSING_PROCESS = frozenset({errno.ESRCH, errno.ENOENT})
Positive = Annotated[int, Field(gt=0, le=MAX_SIGNED)]
Pid = Annotated[int, Field(gt=0, le=2**31 - 1)]
CHILDREN = TypeAdapter(list[Pid], config=ConfigDict(strict=True))


class TaskInfo(ctypes.Structure):
    """Exact 96-byte proc_taskinfo layout from Apple's proc_info.h."""

    virtual: int
    resident: int
    _fields_ = [
        *[
            (name, ctypes.c_uint64)
            for name in (
                "virtual",
                "resident",
                "total_user",
                "total_system",
                "threads_user",
                "threads_system",
            )
        ],
        *[
            (name, ctypes.c_int32)
            for name in (
                "policy",
                "faults",
                "pageins",
                "cow_faults",
                "messages_sent",
                "messages_received",
                "syscalls_mach",
                "syscalls_unix",
                "switches",
                "threads",
                "running",
                "priority",
            )
        ],
    ]


class BsdInfo(ctypes.Structure):
    """Exact 136-byte proc_bsdinfo layout; names never leave the native buffer."""

    pid: int
    status: int
    parent: int
    group: int
    created_seconds: int
    created_microseconds: int
    _fields_ = [
        *[
            (name, ctypes.c_uint32)
            for name in (
                "flags",
                "status",
                "exit_status",
                "pid",
                "parent",
                "uid",
                "gid",
                "ruid",
                "rgid",
                "saved_uid",
                "saved_gid",
                "reserved",
            )
        ],
        ("command", ctypes.c_char * 16),
        ("name", ctypes.c_char * 32),
        *[
            (name, ctypes.c_uint32)
            for name in (
                "files",
                "group",
                "job_count",
                "terminal_device",
                "terminal_group",
            )
        ],
        ("nice", ctypes.c_int32),
        ("created_seconds", ctypes.c_uint64),
        ("created_microseconds", ctypes.c_uint64),
    ]


class ProcessIdentity(StrictModel):
    """Kernel-observed identity prevents accepting a recycled numeric child PID."""

    pid: Pid
    parent: Pid
    group: Pid
    created_seconds: Positive
    created_microseconds: Annotated[int, Field(ge=0, lt=1000000)]


class ProcessMemory(StrictModel):
    """Current kernel counters, not a claim of complete physical memory accounting."""

    virtual_bytes: Positive
    resident_bytes: Annotated[int, Field(ge=0, le=MAX_SIGNED)]


class MapLimit(StrictModel):
    """Actual immutable startup selection, including reduced inherited headroom."""

    startup_virtual_bytes: Positive
    inherited_hard_limit: int
    selected_limit_bytes: Positive
    remaining_headroom_bytes: Annotated[int, Field(gt=0, le=DEFAULT_LIMITS.memory)]

    @model_validator(mode="after")
    def consistent_headroom(self) -> Self:
        """Never represent a limit unrelated to its recorded startup measurement."""
        if (
            self.selected_limit_bytes - self.startup_virtual_bytes
            != self.remaining_headroom_bytes
        ):
            msg = "Map headroom does not match the selected ceiling."
            raise ValueError(msg)
        return self


class NativeProcesses:
    """Query explicitly owned processes only, using verified native signatures."""

    def __init__(self) -> None:
        """Prepare libproc without depending on shell commands or process names."""
        self.library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        self.library.proc_pidinfo.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint64,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        self.library.proc_pidinfo.restype = ctypes.c_int
        self.library.proc_listchildpids.argtypes = [
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        self.library.proc_listchildpids.restype = ctypes.c_int
        self.library.proc_listpgrppids.argtypes = [
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        self.library.proc_listpgrppids.restype = ctypes.c_int

    def query(self, pid: int, flavor: int, buffer: TaskInfo | BsdInfo) -> bool:
        """Require exact ABI counts; only confirmed missing PIDs are races."""
        ctypes.set_errno(0)
        count = self.library.proc_pidinfo(
            pid, flavor, 0, ctypes.byref(buffer), ctypes.sizeof(buffer)
        )
        if count == 0 and ctypes.get_errno() in MISSING_PROCESS:
            return False
        if count != ctypes.sizeof(buffer):
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
        return True

    def identity(self, pid: int) -> ProcessIdentity | None:
        """Discard names and validate only lifecycle identity fields."""
        raw = BsdInfo()
        if not self.query(pid, BSD_INFO, raw):
            return None
        if raw.pid != pid:
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
        if raw.status == ZOMBIE_STATE:
            return None
        try:
            identity = ProcessIdentity(
                pid=raw.pid,
                parent=raw.parent,
                group=raw.group,
                created_seconds=raw.created_seconds,
                created_microseconds=raw.created_microseconds,
            )
        except ValidationError:
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE") from None
        return identity

    def memory(self, pid: int) -> ProcessMemory | None:
        """Keep actual virtual and resident accounting distinct."""
        raw = TaskInfo()
        if not self.query(pid, TASK_INFO, raw):
            return None
        try:
            return ProcessMemory(virtual_bytes=raw.virtual, resident_bytes=raw.resident)
        except ValidationError:
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE") from None

    def children(self, pid: int) -> list[int]:
        """Use a fixed small kernel child buffer, never a host process inventory."""
        return self.list_pids(pid, group=False)

    def group_members(self, group: int) -> list[int]:
        """Inspect only the isolated group anchored by the owned unreaped leader."""
        return self.list_pids(group, group=True)

    def process_exited(self, pid: int) -> bool:
        """Distinguish a terminal zombie or confirmed disappearance from live work."""
        raw = BsdInfo()
        if not self.query(pid, BSD_INFO, raw):
            return True
        if raw.pid != pid:
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
        return raw.status == ZOMBIE_STATE

    def list_pids(self, owner: int, *, group: bool) -> list[int]:
        """Validate the count-returning child/group wrappers with a fixed buffer."""
        raw = (ctypes.c_int * CHILD_CAPACITY)()
        size = ctypes.sizeof(raw)
        ctypes.set_errno(0)
        function = (
            self.library.proc_listpgrppids if group else self.library.proc_listchildpids
        )
        count = function(owner, raw, size)
        if count == 0 and ctypes.get_errno() in MISSING_PROCESS:
            return []
        # proc_listchildpids returns a PID count; proc_pidinfo returns byte counts.
        if ctypes.get_errno() or count < 0 or count >= CHILD_CAPACITY:
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
        try:
            result = CHILDREN.validate_python(list(raw)[:count])
        except ValidationError:
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE") from None
        if len(result) != len(set(result)):
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
        return result


def select_limit(startup: int, inherited: int, unlimited: int, budget: int) -> MapLimit:
    """Choose finite positive headroom without attempting a hard-limit raise."""
    if startup <= 0 or budget <= 0 or startup > MAX_SIGNED - budget:
        raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
    desired = startup + budget
    selected = desired if inherited == unlimited else min(inherited, desired)
    try:
        return MapLimit(
            startup_virtual_bytes=startup,
            inherited_hard_limit=inherited,
            selected_limit_bytes=selected,
            remaining_headroom_bytes=selected - startup,
        )
    except ValidationError:
        raise fail(code="RESOURCE_GUARD_UNAVAILABLE") from None


class ResourceGuard:
    """Install a frozen native map-growth ceiling before accepting input."""

    def install(self) -> MapLimit:
        """Respect inherited finite hard limits and verify exact selected readback."""
        import resource  # noqa: PLC0415 -- native POSIX API, unavailable on Windows.

        memory = NativeProcesses().memory(os.getpid())
        if memory is None:
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
        selected = select_limit(
            memory.virtual_bytes,
            resource.getrlimit(resource.RLIMIT_AS)[1],
            resource.RLIM_INFINITY,
            DEFAULT_LIMITS.memory,
        )
        resource.setrlimit(
            resource.RLIMIT_AS,
            (selected.selected_limit_bytes, selected.selected_limit_bytes),
        )
        if resource.getrlimit(resource.RLIMIT_AS) != (
            selected.selected_limit_bytes,
            selected.selected_limit_bytes,
        ):
            raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
        return selected


def verify_growth(selected: MapLimit) -> None:
    """Request fresh anonymous map growth without touching a large allocation."""
    try:
        mapping = mmap.mmap(-1, selected.remaining_headroom_bytes + mmap.PAGESIZE)
    except OSError as error:
        if error.errno == errno.ENOMEM:
            return
        raise fail(code="RESOURCE_GUARD_UNAVAILABLE") from None
    mapping.close()
    raise fail(code="RESOURCE_GUARD_UNAVAILABLE")
