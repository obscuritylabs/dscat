# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Streaming Expat lexical guards; no DTD, entity, XInclude or network resolution."""

from dataclasses import dataclass
from typing import TYPE_CHECKING
from xml.parsers import expat

from dscat.intake.limits import CHUNK_BYTES, Budget, IntakeError, fail

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class XmlGuard:
    """Keep only bounded counters while Expat delivers streaming events."""

    budget: Budget
    on_start: Callable[[str, dict[str, str], int], None] | None = None
    depth: int = 0
    text_run: int = 0
    string_depth: int = 0
    string_text: int = 0

    def start(self, name: str, attributes: dict[str, str]) -> None:
        """Count structure, names and attributes before semantic handlers."""
        self.depth += 1
        self.text_run = 0
        self.budget.max_depth = max(self.depth, self.budget.max_depth)
        self.budget.check("depth", self.depth, self.budget.limits.depth)
        for value in (name, *attributes.keys(), *attributes.values()):
            self.budget.max_text = max(self.budget.max_text, len(value))
            self.budget.check("text", len(value), self.budget.limits.text)
        if name.startswith("http://www.w3.org/2001/XInclude}"):
            raise fail(code="UNSAFE_INPUT")
        self.count_element(name.rsplit("}", 1)[-1])
        if self.on_start is not None:
            self.on_start(name, attributes, self.depth)

    def count_element(self, local: str) -> None:
        """Count cells/sheets and combined rich-string text."""
        if local == "c":
            self.budget.cells += 1
            self.budget.check("cells", self.budget.cells, self.budget.limits.cells)
        if local == "sheet":
            self.budget.declared_sheets += 1
            self.budget.check(
                "sheets", self.budget.declared_sheets, self.budget.limits.sheets
            )
        if local in {"si", "is"}:
            if self.string_depth:
                raise fail(code="INVALID_WORKBOOK")
            self.string_depth = self.depth
            self.string_text = 0

    def end(self, _name: str) -> None:
        """End one element without retaining content."""
        if self.string_depth == self.depth:
            self.string_depth = 0
        self.depth -= 1
        self.text_run = 0

    def text(self, value: str) -> None:
        """Bound text runs and total text across a rich-string's child nodes."""
        self.text_run += len(value)
        self.budget.max_text = max(self.budget.max_text, self.text_run)
        self.budget.check("text", self.text_run, self.budget.limits.text)
        if self.string_depth:
            self.string_text += len(value)
            self.budget.max_text = max(self.budget.max_text, self.string_text)
            self.budget.check("text", self.string_text, self.budget.limits.text)


def forbidden(*_args: object) -> int:
    """Reject active/foreign declarations without attempting resolution."""
    raise fail(code="UNSAFE_INPUT")


def validate_xml(
    raw: bytes,
    budget: Budget,
    on_start: Callable[[str, dict[str, str], int], None] | None = None,
) -> None:
    """Count actual XML structure and text before semantic interpretation."""
    budget.check("xml", len(raw), budget.limits.xml)
    guard = XmlGuard(budget, on_start)
    parser = expat.ParserCreate(namespace_separator="}")
    parser.StartElementHandler = guard.start
    parser.EndElementHandler = guard.end
    parser.CharacterDataHandler = guard.text
    parser.StartDoctypeDeclHandler = forbidden
    parser.EntityDeclHandler = forbidden
    parser.ExternalEntityRefHandler = forbidden
    parser.SkippedEntityHandler = forbidden
    parser.UnparsedEntityDeclHandler = forbidden
    parser.NotationDeclHandler = forbidden
    parser.ProcessingInstructionHandler = forbidden
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    defer_reparse = True
    parser.SetReparseDeferralEnabled(defer_reparse)
    try:
        for offset in range(0, len(raw), CHUNK_BYTES):
            budget.check_time()
            parser.Parse(raw[offset : offset + CHUNK_BYTES])
        is_final = True
        parser.Parse(b"", is_final)
    except IntakeError:
        raise
    except expat.ExpatError:
        raise fail(code="INVALID_WORKBOOK") from None
