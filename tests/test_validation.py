# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Canonical identity, cross-record references and independent assessments."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Self

import pytest
from pydantic import ValidationError, model_validator

from dscat.intake.normalize import LocatedRecord
from dscat.models.catalog import Catalog, DatasetRecord
from dscat.models.configuration import AssessmentConfiguration, LocalRule
from dscat.models.intake import SourceLocation
from dscat.validation import (
    assess,
    completeness,
    rule_state,
    scalar_value,
    validate_catalog,
)

FIXTURES = Path(__file__).parent / "fixtures/contracts"


def minimum() -> DatasetRecord:
    """Use the independently frozen minimal canonical fixture."""
    return DatasetRecord.model_validate_json((FIXTURES / "minimum.json").read_bytes())


def located(record: DatasetRecord, token: int = 1) -> LocatedRecord:
    """Associate an explicit source ordinal outside canonical facts."""
    return LocatedRecord(
        record=record,
        location=SourceLocation(source_token=token, sheet="Datasets", row=2),
    )


def test_identical_normalized_records_deduplicate_with_both_sources() -> None:
    """Canonical payload comparison excludes source locations and retains references."""
    record = minimum()
    result = validate_catalog(
        [located(record), located(record, 2)], AssessmentConfiguration()
    )
    assert result.catalog is not None
    assert result.catalog.datasets == [record]
    assert result.diagnostics[0].code == "DUPLICATE_IDENTICAL"
    assert (
        result.diagnostics[0].source_token == located(record, 2).location.source_token
    )
    assert result.diagnostics[0].related_source_token == 1
    assert result.assessment.validity == "valid"


@pytest.mark.parametrize(
    "difference",
    [
        {"description": "Different"},
        {"dataset_version": "2"},
        {"capacity_retention": {"state": "unknown"}},
    ],
)
def test_conflicting_payload_withholds_the_whole_catalog(
    difference: dict[str, object],
) -> None:
    """Any normalized supported fact distinguishes a conflicting submission."""
    record = minimum()
    changed = DatasetRecord.model_validate(
        record.model_dump(exclude_none=True) | difference
    )
    result = validate_catalog(
        [located(record), located(changed, 2)], AssessmentConfiguration()
    )
    assert result.catalog is None
    assert result.assessment.validity == "invalid"
    assert result.diagnostics[0].code == "DUPLICATE_CONFLICT"
    assert result.diagnostics[0].related_source_token == 1


def test_case_sensitive_ids_and_empty_directory_catalog() -> None:
    """Different case remains a distinct business identity; no records is valid."""
    original = minimum()
    changed = DatasetRecord.model_validate(
        original.model_dump(exclude_none=True) | {"id": original.id.upper()}
    )
    result = validate_catalog(
        [located(original), located(changed, 2)], AssessmentConfiguration()
    )
    assert result.catalog is not None
    assert len(result.catalog.datasets) == len([original, changed])
    empty = validate_catalog([], AssessmentConfiguration())
    assert empty.catalog is not None
    assert empty.catalog.datasets == []
    assert all(target.state == "unexamined" for target in empty.assessment.targets)


def test_local_service_links_resolve_across_workbooks_and_external_stays_inert() -> (
    None
):
    """Reference resolution uses the complete catalog and never fetches external IDs."""
    record = minimum()
    service = {
        "id": "service",
        "served_datasets": [
            {"reference_kind": "local", "id": "other"},
            {"reference_kind": "external", "id": "urn:example:external"},
        ],
    }
    first = DatasetRecord.model_validate(
        record.model_dump(exclude_none=True) | {"services": [service]}
    )
    missing = validate_catalog([located(first)], AssessmentConfiguration())
    assert missing.catalog is None
    assert missing.diagnostics[0].code == "UNRESOLVED_REFERENCE"
    second = DatasetRecord.model_validate(
        record.model_dump(exclude_none=True) | {"id": "other"}
    )
    complete = validate_catalog(
        [located(first), located(second, 2)], AssessmentConfiguration()
    )
    assert complete.catalog is not None
    assert not complete.diagnostics


def test_local_party_definitions_are_consistent_without_merging_facts() -> None:
    """Local identity resolves uniquely; absent optional facts remain absent."""
    record = minimum()
    role = {
        "reference_kind": "local",
        "party_id": "support",
        "role": "contact",
        "label": "Metadata support",
    }
    first = DatasetRecord.model_validate(
        record.model_dump(exclude_none=True) | {"roles": [role]}
    )
    second = DatasetRecord.model_validate(
        record.model_dump(exclude_none=True)
        | {"id": "other", "roles": [role | {"email": "metadata@example.org"}]}
    )
    result = validate_catalog(
        [located(first), located(second, 2)], AssessmentConfiguration()
    )
    assert result.catalog is not None
    assert result.catalog.datasets[0].roles is not None
    assert result.catalog.datasets[0].roles[0].email is None
    conflict = DatasetRecord.model_validate(
        second.model_dump(exclude_none=True)
        | {"roles": [role | {"label": "Different"}]}
    )
    invalid = validate_catalog(
        [located(first), located(conflict, 2)], AssessmentConfiguration()
    )
    assert invalid.catalog is None
    assert invalid.diagnostics[0].related_source_token == 1


