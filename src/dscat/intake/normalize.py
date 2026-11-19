# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Property-specific conversion into canonical records without invented facts."""

import re
from collections import defaultdict

from pydantic import ValidationError

from dscat.intake.limits import DiagnosticCollector, IntakeError, fail
from dscat.models.base import StrictModel
from dscat.models.catalog import (
    DataService,
    DatasetRecord,
    EntityReference,
    FieldDefinition,
    PublicationApproval,
    RoleAssignment,
)
from dscat.models.diagnostics import Code, Diagnostic
from dscat.models.intake import DatasetRow, DetailRow, IntakeBatch, SourceLocation
from dscat.normalization import normalize_identifier, normalize_quantity

MAX_DAY_DIGITS = len(str(2**31 - 1))
CONSUMER_FIELDS = {
    "intended_use": "intended_uses",
    "limitation": "limitations",
    "access_instruction": "access_instructions",
    "provenance": "provenance",
    "semantic_reference": "semantic_references",
}
ROLE_COLUMNS = {
    "owner": "accountable_owner",
    "steward": "steward",
    "maintainer": "maintainer",
}


class LocatedRecord(StrictModel):
    """Source associations remain outside authoritative canonical metadata."""

    record: DatasetRecord
    location: SourceLocation


class NormalizedBatch(StrictModel):
    """Valid individual records and explicit failures from one workbook."""

    records: list[LocatedRecord]
    diagnostics: list[Diagnostic]
    has_errors: bool


def located_error(
    location: SourceLocation, *, code: Code = "INVALID_METADATA"
) -> Diagnostic:
    """Construct a fixed diagnostic from typed, invocation-local coordinates."""
    fields = location.model_dump(exclude_none=True)
    fields.update(
        {"code": code, "severity": "error", "message_key": "correct_metadata"}
    )

    return Diagnostic.model_validate(fields)


def integer_days(value: str) -> int:
    """Convert only the explicit nonnegative whole-day grammar, never locale text."""
    if (
        len(value) > MAX_DAY_DIGITS
        or re.fullmatch(r"[0-9]+", value) is None
        or int(value) > 2**31 - 1
    ):
        raise fail(code="INVALID_METADATA")
    return int(value)


def group_properties(rows: list[DetailRow]) -> dict[str, object]:
    """Retain one property value and only its supported auxiliary facts."""
    values: dict[str, object] = {}
    for row in rows:
        additions: dict[str, object] = {row.property: row.value}
        if row.unit is not None:
            additions["unit"] = row.unit
        if row.reference is not None:
            additions["reference"] = row.reference
        for name, value in additions.items():
            if name in values and values[name] != value:
                raise fail(code="INVALID_METADATA")
            values[name] = value
    return values


def merge_facts(destination: dict[str, object], values: dict[str, object]) -> None:
    """Conflicting supplied scalars cannot overwrite one another."""
    for key, value in values.items():
        if key in destination and destination[key] != value:
            raise fail(code="INVALID_METADATA")
        destination[key] = value


def property_conversion(section: str, values: dict[str, object]) -> dict[str, object]:
    """Convert declared state/day/byte fields before canonical schema validation."""
    result = dict(values)
    if (
        section
        in {
            "capacity",
            "capacity_retention",
            "access_determination",
            "disclosure_determination",
            "publication",
        }
        and result.get("state") == "Unknown"
    ):
        result["state"] = "unknown"
    for key in ("days", "duration_days"):
        raw = result.get(key)
        if isinstance(raw, str):
            result[key] = integer_days(raw)
    if section == "capacity" and result.get("state") == "known":
        value, unit = result.get("value"), result.get("unit")
        if not isinstance(value, str) or not isinstance(unit, str):
            raise fail(code="INVALID_METADATA")
        result["normalized_bytes"] = normalize_quantity(value, unit)
    return result


