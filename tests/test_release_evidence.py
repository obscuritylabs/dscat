# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Release readiness refuses incomplete, stale and artifact-unbound security claims."""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, get_args

import pytest
from packaging.markers import default_environment
from pydantic import ValidationError
from scripts.evidence_models import ActualBindings, Finding, GateName, ReleaseEvidence
from scripts.release_evidence import FEED_KEYS, assess_release

if TYPE_CHECKING:
    from scripts.evidence_models import IssueCode

NOW = datetime(2026, 1, 2, tzinfo=UTC)
WHEEL = "b" * 64
SDIST = "c" * 64


def candidate() -> tuple[ReleaseEvidence, ActualBindings]:
    """Supply explicit synthetic evidence for each independent prerequisite."""
    distribution = {
        "name": "synthetic-package",
        "version": "1.0",
        "requires": [],
        "licenses": ["MIT"],
    }
    inventory = {
        "python_version": "3.15.2",
        "marker_environment": default_environment(),
        "distributions": [distribution],
    }
    evidence = ReleaseEvidence.model_validate(
        {
            "schema_version": "1.0",
            "source_sha": "a" * 40,
            "source_tree": "f" * 40,
            "source_dirty": False,
            "version": "0.1.0",
            "lock_sha256": "d" * 64,
            "wheel": {"name": "dscat-0.1.0-py3-none-any.whl", "sha256": WHEEL},
            "sdist": {"name": "dscat-0.1.0.tar.gz", "sha256": SDIST},
            "sbom_sha256": "e" * 64,
            "generator_version": "7.6.0",
            "scanner_version": "2.10.1",
            "runtime": inventory,
            "development": inventory,
            "feeds": [
                {
                    "source": source,
                    "scope": scope,
                    "retrieved_at": "2026-01-02T00:00:00Z",
                    "sha256": "1" * 64,
                    "state": "complete",
                }
                for source, scope in sorted(FEED_KEYS)
            ],
            "findings": [],
            "gates": [
                {
                    "name": name,
                    "state": "pass",
                    "executor_role": "independent",
                    "source_sha": "a" * 40,
                    "wheel_sha256": WHEEL,
                    "evidence_sha256": "2" * 64,
                }
                for name in get_args(GateName)
            ],
        }
    )
    actual = ActualBindings(
        source_sha="a" * 40,
        source_tree="f" * 40,
        verified_main=True,
        version="0.1.0",
        lock_sha256="d" * 64,
        wheel_sha256=WHEEL,
        sdist_sha256=SDIST,
        sbom_sha256="e" * 64,
    )
    return evidence, actual


def finding(**changes: object) -> Finding:
    """Supply explicit synthetic severity, applicability and remediation facts."""
    return Finding.model_validate(
        {
            "id": "SYNTHETIC-1",
            "package": "synthetic-package",
            "version": "1.0",
            "scope": "runtime",
            "aliases": ["CVE-2099-0001"],
            "severity": "low",
            "known_exploited": False,
            "applicability": "affected",
            "remediation": {
                "owner_role": "maintainer",
                "plan": "Synthetic regression and correction.",
                "revisit_on": "2026-02-01",
            },
        }
        | changes
    )


def test_complete_synthetic_readiness_and_low_severity_tracking() -> None:
    """Readiness needs complete evidence; tracked Low findings need not block."""
    evidence, actual = candidate()
    assert assess_release(evidence, actual, now=NOW, kev_cves=set()).state == "ready"
    evidence = evidence.model_copy(update={"findings": [finding()]})
    result = assess_release(evidence, actual, now=NOW, kev_cves=set())
    assert result.state == "ready"
    assert result.issues == []


@pytest.mark.parametrize("severity", ["low", "unknown"])
def test_known_exploited_findings_block_at_any_severity(severity: str) -> None:
    """Low and unscored findings cannot evade the independent exploitation gate."""
    evidence, actual = candidate()
    evidence = evidence.model_copy(update={"findings": [finding(severity=severity)]})
    result = assess_release(evidence, actual, now=NOW, kev_cves={"CVE-2099-0001"})
    assert result.state == "blocked"
    assert "known_exploited" in result.issues
    assert "exploitation_conflict" in result.issues


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"known_exploited": True}, "known_exploited"),
        ({"severity": "high"}, "high_severity"),
        ({"severity": "critical"}, "high_severity"),
        ({"severity": "unknown"}, "severity_unassessed"),
        ({"applicability": "under_investigation"}, "applicability_unresolved"),
        ({"package": "unknown-package"}, "finding_identity_mismatch"),
        ({"version": "2.0"}, "finding_identity_mismatch"),
    ],
)
def test_finding_decisions(changes: dict[str, object], expected: IssueCode) -> None:
    """Keep blocking facts independent of a scanner process exit status."""
    evidence, actual = candidate()
    evidence = evidence.model_copy(update={"findings": [finding(**changes)]})
    assert expected in assess_release(evidence, actual, now=NOW, kev_cves=set()).issues


