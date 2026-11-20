# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Artifact-bound release readiness; this tool never publishes a release."""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, get_args

from scripts.evidence_models import (
    ActualBindings,
    GateName,
    IssueCode,
    ReleaseEvidence,
    ReleaseReadiness,
)

if TYPE_CHECKING:
    from scripts.evidence_models import Feed, Finding, Gate

FEED_KEYS = frozenset(
    {
        ("pypi", "runtime"),
        ("pypi", "development"),
        ("osv", "runtime"),
        ("osv", "development"),
        ("cisa-kev", "catalog"),
    }
)
FEED_MAX_AGE = timedelta(hours=24)


def finding_issues(
    finding: Finding, artifacts: set[str], kev_cves: set[str]
) -> list[IssueCode]:
    """Keep exploitation, severity and reviewed non-applicability independent."""
    issues: list[IssueCode] = []
    matched = bool({finding.id, *finding.aliases} & kev_cves)
    if matched and not finding.known_exploited:
        issues.append("exploitation_conflict")
    if finding.severity == "unknown":
        issues.append("severity_unassessed")
    if finding.applicability == "under_investigation":
        issues.append("applicability_unresolved")
    elif finding.applicability == "not_affected":
        disposition = finding.non_applicability
        if (
            disposition is None
            or disposition.review != "approved"
            or set(disposition.artifact_sha256) != artifacts
        ):
            issues.append("invalid_non_applicability")
    else:
        if finding.known_exploited or matched:
            issues.append("known_exploited")
        if finding.severity in {"high", "critical"}:
            issues.append("high_severity")
        if finding.severity in {"medium", "low"} and finding.remediation is None:
            issues.append("remediation_missing")
    return issues


def identity_issues(
    evidence: ReleaseEvidence, actual: ActualBindings
) -> list[IssueCode]:
    """Compare claimed provenance against independently recomputed input identities."""
    issues: list[IssueCode] = []
    if evidence.source_dirty or actual.source_dirty:
        issues.append("dirty_source")
    if not actual.verified_main:
        issues.append("unverified_main")
    if any(
        (
            evidence.source_sha != actual.source_sha,
            evidence.source_tree != actual.source_tree,
            evidence.version != actual.version,
            evidence.lock_sha256 != actual.lock_sha256,
            evidence.wheel.sha256 != actual.wheel_sha256,
            evidence.sdist.sha256 != actual.sdist_sha256,
            evidence.sbom_sha256 != actual.sbom_sha256,
            evidence.tool_evidence_sha256 != actual.tool_evidence_sha256,
        )
    ):
        issues.append("identity_mismatch")
    return issues


def feed_issues(feeds: list[Feed], now: datetime) -> list[IssueCode]:
    """Require each selected source/scope and a completed, current retrieval."""
    issues: list[IssueCode] = []
    if {(feed.source, feed.scope) for feed in feeds} != FEED_KEYS:
        issues.append("feed_missing")
    for feed in feeds:
        if feed.state != "complete":
            issues.append("feed_unavailable")
        age = now - datetime.fromisoformat(feed.retrieved_at)
        if not timedelta(0) <= age <= FEED_MAX_AGE:
            issues.append("feed_stale")
    return issues


def gate_issues(gates: list[Gate], actual: ActualBindings) -> list[IssueCode]:
    """Keep every applicable acceptance observation bound to the release candidate."""
    issues: list[IssueCode] = []
    if {gate.name for gate in gates} != set(get_args(GateName)):
        issues.append("gate_missing")
    for gate in gates:
        if gate.state != "pass":
            issues.append("gate_incomplete")
        if (
            gate.source_sha != actual.source_sha
            or gate.wheel_sha256 != actual.wheel_sha256
        ):
            issues.append("gate_identity_mismatch")
    return issues


def assess_release(
    evidence: ReleaseEvidence,
    actual: ActualBindings,
    *,
    now: datetime,
    kev_cves: set[str],
) -> ReleaseReadiness:
    """Refuse stale, incomplete, inconsistent or blocking security/acceptance claims."""
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        msg = "Release assessment requires an explicit UTC clock."
        raise ValueError(msg)
    issues = [
        *identity_issues(evidence, actual),
        *feed_issues(evidence.feeds, now),
        *gate_issues(evidence.gates, actual),
    ]
    warnings: list[str] = []
    inventories = {"runtime": evidence.runtime, "development": evidence.development}
    for finding in evidence.findings:
        installed = inventories[finding.scope].distributions
        if not any(
            package.name == finding.package and package.version == finding.version
            for package in installed
        ):
            issues.append("finding_identity_mismatch")
        issues.extend(
            finding_issues(
                finding, {actual.wheel_sha256, actual.sdist_sha256}, kev_cves
            )
        )
        if (
            finding.remediation is not None
            and finding.remediation.revisit_on < now.astimezone(UTC).date()
        ):
            warnings.append("remediation_revisit_due")
    return ReleaseReadiness.model_validate(
        {
            "state": "blocked" if issues else "ready",
            "issues": sorted(set(issues)),
            "warnings": sorted(set(warnings)),
        }
    )
