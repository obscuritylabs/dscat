"""Preservation regressions for private permissions and pre-ledger dashboards."""

from __future__ import annotations

import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_transport

from dscat_usage import candidate
from dscat_usage.identity import domain, load_secret
from dscat_usage.private import StateStore, atomic_write, read_bytes, restricted
from dscat_usage.render import OWNED_PROJECTIONS
from dscat_usage.schema import UsageError

SECRET = bytes(range(32))
PUBLIC_DIRECTORY = 0o755
PUBLIC_FILE = 0o644
PRIVATE_DIRECTORY = 0o700
PRIVATE_FILE = 0o600


class PrivatePermissionTests(unittest.TestCase):
    """Existing caller-owned data is rejected without permission repair or loss."""

    def setUp(self) -> None:
        """Create an ordinary parent and a private state within it."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.root.chmod(PUBLIC_DIRECTORY)
        self.secret = self.root / "secret"
        atomic_write(self.secret, SECRET)
        self.store = StateStore.create(self.root / "state", domain(SECRET))
        self.store.put("accepted", {"count": 1})

    def test_external_secret_rejects_public_modes_and_allows_private_file(self) -> None:
        """A public parent is allowed; secret group/other access is never accepted."""
        for mode in (PUBLIC_FILE, 0o640, 0o604):
            with self.subTest(mode=mode):
                self.secret.chmod(mode)
                with self.assertRaises(UsageError) as caught:
                    load_secret(self.secret)
                self.assertEqual(caught.exception.code, 3)
                self.assertEqual(self.secret.read_bytes(), SECRET)
                self.assertEqual(stat.S_IMODE(self.secret.stat().st_mode), mode)
        self.secret.chmod(PRIVATE_FILE)
        self.assertEqual(load_secret(self.secret), SECRET)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), PUBLIC_DIRECTORY)

    def test_exposed_state_boundary_rejects_reopen_and_live_writes(self) -> None:
        """Root, permanent directories and nested private files fail without mutation."""
        nested = self.store.root / "candidates" / "saved"
        nested.mkdir(mode=PRIVATE_DIRECTORY, parents=True)
        nested.parent.chmod(PRIVATE_DIRECTORY)
        atomic_write(nested / "input", b"synthetic private candidate input")
        manifest = self.store.root / "manifest.json"
        original = {p.relative_to(self.store.root): p.read_bytes() for p in self.store.root.rglob("*") if p.is_file()}
        for path in (self.store.root, self.store.root / "objects", nested, nested / "input", manifest):
            with self.subTest(boundary=path.name):
                private_mode = PRIVATE_DIRECTORY if path.is_dir() else PRIVATE_FILE
                exposed_mode = PUBLIC_DIRECTORY if path.is_dir() else PUBLIC_FILE
                path.chmod(exposed_mode)
                for operation in (
                    lambda: StateStore(self.store.root),
                    lambda: self.store.get("accepted"),
                    lambda: self.store.put("accepted", {"count": 2}),
                ):
                    with self.assertRaises(UsageError) as caught:
                        operation()
                    self.assertEqual(caught.exception.code, 3)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), exposed_mode)
                self.assertEqual(
                    {p.relative_to(self.store.root): p.read_bytes() for p in self.store.root.rglob("*") if p.is_file()},
                    original,
                )
                path.chmod(private_mode)
        self.assertEqual(StateStore(self.store.root).get("accepted"), {"count": 1})
        self.store.put("accepted", {"count": 2})
        self.assertEqual(self.store.get("accepted"), {"count": 2})

    def test_inaccessible_permission_metadata_has_generic_code(self) -> None:
        """Unavailable metadata cannot establish a private permission boundary."""
        with patch.object(Path, "stat", side_effect=PermissionError), self.assertRaises(UsageError) as caught:
            restricted(self.secret)
        self.assertEqual(caught.exception.code, 3)
        self.assertNotIn(str(self.secret), str(caught.exception))


class LegacyProjectionTests(unittest.TestCase):
    """Pre-ledger projections cannot silently become a smaller receipt corpus."""

    def test_every_owned_legacy_projection_blocks_without_changing_remote(self) -> None:
        """Refuse each owned page while preserving remote and accepted pointers."""
        for projection in sorted(OWNED_PROJECTIONS):
            with self.subTest(projection=projection):
                fixture = test_transport.TransportTests()
                fixture.setUp()
                try:
                    fixture.store.put("accepted", {"synthetic": "prior accepted pointer"})
                    before = read_bytes(fixture.store.root / "manifest.json")
                    blob = candidate.git(fixture.remote, "hash-object", "-w", "--stdin", data=b"Legacy totals.\n")
                    tree = candidate.git(
                        fixture.remote,
                        "mktree",
                        data=b"100644 blob " + blob.stdout.strip() + b"\t" + projection.encode() + b"\n",
                    )
                    commit = (
                        candidate.git(
                            fixture.remote,
                            "commit-tree",
                            tree.stdout.decode().strip(),
                            data=b"Synthetic historical page\n",
                        )
                        .stdout.decode()
                        .strip()
                    )
                    candidate.git(fixture.remote, "update-ref", "refs/heads/dashboard", commit)
                    with self.assertRaises(UsageError) as caught:
                        fixture.prepare()
                    self.assertEqual(caught.exception.code, 3)
                    self.assertEqual(read_bytes(fixture.store.root / "manifest.json"), before)
                    self.assertEqual(candidate.remote_head(fixture.remote, str(fixture.remote), "dashboard"), commit)
                    self.assertEqual(candidate.tree_files(fixture.remote, commit)[0], {projection: b"Legacy totals.\n"})
                    self.assertFalse((fixture.store.root / "candidates").exists())
                finally:
                    fixture.doCleanups()


if __name__ == "__main__":
    unittest.main()
