# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Closed release decisions bind claims to actual source and artifact identities."""

from datetime import UTC, datetime
from typing import Annotated, Literal, Self

from packaging.markers import default_environment
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version
from pydantic import AfterValidator, Field, field_validator, model_validator

from dscat.models.base import CalendarDate, HttpsReference, Sha256, StrictModel, Text

GitSha = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
MARKER_FIELDS = frozenset(default_environment())


class ProjectIdentity(StrictModel):
    """Reviewed project intent is independent of what either archive declares."""

    version: Text
    requires_python: Text
    requirements: list[Text]


class InstalledAcceptance(StrictModel):
    """Observed installed CLI results include proof that network denial was active."""

    schema_version: Literal["1.0"]
    state: Literal["pass"]
    cli_cases: Literal[9]
    guard_probe_denied: Literal[True]
    workflow_network_attempts: Literal[0]
    unknown_reference_denied: Literal[True]
    template_sha256: Sha256
    canonical_generation: Sha256
    public_generation: Sha256


class RelationshipCorrection(StrictModel):
    """Disclose a generator relationship corrected using verified active metadata."""

    package: Text
    generated: list[Text]
    installed: list[Text]


class SbomReconciliation(StrictModel):
    """Retain generator identity and explain every active-relationship correction."""

    schema_version: Literal["1.0"]
    generator_sha256: Sha256
    relationship_source: Literal["installed-requires-dist-and-lock"]
    corrections: list[RelationshipCorrection]


def utc_timestamp(value: str) -> str:
    """Require an explicit UTC instant without silently assigning a timezone."""
    try:
        instant = datetime.fromisoformat(value)
    except ValueError:
        msg = "Evidence time must be a UTC instant."
        raise ValueError(msg) from None
    if not value.endswith("Z") or instant.tzinfo != UTC:
        msg = "Evidence time must explicitly use UTC."
        raise ValueError(msg)
    return value


UtcTimestamp = Annotated[str, AfterValidator(utc_timestamp)]


class Artifact(StrictModel):
    """A distribution identity contains no private file path."""

    name: Annotated[str, Field(pattern=r"^dscat-[A-Za-z0-9_.+-]+\.(whl|tar\.gz)$")]
    sha256: Sha256


class Distribution(StrictModel):
    """Observed installed metadata is independent of the expected dependency lock."""

    name: Text
    version: Text
    requires: list[Text]
    licenses: list[Text]
    artifact_sha256: Sha256 | None = None
    artifact_url: HttpsReference | None = None

    @field_validator("name")
    @classmethod
    def canonical_name(cls, value: str) -> str:
        """Make package equality explicit using the Python package-name convention."""
        if canonicalize_name(value, validate=True) != value:
            msg = "Distribution names must use their canonical package spelling."
            raise ValueError(msg)
        return value

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        """Reject arbitrary version text rather than guessing dependency ordering."""
        try:
            Version(value)
        except InvalidVersion:
            msg = "Distribution version is invalid."
            raise ValueError(msg) from None
        return value


class Inventory(StrictModel):
    """A complete installed environment and the marker context actually observed."""

    python_version: Text
    marker_environment: dict[str, str]
    distributions: Annotated[list[Distribution], Field(min_length=1, max_length=1000)]

    @model_validator(mode="after")
    def unique_distributions(self) -> Self:
        """Duplicate distribution metadata cannot establish a unique environment."""
        names = [item.name for item in self.distributions]
        if len(names) != len(set(names)):
            msg = "Installed distribution identities must be unique."
            raise ValueError(msg)
        if (
            set(self.marker_environment) != MARKER_FIELDS
            or self.marker_environment.get("python_full_version") != self.python_version
            or self.marker_environment.get("python_version")
            != ".".join(str(part) for part in Version(self.python_version).release[:2])
        ):
            msg = "Installed marker context must be complete and match the interpreter."
            raise ValueError(msg)
        return self


class LockDependency(StrictModel):
    """A selected lock edge carries explicit extras and platform markers."""

    name: Text
    marker: Text | None = None
    extra: list[Text] = Field(default_factory=list)


class LockPackage(StrictModel):
    """Project only the lock's dependency selection into a closed typed boundary."""

    name: Text
    version: Text
    source: dict[str, str]
    dependencies: list[LockDependency] = Field(default_factory=list)
    optional_dependencies: dict[str, list[LockDependency]] = Field(
        default_factory=dict, alias="optional-dependencies"
    )
    dev_dependencies: dict[str, list[LockDependency]] = Field(
        default_factory=dict, alias="dev-dependencies"
    )


class Feed(StrictModel):
    """Captured feed provenance is required even when no findings are returned."""

    source: Literal["pypi", "osv", "cisa-kev"]
    scope: Literal["runtime", "development", "catalog"]
    retrieved_at: UtcTimestamp
    sha256: Sha256
    state: Literal["complete", "unavailable"]


class NonApplicability(StrictModel):
    """A reviewed execution-path disposition applies only to named artifact bytes."""

    justification: Literal[
        "vulnerable_code_not_present",
        "vulnerable_code_not_in_execute_path",
        "vulnerable_code_cannot_be_controlled_by_adversary",
        "inline_mitigations_already_exist",
    ]
    execution_path: Text
    evidence_sha256: Sha256
    artifact_sha256: Annotated[list[Sha256], Field(min_length=2, max_length=2)]
    review: Literal["approved", "pending"]