class RecordBuilder:
    """Assemble only the closed canonical groups for one primary dataset row."""

    def __init__(self, row: DatasetRow, details: list[DetailRow]) -> None:
        """Preserve supplied primary facts and separate grouped detail identities."""
        primary = row.model_dump(exclude_none=True, exclude={"location", *ROLE_COLUMNS})
        party: dict[str, object] = {}
        for key, target in {
            "core_party": "label",
            "core_role": "role",
            "core_email": "email",
            "core_url": "uri",
        }.items():
            if key in primary:
                party[target] = primary.pop(key)
        self.values = primary | {"core_party": party}
        self.row = row
        self.groups: dict[tuple[str, str], list[DetailRow]] = defaultdict(list)
        for detail in details:
            self.groups[detail.section, detail.entry_id].append(detail)
        self.collections: dict[str, list[object]] = defaultdict(list)
        self.consumer: dict[str, list[str]] = defaultdict(list)
        self.records: dict[str, object] = {}
        self.conflicts: list[str] = []
        self.roles: dict[str, RoleAssignment] = {}
        self.services: dict[str, dict[str, object]] = {}
        self.service_links: dict[str, list[EntityReference]] = defaultdict(list)
        self.publication: dict[str, object] = {}
        self.approvals: list[PublicationApproval] = []

    def add_group(self, section: str, entry: str, rows: list[DetailRow]) -> None:
        """Dispatch a closed detail section to its canonical representation."""
        values = property_conversion(section, group_properties(rows))
        simple = {
            "domain",
            "access_determination",
            "disclosure_determination",
            "metadata_review",
            "capacity_retention",
        }
        if section in {"identity", "dates"}:
            # Dates are compared after the same property-specific schema conversion.
            merged = DatasetRecord.model_fields
            for key, value in values.items():
                if key in self.values and key in merged:
                    candidate = DatasetRecord.model_validate(self.values | {key: value})
                    if getattr(candidate, key) != self.values[key]:
                        raise fail(code="INVALID_METADATA")
                self.values[key] = value
        elif section in simple:
            self.values[section] = values
        elif section in {"distribution", "commitment", "capacity"}:
            if section == "commitment":
                values["id"] = entry
            self.collections[
                {
                    "distribution": "distributions",
                    "commitment": "commitments",
                    "capacity": "capacity",
                }[section]
            ].append(values)
        else:
            self.add_complex(section, entry, values)

    def add_complex(self, section: str, entry: str, values: dict[str, object]) -> None:
        """Convert reference/approval/collection groups without delimiter inference."""
        if section == "role":
            self.roles[entry] = RoleAssignment.model_validate(values)
        elif section == "service":
            service = DataService.model_validate(
                {
                    key: value
                    for key, value in values.items()
                    if key not in {"served_dataset_id", "reference_kind"}
                }
            )
            if service.id in self.services:
                raise fail(code="INVALID_METADATA")
            self.services[service.id] = values
        elif section == "service_dataset":
            if values.keys() != {"service_id", "dataset_id", "reference_kind"}:
                raise fail(code="INVALID_METADATA")
            identifier = normalize_identifier(values["service_id"])
            self.service_links[identifier].append(
                EntityReference.model_validate(
                    {
                        "id": values["dataset_id"],
                        "reference_kind": values["reference_kind"],
                    }
                )
            )
        else:
            self.add_descriptive(section, values)

    def add_descriptive(self, section: str, values: dict[str, object]) -> None:
        """Keep descriptive lists, records conflicts and publication facts distinct."""
        if section == "consumer":
            for key, value in values.items():
                if not isinstance(value, str):
                    raise fail(code="INVALID_METADATA")
                self.consumer[CONSUMER_FIELDS[key]].append(value)
        elif section == "records":
            conflict = values.pop("conflict", None)
            if isinstance(conflict, str):
                self.conflicts.append(conflict)
            merge_facts(self.records, values)
        elif section == "publication":
            state = values.pop("state", None)
            if state is not None:
                merge_facts(self.publication, {"state": state})
            if values:
                self.approvals.append(PublicationApproval.model_validate(values))

    def finish_services(self) -> None:
        """Require explicit single-link or grouped-link form, never mix either."""
        if self.service_links.keys() - self.services.keys():
            raise fail(code="UNRESOLVED_REFERENCE")
        for identifier, values in self.services.items():
            single = values.pop("served_dataset_id", None)
            kind = values.pop("reference_kind", None)
            links = self.service_links.get(identifier, [])
            if single is not None or kind is not None:
                if single is None or kind is None or links:
                    raise fail(code="INVALID_METADATA")
                links = [
                    EntityReference.model_validate(
                        {"id": single, "reference_kind": kind}
                    )
                ]
            if links:
                values["served_datasets"] = links
            self.collections["services"].append(values)

    def finish(self) -> DatasetRecord:
        """Resolve role aliases and validate every assembled canonical fact."""
        for column, expected in ROLE_COLUMNS.items():
            reference = getattr(self.row, column)
            if reference is not None:
                entry = normalize_identifier(reference)
                if entry not in self.roles or self.roles[entry].role != expected:
                    raise fail(code="UNRESOLVED_REFERENCE")
        self.finish_services()
        if self.roles:
            self.values["roles"] = list(self.roles.values())
        if self.consumer:
            self.values["consumer"] = dict(self.consumer)
        if self.conflicts:
            self.records["conflicts"] = self.conflicts
        if self.records:
            self.values["records"] = self.records
        if self.approvals:
            self.publication["approvals"] = self.approvals
        if self.publication:
            self.values["publication"] = self.publication
        self.values.update(self.collections)
        return DatasetRecord.model_validate(self.values)


