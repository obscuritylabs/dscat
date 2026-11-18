"""Read-only native history capture into private associations and safe facts."""

from __future__ import annotations

import math
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .identity import domain, receipt
from .mapping import resolve, validate_entries
from .private import read_bytes, safe_path
from .schema import (
    DEFAULT_VOCABULARY,
    MAX_DIAGNOSTICS,
    MAX_FILE,
    MAX_PATH,
    MAX_RECORDS,
    MAX_TOTAL,
    TOKEN_KEYS,
    Observation,
    UsageError,
    Vocabulary,
    canonical,
    digest,
    integer,
    keys,
    loads,
    present,
    require,
    tokens,
)

MAX_NATIVE_ID = 512


@dataclass(frozen=True)
class Limits:
    """Limits schema and validated maintenance operations."""

    file_bytes: int = MAX_FILE
    total_bytes: int = MAX_TOTAL
    records: int = MAX_RECORDS
    diagnostics: int = MAX_DIAGNOSTICS

    def __post_init__(self) -> None:
        """Validate configured immutable field bounds."""
        for name, maximum in (
            ("file_bytes", MAX_FILE),
            ("total_bytes", MAX_TOTAL),
            ("records", MAX_RECORDS),
            ("diagnostics", MAX_DIAGNOSTICS),
        ):
            integer(getattr(self, name), 1, maximum)


@dataclass(frozen=True)
class Config:
    """Config schema and validated maintenance operations."""

    source_root: Path
    project_selector: str
    map_path: Path
    rates_path: Path
    vocabulary_path: Path
    secret_file: Path
    limits: Limits = Limits()
    schema: int = 1

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Config:
        """Construct and validate the supported schema from a mapping."""
        keys(
            value,
            {
                "schema",
                "source_root",
                "project_selector",
                "map_path",
                "rates_path",
                "vocabulary_path",
                "secret_file",
                "limits",
            },
        )
        integer(value["schema"], 1, 1)
        keys(value["limits"], {"file_bytes", "total_bytes", "records", "diagnostics"})
        for name in ("source_root", "project_selector", "map_path", "rates_path", "vocabulary_path", "secret_file"):
            require(
                isinstance(value[name], str) and 0 < len(value[name]) <= MAX_PATH and "\x00" not in value[name],
                "invalid private configuration",
            )
            require(Path(value[name]).is_absolute(), "explicit absolute configuration required")
        return cls(
            source_root=Path(value["source_root"]),
            project_selector=value["project_selector"],
            map_path=Path(value["map_path"]),
            rates_path=Path(value["rates_path"]),
            vocabulary_path=Path(value["vocabulary_path"]),
            secret_file=Path(value["secret_file"]),
            limits=Limits(**value["limits"]),
            schema=value["schema"],
        )


@dataclass(frozen=True)
class NativeAssociation:
    """Private only. Never serialize as a transport observation."""

    kind: str
    thread_id: str
    native_id: str | None
    receipt: str


@dataclass(frozen=True)
class Capture:
    """Capture schema and validated maintenance operations."""

    domain: str
    observed_at: str
    observations: tuple[Observation, ...]
    associations: tuple[NativeAssociation, ...]
    input_digests: dict[str, str]
    diagnostics: dict[str, int]
    coverage: dict[str, Any]


@dataclass
class _Budget:
    limits: Limits
    byte_count: int = 0
    record_count: int = 0
    diagnostics: dict[str, int] = field(default_factory=dict)

    def consume(self, size: int, records: int = 0) -> None:
        """Consume."""
        self.byte_count += size
        self.record_count += records
        require(
            self.byte_count <= self.limits.total_bytes and self.record_count <= self.limits.records,
            "capture resource limit",
            3,
        )

    def note(self, key: str) -> None:
        """Note."""
        require(
            key in self.diagnostics or len(self.diagnostics) < self.limits.diagnostics, "diagnostic resource limit", 3
        )
        self.diagnostics[key] = self.diagnostics.get(key, 0) + 1


def _stamp(value: object) -> str | None:
    if value is None:
        return None
    try:
        if type(value) is int or type(value) is float:
            require(math.isfinite(value), "invalid source timestamp", 4)
            result = datetime.fromtimestamp(value, UTC)
        elif isinstance(value, str):
            result = datetime.fromisoformat(value)
            require(result.tzinfo is not None, "source timestamp timezone unknown", 4)
        else:
            message = "unsupported source timestamp"
            raise UsageError(message, 3)
        return result.astimezone(UTC).isoformat()
    except (ValueError, OverflowError, OSError) as exc:
        message = "invalid source timestamp"
        raise UsageError(message, 4) from exc


