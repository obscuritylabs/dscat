# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Canonical metadata, preserving independent facts and explicit unknown states."""

from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BeforeValidator,
    EmailStr,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from dscat.models.base import (
    CalendarDate,
    HttpsReference,
    Identifier,
    Reference,
    ReferenceSet,
    Sha256,
    StrictModel,
    Target,
    Text,
    TextSet,
)
from dscat.normalization import (
    normalize_identifier,
    normalize_quantity,
    normalize_reference,
    parse_timestamp,
)

Timestamp = Annotated[AwareDatetime, BeforeValidator(parse_timestamp)]
CapacityKind = Literal["size", "average_ingestion", "peak_ingestion"]
Unit = Literal["B", "kB", "MB", "GB", "TB", "PB", "KiB", "MiB", "GiB", "TiB", "PiB"]
ReviewState = Literal["not_reviewed", "in_review", "approved", "changes_requested"]


class PartyReference(StrictModel):
    """A supplied party label is sufficient for intake without role inference."""

    label: Text
    role: Literal["contact", "owner", "unspecified_contact_or_owner"] = (
        "unspecified_contact_or_owner"
    )
    email: EmailStr | None = None
    uri: HttpsReference | None = None


class EntityReference(StrictModel):
    """An explicitly local or external reference without online resolution."""

    reference_kind: Literal["local", "external"]
    id: str

    @field_validator("id", mode="before")
    @classmethod
    def validate_reference(cls, value: object, info: ValidationInfo) -> str:
        """Normalize according to the explicitly selected reference kind."""
        return (
            normalize_identifier(value)
            if info.data.get("reference_kind") == "local"
            else normalize_reference(value)
        )


class RoleAssignment(StrictModel):
    """An explicit party role distinct from the four-field intake contact/owner."""

    reference_kind: Literal["local", "external"]
    party_id: str
    role: Literal["accountable_owner", "steward", "contact", "maintainer"]
    label: Text
    email: EmailStr | None = None
    uri: HttpsReference | None = None

    @field_validator("party_id", mode="before")
    @classmethod
    def validate_party(cls, value: object, info: ValidationInfo) -> str:
        """Check party reference syntax without inferring an accountable role."""
        return (
            normalize_identifier(value)
            if info.data.get("reference_kind") == "local"
            else normalize_reference(value)
        )


class Domain(StrictModel):
    """Optional supplied domain identity and semantic reference."""

    id: Identifier
    reference: Reference | None = None


class Distribution(StrictModel):
    """A distribution is metadata about access, never a live endpoint probe."""

    id: Identifier
    title: Text | None = None
    access_url: HttpsReference | None = None
    download_url: HttpsReference | None = None
    media_type: Text | None = None
    format: Text | None = None


class DataService(StrictModel):
    """A service has its own identity and explicit served-dataset references."""

    id: Identifier
    title: Text | None = None
    endpoint_url: HttpsReference | None = None
    endpoint_description: Text | None = None
    served_datasets: list[EntityReference] | None = None

    @field_validator("served_datasets")
    @classmethod
    def sort_references(
        cls, value: list[EntityReference] | None
    ) -> list[EntityReference] | None:
        """Establish order by explicit reference kind and normalized identity."""
        return (
            None
            if value is None
            else sorted(value, key=lambda ref: (ref.reference_kind, ref.id))
        )

    @model_validator(mode="after")
    def unique_references(self) -> Self:
        """Reject duplicate links or conflicting kinds for one reference."""
        references = self.served_datasets or []
        if len({item.id for item in references}) != len(references):
            msg = "Duplicate or conflicting served-dataset reference."
            raise ValueError(msg)
        return self


class FieldDefinition(StrictModel):
    """An ordered schema field with no data samples or inferred types."""

    object_name: Text
    field_name: Text
    type: Text
    description: Text | None = None
    nullable: bool | None = None
    semantic_references: ReferenceSet | None = None


class ConsumerDetail(StrictModel):
    """Optional descriptive metadata kept separate from the generic summary."""

    intended_uses: TextSet | None = None
    limitations: TextSet | None = None
    access_instructions: TextSet | None = None
    provenance: TextSet | None = None
    semantic_references: ReferenceSet | None = None


class Commitment(StrictModel):
    """An explicitly supplied assertion, never a monitored enforcement result."""

    id: Identifier
    kind: Literal["quality", "service"]
    subject: Text
    description: Text | None = None
    value: Text | None = None
    unit: Text | None = None
    reference: Reference | None = None

    @model_validator(mode="after")
    def require_assertion(self) -> Self:
        """Require a description or a supplied value; a unit needs a value."""
        if (self.description is None and self.value is None) or (
            self.unit is not None and self.value is None
        ):
            msg = "Supply an assertion description or value, and a value for any unit."
            raise ValueError(msg)
        return self


class Determination(StrictModel):
    """Independent access/use or metadata-disclosure facts."""

    state: Literal[
        "unknown", "partially_restricted", "fully_restricted", "unrestricted"
    ]
    authority: Text | None = None
    reference: Reference | None = None
    rationale: Text | None = None
    determined_on: CalendarDate | None = None
    review_status: ReviewState | None = None