def normalize_record(
    row: DatasetRow,
    details: list[DetailRow],
    fields: list[FieldDefinition],
    collector: DiagnosticCollector,
) -> LocatedRecord | None:
    """Collect independent grouped errors and finish one canonical candidate."""
    builder = RecordBuilder(row, details)
    invalid = False
    for (section, entry), rows in sorted(builder.groups.items()):
        try:
            builder.add_group(section, entry, rows)
        except ValidationError, ValueError, IntakeError:
            collector.add(located_error(rows[0].location))
            invalid = True
    if fields:
        builder.collections["fields"] = list(fields)
    try:
        record = builder.finish()
    except IntakeError as error:
        collector.add(located_error(row.location, code=error.diagnostic.code))
    except ValidationError, ValueError:
        collector.add(located_error(row.location))
    else:
        if not invalid:
            return LocatedRecord(record=record, location=row.location)
    return None


def normalize_batch(batch: IntakeBatch) -> NormalizedBatch:
    """Validate all independent records and report orphan/invalid detail groups."""
    collector = DiagnosticCollector()
    for diagnostic in batch.diagnostics:
        collector.add(diagnostic)
    collector.has_errors |= batch.has_errors
    dataset_ids = {row.id for row in batch.datasets if row.id is not None}
    details: dict[str, list[DetailRow]] = defaultdict(list)
    fields: dict[str, list[FieldDefinition]] = defaultdict(list)
    for detail in batch.details:
        if detail.dataset_id not in dataset_ids:
            collector.add(located_error(detail.location, code="UNRESOLVED_REFERENCE"))
        else:
            details[detail.dataset_id].append(detail)
    for row in batch.fields:
        if row.dataset_id not in dataset_ids:
            collector.add(located_error(row.location, code="UNRESOLVED_REFERENCE"))
            continue
        values = row.model_dump(
            exclude_none=True, exclude={"location", "dataset_id", "semantic_reference"}
        )
        if row.semantic_reference is not None:
            values["semantic_references"] = [row.semantic_reference]
        try:
            fields[row.dataset_id].append(FieldDefinition.model_validate(values))
        except ValidationError:
            collector.add(located_error(row.location))
    records: list[LocatedRecord] = []
    for row in batch.datasets:
        record = normalize_record(
            row, details.get(row.id or "", []), fields.get(row.id or "", []), collector
        )
        if record is not None:
            records.append(record)
    return NormalizedBatch(
        records=records, diagnostics=collector.items, has_errors=collector.has_errors
    )
