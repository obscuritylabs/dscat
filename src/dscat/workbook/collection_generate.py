# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Render the accepted collection-first interface without reading submissions."""

import hashlib
import io
import zipfile
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.writer.excel import ExcelWriter

from dscat.intake.annotations import attachment_kind
from dscat.models.intake import WorkbookMetadata
from dscat.workbook.collection_examples import example_rows
from dscat.workbook.collection_layout import (
    COLUMN_SPECS,
    GROUPS,
    GUIDANCE,
    HEADERS,
    TEMPLATE_ROWS,
    UNITS,
)
from dscat.workbook.generate import (
    WorkbookArtifact,
    relative_worksheet_relationships,
    write_text,
)

if TYPE_CHECKING:
    from openpyxl.worksheet.worksheet import Worksheet

NAVY = "17354A"
TEAL = "147D80"
NUMERIC = {"Amount held now", "New amount per run", "Typical runs", "Retention days"}


def add_control(
    sheet: Worksheet, label: str, choices: tuple[str, ...] | None = None
) -> None:
    """Attach ordinary prompts and controls without trusting them during import."""
    column = HEADERS.index(label) + 1
    if choices is not None:
        rule = DataValidation(
            type="list",
            formula1='"' + ",".join(choices) + '"',
            allow_blank=not label.endswith("*"),
        )
        message = "Choose a listed option. Unknown is not No."
    elif label == "Completed on *":
        rule = DataValidation(
            type="date",
            operator="between",
            formula1="1",
            formula2="2958465",
            allow_blank=False,
        )
        message = "Enter a calendar date, displayed YYYY-MM-DD."
    else:
        whole = label == "Retention days"
        rule = DataValidation(
            type="whole" if whole else "decimal",
            operator="greaterThanOrEqual",
            formula1=0,
            allow_blank=True,
        )
        message = (
            "Enter a nonnegative whole number."
            if whole
            else "Enter a nonnegative number. Leave unknown quantities blank."
        )
    rule.showInputMessage = True
    rule.showErrorMessage = True
    rule.errorStyle = "stop"
    rule.promptTitle = "Entry guidance"
    rule.prompt = message
    rule.errorTitle = "Check this entry"
    rule.error = message
    sheet.add_data_validation(rule)
    letter = get_column_letter(column)
    rule.add(f"{letter}6:{letter}{TEMPLATE_ROWS + 5}")


def instructions(workbook: Workbook, *, examples: bool) -> None:
    """Explain completion and synthetic examples with visible immutable markers."""
    sheet = workbook.active
    sheet.title = "Start here"
    for row, (label, guidance) in enumerate(GUIDANCE, 1):
        text = guidance.replace(
            "{mode}", "SYNTHETIC WORKED EXAMPLE" if examples else "BLANK INTAKE"
        )
        for column, value in enumerate((label, text), 1):
            cell = sheet.cell(row, column)
            write_text(cell, value)
            cell.font = Font(name="Calibri", size=11, color=NAVY, bold=column == 1)
            cell.alignment = Alignment(wrap_text=True, vertical="center")
            cell.fill = PatternFill(
                "solid", fgColor="EAF5F4" if row % 2 == 0 else "FFFFFF"
            )
        sheet.row_dimensions[row].height = 76
    sheet.column_dimensions["A"].width = 29
    sheet.column_dimensions["B"].width = 110
    sheet.column_dimensions["C"].width = 22
    sheet.column_dimensions["D"].width = 25
    for cell, value in [
        ("C1", "Workbook schema"),
        ("D1", "2.1"),
        ("C2", "Workbook kind"),
        ("D2", "collection-intake"),
    ]:
        write_text(sheet[cell], value)
    for name, target in [
        ("dscat_workbook_schema", "'Start here'!$D$1"),
        ("dscat_workbook_kind", "'Start here'!$D$2"),
    ]:
        workbook.defined_names.add(DefinedName(name, attr_text=target))
    sheet.sheet_view.showGridLines = False
    sheet.freeze_panes = "B2"


