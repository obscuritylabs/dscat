"""Explicit legacy validation and nonadditive private archival migration."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from .importer import Capture, Config, capture
from .mapping import resolve, validate_entries
from .private import StateStore, locked, read_bytes, safe_path
from .schema import (
    DEFAULT_VOCABULARY,
    MAX_PATH,
    MAX_TOTAL,
    PHASES,
    TOKEN_KEYS,
    Observation,
    Vocabulary,
    canonical,
    digest,
    integer,
    keys,
    loads,
    present,
    require,
    sha,
    text,
    timestamp,
    tokens,
)

OUTPUTS = frozenset(
    {
        "accounting.json",
        "sessions.csv",
        "turns.csv",
        "usage.csv",
        "dimension-summary.csv",
        "phase-summary.csv",
        "report.md",
    }
)
ACCOUNT_KEYS = {
    "schema_version",
    "project",
    "sessions",
    "turns",
    "responses",
    "dimension_summaries",
    "time_groups",
    "totals",
    "time",
    "diagnostics",
    "coverage",
    "observed_at",
    "current_list_scenario",
}
RESPONSE_KEYS = {
    "thread_id",
    "turn_id",
    "response_id",
    "root_id",
    "timestamp",
    "usage",
    "inferred_phase",
    "model",
    "provider",
    "effort",
    "tier",
    "model_source",
    "provider_source",
    "effort_source",
    "tier_source",
    "phase",
    "feature",
    "task",
    "phase_basis",
    "feature_basis",
    "task_basis",
    "cost",
    "currency",
    "rate_id",
    "cost_status",
    "cost_assumption",
}
TURN_KEYS = {
    "thread_id",
    "turn_id",
    "root_id",
    "start",
    "end",
    "duration_seconds",
    "duration_ms",
    "duration_source",
    "interval_source",
    "inferred_phase",
    "phase",
    "feature",
    "task",
    "phase_basis",
    "feature_basis",
    "task_basis",
}


@dataclass(frozen=True)
class MigrationResult:
    """MigrationResult schema and validated maintenance operations."""

    digest: str
    archived: int
    promoted: tuple[Observation, ...]
    entries: tuple[dict[str, Any], ...]
    replay: bool


def _legacy_id(value: object) -> None:
    text(value, r"(?:[a-f0-9]{24}|unknown)")


def _account(value: object) -> None:
    value = keys(value, ACCOUNT_KEYS)
    integer(value["schema_version"], 1, 1)
    timestamp(value["observed_at"])
    for name in ("responses", "turns", "sessions", "dimension_summaries"):
        require(isinstance(value[name], list), "unsupported legacy layout", 3)
    seen: set[tuple[str, str, str]] = set()
    for kind, rows, required in (
        ("response", value["responses"], RESPONSE_KEYS),
        ("turn", value["turns"], TURN_KEYS),
        ("thread", value["sessions"], {"thread_id", "parent_id", "root_id", "inferred_phase"}),
    ):
        for row in rows:
            keys(row, required)
            for name in {"thread_id", "root_id", "parent_id", "turn_id", "response_id"} & row.keys():
                _legacy_id(row[name])
            key = (kind, row["thread_id"], row.get(kind + "_id", row["thread_id"]))
            require(key not in seen, "ambiguous legacy identity", 4)
            seen.add(key)
            require(row["inferred_phase"] in PHASES)
            if kind == "response":
                tokens(row["usage"])
                timestamp(row["timestamp"], nullable=True)
            if kind == "turn":
                for name in ("start", "end"):
                    timestamp(row[name], nullable=True)
                for name in ("duration_ms", "duration_seconds"):
                    number = row[name]
                    require(
                        number is None or (type(number) in (int, float) and 0 <= number <= 10**15),
                        "invalid legacy timing",
                        3,
                    )


def _phase_entries(value: object, vocabulary: Vocabulary) -> list[dict[str, Any]]:
    # Both the original bare entries envelope and explicit version-one envelope
    # are supported. Legacy phase mappings are explicit manual assignments;
    # inferred fields in accounting rows are never imported as mappings.
    value = keys(value, {"entries"}, {"schema_version"})
    if "schema_version" in value:
        integer(value["schema_version"], 1, 1)
    require(isinstance(value["entries"], list))
    result: list[dict[str, Any]] = []
    for entry in value["entries"]:
        keys(entry, {"level", "id"}, {"phase", "feature", "task"})
        converted = {**entry, "reviewed": True, "evidence": "legacy-explicit-phase-map"}
        validate_entries([converted], vocabulary)
        result.append(converted)
    return result


def _registry(value: object, vocabulary: Vocabulary) -> list[dict[str, Any]]:
    value = keys(value, {"schema_version", "artifacts", "labels", "entries"})
    integer(value["schema_version"], 1, 1)
    keys(value["labels"], {"task", "feature"})
    require(isinstance(value["artifacts"], dict))
    for target, label in value["artifacts"].items():
        require(isinstance(target, str) and 0 < len(target) <= MAX_PATH)
        text(label, r"ART-\d{3}")
    for dim, inventory in (("task", vocabulary.tasks), ("feature", vocabulary.features)):
        require(isinstance(value["labels"][dim], dict))
        for label, display in value["labels"][dim].items():
            require(label == display and label in inventory, "unsupported legacy registered label", 3)
    validate_entries(value["entries"], vocabulary)
    return value["entries"]


def _associations(value: object, native: Capture, account: dict[str, Any]) -> dict[tuple[str, str, str], Any]:
    value = keys(value, {"schema", "entries"})
    integer(value["schema"], 1, 1)
    require(isinstance(value["entries"], list))
    available = {(a.kind, a.thread_id, a.native_id): a for a in native.associations}
    legacy = {
        (kind, row["thread_id"], row.get(kind + "_id", row["thread_id"]))
        for kind, rows in (
            ("thread", account["sessions"]),
            ("turn", account["turns"]),
            ("response", account["responses"]),
        )
        for row in rows
    }
    result: dict[tuple[str, str, str], Any] = {}
    seen_native: set[str] = set()
    for entry in value["entries"]:
        keys(entry, {"kind", "legacy_thread", "legacy_id", "native_thread", "native_id"})
        require(entry["kind"] in {"thread", "turn", "response"})
        for key in ("legacy_thread", "legacy_id"):
            _legacy_id(entry[key])
            require(entry[key] != "unknown", "ambiguous legacy identity", 4)
        key = (entry["kind"], entry["legacy_thread"], entry["legacy_id"])
        require(key in legacy and key not in result, "ambiguous legacy association", 4)
        native_key = (entry["kind"], entry["native_thread"], entry["native_id"])
        require(native_key in available, "native association unavailable", 4)
        association = available[native_key]
        require(association.receipt not in seen_native, "ambiguous native association", 4)
        require(digest(association.thread_id.encode())[:24] == entry["legacy_thread"], "legacy association mismatch", 4)
        expected = association.thread_id if association.kind == "thread" else association.native_id
        require(
            isinstance(expected, str) and digest(expected.encode())[:24] == entry["legacy_id"],
            "derived legacy identity cannot promote",
            4,
        )
        result[key] = association
        seen_native.add(association.receipt)
    return result


def migrate(  # noqa: C901, PLR0913, PLR0912, PLR0915 - one locked validate-before-write migration preserves all inputs.
    store: StateStore,
    snapshot: Path,
    phase_map: Path,
    registry: Path,
    *,
    identity_map: Path | None = None,
    config: Config | None = None,
    secret: bytes | None = None,
    vocabulary: Vocabulary = DEFAULT_VOCABULARY,
) -> MigrationResult:
    """Validate without mutation, then atomically archive and merge explicit maps.

    No original file is written. Native capture, when explicitly requested for
    association verification, is read-only and does not advance refresh state.
    """
    with locked(store.root):
        snapshot = safe_path(snapshot)
        require(snapshot.is_dir(), "legacy snapshot unavailable", 3)
        originals = {
            "manifest": read_bytes(snapshot / "manifest.json", private=True),
            "phase_map": read_bytes(phase_map, private=True),
            "registry": read_bytes(registry, private=True),
        }
        manifest = loads(originals["manifest"])
        keys(manifest, {"schema_version", "observed_at", "inputs", "sources", "outputs"})
        integer(manifest["schema_version"], 1, 1)
        timestamp(manifest["observed_at"])
        keys(manifest["inputs"], {"script_sha256", "mapping_sha256", "prices_sha256"})
        for value in manifest["inputs"].values():
            sha(value)
        require(isinstance(manifest["sources"], list))
        for source in manifest["sources"]:
            if isinstance(source, dict) and source.get("category") in {
                "logs_2.sqlite",
                "history.jsonl",
                "session_index.jsonl",
            }:
                keys(source, {"category", "status"})
                require(source["status"] in {"inventory_only_not_used", "absent"})
                continue
            keys(source, {"category", "sha256"}, {"source_id", "bytes", "records"})
            require(
                source["category"] in {"rollout", "sqlite-threads", "sqlite-edges", "sqlite-turns", "excluded-source"}
            )
            sha(source["sha256"])
            if "source_id" in source:
                sha(source["source_id"])
            for key in ("bytes", "records"):
                if key in source:
                    integer(source[key])
        keys(manifest["outputs"], set(OUTPUTS))
        for name, expected in manifest["outputs"].items():
            sha(expected)
            data = read_bytes(snapshot / name, private=True)
            require(digest(data) == expected, "legacy output hash mismatch", 3)
            originals[name] = data
        require(sum(map(len, originals.values())) <= MAX_TOTAL, "legacy resource limit", 3)
        require(
            digest(originals["phase_map"]) == manifest["inputs"]["mapping_sha256"], "legacy phase-map hash mismatch", 3
        )
        account = loads(originals["accounting.json"])
        _account(account)
        entries = _phase_entries(loads(originals["phase_map"]), vocabulary) + _registry(
            loads(originals["registry"]), vocabulary
        )
        validate_entries(entries, vocabulary)
        associations: dict[tuple[str, str, str], Any] = {}
        native: Capture | None = None
        if identity_map is not None:
            config = present(config, "native association configuration required", 3)
            secret = present(secret, "native association configuration required", 3)
            originals["identity_map"] = read_bytes(identity_map, private=True)
            native = capture(config, secret, vocabulary=vocabulary)
            require(native.domain == store.manifest["domain"], "receipt domain mismatch", 4)
            associations = _associations(loads(originals["identity_map"]), native, account)
        promoted: list[Observation] = []
        converted_entries: list[dict[str, Any]] = []
        if native is not None:
            by_receipt = {o.receipt: o for o in native.observations}
            for kind, rows in (
                ("thread", account["sessions"]),
                ("turn", account["turns"]),
                ("response", account["responses"]),
            ):
                for row in rows:
                    association = associations.get((kind, row["thread_id"], row.get(kind + "_id", row["thread_id"])))
                    if association is None:
                        continue
                    record = by_receipt[association.receipt]
                    if kind == "response":
                        for key in TOKEN_KEYS:
                            require(
                                row["usage"][key] is None or record.usage[key] == row["usage"][key],
                                "legacy measurement conflict",
                                4,
                            )
                    elif kind == "turn":
                        for key in ("start", "end", "duration_seconds"):
                            require(row[key] is None or getattr(record, key) == row[key], "legacy timing conflict", 4)
                    promoted.append(record)
            # Map keys may be original private native IDs or legacy transformed
            # IDs. Only a unique verified association establishes conversion.
            for entry in entries:
                matches = [
                    a
                    for a in associations.values()
                    if a.kind == entry["level"]
                    and entry["id"]
                    in {
                        a.native_id if a.kind != "thread" else a.thread_id,
                        digest((a.native_id if a.kind != "thread" else a.thread_id).encode())[:24],
                    }
                ]
                require(len(matches) <= 1, "ambiguous mapping association", 4)
                if matches:
                    associated = matches[0]
                    converted_entries.append(
                        {**entry, "id": associated.thread_id if associated.kind == "thread" else associated.native_id}
                    )
        existing = store.get("map") or {"schema": 1, "entries": []}
        existing = keys(existing, {"schema", "entries"})
        integer(existing["schema"], 1, 1)
        combined = list(existing["entries"])
        for entry in converted_entries:
            if entry not in combined:
                combined.append(entry)
        validate_entries(combined, vocabulary)
        # Reapply only explicit reviewed maps; inferred legacy row labels have
        # deliberately never entered this registry.
        if promoted and native is not None:
            native_by_receipt = {a.receipt: a for a in native.associations}
            attributed: list[Observation] = []
            for record in promoted:
                association = native_by_receipt[record.receipt]
                identities: dict[str, str | None] = {"thread": association.thread_id}
                if record.turn is not None:
                    turn = native_by_receipt.get(record.turn)
                    turn = present(turn, "native turn association unavailable", 4)
                    require(turn.kind == "turn", "native turn association unavailable", 4)
                    identities["turn"] = turn.native_id
                if record.kind == "response":
                    identities["response"] = association.native_id
                attributed.append(replace(record, attribution=resolve(identities, combined, vocabulary)))
            promoted = attributed
        source_digest = digest(canonical({name: digest(data) for name, data in originals.items()}))
        previous = store.get("migration")
        replay = previous is not None and previous["source_digest"] == source_digest
        if replay and previous is not None:
            return MigrationResult(
                store.manifest["pointers"]["migration"],
                len(account["responses"]) + len(account["turns"]) + len(account["sessions"]),
                tuple(Observation.from_dict(o, vocabulary) for o in previous["promoted"]),
                tuple(previous["converted_entries"]),
                replay=True,
            )
        archive = {
            "schema": 1,
            "source_digest": source_digest,
            "original_bytes_hex": {
                name: [data[offset : offset + 4096].hex() for offset in range(0, len(data), 4096)]
                for name, data in originals.items()
            },
            "legacy_entries": entries,
            "converted_entries": converted_entries,
            "promoted": [o.to_dict() for o in promoted],
            "coverage": "unknown",
            "legacy_additivity": "historical-nonadditive",
            "native_input_digests": native.input_digests if native else {},
        }
        written_pointers = store.put_many_locked({"migration": archive, "map": {"schema": 1, "entries": combined}})
        return MigrationResult(
            written_pointers["migration"],
            len(account["responses"]) + len(account["turns"]) + len(account["sessions"]),
            tuple(promoted),
            tuple(converted_entries),
            replay=False,
        )
