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
from dscat.models.diagnostics import Code, Diagnostic, Expected
from dscat.models.intake import DatasetRow, DetailRow, IntakeBatch, SourceLocation
from dscat.normalization import normalize_identifier, normalize_quantity

GROUP_EXPECTED: dict[str, Expected] = {
    "dates": "date",
    "capacity": "capacity",
    "capacity_retention": "days",
    "role": "role_reference",
    "service": "service_reference",
    "service_dataset": "service_reference",
}

RECORD_EXPECTED: dict[str, Expected] = {
    "capacity": "capacity",
    "capacity_retention": "days",
    "services": "service_reference",
    "roles": "role_reference",
}

SCALAR_EXPECTED: dict[str, Expected] = {
    "id": "identifier",
    "email": "email",
    "uri": "https_reference",
    "inventory_added": "date",
    "metadata_reviewed": "date",
    "dataset_modified": "date",
    "determined_on": "date",
    "reviewed_on": "date",
    "approved_on": "date",
    "measured_on": "date",
    "days": "days",
    "duration_days": "days",
    "normalized_bytes": "quantity",
    "semantic_references": "reference",
    "reference": "reference",
    "product_reference": "reference",
    "access_url": "https_reference",
    "download_url": "https_reference",
    "endpoint_url": "https_reference",
}

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
    location: SourceLocation,
    *,
    code: Code = "INVALID_METADATA",
    expected: Expected | None = None,
) -> Diagnostic:
    """Construct a fixed diagnostic from typed, invocation-local coordinates."""
    fields = location.model_dump(exclude_none=True)
    fields.update(
        {"code": code, "severity": "error", "message_key": "correct_metadata"}
    )

    fields["expected"] = expected or (
        "role_reference"
        if code == "UNRESOLVED_REFERENCE"
        else "core"
        if location.sheet == "Datasets"
        else "detail_group"
    )
    return Diagnostic.model_validate(fields)


def unperformed_references(location: SourceLocation | None = None) -> Diagnostic:
    """Report dependent reference checks without inventing dangling-ID failures."""
    fields: dict[str, object] = {
        "code": "REFERENCE_CHECK_UNPERFORMED",
        "severity": "info",
        "message_key": "review_scope",
        "check_state": "unperformed",
    }
    if location is not None:
        fields.update(location.model_dump(exclude_none=True))
    return Diagnostic.model_validate(fields)


def integer_days(value: str) -> int:
    """Convert only the explicit nonnegative whole-day grammar, never locale text."""
    normalized = value.lstrip("0") or "0"
    if (
        len(normalized) > MAX_DAY_DIGITS
        or re.fullmatch(r"[0-9]+", value) is None
        or int(normalized) > 2**31 - 1
    ):
        raise fail(code="INVALID_METADATA")
    return int(normalized)


def group_properties(rows: list[DetailRow]) -> dict[str, object]:
    """Retain one property value and only its supported auxiliary facts."""
    values: dict[str, object] = {}
    properties: set[str] = set()
    for row in rows:
        if row.property in properties:
            raise fail(code="INVALID_METADATA")
        properties.add(row.property)
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
        self.collection_rows: dict[str, list[list[DetailRow]]] = defaultdict(list)
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
            collection = {
                "distribution": "distributions",
                "commitment": "commitments",
                "capacity": "capacity",
            }[section]
            self.collections[collection].append(values)
            self.collection_rows[collection].append(rows)
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
        else:
            raise fail(code="INVALID_METADATA")

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


def collect_group_errors(
    error: ValidationError,
    rows: list[DetailRow],
    section: str,
    collector: DiagnosticCollector,
) -> None:
    """Bind model failures to supported property rows without reflecting error text."""
    for detail in error.errors(include_input=False, include_context=False):
        property_name = str(detail["loc"][0]) if detail["loc"] else ""
        location = next(
            (row.location for row in rows if row.property == property_name),
            rows[0].location,
        )
        expected = (
            GROUP_EXPECTED.get(section, "detail_group")
            if detail["type"] == "missing"
            else SCALAR_EXPECTED.get(
                property_name, GROUP_EXPECTED.get(section, "detail_group")
            )
        )
        collector.add(located_error(location, expected=expected))


