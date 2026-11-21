# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Accept collection registration and reject malformed edits through safe intake."""

import io
import zipfile
from datetime import date
from typing import TYPE_CHECKING

import pytest
from openpyxl import Workbook, load_workbook
from typer.testing import CliRunner

from dscat.cli import app
from dscat.intake.archive import read_archive
from dscat.intake.limits import Budget, IntakeError
from dscat.intake.normalize import normalize_batch
from dscat.models.collection import RegistrationKnownAmount
from dscat.workbook.collection_generate import relative_annotations
from dscat.workbook.collection_layout import FIRST_ROW, HEADERS, TEMPLATE_ROWS
from dscat.workbook.collection_parse import completed_date
from dscat.workbook.generate import create_template, relative_worksheet_relationships
from dscat.workbook.parse import Cell, parse_workbook

if TYPE_CHECKING:
    from pathlib import Path

    from dscat.intake.normalize import NormalizedBatch


EXAMPLE_COUNT = 7
OPERATIONAL = 3


def edited(workbook: Workbook) -> bytes:
    """Save trusted edits and normalize only the local writer's OPC targets."""
    raw = io.BytesIO()
    workbook.save(raw)
    out = io.BytesIO()
    with (
        zipfile.ZipFile(raw) as src,
        zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as dst,
    ):
        for name in src.namelist():
            data = src.read(name)
            if name == "xl/_rels/workbook.xml.rels":
                data = relative_worksheet_relationships(data)
            elif name.startswith("xl/worksheets/_rels/") and name.endswith(".rels"):
                data = relative_annotations(data)
            dst.writestr(name, data)
    return out.getvalue()


def parsed(content: bytes) -> NormalizedBatch:
    """Run authored bytes through exactly the guarded parser/conversion path."""
    budget = Budget()
    return normalize_batch(parse_workbook(read_archive(content, budget), 1, budget))


def minimum() -> Workbook:
    """Complete only required first-pass responses in a blank generated workbook."""
    w = load_workbook(io.BytesIO(create_template().content))
    s = w["Intake"]
    values = {
        "Collection name *": "Synthetic collection",
        "Data owner / accountable team *": "Unknown",
        "Submitted by / accountable for entry *": "Example Contributor",
        "Completed on *": date(2026, 1, 15),
    }
    for h in ["PII *", "PHI *", "CUI *", "PCII *", "ISVI *", "Other sensitive data *"]:
        values[h] = "Unknown"
    for h, v in values.items():
        s.cell(6, HEADERS.index(h) + 1, v)
    assert isinstance(w, Workbook)
    return w


def test_default_and_example_layout_deterministic() -> None:
    """Keep the accepted interface, blank default and ordinary synthetic records."""
    for examples in (False, True):
        a = create_template(examples=examples)
        assert a.content == create_template(examples=examples).content
        w = load_workbook(io.BytesIO(a.content))
        s = w["Intake"]
        assert w.sheetnames == ["Start here", "Intake"]
        assert [c.value for c in s[5]] == list(HEADERS)
        assert s.freeze_panes == "B6"
        assert all(c.comment for c in s[5])
        assert set(s.tables) == {"IntakeEntries"}
        assert not any(
            c.data_type == "f" or c.hyperlink
            for sheet in w
            for row in sheet
            for c in row
        )
        p = parsed(a.content)
        assert not p.has_errors
        assert len(p.records) == (7 if examples else 0)
        if examples:
            assert all(r.record.collection_intake is not None for r in p.records)


def test_minimum_absence_and_quantity_zero() -> None:
    """Accept absent generation and unknown owner without fabricating facts."""
    w = minimum()
    s = w["Intake"]
    s["N6"] = 0
    s["O6"] = "KB"
    s["P6"] = "Estimate"
    p = parsed(edited(w))
    assert not p.has_errors
    record = p.records[0].record
    assert record.description is None
    assert record.core_party is None
    assert record.collection_intake is not None
    assert record.collection_intake.generation is None
    q = record.collection_intake.current_amount
    assert isinstance(q, RegistrationKnownAmount)
    assert q.normalized_bytes == 0


@pytest.mark.parametrize("label", [h for h in HEADERS if h.endswith("*")])
def test_each_missing_required_response(label: str) -> None:
    """Require first-pass responses even if users clear or bypass cell controls."""
    w = minimum()
    w["Intake"].cell(6, HEADERS.index(label) + 1).value = None
    p = parsed(edited(w))
    assert p.has_errors
    assert not p.records
    assert all(d.sheet == "Intake" and d.row == FIRST_ROW for d in p.diagnostics)


