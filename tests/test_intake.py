# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Real XLSX row/header/formula boundaries and canonical property conversion."""

import io
import re
import sys
import zipfile
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from openpyxl import Workbook
from openpyxl.workbook.defined_name import DefinedName
from typer.testing import CliRunner

from dscat.cli import app
from dscat.intake.archive import read_archive
from dscat.intake.limits import Budget, IntakeError
from dscat.intake.normalize import normalize_batch
from dscat.models.catalog import DatasetRecord
from dscat.models.diagnostics import CommandResult
from dscat.workbook.generate import (
    create_template,
    write_text,
)
from dscat.workbook.layout import DATASET_HEADERS, DETAIL_HEADERS, FIELD_HEADERS
from dscat.workbook.parse import parse_workbook

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from dscat.models.intake import IntakeBatch

CORE = {
    "id": "asset-001",
    "title": "Synthetic measurements",
    "description": "Synthetic metadata.",
    "core_party": "Metadata support",
}
FIXTURES = Path(__file__).parent / "fixtures"


@dataclass(frozen=True)
class WorkbookOptions:
    """Control only the shape of explicitly test-owned synthetic fixtures."""

    optional: bool = True
    extra_sheet: str | None = None
    extra_headers: tuple[str, ...] = ()


DEFAULT_OPTIONS = WorkbookOptions()


def add_extra_sheet(book: Workbook, options: WorkbookOptions) -> None:
    """Add a deliberately unrelated or unsupported-semantic test worksheet."""
    if options.extra_sheet is not None:
        sheet = book.create_sheet(options.extra_sheet)
        for column, label in enumerate(options.extra_headers, 1):
            write_text(sheet.cell(1, column), label)


def workbook_bytes(
    datasets: Sequence[Mapping[str, str]],
    *,
    fields: Sequence[Mapping[str, str]] = (),
    details: Sequence[Mapping[str, str]] = (),
    headers: Sequence[str] = DATASET_HEADERS,
    options: WorkbookOptions = DEFAULT_OPTIONS,
) -> bytes:
    """Generate only test-owned workbook input with explicit literal text cells."""
    book = Workbook()
    instructions = book.active
    instructions.title = "Instructions"
    write_text(instructions["B2"], "1.0")
    write_text(instructions["B3"], "dataset-intake")
    for name, coordinate in (
        ("dscat_workbook_schema", "B2"),
        ("dscat_workbook_kind", "B3"),
    ):
        book.defined_names.add(
            DefinedName(
                name, attr_text=f"'Instructions'!${coordinate[0]}${coordinate[1:]}"
            )
        )
    for name, columns, rows in (
        ("Datasets", headers, datasets),
        ("Fields", FIELD_HEADERS, fields),
        ("Details_Quality", DETAIL_HEADERS, details),
    ):
        if name != "Datasets" and not options.optional:
            continue
        sheet = book.create_sheet(name)
        for column, label in enumerate(columns, 1):
            write_text(sheet.cell(1, column), label)
        for row_number, row in enumerate(rows, 2):
            for column, label in enumerate(columns, 1):
                if label in row:
                    write_text(sheet.cell(row_number, column), row[label])
    add_extra_sheet(book, options)
    raw = io.BytesIO()
    book.save(raw)
    output = io.BytesIO()
    with (
        zipfile.ZipFile(raw) as source,
        zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as target,
    ):
        for name in source.namelist():
            content = source.read(name)
            if name == "xl/_rels/workbook.xml.rels":
                content = content.replace(
                    b'Target="/xl/worksheets/', b'Target="worksheets/'
                )
            target.writestr(name, content)
    return output.getvalue()


def batch_from(raw: bytes) -> IntakeBatch:
    """Apply real preflight before the semantic reader in test acceptance."""
    return parse_workbook(read_archive(raw, Budget()), 1, Budget())


def modify_part(raw: bytes, name: str, before: bytes, after: bytes) -> bytes:
    """Mutate one test-owned package part and rebuild CRC/size metadata."""
    output = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(raw)) as source,
        zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as target,
    ):
        for member in source.namelist():
            content = source.read(member)
            if member == name:
                assert before in content
                content = content.replace(before, after, 1)
            target.writestr(member, content)
    return output.getvalue()