def intake_sheet(workbook: Workbook, *, examples: bool) -> None:
    """Render one collection per row with notes, topic bands and size-only units."""
    sheet = workbook.create_sheet("Intake")
    for row, text in [
        (1, "COLLECTION INTAKE / ONE COLLECTION PER ROW"),
        (2, "Start with the collection. Add its generating process only when known."),
        (
            3,
            (
                "* First-pass response required • Unknown is acceptable • "
                "Optional details can be enriched later"
            ),
        ),
    ]:
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=12)
        write_text(sheet.cell(row, 1), text)
        sheet.cell(row, 1).font = Font(
            name="Calibri", size=16 if row == 1 else 11, bold=row == 1, color=NAVY
        )
        sheet.row_dimensions[row].height = 36
    for first, last, label, color in GROUPS:
        sheet.merge_cells(start_row=4, start_column=first, end_row=4, end_column=last)
        write_text(sheet.cell(4, first), label)
        for column in range(first, last + 1):
            sheet.cell(4, column).fill = PatternFill("solid", fgColor=color)
        sheet.cell(4, first).font = Font(
            name="Calibri", size=10, bold=True, color="FFFFFF"
        )
    sheet.row_dimensions[4].height = 25
    sheet.row_dimensions[5].height = 48
    for column, (label, width, prompt) in enumerate(COLUMN_SPECS, 1):
        cell = sheet.cell(5, column)
        write_text(cell, label)
        cell.comment = Comment(
            prompt.replace("prototype", "workbook"), "Intake guidance"
        )
        cell.comment.width = 370
        cell.comment.height = 150
        cell.font = Font(name="Calibri", bold=True, size=11, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=TEAL)
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        sheet.column_dimensions[get_column_letter(column)].width = width
        for row in range(6, TEMPLATE_ROWS + 6):
            cell = sheet.cell(row, column)
            cell.font = Font(name="Calibri", size=11, color=NAVY)
            cell.fill = PatternFill(
                "solid", fgColor="EFF7F7" if row % 2 == 0 else "FFFFFF"
            )
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            cell.number_format = (
                "yyyy-mm-dd"
                if label == "Completed on *"
                else ("General" if label in NUMERIC else "@")
            )
    for row in range(6, TEMPLATE_ROWS + 6):
        sheet.row_dimensions[row].height = 56
    sheet.freeze_panes = "B6"
    sheet.sheet_view.showGridLines = False
    sheet.sheet_view.zoomScale = 85
    sheet.sheet_properties.tabColor = TEAL
    table = Table(
        displayName="IntakeEntries",
        ref=f"A5:{get_column_letter(len(HEADERS))}{TEMPLATE_ROWS + 5}",
    )
    table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    sheet.add_table(table)
    sheet_controls(sheet)
    if examples:
        fill_examples(sheet)


def sheet_controls(sheet: Worksheet) -> None:
    """Attach the fixed controlled vocabulary and numeric constraints."""
    for label in [
        "PII *",
        "PHI *",
        "CUI *",
        "PCII *",
        "ISVI *",
        "Other sensitive data *",
    ]:
        add_control(sheet, label, ("Yes", "No", "Unknown"))
    for label in ["Current unit", "Per-run unit"]:
        add_control(sheet, label, UNITS)
    for label in ["Current amount basis", "Per-run amount basis"]:
        add_control(sheet, label, ("Estimate", "Measured", "Unknown"))
    add_control(sheet, "Per", ("day", "week", "month", "year", "On demand", "Unknown"))
    add_control(
        sheet,
        "Access pattern",
        (
            "Bulk or batch",
            "Interactive search",
            "Record lookup",
            "Streaming",
            "Mixed",
            "Other",
            "Unknown",
        ),
    )
    add_control(
        sheet, "Retention status", ("Not yet determined", "Proposed", "Confirmed")
    )
    for label in sorted(NUMERIC | {"Completed on *"}):
        add_control(sheet, label)


def fill_examples(sheet: Worksheet) -> None:
    """Seed ordinary editable synthetic rows with sufficient display height."""
    for row, values in enumerate(example_rows(), 6):
        for column, label in enumerate(HEADERS, 1):
            value = values.get(label)
            if isinstance(value, str):
                write_text(sheet.cell(row, column), value)
            elif value is not None:
                sheet.cell(row, column, value)
        sheet.row_dimensions[row].height = 150


def relative_annotations(payload: bytes) -> bytes:
    """Normalize only trusted generator annotation targets into prescribed OPC paths."""
    root = ET.fromstring(payload)  # noqa: S314 -- only self-generated trusted XML.
    for relationship in root:
        target = relationship.attrib["Target"]
        if target.startswith("/xl/") and attachment_kind(target[1:]) is not None:
            relationship.set("Target", "../" + target.removeprefix("/xl/"))
        else:
            msg = "Unexpected generated annotation relationship."
            raise ValueError(msg)
    encoded = ET.tostring(root, encoding="utf-8")
    if not isinstance(encoded, bytes):
        msg = "Generator did not serialize relationship bytes."
        raise TypeError(msg)
    return encoded


def collection_template(*, examples: bool = False) -> WorkbookArtifact:
    """Serialize deterministic authored output; never open a submitted workbook."""
    workbook = Workbook()
    workbook.properties.creator = workbook.properties.lastModifiedBy = "DSCat"
    workbook.properties.created = workbook.properties.modified = datetime(
        2026, 1, 1, tzinfo=UTC
    )
    instructions(workbook, examples=examples)
    intake_sheet(workbook, examples=examples)
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        ExcelWriter(workbook, archive).save()
    output = io.BytesIO()
    with (
        zipfile.ZipFile(raw) as source,
        zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as dest,
    ):
        for name in sorted(source.namelist()):
            payload = source.read(name)
            if name == "xl/_rels/workbook.xml.rels":
                payload = relative_worksheet_relationships(payload)
            elif name.startswith("xl/worksheets/_rels/") and name.endswith(".rels"):
                payload = relative_annotations(payload)
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            dest.writestr(info, payload)
    content = output.getvalue()
    return WorkbookArtifact(
        metadata=WorkbookMetadata(schema_version="2.1", kind="collection-intake"),
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
    )
