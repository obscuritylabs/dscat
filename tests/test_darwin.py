# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Native macOS ABI, identity, map-limit selection and safe refusal checks."""

import ctypes
import errno
import json
import subprocess
import sys
from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from dscat.intake.limits import DEFAULT_LIMITS, IntakeError
from dscat.platform import darwin

TASK_BYTES = 96
BSD_BYTES = 136
PID = 11111
PARENT = 11110
GROUP = 11111
BASELINE = 1000000
BUDGET = 64 * 1024**2


def selection() -> darwin.MapLimit:
    """Use a small explicit synthetic budget, never a host process mutation."""
    return darwin.select_limit(BASELINE, -1, -1, BUDGET)


@dataclass
class NativeCall:
    """Controlled native response signatures do not establish platform acceptance."""

    name: str
    response: int | None = None
    error: int = 0
    identity_pid: int = PID
    parent: int = PARENT
    virtual: int = BASELINE
    resident: int = 4096
    children: tuple[int, ...] = ()
    argtypes: list[object] = field(default_factory=list)
    restype: object = None

    def __call__(self, *arguments: object) -> int:
        """Fill only test-owned native buffers and return selected counts/errors."""
        ctypes.set_errno(self.error)
        if self.name == "proc_pidinfo":
            buffer = getattr(arguments[3], "_obj", None)
            if isinstance(buffer, darwin.TaskInfo):
                buffer.virtual = self.virtual
                buffer.resident = self.resident
            else:
                assert isinstance(buffer, darwin.BsdInfo)
                buffer.pid = self.identity_pid
                buffer.parent = self.parent
                buffer.group = GROUP
                buffer.created_seconds = 1
                buffer.created_microseconds = 2
            return ctypes.sizeof(buffer) if self.response is None else self.response
        buffer = arguments[1]
        assert isinstance(buffer, ctypes.Array)
        for index, value in enumerate(self.children):
            buffer[index] = value
        return len(self.children) if self.response is None else self.response


def native(
    monkeypatch: pytest.MonkeyPatch, *, response: int | None = None, error: int = 0
) -> tuple[darwin.NativeProcesses, NativeCall, NativeCall]:
    """Load real ctypes signatures around modelled libproc responses."""
    library = ctypes.CDLL(None)
    query = NativeCall("proc_pidinfo", response, error)
    children = NativeCall("proc_listchildpids", response, error)
    monkeypatch.setattr(library, "proc_pidinfo", query, raising=False)
    monkeypatch.setattr(library, "proc_listchildpids", children, raising=False)
    monkeypatch.setattr(
        library, "proc_listpgrppids", NativeCall("proc_listpgrppids"), raising=False
    )
    monkeypatch.setattr(ctypes, "CDLL", lambda *_args, **_kwargs: library)
    return darwin.NativeProcesses(), query, children