def test_minimum_reordered_headers_and_inert_text() -> None:
    """Four-field intake stays valid and formula-looking string content stays text."""
    core = CORE | {"description": "=1+1"}
    result = normalize_batch(
        batch_from(workbook_bytes([core], headers=list(reversed(DATASET_HEADERS))))
    )
    assert not result.has_errors
    assert result.records[0].record.description == "=1+1"
    assert result.records[0].record.roles is None
    assert result.records[0].record.core_party.role == "unspecified_contact_or_owner"


def test_oldest_template_and_current_generator_parse() -> None:
    """Oldest schema1.0 and current authored feedback remain readable."""
    oldest = (FIXTURES / "workbook-1.0/template.xlsx").read_bytes()
    parsed = batch_from(oldest)
    assert not parsed.has_errors
    assert parsed.datasets == []
    assert parsed.fields == []
    assert parsed.details == []
    current = batch_from(create_template().content)
    assert current == parsed


@pytest.mark.parametrize("changed", ["duplicate", "missing", "unknown", "empty"])
def test_header_contract_rejects_ambiguous_or_unsupported_names(changed: str) -> None:
    """Exact supported header keys, rather than column positions, govern input."""
    headers = list(DATASET_HEADERS)
    if changed == "duplicate":
        headers[-1] = "id"
    elif changed == "missing":
        headers.remove("title")
    elif changed == "unknown":
        headers.append("synthetic-sensitive-header")
    else:
        headers = []
    result = batch_from(workbook_bytes([CORE], headers=headers))
    assert result.has_errors
    assert result.diagnostics[0].row == 1
    assert "sensitive-header" not in result.model_dump_json()


@pytest.mark.parametrize("cache", [b"", b"42"])
def test_input_formula_is_rejected_even_with_plausible_cache(cache: bytes) -> None:
    """Formula metadata never becomes an imported scalar or a successful empty row."""
    raw = workbook_bytes([CORE])
    raw = modify_part(
        raw,
        "xl/worksheets/sheet2.xml",
        b'<c r="C2" t="inlineStr"><is><t>Synthetic metadata.</t></is></c>',
        b'<c r="C2"><f>1+1</f><v>' + cache + b"</v></c>",
    )
    batch = batch_from(raw)
    assert batch.has_errors
    assert batch.datasets == []
    assert batch.diagnostics[0].column == DATASET_HEADERS.index("description") + 1


@pytest.mark.parametrize(
    ("before", "after", "code"),
    [
        (b"'Instructions'!$B$2", b"'Instructions'!$B$4", "INVALID_WORKBOOK"),
        (b'name="dscat_workbook_schema"', b'name="different"', "INVALID_WORKBOOK"),
        (
            b'name="Instructions"',
            b'name="Instructions" state="hidden"',
            "INVALID_WORKBOOK",
        ),
    ],
)
def test_named_metadata_coordinates_are_binding(
    before: bytes, after: bytes, code: str
) -> None:
    """Names and visible marker coordinates cannot be substituted."""
    raw = workbook_bytes([CORE])
    # openpyxl already supplies state=visible; replace it for the hidden case.
    if after.endswith(b'state="hidden"'):
        before += b' sheetId="1" state="visible"'
        after = b'name="Instructions" sheetId="1" state="hidden"'
    raw = modify_part(raw, "xl/workbook.xml", before, after)
    with pytest.raises(IntakeError, match=code):
        batch_from(raw)


def test_future_schema_and_wrong_kind() -> None:
    """Unknown schema versions and conflicting kind markers are explicit failures."""
    raw = workbook_bytes([CORE])
    future = modify_part(raw, "xl/worksheets/sheet1.xml", b">1.0<", b">2.0<")
    with pytest.raises(IntakeError, match="UNSUPPORTED_VERSION"):
        batch_from(future)
    wrong = modify_part(
        raw, "xl/worksheets/sheet1.xml", b">dataset-intake<", b">other<"
    )
    with pytest.raises(IntakeError, match="INVALID_WORKBOOK"):
        batch_from(wrong)


