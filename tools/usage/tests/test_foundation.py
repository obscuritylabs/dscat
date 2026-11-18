"""Synthetic private capture, state, identity and compatibility acceptance."""

from __future__ import annotations

import copy
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dscat_usage.identity import domain, load_secret, receipt
from dscat_usage.importer import Config, Limits, capture
from dscat_usage.mapping import resolve, upsert
from dscat_usage.migration import OUTPUTS, migrate
from dscat_usage.private import StateStore, atomic_write, locked, read_bytes, recover_lock
from dscat_usage.schema import (
    Attestation,
    Candidate,
    Contribution,
    Ledger,
    Observation,
    ReviewEvidence,
    Status,
    UsageError,
    Vocabulary,
    canonical,
    digest,
    loads,
)

PRIVATE_FILE_MODE = 0o600
SECRET = bytes(range(32))
NOW = "2026-01-01T00:00:00+00:00"
VOCAB = Vocabulary(
    models=frozenset({"synthetic-model"}),
    providers=frozenset({"synthetic-provider"}),
    rtm=frozenset({"FR-001", "NFR-006"}),
    tasks=frozenset({"TASK-001"}),
    features=frozenset({"FEATURE-001"}),
)
USAGE = {
    "input_tokens": 10,
    "cached_input_tokens": 2,
    "cache_write_input_tokens": None,
    "output_tokens": 5,
    "reasoning_output_tokens": 1,
    "total_tokens": 15,
}


def entry(level: str = "thread", identity: str = "native-thread", **facts: object) -> dict:
    """Entry."""
    return {"level": level, "id": identity, "reviewed": True, "evidence": "synthetic-dispatch", **facts}


