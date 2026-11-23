# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Closed inert Excel table and header-note vocabulary, never general drawings."""

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from dscat.intake.limits import fail
from dscat.intake.xml import validate_xml

if TYPE_CHECKING:
    from dscat.intake.limits import Budget

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
VML = "urn:schemas-microsoft-com:vml}"
OFFICE = "urn:schemas-microsoft-com:office:office}"
EXCEL = "urn:schemas-microsoft-com:office:excel}"
REL = "http://schemas.openxmlformats.org/package/2006/relationships}"
ATTACHMENTS = {
    "table": (
        r"xl/tables/table[1-9][0-9]*\.xml",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml",
    ),
    "comments": (
        r"xl/comments/comment[1-9][0-9]*\.xml",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.comments+xml",
    ),
    "vmlDrawing": (
        r"xl/drawings/commentsDrawing[1-9][0-9]*\.vml",
        "application/vnd.openxmlformats-officedocument.vmlDrawing",
    ),
}
WORKSHEET_RELS = r"xl/worksheets/_rels/sheet[1-9][0-9]*\.xml\.rels"
FIRST_INPUT_ROW = 6
LAST_EXCEL_ROW = 1048576
NOTE_ROW = 4
COLUMN_COUNT = 30
TABLE_WIDTHS = {"AC": 29, "AD": 30}
HEADER_REF = r"(?:[A-Z]|A[ABCD])5"


def attachment_kind(name: str) -> str | None:
    """Classify only the prescribed annotation and table paths."""
    return next(
        (
            kind
            for kind, (pattern, _) in ATTACHMENTS.items()
            if re.fullmatch(pattern, name)
        ),
        None,
    )


def annotation_mime(name: str) -> str | None:
    """Return the exact MIME type for an allowed extra package part."""
    kind = attachment_kind(name)
    return ATTACHMENTS[kind][1] if kind is not None else None


@dataclass
class TableReader:
    """Collect bounded native table headers without interpreting table expressions."""

    headers: list[str] = field(default_factory=list)
    identifiers: set[str] = field(default_factory=set)
    ref: str = ""
    width: int = 0
    path: list[str] = field(default_factory=list)

    def start(self, name: str, attrs: dict[str, str], _depth: int) -> None:
        """Require one ordinary intake table, with no calculated columns or links."""
        parent = self.path[-1] if self.path else ""
        self.path.append(name)
        allowed = {
            "table": (
                {
                    "id",
                    "name",
                    "displayName",
                    "ref",
                    "headerRowCount",
                    "totalsRowShown",
                },
                "",
            ),
            "autoFilter": ({"ref"}, MAIN + "table"),
            "tableColumns": ({"count"}, MAIN + "table"),
            "tableColumn": ({"id", "name"}, MAIN + "tableColumns"),
            "tableStyleInfo": (
                {
                    "name",
                    "showFirstColumn",
                    "showLastColumn",
                    "showRowStripes",
                    "showColumnStripes",
                },
                MAIN + "table",
            ),
        }
        local = name.removeprefix(MAIN)
        if (
            not name.startswith(MAIN)
            or local not in allowed
            or attrs.keys() - allowed[local][0]
            or parent != allowed[local][1]
        ):
            raise fail(code="UNSUPPORTED_WORKBOOK_PART")
        if local == "table":
            self.ref = attrs.get("ref", "")
            match = re.fullmatch(r"A5:(AC|AD)([1-9][0-9]{0,6})", self.ref)
            if (
                attrs.get("name") != "IntakeEntries"
                or attrs.get("displayName") != "IntakeEntries"
                or match is None
                or not FIRST_INPUT_ROW <= int(match[2]) <= LAST_EXCEL_ROW
                or attrs.get("headerRowCount", "1") != "1"
            ):
                raise fail(code="INVALID_WORKBOOK")
            self.width = TABLE_WIDTHS[match[1]]
        elif (local == "autoFilter" and attrs.get("ref") != self.ref) or (
            local == "tableColumns" and attrs.get("count") != str(self.width)
        ):
            raise fail(code="INVALID_WORKBOOK")
        elif local == "tableColumn":
            identifier = attrs.get("id", "")
            if (
                not bool(attrs.get("name"))
                or identifier in self.identifiers
                or re.fullmatch(r"[1-9][0-9]*", identifier) is None
            ):
                raise fail(code="INVALID_WORKBOOK")
            self.identifiers.add(identifier)
            self.headers.append(attrs["name"])

    def end(self, _name: str, _depth: int) -> None:
        """Release the current lexical path."""
        self.path.pop()


def table_headers(content: bytes, budget: Budget) -> list[str]:
    """Validate table grammar and return the exact declared header order."""
    reader = TableReader()
    validate_xml(content, budget, reader.start, on_end=reader.end)
    if len(reader.headers) != reader.width or len(set(reader.headers)) != reader.width:
        raise fail(code="INVALID_WORKBOOK")
    return reader.headers