@pytest.mark.parametrize("nullable", ["Yes", "No", "TRUE", "1"])
def test_workbook_boolean_encoding_is_explicit(nullable: str) -> None:
    """Only controlled Yes/No cells become canonical booleans."""
    fields = [
        {
            "dataset_id": "asset-001",
            "object_name": "measurements",
            "field_name": "reading",
            "type": "number",
            "nullable": nullable,
        }
    ]
    result = normalize_batch(batch_from(workbook_bytes([CORE], fields=fields)))
    if nullable in {"Yes", "No"}:
        assert not result.has_errors
        assert result.records[0].record.fields is not None
        assert result.records[0].record.fields[0].nullable is (nullable == "Yes")
    else:
        assert result.has_errors


def add_detail_rows(
    output: list[dict[str, str]],
    dataset_id: str,
    section: str,
    entry: str,
    values: Mapping[str, object],
) -> None:
    """Represent explicit fixture facts as independent scalar worksheet rows."""
    for key, value in values.items():
        output.append(
            {
                "dataset_id": dataset_id,
                "section": section,
                "entry_id": entry,
                "property": key,
                "value": str(value),
            }
        )


def consumer_detail_rows(
    dataset_id: str, values: Mapping[str, list[str]]
) -> list[dict[str, str]]:
    """Encode separately supplied consumer strings without delimiter parsing."""
    output: list[dict[str, str]] = []
    add = partial(add_detail_rows, output, dataset_id)
    for key, items in values.items():
        prop = {
            "intended_uses": "intended_use",
            "limitations": "limitation",
            "access_instructions": "access_instruction",
            "provenance": "provenance",
            "semantic_references": "semantic_reference",
        }[key]
        for index, value in enumerate(items):
            add("consumer", f"{prop}-{index}", {prop: value})
    return output


def detailed_rows(record: DatasetRecord) -> list[dict[str, str]]:
    """Encode the independently frozen canonical fixture as explicit grouped facts."""
    result: list[dict[str, str]] = []

    add = partial(add_detail_rows, result, record.id)

    data = record.model_dump(mode="json", exclude_none=True)
    add(
        "identity",
        "dataset",
        {
            key: data[key]
            for key in (
                "dataset_version",
                "contract_id",
                "contract_version",
                "product_reference",
            )
        },
    )
    add(
        "dates",
        "dataset",
        {
            key: data[key]
            for key in (
                "inventory_added",
                "metadata_reviewed",
                "dataset_modified",
                "update_frequency",
            )
        },
    )
    for section in (
        "domain",
        "access_determination",
        "disclosure_determination",
        "metadata_review",
        "capacity_retention",
    ):
        add(section, "dataset", data[section])
    for section, collection in (("role", "roles"), ("distribution", "distributions")):
        for index, value in enumerate(data[collection]):
            add(section, f"entry-{index}", value)
    for service in data["services"]:
        add(
            "service",
            "service-entry",
            {key: value for key, value in service.items() if key != "served_datasets"},
        )
        for index, reference in enumerate(service["served_datasets"]):
            add(
                "service_dataset",
                f"link-{index}",
                {
                    "service_id": service["id"],
                    "dataset_id": reference["id"],
                    "reference_kind": reference["reference_kind"],
                },
            )
    result.extend(consumer_detail_rows(record.id, data["consumer"]))
    for value in data["commitments"]:
        add(
            "commitment",
            value["id"],
            {key: fact for key, fact in value.items() if key != "id"},
        )
    add("publication", "state", {"state": data["publication"]["state"]})
    for index, value in enumerate(data["publication"]["approvals"]):
        add("publication", f"approval-{index}", value)
    add(
        "records",
        "dataset",
        {key: value for key, value in data["records"].items() if key != "conflicts"},
    )
    for index, value in enumerate(data["records"]["conflicts"]):
        add("records", f"conflict-{index}", {"conflict": value})
    for index, value in enumerate(data["capacity"]):
        add(
            "capacity",
            f"observation-{index}",
            {key: fact for key, fact in value.items() if key != "normalized_bytes"},
        )
    return result


