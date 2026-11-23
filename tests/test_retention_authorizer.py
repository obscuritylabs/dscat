# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Preserve private retention attribution across named-column intake and storage."""

import io
from hashlib import sha256
from typing import TYPE_CHECKING

import pytest
from openpyxl import Workbook, load_workbook
from pydantic import ValidationError
from typer.testing import CliRunner

from dscat import cli
from dscat.intake import worker
from dscat.intake.limits import IntakeError
from dscat.models.catalog import Catalog
from dscat.models.configuration import AssessmentConfiguration
from dscat.serialization import canonical_bytes
from dscat.storage.flatfiles import load_snapshot, parse_record, save_snapshot
from dscat.storage.models import DatasetEntry, dataset_path
from dscat.validation import validate_catalog
from dscat.workbook.collection_layout import FIRST_ROW, HEADERS, LEGACY_HEADERS
from dscat.workbook.generate import create_template
from tests.test_collection_intake import edited, minimum, parsed

if TYPE_CHECKING:
    from pathlib import Path

AUTHOR = "Retention decision authorized by"


def reorder(workbook: Workbook, order: list[int]) -> None:
    """Move whole input columns and native table headers as an Excel user would."""
    sheet = workbook["Intake"]
    for row in range(5, sheet.max_row + 1):
        values = [
            (sheet.cell(row, c).value, sheet.cell(row, c).number_format) for c in order
        ]
        for column, (value, style) in enumerate(values, 1):
            sheet.cell(row, column).value = value
            sheet.cell(row, column).number_format = style
    for column in sheet.tables["IntakeEntries"].tableColumns:
        column.name = sheet.cell(5, column.id).value


def legacy(workbook: Workbook) -> Workbook:
    """Represent a genuine 29-column collection form, with no new answer field."""
    sheet = workbook["Intake"]
    sheet.delete_cols(HEADERS.index(AUTHOR) + 1)
    table = sheet.tables["IntakeEntries"]
    table.ref = table.autoFilter.ref = "A5:AC205"
    table.tableColumns.pop(HEADERS.index(AUTHOR))
    for index, column in enumerate(table.tableColumns, 1):
        column.id = index
    workbook["Start here"]["D1"] = "2.0"
    return workbook


@pytest.mark.parametrize(
    "order",
    [
        list(range(30, 0, -1)),
        list(range(22, 31)) + list(range(1, 22)),
        list(range(2, 31, 2)) + list(range(1, 31, 2)),
    ],
)
def test_all_columns_parse_by_name(order: list[int]) -> None:
    """Shuffling every field preserves seven distinct complete example records."""
    workbook = load_workbook(io.BytesIO(create_template(examples=True).content))
    expected = [r.record for r in parsed(edited(workbook)).records]
    reorder(workbook, order)
    result = parsed(edited(workbook))
    assert not result.has_errors
    assert [r.record for r in result.records] == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        "  ",
        " Example Approver A\r\nReview role ",
        "Unknown",
        "Not yet authorized",
        "=inert text",
    ],
)
def test_optional_normalized_authorizer(value: str | None) -> None:
    """Keep absence and normalized supplied attribution independent of other groups."""
    workbook = minimum()
    cell = workbook["Intake"].cell(6, HEADERS.index(AUTHOR) + 1)
    cell.value = value
    cell.data_type = "s"
    result = parsed(edited(workbook))
    assert not result.has_errors
    intake = result.records[0].record.collection_intake
    assert intake is not None
    if value is None or not value.strip():
        assert intake.retention is None
    else:
        assert intake.retention is not None
        assert intake.retention.authorized_by == value.strip().replace("\r\n", "\n")
        assert intake.retention.days is None
        assert intake.retention.status is None


def test_reordered_formula_reports_actual_authorizer_column() -> None:
    """Reject executable attribution and point to its moved cell without echoing it."""
    workbook = minimum()
    order = [22, *range(1, 22), *range(23, 31)]
    reorder(workbook, order)
    workbook["Intake"]["A6"] = "=PRIVATE_AUTHORIZER_SENTINEL()"
    result = parsed(edited(workbook))
    assert result.has_errors
    assert any(d.column == 1 and d.row == FIRST_ROW for d in result.diagnostics)
    assert "PRIVATE_AUTHORIZER" not in str(result.diagnostics)


def test_legacy_headers_reordered_without_authorizer() -> None:
    """Old 2.0 forms remain readable with their original names and no attribution."""
    workbook = legacy(minimum())
    assert tuple(c.value for c in workbook["Intake"][5]) == LEGACY_HEADERS
    reorder(workbook, list(range(29, 0, -1)))
    result = parsed(edited(workbook))
    assert not result.has_errors
    intake = result.records[0].record.collection_intake
    assert intake is not None
    assert intake.retention is None


