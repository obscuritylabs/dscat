# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Keep scanner completeness, alias identity and exploitation explicit."""

import json

import pytest
from pydantic import ValidationError
from scripts.advisories import (
    ObservedAdvisory,
    apply_dispositions,
    merge_advisories,
    parse_audit,
    parse_kev,
)

from tests.test_release_evidence import candidate, finding


def audit_document() -> dict[str, object]:
    """Use the pinned scanner's real public JSON shape with one synthetic package."""
    return {
        "dependencies": [{"name": "synthetic-package", "version": "1.0", "vulns": []}],
        "fixes": [],
    }


def test_complete_zero_finding_scan_and_actual_advisory_shape() -> None:
    """Require complete coverage and keep new findings unassessed."""
    evidence, _ = candidate()
    document = audit_document()
    assert parse_audit(json.dumps(document).encode(), evidence.runtime, "runtime") == []
    document["dependencies"] = [
        {
            "name": "synthetic-package",
            "version": "1.0",
            "vulns": [
                {
                    "id": "SYNTHETIC-1",
                    "aliases": ["CVE-2099-0001"],
                    "fix_versions": ["2.0"],
                    "description": "Synthetic public advisory.",
                }
            ],
        }
    ]
    observed = parse_audit(json.dumps(document).encode(), evidence.runtime, "runtime")
    results = apply_dispositions(observed, [], {"CVE-2099-0001"})
    assert len(results) == 1
    assert results[0].severity == "unknown"
    assert results[0].applicability == "under_investigation"
    assert results[0].known_exploited is True


@pytest.mark.parametrize(
    "mutation",
    ["empty", "missing", "extra", "version", "duplicate", "skipped", "fix", "unknown"],
)
def test_partial_or_unknown_audit_is_never_clean(mutation: str) -> None:
    """Refuse missing packages, skipped checks and unexpected formats."""
    evidence, _ = candidate()
    document = audit_document()
    dependency = {"name": "synthetic-package", "version": "1.0", "vulns": []}
    if mutation == "empty":
        document["dependencies"] = []
    elif mutation == "missing":
        document["dependencies"] = [dependency | {"name": "another-package"}]
    elif mutation == "extra":
        document["dependencies"] = [
            dependency,
            dependency | {"name": "another-package"},
        ]
    elif mutation == "version":
        document["dependencies"] = [dependency | {"version": "2.0"}]
    elif mutation == "duplicate":
        document["dependencies"] = [dependency, dependency]
    elif mutation == "skipped":
        document["dependencies"] = [
            {"name": "synthetic-package", "skip_reason": "Synthetic service failure."}
        ]
    elif mutation == "fix":
        document["fixes"] = [{"name": "synthetic-package", "new_version": "2.0"}]
    else:
        document["unexpected"] = True
    with pytest.raises((ValueError, TypeError), match=r"collection|validation"):
        parse_audit(json.dumps(document).encode(), evidence.runtime, "runtime")


@pytest.mark.parametrize("mutation", ["count", "duplicate", "malformed", "empty"])
def test_kev_count_identities_and_bounds(mutation: str) -> None:
    """Refuse truncated catalogs and malformed exploitation identities."""
    document = {
        "count": 1,
        "vulnerabilities": [
            {"cveID": "CVE-2099-0001", "product": "Synthetic public product"}
        ],
    }
    assert parse_kev(json.dumps(document).encode()) == {"CVE-2099-0001"}
    if mutation == "count":
        document["count"] = 2
    elif mutation == "duplicate":
        document["count"] = 2
        document["vulnerabilities"] *= 2
    elif mutation == "malformed":
        document["vulnerabilities"] = [{"cveID": "unknown"}]
    else:
        document["count"] = 0
        document["vulnerabilities"] = []
    with pytest.raises(ValueError, match=r"inconsistent|validation"):
        parse_kev(json.dumps(document).encode())


def test_alias_connected_components_preserve_scope_and_version() -> None:
    """Join bridging aliases while keeping scopes and versions distinct."""
    first = ObservedAdvisory(
        package="synthetic-package",
        version="1.0",
        scope="runtime",
        identifiers=["A", "B"],
    )
    second = first.model_copy(update={"identifiers": ["C", "D"]})
    bridge = first.model_copy(update={"identifiers": ["B", "C"]})
    development = first.model_copy(update={"scope": "development"})
    version = first.model_copy(update={"version": "2.0"})
    merged = merge_advisories([first, second, development, version, bridge])
    expected_groups = 3
    assert len(merged) == expected_groups
    runtime = next(
        item for item in merged if item.scope == "runtime" and item.version == "1.0"
    )
    assert runtime.identifiers == ["A", "B", "C", "D"]


def test_dispositions_cannot_override_unobserved_or_conflicting_facts() -> None:
    """Apply manual assessments only to current observed advisories."""
    observed = [
        ObservedAdvisory(
            package="synthetic-package",
            version="1.0",
            scope="runtime",
            identifiers=["SYNTHETIC-1", "CVE-2099-0001"],
        )
    ]
    effective = apply_dispositions(observed, [finding()], set())
    assert effective[0].severity == "low"
    assert effective[0].id == "CVE-2099-0001"
    with pytest.raises(ValueError, match="Conflicting"):
        apply_dispositions(
            observed,
            [finding(), finding(id="CVE-2099-0001", aliases=["SYNTHETIC-1"])],
            set(),
        )
    with pytest.raises(ValueError, match="unobserved identity"):
        apply_dispositions(observed, [finding(aliases=["UNOBSERVED"])], set())
    with pytest.raises(ValueError, match="current observed"):
        apply_dispositions([], [finding()], set())
    with pytest.raises(ValueError, match="current observed"):
        apply_dispositions(observed, [finding(version="2.0")], set())


def test_missing_severity_proof_and_unassigned_pass_are_refused() -> None:
    """Require assessment evidence and a real executor role for passing gates."""
    values = finding().model_dump(exclude_none=True)
    values.pop("severity_evidence_sha256")
    with pytest.raises(ValidationError, match="supporting evidence"):
        type(finding()).model_validate(values)
    evidence, _ = candidate()
    with pytest.raises(ValidationError, match="Passing gates"):
        type(evidence.gates[0]).model_validate(
            evidence.gates[0].model_dump(exclude_none=True)
            | {"executor_role": "unassigned"}
        )