@pytest.mark.parametrize(
    ("label", "value"),
    [
        ("PII *", "Maybe"),
        ("Other sensitive data *", "Yes"),
        ("Current unit", "records"),
        ("Amount held now", -1),
        ("Amount held now", "1e3"),
        ("Amount held now", "NaN"),
        ("Amount held now", "0.0000000001"),
        ("Amount held now", "99999999999999999999999999999"),
        ("Retention days", "1.5"),
        ("Retention days", -1),
        ("Retention status", "Confirmed"),
        ("Typical runs", 1),
        ("Completed on *", "2026-02-30"),
        ("Completed on *", 60),
        ("Completed on *", True),
        ("Completed on *", "=TODAY()"),
        ("Access pattern", "Anything"),
    ],
)
def test_invalid_answers_do_not_become_records(label: str, value: object) -> None:
    """Reject bad types, units, states, incomplete groups and executable formulas."""
    w = minimum()
    w["Intake"].cell(6, HEADERS.index(label) + 1, value)
    p = parsed(edited(w))
    assert p.has_errors
    assert not p.records
    assert p.diagnostics


@pytest.mark.parametrize(
    ("kind", "value", "epoch", "expected"),
    [
        ("n", "1", False, "1900-01-01"),
        ("n", "61", False, "1900-03-01"),
        ("n", "0", True, "1904-01-01"),
        ("d", "2026-01-15T00:00:00", False, "2026-01-15"),
        ("inlineStr", "2026-01-15", False, "2026-01-15"),
    ],
)
def test_date_encodings(kind: str, value: str, epoch: object, expected: str) -> None:
    """Decode only calendar facts in explicitly selected Excel epochs."""
    assert (
        completed_date(
            Cell(row=6, column=13, text=value, kind=kind), date1904=bool(epoch)
        ).isoformat()
        == expected
    )


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        ("n", "0"),
        ("n", "-1"),
        ("n", "60"),
        ("n", "1.5"),
        ("n", "999999999999"),
        ("n", "NaN"),
        ("d", "2026-01-15T01:00:00"),
        ("inlineStr", "45000"),
    ],
)
def test_bad_date_encodings(kind: str, value: str) -> None:
    """Refuse ambiguous text, times, false leap days and numeric overflow."""
    with pytest.raises((ValueError, OverflowError)):
        completed_date(Cell(row=6, column=13, text=value, kind=kind), date1904=False)


def test_reordered_headers_and_rows_beyond_table() -> None:
    """Use header names and all populated rows, not table display boundaries."""
    w = minimum()
    s = w["Intake"]
    for r in [5, 6]:
        left, right = s.cell(r, 1).value, s.cell(r, 2).value
        s.cell(r, 1, right)
        s.cell(r, 2, left)
    table = s.tables["IntakeEntries"]
    table.tableColumns[0].name = HEADERS[1]
    table.tableColumns[1].name = HEADERS[0]
    for c in range(1, len(HEADERS) + 1):
        s.cell(206, c, s.cell(6, c).value)
        s.cell(6, c).value = None
    p = parsed(edited(w))
    assert not p.has_errors
    assert p.records[0].location.row == FIRST_ROW + TEMPLATE_ROWS


@pytest.mark.parametrize(
    "mutation",
    ["header", "duplicate", "unknown", "outside", "marker", "version", "kind"],
)
def test_headers_and_markers(mutation: str) -> None:
    """Reject structural drift instead of silently importing only recognizable cells."""
    w = minimum()
    s = w["Intake"]
    if mutation == "header":
        s["A5"] = None
    elif mutation == "duplicate":
        s["B5"] = s["A5"].value
    elif mutation == "unknown":
        s["B5"] = "Unrecognized header"
    elif mutation == "outside":
        s["AD6"] = "Unrecognized value"
    elif mutation == "marker":
        w["Start here"]["D1"] = None
    elif mutation == "version":
        w["Start here"]["D1"] = "9.0"
    else:
        w["Start here"]["D2"] = "unrecognized-kind"
    try:
        result = parsed(edited(w))
    except IntakeError:
        return
    assert result.has_errors


def test_descriptive_sources_and_independent_retention() -> None:
    """Keep unresolved source names valid and separate from rich capacity metadata."""
    w = minimum()
    s = w["Intake"]
    s["X6"] = " External source ;External source; Another source; "
    s["T6"] = 0
    s["U6"] = "Proposed"
    s["J6"] = "Yes"
    s["K6"] = "Fictional restricted notes"
    p = parsed(edited(w))
    assert not p.has_errors
    i = p.records[0].record.collection_intake
    assert i is not None
    assert i.generation is not None
    assert i.generation.source_names == ["Another source", "External source"]
    assert i.retention is not None
    assert i.retention.days == 0
    assert p.records[0].record.capacity is None