@dataclass
class CommentReader:
    """Accept only bounded plain header notes, never threaded or active content."""

    refs: set[str] = field(default_factory=set)
    path: list[str] = field(default_factory=list)

    def start(self, name: str, attrs: dict[str, str], _depth: int) -> None:
        """Restrict note elements, attributes, locations and nesting."""
        parent = self.path[-1] if self.path else ""
        self.path.append(name)
        grammar = {
            "comments": ("", set()),
            "authors": (MAIN + "comments", set()),
            "author": (MAIN + "authors", set()),
            "commentList": (MAIN + "comments", set()),
            "comment": (MAIN + "commentList", {"ref", "authorId", "shapeId"}),
            "text": (MAIN + "comment", set()),
            "t": (MAIN + "text", {"http://www.w3.org/XML/1998/namespace}space"}),
        }
        local = name.removeprefix(MAIN)
        if (
            not name.startswith(MAIN)
            or local not in grammar
            or parent != grammar[local][0]
            or attrs.keys() - grammar[local][1]
        ):
            raise fail(code="UNSUPPORTED_WORKBOOK_PART")
        if local == "comment":
            ref = attrs.get("ref", "")
            if (
                re.fullmatch(HEADER_REF, ref) is None
                or ref in self.refs
                or attrs.get("authorId") != "0"
            ):
                raise fail(code="INVALID_WORKBOOK")
            self.refs.add(ref)

    def end(self, _name: str, _depth: int) -> None:
        """Release the current lexical path."""
        self.path.pop()


@dataclass
class NoteReader:
    """Constrain VML to inert note rectangles with primitive geometry only."""

    path: list[str] = field(default_factory=list)
    anchors: set[tuple[int, int]] = field(default_factory=set)
    fragments: list[str] = field(default_factory=list)
    row: int | None = None
    column: int | None = None

    def start(self, name: str, attrs: dict[str, str], _depth: int) -> None:
        """Reject links, scripts, event handlers, image fills and arbitrary shapes."""
        parent = self.path[-1] if self.path else ""
        grammar = {
            "xml": ("", set()),
            OFFICE + "shapelayout": ("xml", {VML + "ext"}),
            OFFICE + "idmap": (OFFICE + "shapelayout", {VML + "ext", "data"}),
            VML + "shapetype": ("xml", {"id", "coordsize", OFFICE + "spt", "path"}),
            VML + "stroke": (VML + "shapetype", {"joinstyle"}),
            VML + "shape": (
                "xml",
                {
                    "type",
                    "style",
                    "fillcolor",
                    OFFICE + "insetmode",
                    "id",
                    "strokecolor",
                },
            ),
            VML + "fill": (VML + "shape", {"color2"}),
            VML + "shadow": (VML + "shape", {"color", "obscured"}),
            VML + "textbox": (VML + "shape", {"style"}),
            "div": (VML + "textbox", {"style"}),
            EXCEL + "ClientData": (VML + "shape", {"ObjectType"}),
        }
        for local in (
            "MoveWithCells",
            "SizeWithCells",
            "AutoFill",
            "Row",
            "Column",
            "Anchor",
            "Visible",
            "Locked",
            "LockText",
        ):
            grammar[EXCEL + local] = (EXCEL + "ClientData", set())
        if name == VML + "path":
            valid = parent in {
                VML + "shape",
                VML + "shapetype",
            } and not attrs.keys() - {"gradientshapeok", OFFICE + "connecttype"}
        else:
            valid = (
                name in grammar
                and parent == grammar[name][0]
                and not attrs.keys() - grammar[name][1]
            )
        if not valid or any(
            re.fullmatch(r"[-#A-Za-z0-9_:;., %]*", v) is None for v in attrs.values()
        ):
            raise fail(code="UNSUPPORTED_WORKBOOK_PART")
        if (
            (name == VML + "shape" and attrs.get("type") != "#_x0000_t202")
            or (name == VML + "shapetype" and attrs.get("id") != "_x0000_t202")
            or (name == EXCEL + "ClientData" and attrs.get("ObjectType") != "Note")
        ):
            raise fail(code="UNSUPPORTED_WORKBOOK_PART")
        if name == VML + "shape":
            self.row = self.column = None
        self.path.append(name)
        self.fragments = []

    def text(self, value: str) -> None:
        """Keep only small primitive note positioning values."""
        self.fragments.append(value)

    def end(self, name: str, _depth: int) -> None:
        """Validate unique header-cell anchors before accepting a note shape."""
        text = "".join(self.fragments).strip()
        if name in {EXCEL + "Row", EXCEL + "Column"}:
            if re.fullmatch(r"[0-9]{1,2}", text) is None:
                raise fail(code="INVALID_WORKBOOK")
            if name == EXCEL + "Row":
                if self.row is not None:
                    raise fail(code="INVALID_WORKBOOK")
                self.row = int(text)
            else:
                if self.column is not None:
                    raise fail(code="INVALID_WORKBOOK")
                self.column = int(text)
        elif name == VML + "shape":
            if (
                self.row != NOTE_ROW
                or self.column is None
                or not 0 <= self.column < COLUMN_COUNT
                or (self.row, self.column) in self.anchors
            ):
                raise fail(code="INVALID_WORKBOOK")
            self.anchors.add((self.row, self.column))
        elif text and (
            name
            not in {
                EXCEL + "AutoFill",
                EXCEL + "Anchor",
                EXCEL + "Locked",
                EXCEL + "LockText",
            }
            or re.fullmatch(r"[0-9, FalseTruetruefals]*", text) is None
        ):
            raise fail(code="UNSUPPORTED_WORKBOOK_PART")
        self.path.pop()
        self.fragments = []


def note_refs(comments: bytes, drawing: bytes, budget: Budget) -> None:
    """Require each comment to have exactly one matching header note anchor."""
    reader = CommentReader()
    validate_xml(comments, budget, reader.start, on_end=reader.end)
    notes = NoteReader()
    validate_xml(drawing, budget, notes.start, on_end=notes.end, on_text=notes.text)

    def ref(column: int) -> str:
        return (chr(65 + column) if column < 26 else "A" + chr(65 + column - 26)) + "5"  # noqa: PLR2004 -- Excel column encoding.

    if reader.refs != {ref(column) for _, column in notes.anchors}:
        raise fail(code="INVALID_WORKBOOK")
