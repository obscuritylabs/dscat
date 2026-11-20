# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Native filesystem classification and bounded I/O failure contracts."""

import ctypes
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    import os

import pytest

from dscat.intake.limits import IntakeError
from dscat.storage import filesystems
from dscat.storage import io as storage_io


@dataclass
class NativeCall:
    """Model native adapter signatures; this is not platform acceptance evidence."""

    name: str
    failure: str = ""
    filesystem: str = "NTFS"
    local: bool = True
    argtypes: list[object] = field(default_factory=list)
    restype: object = None

    def __call__(self, *arguments: object) -> int:
        """Return controlled native outputs for positive and refusal paths."""
        if self.name == self.failure:
            return -1 if self.name == "statfs64" else 0
        if self.name == "statfs64":
            observed = getattr(arguments[1], "_obj", None)
            assert isinstance(observed, filesystems.DarwinStatfs)
            observed.flags = 0x1000 if self.local else 0
            observed.filesystem = self.filesystem.encode()
            return 0
        if self.name == "GetVolumePathNameW":
            output = arguments[1]
            assert isinstance(output, ctypes.Array)
            value = ctypes.create_unicode_buffer("C:\\")
            ctypes.memmove(output, value, ctypes.sizeof(value))
        if self.name == "GetDriveTypeW":
            return 3 if self.local else 4
        if self.name == "GetVolumeInformationW":
            output = arguments[6]
            assert isinstance(output, ctypes.Array)
            value = ctypes.create_unicode_buffer(self.filesystem)
            ctypes.memmove(output, value, ctypes.sizeof(value))
        return 1


@pytest.mark.parametrize(
    ("filesystem", "local", "failure", "expected"),
    [
        ("apfs", True, "", True),
        ("hfs", True, "", True),
        ("apfs", False, "", False),
        ("smbfs", True, "", False),
        ("apfs", True, "statfs64", False),
    ],
)
def test_darwin_abi_and_refusal(
    monkeypatch: pytest.MonkeyPatch,
    filesystem: str,
    *,
    local: bool,
    failure: str,
    expected: bool,
) -> None:
    """The exact statfs64 ABI accepts only local supported filesystem names."""
    expected_size = 2168
    assert ctypes.sizeof(filesystems.DarwinStatfs) == expected_size
    library = ctypes.CDLL(None)
    monkeypatch.setattr(
        library,
        "statfs64",
        NativeCall("statfs64", failure, filesystem, local),
        raising=False,
    )
    monkeypatch.setattr(ctypes, "CDLL", lambda *_args, **_kwargs: library)
    assert filesystems.darwin_local(Path("/synthetic")) is expected


@pytest.mark.parametrize(
    ("filesystem", "local", "failure", "expected"),
    [
        ("NTFS", True, "", True),
        ("ReFS", True, "", False),
        ("NTFS", False, "", False),
        ("NTFS", True, "GetVolumePathNameW", False),
        ("NTFS", True, "GetVolumeInformationW", False),
    ],
)
def test_windows_native_volume_refusal(
    monkeypatch: pytest.MonkeyPatch,
    filesystem: str,
    *,
    local: bool,
    failure: str,
    expected: bool,
) -> None:
    """Unknown/remote drives and unsupported filesystems fail native selection."""
    library = ctypes.CDLL(None)
    for name in ("GetVolumePathNameW", "GetDriveTypeW", "GetVolumeInformationW"):
        monkeypatch.setattr(
            library, name, NativeCall(name, failure, filesystem, local), raising=False
        )
    monkeypatch.setattr(filesystems, "load_kernel", lambda: library)
    assert filesystems.windows_local(Path("synthetic")) is expected


@pytest.mark.parametrize(
    "raw",
    [
        "invalid",
        "1 2 - ext4 disk rw",
        "1 2 0:1 / / rw - ext4 disk",
        "1 2 0:1 / / rw ext4 disk rw",
    ],
)
def test_malformed_mountinfo_is_not_local(raw: str) -> None:
    """The kernel record parser does not infer omitted structure."""
    with pytest.raises(IntakeError):
        filesystems.linux_mounts(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"1 2 0:1 / / rw - ext4 disk rw\n", True),
        (
            b"1 2 0:1 / / rw - ext4 disk rw\n2 1 0:2 / /synthetic rw - nfs disk rw\n",
            False,
        ),
        (b"1 2 0:1 / /elsewhere rw - ext4 disk rw\n", False),
        (b"1 2 0:1 / / rw - overlay overlay rw\n", False),
        (b"x" * (1024 * 1024 + 1), False),
    ],
)
def test_linux_uses_longest_mount_and_bounded_metadata(
    monkeypatch: pytest.MonkeyPatch, raw: bytes, *, expected: bool
) -> None:
    """A nested remote mount overrides a local parent; overlay is unproven."""
    monkeypatch.setattr(Path, "open", lambda *_args: io.BytesIO(raw))
    assert filesystems.linux_local(Path("/synthetic/path")) is expected
    assert filesystems.unescape_mount(r"/a\040b\134c") == "/a b\\c"