def _same(target: dict[str, Any], key: str, value: object) -> None:
    if value is None:
        return
    require(key not in target or target[key] is None or target[key] == value, "native fact conflict", 4)
    target[key] = value


def _db(path: Path, tables: dict[str, tuple[set[str], set[str]]], budget: _Budget) -> dict[str, list[dict[str, Any]]]:
    safe_path(path)
    require(path.is_file() and path.stat().st_size <= budget.limits.file_bytes, "database source unavailable", 3)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(path) + suffix)
        if sidecar.exists() or sidecar.is_symlink():
            safe_path(sidecar)
            require(sidecar.stat().st_size <= budget.limits.file_bytes, "database sidecar limit", 3)
    budget.consume(path.stat().st_size)
    result: dict[str, list[dict[str, Any]]] = {}
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN")
            connection.row_factory = sqlite3.Row
            for table, (required, optional) in tables.items():
                actual = {r[1] for r in connection.execute("PRAGMA table_info(" + table + ")")}
                if not actual and table == "thread_spawn_edges":
                    result[table] = []
                    budget.note("missing_parent_table")
                    continue
                require(required <= actual, "unsupported database schema", 3)
                columns = sorted(required | (actual & optional))
                rows: list[dict[str, Any]] = []
                cursor = connection.execute(
                    "SELECT " + ",".join(columns) + " FROM " + table  # noqa: S608 - identifiers come only from fixed adapter schema tables.
                )
                for row in cursor:
                    item = dict(row)
                    budget.consume(len(canonical(item)), 1)
                    rows.append(item)
                result[table] = rows
    except sqlite3.Error as exc:
        message = "database capture unavailable"
        raise UsageError(message, 3) from exc
    return result