class MetadataReview(StrictModel):
    """A supplied review state, not a consequence of structural validity."""

    state: ReviewState
    authority: Text | None = None
    reference: Reference | None = None
    reviewed_on: CalendarDate | None = None


SUBJECTS = {
    "canonical": frozenset(
        {
            "id",
            "title",
            "description",
            "core_party.label",
            "core_party.email",
            "contract_id",
            "contract_version",
        }
    ),
    "configuration": frozenset(
        {
            "dcat_us_3.catalog_id",
            "identity.dataset_namespace",
            "identity.contract_namespace",
            "odcs_3_2.contract_version",
            "identity.parties.role_email",
        }
    ),
    "derived_target": frozenset(
        {
            "catalog_iri",
            "dataset_iri",
            "contract_iri",
            "contact_email_iri",
            "contact_username",
            "contract_version",
        }
    ),
}
DCAT_DERIVED = frozenset({"catalog_iri", "dataset_iri", "contact_email_iri"})


class ApprovalSubject(StrictModel):
    """A member of the closed field/value approval scope vocabulary."""

    subject_kind: Literal["canonical", "configuration", "derived_target"]
    subject_id: Text
    target: Target

    @model_validator(mode="after")
    def closed_subject(self) -> Self:
        """Reject unknown subjects and unsupported target/subject combinations."""
        if self.subject_id not in SUBJECTS[self.subject_kind]:
            msg = "Unsupported approval subject."
            raise ValueError(msg)
        if self.subject_kind == "derived_target" and (
            (self.subject_id in DCAT_DERIVED) != (self.target == "dcat-us-3")
        ):
            msg = "Approval subject is unsupported for this target."
            raise ValueError(msg)
        return self


class PublicationApproval(ApprovalSubject):
    """Supplied authority and value identity without authenticating authority."""

    approved_value_sha256: Sha256
    policy_version: Text
    authority: Text
    approved_on: CalendarDate


class PublicationDecision(StrictModel):
    """Publication state remains separate from disclosure and access state."""

    state: Literal["unknown", "approved", "denied"]
    approvals: list[PublicationApproval] | None = None

    @field_validator("approvals")
    @classmethod
    def sort_approvals(
        cls, value: list[PublicationApproval] | None
    ) -> list[PublicationApproval] | None:
        """Order exact scopes deterministically, without granting approval."""
        return (
            None
            if value is None
            else sorted(value, key=lambda a: (a.subject_kind, a.subject_id, a.target))
        )

    @model_validator(mode="after")
    def unique_approvals(self) -> Self:
        """Reject duplicate or conflicting approval scopes."""
        approvals = self.approvals or []
        keys = {(a.subject_kind, a.subject_id, a.target) for a in approvals}
        if len(keys) != len(approvals):
            msg = "Duplicate publication approval scope."
            raise ValueError(msg)
        return self


class RecordsManagement(StrictModel):
    """Descriptive records instructions without inferred deletion authority."""

    authority: Text | None = None
    reference: Reference | None = None
    trigger: Text | None = None
    duration_days: Annotated[int, Field(ge=0, le=2**31 - 1)] | None = None
    instruction: Text | None = None
    hold_state: Literal["unknown", "active", "inactive"] | None = None
    review_state: Literal["unknown", "active", "inactive"] | None = None
    conflicts: TextSet | None = None


class UnknownCapacity(StrictModel):
    """Unknown quantities do not invent a unit, measurement date or zero."""

    kind: CapacityKind
    state: Literal["unknown"]


class KnownCapacity(StrictModel):
    """An exact quantity with independent supplied measurement context."""

    kind: CapacityKind
    state: Literal["known"]
    value: Text
    unit: Unit
    normalized_bytes: Annotated[int, Field(ge=0, le=2**63 - 1)]
    basis: Literal["logical", "physical"]
    measured_on: CalendarDate
    window_start: Timestamp | None = None
    window_end: Timestamp | None = None

    @model_validator(mode="after")
    def consistent_quantity(self) -> Self:
        """Validate normalized bytes and require exactly the applicable rate context."""
        if normalize_quantity(self.value, self.unit) != self.normalized_bytes:
            msg = "Normalized byte count does not match the supplied quantity."
            raise ValueError(msg)
        if self.kind == "size":
            if self.window_start is not None or self.window_end is not None:
                msg = "Size observations do not accept rate windows."
                raise ValueError(msg)
        elif (
            self.window_start is None
            or self.window_end is None
            or self.window_end <= self.window_start
        ):
            msg = "Supply a timezone-aware rate window ending after its start."
            raise ValueError(msg)
        return self


CapacityObservation = Annotated[
    KnownCapacity | UnknownCapacity, Field(discriminator="state")
]


class UnknownRetention(StrictModel):
    """Explicit unknown retention is distinct from omitted or zero retention."""

    state: Literal["unknown"]


class IndefiniteRetention(StrictModel):
    """An explicitly supplied indefinite duration."""

    state: Literal["indefinite"]