def test_native_layout_and_typed_outputs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only lifecycle identifiers and counters cross the ctypes buffer boundary."""
    assert ctypes.sizeof(darwin.TaskInfo) == TASK_BYTES
    assert ctypes.sizeof(darwin.BsdInfo) == BSD_BYTES
    api, _query, children = native(monkeypatch)
    identity = api.identity(PID)
    memory = api.memory(PID)
    assert identity is not None
    assert identity.pid == PID
    assert identity.parent == PARENT
    assert identity.group == GROUP
    assert memory == darwin.ProcessMemory(virtual_bytes=BASELINE, resident_bytes=4096)
    assert api.children(PID) == []
    children.children = (PID + 1,)
    assert api.children(PID) == [PID + 1]
    assert "command" not in identity.model_dump_json()


@pytest.mark.parametrize("error", [errno.ESRCH, errno.ENOENT])
def test_confirmed_process_exit_is_a_distinct_race(
    monkeypatch: pytest.MonkeyPatch, error: int
) -> None:
    """Only confirmed missing processes may produce an absent identity/sample."""
    api, _query, _children = native(monkeypatch, response=0, error=error)
    assert api.identity(PID) is None
    assert api.memory(PID) is None
    assert api.children(PID) == []


@pytest.mark.parametrize(
    ("response", "error"),
    [(0, 0), (0, errno.EPERM), (1, 0), (-1, 0), (BSD_BYTES + 1, 0)],
)
def test_native_short_denied_and_invalid_counts(
    monkeypatch: pytest.MonkeyPatch, response: int, error: int
) -> None:
    """Unavailable introspection cannot be interpreted as an unexamined success."""
    api, _query, _children = native(monkeypatch, response=response, error=error)
    with pytest.raises(IntakeError, match="RESOURCE_GUARD_UNAVAILABLE"):
        api.identity(PID)
    with pytest.raises(IntakeError, match="RESOURCE_GUARD_UNAVAILABLE"):
        api.memory(PID)


def test_native_impossible_identities_and_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Native PID mismatch, invalid parent or impossible counters are refused."""
    api, query, _children = native(monkeypatch)
    query.identity_pid = PID + 1
    with pytest.raises(IntakeError):
        api.identity(PID)
    query.identity_pid = PID
    query.parent = 0
    with pytest.raises(IntakeError):
        api.identity(PID)
    query.virtual = 0
    with pytest.raises(IntakeError):
        api.memory(PID)


@pytest.mark.parametrize(
    ("children", "response", "error"),
    [
        ((0,), None, 0),
        ((PID, PID), None, 0),
        ((), -1, 0),
        ((), 1, 0),
        ((), 16, 0),
        ((), 0, errno.EPERM),
    ],
)
def test_child_enumeration_is_small_exact_and_closed(
    monkeypatch: pytest.MonkeyPatch,
    children: tuple[int, ...],
    response: int | None,
    error: int,
) -> None:
    """No overflow, duplicate, invalid PID or malformed count reaches observation."""
    api, _query, call = native(monkeypatch)
    call.children = children
    call.response = response
    call.error = error
    with pytest.raises(IntakeError):
        api.children(PID)


