# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Semantic XML boundaries independently of ZIP framing and workbook generation."""

import pytest
from pydantic import ValidationError

from dscat.intake.archive import XmlPart
from dscat.intake.limits import Budget, IntakeError
from dscat.workbook.parse import (
    MAIN,
    StringEvents,
    WorkbookEvents,
    WorksheetEvents,
    read_document,
)

NAMESPACE = MAIN.removesuffix("}")
RELATIONSHIPS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def workbook_document(body: str) -> XmlPart:
    """Wrap test-owned workbook XML with explicit namespaces."""
    return XmlPart(
        name="xl/workbook.xml",
        content=(
            f'<workbook xmlns="{NAMESPACE}" xmlns:r="{RELATIONSHIPS}">{body}</workbook>'
        ).encode(),
    )


def worksheet_document(body: str) -> XmlPart:
    """Wrap a sparse worksheet fragment with its real namespace."""
    return XmlPart(
        name="xl/worksheets/sheet1.xml",
        content=(
            f'<worksheet xmlns="{NAMESPACE}"><sheetData>{body}</sheetData></worksheet>'
        ).encode(),
    )


@pytest.mark.parametrize(
    "body",
    [
        '<sheet name="Datasets" r:id="rId1"/>',
        (
            '<sheets><sheet name="Datasets" r:id="rId1"/><sheet name="Dat'
            'asets" r:id="rId2"/></sheets>'
        ),
        (
            '<sheets><sheet name="Datasets" r:id="rId1"/><sheet name="Fie'
            'lds" r:id="rId1"/></sheets>'
        ),
        '<sheets><sheet name="Datasets"/></sheets>',
        '<definedName name="dscat_workbook_schema">Instructions!$B$2</definedName>',
        (
            '<definedNames><definedName name="dscat_workbook_schema" loca'
            'lSheetId="0">Instructions!$B$2</definedName></definedNames>'
        ),
        (
            '<definedNames><definedName name="dscat_workbook_schema" hidd'
            'en="1">Instructions!$B$2</definedName></definedNames>'
        ),
        (
            '<definedNames><definedName name="dscat_workbook_schema">Inst'
            'ructions!$B$2</definedName><definedName name="dscat_workbook'
            '_schema">Instructions!$B$2</definedName></definedNames>'
        ),
    ],
)
def test_workbook_bindings_are_unique_global_and_structural(body: str) -> None:
    """Malformed identities and hidden or scoped markers fail closed."""
    with pytest.raises((IntakeError, ValidationError)):
        read_document(workbook_document(body), Budget(), WorkbookEvents())


def test_optional_marker_quoting_and_false_hidden_are_equivalent() -> None:
    """Excel can drop unnecessary sheet-name quotes without changing coordinates."""
    events = WorkbookEvents()
    read_document(
        workbook_document(
            '<definedNames><definedName name="dscat_workbook_schema" hidd'
            'en="false">Instructions!$B$2</definedName></definedNames>'
        ),
        Budget(),
        events,
    )
    assert events.names == {"dscat_workbook_schema": "'Instructions'!$B$2"}


@pytest.mark.parametrize(
    ("name", "events"),
    [
        ("xl/workbook.xml", WorkbookEvents()),
        ("xl/sharedStrings.xml", StringEvents()),
        ("xl/worksheets/sheet1.xml", WorksheetEvents([])),
    ],
)
def test_semantic_roots_require_supported_namespaces(
    name: str, events: WorkbookEvents | StringEvents | WorksheetEvents
) -> None:
    """Lexically valid foreign XML cannot impersonate the supported OOXML root."""
    with pytest.raises(IntakeError, match="INVALID_WORKBOOK"):
        read_document(XmlPart(name=name, content=b"<synthetic/>"), Budget(), events)