class Remediation(StrictModel):
    """Nonblocking findings still require an assigned plan and a revisit date."""

    owner_role: Literal["maintainer", "security-reviewer", "implementation"]
    plan: Text
    revisit_on: CalendarDate


class Finding(StrictModel):
    """Known exploitation remains independent of advisory severity."""

    id: Text
    package: Text
    version: Text
    scope: Literal["runtime", "development"]
    aliases: list[Text]
    severity: Literal["critical", "high", "medium", "low", "unknown"]
    severity_evidence_sha256: Sha256 | None = None
    known_exploited: bool
    applicability: Literal["affected", "not_affected", "under_investigation"]
    non_applicability: NonApplicability | None = None
    remediation: Remediation | None = None

    @model_validator(mode="after")
    def disposition_shape(self) -> Self:
        """Reject unsupported exemptions and contradictory VEX status."""
        if (self.applicability == "not_affected") != (
            self.non_applicability is not None
        ):
            msg = "Non-applicability requires its own artifact-bound disposition."
            raise ValueError(msg)
        if len(self.aliases) != len(set(self.aliases)):
            msg = "Advisory aliases must be unique."
            raise ValueError(msg)
        if self.severity != "unknown" and self.severity_evidence_sha256 is None:
            msg = "Assessed severity requires supporting evidence."
            raise ValueError(msg)
        return self


GateName = Literal[
    "native_macos",
    "excel_voiceover",
    "terminal_voiceover",
    "safari_voiceover",
    "confidential_reporting",
    "triage_rehearsal",
    "privacy_review",
    "license_review",
    "independent_acceptance",
]


class Gate(StrictModel):
    """A gate records observed evidence; pending work never becomes an inferred pass."""

    name: GateName
    state: Literal["pass", "fail", "pending"]
    executor_role: Literal["implementer", "independent", "operator", "unassigned"]
    source_sha: GitSha
    wheel_sha256: Sha256
    evidence_sha256: Sha256 | None = None

    @model_validator(mode="after")
    def passing_evidence(self) -> Self:
        """Require observed evidence and applicable review independence."""
        if self.state == "pass" and (
            self.evidence_sha256 is None
            or self.executor_role == "unassigned"
            or (
                self.name == "independent_acceptance"
                and self.executor_role != "independent"
            )
        ):
            msg = "Passing gates require the applicable evidence and independence."
            raise ValueError(msg)
        return self


class ReleaseEvidence(StrictModel):
    """A candidate binds the exact distributions, inventories, feeds and acceptance."""

    schema_version: Literal["1.0"]
    source_sha: GitSha
    source_tree: GitSha
    source_dirty: bool
    version: Text
    lock_sha256: Sha256
    wheel: Artifact
    sdist: Artifact
    sbom_sha256: Sha256
    tool_evidence_sha256: Sha256
    generator_version: Literal["7.6.0"]
    scanner_version: Literal["2.10.1"]
    runtime: Inventory
    development: Inventory
    feeds: Annotated[list[Feed], Field(max_length=5)]
    findings: Annotated[list[Finding], Field(max_length=10000)]
    gates: Annotated[list[Gate], Field(max_length=9)]

    @model_validator(mode="after")
    def unique_claims(self) -> Self:
        """Repeated feed, advisory or gate identities cannot hide conflicting claims."""
        keys = [
            [(feed.source, feed.scope) for feed in self.feeds],
            [(finding.scope, finding.package, finding.id) for finding in self.findings],
            [gate.name for gate in self.gates],
        ]
        if any(len(items) != len(set(items)) for items in keys):
            msg = "Release evidence identities must be unique."
            raise ValueError(msg)
        if not self.wheel.name.endswith(".whl") or not self.sdist.name.endswith(
            ".tar.gz"
        ):
            msg = "Artifact roles must match their distribution formats."
            raise ValueError(msg)
        return self


class ArtifactProvenance(StrictModel):
    """Source and distribution identities known before generating the SBOM."""

    source_sha: GitSha
    source_tree: GitSha
    version: Text
    lock_sha256: Sha256
    wheel_sha256: Sha256
    sdist_sha256: Sha256


class ActualBindings(ArtifactProvenance):
    """Identities recomputed from actual inputs rather than copied from claims."""

    verified_main: bool
    source_dirty: bool
    sbom_sha256: Sha256
    tool_evidence_sha256: Sha256


IssueCode = Literal[
    "dirty_source",
    "unverified_main",
    "identity_mismatch",
    "feed_missing",
    "feed_unavailable",
    "feed_stale",
    "gate_missing",
    "gate_incomplete",
    "gate_identity_mismatch",
    "finding_identity_mismatch",
    "applicability_unresolved",
    "severity_unassessed",
    "exploitation_conflict",
    "known_exploited",
    "high_severity",
    "invalid_non_applicability",
    "remediation_missing",
]


class ReleaseReadiness(StrictModel):
    """A fixed-code decision never presents missing evidence as successful release."""

    schema_version: Literal["1.0"] = "1.0"
    state: Literal["ready", "blocked"]
    issues: list[IssueCode]
    warnings: list[Literal["remediation_revisit_due"]]

    @model_validator(mode="after")
    def truthful_readiness(self) -> Self:
        """Require a blocked result exactly when blocking issues are present."""
        if (self.state == "blocked") != bool(self.issues):
            msg = "Release readiness must agree with its blocking issues."
            raise ValueError(msg)
        return self