def test_every_detailed_fact_survives_property_specific_conversion() -> None:
    """The independent full fixture survives actual workbook parsing without loss."""
    expected = DatasetRecord.model_validate_json(
        (FIXTURES / "contracts/detailed.json").read_bytes()
    )
    rows = detailed_rows(expected)
    fields = []
    for item in expected.fields or []:
        row = {
            "dataset_id": expected.id,
            "object_name": item.object_name,
            "field_name": item.field_name,
            "type": item.type,
        }
        if item.description is not None:
            row["description"] = item.description
        if item.nullable is not None:
            row["nullable"] = "Yes" if item.nullable else "No"
        if item.semantic_references is not None:
            row["semantic_reference"] = item.semantic_references[0]
        fields.append(row)
    result = normalize_batch(
        batch_from(workbook_bytes([CORE], fields=fields, details=list(reversed(rows))))
    )
    assert not result.has_errors, result.model_dump_json()
    assert result.records[0].record == expected
    assert (
        DatasetRecord.model_validate_json(
            result.records[0].record.model_dump_json(exclude_none=True)
        )
        == expected
    )


@pytest.mark.skipif(
    sys.platform != "linux", reason="Requires actual native Linux memory guard."
)
def test_real_guarded_linux_cli_validation(tmp_path: Path) -> None:
    """Use the actual guarded command workflow with a synthetic four-field workbook."""
    source = tmp_path / "synthetic.xlsx"
    source.write_bytes(workbook_bytes([CORE]))
    result = CliRunner().invoke(app, ["validate", str(source), "--format", "json"])
    assert result.exit_code == 0, result.stdout
    output = CommandResult.model_validate_json(result.stdout)
    assert output.summary.valid_records == 1
    assert output.assessment is not None
    assert output.assessment.validity == "valid"
    assert output.assessment.targets[0].target == "dcat-us-3"
    assert output.assessment.targets[0].state == "blocked"
    assert output.assessment.targets[0].reasons == [
        "target_contact_missing",
        "target_unrepresentable",
    ]
    assert output.assessment.targets[1].target == "odcs-3.2"
    assert output.assessment.targets[1].state == "unexamined"
    future = modify_part(
        source.read_bytes(), "xl/worksheets/sheet1.xml", b">1.0<", b">9.0<"
    )
    source.write_bytes(future)
    unsupported = CliRunner().invoke(app, ["validate", str(source), "--format", "json"])
    invocation_error = 2
    assert unsupported.exit_code == invocation_error, unsupported.stdout
    report = CommandResult.model_validate_json(unsupported.stdout)
    assert report.exit_code == invocation_error
    assert report.diagnostics[0].code == "UNSUPPORTED_VERSION"


@pytest.mark.parametrize(
    ("column", "role"),
    [
        ("owner", "accountable_owner"),
        ("steward", "steward"),
        ("maintainer", "maintainer"),
    ],
)
def test_explicit_role_references_import_once(column: str, role: str) -> None:
    """Role columns check explicit group identities without inventing parties."""
    rows = [
        {
            "dataset_id": "asset-001",
            "section": "role",
            "entry_id": "role-entry",
            "property": key,
            "value": value,
        }
        for key, value in {
            "reference_kind": "local",
            "party_id": "support",
            "role": role,
            "label": "Metadata support",
        }.items()
    ]
    result = normalize_batch(
        batch_from(workbook_bytes([CORE | {column: "role-entry"}], details=rows))
    )
    assert not result.has_errors
    assert result.records[0].record.roles is not None
    assert len(result.records[0].record.roles) == 1
    assert result.records[0].record.roles[0].party_id == "support"
    assert result.records[0].record.roles[0].role == role


@pytest.mark.parametrize("reference", ["missing", "Metadata support", "\trole-entry"])
def test_role_labels_and_dangling_or_invalid_group_ids_are_rejected(
    reference: str,
) -> None:
    """No fallback treats role-cell text as a supplied party identity or label."""
    result = normalize_batch(batch_from(workbook_bytes([CORE | {"owner": reference}])))
    assert result.has_errors
    assert result.records == []