def canonical_error_location(
    builder: RecordBuilder, path: tuple[int | str, ...]
) -> SourceLocation:
    """Locate a canonical field failure in its original supported detail group."""
    if not path:
        return builder.row.location
    field = str(path[0])
    section = {
        "distributions": "distribution",
        "services": "service",
        "commitments": "commitment",
    }.get(field, field)
    groups = builder.collection_rows.get(field, []) or [
        rows
        for (name, _entry), rows in sorted(builder.groups.items())
        if name == section
    ]
    if not groups:
        return builder.row.location
    index = path[1] if len(path) > 1 and isinstance(path[1], int) else 0
    rows = groups[index] if 0 <= index < len(groups) else groups[0]
    return next(
        (row.location for row in rows if row.property == str(path[-1])),
        rows[0].location,
    )


def finish_record(
    builder: RecordBuilder, collector: DiagnosticCollector
) -> DatasetRecord | None:
    """Translate all final canonical validation failures to safe source diagnostics."""
    try:
        return builder.finish()
    except IntakeError as error:
        collector.add(located_error(builder.row.location, code=error.diagnostic.code))
    except ValidationError as error:
        for detail in error.errors(include_input=False, include_context=False):
            key = str(detail["loc"][0]) if detail["loc"] else ""
            leaf = str(detail["loc"][-1]) if detail["loc"] else ""
            expected = SCALAR_EXPECTED.get(
                leaf,
                RECORD_EXPECTED.get(
                    key,
                    "detail_group" if builder.groups or builder.collections else "core",
                ),
            )
            collector.add(
                located_error(
                    canonical_error_location(builder, detail["loc"]), expected=expected
                )
            )
    return None


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
        except ValidationError as error:
            collect_group_errors(error, rows, section, collector)
            invalid = True
        except ValueError, IntakeError:
            collector.add(
                located_error(
                    rows[0].location,
                    expected=GROUP_EXPECTED.get(section, "detail_group"),
                )
            )
            invalid = True
    if fields:
        builder.collections["fields"] = list(fields)
    record = finish_record(builder, collector)
    if record is not None and not invalid:
        return LocatedRecord(record=record, location=row.location)
    return None


def convert_fields(
    batch: IntakeBatch,
    dataset_ids: set[str],
    *,
    complete_ids: bool,
    collector: DiagnosticCollector,
) -> dict[str, list[FieldDefinition]]:
    """Keep ordered fields and locate duplicate keys and invalid semantic references."""
    fields: dict[str, list[FieldDefinition]] = defaultdict(list)
    seen: set[tuple[str, str, str]] = set()
    for row in batch.fields:
        if row.dataset_id not in dataset_ids:
            collector.add(
                located_error(
                    row.location,
                    code="UNRESOLVED_REFERENCE",
                    expected="dataset_reference",
                )
                if complete_ids
                else unperformed_references(row.location)
            )
            continue
        key = row.dataset_id, row.object_name, row.field_name
        if key in seen:
            collector.add(located_error(row.location, expected="detail_group"))
        seen.add(key)
        values = row.model_dump(
            exclude_none=True, exclude={"location", "dataset_id", "semantic_reference"}
        )
        if row.semantic_reference is not None:
            values["semantic_references"] = [row.semantic_reference]
        try:
            fields[row.dataset_id].append(FieldDefinition.model_validate(values))
        except ValidationError:
            collector.add(located_error(row.location, expected="reference"))
    return fields


def normalize_batch(batch: IntakeBatch) -> NormalizedBatch:
    """Validate all independent records and report orphan/invalid detail groups."""
    collector = DiagnosticCollector()
    for diagnostic in batch.diagnostics:
        collector.add(diagnostic)
    collector.has_errors |= batch.has_errors
    complete_ids = not any(
        item.severity == "error" and item.sheet in {None, "Datasets"}
        for item in batch.diagnostics
    )
    dataset_ids = {row.id for row in batch.datasets if row.id is not None}
    details: dict[str, list[DetailRow]] = defaultdict(list)
    for detail in batch.details:
        if detail.dataset_id not in dataset_ids:
            collector.add(
                located_error(
                    detail.location,
                    code="UNRESOLVED_REFERENCE",
                    expected="dataset_reference",
                )
                if complete_ids
                else unperformed_references(detail.location)
            )
        else:
            details[detail.dataset_id].append(detail)
    fields = convert_fields(
        batch, dataset_ids, complete_ids=complete_ids, collector=collector
    )
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