def test_completeness_separates_absent_unknown_zero_and_plain_text() -> None:
    """An ordinary string saying unknown remains present text."""
    record = DatasetRecord.model_validate(
        minimum().model_dump(exclude_none=True)
        | {
            "description": "unknown",
            "capacity": [{"kind": "size", "state": "unknown"}],
            "capacity_retention": {"state": "known", "days": 0},
        }
    )
    catalog = Catalog(schema_version="1.0", datasets=[record])
    assert completeness(catalog, "description").state == "present"
    assert completeness(catalog, "core_party.email").state == "absent"
    assert completeness(catalog, "capacity").state == "unknown"
    assert completeness(catalog, "capacity.normalized_bytes").state == "unknown"
    assert completeness(catalog, "capacity_retention.days").state == "present"
    assert (
        completeness(Catalog(schema_version="1.0", datasets=[]), "title").state
        == "absent"
    )


@pytest.mark.parametrize(
    ("operator", "operand", "expected"),
    [
        ("present", None, "conforms"),
        ("equals", "Synthetic measurements", "conforms"),
        ("equals", "Other", "does_not_conform"),
        ("equals", True, "does_not_conform"),
        ("one_of", ["Other", "Synthetic measurements"], "conforms"),
        ("one_of", ["Other"], "does_not_conform"),
    ],
)
def test_rules_are_pure_scalar_comparisons(
    operator: str, operand: object, expected: str
) -> None:
    """Local declared conformity does not alter structural validity or authority."""
    fields: dict[str, object] = {"id": "local", "path": "title", "operator": operator}
    if operator == "equals":
        fields["operand"] = operand
    elif operator == "one_of":
        fields["operands"] = operand
    rule = LocalRule.model_validate(fields)
    catalog = Catalog(schema_version="1.0", datasets=[minimum()])
    assert rule_state(catalog, rule) == expected
    assessment = assess(catalog, AssessmentConfiguration(rules=[rule]))
    assert assessment.validity == "valid"
    assert assessment.rules[0].state == expected
    assert catalog.datasets[0].publication is None
    assert all(target.state == "unexamined" for target in assessment.targets)


def test_missing_rule_operands_and_unperformed_scope() -> None:
    """No comparable fact or valid catalog cannot become a passed comparison."""
    catalog = Catalog(schema_version="1.0", datasets=[minimum()])
    equals = LocalRule(
        id="email",
        path="core_party.email",
        operator="equals",
        operand="metadata@example.org",
    )
    present = LocalRule(id="present", path="core_party.email", operator="present")
    assert rule_state(catalog, equals) == "unperformed"
    assert rule_state(catalog, present) == "does_not_conform"
    assert (
        rule_state(Catalog(schema_version="1.0", datasets=[]), present) == "unperformed"
    )
    unexamined = assess(None, AssessmentConfiguration(rules=[equals]))
    assert unexamined.validity == "unexamined"
    assert unexamined.rules[0].state == "unperformed"
    invalid = validate_catalog(
        [located(minimum())], AssessmentConfiguration(rules=[equals]), invalid=True
    )
    assert invalid.catalog is None
    assert invalid.assessment.validity == "invalid"
    assert invalid.assessment.rules[0].state == "unperformed"
    assert scalar_value(datetime(2026, 1, 1, tzinfo=UTC)) == "2026-01-01T00:00:00Z"


def test_reference_kind_ties_do_not_make_role_order_depend_on_input_order() -> None:
    """Distinct explicitly tagged party references receive a stable set order."""
    role = {
        "party_id": "urn:example:party",
        "role": "contact",
        "label": "Metadata support",
    }
    roles = [role | {"reference_kind": kind} for kind in ("local", "external")]
    first = DatasetRecord.model_validate(
        minimum().model_dump(exclude_none=True) | {"roles": roles}
    )
    second = DatasetRecord.model_validate(
        minimum().model_dump(exclude_none=True) | {"roles": list(reversed(roles))}
    )
    assert first == second
    result = validate_catalog(
        [located(first), located(second, 2)], AssessmentConfiguration()
    )
    assert result.catalog is not None
    assert result.diagnostics[0].code == "DUPLICATE_IDENTICAL"


