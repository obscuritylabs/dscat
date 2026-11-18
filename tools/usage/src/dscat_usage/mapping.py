"""Reviewed private mappings with per-dimension precedence."""

from __future__ import annotations

from typing import Any

from .private import StateStore, locked
from .schema import (
    DEFAULT_VOCABULARY,
    DIMENSIONS,
    MAX_PATH,
    PHASES,
    SPECIAL_PRIMARY,
    Vocabulary,
    empty_attribution,
    integer,
    keys,
    require,
    text,
)


def validate_entry(entry: dict[str, Any], vocabulary: Vocabulary) -> None:
    """Validate one reviewed private mapping entry."""
    keys(entry, {"level", "id", "reviewed", "evidence"}, set(DIMENSIONS) | {"schema"})
    if "schema" in entry:
        integer(entry["schema"], 1, 1)
    require(isinstance(entry["level"], str) and entry["level"] in {"thread", "turn", "response"})
    text(entry["id"], r"[^\x00-\x1f]{1,512}")
    require(entry["reviewed"] is True, "reviewed mapping required")
    require(isinstance(entry["evidence"], str) and 0 < len(entry["evidence"]) <= MAX_PATH)
    require(bool(set(DIMENSIONS) & entry.keys()), "empty mapping")
    if "primary" in entry:
        require(
            isinstance(entry["primary"], str) and entry["primary"] in vocabulary.rtm | SPECIAL_PRIMARY,
            "unknown primary",
        )
    if "phase" in entry:
        require(isinstance(entry["phase"], str) and entry["phase"] in PHASES, "unknown phase")
    for dim, inventory in (("task", vocabulary.tasks), ("feature", vocabulary.features)):
        if dim in entry:
            require(isinstance(entry[dim], str) and entry[dim] in inventory, "unknown registered label")
    if "associated" in entry:
        require(isinstance(entry["associated"], list) and all(isinstance(x, str) for x in entry["associated"]))
        require(
            len(set(entry["associated"])) == len(entry["associated"]) and set(entry["associated"]) <= vocabulary.rtm
        )


def validate_entries(entries: list[dict[str, Any]], vocabulary: Vocabulary) -> None:
    """Validate mapping entries and reject dimension conflicts."""
    require(isinstance(entries, list))
    seen: dict[tuple[str, str, str], Any] = {}
    for entry in entries:
        validate_entry(entry, vocabulary)
        for dim in DIMENSIONS:
            if dim in entry:
                key = (entry["level"], entry["id"], dim)
                require(key not in seen or seen[key] == entry[dim], "mapping dimension conflict", 4)
                seen[key] = entry[dim]


def resolve(
    identities: dict[str, str | None], entries: list[dict[str, Any]], vocabulary: Vocabulary = DEFAULT_VOCABULARY
) -> dict[str, Any]:
    """Resolve mapping dimensions independently by native-identity precedence."""
    validate_entries(entries, vocabulary)
    result = empty_attribution()
    for dimension in DIMENSIONS:
        for level in ("response", "turn", "thread"):
            values = [
                e[dimension]
                for e in entries
                if e["level"] == level and e["id"] == identities.get(level) and dimension in e
            ]
            if values:
                result[dimension] = values[0]
                break
    return result


def upsert(store: StateStore, entry: dict[str, Any], vocabulary: Vocabulary) -> str:
    """Atomically add a nonconflicting reviewed mapping entry."""
    validate_entry(entry, vocabulary)
    with locked(store.root):
        value = store.get("map") or {"schema": 1, "entries": []}
        value = keys(value, {"schema", "entries"})
        integer(value["schema"], 1, 1)
        entries = value["entries"]
        validate_entries([*entries, entry], vocabulary)
        if entry not in entries:
            entries.append(entry)
        return store.put_locked("map", {"schema": 1, "entries": entries})
