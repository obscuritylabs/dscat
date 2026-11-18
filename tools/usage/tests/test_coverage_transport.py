"""Synthetic Git races and failures preserve frozen and accepted identities."""

from __future__ import annotations

import subprocess
import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import test_ledger_metrics as measurements
import test_transport as fixtures

from dscat_usage import candidate as candidates
from dscat_usage import ledger, transport
from dscat_usage.private import read_bytes
from dscat_usage.review import bindings
from dscat_usage.schema import Ledger, UsageError


class TransportBoundaryTests(unittest.TestCase):
    """Check failures against disposable local remotes and private state."""

    def setUp(self) -> None:
        """Reuse fixture builders without repeating inherited test methods."""
        self.fixture = fixtures.TransportTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def seed(self, files: dict[bytes, tuple[str, bytes]], parent: str | None = None) -> str:
        """Create ordinary synthetic remote commits without checking out paths."""
        remote = self.fixture.remote
        candidates.git(remote, "read-tree", "--empty")
        index = bytearray()
        for path, (mode, content) in files.items():
            blob = candidates.git(remote, "hash-object", "-w", "--stdin", data=content).stdout.strip()
            index.extend(mode.encode() + b" " + blob + b"\t" + path + b"\0")
        candidates.git(remote, "update-index", "-z", "--index-info", data=bytes(index))
        tree = candidates.git(remote, "write-tree").stdout.decode().strip()
        parents = [] if parent is None else ["-p", parent]
        commit = (
            candidates.git(
                remote, "commit-tree", tree, *parents, data=b"Synthetic page update\n", date="2026-01-01T00:00:00Z"
            )
            .stdout.decode()
            .strip()
        )
        candidates.git(remote, "update-ref", "refs/heads/dashboard", commit)
        return commit

    def test_git_os_and_timeout_failures_preserve_accepted_state(self) -> None:
        """Unavailable Git returns a bounded transport error and permits retry."""
        self.fixture.publish()
        before = self.fixture.store.manifest
        for failure in (PermissionError("synthetic denial"), subprocess.TimeoutExpired("git", 120)):
            with self.subTest(failure=type(failure).__name__):
                with (
                    patch.object(candidates.subprocess, "run", side_effect=failure),
                    self.assertRaisesRegex(UsageError, "transport unavailable") as caught,
                ):
                    self.fixture.prepare()
                self.assertEqual(caught.exception.code, 6)
                self.assertEqual(self.fixture.store.manifest, before)
        self.assertEqual(self.fixture.submit().status, "submitted")

    def test_non_utf8_outgoing_path_blocks_candidate_without_changing_remote(self) -> None:
        """Git byte paths outside the UTF-8 contract cannot escape the boundary."""
        parent = self.seed({b"synthetic-\xff.md": ("100644", b"Synthetic page\n")})
        before = self.fixture.store.manifest
        with self.assertRaisesRegex(UsageError, "unsupported outgoing path") as caught:
            self.fixture.prepare()
        self.assertEqual(caught.exception.code, 3)
        self.assertEqual(self.fixture.store.manifest, before)
        self.assertEqual(candidates.remote_head(self.fixture.remote, str(self.fixture.remote), "dashboard"), parent)

    def test_nested_unrelated_tree_preserves_git_order_modes_and_bytes(self) -> None:
        """Nested directories and similarly prefixed files retain exact framing."""
        pages = {
            b"Guide/Readme.md": ("100644", b"Nested synthetic page\n"),
            b"Guide/Tools/run": ("100755", b"Synthetic executable bytes\n"),
            b"Guide.md": ("100644", b"Synthetic sibling\n"),
        }
        parent = self.seed(pages)
        self.fixture.prepare()
        self.fixture.review()
        result = self.fixture.submit()
        files, modes = candidates.tree_files(self.fixture.remote, result.remote_commit)
        for name, (mode, content) in pages.items():
            self.assertEqual(files[name.decode()], content)
            self.assertEqual(modes[name.decode()], mode)
        self.assertEqual(candidates.load(self.fixture.store)[0].parent, parent)
        self.assertEqual(result.status, "submitted")

    def test_identical_prepare_reuses_bundle_and_reopens_review(self) -> None:
        """A deterministic retry keeps immutable bytes and requires fresh review."""
        with patch.object(candidates, "datetime", wraps=datetime) as clock:
            clock.now.return_value = datetime(2026, 1, 2, tzinfo=UTC)
            first = self.fixture.prepare()
            identity = bindings(first)["candidate_digest"]
            directory = self.fixture.store.root / "candidates" / identity
            before = {path.relative_to(directory): read_bytes(path) for path in directory.rglob("*") if path.is_file()}
            self.fixture.review()
            second = self.fixture.prepare()
        self.assertEqual(second, first)
        self.assertEqual(
            {path.relative_to(directory): read_bytes(path) for path in directory.rglob("*") if path.is_file()}, before
        )
        self.assertEqual(self.fixture.store.get("review"), {"schema": 1, "pending": identity})
        self.fixture.error(5, self.fixture.submit)
        self.assertIsNone(self.fixture.store.get("accepted"))

    def test_fetch_race_preserves_prior_candidate_and_accepted_pointer(self) -> None:
        """Remote advancement between advertisement and fetch fails explicitly."""
        submitted = self.fixture.publish()
        before = self.fixture.store.manifest
        original = candidates.git

        def advance(repo: Path | None, *args: str, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            """Advance the disposable remote exactly when fetch starts."""
            if args and args[0] == "fetch":
                self.seed({b"Other.md": ("100644", b"Concurrent synthetic page\n")}, submitted.remote_commit)
            return original(repo, *args, **kwargs)

        with (
            patch.object(candidates, "git", side_effect=advance),
            self.assertRaisesRegex(UsageError, "remote changed during fetch; retry") as caught,
        ):
            self.fixture.prepare()
        self.assertEqual(caught.exception.code, 6)
        self.assertEqual(self.fixture.store.manifest, before)

    def test_remote_removed_during_confirmation_preserves_accepted_pointer(self) -> None:
        """A disappearing ref cannot confirm a previously submitted identity."""
        self.fixture.publish()
        before = self.fixture.store.manifest
        original = transport.fetch
        calls = 0
        confirmation_call = 2

        def remove(repo: Path, remote: str, branch: str) -> str | None:
            """Remove the disposable ref after preflight and identity advertisement."""
            nonlocal calls
            calls += 1
            if calls == confirmation_call:
                candidates.git(self.fixture.remote, "update-ref", "-d", "refs/heads/dashboard")
            return original(repo, remote, branch)

        with (
            patch.object(transport, "fetch", side_effect=remove),
            self.assertRaisesRegex(UsageError, "remote identity unresolved") as caught,
        ):
            self.fixture.submit()
        self.assertEqual(caught.exception.code, 6)
        self.assertEqual(self.fixture.store.manifest, before)

    def test_push_race_remerges_and_requires_new_review(self) -> None:
        """An ordinary push losing a race preserves its frozen candidate."""
        other, inputs = self.fixture.state("racing-contributor")
        first = self.fixture.prepare()
        identity = bindings(first)["candidate_digest"]
        self.fixture.review()
        original = transport.git

        def race(repo: Path | None, *args: str, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            """Submit another contributor immediately before the first push."""
            if args and args[0] == "push":
                with patch.object(transport, "git", original):
                    self.fixture.publish(other, inputs)
            return original(repo, *args, **kwargs)

        with patch.object(transport, "git", side_effect=race):
            result = self.fixture.submit()
        self.assertEqual(result.status, "review_required")
        self.assertNotEqual(result.candidate_digest, identity)
        self.assertTrue((self.fixture.store.root / "candidates" / identity).is_dir())
        self.assertIsNone(self.fixture.store.get("accepted"))
        self.assertEqual(len(candidates.load(self.fixture.store)[0].generations), 2)
        self.fixture.error(5, self.fixture.submit)
        self.fixture.review()
        self.assertEqual(self.fixture.submit().status, "submitted")


class ConflictBoundaryTests(unittest.TestCase):
    """Receipt conflicts remain quarantined without hiding unrelated failures."""

    def test_third_observation_does_not_clear_an_existing_receipt_conflict(self) -> None:
        """Later agreement cannot resolve contradictory participating evidence."""
        original = measurements.response()
        contradictory = replace(
            original, model=None, usage={**original.usage, "input_tokens": 101, "total_tokens": 151}
        )
        contributions = tuple(
            measurements.contribution((record,), contributor)
            for record, contributor in ((original, "a" * 32), (contradictory, "b" * 32), (original, "c" * 32))
        )
        with self.assertRaises(ledger.MergeConflict) as caught:
            ledger.canonical_records(Ledger(measurements.DOMAIN, contributions), measurements.VOCAB)
        self.assertEqual(caught.exception.receipts, (original.receipt,))
        self.assertEqual(caught.exception.count, 1)
        self.assertNotIn(original.receipt, str(caught.exception))

    def test_nonconflict_validation_failure_is_not_reported_as_receipt_conflict(self) -> None:
        """Unexpected boundary errors retain their failure code and reason."""
        record = measurements.response()
        corpus = Ledger(
            measurements.DOMAIN,
            (measurements.contribution((record,), "a" * 32), measurements.contribution((record,), "b" * 32)),
        )
        failure = UsageError("synthetic resource failure", 3)
        with (
            patch.object(ledger, "_combine", side_effect=failure),
            self.assertRaisesRegex(UsageError, "synthetic resource failure") as caught,
        ):
            ledger.canonical_records(corpus, measurements.VOCAB)
        self.assertIs(caught.exception, failure)


if __name__ == "__main__":
    unittest.main()