def test_wrong_role_group_and_orphan_optional_rows() -> None:
    """References must match the declared role and a dataset in the same workbook."""
    rows = [
        {
            "dataset_id": "asset-001",
            "section": "role",
            "entry_id": "role-entry",
            "property": key,
            "value": value,
        }
        for key, value in {
            "reference_kind": "external",
            "party_id": "urn:example:support",
            "role": "contact",
            "label": "Metadata support",
        }.items()
    ]
    wrong = normalize_batch(
        batch_from(workbook_bytes([CORE | {"owner": "role-entry"}], details=rows))
    )
    assert wrong.has_errors
    assert wrong.diagnostics[-1].code == "UNRESOLVED_REFERENCE"
    orphan = normalize_batch(batch_from(workbook_bytes([], details=rows)))
    assert orphan.has_errors
    assert all(item.code == "UNRESOLVED_REFERENCE" for item in orphan.diagnostics)
    supplied = normalize_batch(batch_from(workbook_bytes([CORE], details=rows)))
    assert not supplied.has_errors
    assert supplied.records[0].record.roles is not None
    assert supplied.records[0].record.roles[0].reference_kind == "external"


def property_rows(
    section: str, values: Mapping[str, str], *, entry: str = "dataset"
) -> list[dict[str, str]]:
    """Supply explicit scalar facts without inferring object or list encodings."""
    return [
        {
            "dataset_id": "asset-001",
            "section": section,
            "entry_id": entry,
            "property": key,
            "value": value,
        }
        for key, value in values.items()
    ]


@pytest.mark.parametrize(
    ("section", "entry", "values"),
    [
        ("domain", "dataset", {"id": "bad/id"}),
        ("capacity", "observation", {"kind": "size", "state": "known", "value": "1"}),
        ("capacity", "observation", {"kind": "size", "state": "unknown", "unit": "MB"}),
        (
            "capacity",
            "observation",
            {
                "kind": "size",
                "state": "known",
                "value": "NaN",
                "unit": "MB",
                "basis": "logical",
                "measured_on": "2026-01-01",
            },
        ),
        ("capacity_retention", "dataset", {"state": "known", "days": "-1"}),
        ("capacity_retention", "dataset", {"state": "known", "days": "2147483648"}),
        ("capacity_retention", "dataset", {"state": "known", "days": "1.5"}),
        ("capacity_retention", "dataset", {"state": "known", "days": "1 month"}),
        ("records", "dataset", {"duration_days": "99999999999999999999999"}),
        ("role", "role-entry", {"role": "contact", "label": "Metadata support"}),
        ("distribution", "distribution-entry", {"id": "bad/id"}),
        ("commitment", "commitment-entry", {"kind": "quality", "subject": "reading"}),
        ("service", "service-entry", {"title": "Synthetic service"}),
        (
            "service_dataset",
            "link",
            {"dataset_id": "asset-001", "reference_kind": "local"},
        ),
        (
            "service_dataset",
            "link",
            {
                "service_id": "missing",
                "dataset_id": "asset-001",
                "reference_kind": "local",
            },
        ),
        ("consumer", "consumer-entry", {"semantic_reference": "javascript:synthetic"}),
        (
            "metadata_review",
            "dataset",
            {"state": "approved", "reviewed_on": "2026-02-30"},
        ),
        (
            "publication",
            "approval",
            {"state": "approved", "authority": "Synthetic authority"},
        ),
        ("publication", "state", {"state": "unsupported"}),
    ],
)
def test_grouped_fact_failures_do_not_create_partial_canonical_records(
    section: str, entry: str, values: dict[str, str]
) -> None:
    """Invalid structured details fail while retaining safe source locations."""
    result = normalize_batch(
        batch_from(
            workbook_bytes([CORE], details=property_rows(section, values, entry=entry))
        )
    )
    assert result.has_errors
    assert result.records == []
    assert all(item.source_token == 1 for item in result.diagnostics)


