"""Local, offline, metadata-only Codex accounting snapshot builder."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import tempfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

METRICS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)
PHASES = (
    "requirements",
    "architecture",
    "planning",
    "implementation",
    "verification",
    "review",
    "integration",
    "release preparation",
    "post-release verification",
    "coordinator",
    "mixed",
    "unknown",
)
SETTINGS = {"model": "model", "provider": "model_provider", "effort": "effort", "tier": "service_tier"}
DIMS = ("phase", "feature", "task", "thread", "root", "turn", "response", "model")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()


def safe(value: Any) -> str | None:
    if (
        isinstance(value, str)
        and re.fullmatch(r"[A-Za-z0-9_.:/ -]{1,180}", value)
        and not value.startswith(("=", "+", "-", "@"))
    ):
        return value
    return None


def ident(value: Any) -> str:
    if value is None:
        return "unknown"
    return digest(str(value).encode())[:24]


def stamp(value: Any) -> float | None:
    try:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (ValueError, OverflowError):
        pass
    return None


def iso(value: float | None) -> str | None:
    return datetime.fromtimestamp(value, UTC).isoformat() if value is not None else None


def union(intervals: list[tuple[float, float]]) -> float:
    end = None
    total = 0.0
    for a, b in sorted(intervals):
        if end is None or a > end:
            total += b - a
        elif b > end:
            total += b - end
        end = max(end or b, b)
    return total


def validate_map(obj: dict) -> list[dict]:
    result = []
    seen = set()
    for r in obj.get("entries", []):
        level = r.get("level")
        key = r.get("id")
        if level not in ("response", "turn", "thread") or not safe(key):
            raise ValueError("invalid mapping identity")
        for dim in ("phase", "feature", "task"):
            if dim not in r:
                continue
            value = r[dim]
            if not safe(value) or (dim == "phase" and value not in PHASES):
                raise ValueError("invalid mapping label")
            k = (level, key, dim)
            if k in seen:
                raise ValueError("duplicate mapping dimension")
            seen.add(k)
        result.append(r)
    return result


def assign(row: dict, entries: list[dict], dim: str) -> tuple[str, str]:
    for level in ("response", "turn", "thread"):
        for entry in entries:
            if entry["level"] == level and entry["id"] == row.get(level + "_id") and dim in entry:
                return entry[dim], "manual"
    if dim == "phase":
        return row.get("inferred_phase", "unknown"), "inferred" if row.get(
            "inferred_phase", "unknown"
        ) != "unknown" else "unknown"
    return "unknown", "unknown"


def rates_validate(obj: dict) -> list[dict]:
    rates = obj.get("rates", [])
    ids = set()
    for r in rates:
        for k in ("id", "model", "provider", "currency", "basis"):
            if not safe(r.get(k)):
                raise ValueError("invalid rate metadata")
        if r["id"] in ids:
            raise ValueError("duplicate rate id")
        ids.add(r["id"])
        if not r.get("source_url") and not r.get("manual_provenance"):
            raise ValueError("missing rate provenance")
        if r.get("source_url") and (not r["source_url"].startswith("https://") or not r.get("retrieved_date")):
            raise ValueError("invalid official provenance")
        a = stamp(r.get("effective_start"))
        b = stamp(r.get("effective_end")) if r.get("effective_end") else float("inf")
        if a is None or b is None or b <= a:
            raise ValueError("invalid rate dates")
        r["_start"] = a
        r["_end"] = b
        for k, v in {"denominator": r.get("denominator"), **r.get("prices", {})}.items():
            if not isinstance(v, str):
                raise ValueError("rates require decimal strings")
            try:
                d = Decimal(v)
            except InvalidOperation:
                raise ValueError("invalid decimal") from None
            if not d.is_finite() or d < 0 or (k == "denominator" and d == 0):
                raise ValueError("invalid decimal")
        for old in rates[: rates.index(r)]:
            if (
                (r["model"], r["provider"]) == (old["model"], old["provider"])
                and (r.get("tier") == old.get("tier") or not r.get("tier") or not old.get("tier"))
                and max(a, old["_start"]) < min(b, old["_end"])
            ):
                raise ValueError("overlapping rates")
    return rates


def price(row: dict, rates: list[dict]) -> dict:
    result = {"cost": None, "currency": None, "rate_id": None, "cost_status": "unpriced", "cost_assumption": None}
    t = stamp(row.get("timestamp"))
    if t is None or not row.get("model") or not row.get("provider"):
        return result
    matches = [
        r
        for r in rates
        if r["model"] == row["model"]
        and r["provider"] == row["provider"]
        and r["_start"] <= t < r["_end"]
        and not r.get("context_threshold")
        and (r.get("tier") == row.get("tier") if row.get("tier") else r["basis"] == "standard-list-assumption")
    ]
    if len(matches) != 1:
        return result
    r = matches[0]
    u = row["usage"]
    inp = u["input_tokens"]
    cached = u["cached_input_tokens"]
    out = u["output_tokens"]
    if r.get("max_input_tokens") is not None and (inp is None or inp > r["max_input_tokens"]):
        return result
    if inp is None or cached is None or out is None or u["cache_write_input_tokens"] != 0:
        return result
    if cached > inp or (u["reasoning_output_tokens"] is not None and u["reasoning_output_tokens"] > out):
        return {**result, "cost_status": "invalid"}
    if not all(k in r["prices"] for k in ("input", "cached_input", "output")):
        return result
    cost = (
        Decimal(inp - cached) * Decimal(r["prices"]["input"])
        + Decimal(cached) * Decimal(r["prices"]["cached_input"])
        + Decimal(out) * Decimal(r["prices"]["output"])
    ) / Decimal(r["denominator"])
    return {
        "cost": str(cost),
        "currency": r["currency"],
        "rate_id": r["id"],
        "cost_status": "estimated",
        "cost_assumption": r["basis"],
    }


def read_db(path: Path, table: str, cols: list[str], diagnostics: Counter) -> list[dict]:
    if not path.exists():
        diagnostics["missing_database"] += 1
        return []
    try:
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as c:
            c.execute("BEGIN")
            actual = {r[1] for r in c.execute("pragma table_info(" + table + ")")}
            selected = [k for k in cols if k in actual]
            if not selected:
                diagnostics["unsupported_database_schema"] += 1
                return []
            c.row_factory = sqlite3.Row
            return [dict(r) for r in c.execute("select " + ",".join(selected) + " from " + table)]
    except sqlite3.Error:
        diagnostics["inaccessible_database"] += 1
        return []


def aggregate(rows: list[dict]) -> dict:
    costs = defaultdict(Decimal)
    missing = {k: sum(r["usage"][k] is None for r in rows) for k in METRICS}
    for r in rows:
        if r["cost"] is not None:
            costs[r["currency"]] += Decimal(r["cost"])
    return {
        "responses": len(rows),
        "known_tokens": {k: sum(r["usage"][k] or 0 for r in rows) for k in METRICS},
        "missing_tokens": missing,
        "estimated_subtotal_by_currency": {k: str(v) for k, v in sorted(costs.items())},
        "unpriced_responses": sum(r["cost"] is None for r in rows),
        "unpriced_known_total_tokens": sum(r["usage"]["total_tokens"] or 0 for r in rows if r["cost"] is None),
    }


def build(source: Path, project: Path, entries: list[dict], rates: list[dict]) -> tuple[dict, list[dict]]:
    diag = Counter()
    inventory = []
    meta = defaultdict(list)
    contexts = defaultdict(list)
    responses = []
    timing = defaultdict(dict)
    dbthreads = read_db(
        source / "state_5.sqlite",
        "threads",
        [
            "id",
            "cwd",
            "rollout_path",
            "model",
            "model_provider",
            "reasoning_effort",
            "agent_path",
            "attached_thread_parent_id",
        ],
        diag,
    )
    edges = read_db(source / "state_5.sqlite", "thread_spawn_edges", ["parent_thread_id", "child_thread_id"], diag)
    dbturns = read_db(
        source / "thread_history_1.sqlite",
        "thread_turns",
        ["thread_id", "turn_id", "started_at", "completed_at", "duration_ms", "root_turn_id"],
        diag,
    )
    for name, rows in [("threads", dbthreads), ("edges", edges), ("turns", dbturns)]:
        inventory.append({"category": "sqlite-" + name, "sha256": digest(encoded(rows)), "records": len(rows)})
    files = set(source.glob("sessions/**/*.jsonl")) | set(source.glob("archived_sessions/**/*.jsonl"))
    files |= {Path(r["rollout_path"]) for r in dbthreads if r.get("rollout_path")}
    for r in dbthreads:
        meta[r["id"]].append(r)
    for path in sorted(files):
        try:
            with path.open("rb") as f:
                data = f.read(os.fstat(f.fileno()).st_size)
        except OSError:
            diag["inaccessible_rollout"] += 1
            continue
        inventory.append(
            {
                "category": "rollout",
                "source_id": digest(str(path.resolve()).encode()),
                "sha256": digest(data),
                "bytes": len(data),
            }
        )
        thread = None
        lines = data.splitlines(keepends=True)
        for line in lines:
            if not line.endswith(b"\n"):
                diag["partial_line"] += 1
                continue
            try:
                record = json.loads(line)
                p = record.get("payload", {})
                typ = record.get("type")
            except (ValueError, AttributeError):
                diag["malformed_record"] += 1
                continue
            if not isinstance(p, dict):
                diag["malformed_record"] += 1
                continue
            if typ == "session_meta":
                thread = p.get("id") or p.get("session_id")
                meta[thread].append(
                    {k: p.get(k) for k in ("id", "cwd", "parent_thread_id", "agent_path", "model_provider")}
                )
            elif typ == "turn_context" and thread:
                contexts[(thread, p.get("turn_id"))].append(
                    {k: p.get(k) for k in ("model", "model_provider", "effort", "service_tier")}
                )
            elif typ == "token_usage_record":
                responses.append(
                    {
                        "thread": p.get("thread_id") or thread,
                        "turn": p.get("turn_id"),
                        "response": p.get("response_id"),
                        "timestamp": record.get("timestamp"),
                        "raw_usage": p.get("usage"),
                        "settings": {k: p.get(v) for k, v in SETTINGS.items()},
                    }
                )
            elif typ == "event_msg" and p.get("type") in ("task_started", "task_complete") and thread:
                k = (thread, p.get("turn_id"))
                field = "start" if p["type"] == "task_started" else "end"
                val = stamp(p.get("started_at") if field == "start" else None) or stamp(record.get("timestamp"))
                if field in timing[k] and timing[k][field] != val:
                    diag["timing_conflict"] += 1
                timing[k][field] = val
    parents = {e.get("child_thread_id"): e.get("parent_thread_id") for e in edges}
    eligible = set()
    explicit_other = set()
    norm = str(project.resolve())
    for tid, records in meta.items():
        cwds = {str(Path(r["cwd"]).resolve()) for r in records if r.get("cwd")}
        if cwds == {norm}:
            eligible.add(tid)
        elif cwds:
            explicit_other.add(tid)
            diag["project_conflict" if len(cwds) > 1 else "different_project"] += 1
        ps = {r.get("parent_thread_id") or r.get("attached_thread_parent_id") for r in records} - {None}
        if len(ps) == 1:
            parents[tid] = next(iter(ps))
        elif len(ps) > 1:
            diag["parent_conflict"] += 1
    while True:
        new = {t for t, p in parents.items() if p in eligible and t not in explicit_other} - eligible
        if not new:
            break
        eligible |= new

    def root(t: str) -> str:
        seen = set()
        cur = t
        while parents.get(cur):
            if cur in seen:
                diag["parent_cycle"] += 1
                return "unknown"
            seen.add(cur)
            cur = parents[cur]
        if cur not in meta:
            diag["missing_parent"] += 1
        return ident(cur)

    sessions = []
    inferred = {}
    roots = {}
    for t in sorted(eligible):
        paths = {r.get("agent_path") for r in meta[t] if r.get("agent_path")}
        phase = "unknown"
        if len(paths) == 1:
            seg = next(iter(paths)).split("/")[-1].lower()
            for candidate, words in [
                ("requirements", ("scope", "requirement")),
                ("architecture", ("design", "architect")),
                ("planning", ("plan",)),
                ("implementation", ("implement",)),
                ("verification", ("verify", "verification")),
                ("review", ("review", "reconcile")),
                ("integration", ("integrat",)),
                ("release preparation", ("release",)),
            ]:
                if any(w in seg for w in words):
                    phase = candidate
                    break
        inferred[t] = phase
        roots[t] = root(t)
        sessions.append(
            {"thread_id": ident(t), "parent_id": ident(parents.get(t)), "root_id": roots[t], "inferred_phase": phase}
        )
    canonical = {}
    conflicts = set()
    for r in responses:
        if r["thread"] not in eligible:
            continue
        raw = r.pop("raw_usage")
        usage = {
            k: (raw.get(k) if isinstance(raw, dict) and type(raw.get(k)) is int and raw[k] >= 0 else None)
            for k in METRICS
        }
        r["usage"] = usage
        key = (
            r["thread"],
            r["response"] or digest(encoded({k: r[k] for k in ("thread", "turn", "timestamp", "usage")})),
        )
        if not r["response"]:
            diag["degraded_response_identity"] += 1
        if key in canonical:
            old = canonical[key]
            if (old["usage"], old["turn"], old["timestamp"], old["settings"]) != (
                usage,
                r["turn"],
                r["timestamp"],
                r["settings"],
            ):
                conflicts.add(key)
            else:
                diag["duplicate_response"] += 1
        else:
            canonical[key] = r
    diag["conflicting_response"] = len(conflicts)
    rows = []
    for key, r in sorted(canonical.items()):
        if key in conflicts:
            continue
        t = r["thread"]
        turn = r["turn"]
        row = {
            "thread_id": ident(t),
            "turn_id": ident(turn),
            "response_id": ident(r["response"]) if r["response"] else key[1][:24],
            "root_id": roots[t],
            "timestamp": r["timestamp"] if stamp(r["timestamp"]) is not None else None,
            "usage": r["usage"],
            "inferred_phase": inferred[t],
        }
        for setting, pkey in SETTINGS.items():
            v = safe(r["settings"].get(setting))
            basis = "response" if v else "unknown"
            if not v:
                values = {safe(c.get(pkey)) for c in contexts[(t, turn)]} - {None}
                if len(values) == 1:
                    v = next(iter(values))
                    basis = "turn_context"
                elif len(values) > 1:
                    basis = "ambiguous"
                    diag["setting_conflict"] += 1
                else:
                    column = "reasoning_effort" if setting == "effort" else pkey
                    values = {safe(m.get(column)) for m in meta[t]} - {None}
                    if len(values) == 1:
                        v = next(iter(values))
                        basis = "thread_fallback"
                    elif len(values) > 1:
                        basis = "ambiguous"
                        diag["setting_conflict"] += 1
            row[setting] = v
            row[setting + "_source"] = basis
        u = row["usage"]
        if (
            u["input_tokens"] is not None
            and u["cached_input_tokens"] is not None
            and u["cached_input_tokens"] > u["input_tokens"]
        ):
            diag["invalid_cached_subset"] += 1
        if (
            u["output_tokens"] is not None
            and u["reasoning_output_tokens"] is not None
            and u["reasoning_output_tokens"] > u["output_tokens"]
        ):
            diag["invalid_reasoning_subset"] += 1
        if (
            all(u[k] is not None for k in ("input_tokens", "output_tokens", "total_tokens"))
            and u["input_tokens"] + u["output_tokens"] != u["total_tokens"]
        ):
            diag["recorded_total_mismatch"] += 1
        for dim in ("phase", "feature", "task"):
            row[dim], row[dim + "_basis"] = assign(row, entries, dim)
        row.update(price(row, rates))
        rows.append(row)
    sqlturns = {(r["thread_id"], r["turn_id"]): r for r in dbturns if r["thread_id"] in eligible}
    turns = []
    turnkeys = (
        set(sqlturns)
        | {k for k in timing if k[0] in eligible}
        | {(r["thread"], r["turn"]) for r in canonical.values() if r["thread"] in eligible}
    )
    for t, tr in sorted(turnkeys, key=str):
        sql = sqlturns.get((t, tr), {})
        log = timing.get((t, tr), {})
        a = log.get("start")
        b = log.get("end")
        source_name = "rollout"
        if a is None or b is None:
            a = stamp(sql.get("started_at"))
            b = stamp(sql.get("completed_at"))
            source_name = "sqlite"
        if a is not None and b is not None and b < a:
            diag["reversed_interval"] += 1
            a = b = None
        sql_started = stamp(sql.get("started_at"))
        if log.get("start") is not None and log.get("end") is not None and sql_started is not None:
            if abs(log["start"] - sql_started) > 2:
                diag["interval_source_conflict"] += 1
        ms = sql.get("duration_ms")
        recorded_duration = isinstance(ms, (int, float)) and not isinstance(ms, bool) and ms >= 0
        if ms is not None and not recorded_duration:
            diag["invalid_duration_ms"] += 1
        if recorded_duration:
            duration = ms / 1000
            duration_source = "sqlite_recorded_ms"
        elif a is not None and b is not None:
            duration = b - a
            duration_source = "derived_interval"
        else:
            duration = None
            duration_source = "unknown"
        row = {
            "thread_id": ident(t),
            "turn_id": ident(tr),
            "root_id": roots[t],
            "start": iso(a),
            "end": iso(b),
            "duration_seconds": duration,
            "duration_ms": ms,
            "duration_source": duration_source,
            "interval_source": source_name,
            "inferred_phase": inferred[t],
        }
        for dim in ("phase", "feature", "task"):
            row[dim], row[dim + "_basis"] = assign(row, entries, dim)
            response_values = {
                r[dim] for r in rows if r["thread_id"] == row["thread_id"] and r["turn_id"] == row["turn_id"]
            }
            if response_values and response_values != {row[dim]}:
                row[dim] = "mixed"
                row[dim + "_basis"] = "unallocated_response_override"
                diag["unallocated_turn_" + dim] += 1
        turns.append(row)
    summaries = []
    for dim in DIMS:
        groups = defaultdict(list)
        for r in rows:
            group = r.get(dim) if dim in ("phase", "feature", "task", "model") else r.get(dim + "_id")
            groups[
                (
                    group or "unknown",
                    r["model"] or "unknown",
                    r["provider"] or "unknown",
                    r["effort"] or "unknown",
                    r["tier"] or "unknown",
                )
            ].append(r)
        for (group, model, provider, effort, tier), rr in sorted(groups.items()):
            summaries.append(
                {
                    "dimension": dim,
                    "group": group,
                    "model": model,
                    "provider": provider,
                    "effort": effort,
                    "tier": tier,
                    **aggregate(rr),
                }
            )

    def time_stats(tt: list[dict]) -> dict:
        intervals = [(stamp(t["start"]), stamp(t["end"])) for t in tt if t["start"] and t["end"]]
        recorded = [t["duration_seconds"] or 0 for t in tt if t["duration_source"] == "sqlite_recorded_ms"]
        derived = [t["duration_seconds"] or 0 for t in tt if t["duration_source"] == "derived_interval"]
        return {
            "recorded_duration_seconds": sum(recorded),
            "derived_interval_duration_seconds": sum(derived),
            "total_known_duration_seconds": sum(recorded) + sum(derived),
            "missing_duration_turns": sum(t["duration_source"] == "unknown" for t in tt),
            "closed_interval_union_seconds": union(intervals),
            "summed_interval_seconds": sum(b - a for a, b in intervals),
            "overlap_seconds": sum(b - a for a, b in intervals) - union(intervals),
            "span_seconds": max(b for _, b in intervals) - min(a for a, _ in intervals) if intervals else None,
            "open_turns": sum(not t["end"] for t in tt),
        }

    time_groups = []
    for dim in ("phase", "feature", "task", "thread", "root"):
        gs = defaultdict(list)
        for t in turns:
            gs[t.get(dim) if dim in ("phase", "feature", "task") else t[dim + "_id"]].append(t)
        for group, tt in sorted(gs.items()):
            time_groups.append({"dimension": dim, "group": group, **time_stats(tt)})
    for name in ("logs_2.sqlite", "history.jsonl", "session_index.jsonl"):
        inventory.append(
            {"category": name, "status": "inventory_only_not_used" if (source / name).exists() else "absent"}
        )
    return {
        "schema_version": 1,
        "project": "local-project",
        "sessions": sessions,
        "turns": turns,
        "responses": rows,
        "dimension_summaries": summaries,
        "time_groups": time_groups,
        "totals": aggregate(rows),
        "time": time_stats(turns),
        "diagnostics": dict(sorted(diag.items())),
        "coverage": {
            "included_threads": len(eligible),
            "discovered_threads": len(meta),
            "canonical_conflicts_excluded": len(conflicts),
            "historical_completeness": "unknown",
            "model_time": "unknown",
        },
    }, inventory


def csv_bytes(rows: list[dict]) -> bytes:
    flattened = []
    for row in rows:
        flat = {}
        for k, v in row.items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    flat[k + "_" + kk] = vv
            else:
                flat[k] = v
        flattened.append(flat)
    out = io.StringIO()
    fields = sorted({k for r in flattened for k in r})
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for row in flattened:
        writer.writerow(
            {k: ("'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v) for k, v in row.items()}
        )
    return out.getvalue().encode()


def private_write(path: Path, data: bytes) -> None:
    path.write_bytes(data)
    path.chmod(0o600)


def outside_checkout(path: Path) -> Path:
    """Reject private input/output paths located in a Git checkout."""
    path = path.expanduser().resolve()
    for parent in (path, *path.parents):
        marker = parent / ".git"
        if marker.exists() or marker.is_symlink():
            raise ValueError("private data paths must be outside Git checkouts")
    return path


def refresh(source: Path, project: Path, output: Path, mapping: Path, pricing: Path) -> dict:
    if not source.is_dir() or not project.is_dir():
        raise ValueError("source and project paths must name existing directories")
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    output.chmod(0o700)
    lock = output / ".refresh.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("refresh already locked") from None
    os.close(fd)
    temp = None
    try:
        mapdata = mapping.read_bytes()
        pricedata = pricing.read_bytes()
        entries = validate_map(json.loads(mapdata))
        rates = rates_validate(json.loads(pricedata))
        account, inventory = build(source, project, entries, rates)
        observed = datetime.now(UTC).isoformat()
        account["observed_at"] = observed
        scenario = []
        for row in account["responses"]:
            hypothetical = {**row, "timestamp": observed}
            hypothetical.update(price(hypothetical, rates))
            scenario.append(hypothetical)
        account["current_list_scenario"] = {
            "basis": "Counterfactual current public API standard list-price equivalent for all recorded usage; not historical rates or actual billing.",
            "rate_observation_date": observed[:10],
            "totals": aggregate(scenario),
            "dimension_summaries": [],
        }
        for dim in DIMS:
            groups = defaultdict(list)
            for row in scenario:
                groups[row.get(dim) if dim in ("phase", "feature", "task", "model") else row.get(dim + "_id")].append(
                    row
                )
            for group, rr in sorted(groups.items(), key=lambda kv: str(kv[0])):
                account["current_list_scenario"]["dimension_summaries"].append(
                    {"dimension": dim, "group": group or "unknown", **aggregate(rr)}
                )
        parent = output / "snapshots"
        parent.mkdir(mode=0o700, exist_ok=True)
        temp = Path(tempfile.mkdtemp(prefix=".building-", dir=parent))
        temp.chmod(0o700)
        outputs = {
            "accounting.json": encoded(account),
            "sessions.csv": csv_bytes(account["sessions"]),
            "turns.csv": csv_bytes(account["turns"]),
            "usage.csv": csv_bytes(account["responses"]),
            "dimension-summary.csv": csv_bytes(account["dimension_summaries"]),
            "phase-summary.csv": csv_bytes([r for r in account["dimension_summaries"] if r["dimension"] == "phase"]),
        }
        report = f"""# Local Codex usage accounting\n\nObserved: {observed}\n\nRefresh: `python3 tools/local-usage/codex_refresh.py --source-root PATH --project-root PATH --output PATH --phase-map PATH --prices PATH`\n\n{len(account["sessions"])} included threads; {len(account["responses"])} trusted responses; {len(account["turns"])} observed turns.\n\nKnown token sums and missing counts: `{json.dumps(account["totals"]["known_tokens"])}`; missing: `{json.dumps(account["totals"]["missing_tokens"])}`. Cached input and reasoning are subsets, never additive.\n\nEstimated usage cost known subtotals by currency: `{json.dumps(account["totals"]["estimated_subtotal_by_currency"])}`. Unpriced responses: {account["totals"]["unpriced_responses"]}. These are incomplete estimated usage costs, not billed totals. Rates are editable public API list-price assumptions or explicitly supplied manual rates. Actual bills, subscription allowance, discounts, taxes and unavailable retries are unknown.\n\nTime: `{json.dumps(account["time"])}`. Recorded duration, interval-derived duration, closed interval union and observation span are separate. Category intervals overlap and cannot be added. Productive time and per-model generation time are unknown. Response overrides never duplicate turn time; inconsistent response categories leave mixed/unallocated time.\n\nPhase labels use manual mappings or low-confidence technical agent-path inference. Features and tasks remain unknown until independently mapped. The detailed CSV and JSON provide alternate phase/feature/task/thread/root/turn/response/model views; do not add views together. Model/provider/effort/tier sources accompany every response; thread fallback is historical uncertainty. Unknown service tier remains unknown even when a standard-list assumption is selected.\n\nPricing coverage by model: `{json.dumps({m: {"responses": sum(r["model"] == m for r in account["responses"]), "unpriced": sum(r["model"] == m and r["cost"] is None for r in account["responses"])} for m in sorted({r["model"] or "unknown" for r in account["responses"]})})}`.\n\nCounterfactual current-list API equivalent (all usage repriced at observation date, not historical rates or money paid): `{json.dumps(account["current_list_scenario"]["totals"])}`. See accounting.json for reconciled alternate-dimension scenario breakdowns.\n\nConfigured rate provenance: `{json.dumps([{k: v for k, v in r.items() if not k.startswith("_")} for r in rates])}`. No exact official rate is invented for unavailable model identifiers.\n\nCoverage: `{json.dumps(account["coverage"])}`. Diagnostics: `{json.dumps(account["diagnostics"])}`. Accessible local history only; historical completeness is unknown. Active turns and newly appended bytes are included on later refreshes. Mirror/cumulative counters never enter usage sums. Conflicting response identities are quarantined. Source inventory and hashes are in manifest.json; source content and paths are excluded.\n"""
        outputs["report.md"] = report.encode()
        for name, data in outputs.items():
            private_write(temp / name, data)
        manifest = {
            "schema_version": 1,
            "observed_at": observed,
            "inputs": {
                "script_sha256": digest(Path(__file__).read_bytes()),
                "mapping_sha256": digest(mapdata),
                "prices_sha256": digest(pricedata),
            },
            "sources": inventory,
            "outputs": {n: digest(d) for n, d in outputs.items()},
        }
        private_write(temp / "manifest.json", encoded(manifest))
        snapshot = digest(encoded(manifest))[:24]
        final = parent / snapshot
        temp.rename(final)
        temp = None
        pointer = {
            "snapshot": "snapshots/" + snapshot,
            "manifest_sha256": digest((final / "manifest.json").read_bytes()),
        }
        pending = output / ".current.tmp"
        private_write(pending, encoded(pointer))
        os.replace(pending, output / "current.json")
        return {
            "snapshot": pointer["snapshot"],
            "responses": len(account["responses"]),
            "totals": account["totals"],
            "time": account["time"],
            "diagnostics": account["diagnostics"],
        }
    finally:
        if temp is not None:
            shutil.rmtree(temp, ignore_errors=True)
        lock.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True, help="Explicit local Codex history directory.")
    parser.add_argument(
        "--project-root", type=Path, required=True, help="Exact project path recorded in local histories."
    )
    parser.add_argument("--output", type=Path, required=True, help="Private output directory outside Git checkouts.")
    parser.add_argument("--phase-map", type=Path, required=True, help="Private phase mapping JSON file.")
    parser.add_argument("--prices", type=Path, required=True, help="Private price mapping JSON file.")
    args = parser.parse_args()
    try:
        output = outside_checkout(args.output)
        mapping = outside_checkout(args.phase_map)
        pricing = outside_checkout(args.prices)
        result = refresh(args.source_root, args.project_root, output, mapping, pricing)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        print("Refresh failed: invalid input, unavailable source/output, or active lock; previous snapshot preserved.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