def test_shared_and_inline_rich_strings_preserve_runs() -> None:
    """Rich text remains one scalar in order; whitespace is normalized later."""
    strings = StringEvents()
    part = XmlPart(
        name="xl/sharedStrings.xml",
        content=(
            f'<sst xmlns="{NAMESPACE}"><si><r><t>asset-</t></r><r><t>001</'
            f"t></r></si><si><t> title </t></si></sst>"
        ).encode(),
    )
    read_document(part, Budget(), strings)
    assert strings.strings == ["asset-001", " title "]
    sheet = WorksheetEvents(strings.strings)
    read_document(
        worksheet_document(
            '<row r="2"><c r="A2" t="s"><v>0</v></c><c r="B2" t="inlineSt'
            'r"><is><r><t>Synthetic </t></r><r><t>title</t></r></is></c><'
            "/row>"
        ),
        Budget(),
        sheet,
    )
    assert sheet.cells[2, 1].text == "asset-001"
    assert sheet.cells[2, 2].text == "Synthetic title"


@pytest.mark.parametrize(
    "body",
    [
        '<row r="2"><c r="A2"/><c r="A2"/></row>',
        '<row r="bad"><c r="A2"/></row>',
        '<row r="3"><c r="A2"/></row>',
        '<row><c r="A0"/></row>',
        '<row><c r="XFE2"/></row>',
        '<row><c r="A1048577"/></row>',
        '<row><c r="A2" t="unsupported"/></row>',
        '<row><c r="A2"><c r="B2"/></c></row>',
        '<row><c r="A2"><f>1</f><f>2</f></c></row>',
        '<row><c r="A2"><v>1</v><v>2</v></c></row>',
        '<row><c r="A2" t="inlineStr"><v>1</v></c></row>',
        '<row><c r="A2" t="n"><is><t>1</t></is></c></row>',
        '<row><c r="A2" t="s"><v>-1</v></c></row>',
        '<row><c r="A2" t="s"><v>0</v></c></row>',
        '<row><c r="A2" t="s"><v>99999999999</v></c></row>',
        '<c r="A2"/>',
    ],
)
def test_cells_cannot_alias_overwrite_or_infer_unsupported_encodings(body: str) -> None:
    """Invalid coordinates, shared indices and conflicting scalar forms are rejected."""
    with pytest.raises((IntakeError, ValidationError)):
        read_document(worksheet_document(body), Budget(), WorksheetEvents([]))


def test_cell_formula_and_cache_are_separate_and_error_boolean_are_not_text() -> None:
    """The row adapter can reject formulas/errors without importing cached text."""
    events = WorksheetEvents([])
    read_document(
        worksheet_document(
            '<row><c r="A2"><f>1+1</f><v>2</v></c><c r="B2" t="e"><v>#VAL'
            'UE!</v></c><c r="C2" t="b"><v>1</v></c></row>'
        ),
        Budget(),
        events,
    )
    assert events.cells[2, 1].formula == "1+1"
    assert events.cells[2, 1].text == "2"
    assert events.cells[2, 2].error
    assert events.cells[2, 3].error


def test_phonetic_annotations_do_not_change_visible_string_facts() -> None:
    """Ruby/phonetic annotation text is formatting rather than additional cell data."""
    strings = StringEvents()
    content = (
        f'<sst xmlns="{NAMESPACE}"><si><t>visible</t>'
        '<rPh sb="0" eb="1"><t>annotation</t></rPh></si></sst>'
    ).encode()
    read_document(
        XmlPart(name="xl/sharedStrings.xml", content=content), Budget(), strings
    )
    assert strings.strings == ["visible"]
    cells = WorksheetEvents([])
    read_document(
        worksheet_document(
            '<row><c r="A2" t="inlineStr"><is><t>visible</t>'
            '<rPh sb="0" eb="1"><t>annotation</t></rPh>'
            "</is></c></row>"
        ),
        Budget(),
        cells,
    )
    assert cells.cells[2, 1].text == "visible"
