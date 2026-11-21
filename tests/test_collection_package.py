# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Exercise closed native-table and header-note package additions."""

import io
import zipfile
from xml.etree import ElementTree as ET

import pytest
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.worksheet.table import Table

from dscat.intake.archive import read_archive
from dscat.intake.limits import Budget, IntakeError


def package() -> dict[str, bytes]:
    """Create only trusted local test output, with inert header comments."""
    w = Workbook()
    w.active.title = "Start here"
    s = w.create_sheet("Intake")
    for c in range(1, 30):
        s.cell(5, c, f"Header {c}").comment = Comment(
            "Synthetic help", "Example author"
        )
    s.add_table(Table(displayName="IntakeEntries", ref="A5:AC205"))
    out = io.BytesIO()
    w.save(out)
    with zipfile.ZipFile(out) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    for name, data in list(parts.items()):
        if name.endswith(".rels"):
            root = ET.fromstring(data)  # noqa: S314 -- trusted locally authored fixture.
            for r in root:
                target = r.attrib["Target"]
                if target.startswith("/xl/"):
                    r.set(
                        "Target",
                        ("../" if "worksheets/_rels/" in name else "")
                        + target.removeprefix("/xl/"),
                    )
            parts[name] = ET.tostring(root)
    return parts


def packed(parts: dict[str, bytes]) -> bytes:
    """Serialize authored mutations without bypassing normal archive validation."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for n, b in parts.items():
            z.writestr(n, b)
    return out.getvalue()


def test_inert_native_package() -> None:
    """Accept only the closed owned table/comment/note relationships."""
    parsed = read_archive(packed(package()), Budget())
    assert len([r for r in parsed.relationships if r.source == "worksheet"]) == len(
        {"table", "comments", "vmlDrawing"}
    )


@pytest.mark.parametrize(
    ("part", "old", "new"),
    [
        (
            "xl/drawings/commentsDrawing1.vml",
            b'ObjectType="Note"',
            b'ObjectType="Button"',
        ),
        (
            "xl/drawings/commentsDrawing1.vml",
            b"visibility:hidden",
            b"width:expression(alert())",
        ),
        (
            "xl/drawings/commentsDrawing1.vml",
            b"<ns2:Row>4</ns2:Row>",
            b"<ns2:Row>5</ns2:Row>",
        ),
        ("xl/drawings/commentsDrawing1.vml", b"<xml>", b"<xml><script/>"),
        ("xl/comments/comment1.xml", b'ref="A5"', b'ref="A6"'),
        ("xl/tables/table1.xml", b'count="29"', b'count="28"'),
        ("xl/tables/table1.xml", b'ref="A5:AC205"', b'ref="A1:AC205"'),
        ("xl/tables/table1.xml", b'name="Header 2"', b'name="Header 1"'),
        (
            "xl/worksheets/_rels/sheet2.xml.rels",
            b"../tables/table1.xml",
            b"../../xl/tables/table1.xml",
        ),
        (
            "xl/worksheets/_rels/sheet2.xml.rels",
            b'Id="rId1"',
            b'TargetMode="External" Id="rId1"',
        ),
        (
            "[Content_Types].xml",
            b"spreadsheetml.table+xml",
            b"spreadsheetml.worksheet+xml",
        ),
    ],
)
def test_hostile_annotation_mutations(part: str, old: bytes, new: bytes) -> None:
    """Reject active geometry, wrong anchors, unsafe links and metadata drift."""
    parts = package()
    assert old in parts[part]
    parts[part] = parts[part].replace(old, new)
    with pytest.raises(IntakeError):
        read_archive(packed(parts), Budget())


@pytest.mark.parametrize(
    "part",
    [
        "xl/tables/table1.xml",
        "xl/comments/comment1.xml",
        "xl/worksheets/_rels/sheet2.xml.rels",
    ],
)
def test_missing_or_orphan_parts(part: str) -> None:
    """Require complete owned attachment closure even for nonsemantic notes."""
    parts = package()
    del parts[part]
    with pytest.raises(IntakeError):
        read_archive(packed(parts), Budget())