@pytest.mark.parametrize("platform", ["darwin", "linux", "win32", "unsupported"])
def test_publication_platform_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    """Unavailable native selection refuses without creating destination artifacts."""
    monkeypatch.setattr(filesystems.sys, "platform", platform)
    for name in ("darwin_local", "linux_local", "windows_local"):
        monkeypatch.setattr(filesystems, name, lambda _path: True)
    if platform == "unsupported":
        with pytest.raises(IntakeError):
            filesystems.require_local(tmp_path)
    else:
        filesystems.require_local(tmp_path)
    for name in ("darwin_local", "linux_local", "windows_local"):
        monkeypatch.setattr(filesystems, name, lambda _path: False)
    with pytest.raises(IntakeError):
        filesystems.require_local(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_regular_file_bounds_type_and_device(tmp_path: Path) -> None:
    """Inclusive file bounds and same-device directories are enforced."""
    path = tmp_path / "file"
    storage_io.write_file(path, b"1234")
    assert storage_io.read_file(path, 4) == b"1234"
    with pytest.raises(IntakeError):
        storage_io.read_file(path, 3)
    with pytest.raises(FileExistsError):
        storage_io.write_file(path, b"replacement")
    with pytest.raises(IntakeError):
        storage_io.directory(path)
    with pytest.raises(IntakeError):
        storage_io.directory(tmp_path, tmp_path.stat().st_dev + 1)
    with pytest.raises(IntakeError):
        storage_io.read_file(tmp_path, 10)
    storage_io.flush_directory(tmp_path)


@pytest.mark.parametrize("change_after", [1, 2, 3])
def test_changed_file_identities_refuse_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change_after: int
) -> None:
    """Changes at open, final descriptor and final path observations fail closed."""
    path = tmp_path / "file"
    path.write_bytes(b"synthetic")
    identity = storage_io.file_identity(path.stat())
    changed = identity.model_copy(update={"modified_ns": identity.modified_ns + 1})
    calls = 0

    def observe(_attributes: os.stat_result) -> object:
        nonlocal calls
        calls += 1
        return changed if calls > change_after else identity

    monkeypatch.setattr(storage_io, "file_identity", observe)
    with pytest.raises(IntakeError, match="UNSAFE_INPUT"):
        storage_io.read_file(path, 100)


def test_growth_during_read_is_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even a stale observed file size cannot overrun the streaming byte ceiling."""
    path = tmp_path / "file"
    path.write_bytes(b"12345")
    identity = storage_io.file_identity(path.stat()).model_copy(update={"size": 0})
    monkeypatch.setattr(storage_io, "file_identity", lambda _attributes: identity)
    with pytest.raises(IntakeError, match="INPUT_LIMIT"):
        storage_io.read_file(path, 4)


class ShortWriter(io.BufferedWriter):
    """Test-owned file object that deliberately fails its full-write contract."""

    @override
    def write(self, _buffer: object, /) -> int:
        """Report a short write without accepting a partially published artifact."""
        return 0


def test_short_write_and_file_flush_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Short and failed flush operations cannot pass the staged-write boundary."""
    monkeypatch.setattr(
        storage_io.os,
        "fdopen",
        lambda descriptor, _mode: ShortWriter(io.FileIO(descriptor, "wb")),
    )
    with pytest.raises(IntakeError, match="PUBLICATION_FAILURE"):
        storage_io.write_file(tmp_path / "short", b"synthetic")
    monkeypatch.undo()

    def refused(_descriptor: int) -> None:
        msg = "synthetic flush failure"
        raise OSError(msg)

    monkeypatch.setattr(storage_io.os, "fsync", refused)
    with pytest.raises(OSError, match="flush failure"):
        storage_io.write_file(tmp_path / "flush", b"synthetic")
    with pytest.raises(OSError, match="flush failure"):
        storage_io.flush_directory(tmp_path)


def test_windows_directory_flush_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows relies on flushed closed files; no power-loss guarantee is claimed."""
    monkeypatch.setattr(storage_io.os, "name", "nt")
    storage_io.flush_directory(tmp_path)
