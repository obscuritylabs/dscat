"""Synthetic business-boundary tests; no private source fixtures."""

import copy
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("usage_refresh", Path(__file__).parents[1] / "codex_refresh.py")
m = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = m
SPEC.loader.exec_module(m)


class Accounting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.project = self.root / "project"
        self.out = self.root / "out"
        self.source.mkdir()
        self.project.mkdir()
        self.out.mkdir()
        (self.source / "sessions").mkdir()
        self.mapping = self.out / "phase-map.json"
        self.pricing = self.out / "prices.json"
        self.mapping.write_text('{"entries":[]}')
        self.pricing.write_text('{"rates":[]}')
        self.usage = dict(zip(m.METRICS, (100, 60, 0, 20, 5, 120)))

    def records(self, thread="thread-a", cwd=None, parent=None):
        return [
            {
                "type": "session_meta",
                "payload": {
                    "id": thread,
                    "cwd": str(cwd or self.project),
                    "parent_thread_id": parent,
                    "agent_path": "/agent/implement",
                    "model_provider": "provider",
                    "private_body": "SECRET_BODY_SENTINEL",
                },
            },
            {"type": "turn_context", "payload": {"turn_id": "turn-a", "model": "model-a", "effort": "low"}},
            {
                "type": "event_msg",
                "timestamp": "2026-11-17T00:00:00Z",
                "payload": {"type": "task_started", "turn_id": "turn-a"},
            },
            {
                "type": "event_msg",
                "timestamp": "2026-11-17T00:00:10Z",
                "payload": {"type": "task_complete", "turn_id": "turn-a"},
            },
            {
                "type": "token_usage_record",
                "timestamp": "2026-11-17T00:00:05Z",
                "payload": {
                    "thread_id": thread,
                    "turn_id": "turn-a",
                    "response_id": "response-a",
                    "usage": self.usage,
                    "thread_token_usage": {"total_tokens": 999999},
                },
            },
        ]

    def write(self, records, name="a.jsonl", extra=b""):
        p = self.source / "sessions" / name
        p.write_bytes(b"".join(m.encoded(r).replace(b"\n", b"") + b"\n" for r in records) + extra)
        return p

    def build(self, entries=None, rates=None):
        return m.build(self.source, self.project, entries or [], rates or [])[0]

    def rate(self):
        return {
            "id": "rate",
            "model": "model-a",
            "provider": "provider",
            "currency": "USD",
            "basis": "standard-list-assumption",
            "effective_start": "2026-11-17T00:00:00Z",
            "effective_end": "2026-11-18T00:00:00Z",
            "denominator": "1000000",
            "prices": {"input": "2", "cached_input": "0.1", "output": "10"},
            "manual_provenance": "synthetic fixture",
        }

    def test_dedup_mirrors_privacy(self):
        self.write(self.records())
        self.write(self.records(), "b.jsonl")
        a = self.build()
        self.assertEqual(a["totals"]["responses"], 1)
        self.assertEqual(a["totals"]["known_tokens"]["total_tokens"], 120)
        self.assertNotIn("SECRET_BODY_SENTINEL", m.encoded(a).decode())
        self.assertNotIn(str(self.project), m.encoded(a).decode())
        self.assertEqual(a["time"]["closed_interval_union_seconds"], 10)

    def test_conflict_quarantine(self):
        r = self.records()
        self.write(r)
        r[-1]["payload"]["usage"] = {**self.usage, "output_tokens": 99}
        self.write(r, "b.jsonl")
        self.assertEqual(self.build()["totals"]["responses"], 0)

    def test_duplicate_response_metadata_conflicts_order_independent(self):
        for field in ("model", "model_provider", "effort", "service_tier", "timestamp"):
            with self.subTest(field=field):
                first = self.records()
                second = copy.deepcopy(first)
                if field == "timestamp":
                    second[-1]["timestamp"] = "2026-11-18T00:00:05Z"
                else:
                    first[-1]["payload"][field] = "value-a"
                    second[-1]["payload"][field] = "value-b"
                self.write(first)
                self.write(second, "b.jsonl")
                a = self.build()
                self.assertEqual(a["totals"]["responses"], 0)
                self.assertEqual(a["diagnostics"]["conflicting_response"], 1)
                self.write(second)
                self.write(first, "b.jsonl")
                b = self.build()
                self.assertEqual(a["totals"], b["totals"])
                self.assertEqual(a["diagnostics"], b["diagnostics"])

    def test_unknown_cache_write_is_unpriced_in_snapshot_and_scenario(self):
        records = self.records()
        records[-1]["payload"]["usage"].pop("cache_write_input_tokens")
        self.write(records)
        self.pricing.write_text(json.dumps({"rates": [self.rate()]}))
        a = self.build(rates=m.rates_validate({"rates": [self.rate()]}))
        self.assertIsNone(a["responses"][0]["cost"])
        self.assertEqual(a["totals"]["missing_tokens"]["cache_write_input_tokens"], 1)
        self.assertEqual(a["totals"]["unpriced_responses"], 1)
        result = m.refresh(self.source, self.project, self.out, self.mapping, self.pricing)
        frozen = json.loads((self.out / result["snapshot"] / "accounting.json").read_text())
        self.assertEqual(frozen["current_list_scenario"]["totals"]["unpriced_responses"], 1)

    def test_null_zero_truncated_malformed(self):
        r = self.records()
        r[-1]["payload"]["usage"] = {"input_tokens": 0}
        self.write(r, extra=b'broken\n{"partial":')
        a = self.build()
        self.assertEqual(a["totals"]["known_tokens"]["input_tokens"], 0)
        self.assertEqual(a["totals"]["missing_tokens"]["output_tokens"], 1)
        self.assertEqual(a["diagnostics"]["partial_line"], 1)
        self.assertEqual(a["diagnostics"]["malformed_record"], 1)

    def test_filter_exact_descendants(self):
        self.write(self.records())
        self.write(self.records("other", self.root / "project-other"), "b.jsonl")
        r = self.records("child", parent="thread-a")
        r[0]["payload"]["cwd"] = None
        self.write(r, "c.jsonl")
        self.assertEqual(self.build()["coverage"]["included_threads"], 2)

    def test_project_conflict(self):
        r = self.records()
        self.write(r)
        r[0]["payload"]["cwd"] = str(self.root / "elsewhere")
        self.write(r, "b.jsonl")
        self.assertEqual(self.build()["coverage"]["included_threads"], 0)

    def test_settings_history_and_ambiguity(self):
        r = self.records()
        r.insert(2, {"type": "turn_context", "payload": {"turn_id": "turn-b", "model": "model-b"}})
        self.write(r)
        self.assertEqual(self.build()["responses"][0]["model"], "model-a")
        r.insert(2, {"type": "turn_context", "payload": {"turn_id": "turn-a", "model": "model-b"}})
        self.write(r)
        self.assertIsNone(self.build()["responses"][0]["model"])

    def test_override_independent_mixed_time(self):
        self.write(self.records())
        tid = m.ident("thread-a")
        rid = m.ident("response-a")
        entries = m.validate_map(
            {
                "entries": [
                    {"level": "thread", "id": tid, "phase": "requirements", "feature": "feature-a"},
                    {"level": "response", "id": rid, "phase": "review", "task": "task-a"},
                ]
            }
        )
        a = self.build(entries)
        r = a["responses"][0]
        self.assertEqual((r["phase"], r["feature"], r["task"]), ("review", "feature-a", "task-a"))
        self.assertEqual(a["turns"][0]["phase"], "mixed")
        self.assertEqual(a["time"]["recorded_duration_seconds"], 0)
        self.assertEqual(a["time"]["derived_interval_duration_seconds"], 10)

    def test_invalid_map(self):
        for entries in [
            [{"level": "thread", "id": "a", "phase": "invalid"}],
            [{"level": "thread", "id": "a", "feature": "=FORMULA"}],
            [{"level": "thread", "id": "a", "phase": "review"}] * 2,
        ]:
            with self.assertRaises(ValueError):
                m.validate_map({"entries": entries})

    def test_private_paths_must_be_outside_checkout(self):
        with self.assertRaises(ValueError):
            m.outside_checkout(Path(__file__).resolve())
        self.assertEqual(m.outside_checkout(self.root / "private"), (self.root / "private").resolve())

    def test_cost_decimal_subset_and_dates(self):
        self.write(self.records())
        rates = m.rates_validate({"rates": [self.rate()]})
        row = self.build(rates=rates)["responses"][0]
        self.assertEqual(row["cost"], "0.000286")
        self.assertIsNone(row["tier"])
        self.assertEqual(row["cost_assumption"], "standard-list-assumption")
        row["timestamp"] = "2026-11-18T00:00:00Z"
        self.assertIsNone(m.price(row, rates)["cost"])

    def test_unpriced_invalid_and_unsupported(self):
        self.write(self.records())
        r = self.build()["responses"][0]
        rates = m.rates_validate({"rates": [self.rate()]})
        for key, val in [("model", None), ("provider", None), ("timestamp", None), ("tier", "fast")]:
            with self.subTest(key=key):
                self.assertIsNone(m.price({**r, key: val}, rates)["cost"])
        for key, val in [
            ("input_tokens", None),
            ("cached_input_tokens", 101),
            ("cache_write_input_tokens", None),
            ("cache_write_input_tokens", 2),
            ("reasoning_output_tokens", 21),
        ]:
            with self.subTest(key=key):
                self.assertIsNone(m.price({**r, "usage": {**r["usage"], key: val}}, rates)["cost"])

    def test_invalid_rates(self):
        for value in ["NaN", "Infinity", "-1", "bad"]:
            r = self.rate()
            r["prices"]["input"] = value
            with self.assertRaises(ValueError):
                m.rates_validate({"rates": [r]})
        r = self.rate()
        r["denominator"] = "0"
        with self.assertRaises(ValueError):
            m.rates_validate({"rates": [r]})
        with self.assertRaises(ValueError):
            m.rates_validate({"rates": [self.rate(), {**self.rate(), "id": "second"}]})

    def test_currency_reconciliation(self):
        self.write(self.records())
        a = self.build(rates=m.rates_validate({"rates": [self.rate()]}))
        self.assertEqual(a["totals"]["estimated_subtotal_by_currency"], {"USD": "0.000286"})
        for dim in m.DIMS:
            rows = [r for r in a["dimension_summaries"] if r["dimension"] == dim]
            self.assertEqual(sum(r["responses"] for r in rows), 1)
            self.assertEqual(
                sum(m.Decimal(r["estimated_subtotal_by_currency"].get("USD", "0")) for r in rows), m.Decimal("0.000286")
            )
        b = copy.deepcopy(a["responses"][0])
        b["currency"] = "EUR"
        self.assertEqual(set(m.aggregate([a["responses"][0], b])["estimated_subtotal_by_currency"]), {"USD", "EUR"})

    def test_union_open_reversed(self):
        self.assertEqual(m.union([(0, 10), (2, 4), (5, 20), (30, 40)]), 30)
        r = self.records()
        r.pop(3)
        self.write(r)
        self.assertEqual(self.build()["time"]["open_turns"], 1)
        r = self.records()
        r[3]["timestamp"] = "2026-11-16T00:00:00Z"
        self.write(r)
        self.assertEqual(self.build()["diagnostics"]["reversed_interval"], 1)

    def test_missing_id_and_lineage_cycle(self):
        r = self.records(parent="thread-a")
        r[-1]["payload"].pop("response_id")
        self.write(r)
        a = self.build()
        self.assertEqual(a["diagnostics"]["degraded_response_identity"], 1)
        self.assertEqual(a["sessions"][0]["root_id"], "unknown")

    def test_snapshot_repeat_failure_lock_hash_modes(self):
        self.write(self.records())
        result = m.refresh(self.source, self.project, self.out, self.mapping, self.pricing)
        pointer = (self.out / "current.json").read_bytes()
        snap = self.out / result["snapshot"]
        report = (snap / "report.md").read_text()
        self.assertIn(
            "Refresh: `python3 tools/local-usage/codex_refresh.py --source-root PATH --project-root PATH "
            "--output PATH --phase-map PATH --prices PATH`",
            report,
        )
        manifest = json.loads((snap / "manifest.json").read_text())
        for name, h in manifest["outputs"].items():
            self.assertEqual(m.digest((snap / name).read_bytes()), h)
            self.assertEqual((snap / name).stat().st_mode & 0o777, 0o600)
        first = json.loads((snap / "accounting.json").read_text())
        second = m.refresh(self.source, self.project, self.out, self.mapping, self.pricing)
        self.assertEqual(
            first["totals"], json.loads((self.out / second["snapshot"] / "accounting.json").read_text())["totals"]
        )
        pointer = (self.out / "current.json").read_bytes()
        with patch.object(m, "private_write", side_effect=OSError("synthetic")), self.assertRaises(OSError):
            m.refresh(self.source, self.project, self.out, self.mapping, self.pricing)
        self.assertEqual((self.out / "current.json").read_bytes(), pointer)
        (self.out / ".refresh.lock").touch()
        with self.assertRaises(ValueError):
            m.refresh(self.source, self.project, self.out, self.mapping, self.pricing)
        self.assertEqual(self.mapping.read_text(), '{"entries":[]}')

    def test_missing_source_or_project_preserves_previous_pointer(self):
        with self.assertRaises(ValueError):
            m.refresh(self.source / "missing", self.project, self.out, self.mapping, self.pricing)
        with self.assertRaises(ValueError):
            m.refresh(self.source, self.project / "missing", self.out, self.mapping, self.pricing)
        self.assertFalse((self.out / "current.json").exists())

    def test_recorded_and_derived_duration_are_separate(self):
        self.write(self.records())
        database = sqlite3.connect(self.source / "thread_history_1.sqlite")
        database.execute(
            "CREATE TABLE thread_turns (thread_id TEXT, turn_id TEXT, started_at TEXT, completed_at TEXT, duration_ms INTEGER, root_turn_id TEXT)"
        )
        database.executemany(
            "INSERT INTO thread_turns VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    "thread-a",
                    "turn-a",
                    "2026-11-17T00:00:00Z",
                    "2026-11-17T00:00:10Z",
                    5000,
                    "root-a",
                ),
                (
                    "thread-a",
                    "turn-b",
                    "2026-11-17T00:01:00Z",
                    "2026-11-17T00:01:10Z",
                    -1,
                    "root-a",
                ),
                ("thread-a", "turn-c", "2026-11-17T00:02:00Z", None, None, "root-a"),
            ],
        )
        database.commit()
        database.close()

        account = self.build()
        self.assertEqual(account["time"]["recorded_duration_seconds"], 5)
        self.assertEqual(account["time"]["derived_interval_duration_seconds"], 10)
        self.assertEqual(account["time"]["total_known_duration_seconds"], 15)
        self.assertEqual(account["time"]["missing_duration_turns"], 1)
        self.assertEqual(account["diagnostics"]["invalid_duration_ms"], 1)
        sources = {row["turn_id"]: row["duration_source"] for row in account["turns"]}
        self.assertEqual(sources[m.ident("turn-a")], "sqlite_recorded_ms")
        self.assertEqual(sources[m.ident("turn-b")], "derived_interval")
        self.assertEqual(sources[m.ident("turn-c")], "unknown")


if __name__ == "__main__":
    unittest.main()
