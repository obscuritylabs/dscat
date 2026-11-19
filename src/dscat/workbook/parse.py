# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Bounded worksheet events and strict schema 1.0 intake rows; no formula execution."""

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated, Literal, Protocol

from pydantic import Field, ValidationError

from dscat.intake.limits import Budget, DiagnosticCollector, fail
from dscat.intake.xml import validate_xml
from dscat.models.base import StrictModel
from dscat.models.diagnostics import Diagnostic, Expected
from dscat.models.intake import (
    DatasetRow,
    DetailRow,
    FieldRow,
    IntakeBatch,
    SourceLocation,
    WorkbookMetadata,
)
from dscat.normalization import normalize_text
from dscat.workbook.layout import (
    DATASET_HEADERS,
    DETAIL_HEADERS,
    FEEDBACK_HEADER,
    FIELD_HEADERS,
)

if TYPE_CHECKING:
    from dscat.intake.archive import SafeArchive, XmlPart
    from dscat.models.diagnostics import Sheet


FIELD_EXPECTED: dict[str, Expected] = {
    "id": "identifier",
    "dataset_id": "identifier",
    "entry_id": "identifier",
    "core_role": "core_role",
    "nullable": "nullable",
    "inventory_added": "date",
    "metadata_reviewed": "date",
    "dataset_modified": "date",
    "owner": "role_reference",
    "steward": "role_reference",
    "maintainer": "role_reference",
}

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
OFFICE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
MAX_SHARED_INDEX_DIGITS = 10
SCHEMA_NAMES = {
    "dscat_workbook_schema": "'Instructions'!$B$2",
    "dscat_workbook_kind": "'Instructions'!$B$3",
}
TABLE_HEADERS = {
    "Datasets": DATASET_HEADERS,
    "Fields": FIELD_HEADERS,
    "Details_Quality": DETAIL_HEADERS,
}
REQUIRED_HEADERS = {
    "Datasets": frozenset(DATASET_HEADERS[:4]),
    "Fields": frozenset(FIELD_HEADERS[:4]),
    "Details_Quality": frozenset(DETAIL_HEADERS[:5]),
}


class Cell(StrictModel):
    """One scalar cell with formula/error status retained outside its text."""

    row: Annotated[int, Field(ge=1, le=1048576)]
    column: Annotated[int, Field(ge=1, le=16384)]
    text: Annotated[str, Field(max_length=32767)] = ""
    formula: str | None = None
    error: bool = False


class SheetBinding(StrictModel):
    """One unique workbook sheet name and local relationship identity."""

    name: Annotated[str, Field(min_length=1, max_length=31)]
    relationship_id: str
    state: Literal["visible", "hidden", "veryHidden"] = "visible"


class Events(Protocol):
    """Only bounded lexical events cross into the semantic worksheet adapters."""

    def start(self, name: str, attributes: dict[str, str], depth: int, /) -> None:
        """Consume a start event after lexical counters."""
        ...

    def end(self, name: str, depth: int, /) -> None:
        """Consume one end event."""
        ...

    def text(self, value: str, /) -> None:
        """Consume bounded text without interpreting it as code."""
        ...


def read_document(part: XmlPart, budget: Budget, events: Events) -> None:
    """Reuse the guarded parser, including declaration/entity and byte ceilings."""
    validate_xml(
        part.content, budget, events.start, on_end=events.end, on_text=events.text
    )


