"""Permission-restricted, locked, atomic private storage."""

from __future__ import annotations

import errno
import os
import secrets
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

from .schema import MAX_FILE, UsageError, canonical, digest, integer, keys, loads, require, sha, text


def safe_path(path: Path, *, exists: bool = True) -> Path:
    """Reject symlinks and unavailable path components."""
    # Resolve would follow symlinks before the explicit rejection below.
    path = Path(os.path.abspath(path))  # noqa: PTH100 - preserve lexical path for symlink rejection.
    for component in (path, *path.parents):
        require(not component.is_symlink(), "symlink rejected", 3)
    require(not exists or path.exists(), "input unavailable", 3)
    return path


def restricted(path: Path) -> Path:
    """Reject exposed private files/directories without changing caller permissions."""
    path = safe_path(path)
    try:
        require(path.stat().st_mode & 0o077 == 0, "private permissions required", 3)
    except OSError as exc:
        message = "private input unavailable"
        raise UsageError(message, 3) from exc
    return path


def read_bytes(path: Path, limit: int = MAX_FILE, *, private: bool = False) -> bytes:
    """Read a stable bounded prefix from an ordinary file."""
    path = safe_path(path)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            require(not private or before.st_mode & 0o077 == 0, "private permissions required", 3)
            require(stat.S_ISREG(before.st_mode) and before.st_size <= limit, "source size or type unavailable", 3)
            data = stream.read(before.st_size)
            after = os.fstat(stream.fileno())
            require(len(data) == before.st_size and after.st_size >= before.st_size, "source changed during capture", 3)
            stream.seek(0)
            require(stream.read(before.st_size) == data, "source prefix changed during capture", 3)
            return data
    except OSError as exc:
        message = "input unavailable"
        raise UsageError(message, 3) from exc


def read_json(path: Path) -> Any:  # noqa: ANN401 - generic JSON read; callers validate exact domain schemas.
    """Decode a bounded private JSON file."""
    return loads(read_bytes(path))


def _sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write(path: Path, data: bytes) -> None:
    """Replace one file; callers lock multi-file transactions around this operation."""
    path = safe_path(path, exists=False)
    require(path.parent.is_dir(), "private parent unavailable", 3)
    temporary: str | None = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        safe_path(path, exists=False)
        Path(temporary).replace(path)
        temporary = None
        _sync_directory(path.parent)
    except OSError as exc:
        message = "private write failed"
        raise UsageError(message, 3) from exc
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def _owner() -> dict[str, Any]:
    return {"schema": 1, "pid": os.getpid(), "nonce": secrets.token_hex(16)}


@contextmanager
def locked(root: Path) -> Iterator[None]:
    """Hold the exclusive private-state owner lock."""
    root = safe_path(root)
    lock = root / ".lock"
    owner = canonical(_owner())
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    except FileExistsError as exc:
        message = "lock contention; confirm inactive owner before recovery"
        raise UsageError(message, 7) from exc
    except OSError as exc:
        message = "lock unavailable"
        raise UsageError(message, 7) from exc
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(owner)
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        require(read_bytes(lock) == owner, "lock ownership changed", 7)
        lock.unlink()
        _sync_directory(root)


def recover_lock(root: Path) -> None:
    """Explicit recovery checks the recorded local owner; active/reused PIDs fail closed."""
    lock = safe_path(root) / ".lock"
    data = read_bytes(lock)
    owner = loads(data)
    keys(owner, {"schema", "pid", "nonce"})
    integer(owner["schema"], 1, 1)
    integer(owner["pid"], 1)
    text(owner["nonce"], r"[a-f0-9]{32}")
    try:
        os.kill(owner["pid"], 0)
    except OSError as exc:
        require(exc.errno == errno.ESRCH, "lock owner activity unknown", 7)
    else:
        message = "lock owner active"
        raise UsageError(message, 7)
    require(read_bytes(lock) == data, "lock changed during recovery", 7)
    lock.unlink()
    _sync_directory(lock.parent)


class StateStore:
    """A manifest pointer commits immutable objects after all writes succeed."""

    def __init__(self, root: Path) -> None:
        """Initialize and validate the private boundary."""
        self.root = safe_path(root)
        self._manifest()

    @classmethod
    def create(cls, root: Path, domain: str) -> StateStore:
        """Create a new permission-restricted private state."""
        sha(domain)
        root = safe_path(root, exists=False)
        require(not root.exists(), "state already exists", 3)
        safe_path(root.parent)
        try:
            root.mkdir(mode=0o700)
            (root / "objects").mkdir(mode=0o700)
            atomic_write(
                root / "manifest.json",
                canonical({"schema": 1, "contributor": secrets.token_hex(16), "domain": domain, "pointers": {}}),
            )
        except OSError as exc:
            message = "state creation failed"
            raise UsageError(message, 3) from exc
        return cls(root)

    def _manifest(self) -> dict[str, Any]:
        restricted(self.root)
        restricted(self.root / "objects")
        # Permanent private storage has a different boundary from temporary Git
        # repositories, whose ordinary Git modes remain protected by their root.
        for path in self.root.iterdir():
            restricted(path)
            if path.name in {"objects", "snapshots", "candidates"}:
                for child in path.rglob("*"):
                    restricted(child)
        value = read_json(self.root / "manifest.json")
        keys(value, {"schema", "contributor", "domain", "pointers"})
        integer(value["schema"], 1, 1)
        text(value["contributor"], r"[a-f0-9]{32}")
        sha(value["domain"])
        require(isinstance(value["pointers"], dict), "corrupt state", 3)
        for name, identity in value["pointers"].items():
            text(name)
            sha(identity)
            require(
                digest(read_bytes(self.root / "objects" / (identity + ".json"))) == identity, "corrupt state object", 3
            )
        return value

    @property
    def manifest(self) -> dict[str, Any]:
        """Return the validated current manifest."""
        return self._manifest()

    def get(self, name: str) -> Any | None:  # noqa: ANN401 - private generic object store; callers validate schemas.
        """Read the immutable object selected by a private pointer."""
        text(name)
        identity = self._manifest()["pointers"].get(name)
        return None if identity is None else read_json(self.root / "objects" / (identity + ".json"))

    def put_locked(self, name: str, value: object) -> str:
        """Caller holds locked(root). Object write precedes pointer replacement."""
        return self.put_many_locked({name: value})[name]

    def put_many_locked(self, values: dict[str, Any]) -> dict[str, str]:
        """Commit multiple object pointers in one atomic manifest replacement."""
        manifest = self._manifest()
        result: dict[str, str] = {}
        for name, value in values.items():
            text(name)
            data = canonical(value)
            require(len(data) <= MAX_FILE, "state object size limit", 3)
            identity = digest(data)
            path = self.root / "objects" / (identity + ".json")
            if path.exists():
                require(read_bytes(path) == data, "corrupt immutable object", 3)
            else:
                atomic_write(path, data)
            manifest["pointers"][name] = identity
            result[name] = identity
        atomic_write(self.root / "manifest.json", canonical(manifest))
        return result

    def put(self, name: str, value: object) -> str:
        """Atomically store an object under the private owner lock."""
        with locked(self.root):
            return self.put_locked(name, value)
