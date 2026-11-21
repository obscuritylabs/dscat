# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Generate a synthetic, accessible intake template; never read submissions here."""

import hashlib
import io
import zipfile
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Literal, Self
from xml.etree import ElementTree as ET

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.writer.excel import ExcelWriter
from pydantic import Field, model_validator

from dscat.models.base import Sha256, StrictModel
from dscat.models.intake import DETAIL_PROPERTIES, WorkbookMetadata
from dscat.workbook.layout import (
    ENUM_CHOICES,
    FEEDBACK_HEADER,
    KIND_CELL,
    SCHEMA_CELL,
    SHEET_HEADERS,
    TEMPLATE_ROWS,
    UNITS,
    feedback_formula,
)

if TYPE_CHECKING:
    from openpyxl.cell.cell import Cell
    from openpyxl.worksheet.worksheet import Worksheet


class Control(StrictModel):
    """A bounded authored Excel validation specification."""

    kind: Literal["list", "custom", "textLength"]
    formula: Annotated[str, Field(min_length=1, max_length=255)]
    prompt: Annotated[str, Field(min_length=1, max_length=255)]
    stop: bool = True
    maximum: str | None = None


class WorkbookArtifact(StrictModel):
    """A bounded generated workbook bound to its exact bytes and schema identity."""

    metadata: WorkbookMetadata
    content: Annotated[bytes, Field(min_length=1, max_length=32 * 1024**2)]
    sha256: Sha256

    @model_validator(mode="after")
    def match_content(self) -> Self:
        """Refuse a corrupt or mismatched generated artifact before publication."""
        if hashlib.sha256(
            self.content
        ).hexdigest() != self.sha256 or not zipfile.is_zipfile(
            io.BytesIO(self.content)
        ):
            msg = "Generated workbook integrity validation failed."
            raise ValueError(msg)
        return self


def write_text(cell: Cell, value: str) -> None:
    """Write even formula-looking or URL-looking metadata as inert text."""
    if len(value) > 32767:  # noqa: PLR2004 -- supported workbook text ceiling.
        msg = "Workbook text exceeds the supported character limit."
        raise ValueError(msg)
    cell.value = value
    cell.data_type = "s"
    cell.hyperlink = None


def add_list(
    workbook: Workbook, column: int, name: str, values: tuple[str, ...]
) -> None:
    """Keep validation lists visible and named without extra OOXML package parts."""
    sheet = workbook["Instructions"]
    letter = get_column_letter(column)
    write_text(sheet.cell(1, column), name)
    for row, value in enumerate(values, start=2):
        write_text(sheet.cell(row, column), value)
    workbook.defined_names.add(
        DefinedName(
            name, attr_text=f"'Instructions'!${letter}$2:${letter}${len(values) + 1}"
        )
    )
    sheet.column_dimensions[letter].width = 28


def add_validation(
    sheet: Worksheet,
    columns: str,
    control: Control,
) -> None:
    """Attach descriptive Excel controls without asserting validation authority."""
    validation = DataValidation(
        type=control.kind,
        formula1=control.formula,
        formula2=control.maximum,
        allow_blank=True,
    )
    validation.showInputMessage = True
    validation.promptTitle = "Metadata guidance"
    validation.prompt = control.prompt
    validation.showErrorMessage = control.stop
    validation.errorTitle = "Check this entry"
    validation.error = control.prompt
    validation.errorStyle = "stop"
    if control.kind == "textLength":
        validation.operator = "between"
    sheet.add_data_validation(validation)
    validation.add(f"{columns}2:{columns}{TEMPLATE_ROWS + 1}")