@dataclass
class WorkbookEvents:
    """Read sheet bindings and global version markers without a workbook library."""

    sheets: list[SheetBinding] = field(default_factory=list)
    names: dict[str, str] = field(default_factory=dict)
    active_name: str | None = None
    fragments: list[str] = field(default_factory=list)
    path: list[str] = field(default_factory=list)

    def start(self, name: str, attributes: dict[str, str], depth: int) -> None:
        """Require transitional OOXML and unambiguous sheet/marker declarations."""
        self.path.append(name)
        if depth == 1 and name != MAIN + "workbook":
            raise fail(code="INVALID_WORKBOOK")
        if name == MAIN + "sheet":
            if self.path != [MAIN + "workbook", MAIN + "sheets", MAIN + "sheet"]:
                raise fail(code="INVALID_WORKBOOK")
            binding = SheetBinding.model_validate(
                {
                    "name": attributes.get("name"),
                    "relationship_id": attributes.get(OFFICE_REL + "id"),
                    "state": attributes.get("state", "visible"),
                }
            )
            if any(
                item.name == binding.name
                or item.relationship_id == binding.relationship_id
                for item in self.sheets
            ):
                raise fail(code="INVALID_WORKBOOK")
            self.sheets.append(binding)
        elif name == MAIN + "definedName" and attributes.get("name") in SCHEMA_NAMES:
            if self.path != [
                MAIN + "workbook",
                MAIN + "definedNames",
                MAIN + "definedName",
            ]:
                raise fail(code="INVALID_WORKBOOK")
            marker = attributes["name"]
            if (
                marker in self.names
                or "localSheetId" in attributes
                or attributes.get("hidden", "0") not in {"0", "false"}
            ):
                raise fail(code="INVALID_WORKBOOK")
            self.active_name = marker
            self.fragments = []

    def end(self, name: str, _depth: int) -> None:
        """Retain only explicitly recognized marker targets."""
        self.path.pop()
        if name == MAIN + "definedName" and self.active_name is not None:
            target = "".join(self.fragments)
            expected = SCHEMA_NAMES[self.active_name]
            self.names[self.active_name] = (
                expected
                if target == expected.replace("'Instructions'", "Instructions")
                else target
            )
            self.active_name = None

    def text(self, value: str) -> None:
        """Collect text only while inside a supported marker declaration."""
        if self.active_name is not None:
            self.fragments.append(value)


@dataclass
class StringEvents:
    """Resolve OOXML shared strings without formatting-based type inference."""

    strings: list[str] = field(default_factory=list)
    fragments: list[str] = field(default_factory=list)
    in_text: bool = False
    phonetic_depth: int = 0

    def start(self, name: str, _attributes: dict[str, str], depth: int) -> None:
        """Require the shared-string root and collect text runs only."""
        if depth == 1 and name != MAIN + "sst":
            raise fail(code="INVALID_WORKBOOK")
        if name == MAIN + "si":
            self.fragments = []
        if name == MAIN + "rPh":
            self.phonetic_depth += 1
        self.in_text = name == MAIN + "t" and self.phonetic_depth == 0

    def end(self, name: str, _depth: int) -> None:
        """Combine rich runs into one scalar in their explicit order."""
        if name == MAIN + "rPh":
            self.phonetic_depth -= 1
        if name == MAIN + "si":
            self.strings.append("".join(self.fragments))
        self.in_text = False

    def text(self, value: str) -> None:
        """Preserve string text exactly until property-specific normalization."""
        if self.in_text:
            self.fragments.append(value)


def coordinate(value: str) -> tuple[int, int]:
    """Decode an explicit XLSX coordinate without allocating a rectangular grid."""
    match = re.fullmatch(r"([A-Z]{1,3})([1-9][0-9]{0,6})", value)
    if match is None:
        raise fail(code="INVALID_WORKBOOK")
    column = 0
    for char in match[1]:
        column = column * 26 + ord(char) - ord("A") + 1
    row = int(match[2])
    # The strict cell model applies the actual worksheet coordinate bounds.
    return row, column


