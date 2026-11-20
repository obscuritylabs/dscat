# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Conservative native local-filesystem checks before any publication writes."""

import ctypes
import os
import re
import sys
from pathlib import Path

from dscat.intake.limits import fail
from dscat.platform.windows import load_kernel

MOUNT_MIN_FIELDS = 6
MOUNT_MIN_TAIL = 3
DRIVE_FIXED = 3

LOCAL_LINUX = frozenset({"ext2", "ext3", "ext4", "xfs", "btrfs", "tmpfs"})


class DarwinStatfs(ctypes.Structure):
    """Darwin statfs64 ABI; filesystem flags and name are read after the call."""

    flags: int
    filesystem: bytes
    _fields_ = [
        ("block_size", ctypes.c_uint32),
        ("io_size", ctypes.c_int32),
        *[
            (name, ctypes.c_uint64)
            for name in ("blocks", "free", "available", "files", "free_files")
        ],
        ("fsid", ctypes.c_int32 * 2),
        ("owner", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("subtype", ctypes.c_uint32),
        ("filesystem", ctypes.c_char * 16),
        ("mounted_on", ctypes.c_char * 1024),
        ("mounted_from", ctypes.c_char * 1024),
        ("flags_extended", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 7),
    ]


def darwin_local(path: Path) -> bool:
    """Accept local APFS/HFS only, using Apple's statfs64 layout and MNT_LOCAL."""
    library = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
    library.statfs64.argtypes = [ctypes.c_char_p, ctypes.POINTER(DarwinStatfs)]
    library.statfs64.restype = ctypes.c_int
    observed = DarwinStatfs()
    return (
        bool(library.statfs64(os.fsencode(path), ctypes.byref(observed)) == 0)
        and bool(observed.flags & 0x1000)
        and observed.filesystem in {b"apfs", b"hfs"}
    )


def unescape_mount(value: str) -> str:
    """Decode the kernel's octal mountinfo path escaping without shell parsing."""
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), value)


def linux_mounts(raw: str) -> list[tuple[Path, str]]:
    """Extract mount points/types from the kernel's mountinfo record grammar."""
    result: list[tuple[Path, str]] = []
    for line in raw.splitlines():
        before, separator, after = line.partition(" - ")
        fields = before.split()
        tail = after.split()
        if (
            not separator
            or len(fields) < MOUNT_MIN_FIELDS
            or len(tail) < MOUNT_MIN_TAIL
        ):
            raise fail(code="PUBLICATION_FAILURE")
        result.append((Path(unescape_mount(fields[4])), tail[0]))
    return result


def linux_local(path: Path) -> bool:
    """Reject unknown/network mounts; overlay needs a separately proven backing."""
    with Path("/proc/self/mountinfo").open("rb") as stream:
        raw = stream.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        return False
    mounts = linux_mounts(raw.decode("utf-8", errors="strict"))
    candidates = [(root, kind) for root, kind in mounts if path.is_relative_to(root)]
    if not candidates:
        return False
    return max(candidates, key=lambda item: len(item[0].parts))[1] in LOCAL_LINUX


def windows_local(path: Path) -> bool:
    """Accept fixed local NTFS volumes, including mounted volume paths."""
    library = load_kernel()
    library.GetVolumePathNameW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_uint32,
    ]
    library.GetVolumePathNameW.restype = ctypes.c_int
    library.GetDriveTypeW.argtypes = [ctypes.c_wchar_p]
    library.GetDriveTypeW.restype = ctypes.c_uint32
    library.GetVolumeInformationW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_uint32,
    ]
    library.GetVolumeInformationW.restype = ctypes.c_int
    volume = ctypes.create_unicode_buffer(32768)
    filesystem = ctypes.create_unicode_buffer(256)
    return (
        bool(library.GetVolumePathNameW(str(path), volume, len(volume)))
        and bool(library.GetDriveTypeW(volume) == DRIVE_FIXED)
        and bool(
            library.GetVolumeInformationW(
                volume, None, 0, None, None, None, filesystem, len(filesystem)
            )
        )
        and bool(filesystem.value == "NTFS")
    )


def require_local(path: Path) -> None:
    """Refuse unsupported destinations before creating output or lock files."""
    resolved = path.resolve(strict=True)
    accepted = False
    if sys.platform == "darwin":
        accepted = darwin_local(resolved)
    elif sys.platform == "linux":
        accepted = linux_local(resolved)
    elif sys.platform == "win32":
        accepted = windows_local(resolved)
    if not accepted:
        raise fail(code="PUBLICATION_FAILURE")
