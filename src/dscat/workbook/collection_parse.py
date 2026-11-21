# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Parse the collection table using already bounded inert XML cell events."""

import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from pydantic import ValidationError

from dscat.intake.annotations import table_headers
from dscat.intake.limits import DiagnosticCollector, fail
from dscat.models.intake import (
    CollectionRow,
    IntakeBatch,
    SourceLocation,
    WorkbookMetadata,
)
from dscat.normalization import normalize_text, parse_date
from dscat.workbook.collection_layout import FIELD_NAMES, HEADERS

if TYPE_CHECKING:
    from dscat.intake.archive import SafeArchive
    from dscat.intake.limits import Budget
    from dscat.workbook.parse import Cell, WorkbookEvents

MARKERS = {
    "dscat_workbook_schema": "'Start here'!$D$1",
    "dscat_workbook_kind": "'Start here'!$D$2",
}
MAX_SERIAL = 3652059
LEAP_DAY = 60
MAX_DIGITS = 28
MIN_EXPONENT = -9
HEADER_ROW = 5
FIRST_ROW = 6
NUMERIC = {"current_value", "per_run_value", "typical_runs", "retention_days"}


def completed_date(cell: Cell, *, date1904: bool) -> date:
    """Decode only date cells, refusing Excel's fictitious leap day and times."""
    value = normalize_text(cell.text)
    if cell.kind == "n":
        serial = Decimal(value)
        if (
            not serial.is_finite()
            or serial != serial.to_integral_value()
            or serial < 0
            or serial > MAX_SERIAL
            or (not date1904 and serial in {0, LEAP_DAY})
        ):
            msg = "Invalid Excel date serial."
            raise ValueError(msg)
        days = int(serial)
        if not date1904 and days > LEAP_DAY:
            days -= 1
        return (
            date(1904, 1, 1) + timedelta(days=days)
            if date1904
            else date(1899, 12, 31) + timedelta(days=days)
        )
    if cell.kind == "d":
        match = re.fullmatch(
            r"([0-9]{4}-[0-9]{2}-[0-9]{2})(?:T00:00:00(?:\.0+)?Z?)?", value
        )
        if match is None:
            msg = "Expected a date or midnight date representation."
            raise ValueError(msg)
        value = match[1]
    return parse_date(value)


def numeric_text(cell: Cell) -> str:
    """Expand bounded numeric-cell exponents while rejecting exponent text."""
    value = normalize_text(cell.text)
    if cell.kind != "n":
        return value
    number = Decimal(value)
    exponent = number.as_tuple().exponent
    if (
        not isinstance(exponent, int)
        or not number.is_finite()
        or number.adjusted() > MAX_DIGITS
        or exponent < MIN_EXPONENT
    ):
        msg = "Numeric value exceeds supported precision."
        raise ValueError(msg)
    return format(number, "f")


def metadata(
    workbook: WorkbookEvents, sheets: dict[str, dict[tuple[int, int], Cell]]
) -> WorkbookMetadata:
    """Require exact visible current marker bindings and matching artifact kind."""
    if (
        workbook.names != MARKERS
        or not {"Start here", "Intake"} <= sheets.keys()
        or any(
            s.state != "visible"
            for s in workbook.sheets
            if s.name in {"Start here", "Intake"}
        )
    ):
        raise fail(code="INVALID_WORKBOOK")
    marker = sheets["Start here"]
    values = []
    for coordinate in [(1, 4), (2, 4)]:
        cell = marker.get(coordinate)
        if cell is None or cell.formula is not None or cell.error:
            raise fail(code="INVALID_WORKBOOK")
        values.append(cell.text)
    if values[0] != "2.0":
        raise fail(code="UNSUPPORTED_VERSION")
    return WorkbookMetadata.model_validate({"schema_version": "2.0", "kind": values[1]})


