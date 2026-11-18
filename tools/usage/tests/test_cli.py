"""Command boundary, input closure and preservation tests with synthetic state."""

from __future__ import annotations

import contextlib
import io
import os
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from walkthrough import computer, native_source, review, run, walkthrough

from dscat_usage import candidate
from dscat_usage.cli import main
from dscat_usage.private import StateStore, atomic_write, read_bytes
from dscat_usage.schema import Status, UsageError, canonical, loads


class CliTests(unittest.TestCase):
    """Exercise executable commands rather than a second implementation."""

    def setUp(self) -> None:
        """Provision a disposable external shared secret."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.secret = self.root / "secret.bin"
        atomic_write(self.secret, bytes(range(32)))

    def test_complete_walkthrough(self) -> None:
        """Both computer flows and supported legacy migration execute offline."""
        with contextlib.redirect_stdout(io.StringIO()):
            walkthrough()

    def test_setup_preserves_config_and_existing_state(self) -> None:
        """Repeated setup does not replace contributor or caller bytes."""
        state, config, _ = computer(self.root, self.secret, 1)
        before = read_bytes(config), read_bytes(state / "manifest.json")
        result = run("setup", "--state", state, "--config", config, "--secret-file", self.secret, expected=3)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(before, (read_bytes(config), read_bytes(state / "manifest.json")))
        if os.name == "posix":
            self.assertEqual(state.stat().st_mode & 0o777, 0o700)
            self.assertEqual((state / "manifest.json").stat().st_mode & 0o777, 0o600)

    def test_setup_existing_config_is_not_rewritten(self) -> None:
        """A fresh second computer can use explicit valid prewritten config."""
        _, config, _ = computer(self.root, self.secret, 1)
        before = read_bytes(config)
        run("setup", "--state", self.root / "another-state", "--config", config, "--secret-file", self.secret)
        self.assertEqual(read_bytes(config), before)

    def test_argument_errors_are_strict_generic_json(self) -> None:
        """Missing required options and unsupported commands reveal no arguments."""
        for args in (("refresh",), ("unsupported-private-label",), ("refresh", "--state", "private-input")):
            result = run(*args, expected=2)
            self.assertEqual(result, Status("failed").to_dict())

    def test_help_and_version_notice(self) -> None:
        """Installed and module surfaces expose a matching proprietary notice."""
        for argument in ("--help", "--version"):
            output = io.StringIO()
            with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as result:
                main([argument])
            self.assertEqual(result.exception.code, 0)
            self.assertIn("Proprietary to Obscurity Labs", output.getvalue())

    def test_missing_input_does_not_replace_refresh(self) -> None:
        """Unavailable and unsafe sources preserve the prior frozen contribution."""
        state, config, source = computer(self.root, self.secret, 1)
        path = native_source(source, "/synthetic/project", thread="thread-one", closed=True)
        run("refresh", "--state", state, "--config", config)
        before = read_bytes(state / "manifest.json")
        path.unlink()
        run("refresh", "--state", state, "--config", config, expected=3)
        self.assertEqual(read_bytes(state / "manifest.json"), before)
        path.symlink_to(self.secret)
        run("refresh", "--state", state, "--config", config, expected=3)
        self.assertEqual(read_bytes(state / "manifest.json"), before)

    def test_mapping_conflict_lock_and_unregistered_label(self) -> None:
        """Strict maps conflict and contend without losing successful entries."""
        state, config, _ = computer(self.root, self.secret, 1)
        path = self.root / "entry.json"
        entry = {
            "schema": 1,
            "level": "thread",
            "id": "native-one",
            "reviewed": True,
            "evidence": "synthetic-dispatch",
            "primary": "NFR-006",
        }
        atomic_write(path, canonical(entry))
        common = ("map", "--state", state, "--config", config, "--entry", path)
        run(*common)
        before = StateStore(state).get("map")
        atomic_write(path, canonical({**entry, "primary": "FR-001"}))
        run(*common, expected=4)
        self.assertEqual(StateStore(state).get("map"), before)
        atomic_write(path, canonical({**entry, "primary": "invalid"}))
        run(*common, expected=2)
        atomic_write(path, canonical(entry))
        atomic_write(state / ".lock", b"synthetic occupied lock")
        run(*common, expected=7)
        self.assertEqual(StateStore(state).get("map"), before)

    def test_domain_mismatch_and_transport_failure(self) -> None:
        """Secret substitution cannot create a second corpus or erase accepted state."""
        state, config, source = computer(self.root, self.secret, 1)
        native_source(source, "/synthetic/project", thread="thread-one", closed=True)
        atomic_write(self.secret, b"z" * 32)
        run("refresh", "--state", state, "--config", config, expected=4)
        atomic_write(self.secret, bytes(range(32)))
        run("refresh", "--state", state, "--config", config)
        run(
            "contribute",
            "--state",
            state,
            "--config",
            config,
            "--remote",
            self.root / "absent.git",
            "--branch",
            "dashboard",
            "--generator-invocation",
            "generator-one",
            expected=6,
        )
        self.assertIsNone(StateStore(state).get("accepted"))

    def test_identical_external_and_local_mapping_is_applied_once(self) -> None:
        """Copied reviewed entries retain one primary allocation after refresh."""
        state, config, source = computer(self.root, self.secret, 1)
        native_source(source, "/synthetic/project", thread="thread-one", closed=True)
        entry = {
            "schema": 1,
            "level": "thread",
            "id": "thread-one",
            "reviewed": True,
            "evidence": "synthetic-dispatch",
            "primary": "NFR-006",
        }
        entry_path = self.root / "entry.json"
        atomic_write(entry_path, canonical(entry))
        run("map", "--state", state, "--config", config, "--entry", entry_path)
        config_value = loads(read_bytes(config))
        atomic_write(Path(config_value["map_path"]), canonical({"schema": 1, "entries": [entry]}))
        run("refresh", "--state", state, "--config", config)
        store = StateStore(state)
        frozen_map = loads(read_bytes(Path(store.get("refresh")["paths"]["map"])))
        self.assertEqual(frozen_map["entries"], [entry])
        self.assertTrue(
            all(row["attribution"]["primary"] == "NFR-006" for row in store.get("contribution")["observations"])
        )

    def test_input_closure_is_immutable_and_complete(self) -> None:
        """Capture binds exactly the registry and source prefixes actually used."""
        state, config, source = computer(self.root, self.secret, 1)
        native_source(source, "/synthetic/project", thread="thread-one", closed=True)
        run("refresh", "--state", state, "--config", config)
        paths = StateStore(state).get("refresh")["paths"]
        self.assertTrue(
            {
                "config",
                "map",
                "capture",
                "contribution",
                "vocabulary",
                "rates",
                "original-config",
                "original-map",
                "normalized",
                "source-descriptor",
            }
            <= paths.keys()
        )
        frozen = loads(read_bytes(Path(paths["capture"])))
        self.assertEqual(set(frozen["input_digests"]), {"jsonl-0", "sqlite-threads", "sqlite-turns"})
        atomic_write(config, canonical({**loads(read_bytes(config)), "project_selector": "/changed"}))
        run(
            "contribute",
            "--state",
            state,
            "--config",
            config,
            "--remote",
            self.root / "absent.git",
            "--branch",
            "dashboard",
            "--generator-invocation",
            "generator-one",
            expected=5,
        )

    def test_pending_capture_and_ambiguous_submission_recovery(self) -> None:
        """Unsent corrections reuse a slot; uncertain submissions block refresh."""
        state, config, source = computer(self.root, self.secret, 1)
        native_source(source, "/synthetic/project", thread="thread-one", closed=True)
        common = ("--state", state, "--config", config)
        run("refresh", *common)
        run("refresh", *common)
        self.assertEqual(StateStore(state).get("contribution")["generation"], 1)
        remote = self.root / "remote.git"
        candidate.git(None, "init", "--bare", str(remote))
        atomic_write(remote / "dscat-usage-synthetic", b"disposable synthetic remote\n")
        submission = (*common, "--remote", remote, "--branch", "dashboard", "--generator-invocation", "generator-one")
        run("contribute", *submission, expected=5)
        review(state, state.parent)
        # Before any submission, a corrected capture can replace the pending slot.
        run("refresh", *common)
        run("update", *submission, expected=5)
        self.assertIsNone(StateStore(state).get("submission-attempt"))
        run("contribute", *submission, expected=5)
        review(state, state.parent)
        error = UsageError("synthetic unresolved submission", 6)
        with patch("dscat_usage.cli.transport.submit", side_effect=error):
            run("update", *submission, expected=6)
        before = read_bytes(state / "manifest.json")
        run("refresh", *common, expected=5)
        self.assertEqual(read_bytes(state / "manifest.json"), before)
        run("update", *submission)
        run("refresh", *common)
        self.assertEqual(StateStore(state).get("contribution")["generation"], 2)

    def test_module_entry_and_human_diagnostics(self) -> None:
        """Module entry matches installed help and bounded human error behavior."""
        output = io.StringIO()
        with (
            patch.object(sys, "argv", ["dscat-usage", "--version"]),
            contextlib.redirect_stdout(output),
            self.assertRaises(SystemExit) as result,
        ):
            runpy.run_module("dscat_usage", run_name="__main__")
        self.assertEqual(result.exception.code, 0)
        self.assertIn("0.1.0", output.getvalue())
        for arguments, expected in (([], 2), (["check", "--state", str(self.root / "absent")], 3)):
            output = io.StringIO()
            with patch.object(sys, "argv", ["dscat-usage", *arguments]), contextlib.redirect_stdout(output):
                result = main()
            self.assertEqual(result, expected)
            self.assertNotIn(str(self.root), output.getvalue())
        with patch("dscat_usage.cli.StateStore.create", side_effect=OSError("synthetic disk full")):
            for structured in (False, True):
                output = io.StringIO()
                arguments = [
                    "setup",
                    "--state",
                    str(self.root / "state"),
                    "--config",
                    str(self.root / "config"),
                    "--secret-file",
                    str(self.secret),
                ]
                if structured:
                    arguments.append("--json")
                with contextlib.redirect_stdout(output):
                    result = main(arguments)
                self.assertEqual(result, 3)
                self.assertNotIn("synthetic disk full", output.getvalue())

    def test_update_prepares_and_missing_refresh_is_explicit(self) -> None:
        """Initial update prepares only, and cannot manufacture absent capture."""
        state, config, source = computer(self.root, self.secret, 1)
        remote = self.root / "remote.git"
        candidate.git(None, "init", "--bare", str(remote))
        atomic_write(remote / "dscat-usage-synthetic", b"disposable synthetic remote\n")
        common = (
            "--state",
            state,
            "--config",
            config,
            "--remote",
            remote,
            "--branch",
            "dashboard",
            "--generator-invocation",
            "generator-one",
        )
        run("update", *common, expected=3)
        native_source(source, "/synthetic/project", thread="thread-one", closed=True)
        run("refresh", "--state", state, "--config", config)
        result = run("update", *common, expected=5)
        self.assertEqual(result["status"], "review_required")
        self.assertIsNone(StateStore(state).get("accepted"))

    def test_state_rejected_inside_checkout(self) -> None:
        """Private state cannot accidentally enter a transport checkout."""
        root = self.root / "checkout"
        root.mkdir()
        (root / ".git").mkdir()
        run(
            "setup",
            "--state",
            root / "private",
            "--config",
            root / "config.json",
            "--secret-file",
            self.secret,
            expected=3,
        )
        self.assertFalse((root / "private").exists())


if __name__ == "__main__":
    unittest.main()