def test_cli_examples_and_overwrite(tmp_path: Path) -> None:
    """Expose examples explicitly and preserve outputs on refused replacement."""
    target = tmp_path / "example.xlsx"
    runner = CliRunner()
    args = ["template", "--output", str(target), "--examples"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    original = target.read_bytes()
    assert len(parsed(original).records) == EXAMPLE_COUNT
    assert runner.invoke(app, args).exit_code == OPERATIONAL
    assert target.read_bytes() == original
    assert runner.invoke(app, [*args, "--replace"]).exit_code == 0
    assert target.read_bytes() == original


@pytest.mark.parametrize(
    "mutation",
    [
        "hidden",
        "moved-name",
        "extra",
        "table-header",
        "numeric-overflow",
        "numeric-nan",
        "empty-source",
        "other-empty",
    ],
)
def test_remaining_structural_and_partial_edits(mutation: str) -> None:
    """Reject header/control drift while allowing empty optional descriptive sources."""
    w = minimum()
    s = w["Intake"]
    if mutation == "hidden":
        s.sheet_state = "hidden"
    elif mutation == "moved-name":
        w.defined_names["dscat_workbook_schema"].attr_text = "'Start here'!$D$2"
    elif mutation == "extra":
        w.create_sheet("Extra")
    elif mutation == "table-header":
        s.tables["IntakeEntries"].tableColumns[0].name = "Changed header"
    elif mutation in {"numeric-overflow", "numeric-nan"}:
        cell = s["N6"]
        cell.value = "1E99" if mutation == "numeric-overflow" else "NaN"
        cell.data_type = "n"
    elif mutation == "empty-source":
        s["X6"] = " ; ; "
    else:
        s["AD6"] = "  "
    try:
        p = parsed(edited(w))
    except IntakeError:
        return
    if mutation in {"empty-source", "other-empty"}:
        assert not p.has_errors
    else:
        assert p.has_errors


def test_raw_whitespace_does_not_supply_a_required_value() -> None:
    """Ignore empty lexical cells before first-pass requiredness checks."""
    from dscat.intake.limits import DiagnosticCollector  # noqa: PLC0415 -- safe error collector.
    from dscat.models.intake import SourceLocation  # noqa: PLC0415 -- located fixture.
    from dscat.workbook.collection_parse import parse_row  # noqa: PLC0415 -- isolated bounded row boundary.

    collector = DiagnosticCollector()
    assert (
        parse_row(
            {1: Cell(row=6, column=1, text=" ")},
            {1: "name"},
            SourceLocation(source_token=1, sheet="Intake", row=6),
            collector,
            date1904=False,
        )
        is None
    )


def test_generator_relationship_refusal_and_serializer_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refuse unexpected generated parts and nonbyte serialization results."""
    from dscat.workbook import collection_generate as generate  # noqa: PLC0415 -- generator fault injection.

    with pytest.raises(ValueError, match="Unexpected generated"):
        generate.relative_annotations(
            b'<Relationships><Relationship Target="unexpected"/></Relationships>'
        )
    monkeypatch.setattr(generate.ET, "tostring", lambda *_a, **_k: "not bytes")
    with pytest.raises(TypeError, match="serialize relationship bytes"):
        generate.relative_annotations(b"<Relationships/>")


def test_invalid_epoch_setting() -> None:
    """Refuse unsupported epoch declarations rather than guessing a date system."""
    from tests.test_collection_package import packed  # noqa: PLC0415 -- trusted mutation packaging.

    raw = edited(minimum())
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    assert b"<workbookPr/>" in parts["xl/workbook.xml"]
    parts["xl/workbook.xml"] = parts["xl/workbook.xml"].replace(
        b"<workbookPr/>", b'<workbookPr date1904="invalid"/>'
    )
    with pytest.raises(IntakeError):
        parsed(packed(parts))


def test_table_owned_by_wrong_sheet() -> None:
    """Keep passive table ownership bound to the actual intake worksheet."""
    workbook = minimum()
    sheet = workbook["Intake"]
    table = sheet.tables["IntakeEntries"]
    del sheet.tables["IntakeEntries"]
    other = workbook.create_sheet("Other table")
    for column, header in enumerate(HEADERS, 1):
        other.cell(5, column, header)
    other.add_table(table)
    with pytest.raises(IntakeError):
        parsed(edited(workbook))


def test_current_package_inventory_fixture() -> None:
    """Protect the observed current OOXML closure without distributing old forms."""
    import json  # noqa: PLC0415 -- fixed fixture inspection.
    from pathlib import Path  # noqa: PLC0415 -- fixture location.

    inventory = json.loads(
        (Path(__file__).parent / "fixtures/workbook-2.0/package-parts.json").read_text()
    )
    content = create_template().content
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        assert sorted(archive.namelist()) == inventory["parts"]
    assert list(HEADERS) == inventory["headers"]
    assert (
        sorted({r.kind for r in read_archive(content, Budget()).relationships})
        == inventory["relationship_kinds"]
    )
