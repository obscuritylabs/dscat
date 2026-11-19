# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Canonical duplicate/reference validation and independent local assessments."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError

from dscat.intake.limits import DiagnosticCollector
from dscat.intake.normalize import LocatedRecord, located_error, unperformed_references
from dscat.models.base import StrictModel
from dscat.models.catalog import Catalog, KnownCapacity
from dscat.models.diagnostics import (
    CheckState,
    CompletenessResult,
    Diagnostic,
    RuleResult,
    TargetReadiness,
    ValidationAssessment,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dscat.models.configuration import AssessmentConfiguration, LocalRule
    from dscat.models.intake import SourceLocation


class ValidatedCatalog(StrictModel):
    """An optional wholly valid aggregate and separately derived assessment."""

    catalog: Catalog | None = None
    diagnostics: list[Diagnostic]
    assessment: ValidationAssessment
    valid_records: int


@dataclass(frozen=True)
class Missing:
    """An absent schema field, never a supplied canonical null value."""


@dataclass(frozen=True)
class UnknownValue:
    """A requested fact omitted inside an explicitly unknown observation."""


MISSING = Missing()
UNKNOWN = UnknownValue()


def scalar_value(value: object) -> object:
    """Use canonical scalar encodings for dates and timezone-aware timestamps."""
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    return value


def field_values(value: object, components: Sequence[str]) -> list[object]:
    """Traverse only schema-validated model attributes and explicit collections."""
    if value is None or isinstance(value, Missing):
        return [MISSING]
    if isinstance(value, list):
        return [
            item for child in value for item in field_values(child, components)
        ] or [MISSING]
    if not components:
        return [scalar_value(value)]
    if not isinstance(value, BaseModel):
        return [MISSING]
    child = getattr(value, components[0], MISSING)
    if isinstance(child, Missing) and getattr(value, "state", None) == "unknown":
        return [UNKNOWN]
    return field_values(child, components[1:])


def completeness(catalog: Catalog, path: str) -> CompletenessResult:
    """Report catalog-wide presence, retaining explicit unknown and absent states."""
    values = [
        item
        for record in catalog.datasets
        for item in field_values(record, path.split("."))
    ]
    if not values or any(isinstance(item, Missing) for item in values):
        state = "absent"
    elif any(
        (isinstance(item, BaseModel) and getattr(item, "state", None) == "unknown")
        or isinstance(item, UnknownValue)
        or (
            item == "unknown"
            and path.rsplit(".", 1)[-1] in {"state", "hold_state", "review_state"}
        )
        for item in values
    ):
        state = "unknown"
    else:
        state = "present"
    return CompletenessResult(path=path, state=state)


def rule_state(catalog: Catalog, rule: LocalRule) -> CheckState:
    """Apply pure exact-type scalar comparisons without expressions or coercion."""
    if not catalog.datasets:
        return "unperformed"
    values = [
        item
        for record in catalog.datasets
        for item in field_values(record, rule.path.split("."))
    ]
    missing = any(isinstance(value, Missing | UnknownValue) for value in values)
    if rule.operator == "present":
        return "does_not_conform" if missing else "conforms"
    if missing:
        return "unperformed"
    operands = [rule.operand] if rule.operator == "equals" else rule.operands or []
    matches = all(
        any(type(value) is type(operand) and value == operand for operand in operands)
        for value in values
    )
    return "conforms" if matches else "does_not_conform"


def assess(
    catalog: Catalog | None,
    configuration: AssessmentConfiguration,
    *,
    invalid: bool = False,
) -> ValidationAssessment:
    """Keep intake, completeness and declared conformity independent of authority."""
    return ValidationAssessment(
        validity="invalid"
        if invalid
        else "valid"
        if catalog is not None
        else "unexamined",
        completeness=[]
        if catalog is None
        else [completeness(catalog, path) for path in configuration.completeness],
        rules=[
            RuleResult(
                rule_id=rule.id,
                severity=rule.severity,
                state="unperformed" if catalog is None else rule_state(catalog, rule),
            )
            for rule in configuration.rules
        ],
        targets=[
            TargetReadiness(target=target, state="unexamined")
            for target in ("dcat-us-3", "odcs-3.2")
        ],
    )


def deduplicate(
    records: Sequence[LocatedRecord], collector: DiagnosticCollector
) -> list[LocatedRecord]:
    """Compare all normalized supported facts, excluding private source associations."""
    unique: dict[str, LocatedRecord] = {}
    for item in records:
        previous = unique.get(item.record.id)
        if previous is None:
            unique[item.record.id] = item
        else:
            identical = previous.record == item.record
            collector.add(
                Diagnostic(
                    code="DUPLICATE_IDENTICAL" if identical else "DUPLICATE_CONFLICT",
                    severity="info" if identical else "error",
                    message_key="review_scope",
                    source_token=item.location.source_token,
                    related_source_token=previous.location.source_token,
                    sheet=item.location.sheet,
                    row=item.location.row,
                )
            )
    return [unique[key] for key in sorted(unique)]


def validate_references(
    records: list[LocatedRecord], collector: DiagnosticCollector
) -> None:
    """Resolve local dataset and party identities without online dereferencing."""
    ids = {item.record.id for item in records}
    parties: dict[str, tuple[SourceLocation, dict[str, object]]] = {}
    for item in records:
        for service in item.record.services or []:
            for reference in service.served_datasets or []:
                if reference.reference_kind == "local" and reference.id not in ids:
                    collector.add(
                        located_error(
                            item.location,
                            code="UNRESOLVED_REFERENCE",
                            expected="service_reference",
                        )
                    )
        for role in item.record.roles or []:
            if role.reference_kind != "local":
                continue
            facts = role.model_dump(
                exclude_none=True, exclude={"reference_kind", "party_id", "role"}
            )
            previous = parties.get(role.party_id)
            if previous is not None:
                previous_location, prior = previous
                if any(
                    key in prior and prior[key] != value for key, value in facts.items()
                ):
                    collector.add(
                        located_error(
                            item.location, code="UNRESOLVED_REFERENCE"
                        ).model_copy(
                            update={
                                "related_source_token": previous_location.source_token
                            }
                        )
                    )
                else:
                    prior.update(facts)
            else:
                parties[role.party_id] = item.location, facts


def informative_assessments(
    records: list[LocatedRecord], collector: DiagnosticCollector
) -> None:
    """Describe incomparable rates and retained conflicts without enforcement."""
    for item in records:
        averages = [
            value
            for value in item.record.capacity or []
            if isinstance(value, KnownCapacity) and value.kind == "average_ingestion"
        ]
        peaks = [
            value
            for value in item.record.capacity or []
            if isinstance(value, KnownCapacity) and value.kind == "peak_ingestion"
        ]
        if any(
            (average.basis, average.window_start, average.window_end)
            != (peak.basis, peak.window_start, peak.window_end)
            for average in averages
            for peak in peaks
        ):
            collector.add(
                Diagnostic(
                    code="INCOMPARABLE_CAPACITY",
                    severity="info",
                    message_key="review_scope",
                    source_token=item.location.source_token,
                    sheet=item.location.sheet,
                    row=item.location.row,
                    check_state="unperformed",
                )
            )
        if item.record.records is not None and bool(item.record.records.conflicts):
            collector.add(
                Diagnostic(
                    code="RECORDS_CONFLICT",
                    severity="warning",
                    message_key="review_scope",
                    source_token=item.location.source_token,
                    sheet=item.location.sheet,
                    row=item.location.row,
                )
            )


def validate_catalog(
    records: Sequence[LocatedRecord],
    configuration: AssessmentConfiguration,
    diagnostics: Sequence[Diagnostic] = (),
    *,
    invalid: bool = False,
) -> ValidatedCatalog:
    """Accumulate independent failures before accepting any complete catalog."""
    collector = DiagnosticCollector()
    for diagnostic in diagnostics:
        collector.add(diagnostic)
    collector.has_errors |= invalid
    unique = deduplicate(records, collector)
    if collector.has_errors:
        collector.add(unperformed_references())
    else:
        validate_references(unique, collector)
    informative_assessments(unique, collector)
    catalog = None
    if not collector.has_errors:
        try:
            catalog = Catalog(
                schema_version="1.0", datasets=[item.record for item in unique]
            )
        except ValidationError:
            # Explicit reference checks identify actionable failures before this fence.
            collector.add(
                Diagnostic(
                    code="INVALID_METADATA",
                    severity="error",
                    message_key="correct_metadata",
                )
            )
    fields: dict[str, object] = {
        "diagnostics": collector.items,
        "assessment": assess(catalog, configuration, invalid=collector.has_errors),
        "valid_records": len(unique),
    }
    if catalog is not None:
        fields["catalog"] = catalog
    return ValidatedCatalog.model_validate(fields)