@dataclass
class WorksheetEvents:
    """Read sparse scalar cells and keep formulas separate from cached values."""

    strings: list[str]
    cells: dict[tuple[int, int], Cell] = field(default_factory=dict)
    active: dict[str, object] | None = None
    kind: str = "n"
    collecting: str = ""
    fragments: list[str] = field(default_factory=list)
    formula_fragments: list[str] = field(default_factory=list)
    seen_value: bool = False
    seen_formula: bool = False
    path: list[str] = field(default_factory=list)
    row_number: int | None = None

    def start(self, name: str, attributes: dict[str, str], depth: int) -> None:
        """Require real worksheet cells, explicit coordinates and supported types."""
        self.path.append(name)
        if depth == 1 and name != MAIN + "worksheet":
            raise fail(code="INVALID_WORKBOOK")
        if name == MAIN + "row":
            raw = attributes.get("r")
            if raw is not None and re.fullmatch(r"[1-9][0-9]{0,6}", raw) is None:
                raise fail(code="INVALID_WORKBOOK")
            self.row_number = int(raw) if raw is not None else None
        if name == MAIN + "c":
            if self.path != [
                MAIN + "worksheet",
                MAIN + "sheetData",
                MAIN + "row",
                MAIN + "c",
            ]:
                raise fail(code="INVALID_WORKBOOK")
            row, column = coordinate(attributes.get("r", ""))
            if (self.row_number is not None and row != self.row_number) or (
                row,
                column,
            ) in self.cells:
                raise fail(code="INVALID_WORKBOOK")
            self.active = {"row": row, "column": column}
            self.kind = attributes.get("t", "n")
            if self.kind not in {"n", "s", "inlineStr", "str", "b", "d", "e"}:
                raise fail(code="INVALID_WORKBOOK")
            self.fragments, self.formula_fragments = [], []
            self.seen_value = self.seen_formula = False
        elif self.active is not None:
            self.start_value(name)

    def start_value(self, name: str) -> None:
        """Reject conflicting values and track formula text independently."""
        if name == MAIN + "f":
            if self.seen_formula:
                raise fail(code="INVALID_WORKBOOK")
            self.seen_formula = True
            self.collecting = "formula"
        elif name in {MAIN + "v", MAIN + "t"}:
            if MAIN + "rPh" in self.path:
                self.collecting = ""
                return
            if (
                name == MAIN + "v" and (self.seen_value or self.kind == "inlineStr")
            ) or (name == MAIN + "t" and self.kind != "inlineStr"):
                raise fail(code="INVALID_WORKBOOK")
            self.seen_value = True
            self.collecting = "value"

    def end(self, name: str, _depth: int) -> None:
        """Finish one sparse typed cell without evaluating formula/cache pairs."""
        self.path.pop()
        if name == MAIN + "c" and self.active is not None:
            text = "".join(self.fragments)
            if self.kind == "s":
                if (
                    len(text) > MAX_SHARED_INDEX_DIGITS
                    or re.fullmatch(r"[0-9]+", text) is None
                    or int(text) >= len(self.strings)
                ):
                    raise fail(code="INVALID_WORKBOOK")
                text = self.strings[int(text)]
            fields = self.active | {"text": text, "error": self.kind in {"e", "b"}}
            if self.seen_formula:
                fields["formula"] = "".join(self.formula_fragments)
            cell = Cell.model_validate(fields)
            self.cells[(cell.row, cell.column)] = cell
            self.active = None
        if name in {MAIN + "v", MAIN + "t", MAIN + "f", MAIN + "c"}:
            self.collecting = ""

    def text(self, value: str) -> None:
        """Collect a scalar only in a cell value or its explicit formula node."""
        if self.collecting == "formula":
            self.formula_fragments.append(value)
        elif self.collecting == "value":
            self.fragments.append(value)