class KnownRetention(StrictModel):
    """Retention is an integer day count, never a disposal calculation."""

    state: Literal["known"]
    days: Annotated[int, Field(ge=0, le=2**31 - 1)]


CapacityRetention = Annotated[
    KnownRetention | UnknownRetention | IndefiniteRetention,
    Field(discriminator="state"),
]


class DatasetRecord(StrictModel):
    """One normalized dataset with independent optional metadata groups."""

    id: Identifier
    title: Text
    description: Text
    core_party: PartyReference
    dataset_version: Text | None = None
    contract_id: Text | None = None
    contract_version: Text | None = None
    product_reference: Reference | None = None
    roles: list[RoleAssignment] | None = None
    domain: Domain | None = None
    inventory_added: CalendarDate | None = None
    metadata_reviewed: CalendarDate | None = None
    dataset_modified: CalendarDate | None = None
    update_frequency: Text | None = None
    distributions: list[Distribution] | None = None
    services: list[DataService] | None = None
    fields: list[FieldDefinition] | None = None
    consumer: ConsumerDetail | None = None
    commitments: list[Commitment] | None = None
    access_determination: Determination | None = None
    disclosure_determination: Determination | None = None
    metadata_review: MetadataReview | None = None
    publication: PublicationDecision | None = None
    records: RecordsManagement | None = None
    capacity: list[CapacityObservation] | None = None
    capacity_retention: CapacityRetention | None = None

    @field_validator("distributions", "services", "commitments")
    @classmethod
    def sort_identified[T: (Distribution, DataService, Commitment)](
        cls,
        value: list[T] | None,
    ) -> list[T] | None:
        """Order identity-bearing metadata while leaving field-schema order intact."""
        return None if value is None else sorted(value, key=lambda item: item.id)

    @field_validator("roles")
    @classmethod
    def sort_roles(
        cls, value: list[RoleAssignment] | None
    ) -> list[RoleAssignment] | None:
        """Order explicit roles by party identity and role."""
        return (
            None
            if value is None
            else sorted(value, key=lambda item: (item.party_id, item.role))
        )

    @field_validator("capacity")
    @classmethod
    def sort_capacity(
        cls, value: list[CapacityObservation] | None
    ) -> list[CapacityObservation] | None:
        """Order observations by kind, state and explicit measurement context."""

        def key(item: CapacityObservation) -> tuple[str, str, str, str, str]:
            if isinstance(item, UnknownCapacity):
                return item.kind, item.state, "", "", ""
            return (
                item.kind,
                item.state,
                item.basis,
                str(item.window_start or ""),
                str(item.window_end or ""),
            )

        return None if value is None else sorted(value, key=key)

    @model_validator(mode="after")
    def check_collections(self) -> Self:
        """Reject ambiguous local keys and inconsistent comparable ingestion rates."""
        collections = [
            [(r.reference_kind, r.party_id, r.role) for r in self.roles or []],
            [d.id for d in self.distributions or []],
            [s.id for s in self.services or []],
            [(f.object_name, f.field_name) for f in self.fields or []],
            [c.id for c in self.commitments or []],
            [
                (c.kind, c.basis, c.window_start, c.window_end)
                if isinstance(c, KnownCapacity)
                else (c.kind,)
                for c in self.capacity or []
            ],
        ]
        if any(len(keys) != len(set(keys)) for keys in collections):
            msg = "Duplicate or ambiguous collection identity."
            raise ValueError(msg)
        averages = [
            c
            for c in self.capacity or []
            if isinstance(c, KnownCapacity) and c.kind == "average_ingestion"
        ]
        peaks = [
            c
            for c in self.capacity or []
            if isinstance(c, KnownCapacity) and c.kind == "peak_ingestion"
        ]
        for average in averages:
            for peak in peaks:
                if (average.basis, average.window_start, average.window_end) == (
                    peak.basis,
                    peak.window_start,
                    peak.window_end,
                ) and peak.normalized_bytes < average.normalized_bytes:
                    msg = (
                        "Comparable peak ingestion must be at least average ingestion."
                    )
                    raise ValueError(msg)
        return self


class Catalog(StrictModel):
    """Versioned dataset aggregate without source paths or derived assessments."""

    schema_version: Literal["1.0"]
    datasets: list[DatasetRecord]

    @field_validator("datasets")
    @classmethod
    def sort_datasets(cls, value: list[DatasetRecord]) -> list[DatasetRecord]:
        """Canonical datasets have case-sensitive normalized identifier order."""
        return sorted(value, key=lambda record: record.id)

    @model_validator(mode="after")
    def unique_datasets(self) -> Self:
        """Require unique normalized business identities and resolvable local links."""
        ids = {record.id for record in self.datasets}
        if len(ids) != len(self.datasets):
            msg = "Duplicate dataset identity."
            raise ValueError(msg)
        for record in self.datasets:
            for service in record.services or []:
                if any(
                    ref.reference_kind == "local" and ref.id not in ids
                    for ref in service.served_datasets or []
                ):
                    msg = "Unresolved local served-dataset reference."
                    raise ValueError(msg)
        return self