def populate_instructions(workbook: Workbook) -> None:
    """Put concise keyboard and correction guidance before every input sheet."""
    sheet = workbook.create_sheet("Instructions", 0)
    instructions = (
        (
            "Dataset metadata intake",
            "Start with Datasets; optional detail sheets may stay blank.",
        ),
        ("Workbook schema", "1.0"),
        ("Workbook kind", "dataset-intake"),
        (
            "Required core",
            (
                "Enter id, title, description and core_party for each dataset. Leave "
                "other cells blank when absent."
            ),
        ),
        (
            "Party role",
            (
                "Choose contact or owner if known. Blank means unspecified "
                "contact/owner; no accountability is inferred."
            ),
        ),
        (
            "Optional schema",
            (
                "Fields describes fields. Use one dataset_id, object_name and "
                "field_name per row; nullable uses Yes or No."
            ),
        ),
        (
            "Optional details",
            (
                "Details_Quality uses one scalar property per row. Choose section and"
                " property; group related rows with the same entry_id."
            ),
        ),
        (
            "Dataset properties",
            (
                "Use entry_id dataset for single-value identity, date, domain, "
                "determination, review, records and retention properties."
            ),
        ),
        (
            "Repeated facts",
            (
                "Use different entry IDs for repeated consumer values, conflicts, "
                "assertions, roles, services and distributions. Datasets owner/steward/"
                "maintainer cells reference matching role entry IDs for this dataset."
            ),
        ),
        (
            "Dates and numbers",
            (
                "Use YYYY-MM-DD date text and nonnegative decimal text. Capacity "
                "requires explicit units and context; Unknown is not zero."
            ),
        ),
        (
            "Keyboard navigation",
            (
                "Use Ctrl+PageDown/PageUp to change sheets, Tab/Shift+Tab between "
                "cells and Alt+Down for dropdowns in Windows Excel."
            ),
        ),
        (
            "Text feedback",
            (
                "Read the feedback column to locate missing values, duplicate IDs and"
                " date/choice corrections. No correction relies on color."
            ),
        ),
        (
            "CLI verification",
            (
                "Workbook controls are guidance. The CLI independently checks types, "
                "conflicts, references, versions and safe content before any export."
            ),
        ),
        (
            "Template capacity",
            (
                "The first 1,000 input rows have controls and feedback. Extend using "
                "Excel fill/copy as needed; the CLI enforces overall limits."
            ),
        ),
        (
            "Privacy",
            (
                "Prefer role contact details. Do not enter data samples, credentials "
                "or unnecessary personal information."
            ),
        ),
        (
            "Reference values",
            (
                "URLs are descriptive text. No hyperlink, connection, macro or "
                "endpoint test is generated."
            ),
        ),
        (
            "Version markers",
            (
                "Keep the visible schema and kind markers unchanged. Unsupported "
                "versions are refused by the CLI."
            ),
        ),
        (
            "Scope",
            (
                "Lineage, forecasting, live policy enforcement and provisioning are "
                "outside this template."
            ),
        ),
        (
            "License",
            (
                "Copyright (c) 2026 Obscurity Labs. All rights reserved. Proprietary "
                "License."
            ),
        ),
    )
    for row, (label, description) in enumerate(instructions, start=1):
        write_text(sheet.cell(row, 1), label)
        write_text(sheet.cell(row, 2), description)
        sheet.cell(row, 1).font = Font(bold=True)
        sheet.cell(row, 2).alignment = Alignment(wrap_text=True, vertical="top")
        sheet.row_dimensions[row].height = 45
    sheet.column_dimensions["A"].width = 25
    sheet.column_dimensions["B"].width = 95
    sheet.freeze_panes = "A4"
    workbook.defined_names.add(
        DefinedName(
            "dscat_workbook_schema",
            attr_text=f"'Instructions'!${SCHEMA_CELL[0]}${SCHEMA_CELL[1:]}",
        )
    )
    workbook.defined_names.add(
        DefinedName(
            "dscat_workbook_kind",
            attr_text=f"'Instructions'!${KIND_CELL[0]}${KIND_CELL[1:]}",
        )
    )
    lists = {
        "dscat_sections": tuple(DETAIL_PROPERTIES),
        "dscat_units": UNITS,
        "dscat_no_choices": ("",),
    }
    lists.update(
        {
            f"dscat_{section}_properties": tuple(sorted(properties))
            for section, properties in DETAIL_PROPERTIES.items()
        }
    )
    lists.update(
        {
            f"dscat_{section}_{prop}_values": values
            for (section, prop), values in ENUM_CHOICES.items()
        }
    )
    for column, (name, values) in enumerate(lists.items(), start=4):
        add_list(workbook, column, name, values)


def add_role_controls(sheet: Worksheet) -> None:
    """Explain the optional references without inventing party identities."""
    for column, role in zip(
        "MNO", ("accountable_owner", "steward", "maintainer"), strict=True
    ):
        add_validation(
            sheet,
            column,
            Control(
                kind="textLength",
                formula="0",
                maximum="128",
                prompt=(
                    f"Optional Details_Quality role entry_id for this dataset; "
                    f"role must be {role}."
                ),
            ),
        )


