# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Closed versioned worksheet vocabulary and located intake messages."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from dscat.models.base import CalendarDate, Identifier, StrictModel, Text
from dscat.models.diagnostics import Diagnostic, Sheet

DETAIL_PROPERTIES = {
    "identity": frozenset(
        {"dataset_version", "contract_id", "contract_version", "product_reference"}
    ),
    "dates": frozenset(
        {"inventory_added", "metadata_reviewed", "dataset_modified", "update_frequency"}
    ),
    "role": frozenset({"party_id", "role", "label", "email", "uri", "reference_kind"}),
    "domain": frozenset({"id", "reference"}),
    "distribution": frozenset(
        {"id", "title", "access_url", "download_url", "media_type", "format"}
    ),
    "service": frozenset(
        {
            "id",
            "title",
            "endpoint_url",
            "endpoint_description",
            "served_dataset_id",
            "reference_kind",
        }
    ),
    "service_dataset": frozenset({"service_id", "dataset_id", "reference_kind"}),
    "consumer": frozenset(
        {
            "intended_use",
            "limitation",
            "access_instruction",
            "provenance",
            "semantic_reference",
        }
    ),
    "commitment": frozenset(
        {"kind", "subject", "description", "value", "unit", "reference"}
    ),
    "access_determination": frozenset(
        {
            "state",
            "authority",
            "reference",
            "rationale",
            "determined_on",
            "review_status",
        }
    ),
    "disclosure_determination": frozenset(
        {
            "state",
            "authority",
            "reference",
            "rationale",
            "determined_on",
            "review_status",
        }
    ),
    "metadata_review": frozenset({"state", "authority", "reference", "reviewed_on"}),
    "publication": frozenset(
        {
            "state",
            "authority",
            "approved_on",
            "policy_version",
            "subject_kind",
            "subject_id",
            "target",
            "approved_value_sha256",
        }
    ),
    "records": frozenset(
        {
            "authority",
            "reference",
            "trigger",
            "duration_days",
            "instruction",
            "hold_state",
            "review_state",
            "conflict",
        }
    ),
    "capacity": frozenset(
        {
            "kind",
            "state",
            "value",
            "unit",
            "basis",
            "measured_on",
            "window_start",
            "window_end",
        }
    ),
    "capacity_retention": frozenset({"state", "days"}),
}
SINGLETON_SECTIONS = frozenset(
    {
        "identity",
        "dates",
        "domain",
        "access_determination",
        "disclosure_determination",
        "metadata_review",
        "records",
        "capacity_retention",
    }
)


class SourceLocation(StrictModel):
    """Invocation-local source ordinal and known worksheet coordinates."""

    source_token: Annotated[int, Field(ge=1)]
    sheet: Sheet
    row: Annotated[int, Field(ge=1)]
    column: Annotated[int, Field(ge=1)] | None = None


class WorkbookMetadata(StrictModel):
    """The supported workbook schema and artifact kind are explicit constants."""

    schema_version: Literal["1.0", "2.0"]
    kind: Literal["dataset-intake", "collection-intake"]

    @model_validator(mode="after")
    def matching_kind(self) -> Self:
        """Keep schema version and artifact kind paired explicitly."""
        if (self.schema_version == "2.0") != (self.kind == "collection-intake"):
            msg = "Workbook schema and artifact kind disagree."
            raise ValueError(msg)
        return self


class DatasetRow(StrictModel):
    """A primary row; owner/steward/maintainer reference located role entry IDs."""

    location: SourceLocation
    id: Identifier | None = None
    title: Text | None = None
    description: Text | None = None
    core_party: Text | None = None
    core_role: Literal["contact", "owner"] | None = None
    core_email: Text | None = None
    core_url: Text | None = None
    dataset_version: Text | None = None
    inventory_added: CalendarDate | None = None
    metadata_reviewed: CalendarDate | None = None
    dataset_modified: CalendarDate | None = None
    update_frequency: Text | None = None
    owner: Identifier | None = None
    steward: Identifier | None = None
    maintainer: Identifier | None = None


