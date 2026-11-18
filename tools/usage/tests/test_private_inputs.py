"""Private external inputs reject exposure without changing caller or accepted data."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from collections.abc import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import test_foundation as foundation
import test_transport as transport_fixtures
from walkthrough import computer, native_source, run, synthetic_review

from dscat_usage import candidate
from dscat_usage.private import StateStore, atomic_write, read_bytes
from dscat_usage.schema import Status, UsageError, canonical, loads


class PrivateInputTests(unittest.TestCase):
    """Exercise permission validation at executable acceptance and revalidation boundaries."""

    def setUp(self) -> None:
        """Provision only disposable synthetic inputs under ordinary ancestors."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.root.chmod(0o755)
        self.secret = self.root / "secret"
        atomic_write(self.secret, bytes(range(32)))
        self.state, self.config, self.source = computer(self.root, self.secret, 1)
        native_source(self.source, "/synthetic/project", thread="native-thread", closed=True)
        self.entry = self.root / "entry.json"
        atomic_write(self.entry, canonical(foundation.entry(identity="native-thread", primary="NFR-006")))
        value = loads(read_bytes(self.config))
        self.mapping = self.root / "external-map.json"
        atomic_write(self.mapping, read_bytes(Path(value["map_path"])))
        atomic_write(self.config, canonical({**value, "map_path": str(self.mapping)}))

    def refuse(self, path: Path, args: tuple[object, ...], *, state: Path | None = None) -> None:
        """All exposed modes fail generically, preserve bytes/modes/pointers, then restore."""
        state = self.state if state is None else state
        original = read_bytes(path)
        manifest = read_bytes(state / "manifest.json")
        for mode in (0o644, 0o640, 0o604):
            path.chmod(mode)
            self.assertEqual(run(*args, expected=3), Status("unavailable").to_dict())
            self.assertEqual(read_bytes(path), original)
            self.assertEqual(path.stat().st_mode & 0o777, mode)
            self.assertEqual(read_bytes(state / "manifest.json"), manifest)
        path.chmod(0o600)

    def test_config_and_maps_at_refresh_and_map(self) -> None:
        """Every config/map/entry read fails before replacing a valid capture or map."""
        refresh = ("refresh", "--state", self.state, "--config", self.config)
        run(*refresh)
        for path in (self.config, self.mapping):
            with self.subTest(path=path.name):
                self.refuse(path, refresh)
                run(*refresh)
        command = ("map", "--state", self.state, "--config", self.config, "--entry", self.entry)
        for path in (self.config, self.mapping, self.entry):
            with self.subTest(path=path.name):
                self.refuse(path, command)
                run(*command)

    def test_setup_checks_private_inputs_before_creating_state(self) -> None:
        """Prewritten config/maps reject exposure before creating a contributor."""
        for number, path in enumerate((self.config, self.mapping)):
            with self.subTest(path=path.name):
                state = self.root / ("new-state-" + str(number))
                command = ("setup", "--state", state, "--config", self.config, "--secret-file", self.secret)
                original = read_bytes(path)
                path.chmod(0o644)
                self.assertEqual(run(*command, expected=3), Status("unavailable").to_dict())
                self.assertFalse(state.exists())
                self.assertEqual(read_bytes(path), original)
                self.assertEqual(path.stat().st_mode & 0o777, 0o644)
                path.chmod(0o600)
                run(*command)

    def test_configuration_revalidated_before_preparation(self) -> None:
        """Unchanged config bytes with newly exposed permissions cannot prepare transport."""
        run("refresh", "--state", self.state, "--config", self.config)
        for command in ("contribute", "update"):
            args = (
                command,
                "--state",
                self.state,
                "--config",
                self.config,
                "--remote",
                self.root / "absent.git",
                "--branch",
                "dashboard",
                "--generator-invocation",
                "synthetic-generator",
            )
            self.refuse(self.config, args)
            # Restored config reaches transport, which reports the missing remote.
            run(*args, expected=6)
            self.assertIsNone(StateStore(self.state).get("candidate"))

    def test_review_evidence_private_before_pointer_write(self) -> None:
        """Attestation and execution envelopes are private inputs; retry retains bindings."""
        fixture = transport_fixtures.TransportTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.prepare()
        attestation, evidence = synthetic_review(fixture.store, fixture.root)
        command = (
            "review",
            "--state",
            fixture.store.root,
            "--attestation",
            attestation,
            "--execution-evidence",
            evidence,
        )
        for path in (attestation, evidence):
            with self.subTest(path=path.name):
                self.refuse(path, command, state=fixture.store.root)
                run(*command)

    def test_migration_private_maps_associations_and_snapshot(self) -> None:
        """Migration rejects exposed legacy identities/maps before archiving or promotion."""
        fixture = foundation.FoundationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.write_source()
        snapshot, phase, registry = fixture.legacy()
        identity = fixture.identities()
        value = loads(read_bytes(self.config))
        atomic_write(
            self.config,
            canonical(
                {
                    **value,
                    "source_root": str(fixture.source),
                    "project_selector": fixture.project,
                }
            ),
        )
        command = (
            "migrate",
            "--state",
            self.state,
            "--config",
            self.config,
            "--snapshot",
            snapshot,
            "--phase-map",
            phase,
            "--registry",
            registry,
            "--identity-map",
            identity,
        )
        for path in (phase, registry, identity, *sorted(snapshot.iterdir())):
            with self.subTest(path=path.name):
                self.refuse(path, command)
                run(*command)
        self.assertEqual(len(StateStore(self.state).get("migration")["promoted"]), 3)

    def test_external_candidate_closure_preparation_and_revalidation(self) -> None:
        """Private descriptors/config/maps/associations remain restricted after review."""
        fixture = transport_fixtures.TransportTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.inputs["source-descriptor"] = fixture.root / "source-descriptor.json"
        atomic_write(fixture.inputs["source-descriptor"], canonical({"schema": 1, "source": "synthetic"}))
        before = read_bytes(fixture.store.root / "manifest.json")
        for path in fixture.inputs.values():
            path.chmod(0o644)
            with self.assertRaises(UsageError) as caught:
                fixture.prepare()
            self.assertEqual(caught.exception.code, 3)
            self.assertEqual(read_bytes(fixture.store.root / "manifest.json"), before)
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)
            path.chmod(0o600)
        fixture.prepare()
        fixture.review()
        fixture.submit()
        accepted = fixture.store.get("accepted")
        for path in fixture.inputs.values():
            with self.subTest(path=path.name):
                self.refuse(path, ("check", "--state", fixture.store.root), state=fixture.store.root)
                run("check", "--state", fixture.store.root)
                command = (
                    "update",
                    "--state",
                    fixture.store.root,
                    "--config",
                    fixture.inputs["config"],
                    "--remote",
                    fixture.remote,
                    "--branch",
                    "dashboard",
                    "--generator-invocation",
                    "synthetic-generator",
                )
                self.refuse(path, command, state=fixture.store.root)
                run("check", "--state", fixture.store.root)
        self.assertIsNotNone(accepted)
        self.assertEqual(fixture.store.get("accepted"), accepted)

    def test_permission_change_during_candidate_preparation(self) -> None:
        """The last descriptor reread blocks a permission change after initial capture."""
        fixture = transport_fixtures.TransportTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        original: Callable[..., str] = candidate.build_commit
        path = fixture.inputs["config"]

        def change_mode(*args: object, **kwargs: object) -> str:
            result = original(*args, **kwargs)
            path.chmod(0o644)
            return result

        before = read_bytes(fixture.store.root / "manifest.json")
        with (
            patch("dscat_usage.candidate.build_commit", side_effect=change_mode),
            self.assertRaises(UsageError) as caught,
        ):
            fixture.prepare()
        self.assertEqual(caught.exception.code, 3)
        self.assertEqual(read_bytes(fixture.store.root / "manifest.json"), before)
        self.assertEqual(path.stat().st_mode & 0o777, 0o644)
        path.chmod(0o600)
        fixture.prepare()

    def test_permission_change_during_identical_candidate_reuse(self) -> None:
        """A failed identical retry preserves frozen bytes, modes and the PASS review."""
        fixture = transport_fixtures.TransportTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.inputs["source-descriptor"] = fixture.root / "source-descriptor.json"
        atomic_write(fixture.inputs["source-descriptor"], canonical({"schema": 1, "source": "synthetic"}))
        original: Callable[..., str] = candidate.build_commit

        def snapshot() -> dict[Path, tuple[bytes | None, int]]:
            return {
                path.relative_to(fixture.store.root): (
                    read_bytes(path) if path.is_file() else None,
                    path.stat().st_mode & 0o777,
                )
                for path in fixture.store.root.rglob("*")
            }

        with patch.object(candidate, "datetime", wraps=datetime) as clock:
            clock.now.return_value = datetime(2026, 1, 2, tzinfo=UTC)
            first = fixture.prepare()
            for label, path in fixture.inputs.items():
                with self.subTest(input_label=label):
                    fixture.review()
                    candidate.validate(fixture.store, require_review=True)
                    before = snapshot()
                    inputs_before = {key: read_bytes(value) for key, value in fixture.inputs.items()}

                    def expose(*args: object, exposed: Path = path, **kwargs: object) -> str:
                        result = original(*args, **kwargs)
                        exposed.chmod(0o644)
                        return result

                    with (
                        patch.object(candidate, "build_commit", side_effect=expose),
                        self.assertRaises(UsageError) as caught,
                    ):
                        fixture.prepare()
                    self.assertEqual(caught.exception.code, 3)
                    self.assertEqual(snapshot(), before)
                    self.assertEqual({key: read_bytes(value) for key, value in fixture.inputs.items()}, inputs_before)
                    for key, value in fixture.inputs.items():
                        self.assertEqual(value.stat().st_mode & 0o777, 0o644 if key == label else 0o600)
                    path.chmod(0o600)
                    self.assertEqual(candidate.validate(fixture.store, require_review=True), first)
                    self.assertEqual(fixture.prepare(), first)
                    self.assertIn("pending", fixture.store.get("review"))

    def test_public_sources_rates_and_vocabulary_remain_supported(self) -> None:
        """Native sources/public inventories may be 0644 under ordinary 0755 parents."""
        config = loads(read_bytes(self.config))
        for label in ("rates", "vocabulary"):
            public = self.root / (label + ".json")
            atomic_write(public, read_bytes(Path(config[label + "_path"])))
            public.chmod(0o644)
            config[label + "_path"] = str(public)
        atomic_write(self.config, canonical(config))
        for path in self.source.rglob("*"):
            path.chmod(0o755 if path.is_dir() else 0o644)
        run("refresh", "--state", self.state, "--config", self.config)
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o755)
        for label in ("rates", "vocabulary"):
            self.assertEqual(Path(config[label + "_path"]).stat().st_mode & 0o777, 0o644)


if __name__ == "__main__":
    unittest.main()