def populate_inputs(workbook: Workbook) -> None:
    """Create ordinary ranges with explicit text cells and reserved feedback."""
    for name, headers in SHEET_HEADERS.items():
        sheet = workbook.create_sheet(name)
        for column, header in enumerate((*headers, FEEDBACK_HEADER), start=1):
            write_text(sheet.cell(1, column), header)
            sheet.cell(1, column).font = Font(bold=True)
            sheet.column_dimensions[get_column_letter(column)].width = 24
        sheet.row_dimensions[1].height = 30
        sheet.freeze_panes = "E2"
        sheet.auto_filter.ref = (
            f"A1:{get_column_letter(len(headers))}{TEMPLATE_ROWS + 1}"
        )
        for row in range(2, TEMPLATE_ROWS + 2):
            for column in range(1, len(headers) + 1):
                sheet.cell(row, column).number_format = "@"
            sheet.cell(row, len(headers) + 1).value = feedback_formula(name, row)
        feedback_column = get_column_letter(len(headers) + 1)
        sheet.column_dimensions[feedback_column].width = 58
        sheet.conditional_formatting.add(
            f"{feedback_column}2:{feedback_column}{TEMPLATE_ROWS + 1}",
            FormulaRule(
                formula=[
                    (
                        f'AND({feedback_column}2<>"",'
                        f'{feedback_column}2<>"Ready for CLI validation")'
                    )
                ],
                fill=PatternFill("solid", fgColor="FFE0E0"),
            ),
        )
    datasets = workbook["Datasets"]
    for column in "ABCD":
        add_validation(
            datasets,
            column,
            Control(
                kind="textLength",
                formula="1",
                prompt="Required ID: 1-128 case-sensitive ASCII identifier characters."
                if column == "A"
                else "Required text; enter metadata without formulas.",
                maximum="128" if column == "A" else "32767",
            ),
        )
    add_validation(
        datasets,
        "E",
        Control(
            kind="list",
            formula='"contact,owner"',
            prompt="Optional: choose contact or owner; blank does not infer a role.",
        ),
    )
    add_role_controls(datasets)
    for column in "IJK":
        add_validation(
            datasets,
            column,
            Control(
                kind="custom",
                formula=(
                    f'OR({column}2="",AND(ISTEXT({column}2),LEN({column}2)=10,'
                    f'MID({column}2,5,1)="-",MID({column}2,8,1)="-"))'
                ),
                prompt="Use YYYY-MM-DD date text; feedback checks the calendar.",
            ),
        )
    add_validation(
        workbook["Fields"],
        "F",
        Control(
            kind="list",
            formula='"Yes,No"',
            prompt="Optional nullable choice: Yes or No. Blank means absent.",
        ),
    )
    details = workbook["Details_Quality"]
    add_validation(
        details,
        "B",
        Control(
            kind="list",
            formula="dscat_sections",
            prompt="Choose the supported metadata section.",
        ),
    )
    add_validation(
        details,
        "D",
        Control(
            kind="list",
            formula='INDIRECT("dscat_"&$B2&"_properties")',
            prompt="Choose a property for the selected section.",
        ),
    )
    add_validation(
        details,
        "E",
        Control(
            kind="list",
            formula='IFERROR(INDIRECT("dscat_"&$B2&"_"&$D2&"_values"),dscat_no_choices)',
            prompt=(
                "Use suggested choices when shown; otherwise enter one scalar. "
                "Read feedback and run CLI validation."
            ),
            stop=False,
        ),
    )
    add_validation(
        details,
        "F",
        Control(
            kind="list",
            formula="dscat_units",
            prompt=(
                "Capacity uses listed byte units. "
                "Assertions may use an explicitly supplied unit."
            ),
            stop=False,
        ),
    )


def relative_worksheet_relationships(payload: bytes) -> bytes:
    """Normalize absolute worksheet targets emitted by the pinned generator only."""
    root = ET.fromstring(payload)  # noqa: S314 -- self-generated XML, never intake.
    worksheets = {f"/xl/worksheets/sheet{index}.xml" for index in range(1, 5)}
    for relationship in root:
        target = relationship.attrib["Target"]
        if target in worksheets:
            relationship.set("Target", target.removeprefix("/xl/"))
        elif target.startswith("/"):
            msg = "Generator emitted an unsupported absolute relationship."
            raise ValueError(msg)
    serialized = ET.tostring(root, encoding="utf-8")
    if not isinstance(serialized, bytes):
        msg = "Generator XML serialization did not produce bytes."
        raise TypeError(msg)
    return serialized


def _create_legacy_template() -> WorkbookArtifact:
    """Build a deterministic, macro-free workbook without reading catalog input."""
    workbook = Workbook()
    workbook.remove(workbook.active)
    workbook.properties.creator = "DSCat"
    workbook.properties.lastModifiedBy = "DSCat"
    workbook.properties.created = datetime(2026, 1, 1, tzinfo=UTC)
    workbook.properties.modified = datetime(2026, 1, 1, tzinfo=UTC)
    populate_instructions(workbook)
    populate_inputs(workbook)
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        ExcelWriter(workbook, archive).save()
    deterministic = io.BytesIO()
    with (
        zipfile.ZipFile(raw) as source,
        zipfile.ZipFile(
            deterministic, "w", compression=zipfile.ZIP_DEFLATED
        ) as destination,
    ):
        for name in sorted(source.namelist()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            payload = source.read(name)
            if name == "xl/_rels/workbook.xml.rels":
                payload = relative_worksheet_relationships(payload)
            destination.writestr(info, payload)
    content = deterministic.getvalue()
    return WorkbookArtifact(
        metadata=WorkbookMetadata(schema_version="1.0", kind="dataset-intake"),
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
    )


def create_template(*, examples: bool = False) -> WorkbookArtifact:
    """Generate the collection-first workbook with optional synthetic examples."""
    from dscat.workbook.collection_generate import collection_template  # noqa: PLC0415 -- separate legacy fixtures from current rendering.

    return collection_template(examples=examples)