def capture(  # noqa: C901, PLR0912, PLR0915 - explicit native variant parsing stays in one bounded read-only capture.
    config: Config,
    secret: bytes,
    entries: list[dict[str, Any]] | None = None,
    vocabulary: Vocabulary = DEFAULT_VOCABULARY,
) -> Capture:
    """Capture native usage-accounting events, turns and optional SQLite tables.

    A token_usage_record has an explicit native response ID. Codex token_count
    events instead identify an accounting observation, not an API response.
    Their supported native event identity is the unique recorded timestamp
    within a thread, namespaced as codex-token-count/v1. Repeated timestamps
    must agree on turn and facts or capture fails; mutable tokens, settings,
    source paths and content hashes never form receipt identity. A native turn
    ID must come from the event or active task_started/turn_context record.

    Only last_token_usage is measured per event. total_token_usage is a
    cumulative snapshot used for replay suppression and monotonicity checks,
    never a substitute for last usage. Missing last usage stays unknown.

    Digests describe separately captured sources, not a cross-source transaction.
    A final partial JSONL line remains visible and is excluded from parsing.
    """
    integer(config.schema, 1, 1)
    root = safe_path(config.source_root)
    require(root.is_dir(), "history root unavailable", 3)
    entries = [] if entries is None else entries
    validate_entries(entries, vocabulary)
    budget = _Budget(config.limits)
    input_digests: dict[str, str] = {}
    metadata: dict[str, dict[str, Any]] = {}
    response_rows: list[dict[str, Any]] = []
    turn_rows: dict[tuple[str, str], dict[str, Any]] = {}
    contexts: dict[tuple[str, str], dict[str, Any]] = {}
    accounting_events: dict[tuple[str, str], dict[str, Any]] = {}

    def meta(identity: object, facts: dict[str, Any]) -> None:
        """Meta."""
        if not isinstance(identity, str) or not 0 < len(identity) <= MAX_NATIVE_ID:
            message = "native thread identity unavailable"
            raise UsageError(message, 4)
        target = metadata.setdefault(identity, {})
        for key in ("cwd", "parent_thread_id", "model", "model_provider", "effort", "service_tier"):
            if key in facts:
                require(
                    facts[key] is None or (isinstance(facts[key], str) and len(facts[key]) <= MAX_PATH),
                    "invalid native metadata",
                    3,
                )
                _same(target, key, facts[key])
                if key == "parent_thread_id":
                    target.setdefault(key, None)

    dbpath = root / "state_5.sqlite"
    if dbpath.exists() or dbpath.is_symlink():
        db = _db(
            dbpath,
            {
                "threads": (
                    {"id", "cwd"},
                    {"model", "model_provider", "reasoning_effort", "attached_thread_parent_id"},
                ),
                "thread_spawn_edges": ({"parent_thread_id", "child_thread_id"}, set()),
            },
            budget,
        )
        input_digests["sqlite-threads"] = digest(canonical(db))
        for row in db["threads"]:
            facts = {**row, "effort": row.get("reasoning_effort")}
            if "attached_thread_parent_id" in row:
                facts["parent_thread_id"] = row["attached_thread_parent_id"]
            meta(row["id"], facts)
        for row in db["thread_spawn_edges"]:
            meta(row["child_thread_id"], {"parent_thread_id": row["parent_thread_id"]})
    else:
        budget.note("missing_thread_database")

    paths: list[Path] = []
    # Walk without following directory links, rejecting links rather than silently
    # skipping a potentially relevant native source.
    for directory in (root / "sessions", root / "archived_sessions"):
        if not directory.exists() and not directory.is_symlink():
            continue
        safe_path(directory)
        for current, directories, filenames in os.walk(directory, followlinks=False):
            for name in directories + filenames:
                safe_path(Path(current) / name)
            paths.extend(Path(current) / name for name in filenames if name.endswith(".jsonl"))
            require(len(paths) <= config.limits.records, "source inventory limit", 3)
    for index, path in enumerate(sorted(paths)):
        data = read_bytes(path, config.limits.file_bytes)
        budget.consume(len(data))
        input_digests[f"jsonl-{index}"] = digest(data)
        thread: str | None = None
        active_turn: str | None = None
        cumulative: dict[str, dict[str, int | None]] = {}
        previous_usage: dict[str, dict[str, int | None]] = {}
        for line in data.splitlines(keepends=True):
            if not line.endswith(b"\n"):
                budget.note("partial_lines")
                continue
            budget.consume(0, 1)
            record = loads(line)
            require(
                isinstance(record, dict) and isinstance(record.get("payload"), dict), "unsupported history record", 3
            )
            payload = record["payload"]
            kind = record.get("type")
            if kind == "session_meta":
                thread = payload.get("id") or payload.get("session_id")
                meta(thread, payload)
                active_turn = None
            elif kind == "turn_context":
                tid, turn = payload.get("thread_id") or thread, payload.get("turn_id") or active_turn
                if not isinstance(tid, str) or not isinstance(turn, str):
                    message = "turn identity unavailable"
                    raise UsageError(message, 4)
                active_turn = turn
                target = contexts.setdefault((tid, turn), {})
                for key in ("model", "model_provider", "effort", "service_tier"):
                    _same(target, key, payload.get(key))
            elif kind == "token_usage_record":
                response_rows.append(
                    {**payload, "thread_id": payload.get("thread_id") or thread, "timestamp": record.get("timestamp")}
                )
            elif kind == "event_msg" and payload.get("type") == "token_count":
                tid, turn = payload.get("thread_id") or thread, payload.get("turn_id") or active_turn
                info = payload.get("info")
                if info is None:
                    budget.note("empty_token_count")
                    continue
                require(isinstance(info, dict), "unsupported native token record", 3)
                if not isinstance(tid, str) or not isinstance(turn, str) or not turn:
                    message = "turn identity unavailable"
                    raise UsageError(message, 4)
                event_time = _stamp(record.get("timestamp"))
                response = payload.get("response_id")
                if response is None:
                    event_time = present(event_time, "stable accounting event identity unavailable", 4)
                    response = "codex-token-count/v1:" + event_time
                usage = {}
                for key in ("last_token_usage", "total_token_usage"):
                    raw = info.get(key)
                    require(raw is None or isinstance(raw, dict), "unsupported native token record", 3)
                    usage[key] = {name: raw.get(name) if raw is not None else None for name in TOKEN_KEYS}
                    tokens(usage[key])
                last, total = usage["last_token_usage"], usage["total_token_usage"]
                if not isinstance(response, str) or not response:
                    message = "stable accounting event identity unavailable"
                    raise UsageError(message, 4)
                event_key = (tid, response)
                event_facts = {
                    "turn": turn,
                    "timestamp": event_time,
                    "usage": usage,
                    **{name: payload.get(name) for name in ("model", "model_provider", "effort", "service_tier")},
                }
                require(
                    event_key not in accounting_events or accounting_events[event_key] == event_facts,
                    "native accounting event conflict",
                    4,
                )
                accounting_events[event_key] = event_facts
                if info.get("total_token_usage") is not None:
                    prior = cumulative.get(tid)
                    if prior is not None:
                        require(
                            all(
                                prior[key] is None or total[key] is None or total[key] >= prior[key]
                                for key in TOKEN_KEYS
                            ),
                            "cumulative token regression",
                            4,
                        )
                        if prior == total:
                            require(previous_usage[tid] == last, "cumulative token replay conflict", 4)
                            budget.note("duplicate_token_count")
                            continue
                    require(
                        all(last[key] is None or total[key] is None or last[key] <= total[key] for key in TOKEN_KEYS),
                        "last token usage exceeds cumulative",
                        4,
                    )
                    cumulative[tid] = total
                    previous_usage[tid] = last
                if info.get("last_token_usage") is None:
                    budget.note("missing_last_token_usage")
                response_rows.append(
                    {
                        **payload,
                        "thread_id": tid,
                        "turn_id": turn,
                        "response_id": response,
                        "timestamp": event_time,
                        "usage": last,
                    }
                )
            elif (
                kind == "event_msg"
                and isinstance(payload.get("type"), str)
                and payload["type"] in {"task_started", "task_complete"}
            ):
                tid, turn = payload.get("thread_id") or thread, payload.get("turn_id")
                if not isinstance(tid, str) or not isinstance(turn, str):
                    message = "turn identity unavailable"
                    raise UsageError(message, 4)
                target = turn_rows.setdefault((tid, turn), {})
                key = "start" if payload["type"] == "task_started" else "end"
                _same(
                    target,
                    key,
                    _stamp(
                        payload.get("started_at")
                        if key == "start" and payload.get("started_at") is not None
                        else record.get("timestamp")
                    ),
                )
                if key == "start":
                    require(active_turn is None or active_turn == turn, "overlapping native turns", 4)
                    active_turn = turn
                elif active_turn == turn:
                    active_turn = None

    dbpath = root / "thread_history_1.sqlite"
    if dbpath.exists() or dbpath.is_symlink():
        db = _db(
            dbpath, {"thread_turns": ({"thread_id", "turn_id"}, {"started_at", "completed_at", "duration_ms"})}, budget
        )
        input_digests["sqlite-turns"] = digest(canonical(db))
        for row in db["thread_turns"]:
            target = turn_rows.setdefault((row["thread_id"], row["turn_id"]), {})
            for key, source in (("start", "started_at"), ("end", "completed_at")):
                _same(target, key, _stamp(row.get(source)))
            if row.get("duration_ms") is not None:
                milliseconds = row["duration_ms"]
                require(
                    type(milliseconds) in (int, float) and math.isfinite(milliseconds) and 0 <= milliseconds <= 10**15,
                    "invalid recorded duration",
                    4,
                )
                _same(target, "duration_seconds", milliseconds / 1000)
    else:
        budget.note("missing_turn_database")

    require(input_digests, "history unavailable", 3)
    project = os.path.normpath(config.project_selector)
    eligible = {
        tid
        for tid, item in metadata.items()
        if item.get("cwd") is not None and os.path.normpath(item["cwd"]) == project
    }
    other = {
        tid
        for tid, item in metadata.items()
        if item.get("cwd") is not None and os.path.normpath(item["cwd"]) != project
    }
    while True:
        additions = {
            tid for tid, item in metadata.items() if item.get("parent_thread_id") in eligible and tid not in other
        } - eligible
        if not additions:
            break
        eligible |= additions
    require(eligible, "selected history unavailable", 3)
    observations: dict[str, Observation] = {}
    associations: dict[str, NativeAssociation] = {}

    def relationships(tid: str) -> dict[str, Any]:
        """Relationships."""
        item = metadata[tid]
        parent = item.get("parent_thread_id")
        seen: set[str] = set()
        current = tid
        known = "parent_thread_id" in item
        while current in metadata and metadata[current].get("parent_thread_id"):
            require(current not in seen, "parent identity cycle", 4)
            seen.add(current)
            current = metadata[current]["parent_thread_id"]
        root_id = current if current in metadata and "parent_thread_id" in metadata[current] else None
        return {
            "thread": receipt(secret, "thread", tid),
            "parent": receipt(secret, "parent", parent) if parent is not None else None,
            "parent_known": known,
            "root": receipt(secret, "root", root_id) if root_id else None,
        }

    def add(kind: str, tid: str, native: str | None, **facts: object) -> None:
        """Add."""
        identity = receipt(secret, kind, tid, native)
        record = Observation(kind=kind, receipt=identity, **relationships(tid), **facts)
        record.validate(vocabulary)
        require(
            identity not in observations or observations[identity] == record, "duplicate native observation conflict", 4
        )
        observations[identity] = record
        associations[identity] = NativeAssociation(kind, tid, native, identity)

    for tid in sorted(eligible):
        add("thread", tid, None, attribution=resolve({"thread": tid}, entries, vocabulary))
    for row in response_rows:
        tid = row["thread_id"]
        require(isinstance(tid, str), "stable thread identity unavailable", 4)
        if tid not in eligible:
            continue
        turn, response = row.get("turn_id"), row.get("response_id")
        if not isinstance(turn, str) or not isinstance(response, str):
            message = "stable response identity unavailable"
            raise UsageError(message, 4)
        turn_rows.setdefault((tid, turn), {})
        raw = row.get("usage")
        if not isinstance(raw, dict):
            message = "unsupported native token record"
            raise UsageError(message, 3)
        usage = {key: raw.get(key) for key in TOKEN_KEYS}
        tokens(usage)
        settings: dict[str, str | None] = {}
        for output, source, inventory in (
            ("model", "model", vocabulary.models),
            ("provider", "model_provider", vocabulary.providers),
            ("effort", "effort", vocabulary.efforts),
            ("tier", "service_tier", vocabulary.tiers),
        ):
            value = row.get(source)
            if value is None:
                value = contexts.get((tid, turn), {}).get(source)
            if value is None:
                value = metadata[tid].get(source)
            settings[output] = value if isinstance(value, str) and value in inventory else None
        add(
            "response",
            tid,
            response,
            turn=receipt(secret, "turn", tid, turn),
            timestamp=_stamp(row.get("timestamp")),
            usage=usage,
            attribution=resolve({"response": response, "turn": turn, "thread": tid}, entries, vocabulary),
            **settings,
        )
    for (tid, turn), item in sorted(turn_rows.items()):
        if tid not in eligible:
            continue
        require(isinstance(turn, str) and bool(turn), "stable turn identity unavailable", 4)
        start, end = item.get("start"), item.get("end")
        duration = item.get("duration_seconds")
        basis = "recorded" if duration is not None else "missing"
        if duration is None and start is not None and end is not None:
            duration = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
            basis = "derived_interval"
        attrs = resolve({"turn": turn, "thread": tid}, entries, vocabulary)
        responses = [
            r for r in observations.values() if r.kind == "response" and r.turn == receipt(secret, "turn", tid, turn)
        ]
        for dimension in attrs:
            values = [r.attribution[dimension] for r in responses]
            if values and any(value != values[0] for value in values):
                attrs[dimension] = (
                    "mixed"
                    if dimension == "phase"
                    else "unallocated"
                    if dimension == "primary"
                    else []
                    if dimension == "associated"
                    else None
                )
            elif values:
                attrs[dimension] = values[0]
        add(
            "turn",
            tid,
            turn,
            turn=receipt(secret, "turn", tid, turn),
            start=start,
            end=end,
            duration_seconds=duration,
            timing_basis=basis,
            attribution=attrs,
        )
    return Capture(
        domain(secret),
        datetime.now(UTC).isoformat(),
        tuple(observations[k] for k in sorted(observations)),
        tuple(associations[k] for k in sorted(associations)),
        input_digests,
        budget.diagnostics,
        {
            "historical_completeness": "unknown",
            "active_tail": "unknown",
            "unavailable_sources": sum(
                value for key, value in budget.diagnostics.items() if key.startswith("missing_")
            ),
            "partial_lines": budget.diagnostics.get("partial_lines", 0),
        },
    )