class FieldRow(StrictModel):
    """Located schema field with explicit boolean and reference encodings."""

    location: SourceLocation
    dataset_id: Identifier
    object_name: Text
    field_name: Text
    type: Text
    description: Text | None = None
    nullable: bool | None = None
    semantic_reference: Text | None = None


class DetailRow(StrictModel):
    """One property-specific scalar, never an inferred JSON/list expression."""

    location: SourceLocation
    dataset_id: Identifier
    section: Text
    entry_id: Identifier
    property: Text
    value: Text
    unit: Text | None = None
    reference: Text | None = None

    @model_validator(mode="after")
    def closed_vocabulary(self) -> Self:
        """Reject unknown sections/properties and unsupported auxiliary cells."""
        if (
            self.section not in DETAIL_PROPERTIES
            or self.property not in DETAIL_PROPERTIES[self.section]
        ):
            msg = "Unsupported detail section or property."
            raise ValueError(msg)
        singleton = self.section in SINGLETON_SECTIONS and not (
            self.section == "records" and self.property == "conflict"
        )
        if singleton and self.entry_id != "dataset":
            msg = (
                "Single-value dataset properties require the dataset entry identifier."
            )
            raise ValueError(msg)
        supports_unit = (
            self.section in {"capacity", "commitment"} and self.property == "value"
        )
        supports_reference = self.section == "commitment" and self.property in {
            "value",
            "description",
        }
        if (self.unit is not None and not supports_unit) or (
            self.reference is not None and not supports_reference
        ):
            msg = "Auxiliary unit or reference is unsupported for this property."
            raise ValueError(msg)
        return self


class CollectionRow(StrictModel):
    """Located lexical collection answers before independent group conversion."""

    location: SourceLocation
    name: Text
    owner: Text
    pii: Literal["Yes", "No", "Unknown"]
    phi: Literal["Yes", "No", "Unknown"]
    cui: Literal["Yes", "No", "Unknown"]
    pcii: Literal["Yes", "No", "Unknown"]
    isvi: Literal["Yes", "No", "Unknown"]
    other: Literal["Yes", "No", "Unknown"]
    submitted_by: Text
    completed_on: CalendarDate
    description: Text | None = None
    location_label: Text | None = None
    other_explanation: Text | None = None
    current_value: Text | None = None
    current_unit: Literal["KB", "MB", "GB", "TB", "PB"] | None = None
    current_basis: Literal["Estimate", "Measured", "Unknown"] | None = None
    consumers: Text | None = None
    use: Text | None = None
    access_pattern: Text | None = None
    retention_days: Text | None = None
    retention_status: Literal["Not yet determined", "Proposed", "Confirmed"] | None = (
        None
    )
    process: Text | None = None
    explanation: Text | None = None
    source_names: Text | None = None
    per_run_value: Text | None = None
    per_run_unit: Literal["KB", "MB", "GB", "TB", "PB"] | None = None
    per_run_basis: Literal["Estimate", "Measured", "Unknown"] | None = None
    typical_runs: Text | None = None
    period: Text | None = None


class IntakeBatch(StrictModel):
    """Typed rows and fixed diagnostics from examined workbook sources."""

    metadata: WorkbookMetadata
    datasets: list[DatasetRow]
    fields: list[FieldRow]
    details: list[DetailRow]
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    has_errors: bool = False
    collections: list[CollectionRow] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_detail_properties(self) -> Self:
        """Prevent any repeated property from silently overwriting a fact."""
        keys = {
            (row.dataset_id, row.section, row.entry_id, row.property)
            for row in self.details
        }
        if len(keys) != len(self.details):
            msg = (
                "Repeated detail property, including identical repeats, is unsupported."
            )
            raise ValueError(msg)
        return self