def marker_metadata(
    workbook: WorkbookEvents, sheets: dict[str, dict[tuple[int, int], Cell]]
) -> WorkbookMetadata:
    """Verify visible named cells and literal markers before processing tables."""
    if (
        workbook.names != SCHEMA_NAMES
        or not {"Instructions", "Datasets"} <= sheets.keys()
    ):
        raise fail(code="INVALID_WORKBOOK")
    if (
        next(item for item in workbook.sheets if item.name == "Instructions").state
        != "visible"
    ):
        raise fail(code="INVALID_WORKBOOK")
    instructions = sheets["Instructions"]
    values: list[str] = []
    for row in (2, 3):
        cell = instructions.get((row, 2))
        if cell is None or cell.formula is not None or cell.error:
            raise fail(code="INVALID_WORKBOOK")
        values.append(cell.text)
    if values[0] != "1.0":
        raise fail(code="UNSUPPORTED_VERSION")
    return WorkbookMetadata.model_validate(
        {"schema_version": values[0], "kind": values[1]}
    )


def table_headers(
    cells: dict[tuple[int, int], Cell],
    sheet: Sheet,
    collector: DiagnosticCollector,
    source_token: int,
) -> dict[int, str]:
    """Use exact header names and reject duplicates, missing core and unknown names."""
    allowed = TABLE_HEADERS[sheet]
    headers = {
        column: cell.text
        for (row, column), cell in cells.items()
        if row == 1 and cell.text
    }
    if (
        len(set(headers.values())) != len(headers)
        or any(value not in (*allowed, FEEDBACK_HEADER) for value in headers.values())
        or not REQUIRED_HEADERS[sheet] <= set(headers.values())
        or any(
            cell.formula is not None or cell.error
            for (row, _column), cell in cells.items()
            if row == 1
        )
    ):
        collector.add(
            fail(
                code="INVALID_WORKBOOK", source_token=source_token
            ).diagnostic.model_copy(update={"sheet": sheet, "row": 1})
        )
        return {}
    return headers


def data_rows(
    cells: dict[tuple[int, int], Cell],
    headers: dict[int, str],
    sheet: Sheet,
    source_token: int,
    collector: DiagnosticCollector,
) -> list[tuple[SourceLocation, dict[str, object]]]:
    """Collect nonblank rows and reject formulas even when their cache appears blank."""
    rows: dict[int, dict[str, object]] = {}
    invalid: set[int] = set()
    for (row, column), cell in sorted(cells.items()):
        if row == 1:
            continue
        header = headers.get(column)
        if header == FEEDBACK_HEADER:
            continue
        if cell.formula is not None or cell.error or (cell.text and header is None):
            collector.add(
                fail(
                    code="INVALID_METADATA", source_token=source_token
                ).diagnostic.model_copy(
                    update={"sheet": sheet, "row": row, "column": column}
                )
            )
            invalid.add(row)
        elif header is not None and normalize_text(cell.text):
            rows.setdefault(row, {})[header] = cell.text
    return [
        (SourceLocation(source_token=source_token, sheet=sheet, row=row), values)
        for row, values in sorted(rows.items())
        if row not in invalid
    ]


def located_rows[T: (DatasetRow, FieldRow, DetailRow)](
    cells: dict[tuple[int, int], Cell],
    sheet: Sheet,
    model: type[T],
    source_token: int,
    collector: DiagnosticCollector,
) -> list[T]:
    """Validate each row independently and translate schema errors to safe locations."""
    headers = table_headers(cells, sheet, collector, source_token)
    if not headers:
        return []
    result: list[T] = []
    for row_location, values in data_rows(
        cells, headers, sheet, source_token, collector
    ):
        location = row_location
        if model is DetailRow:
            location = location.model_copy(
                update={
                    "column": next(
                        column for column, name in headers.items() if name == "value"
                    )
                }
            )
        if model is FieldRow and "nullable" in values:
            raw = values["nullable"]
            values["nullable"] = (
                {"Yes": True, "No": False}.get(raw, raw)
                if isinstance(raw, str)
                else raw
            )
        try:
            result.append(model.model_validate(values | {"location": location}))
        except ValidationError as error:
            for detail in error.errors(include_input=False, include_context=False):
                field_name = detail["loc"][0] if detail["loc"] else ""
                column = next(
                    (column for column, name in headers.items() if name == field_name),
                    None,
                )
                expected = FIELD_EXPECTED.get(
                    str(field_name), "detail_property" if model is DetailRow else "text"
                )
                fields: dict[str, object] = {
                    "sheet": sheet,
                    "row": location.row,
                    "expected": expected,
                }
                if column is not None:
                    fields["column"] = column
                collector.add(
                    fail(
                        code="INVALID_METADATA", source_token=source_token
                    ).diagnostic.model_copy(update=fields)
                )
    return result