@pytest.mark.parametrize("value", ["0", "000000000000000000000000", "2147483647"])
def test_retention_days_preserve_zero_and_maximum(value: str) -> None:
    """Whole days use numeric magnitude, with no calendar or deletion inference."""
    result = normalize_batch(
        batch_from(
            workbook_bytes(
                [CORE],
                details=property_rows(
                    "capacity_retention", {"state": "known", "days": value}
                ),
            )
        )
    )
    assert not result.has_errors
    retention = result.records[0].record.capacity_retention
    assert retention is not None
    assert retention.state == "known"
    assert retention.days == int(value)
    assert result.records[0].record.records is None


def test_unknown_quantity_and_known_zero_are_independent() -> None:
    """The workbook spelling Unknown creates a tagged quantity without defaults."""
    unknown = property_rows(
        "capacity", {"kind": "size", "state": "Unknown"}, entry="unknown"
    )
    zero = property_rows(
        "capacity",
        {
            "kind": "average_ingestion",
            "state": "known",
            "value": "0",
            "unit": "KiB",
            "basis": "physical",
            "measured_on": "2026-01-01",
            "window_start": "2026-01-01T00:00:00Z",
            "window_end": "2026-01-02T00:00:00Z",
        },
        entry="known",
    )
    result = normalize_batch(batch_from(workbook_bytes([CORE], details=unknown + zero)))
    assert not result.has_errors
    observations = result.records[0].record.capacity
    assert observations is not None
    known = next(item for item in observations if item.state == "known")
    absent = next(item for item in observations if item.state == "unknown")
    assert known.normalized_bytes == 0
    assert absent.model_dump(exclude_none=True) == {"kind": "size", "state": "unknown"}


def test_duplicate_properties_and_unknown_vocabulary_fail_before_conversion() -> None:
    """Repeated values and arbitrary semantic sections cannot overwrite facts."""
    rows = property_rows("identity", {"dataset_version": "1"})
    duplicate = batch_from(workbook_bytes([CORE], details=rows + rows))
    assert duplicate.has_errors
    for change in (
        {"section": "synthetic-sensitive-section"},
        {"property": "synthetic-sensitive-property"},
        {"unit": "MB"},
        {"reference": "urn:example:unsupported"},
    ):
        result = batch_from(workbook_bytes([CORE], details=[rows[0] | change]))
        assert result.has_errors
        assert "synthetic-sensitive" not in result.model_dump_json()


@pytest.mark.parametrize(
    ("primary", "detail", "valid"),
    [
        ({"dataset_version": "1"}, {"dataset_version": "1"}, True),
        ({"dataset_version": "1"}, {"dataset_version": "2"}, False),
        ({"inventory_added": "2026-01-01"}, {"inventory_added": "2026-01-01"}, True),
        ({"inventory_added": "2026-01-01"}, {"inventory_added": "2026-01-02"}, False),
    ],
)
def test_primary_and_detailed_singletons_cannot_overwrite_conflicting_facts(
    primary: dict[str, str], detail: dict[str, str], *, valid: bool
) -> None:
    """Repeated fact representations compare after the same canonical conversion."""
    section = "dates" if "inventory_added" in detail else "identity"
    result = normalize_batch(
        batch_from(
            workbook_bytes([CORE | primary], details=property_rows(section, detail))
        )
    )
    assert result.has_errors is not valid


def test_services_require_exactly_one_link_form_and_unique_object_identity() -> None:
    """Single and grouped references are alternatives; duplicates cannot merge."""
    service = property_rows(
        "service",
        {"id": "service", "served_dataset_id": "asset-001", "reference_kind": "local"},
        entry="service-entry",
    )
    single = normalize_batch(batch_from(workbook_bytes([CORE], details=service)))
    assert not single.has_errors
    assert single.records[0].record.services is not None
    assert single.records[0].record.services[0].served_datasets is not None
    grouped = property_rows(
        "service_dataset",
        {"service_id": "service", "dataset_id": "asset-001", "reference_kind": "local"},
        entry="link",
    )
    assert normalize_batch(
        batch_from(workbook_bytes([CORE], details=service + grouped))
    ).has_errors
    missing_kind = [row for row in service if row["property"] != "reference_kind"]
    assert normalize_batch(
        batch_from(workbook_bytes([CORE], details=missing_kind))
    ).has_errors
    duplicate = property_rows("service", {"id": "service"}, entry="another-entry")
    assert normalize_batch(
        batch_from(workbook_bytes([CORE], details=service + duplicate))
    ).has_errors
    no_links = normalize_batch(batch_from(workbook_bytes([CORE], details=duplicate)))
    assert not no_links.has_errors
    assert no_links.records[0].record.services is not None
    assert no_links.records[0].record.services[0].served_datasets is None


