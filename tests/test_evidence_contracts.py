# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Malformed identities and contradictory evidence cannot certify a release."""

import pytest
from pydantic import ValidationError
from scripts.evidence_models import (
    Distribution,
    Feed,
    Finding,
    Inventory,
    ReleaseEvidence,
    ReleaseReadiness,
)

from tests.test_release_evidence import candidate, finding


@pytest.mark.parametrize(
    "timestamp",
    ["not-a-time", "2026-01-01T00:00:00", "2026-01-01T00:00:00+01:00"],
)
def test_feed_requires_explicit_utc_instant(timestamp: str) -> None:
    """Feed freshness must never guess a timezone or accept malformed dates."""
    with pytest.raises(ValidationError, match=r"UTC instant|explicitly use UTC"):
        Feed(
            source="pypi",
            scope="runtime",
            retrieved_at=timestamp,
            sha256="a" * 64,
            state="complete",
        )


@pytest.mark.parametrize("changes", [{"name": "Synthetic_Package"}, {"version": "?"}])
def test_distribution_identity_is_unambiguous(changes: dict[str, str]) -> None:
    """Canonical names and ordered versions prevent advisory matching ambiguity."""
    with pytest.raises(ValidationError, match=r"canonical package spelling|version"):
        Distribution.model_validate(
            {
                "name": "synthetic-package",
                "version": "1.0",
                "requires": [],
                "licenses": [],
            }
            | changes
        )


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "full", "short"])
def test_inventory_cannot_borrow_missing_target_context(mutation: str) -> None:
    """Duplicates and inconsistent marker contexts cannot produce a clean inventory."""
    evidence, _ = candidate()
    values = evidence.runtime.model_dump(exclude_none=True)
    if mutation == "duplicate":
        values["distributions"] *= 2
    elif mutation == "missing":
        values["marker_environment"].pop("sys_platform")
    else:
        field = "python_full_version" if mutation == "full" else "python_version"
        values["marker_environment"][field] = "3.14.0"
    with pytest.raises(ValidationError, match=r"unique|complete and match"):
        Inventory.model_validate(values)


@pytest.mark.parametrize("mutation", ["status", "aliases", "unrelated-vex"])
def test_finding_disposition_cannot_be_contradictory(mutation: str) -> None:
    """Require an exclusive applicability status and distinct alias identities."""
    values = finding().model_dump(exclude_none=True)
    if mutation == "status":
        values["applicability"] = "not_affected"
    elif mutation == "aliases":
        values["aliases"] *= 2
    else:
        values["non_applicability"] = {
            "justification": "vulnerable_code_not_present",
            "execution_path": "Synthetic unrelated path evidence.",
            "evidence_sha256": "e" * 64,
            "artifact_sha256": ["b" * 64, "c" * 64],
            "review": "approved",
        }
    with pytest.raises(
        ValidationError, match=r"Non-applicability|aliases must be unique"
    ):
        Finding.model_validate(values)


@pytest.mark.parametrize("identity", ["feeds", "gates", "findings", "artifact-role"])
def test_duplicate_or_misassigned_release_claims_refuse(identity: str) -> None:
    """Repeated claims and wrong distribution roles cannot certify artifact identity."""
    evidence, _ = candidate()
    values = evidence.model_dump(exclude_none=True)
    if identity == "artifact-role":
        values["wheel"], values["sdist"] = values["sdist"], values["wheel"]
    else:
        first = (
            finding().model_dump(exclude_none=True)
            if identity == "findings"
            else values[identity][0]
        )
        values[identity] = [first, first]
    with pytest.raises(ValidationError, match=r"unique|roles must match"):
        ReleaseEvidence.model_validate(values)


@pytest.mark.parametrize(
    ("state", "issues"), [("ready", ["gate_missing"]), ("blocked", [])]
)
def test_readiness_cannot_contradict_blockers(state: str, issues: list[str]) -> None:
    """The state field cannot override missing acceptance evidence."""
    with pytest.raises(ValidationError, match=r"agree with its blocking issues"):
        ReleaseReadiness.model_validate(
            {"state": state, "issues": issues, "warnings": []}
        )