def parse_parts(archive: SafeArchive, source_token: int, budget: Budget) -> IntakeBatch:
    """Parse only a preflighted package inside its guarded workbook process."""
    parts = {part.name: part for part in archive.parts}
    workbook = WorkbookEvents()
    read_document(parts["xl/workbook.xml"], budget, workbook)
    strings = StringEvents()
    if "xl/sharedStrings.xml" in parts:
        read_document(parts["xl/sharedStrings.xml"], budget, strings)
    sheets: dict[str, dict[tuple[int, int], Cell]] = {}
    used: set[str] = set()
    for binding in workbook.sheets:
        target = next(
            (
                item.target
                for item in archive.relationships
                if item.source == "workbook"
                and item.kind == "worksheet"
                and item.id == binding.relationship_id
            ),
            None,
        )
        if target is None:
            raise fail(code="INVALID_WORKBOOK")
        used.add(target)
        worksheet = WorksheetEvents(strings.strings)
        read_document(parts[target], budget, worksheet)
        sheets[binding.name] = worksheet.cells
    if used != {
        item.target for item in archive.relationships if item.kind == "worksheet"
    }:
        raise fail(code="INVALID_WORKBOOK")
    metadata = marker_metadata(workbook, sheets)
    collector = DiagnosticCollector()
    for name, cells in sheets.items():
        if name not in {*TABLE_HEADERS, "Instructions"}:
            headers = {cell.text for (row, _column), cell in cells.items() if row == 1}
            if name == "Lineage" or any(
                required <= headers for required in REQUIRED_HEADERS.values()
            ):
                raise fail(code="UNSUPPORTED_VERSION")
            collector.add(
                Diagnostic(
                    code="IGNORED_WORKSHEET",
                    severity="warning",
                    message_key="review_scope",
                    source_token=source_token,
                    check_state="unperformed",
                )
            )
    datasets = located_rows(
        sheets["Datasets"], "Datasets", DatasetRow, source_token, collector
    )
    fields = (
        located_rows(sheets["Fields"], "Fields", FieldRow, source_token, collector)
        if "Fields" in sheets
        else []
    )
    details = (
        located_rows(
            sheets["Details_Quality"],
            "Details_Quality",
            DetailRow,
            source_token,
            collector,
        )
        if "Details_Quality" in sheets
        else []
    )
    keys: set[tuple[str, str, str, str]] = set()
    unique: list[DetailRow] = []
    for row in details:
        key = row.dataset_id, row.section, row.entry_id, row.property
        if key in keys:
            collector.add(
                fail(
                    code="INVALID_METADATA", source_token=source_token
                ).diagnostic.model_copy(
                    update={"sheet": row.location.sheet, "row": row.location.row}
                )
            )
        else:
            unique.append(row)
            keys.add(key)
    return IntakeBatch(
        metadata=metadata,
        datasets=datasets,
        fields=fields,
        details=unique,
        diagnostics=collector.items,
        has_errors=collector.has_errors,
    )


def parse_workbook(
    archive: SafeArchive, source_token: int, budget: Budget
) -> IntakeBatch:
    """Translate malformed structured workbook metadata to a fixed input failure."""
    try:
        return parse_parts(archive, source_token, budget)
    except ValidationError:
        raise fail(code="INVALID_WORKBOOK", source_token=source_token) from None