def test_orphan_fields_bad_semantic_reference_and_partial_core_are_not_validated() -> (
    None
):
    """Inspect independent rows despite an invalid neighboring record."""
    field = {
        "dataset_id": "asset-001",
        "object_name": "measurements",
        "field_name": "reading",
        "type": "number",
        "semantic_reference": "javascript:synthetic",
    }
    invalid = normalize_batch(batch_from(workbook_bytes([CORE], fields=[field])))
    assert invalid.has_errors
    assert invalid.diagnostics[0].sheet == "Fields"
    orphan = normalize_batch(batch_from(workbook_bytes([], fields=[field])))
    assert orphan.has_errors
    assert orphan.diagnostics[0].code == "UNRESOLVED_REFERENCE"
    partial = normalize_batch(batch_from(workbook_bytes([{"id": "partial"}, CORE])))
    assert partial.has_errors
    assert len(partial.records) == 1
    assert partial.records[0].record.id == "asset-001"


def test_optional_sheets_and_columns_can_be_absent() -> None:
    """The core stays sufficient without optional sheets and headers."""
    result = normalize_batch(
        batch_from(
            workbook_bytes(
                [CORE],
                headers=DATASET_HEADERS[:4],
                options=WorkbookOptions(optional=False),
            )
        )
    )
    assert not result.has_errors
    assert result.records[0].record.fields is None


@pytest.mark.parametrize(
    ("name", "headers", "rejected"),
    [
        ("Notes", ("annotation",), False),
        ("Lineage", (), True),
        ("Other", DATASET_HEADERS[:4], True),
    ],
)
def test_unrelated_sheets_are_distinct_from_unsupported_semantic_tables(
    name: str, headers: tuple[str, ...], *, rejected: bool
) -> None:
    """Unrelated ranges warn safely; unsupported semantic sections cannot disappear."""
    raw = workbook_bytes(
        [CORE], options=WorkbookOptions(extra_sheet=name, extra_headers=headers)
    )
    if rejected:
        with pytest.raises(IntakeError, match="UNSUPPORTED_VERSION"):
            batch_from(raw)
    else:
        result = normalize_batch(batch_from(raw))
        assert not result.has_errors
        assert result.diagnostics[0].code == "IGNORED_WORKSHEET"
        assert result.diagnostics[0].check_state == "unperformed"
        assert len(result.records) == 1


@pytest.mark.parametrize(
    "marker",
    [b"", b'<c r="B2"><f>1</f><v>1.0</v></c>', b'<c r="B2" t="e"><v>#VALUE!</v></c>'],
)
def test_schema_marker_is_literal_and_present(marker: bytes) -> None:
    """Missing, formula and error marker cells cannot claim the schema version."""
    raw = modify_part(
        workbook_bytes([CORE]),
        "xl/worksheets/sheet1.xml",
        b'<c r="B2" t="inlineStr"><is><t>1.0</t></is></c>',
        marker,
    )
    with pytest.raises(IntakeError, match="INVALID_WORKBOOK"):
        batch_from(raw)


@pytest.mark.parametrize("unbound", [False, True])
def test_sheet_relationship_binding_must_be_exact(*, unbound: bool) -> None:
    """No referenced worksheet may be missing or silently left without a binding."""
    raw = workbook_bytes([CORE])
    if unbound:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            workbook = archive.read("xl/workbook.xml")
        match = re.search(rb'<sheet\b[^>]*name="Fields"[^>]*/>', workbook)
        assert match is not None
        raw = modify_part(raw, "xl/workbook.xml", match[0], b"")
    else:
        raw = modify_part(raw, "xl/workbook.xml", b'r:id="rId3"', b'r:id="rIdMissing"')
    with pytest.raises(IntakeError, match="INVALID_WORKBOOK"):
        batch_from(raw)


