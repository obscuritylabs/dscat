"""Synthetic boundary failures preserve private state and source integrity."""

from __future__ import annotations

import copy
import errno
import os
import sqlite3
import sys
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import test_foundation as foundation

from dscat_usage.identity import receipt
from dscat_usage.importer import Limits, capture
from dscat_usage.mapping import resolve, upsert
from dscat_usage.migration import migrate
from dscat_usage.private import StateStore, locked, read_bytes, recover_lock
from dscat_usage.schema import UsageError, canonical, digest, loads, timestamp


class FoundationBoundaryTests(unittest.TestCase):
    """Exercise unsupported inputs, explicit failure codes and safe retries."""

    def setUp(self) -> None:
        """Reuse synthetic fixture construction without inheriting its tests."""
        self.fixture = foundation.FoundationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def reject_capture(self, records: list[dict[str, Any]], code: int, reason: str) -> None:
        """Check bounded failure and preservation for a native source mutation."""
        path = self.fixture.write_source(records)
        before = path.read_bytes(), self.fixture.store.manifest
        with self.assertRaisesRegex(UsageError, reason) as caught:
            capture(self.fixture.config, foundation.SECRET)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(before, (path.read_bytes(), self.fixture.store.manifest))

    def test_native_timestamp_types_and_invalid_calendar(self) -> None:
        """Unsupported, impossible and timezone-free event times fail closed."""
        for value, code, reason in (
            (True, 4, "invalid source timestamp"),
            ([], 4, "invalid source timestamp"),
            ("not-a-date", 4, "invalid source timestamp"),
            ("2026-01-01T00:00:00", 4, "invalid source timestamp"),
            (10**18, 4, "invalid source timestamp"),
        ):
            with self.subTest(value=value):
                records = self.fixture.source_records()
                records[2]["timestamp"] = value
                self.reject_capture(records, code, reason)

    def test_native_missing_context_and_completion_identity(self) -> None:
        """Contexts and completion events cannot invent a missing native turn."""
        for record in (
            {"type": "turn_context", "payload": {}},
            {"type": "event_msg", "payload": {"type": "task_complete"}},
        ):
            with self.subTest(record=record):
                self.reject_capture([self.fixture.source_records()[0], record], 4, "turn identity unavailable")

    def test_native_thread_and_usage_shapes(self) -> None:
        """Missing thread IDs and non-object usage reject the affected capture."""
        records = self.fixture.source_records()
        records[0]["payload"]["id"] = 123
        self.reject_capture(records, 4, "native thread identity unavailable")
        records = self.fixture.source_records()
        records[2]["payload"]["usage"] = []
        self.reject_capture(records, 3, "unsupported native token record")

    def test_native_accounting_event_identity_and_raw_usage(self) -> None:
        """Explicit accounting IDs and both counter envelopes are validated."""
        for field, value in (("response_id", 123), ("response_id", ""), ("last_token_usage", [])):
            with self.subTest(field=field, value=value):
                records = self.fixture.native_records()
                if field == "last_token_usage":
                    records[3]["payload"]["info"][field] = value
                    reason, code = "unsupported native token record", 3
                else:
                    records[3]["payload"][field] = value
                    reason, code = "stable accounting event identity unavailable", 4
                self.reject_capture(records, code, reason)

    def test_ignored_native_event_is_not_a_response(self) -> None:
        """Unrelated native messages do not fabricate usage or turn records."""
        records = self.fixture.source_records(response=False, closed=False)
        records.extend(
            [
                {"type": "event_msg", "payload": {"type": "unrelated"}},
                {"type": "event_msg", "payload": {"type": 123}},
                {"type": "other_record", "payload": {}},
            ]
        )
        self.fixture.write_source(records)
        result = capture(self.fixture.config, foundation.SECRET)
        self.assertEqual({item.kind for item in result.observations}, {"thread", "turn"})

    def test_sqlite_metadata_parent_selection_and_external_exclusion(self) -> None:
        """Selected descendants join their root; explicit other projects stay out."""
        path = self.fixture.source / "state_5.sqlite"
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("CREATE TABLE threads(id TEXT,cwd TEXT,attached_thread_parent_id TEXT)")
            connection.executemany(
                "INSERT INTO threads VALUES(?,?,?)",
                [
                    ("native-thread", self.fixture.project, None),
                    ("child-thread", None, "native-thread"),
                    ("excluded-thread", "/synthetic-other-project", "native-thread"),
                ],
            )
            connection.execute("CREATE TABLE thread_spawn_edges(parent_thread_id TEXT,child_thread_id TEXT)")
            connection.execute("INSERT INTO thread_spawn_edges VALUES(?,?)", ("native-thread", "child-thread"))
            connection.commit()
        records = self.fixture.source_records()
        records.extend(
            [
                {
                    "type": "token_usage_record",
                    "payload": {
                        "thread_id": "excluded-thread",
                        "turn_id": "excluded-turn",
                        "response_id": "excluded-response",
                    },
                },
                {
                    "type": "event_msg",
                    "payload": {"type": "task_complete", "thread_id": "excluded-thread", "turn_id": "excluded-turn"},
                },
            ]
        )
        self.fixture.write_source(records)
        before = path.read_bytes()
        result = capture(self.fixture.config, foundation.SECRET)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual({a.thread_id for a in result.associations}, {"native-thread", "child-thread"})
        child = next(o for o in result.observations if o.thread == receipt(foundation.SECRET, "thread", "child-thread"))
        self.assertEqual(child.parent, receipt(foundation.SECRET, "parent", "native-thread"))
        self.assertEqual(child.root, receipt(foundation.SECRET, "root", "native-thread"))

    def test_sqlite_missing_optional_parent_table_and_corrupt_database(self) -> None:
        """Optional ancestry stays unknown; corrupt databases stay unavailable."""
        path = self.fixture.source / "state_5.sqlite"
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("CREATE TABLE threads(id TEXT,cwd TEXT)")
            connection.execute("INSERT INTO threads VALUES(?,?)", ("native-thread", self.fixture.project))
            connection.commit()
        result = capture(self.fixture.config, foundation.SECRET)
        self.assertEqual(result.diagnostics["missing_parent_table"], 1)
        self.assertFalse(result.observations[0].parent_known)
        path.write_bytes(b"not a SQLite database")
        with self.assertRaisesRegex(UsageError, "database capture unavailable") as caught:
            capture(self.fixture.config, foundation.SECRET)
        self.assertEqual(caught.exception.code, 3)

    def test_sqlite_sidecar_safety_and_size_budget(self) -> None:
        """Readable sidecars stay intact; oversized sidecars stop capture."""
        path = self.fixture.source / "state_5.sqlite"
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("CREATE TABLE threads(id TEXT,cwd TEXT)")
            connection.execute("INSERT INTO threads VALUES(?,?)", ("native-thread", self.fixture.project))
            connection.commit()
        sidecar = Path(str(path) + "-shm")
        sidecar.write_bytes(b"")
        before = path.read_bytes()
        result = capture(self.fixture.config, foundation.SECRET)
        self.assertEqual([record.kind for record in result.observations], ["thread"])
        self.assertEqual(sidecar.read_bytes(), b"")
        sidecar.write_bytes(b"x" * (len(before) + 1))
        config = replace(self.fixture.config, limits=Limits(file_bytes=len(before)))
        with self.assertRaisesRegex(UsageError, "database sidecar limit") as caught:
            capture(config, foundation.SECRET)
        self.assertEqual(caught.exception.code, 3)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(sidecar.read_bytes(), b"x" * (len(before) + 1))
        sidecar.unlink()
        self.assertEqual(len(capture(config, foundation.SECRET).observations), 1)

    def test_sqlite_missing_optional_duration_uses_closed_interval(self) -> None:
        """Optional missing duration leaves a measured interval available."""
        self.fixture.write_source(self.fixture.source_records(response=False, closed=False)[:1])
        path = self.fixture.source / "thread_history_1.sqlite"
        with closing(sqlite3.connect(path)) as connection:
            connection.execute(
                "CREATE TABLE thread_turns(thread_id TEXT,turn_id TEXT,started_at TEXT,completed_at TEXT)"
            )
            connection.execute(
                "INSERT INTO thread_turns VALUES(?,?,?,?)",
                ("native-thread", "native-turn", foundation.NOW, "2026-01-01T00:00:10+00:00"),
            )
            connection.commit()
        before = path.read_bytes()
        result = capture(self.fixture.config, foundation.SECRET)
        turn = next(record for record in result.observations if record.kind == "turn")
        self.assertEqual((turn.duration_seconds, turn.timing_basis), (10.0, "derived_interval"))
        self.assertEqual(path.read_bytes(), before)

    def test_native_resource_budgets_are_cumulative(self) -> None:
        """Inventory, record, total-byte and diagnostic limits fail unavailable."""
        path = self.fixture.write_source()
        size = len(path.read_bytes())
        for limits in (
            Limits(total_bytes=size - 1),
            Limits(records=1),
            Limits(diagnostics=1),
        ):
            with self.subTest(limits=limits), self.assertRaises(UsageError) as caught:
                capture(replace(self.fixture.config, limits=limits), foundation.SECRET)
            self.assertEqual(caught.exception.code, 3)
        (path.parent / "second.jsonl").write_bytes(path.read_bytes())
        with self.assertRaisesRegex(UsageError, "source inventory limit"):
            capture(replace(self.fixture.config, limits=Limits(records=1)), foundation.SECRET)

    def test_response_category_disagreement_keeps_turn_duration_once(self) -> None:
        """Response mappings may differ while the containing turn remains mixed."""
        records = self.fixture.source_records()
        second = copy.deepcopy(records[2])
        second["payload"]["response_id"] = "other-response"
        records.append(second)
        self.fixture.write_source(records)
        entries = [
            foundation.entry(
                "response", "native-response", primary="FR-001", phase="implementation", associated=["FR-001"]
            ),
            foundation.entry("response", "other-response", primary="NFR-006", phase="review", associated=["NFR-006"]),
        ]
        result = capture(self.fixture.config, foundation.SECRET, entries, foundation.VOCAB)
        turns = [r for r in result.observations if r.kind == "turn"]
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0].duration_seconds, 10.0)
        self.assertEqual(
            (turns[0].attribution["primary"], turns[0].attribution["phase"], turns[0].attribution["associated"]),
            ("unallocated", "mixed", []),
        )

    def test_associated_mapping_validation_and_identical_upsert(self) -> None:
        """Associated requirements cannot duplicate allocation or accept labels."""
        for associated in (["FR-001", "FR-001"], ["private-label"], [True]):
            with self.subTest(associated=associated), self.assertRaises(UsageError):
                resolve({}, [foundation.entry(associated=associated)], foundation.VOCAB)
        entry = foundation.entry(associated=["FR-001"])
        first = upsert(self.fixture.store, entry, foundation.VOCAB)
        self.assertEqual(upsert(self.fixture.store, entry, foundation.VOCAB), first)
        self.assertEqual(len(self.fixture.store.get("map")["entries"]), 1)

    def test_storage_os_failures_have_stable_codes(self) -> None:
        """Unavailable reads, locks and creation report bounded domain errors."""
        path = self.fixture.root / "ordinary.json"
        path.write_bytes(b"{}")
        with patch("dscat_usage.private.os.open", side_effect=PermissionError), self.assertRaises(UsageError) as caught:
            read_bytes(path)
        self.assertEqual(caught.exception.code, 3)
        with (
            patch("dscat_usage.private.os.open", side_effect=PermissionError),
            self.assertRaises(UsageError) as caught,
            locked(self.fixture.store.root),
        ):
            self.fail("unavailable lock cannot enter its body")
        self.assertEqual(caught.exception.code, 7)
        with patch.object(Path, "mkdir", side_effect=PermissionError), self.assertRaises(UsageError) as caught:
            StateStore.create(self.fixture.root / "denied-state", self.fixture.store.manifest["domain"])
        self.assertEqual(caught.exception.code, 3)

    def test_atomic_replacement_failure_preserves_pointer_and_allows_retry(self) -> None:
        """A failed replace removes temporary bytes and preserves accepted data."""
        self.fixture.store.put("accepted", {"value": 1})
        before = self.fixture.store.manifest
        with patch.object(Path, "replace", side_effect=OSError), self.assertRaises(UsageError) as caught:
            self.fixture.store.put("accepted", {"value": 2})
        self.assertEqual(caught.exception.code, 3)
        self.assertEqual(self.fixture.store.manifest, before)
        self.assertEqual(list(self.fixture.store.root.rglob(".write-*")), [])
        self.fixture.store.put("accepted", {"value": 2})
        self.assertEqual(self.fixture.store.get("accepted"), {"value": 2})

    def test_uncertain_lock_owner_cannot_be_recovered(self) -> None:
        """Permission failure checking owner activity never deletes the lock."""
        path = self.fixture.store.root / ".lock"
        data = canonical({"schema": 1, "pid": 12345, "nonce": "a" * 32})
        path.write_bytes(data)
        with (
            patch("dscat_usage.private.os.kill", side_effect=OSError(errno.EPERM, "denied")),
            self.assertRaises(UsageError) as caught,
        ):
            recover_lock(self.fixture.store.root)
        self.assertEqual(caught.exception.code, 7)
        self.assertEqual(path.read_bytes(), data)

    def test_named_pipe_is_rejected_without_blocking(self) -> None:
        """A source boundary accepts regular files, never a blocking FIFO."""
        path = self.fixture.root / "pipe"
        os.mkfifo(path)
        with self.assertRaisesRegex(UsageError, "source size or type unavailable") as caught:
            read_bytes(path)
        self.assertEqual(caught.exception.code, 3)

    def test_strict_json_and_timestamp_boundary_errors(self) -> None:
        """Non-JSON Python values, bad encoding and malformed timestamps fail."""
        for value in ({"unsupported": {1}}, {1: "non-string key"}):
            with self.subTest(value=value), self.assertRaises(UsageError):
                canonical(value)
        for data in (b"\xff", b"{", b"[" * 1500):
            with self.subTest(data=data[:10]), self.assertRaises(UsageError) as caught:
                loads(data)
            self.assertEqual(caught.exception.code, 3)
        for value in (True, "x" * 100, "invalid-date", "2026-01-01T00:00:00"):
            with self.subTest(value=value), self.assertRaises(UsageError):
                timestamp(value)

    def rewrite_manifest(self, snapshot: Path, **changes: object) -> None:
        """Update a synthetic manifest after an intentional fixture change."""
        path = snapshot / "manifest.json"
        value = loads(path.read_bytes())
        value.update(changes)
        path.write_bytes(canonical(value))

    def test_migration_versioned_phase_map_and_source_descriptors(self) -> None:
        """Versioned maps and hashed source inventories retain private evidence."""
        snapshot, phase, registry = self.fixture.legacy()
        value = loads(phase.read_bytes())
        value["schema_version"] = 1
        phase.write_bytes(canonical(value))
        manifest = loads((snapshot / "manifest.json").read_bytes())
        manifest["inputs"]["mapping_sha256"] = digest(phase.read_bytes())
        manifest["sources"].extend(
            [
                {"category": "rollout", "sha256": "a" * 64, "source_id": "b" * 64, "bytes": 12, "records": 1},
                {"category": "sqlite-threads", "sha256": "c" * 64},
            ]
        )
        self.rewrite_manifest(snapshot, **manifest)
        value = loads(registry.read_bytes())
        value["artifacts"] = {"synthetic-artifact": "ART-001"}
        registry.write_bytes(canonical(value))
        before = {p: p.read_bytes() for p in [*snapshot.iterdir(), phase, registry]}
        result = migrate(self.fixture.store, snapshot, phase, registry, vocabulary=foundation.VOCAB)
        self.assertEqual(result.archived, 3)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertEqual(self.fixture.store.get("migration")["coverage"], "unknown")

    def test_migration_rejects_invalid_source_descriptors_without_state_change(self) -> None:
        """Unknown sources, corrupt digests and boolean counts cannot migrate."""
        snapshot, phase, registry = self.fixture.legacy()
        before = self.fixture.store.manifest
        for source in (
            {"category": "unsupported", "sha256": "a" * 64},
            {"category": "rollout", "sha256": "invalid"},
            {"category": "rollout", "sha256": "a" * 64, "records": True},
            {"category": "history.jsonl", "status": "complete"},
        ):
            with self.subTest(source=source):
                self.rewrite_manifest(snapshot, sources=[source])
                with self.assertRaises(UsageError):
                    migrate(self.fixture.store, snapshot, phase, registry, vocabulary=foundation.VOCAB)
                self.assertEqual(self.fixture.store.manifest, before)

    def test_partial_native_association_preserves_unpromoted_archive(self) -> None:
        """A verified thread alone does not promote unassociated legacy usage."""
        self.fixture.write_source()
        paths = self.fixture.legacy()
        registry = loads(paths[2].read_bytes())
        registry["entries"].append(foundation.entry("response", digest(b"native-response")[:24], primary="FR-001"))
        paths[2].write_bytes(canonical(registry))
        identity = self.fixture.identities()
        value = loads(identity.read_bytes())
        value["entries"] = value["entries"][:1]
        identity.write_bytes(canonical(value))
        result = migrate(
            self.fixture.store,
            *paths,
            identity_map=identity,
            config=self.fixture.config,
            secret=foundation.SECRET,
            vocabulary=foundation.VOCAB,
        )
        self.assertEqual([o.kind for o in result.promoted], ["thread"])
        self.assertEqual(result.archived, 3)
        self.assertEqual(self.fixture.store.get("migration")["legacy_additivity"], "historical-nonadditive")
        self.assertEqual({entry["level"] for entry in self.fixture.store.get("map")["entries"]}, {"thread"})


if __name__ == "__main__":
    unittest.main()