def parse_row(
    cells: dict[int, Cell],
    headers: dict[int, str],
    location: SourceLocation,
    collector: DiagnosticCollector,
    *,
    date1904: bool,
) -> CollectionRow | None:
    """Collect every bad cell and required-field error without echoing values."""
    values: dict[str, object] = {}
    bad = False
    source_token, row = location.source_token, location.row
    for column, cell in cells.items():
        field = headers.get(column)
        if (
            cell.formula is not None
            or cell.error
            or (bool(cell.text) and field is None)
        ):
            collector.add(
                fail(
                    code="INVALID_METADATA", source_token=source_token
                ).diagnostic.model_copy(
                    update={"sheet": "Intake", "row": row, "column": column}
                )
            )
            bad = True
        elif field is not None and normalize_text(cell.text):
            try:
                values[field] = (
                    completed_date(cell, date1904=date1904)
                    if field == "completed_on"
                    else numeric_text(cell)
                    if field in NUMERIC
                    else cell.text
                )
            except ValueError, OverflowError, InvalidOperation:
                collector.add(
                    fail(
                        code="INVALID_METADATA", source_token=source_token
                    ).diagnostic.model_copy(
                        update={
                            "sheet": "Intake",
                            "row": row,
                            "column": column,
                            "expected": "date"
                            if field == "completed_on"
                            else "quantity",
                        }
                    )
                )
                bad = True
    try:
        result = CollectionRow.model_validate(
            values
            | {
                "location": location,
                "columns": {field: column for column, field in headers.items()},
            }
        )
    except ValidationError as error:
        for detail in error.errors(include_input=False, include_context=False):
            key = str(detail["loc"][0]) if detail["loc"] else ""
            column = next((c for c, f in headers.items() if f == key), 1)
            collector.add(
                fail(
                    code="INVALID_METADATA", source_token=source_token
                ).diagnostic.model_copy(
                    update={
                        "sheet": "Intake",
                        "row": row,
                        "column": column,
                        "expected": "date" if key == "completed_on" else "text",
                    }
                )
            )
        return None
    return None if bad else result


def parse_collections(
    archive: SafeArchive,
    workbook: WorkbookEvents,
    sheets: dict[str, dict[tuple[int, int], Cell]],
    source_token: int,
    budget: Budget,
) -> IntakeBatch:
    """Read every bounded row, independently of the visible table's stored range."""
    version = metadata(workbook, sheets)
    collector = DiagnosticCollector()
    cells = sheets["Intake"]
    actual = {
        c: cell.text for (r, c), cell in cells.items() if r == HEADER_ROW and cell.text
    }
    if (
        sorted(actual) != list(range(1, len(HEADERS) + 1))
        or len(actual) != len(HEADERS)
        or set(actual.values()) != set(HEADERS)
        or any(
            cell.formula is not None or cell.error
            for (r, _), cell in cells.items()
            if r == HEADER_ROW
        )
    ):
        collector.add(
            fail(
                code="INVALID_WORKBOOK", source_token=source_token
            ).diagnostic.model_copy(update={"sheet": "Intake", "row": 5})
        )
        return IntakeBatch(
            metadata=version,
            datasets=[],
            fields=[],
            details=[],
            diagnostics=collector.items,
            has_errors=True,
        )
    check_tables(archive, workbook, actual, budget)
    headers = {c: FIELD_NAMES[HEADERS.index(h)] for c, h in actual.items()}
    grouped: dict[int, dict[int, Cell]] = {}
    for (r, c), cell in sorted(cells.items()):
        if r >= FIRST_ROW and (
            normalize_text(cell.text) or cell.formula is not None or cell.error
        ):
            grouped.setdefault(r, {})[c] = cell
    rows = []
    for r, group in grouped.items():
        parsed = parse_row(
            group,
            headers,
            SourceLocation(source_token=source_token, sheet="Intake", row=r),
            collector,
            date1904=workbook.date1904,
        )
        if parsed is not None:
            rows.append(parsed)
    for _name in sheets.keys() - {"Start here", "Intake"}:
        collector.add(
            fail(code="UNSUPPORTED_VERSION", source_token=source_token).diagnostic
        )
    return IntakeBatch(
        metadata=version,
        datasets=[],
        fields=[],
        details=[],
        collections=rows,
        diagnostics=collector.items,
        has_errors=collector.has_errors,
    )


def check_tables(
    archive: SafeArchive,
    workbook: WorkbookEvents,
    actual: dict[int, str],
    budget: Budget,
) -> None:
    """Require table and worksheet header order to agree for the intake owner."""
    parts = {p.name: p for p in archive.parts}
    intake_owner = next(
        s.relationship_id for s in workbook.sheets if s.name == "Intake"
    )
    target = next(
        r.target
        for r in archive.relationships
        if r.kind == "worksheet" and r.id == intake_owner
    )
    for relation in archive.relationships:
        if relation.source == "worksheet":
            if relation.owner != target:
                raise fail(code="INVALID_WORKBOOK")
            if relation.kind == "table" and table_headers(
                parts[relation.target].content, budget
            ) != [actual[c] for c in sorted(actual)]:
                raise fail(code="INVALID_WORKBOOK")