@pytest.mark.parametrize("marker", ["2.1", "2.1-form"])
def test_supported_new_markers(marker: str) -> None:
    """Accept the earlier distributed form alias without discarding its new answer."""
    workbook = minimum()
    workbook["Start here"]["D1"] = marker
    workbook["Intake"].cell(6, HEADERS.index(AUTHOR) + 1, "Example Approver")
    result = parsed(edited(workbook))
    assert not result.has_errors
    intake = result.records[0].record.collection_intake
    assert intake is not None
    assert intake.retention is not None
    assert intake.retention.authorized_by == "Example Approver"


@pytest.mark.parametrize("old", [False, True])
def test_marker_and_header_vocabulary_must_agree(*, old: bool) -> None:
    """Refuse a new vocabulary tagged old or an old vocabulary tagged new."""
    workbook = legacy(minimum()) if old else minimum()
    workbook["Start here"]["D1"] = "2.1" if old else "2.0"
    assert parsed(edited(workbook)).has_errors


def test_attribution_storage_versions_and_determinism(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Build the new version, retain attribution, and reject it under older versions."""
    workbook = minimum()
    workbook["Intake"].cell(6, HEADERS.index(AUTHOR) + 1, "Private example authorizer")
    result = parsed(edited(workbook))
    validation = validate_catalog(result.records, AssessmentConfiguration())
    catalog = validation.catalog
    assert catalog is not None
    assert catalog.schema_version == "1.2"
    root = tmp_path / "catalog"
    saved = save_snapshot(root, catalog)
    loaded = load_snapshot(root)
    assert loaded.catalog == catalog
    assert loaded.manifest.schema_version == "1.2"
    assert all(e.schema_version == "1.2" for e in loaded.manifest.datasets)
    assert (
        save_snapshot(root, loaded.catalog, replace=True).generation == saved.generation
    )
    raw = canonical_bytes(catalog.datasets[0])
    for version in ["1.0", "1.1"]:
        with pytest.raises(ValidationError):
            Catalog.model_validate(
                catalog.model_dump(exclude_none=True) | {"schema_version": version}
            )
        identifier = catalog.datasets[0].id
        entry = DatasetEntry.model_validate(
            {
                "id": identifier,
                "path": dataset_path(identifier),
                "sha256": sha256(raw).hexdigest(),
                "schema_version": version,
            }
        )
        with pytest.raises(IntakeError):
            parse_record(raw, entry)
    source = tmp_path / "intake.xlsx"
    source.write_bytes(edited(workbook))
    built = tmp_path / "cli-catalog"
    monkeypatch.setattr(
        cli, "invoke", lambda request, _timeout: worker.inspect_selection(request)
    )
    response = CliRunner().invoke(
        cli.app, ["build", str(source), "--output", str(built), "--format", "json"]
    )
    assert response.exit_code == 0, response.output
    assert load_snapshot(built).catalog == catalog


def test_new_version_preserved_without_authorizer(tmp_path: Path) -> None:
    """A loaded 1.2 catalog is never downgraded just because attribution is absent."""
    result = parsed(edited(minimum()))
    catalog = Catalog(schema_version="1.2", datasets=[r.record for r in result.records])
    root = tmp_path / "catalog"
    save_snapshot(root, catalog)
    assert load_snapshot(root).catalog == catalog


@pytest.mark.parametrize(
    ("part", "old", "new"),
    [
        ("xl/tables/table1.xml", b'count="30"', b'count="29"'),
        ("xl/tables/table1.xml", b"A5:AD205", b"A5:AE205"),
        ("xl/comments/comment1.xml", b'ref="AD5"', b'ref="AE5"'),
        (
            "xl/drawings/commentsDrawing1.vml",
            b"<ns2:Column>29</ns2:Column>",
            b"<ns2:Column>30</ns2:Column>",
        ),
    ],
)
def test_new_package_width_is_closed(part: str, old: bytes, new: bytes) -> None:
    """The extra column permits no wider tables, mismatched counts or note anchors."""
    import zipfile  # noqa: PLC0415 -- trusted generated package mutation.

    from tests.test_collection_package import packed  # noqa: PLC0415 -- fixture serialization.

    with zipfile.ZipFile(io.BytesIO(create_template().content)) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    assert old in parts[part]
    parts[part] = parts[part].replace(old, new)
    with pytest.raises(IntakeError):
        parsed(packed(parts))


def test_legacy_note_cannot_point_beyond_legacy_headers() -> None:
    """A valid passive note still needs an actual header in its declared revision."""
    from openpyxl.comments import Comment  # noqa: PLC0415 -- authored test note.

    workbook = legacy(minimum())
    workbook["Intake"]["AD5"].comment = Comment(
        "Outside legacy width", "Example author"
    )
    with pytest.raises(IntakeError):
        parsed(edited(workbook))