def test_complete_shared_string_package_uses_the_same_canonical_contract() -> None:
    """Actual ZIP/OPC preflight and shared rich-string lookup preserve the core ID."""
    raw = workbook_bytes([CORE])
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    parts["xl/worksheets/sheet2.xml"] = parts["xl/worksheets/sheet2.xml"].replace(
        b'<c r="A2" t="inlineStr"><is><t>asset-001</t></is></c>',
        b'<c r="A2" t="s"><v>0</v></c>',
    )
    parts["xl/sharedStrings.xml"] = (
        b'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/'
        b'2006/main"><si><r><t>asset-</t></r><r><t>001</t></r></si></s'
        b"st>"
    )
    parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace(
        b"</Types>",
        (
            b'<Override PartName="/xl/sharedStrings.xml" ContentType="appl'
            b"ication/vnd.openxmlformats-officedocument.spreadsheetml.shar"
            b'edStrings+xml"/></Types>'
        ),
    )
    parts["xl/_rels/workbook.xml.rels"] = parts["xl/_rels/workbook.xml.rels"].replace(
        b"</Relationships>",
        (
            b'<Relationship Type="http://schemas.openxmlformats.org/office'
            b'Document/2006/relationships/sharedStrings" Target="sharedStr'
            b'ings.xml" Id="rIdShared"/></Relationships>'
        ),
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    result = normalize_batch(batch_from(output.getvalue()))
    assert not result.has_errors
    assert result.records[0].record.id == "asset-001"


def test_feedback_and_extended_rows_never_become_input_facts() -> None:
    """Reordered feedback and rows beyond the initial controls remain inert."""
    headers = ("feedback", *DATASET_HEADERS[:4])
    raw = workbook_bytes(
        [CORE | {"feedback": "synthetic-private-feedback"}], headers=headers
    )
    raw = modify_part(
        raw,
        "xl/worksheets/sheet2.xml",
        b'<c r="A2" t="inlineStr"><is><t>synthetic-private-feedback</t></is></c>',
        b'<c r="A2"><f>1+1</f><v>synthetic-private-cache</v></c>',
    )
    raw = modify_part(
        raw, "xl/worksheets/sheet2.xml", b'<row r="2">', b'<row r="1002">'
    )
    for column in "ABCDE":
        raw = modify_part(
            raw,
            "xl/worksheets/sheet2.xml",
            f'r="{column}2"'.encode(),
            f'r="{column}1002"'.encode(),
        )
    result = normalize_batch(batch_from(raw))
    assert not result.has_errors
    assert "synthetic-private" not in result.records[0].record.model_dump_json()
    assert result.records[0].location.row == int("1002")


def test_invalid_primary_rows_do_not_fabricate_dangling_optional_references() -> None:
    """Keep dependent reference checks unperformed for an incomplete ID registry."""
    details = property_rows("identity", {"dataset_version": "1"})
    fields = [
        {
            "dataset_id": "asset-001",
            "object_name": "measurements",
            "field_name": "reading",
            "type": "number",
        }
    ]
    raw = workbook_bytes([CORE], fields=fields, details=details)
    raw = modify_part(
        raw,
        "xl/worksheets/sheet2.xml",
        b'<c r="C2" t="inlineStr"><is><t>Synthetic metadata.</t></is></c>',
        b'<c r="C2"><f>1+1</f><v>2</v></c>',
    )
    result = normalize_batch(batch_from(raw))
    assert result.has_errors
    assert not any(item.code == "UNRESOLVED_REFERENCE" for item in result.diagnostics)
    assert any(
        item.code == "REFERENCE_CHECK_UNPERFORMED" for item in result.diagnostics
    )


def test_duplicate_field_keys_report_the_field_row() -> None:
    """Ordered schema duplicates are errors at the original field location."""
    field = {
        "dataset_id": "asset-001",
        "object_name": "measurements",
        "field_name": "reading",
        "type": "number",
    }
    result = normalize_batch(batch_from(workbook_bytes([CORE], fields=[field, field])))
    assert result.has_errors
    assert result.diagnostics[0].sheet == "Fields"
    assert result.diagnostics[0].row == len([1, 2, 3])