def test_limit_selection_unlimited_inherited_and_reduced_headroom() -> None:
    """Every exec respects its inherited hard ceiling without rebasing or raising."""
    first = selection()
    assert first.startup_virtual_bytes == BASELINE
    assert first.selected_limit_bytes == BASELINE + BUDGET
    assert first.remaining_headroom_bytes == BUDGET
    reduced = darwin.select_limit(BASELINE, BASELINE + BUDGET // 2, -1, BUDGET)
    assert reduced.remaining_headroom_bytes == BUDGET // 2
    assert reduced.selected_limit_bytes == reduced.inherited_hard_limit
    larger = darwin.select_limit(BASELINE, BASELINE + 2 * BUDGET, -1, BUDGET)
    assert larger.remaining_headroom_bytes == BUDGET


@pytest.mark.parametrize(
    ("startup", "inherited", "budget"),
    [
        (0, -1, BUDGET),
        (-1, -1, BUDGET),
        (BASELINE, -1, 0),
        (darwin.MAX_SIGNED, -1, BUDGET),
        (BASELINE, BASELINE, BUDGET),
        (BASELINE, BASELINE - 1, BUDGET),
    ],
)
def test_no_headroom_and_overflow_refuse(
    startup: int, inherited: int, budget: int
) -> None:
    """Unsafe startup/limit states fail before any untrusted request is accepted."""
    with pytest.raises(IntakeError):
        darwin.select_limit(startup, inherited, -1, budget)
    with pytest.raises(ValidationError):
        darwin.MapLimit(
            startup_virtual_bytes=BASELINE,
            inherited_hard_limit=-1,
            selected_limit_bytes=BASELINE + 2,
            remaining_headroom_bytes=1,
        )


def test_guard_install_readback_and_missing_self(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Install only the selected hard/soft cap, and require exact native readback."""
    resource = pytest.importorskip("resource")
    native(monkeypatch)
    unlimited = int(resource.RLIM_INFINITY)
    observed = (unlimited, unlimited)

    def get_limit(_kind: int) -> tuple[int, int]:
        return observed

    def set_limit(_kind: int, values: tuple[int, int]) -> None:
        nonlocal observed
        observed = values

    monkeypatch.setattr(resource, "getrlimit", get_limit)
    monkeypatch.setattr(resource, "setrlimit", set_limit)
    selected = darwin.ResourceGuard().install()
    assert selected.remaining_headroom_bytes == DEFAULT_LIMITS.memory
    assert observed == (selected.selected_limit_bytes, selected.selected_limit_bytes)
    monkeypatch.setattr(resource, "setrlimit", lambda *_args: None)
    observed = (unlimited, unlimited)
    with pytest.raises(IntakeError):
        darwin.ResourceGuard().install()
    monkeypatch.setattr(darwin.NativeProcesses, "memory", lambda *_args: None)
    with pytest.raises(IntakeError):
        darwin.ResourceGuard().install()


@pytest.mark.parametrize("error", [errno.ENOMEM, errno.EACCES])
def test_mapping_refusal_must_have_expected_resource_reason(
    monkeypatch: pytest.MonkeyPatch, error: int
) -> None:
    """Permission or argument failures are not proof of enforced map growth."""

    def refuse(*_args: object) -> None:
        raise OSError(error, "synthetic mapping refusal")

    monkeypatch.setattr(darwin.mmap, "mmap", refuse)
    if error == errno.ENOMEM:
        darwin.verify_growth(selection())
    else:
        with pytest.raises(IntakeError):
            darwin.verify_growth(selection())


def test_ignored_map_limit_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """A successful fresh map is closed and cannot produce a verified receipt."""
    closed: list[bool] = []

    class Mapping:
        """Synthetic mapping; no large allocation is made in this test."""

        def close(self) -> None:
            """Track release before the fixed unavailable-guard diagnostic."""
            closed.append(True)

    monkeypatch.setattr(darwin.mmap, "mmap", lambda *_args: Mapping())
    with pytest.raises(IntakeError):
        darwin.verify_growth(selection())
    assert closed == [True]


@pytest.mark.skipif(
    sys.platform != "darwin", reason="Native macOS libproc/resource adapter."
)
def test_real_native_guard_in_disposable_process() -> None:
    """Actual guard installation/refusal uses a child, never the test-runner process."""
    source = (
        "from dscat.platform import install_guard; "
        "print(install_guard().model_dump_json(exclude_none=True))"
    )
    result = subprocess.run(  # noqa: S603 -- fixed interpreter and trusted test code.
        [sys.executable, "-I", "-c", source],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0
    assert not result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["mechanism"] == "darwin_rlimit_as_growth"
    assert receipt["map_limit"]["remaining_headroom_bytes"] > 0
    assert receipt["map_limit"]["remaining_headroom_bytes"] <= DEFAULT_LIMITS.memory


def test_terminal_native_identity_and_group_members(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Terminal processes are distinguishable from live owners and malformed IDs."""
    api, query, _children = native(monkeypatch)
    assert not api.process_exited(PID)
    assert api.group_members(GROUP) == []
    query.identity_pid = PID + 1
    with pytest.raises(IntakeError):
        api.process_exited(PID)
    query.response = 0
    query.error = errno.ESRCH
    assert api.process_exited(PID)


def test_zombie_identity_is_not_a_live_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    """A terminal worker awaiting its parent's reap contributes no live sample."""
    api, _query, _children = native(monkeypatch)
    original = api.query

    def terminal(
        pid: int, flavor: int, buffer: darwin.BsdInfo | darwin.TaskInfo
    ) -> bool:
        result = original(pid, flavor, buffer)
        if isinstance(buffer, darwin.BsdInfo):
            buffer.status = darwin.ZOMBIE_STATE
        return result

    monkeypatch.setattr(api, "query", terminal)
    assert api.identity(PID) is None
    assert api.process_exited(PID)