def test_scalar_dates_severity_and_known_zero_use_explicit_types() -> None:
    """Date encodings compare canonically, and bool is distinct from integer zero."""
    record = DatasetRecord.model_validate(
        minimum().model_dump(exclude_none=True)
        | {
            "inventory_added": "2026-01-01",
            "capacity_retention": {"state": "known", "days": 0},
        }
    )
    catalog = Catalog(schema_version="1.0", datasets=[record])
    date_rule = LocalRule(
        id="date", path="inventory_added", operator="equals", operand="2026-01-01"
    )
    wrong = LocalRule(
        id="zero",
        path="capacity_retention.days",
        operator="equals",
        operand=False,
        severity="error",
    )
    assert rule_state(catalog, date_rule) == "conforms"
    assert rule_state(catalog, wrong) == "does_not_conform"
    assessment = assess(catalog, AssessmentConfiguration(rules=[date_rule, wrong]))
    assert assessment.validity == "valid"
    assert assessment.rules[-1].severity == "error"
    assert catalog.datasets[0].publication is None


def test_incomparable_rates_and_records_conflicts_remain_descriptive() -> None:
    """A low peak in another basis/window is not an invented comparable measurement."""
    detailed = DatasetRecord.model_validate_json(
        (FIXTURES / "detailed.json").read_bytes()
    )
    data = detailed.model_dump(mode="json", exclude_none=True)
    observations = data["capacity"]
    for observation in observations:
        if observation["kind"] == "peak_ingestion":
            observation.update(
                {"basis": "physical", "value": "1", "normalized_bytes": 1000000}
            )
    record = DatasetRecord.model_validate(data)
    result = validate_catalog([located(record)], AssessmentConfiguration())
    assert result.catalog is not None
    assert {item.code for item in result.diagnostics} == {
        "INCOMPARABLE_CAPACITY",
        "RECORDS_CONFLICT",
    }
    assert all(item.severity != "error" for item in result.diagnostics)
    assert result.catalog.datasets[0].records == detailed.records


def test_assessment_never_evaluates_unknown_objects_or_missing_children() -> None:
    """Only schema models participate in pure path traversal."""
    from dscat.validation import MISSING, field_values  # noqa: PLC0415 -- focused helper acceptance.

    assert field_values("text", ["unsupported"]) == [MISSING]
    assert (
        completeness(
            Catalog(schema_version="1.0", datasets=[minimum()]), "roles.email"
        ).state
        == "absent"
    )
    external = DatasetRecord.model_validate(
        minimum().model_dump(exclude_none=True)
        | {
            "roles": [
                {
                    "reference_kind": "external",
                    "party_id": "urn:example:party",
                    "role": "contact",
                    "label": "Metadata support",
                }
            ]
        }
    )
    assert (
        validate_catalog([located(external)], AssessmentConfiguration()).catalog
        is not None
    )


def test_catalog_object_count_has_the_approved_hard_bound() -> None:
    """Structured catalog input cannot bypass the invocation's100,000 record ceiling."""
    with pytest.raises(ValidationError, match="100000"):
        Catalog(schema_version="1.0", datasets=[minimum()] * 100001)


def test_dependent_references_are_unperformed_for_incomplete_validated_inputs() -> None:
    """An omitted invalid target record does not fabricate a dangling local-ID error."""
    record = DatasetRecord.model_validate(
        minimum().model_dump(exclude_none=True)
        | {
            "services": [
                {
                    "id": "service",
                    "served_datasets": [
                        {"reference_kind": "local", "id": "unexamined-target"}
                    ],
                }
            ]
        }
    )
    result = validate_catalog(
        [located(record)], AssessmentConfiguration(), invalid=True
    )
    assert result.catalog is None
    assert result.assessment.validity == "invalid"
    assert not any(item.code == "UNRESOLVED_REFERENCE" for item in result.diagnostics)
    assert result.diagnostics[0].code == "REFERENCE_CHECK_UNPERFORMED"
    assert result.diagnostics[0].check_state == "unperformed"


def test_output_schema_rejection_withholds_a_partial_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An injected aggregate constraint cannot create a successful partial output."""

    class RejectingCatalog(Catalog):
        """Reject valid facts with a synthetic final aggregate constraint."""

        @model_validator(mode="after")
        def reject(self) -> Self:
            """Reject with synthetic text that must not appear in public diagnostics."""
            msg = "synthetic-sensitive-schema-rejection"
            raise ValueError(msg)

    record = minimum()
    original = record.model_dump_json(exclude_none=True)
    monkeypatch.setattr("dscat.validation.Catalog", RejectingCatalog)
    result = validate_catalog([located(record)], AssessmentConfiguration())
    assert result.catalog is None
    assert result.assessment.validity == "invalid"
    assert "sensitive-schema" not in result.model_dump_json()
    assert record.model_dump_json(exclude_none=True) == original
