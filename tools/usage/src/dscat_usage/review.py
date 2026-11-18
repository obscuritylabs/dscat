"""Validate supplied fresh execution provenance; never manufacture a PASS.

The coordinator supplies dispatch/return records derived from real orchestration.
This procedural boundary cannot authenticate honesty against a process able to
forge private state. Different reviewer strings alone never establish review.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from .candidate import instant, target, validate
from .private import StateStore, locked, read_bytes
from .schema import (
    BINDINGS,
    Attestation,
    Candidate,
    ReviewEvidence,
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
)


def bindings(candidate: Candidate) -> dict[str, Any]:
    """Return every exact candidate binding required by review evidence."""
    return {
        "candidate_digest": digest(canonical(candidate.to_dict())),
        **{name: getattr(candidate, name) for name in BINDINGS - {"candidate_digest"}},
    }


def _execution(value: dict[str, Any], candidate: Candidate) -> ReviewEvidence:
    keys(value, {"schema", "review", "dispatch", "return", "synthetic"})
    integer(value["schema"], 1, 1)
    require(
        type(value["synthetic"]) is bool and value["synthetic"] == candidate.synthetic,
        "review execution mode mismatch",
        5,
    )
    evidence = ReviewEvidence.from_dict(value["review"])
    expected = bindings(candidate)
    require(all(getattr(evidence, key) == val for key, val in expected.items()), "review binding mismatch", 5)
    require(
        evidence.generator_invocation == candidate.generator_invocation and evidence.synthetic == candidate.synthetic,
        "review invocation mismatch",
        5,
    )
    require(evidence.disposition == "PASS", "review did not pass", 5)
    dispatch, returned = value["dispatch"], value["return"]
    keys(
        dispatch,
        {
            "event",
            "tool",
            "coordinator_invocation",
            "task",
            "generator_invocation",
            "reviewer_invocation",
            "fork_turns",
            "candidate_digest",
            "timestamp",
            "record_digest",
        },
    )
    keys(
        returned,
        {
            "event",
            "tool",
            "task",
            "reviewer_invocation",
            "candidate_digest",
            "disposition",
            "scope",
            "timestamp",
            "record_digest",
        },
    )
    require(
        dispatch["event"] == "fresh-dispatch"
        and dispatch["tool"] == "collaboration.spawn_agent"
        and dispatch["fork_turns"] == "none",
        "fresh dispatch evidence required",
        5,
    )
    require(
        returned["event"] == "fresh-return"
        and returned["tool"] == "collaboration.final_answer"
        and returned["scope"] == "complete-candidate"
        and returned["disposition"] == "PASS",
        "fresh return evidence required",
        5,
    )
    text(dispatch["coordinator_invocation"])
    require(
        dispatch["coordinator_invocation"] not in {evidence.generator_invocation, evidence.reviewer_invocation},
        "coordinator provenance required",
        5,
    )
    require(dispatch["generator_invocation"] == evidence.generator_invocation, "dispatch generator mismatch", 5)
    for record in (dispatch, returned):
        require(
            record["task"] == evidence.task
            and record["reviewer_invocation"] == evidence.reviewer_invocation
            and record["candidate_digest"] == expected["candidate_digest"],
            "execution provenance mismatch",
            5,
        )
        sha(record["record_digest"])
        timestamp(record["timestamp"])
    require(dispatch["record_digest"] != returned["record_digest"], "distinct dispatch and return records required", 5)
    require(
        instant(candidate.created_at)
        <= instant(dispatch["timestamp"])
        <= instant(evidence.timestamp)
        <= instant(returned["timestamp"]),
        "stale execution evidence",
        5,
    )
    return evidence


def _validate(candidate: Candidate, attestation_data: bytes, execution_data: bytes) -> None:
    target(candidate.remote, candidate.branch, candidate.synthetic)
    evidence = _execution(loads(execution_data), candidate)
    attestation = Attestation.from_dict(loads(attestation_data))
    require(attestation.execution_evidence_digest == digest(execution_data), "execution evidence changed", 5)
    require(
        {key: value for key, value in attestation.to_dict().items() if key != "execution_evidence_digest"}
        == evidence.to_dict(),
        "attestation binding mismatch",
        5,
    )


def checked_review(store: StateStore, candidate: Candidate) -> None:
    """Require unchanged frozen review evidence for the exact candidate."""
    value = present(store.get("review"), "independent review required", 5)
    require("pending" not in value, "independent review required", 5)
    keys(value, {"schema", "candidate_digest", "attestation", "execution", "attestation_digest", "execution_digest"})
    integer(value["schema"], 1, 1)
    require(value["candidate_digest"] == bindings(candidate)["candidate_digest"], "review is stale", 5)
    attestation, execution = canonical(value["attestation"]), canonical(value["execution"])
    require(
        digest(attestation) == value["attestation_digest"] and digest(execution) == value["execution_digest"],
        "review changed",
        5,
    )
    _validate(candidate, attestation, execution)


def validate_review(store: StateStore, *, attestation: Path, execution_evidence: Path) -> Candidate:
    """Consume canonical external evidence; save its digest after full validation.

    Synthetic execution documents are accepted only with explicitly marked disposable
    local bare remotes. Real dispatch records use the same executable schema, with
    synthetic false; there is no placeholder production adapter.
    """
    with locked(store.root):
        candidate = validate(store)
        attestation_data, execution_data = (
            read_bytes(attestation, private=True),
            read_bytes(execution_evidence, private=True),
        )
        # Canonical bytes give the frozen evidence a single stable identity.
        require(
            canonical(loads(attestation_data)) == attestation_data
            and canonical(loads(execution_data)) == execution_data,
            "canonical review evidence required",
            5,
        )
        _validate(candidate, attestation_data, execution_data)
        store.put_locked(
            "review",
            {
                "schema": 1,
                "candidate_digest": bindings(candidate)["candidate_digest"],
                "attestation": loads(attestation_data),
                "execution": loads(execution_data),
                "attestation_digest": digest(attestation_data),
                "execution_digest": digest(execution_data),
            },
        )
        return candidate