class FoundationTests(unittest.TestCase):
    """FoundationTests schema and validated maintenance operations."""

    def setUp(self) -> None:
        """Create isolated synthetic fixtures."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "sessions").mkdir()
        self.project = str(self.root / "project")
        self.config = Config(
            self.source,
            self.project,
            self.root / "map",
            self.root / "rates",
            self.root / "vocabulary",
            self.root / "secret",
        )
        self.store = StateStore.create(self.root / "private", domain(SECRET))

    def source_records(self, *, response: bool = True, closed: bool = True) -> list[dict]:
        """Source records."""
        records = [
            {"type": "session_meta", "payload": {"id": "native-thread", "cwd": self.project, "parent_thread_id": None}},
            {"type": "event_msg", "timestamp": NOW, "payload": {"type": "task_started", "turn_id": "native-turn"}},
        ]
        if response:
            records.append(
                {
                    "type": "token_usage_record",
                    "timestamp": NOW,
                    "payload": {
                        "turn_id": "native-turn",
                        "response_id": "native-response",
                        "usage": USAGE,
                        "model": "synthetic-model",
                        "model_provider": "synthetic-provider",
                    },
                }
            )
        if closed:
            records.append(
                {
                    "type": "event_msg",
                    "timestamp": "2026-01-01T00:00:10+00:00",
                    "payload": {"type": "task_complete", "turn_id": "native-turn"},
                }
            )
        return records

    def write_source(self, records: list[dict] | None = None) -> Path:
        """Write source."""
        path = self.source / "sessions" / "synthetic.jsonl"
        path.write_bytes(
            b"".join(canonical(row) + b"\n" for row in self.source_records() if records is None)
            if records is None
            else b"".join(canonical(row) + b"\n" for row in records)
        )
        return path

    def native_records(self) -> list[dict]:
        """Native records."""
        source = Path(__file__).parent / "fixtures" / "native-token-count-v1.jsonl"
        records = [loads(line) for line in source.read_bytes().splitlines()]
        records[0]["payload"]["cwd"] = self.project
        return records

    def legacy(self) -> tuple[Path, Path, Path]:
        """Legacy."""
        snapshot = self.root / "legacy"
        snapshot.mkdir()
        phase = self.root / "phase.json"
        registry = self.root / "registry.json"
        legacy_thread = digest(b"native-thread")[:24]
        legacy_turn = digest(b"native-turn")[:24]
        legacy_response = digest(b"native-response")[:24]
        atomic_write(
            phase, canonical({"entries": [{"level": "thread", "id": legacy_thread, "phase": "implementation"}]})
        )
        atomic_write(
            registry,
            canonical(
                {
                    "schema_version": 1,
                    "artifacts": {},
                    "labels": {"task": {"TASK-001": "TASK-001"}, "feature": {}},
                    "entries": [entry(identity=legacy_thread, primary="FR-001", task="TASK-001")],
                }
            ),
        )
        account = {
            "schema_version": 1,
            "project": "local-project",
            "observed_at": NOW,
            "dimension_summaries": [],
            "time_groups": [],
            "totals": {},
            "time": {},
            "diagnostics": {},
            "coverage": {"historical_completeness": "unknown"},
            "current_list_scenario": {},
            "sessions": [
                {
                    "thread_id": legacy_thread,
                    "parent_id": "unknown",
                    "root_id": legacy_thread,
                    "inferred_phase": "coordinator",
                }
            ],
            "turns": [
                {
                    "thread_id": legacy_thread,
                    "turn_id": legacy_turn,
                    "root_id": legacy_thread,
                    "start": NOW,
                    "end": "2026-01-01T00:00:10+00:00",
                    "duration_seconds": 10.0,
                    "duration_ms": None,
                    "duration_source": "derived_interval",
                    "interval_source": "rollout",
                    "inferred_phase": "coordinator",
                    "phase": "implementation",
                    "feature": "unknown",
                    "task": "unknown",
                    "phase_basis": "manual",
                    "feature_basis": "unknown",
                    "task_basis": "unknown",
                }
            ],
            "responses": [
                {
                    "thread_id": legacy_thread,
                    "turn_id": legacy_turn,
                    "response_id": legacy_response,
                    "root_id": legacy_thread,
                    "timestamp": NOW,
                    "usage": USAGE,
                    "inferred_phase": "coordinator",
                    "model": "synthetic-model",
                    "provider": "synthetic-provider",
                    "effort": None,
                    "tier": None,
                    "model_source": "response",
                    "provider_source": "response",
                    "effort_source": "unknown",
                    "tier_source": "unknown",
                    "phase": "implementation",
                    "feature": "unknown",
                    "task": "unknown",
                    "phase_basis": "manual",
                    "feature_basis": "unknown",
                    "task_basis": "unknown",
                    "cost": None,
                    "currency": None,
                    "rate_id": None,
                    "cost_status": "unpriced",
                    "cost_assumption": None,
                }
            ],
        }
        outputs = {name: canonical(account) if name == "accounting.json" else b"synthetic\n" for name in OUTPUTS}
        for name, data in outputs.items():
            atomic_write(snapshot / name, data)
        atomic_write(
            snapshot / "manifest.json",
            canonical(
                {
                    "schema_version": 1,
                    "observed_at": NOW,
                    "inputs": {
                        "script_sha256": "a" * 64,
                        "mapping_sha256": digest(phase.read_bytes()),
                        "prices_sha256": "b" * 64,
                    },
                    "sources": [{"category": "history.jsonl", "status": "absent"}],
                    "outputs": {name: digest(data) for name, data in outputs.items()},
                }
            ),
        )
        return snapshot, phase, registry

    def identities(self) -> Path:
        """Identities."""
        path = self.root / "identities.json"
        atomic_write(
            path,
            canonical(
                {
                    "schema": 1,
                    "entries": [
                        {
                            "kind": kind,
                            "legacy_thread": digest(b"native-thread")[:24],
                            "legacy_id": digest(native.encode())[:24],
                            "native_thread": "native-thread",
                            "native_id": None if kind == "thread" else native,
                        }
                        for kind, native in (
                            ("thread", "native-thread"),
                            ("turn", "native-turn"),
                            ("response", "native-response"),
                        )
                    ],
                }
            ),
        )
        return path

    def test_canonical_and_json_reject_hostile_values(self) -> None:
        """Verify canonical and json reject hostile values."""
        self.assertEqual(canonical({"z": 2, "a": "é"}), b'{"a":"\xc3\xa9","z":2}')
        for raw in (
            b'{"a":1,"a":2}',
            b'{"a":NaN}',
            b'{"a":1e999}',
            b'"\xff"',
            b"[" * 40 + b"0" + b"]" * 40,
            b"1" + b"0" * 400,
            b"1" + b"0" * 5000,
        ):
            with self.subTest(raw=raw[:20]), self.assertRaises(UsageError):
                loads(raw)
        for number in (float("nan"), float("inf")):
            with self.assertRaises(UsageError):
                canonical(number)
        with self.assertRaises(UsageError):
            canonical(10**400)

    def test_receipts_stable_separated_and_secret_required(self) -> None:
        """Verify receipts stable separated and secret required."""
        self.assertEqual(receipt(SECRET, "response", "t", "r"), receipt(SECRET, "response", "t", "r"))
        self.assertNotEqual(receipt(SECRET, "response", "t", "r"), receipt(SECRET, "turn", "t", "r"))
        self.assertNotEqual(domain(SECRET), domain(b"x" * 32))
        for bad in (b"", b"a" * 31, b"a" * 33):
            with self.assertRaises(UsageError):
                domain(bad)
        atomic_write(self.config.secret_file, SECRET)
        self.assertEqual(load_secret(self.config.secret_file), SECRET)
        with self.assertRaises(UsageError):
            receipt(SECRET, "response", "t", None)

    def test_frozen_compatibility_fixtures(self) -> None:
        """Verify frozen compatibility fixtures."""
        fixtures = Path(__file__).parent / "fixtures"
        value = loads((fixtures / "contribution-v1.json").read_bytes())
        self.assertEqual(
            canonical(Contribution.from_dict(value, VOCAB).to_dict()), (fixtures / "contribution-v1.json").read_bytes()
        )
        snapshot = self.root / "frozen-legacy"
        snapshot.mkdir()
        for path in (fixtures / "legacy-v1").iterdir():
            atomic_write(snapshot / path.name, path.read_bytes())
        phase, registry = self.root / "phase.json", self.root / "registry.json"
        atomic_write(phase, (fixtures / "phase-map-v1.json").read_bytes())
        atomic_write(registry, (fixtures / "registry-v1.json").read_bytes())
        result = migrate(
            self.store,
            snapshot,
            phase,
            registry,
            vocabulary=VOCAB,
        )
        self.assertEqual(result.archived, 3)

    def test_explicit_configuration_and_hostile_shapes(self) -> None:
        """Verify explicit configuration and hostile shapes."""
        value = {
            "schema": 1,
            "source_root": str(self.source),
            "project_selector": self.project,
            "map_path": str(self.config.map_path),
            "rates_path": str(self.config.rates_path),
            "vocabulary_path": str(self.config.vocabulary_path),
            "secret_file": str(self.config.secret_file),
            "limits": asdict(Limits()),
        }
        self.assertEqual(Config.from_dict(value), self.config)
        for field, bad in (("source_root", "."), ("schema", True), ("project_selector", [])):
            changed = {**value, field: bad}
            with self.subTest(field=field), self.assertRaises(UsageError):
                Config.from_dict(changed)
        self.write_source()
        record = next(r for r in capture(self.config, SECRET).observations if r.kind == "response")
        for field in ("kind", "timing_basis", "model"):
            changed = {**record.to_dict(), field: []}
            with self.subTest(field=field), self.assertRaises(UsageError):
                Observation.from_dict(changed)

    def test_separate_process_map_contention_preserves_existing(self) -> None:
        """Verify separate process map contention preserves existing."""
        upsert(self.store, entry(primary="FR-001"), VOCAB)
        environment = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
        script = (
            "from pathlib import Path; import sys; from dscat_usage.private import StateStore; "
            "from dscat_usage.schema import UsageError; s=StateStore(Path(sys.argv[1]));\n"
            "try: s.put('other',{})\nexcept UsageError as e: sys.exit(e.code)"
        )
        with locked(self.store.root):
            process = subprocess.run(  # noqa: S603 - fixed Python executable and synthetic child-process script.
                [sys.executable, "-c", script, str(self.store.root)], env=environment, capture_output=True, check=False
            )
            self.assertEqual(process.returncode, 7)
        self.assertEqual(self.store.get("map")["entries"], [entry(primary="FR-001")])

    def test_native_sqlite_thread_schema_variant(self) -> None:
        """Verify native sqlite thread schema variant."""
        self.write_source()
        path = self.source / "state_5.sqlite"
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("CREATE TABLE threads(id TEXT,cwd TEXT)")
            connection.execute("INSERT INTO threads VALUES(?,?)", ("native-thread", self.project))
            connection.commit()
        before = path.read_bytes()
        result = capture(self.config, SECRET)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(len(result.observations), 3)
        self.assertIn("missing_parent_table", result.diagnostics)

    def test_strict_observation_and_token_boundaries(self) -> None:
        """Verify strict observation and token boundaries."""
        self.write_source()
        record = next(r for r in capture(self.config, SECRET, vocabulary=VOCAB).observations if r.kind == "response")
        self.assertEqual(Observation.from_dict(record.to_dict(), VOCAB), record)
        for key, value in (("prompt", "private"), ("model", "unreviewed"), ("parent_known", 1)):
            changed = record.to_dict()
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(UsageError):
                Observation.from_dict(changed, VOCAB)
        for key, value in (
            ("input_tokens", True),
            ("cached_input_tokens", 11),
            ("reasoning_output_tokens", 6),
            ("total_tokens", 999),
            ("output_tokens", -1),
        ):
            changed = record.to_dict()
            changed["usage"][key] = value
            with self.subTest(key=key), self.assertRaises(UsageError):
                Observation.from_dict(changed, VOCAB)

    def test_contribution_ledger_and_status_roundtrip(self) -> None:
        """Verify contribution ledger and status roundtrip."""
        self.write_source()
        result = capture(self.config, SECRET, vocabulary=VOCAB)
        contribution = Contribution(
            result.domain, self.store.manifest["contributor"], 1, None, result.observed_at, result.observations
        )
        self.assertEqual(Contribution.from_dict(contribution.to_dict(), VOCAB), contribution)
        ledger = Ledger(result.domain, (contribution,))
        self.assertEqual(Ledger.from_dict(ledger.to_dict(), VOCAB), ledger)
        changed = ledger.to_dict()
        changed["domain"] = "a" * 64
        with self.assertRaises(UsageError):
            Ledger.from_dict(changed, VOCAB)
        self.assertEqual(Status.from_dict(Status("prepared", {"responses": 1}).to_dict()).status, "prepared")
        with self.assertRaises(UsageError):
            Status("prepared", {"private-label": 1}).validate()

    def test_review_and_candidate_schema_boundaries(self) -> None:
        """Verify review and candidate schema boundaries."""
        candidate = Candidate(
            domain(SECRET),
            "generator",
            NOW,
            None,
            "a" * 64,
            "b" * 64,
            "c" * 64,
            {"Usage.md": "d" * 64},
            {"capture": "e" * 64},
            {"f" * 32: 1},
            "synthetic-local-remote",
            "wiki",
            {
                "name": "Usage Dashboard",
                "email": "usage-dashboard@users.noreply.github.com",
                "message": "Update aggregate usage dashboard",
            },
            synthetic=True,
        )
        self.assertEqual(Candidate.from_dict(candidate.to_dict()), candidate)
        evidence = ReviewEvidence(
            "TASK-001",
            "generator",
            "reviewer",
            "a" * 64,
            "b" * 64,
            "c" * 64,
            "d" * 64,
            None,
            NOW,
            "PASS",
            synthetic=True,
        )
        self.assertEqual(ReviewEvidence.from_dict(evidence.to_dict()), evidence)
        attestation = Attestation(**evidence.to_dict(), execution_evidence_digest="e" * 64)
        self.assertEqual(Attestation.from_dict(attestation.to_dict()), attestation)
        changed = evidence.to_dict()
        changed["reviewer_invocation"] = "generator"
        with self.assertRaises(UsageError):
            ReviewEvidence.from_dict(changed)

    def test_state_atomic_and_corruption_preservation(self) -> None:
        """Verify state atomic and corruption preservation."""
        self.store.put("accepted", {"value": 1})
        before = (self.store.root / "manifest.json").read_bytes()
        with patch("dscat_usage.private.os.replace", side_effect=OSError("synthetic")), self.assertRaises(UsageError):
            self.store.put("accepted", {"value": 2})
        self.assertEqual((self.store.root / "manifest.json").read_bytes(), before)
        self.assertEqual(self.store.get("accepted"), {"value": 1})
        identity = self.store.manifest["pointers"]["accepted"]
        (self.store.root / "objects" / (identity + ".json")).write_bytes(b"{}")
        with self.assertRaises(UsageError):
            StateStore(self.store.root)

    def test_private_permissions_and_no_replacement(self) -> None:
        """Verify private permissions and no replacement."""
        self.store.put("accepted", {})
        self.assertEqual(self.store.root.stat().st_mode & 0o777, 0o700)
        self.assertTrue(
            all(p.stat().st_mode & 0o777 == PRIVATE_FILE_MODE for p in self.store.root.rglob("*") if p.is_file())
        )
        with self.assertRaises(UsageError):
            StateStore.create(self.store.root, domain(SECRET))

    def test_locks_contention_and_explicit_recovery(self) -> None:
        """Verify locks contention and explicit recovery."""
        with locked(self.store.root):
            with self.assertRaises(UsageError) as caught:
                self.store.put("other", {})
            self.assertEqual(caught.exception.code, 7)
            with self.assertRaises(UsageError):
                recover_lock(self.store.root)
        lock = self.store.root / ".lock"
        lock.write_bytes(canonical({"schema": 1, "pid": 99999999, "nonce": "a" * 32}))
        recover_lock(self.store.root)
        self.assertFalse(lock.exists())

    def test_killed_writer_leaves_previous_pointer(self) -> None:
        """Verify killed writer leaves previous pointer."""
        self.store.put("accepted", {"value": 1})
        environment = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
        script = (
            "from pathlib import Path; from dscat_usage.private import locked; import os,sys; "
            "c=locked(Path(sys.argv[1])); c.__enter__(); os._exit(9)"
        )
        process = subprocess.run(  # noqa: S603 - fixed Python executable and synthetic child-process script.
            [sys.executable, "-c", script, str(self.store.root)], env=environment, check=False, capture_output=True
        )
        self.assertEqual(process.returncode, 9)
        self.assertEqual(self.store.get("accepted"), {"value": 1})
        with self.assertRaises(UsageError):
            self.store.put("accepted", {"value": 2})
        recover_lock(self.store.root)
        self.store.put("accepted", {"value": 2})

    def test_symlinks_rejected_in_source_and_state(self) -> None:
        """Verify symlinks rejected in source and state."""
        self.write_source()
        (self.source / "sessions" / "link.jsonl").symlink_to(self.source / "sessions" / "synthetic.jsonl")
        with self.assertRaises(UsageError):
            capture(self.config, SECRET)
        path = self.root / "link"
        path.symlink_to(self.store.root / "manifest.json")
        with self.assertRaises(UsageError):
            read_bytes(path)
        with self.assertRaises(UsageError):
            atomic_write(path, b"{}")

    def test_mapping_independent_precedence_and_conflicts(self) -> None:
        """Verify mapping independent precedence and conflicts."""
        upsert(self.store, entry(primary="FR-001", phase="planning"), VOCAB)
        upsert(self.store, entry("response", "native-response", phase="implementation"), VOCAB)
        entries = self.store.get("map")["entries"]
        result = resolve({"thread": "native-thread", "response": "native-response"}, entries, VOCAB)
        self.assertEqual((result["primary"], result["phase"]), ("FR-001", "implementation"))
        before = self.store.manifest
        with self.assertRaises(UsageError):
            upsert(self.store, entry(primary="NFR-006"), VOCAB)
        self.assertEqual(self.store.manifest, before)
        with self.assertRaises(UsageError):
            upsert(self.store, entry(task="private-label"), VOCAB)

    def test_native_capture_copied_sources_partial_and_unknowns(self) -> None:
        """Verify native capture copied sources partial and unknowns."""
        path = self.write_source()
        path.write_bytes(path.read_bytes() + b'{"incomplete":')
        first = capture(self.config, SECRET, vocabulary=VOCAB)
        (self.source / "sessions" / "copy.jsonl").write_bytes(path.read_bytes())
        second = capture(self.config, SECRET, vocabulary=VOCAB)
        self.assertEqual(first.observations, second.observations)
        self.assertEqual(second.coverage["partial_lines"], 2)
        self.assertEqual(len(first.observations), 3)
        response = next(r for r in first.observations if r.kind == "response")
        self.assertIsNone(response.usage["cache_write_input_tokens"])
        self.assertEqual(response.model, "synthetic-model")
        unknown = next(r for r in capture(self.config, SECRET).observations if r.kind == "response")
        self.assertIsNone(unknown.model)
        turn = next(r for r in first.observations if r.kind == "turn")
        self.assertEqual((turn.duration_seconds, turn.timing_basis), (10.0, "derived_interval"))

    def test_no_response_open_turn_is_preserved(self) -> None:
        """Verify no response open turn is preserved."""
        self.write_source(self.source_records(response=False, closed=False))
        result = capture(self.config, SECRET)
        turn = next(r for r in result.observations if r.kind == "turn")
        self.assertIsNone(turn.end)
        self.assertIsNone(turn.duration_seconds)
        self.assertEqual(len(result.observations), 2)

    def test_native_token_count_last_usage_context_and_copied_dedup(self) -> None:
        """Verify native token count last usage context and copied dedup."""
        path = self.write_source(self.native_records())
        before = path.read_bytes()
        first = capture(self.config, SECRET, vocabulary=VOCAB)
        responses = [r for r in first.observations if r.kind == "response"]
        self.assertEqual(len(responses), 2)
        self.assertEqual(sum(r.usage["total_tokens"] for r in responses), 45)
        self.assertEqual({r.timestamp for r in responses}, {"2026-01-01T00:00:05+00:00", "2026-01-01T00:00:07+00:00"})
        self.assertTrue(
            all(
                r.model == "synthetic-model"
                and r.provider == "synthetic-provider"
                and r.turn == receipt(SECRET, "turn", "native-thread", "native-turn")
                for r in responses
            )
        )
        turn = next(r for r in first.observations if r.kind == "turn")
        self.assertEqual((turn.duration_seconds, turn.timing_basis), (10.0, "derived_interval"))
        self.assertEqual(first.diagnostics["duplicate_token_count"], 1)
        self.assertEqual(path.read_bytes(), before)
        (self.source / "sessions" / "copy.jsonl").write_bytes(before)
        second = capture(self.config, SECRET, vocabulary=VOCAB)
        self.assertEqual(first.observations, second.observations)
        self.assertEqual(first.associations, second.associations)

    def test_native_token_count_event_identity_excludes_mutable_facts(self) -> None:
        """Verify native token count event identity excludes mutable facts."""
        records = self.native_records()
        self.write_source(records)
        before = capture(self.config, SECRET, vocabulary=VOCAB)
        # Corrected counters keep the same native event timestamps and receipts.
        for row in records[3:6]:
            for name in ("last_token_usage", "total_token_usage"):
                row["payload"]["info"][name]["cached_input_tokens"] = 0
        self.write_source(records)
        after = capture(self.config, SECRET, vocabulary=VOCAB)
        self.assertEqual({a.receipt for a in before.associations}, {a.receipt for a in after.associations})
        self.assertNotEqual(before.observations, after.observations)
        self.write_source(self.native_records())
        (self.source / "sessions" / "conflict.jsonl").write_bytes(b"".join(canonical(row) + b"\n" for row in records))
        with self.assertRaises(UsageError) as caught:
            capture(self.config, SECRET, vocabulary=VOCAB)
        self.assertEqual(caught.exception.code, 4)

    def test_native_token_count_unknown_last_and_empty_information(self) -> None:
        """Verify native token count unknown last and empty information."""
        records = self.native_records()
        rows = [*records[:3], records[3], records[-1]]
        rows[3]["payload"]["info"]["last_token_usage"] = None
        self.write_source(rows)
        result = capture(self.config, SECRET, vocabulary=VOCAB)
        response = next(r for r in result.observations if r.kind == "response")
        self.assertTrue(all(value is None for value in response.usage.values()))
        self.assertEqual(result.diagnostics["missing_last_token_usage"], 1)
        rows[3]["payload"]["info"] = None
        self.write_source(rows)
        result = capture(self.config, SECRET)
        self.assertFalse(any(r.kind == "response" for r in result.observations))
        self.assertEqual(result.diagnostics["empty_token_count"], 1)

    def test_native_token_count_missing_identity_and_invalid_counters_fail(self) -> None:
        """Verify native token count missing identity and invalid counters fail."""
        for mutation in ("timestamp", "turn", "info", "subset", "cumulative", "replay", "regression", "collision"):
            records = self.native_records()
            if mutation == "timestamp":
                del records[3]["timestamp"]
            elif mutation == "turn":
                records = [records[0], records[3]]
            elif mutation == "info":
                records[3]["payload"]["info"] = []
            elif mutation == "subset":
                records[3]["payload"]["info"]["last_token_usage"]["cached_input_tokens"] = 11
            elif mutation == "cumulative":
                records[3]["payload"]["info"]["total_token_usage"] = {
                    **USAGE,
                    "input_tokens": 1,
                    "cached_input_tokens": 0,
                    "total_tokens": 6,
                }
            elif mutation == "replay":
                records[4]["payload"]["info"]["last_token_usage"]["cached_input_tokens"] = 1
            elif mutation == "regression":
                records[5]["payload"]["info"]["total_token_usage"] = USAGE
            else:
                records[5]["timestamp"] = records[3]["timestamp"]
            self.write_source(records)
            before = self.store.manifest
            with self.subTest(mutation=mutation), self.assertRaises(UsageError):
                capture(self.config, SECRET, vocabulary=VOCAB)
            self.assertEqual(self.store.manifest, before)

    def test_native_token_count_explicit_identity_and_absent_cumulative(self) -> None:
        """Verify native token count explicit identity and absent cumulative."""
        records = self.native_records()
        for index, row in enumerate(records[3:6]):
            row["payload"]["response_id"] = f"explicit-response-{index}"
            row["payload"]["info"]["total_token_usage"] = None
        self.write_source(records)
        result = capture(self.config, SECRET, vocabulary=VOCAB)
        responses = [r for r in result.observations if r.kind == "response"]
        self.assertEqual(len(responses), 3)
        self.assertEqual(
            {r.receipt for r in responses},
            {receipt(SECRET, "response", "native-thread", f"explicit-response-{index}") for index in range(3)},
        )

    def test_missing_schema_identity_and_resource_limits(self) -> None:
        """Verify missing schema identity and resource limits."""
        with self.assertRaises(UsageError) as caught:
            capture(self.config, SECRET)
        self.assertEqual(caught.exception.code, 3)
        records = self.source_records()
        del records[2]["payload"]["response_id"]
        self.write_source(records)
        with self.assertRaises(UsageError) as caught:
            capture(self.config, SECRET)
        self.assertEqual(caught.exception.code, 4)
        self.write_source()
        tiny = Config(
            self.source,
            self.project,
            self.config.map_path,
            self.config.rates_path,
            self.config.vocabulary_path,
            self.config.secret_file,
            Limits(file_bytes=10),
        )
        with self.assertRaises(UsageError):
            capture(tiny, SECRET)
        with self.assertRaises(UsageError):
            Limits(records=True)

    def test_sqlite_readonly_variants_and_recorded_duration(self) -> None:
        """Verify sqlite readonly variants and recorded duration."""
        self.write_source()
        path = self.source / "thread_history_1.sqlite"
        with closing(sqlite3.connect(path)) as connection:
            connection.execute(
                "CREATE TABLE thread_turns(thread_id TEXT,turn_id TEXT,started_at INTEGER,"
                "completed_at INTEGER,duration_ms INTEGER)"
            )
            connection.execute(
                "INSERT INTO thread_turns VALUES(?,?,?,?,?)",
                ("native-thread", "native-turn", 1767225600, 1767225610, 9000),
            )
            connection.commit()
        before = path.read_bytes()
        result = capture(self.config, SECRET)
        turn = next(r for r in result.observations if r.kind == "turn")
        self.assertEqual((turn.duration_seconds, turn.timing_basis), (9.0, "recorded"))
        self.assertEqual(path.read_bytes(), before)
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("DROP TABLE thread_turns")
            connection.execute("CREATE TABLE unsupported(other TEXT)")
            connection.commit()
        with self.assertRaises(UsageError):
            capture(self.config, SECRET)

    def test_native_conflicting_observations_block(self) -> None:
        """Verify native conflicting observations block."""
        records = self.source_records()
        duplicate = copy.deepcopy(records[2])
        duplicate["payload"]["usage"]["cached_input_tokens"] = 3
        records.append(duplicate)
        self.write_source(records)
        with self.assertRaises(UsageError) as caught:
            capture(self.config, SECRET)
        self.assertEqual(caught.exception.code, 4)

    def test_legacy_archive_replay_preserves_all_bytes(self) -> None:
        """Verify legacy archive replay preserves all bytes."""
        snapshot, phase, registry = self.legacy()
        originals = {p: p.read_bytes() for p in [*snapshot.iterdir(), phase, registry]}
        first = migrate(self.store, snapshot, phase, registry, vocabulary=VOCAB)
        self.assertEqual((first.archived, first.promoted, first.replay), (3, (), False))
        second = migrate(self.store, snapshot, phase, registry, vocabulary=VOCAB)
        self.assertTrue(second.replay)
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(originals, {p: p.read_bytes() for p in originals})
        archive = self.store.get("migration")
        self.assertEqual(archive["legacy_additivity"], "historical-nonadditive")
        self.assertEqual(archive["coverage"], "unknown")
        self.assertEqual(self.store.get("map")["entries"], [])
        self.assertEqual(
            bytes.fromhex("".join(archive["original_bytes_hex"]["accounting.json"])),
            (snapshot / "accounting.json").read_bytes(),
        )

    def test_legacy_verified_native_associations_and_attribution(self) -> None:
        """Verify legacy verified native associations and attribution."""
        self.write_source()
        paths = self.legacy()
        result = migrate(
            self.store, *paths, identity_map=self.identities(), config=self.config, secret=SECRET, vocabulary=VOCAB
        )
        self.assertEqual(len(result.promoted), 3)
        self.assertTrue(
            all(
                r.attribution["phase"] == "implementation" and r.attribution["primary"] == "FR-001"
                for r in result.promoted
            )
        )
        self.assertTrue(all(r.attribution["phase"] != "coordinator" for r in result.promoted))

    def test_legacy_response_retains_turn_precedence_per_dimension(self) -> None:
        """Verify legacy response retains turn precedence per dimension."""
        self.write_source()
        paths = self.legacy()
        registry = loads(paths[2].read_bytes())
        registry["entries"].extend(
            [
                entry(
                    "turn", digest(b"native-turn")[:24], primary="NFR-006", feature="FEATURE-001", phase="verification"
                ),
                entry("response", digest(b"native-response")[:24], phase="review"),
            ]
        )
        paths[2].write_bytes(canonical(registry))
        result = migrate(
            self.store, *paths, identity_map=self.identities(), config=self.config, secret=SECRET, vocabulary=VOCAB
        )
        response = next(r for r in result.promoted if r.kind == "response")
        self.assertEqual(
            response.attribution,
            {"primary": "NFR-006", "associated": [], "phase": "review", "task": "TASK-001", "feature": "FEATURE-001"},
        )
        replay = migrate(
            self.store, *paths, identity_map=self.identities(), config=self.config, secret=SECRET, vocabulary=VOCAB
        )
        self.assertTrue(replay.replay)
        self.assertEqual(result.promoted, replay.promoted)

    def test_legacy_failure_preserves_state_and_inputs(self) -> None:
        """Verify legacy failure preserves state and inputs."""
        paths = self.legacy()
        before = self.store.manifest
        (paths[0] / "usage.csv").write_bytes(b"corrupt")
        with self.assertRaises(UsageError):
            migrate(self.store, *paths, vocabulary=VOCAB)
        self.assertEqual(self.store.manifest, before)

    def test_legacy_conflict_and_missing_native_rejected(self) -> None:
        """Verify legacy conflict and missing native rejected."""
        paths = self.legacy()
        registry = loads(paths[2].read_bytes())
        registry["entries"].append(entry(identity=digest(b"native-thread")[:24], primary="NFR-006"))
        paths[2].write_bytes(canonical(registry))
        with self.assertRaises(UsageError) as caught:
            migrate(self.store, *paths, vocabulary=VOCAB)
        self.assertEqual(caught.exception.code, 4)
        registry["entries"].pop()
        paths[2].write_bytes(canonical(registry))
        with self.assertRaises(UsageError):
            migrate(
                self.store, *paths, identity_map=self.identities(), config=self.config, secret=SECRET, vocabulary=VOCAB
            )
        self.assertIsNone(self.store.get("migration"))

    def test_legacy_ambiguous_identity_and_domain_rejected(self) -> None:
        """Verify legacy ambiguous identity and domain rejected."""
        self.write_source()
        paths = self.legacy()
        identity = self.identities()
        value = loads(identity.read_bytes())
        value["entries"].append(value["entries"][0])
        identity.write_bytes(canonical(value))
        with self.assertRaises(UsageError) as caught:
            migrate(self.store, *paths, identity_map=identity, config=self.config, secret=SECRET, vocabulary=VOCAB)
        self.assertEqual(caught.exception.code, 4)
        with self.assertRaises(UsageError):
            migrate(
                self.store,
                *paths,
                identity_map=self.identities(),
                config=self.config,
                secret=b"x" * 32,
                vocabulary=VOCAB,
            )


if __name__ == "__main__":
    unittest.main()