@pytest.mark.parametrize("severity", ["medium", "low"])
def test_nonblocking_severity_requires_remediation(severity: str) -> None:
    """A missing plan/owner/revisit cannot silently disappear from release decisions."""
    evidence, actual = candidate()
    values = finding(severity=severity).model_dump(exclude_none=True)
    values.pop("remediation")
    evidence = evidence.model_copy(
        update={"findings": [Finding.model_validate(values)]}
    )
    assert (
        "remediation_missing"
        in assess_release(evidence, actual, now=NOW, kev_cves=set()).issues
    )


@pytest.mark.parametrize(
    "age",
    [
        timedelta(0),
        timedelta(hours=24),
        timedelta(hours=24, microseconds=1),
        timedelta(microseconds=-1),
    ],
)
def test_advisory_freshness_boundaries(age: timedelta) -> None:
    """Exactly 24 hours is accepted; older or future retrieval claims are refused."""
    evidence, actual = candidate()
    stamp = (NOW - age).isoformat().replace("+00:00", "Z")
    feeds = [feed.model_copy(update={"retrieved_at": stamp}) for feed in evidence.feeds]
    result = assess_release(
        evidence.model_copy(update={"feeds": feeds}), actual, now=NOW, kev_cves=set()
    )
    assert ("feed_stale" in result.issues) == (
        age < timedelta(0) or age > timedelta(hours=24)
    )


@pytest.mark.parametrize(
    "name",
    [
        "source_sha",
        "source_tree",
        "version",
        "lock_sha256",
        "wheel_sha256",
        "sdist_sha256",
        "sbom_sha256",
    ],
)
def test_recomputed_identity_mismatch(name: str) -> None:
    """No copied manifest hash can stand for the actual source, wheel, sdist or SBOM."""
    evidence, actual = candidate()
    values = actual.model_dump()
    values[name] = "9" * len(values[name]) if name != "version" else "0.2.0"
    result = assess_release(
        evidence, ActualBindings.model_validate(values), now=NOW, kev_cves=set()
    )
    assert "identity_mismatch" in result.issues


def test_unavailable_missing_or_incomplete_evidence_blocks() -> None:
    """Missing manual/service/feed evidence and unverified main cannot imply ready."""
    evidence, actual = candidate()
    changes = {
        "source_dirty": True,
        "feeds": [evidence.feeds[0].model_copy(update={"state": "unavailable"})],
        "gates": [
            evidence.gates[0].model_copy(
                update={"state": "pending", "source_sha": "9" * 40}
            )
        ],
    }
    result = assess_release(
        evidence.model_copy(update=changes),
        actual.model_copy(update={"verified_main": False}),
        now=NOW,
        kev_cves=set(),
    )
    assert set(result.issues) == {
        "dirty_source",
        "unverified_main",
        "feed_missing",
        "feed_unavailable",
        "gate_missing",
        "gate_incomplete",
        "gate_identity_mismatch",
    }


def test_non_applicability_requires_reviewed_exact_artifacts() -> None:
    """A reviewed path argument can exempt a finding only for its exact built bytes."""
    evidence, actual = candidate()
    disposition = {
        "justification": "vulnerable_code_not_in_execute_path",
        "execution_path": "Synthetic vulnerable entry is outside the selected path.",
        "evidence_sha256": "3" * 64,
        "artifact_sha256": [WHEEL, SDIST],
        "review": "approved",
    }
    known = finding(
        severity="high", applicability="not_affected", non_applicability=disposition
    )
    evidence = evidence.model_copy(update={"findings": [known]})
    assert assess_release(evidence, actual, now=NOW, kev_cves=set()).state == "ready"
    for changes in (
        {"review": "pending"},
        {"artifact_sha256": [WHEEL, "0" * 64]},
        {"artifact_sha256": [WHEEL, WHEEL]},
    ):
        altered = finding(
            severity="high",
            applicability="not_affected",
            non_applicability=disposition | changes,
        )
        result = assess_release(
            evidence.model_copy(update={"findings": [altered]}),
            actual,
            now=NOW,
            kev_cves=set(),
        )
        assert "invalid_non_applicability" in result.issues
    for changes in ({"execution_path": ""}, {"evidence_sha256": "unknown"}):
        with pytest.raises(ValidationError):
            finding(
                applicability="not_affected", non_applicability=disposition | changes
            )
