"""Deterministic contributor replacement and receipt-level conflict detection."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from .schema import (
    DEFAULT_VOCABULARY,
    MAX_RECORDS,
    Contribution,
    Ledger,
    Observation,
    UsageError,
    Vocabulary,
    canonical,
    digest,
    require,
)

CONFLICT_EXIT = 4


class MergeConflictError(UsageError):
    """A bounded public diagnostic with receipts available only to private callers."""

    def __init__(self, receipts: tuple[str, ...]) -> None:
        """Retain private receipt details and a bounded public count."""
        super().__init__("conflicting receipt observations", 4)
        self.receipts = receipts
        self.count = len(receipts)


# Preserve existing exception imports while following conventional class names.
MergeConflict = MergeConflictError


def contribution_digest(contribution: Contribution, vocabulary: Vocabulary = DEFAULT_VOCABULARY) -> str:
    """Digest the exact validated contribution used for the next predecessor."""
    contribution.validate(vocabulary)
    return digest(canonical(contribution.to_dict()))


def _known[T](left: T | None, right: T | None) -> T | None:
    require(left is None or right is None or left == right, "conflicting observation facts", 4)
    return right if left is None else left


def _combine(left: Observation, right: Observation, vocabulary: Vocabulary) -> Observation:
    values: dict[str, Any] = {}
    for name in (
        "kind",
        "receipt",
        "thread",
        "turn",
        "parent",
        "root",
        "timestamp",
        "start",
        "end",
        "duration_seconds",
        "model",
        "provider",
        "effort",
        "tier",
    ):
        first, second = getattr(left, name), getattr(right, name)
        if name in {"timestamp", "start", "end"}:
            first = datetime.fromisoformat(first).astimezone(UTC).isoformat() if first else None
            second = datetime.fromisoformat(second).astimezone(UTC).isoformat() if second else None
        values[name] = _known(first, second)
    values["parent_known"] = left.parent_known or right.parent_known
    # A known root (parent_known=True, parent=None) conflicts with a known parent.
    if left.parent_known and right.parent_known:
        require(left.parent == right.parent, "conflicting parent facts", 4)
    values["timing_basis"] = (
        _known(
            None if left.timing_basis == "missing" else left.timing_basis,
            None if right.timing_basis == "missing" else right.timing_basis,
        )
        or "missing"
    )
    values["usage"] = {key: _known(left.usage[key], right.usage[key]) for key in left.usage}
    attrs: dict[str, Any] = {}
    for dimension, unknown in (("primary", "unallocated"), ("phase", "unknown"), ("task", None), ("feature", None)):
        first, second = left.attribution[dimension], right.attribution[dimension]
        attrs[dimension] = _known(None if first == unknown else first, None if second == unknown else second)
        if attrs[dimension] is None:
            attrs[dimension] = unknown
    attrs["associated"] = sorted(set(left.attribution["associated"]) | set(right.attribution["associated"]))
    values["attribution"] = attrs
    result = Observation(**values)
    result.validate(vocabulary)
    return result


def canonical_records(ledger: Ledger, vocabulary: Vocabulary = DEFAULT_VOCABULARY) -> tuple[Observation, ...]:
    """Collapse compatible overlaps; quarantine every conflicting receipt privately.

    No partial corpus is returned after a conflict. Callers may save the exception's
    receipts in private state, but must expose only its generic reason and count.
    """
    ledger.validate(vocabulary)
    records: dict[str, Observation] = {}
    conflicts: set[str] = set()
    for contribution in sorted(ledger.contributions, key=lambda item: item.contributor):
        for record in contribution.observations:
            if record.receipt in conflicts:
                continue
            try:
                previous = records.get(record.receipt)
                records[record.receipt] = record if previous is None else _combine(previous, record, vocabulary)
            except UsageError as exc:
                if exc.code != CONFLICT_EXIT:
                    raise
                conflicts.add(record.receipt)
    if conflicts:
        raise MergeConflict(tuple(sorted(conflicts)))
    require(len(records) <= MAX_RECORDS, "combined record limit", 3)
    return tuple(records[key] for key in sorted(records))


def merge(ledger: Ledger | None, contribution: Contribution, vocabulary: Vocabulary = DEFAULT_VOCABULARY) -> Ledger:
    """Apply one full observation generation without mutating accepted inputs.

    Missing captures cannot become replacements. Recovery from a lost predecessor
    requires restoring private contributor state; inventing a new generation fails.
    """
    contribution.validate(vocabulary)
    if ledger is None:
        ledger = Ledger(contribution.domain, ())
    ledger.validate(vocabulary)
    require(ledger.domain == contribution.domain, "receipt domain mismatch; explicit migration required", 4)
    previous = next((item for item in ledger.contributions if item.contributor == contribution.contributor), None)
    if previous is not None and previous.generation == contribution.generation:
        require(
            contribution_digest(previous, vocabulary) == contribution_digest(contribution, vocabulary),
            "generation fork; restore contributor state",
            4,
        )
        canonical_records(ledger, vocabulary)
        return ledger
    if contribution.coverage["unavailable_sources"]:
        current = {record.receipt: record for record in contribution.observations}
        require(
            previous is not None and all(current.get(record.receipt) == record for record in previous.observations),
            "incomplete contribution; preserve previous observations",
            3,
        )
    if contribution.coverage["partial_lines"]:
        require(not contribution.removals, "partial capture cannot remove accepted observations", 3)
    if previous is None:
        require(
            contribution.generation == 1 and not contribution.removals, "lost contributor state; restore predecessor", 4
        )
    else:
        require(
            contribution.generation == previous.generation + 1, "generation rollback or gap; restore predecessor", 4
        )
        require(
            contribution.predecessor == contribution_digest(previous, vocabulary),
            "lost predecessor; restore contributor state",
            4,
        )
        require(
            datetime.fromisoformat(contribution.observed_at) >= datetime.fromisoformat(previous.observed_at),
            "observation clock regression",
            4,
        )
        removed = {r.receipt for r in previous.observations} - {r.receipt for r in contribution.observations}
        require(removed == set(contribution.removals), "explicit removals required for correction", 4)
    contributions = [item for item in ledger.contributions if item.contributor != contribution.contributor]
    contributions.append(contribution)
    result = replace(ledger, contributions=tuple(sorted(contributions, key=lambda item: item.contributor)))
    canonical_records(result, vocabulary)
    return result
