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


def package(*, notes: bool = True, table: bool = True) -> dict[str, bytes]:
    """Create only trusted local test output, with inert header comments."""
    w = Workbook()
    w.active.title = "Start here"
    s = w.create_sheet("Intake")
    for c in range(1, 30):
        s.cell(5, c, f"Header {c}")
        if notes:
            s.cell(5, c).comment = Comment("Synthetic help", "Example author")
    if table:
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


@pytest.mark.parametrize(("notes", "table"), [(False, True), (True, False)])
def test_removed_optional_controls_do_not_expand_package_scope(
    *, notes: bool, table: bool
) -> None:
    """Accept coherent passive-control removal, still checking any remaining parts."""
    read_archive(packed(package(notes=notes, table=table)), Budget())


@pytest.mark.parametrize(
    ("part", "old", "new"),
    [
        ("xl/tables/table1.xml", b"<table ", b'<table connectionId="1" '),
        ("xl/tables/table1.xml", b'id="2" name="Header 2"', b'id="1" name="Header 2"'),
        ("xl/comments/comment1.xml", b"<authors>", b'<authors unexpected="1">'),
        (
            "xl/drawings/commentsDrawing1.vml",
            b"<ns2:Row>4</ns2:Row>",
            b"<ns2:Row>x</ns2:Row>",
        ),
        (
            "xl/drawings/commentsDrawing1.vml",
            b"<ns2:Row>4</ns2:Row>",
            b"<ns2:Row>4</ns2:Row><ns2:Row>4</ns2:Row>",
        ),
        (
            "xl/drawings/commentsDrawing1.vml",
            b"<ns2:Column>0</ns2:Column>",
            b"<ns2:Column>0</ns2:Column><ns2:Column>0</ns2:Column>",
        ),
        (
            "xl/drawings/commentsDrawing1.vml",
            b"<ns2:AutoFill>False</ns2:AutoFill>",
            b"<ns2:AutoFill>unexpected</ns2:AutoFill>",
        ),
        (
            "xl/worksheets/_rels/sheet2.xml.rels",
            b"<ns0:Relationships ",
            b'<ns0:Relationships unexpected="1" ',
        ),
        ("xl/worksheets/_rels/sheet2.xml.rels", b'Id="comments"', b'Id="rId1"'),
        (
            "xl/worksheets/_rels/sheet2.xml.rels",
            b'Id="comments"',
            b'Unexpected="1" Id="comments"',
        ),
        ("xl/worksheets/sheet2.xml", b"<tablePart ", b"<tablePart "),
    ],
)
def test_additional_malformed_annotation_shapes(
    part: str, old: bytes, new: bytes
) -> None:
    """Exercise malformed vocabulary, identifiers, text and repeated references."""
    parts = package()
    if old == new:
        # Duplicate an actual local table reference, preserving the attachment itself.
        import re  # noqa: PLC0415 -- local mutation of a trusted test string.

        parts[part] = re.sub(rb"(<tablePart [^>]*/>)", rb"\1\1", parts[part])
    else:
        assert old in parts[part]
        parts[part] = parts[part].replace(old, new)
    with pytest.raises(IntakeError):
        read_archive(packed(parts), Budget())


def test_note_anchor_set_must_match_comment_cells() -> None:
    """Reject a coherent VML note with no matching comment text entry."""
    import re  # noqa: PLC0415 -- trusted authored mutation.

    parts = package()
    key = "xl/comments/comment1.xml"
    parts[key] = re.sub(rb'<comment ref="A5".*?</comment>', b"", parts[key])
    with pytest.raises(IntakeError):
        read_archive(packed(parts), Budget())


def test_missing_attachment_owner_and_reference_mismatch() -> None:
    """Reject dangling owner files and mismatched worksheet reference IDs."""
    from dscat.intake.archive import XmlPart, read_annotation_relationships  # noqa: PLC0415 -- focused boundary mutation.

    parts = package()
    del parts["xl/worksheets/sheet2.xml"]
    typed = {n: XmlPart(name=n, content=b) for n, b in parts.items()}
    with pytest.raises(IntakeError):
        read_annotation_relationships(typed, Budget())
    parts = package()
    key = "xl/worksheets/sheet2.xml"
    parts[key] = parts[key].replace(b'r:id="rId1"', b'r:id="wrong"')
    with pytest.raises(IntakeError):
        read_archive(packed(parts), Budget())


def test_incomplete_note_relationship_pair() -> None:
    """Require comments and their note drawing as a pair, even if neither is active."""
    from dscat.intake.archive import (  # noqa: PLC0415 -- closed relationship fixture.
        AnnotationRelationships,
        Relationship,
        check_annotations,
    )

    reader = AnnotationRelationships("xl/worksheets/sheet2.xml", {}, set())
    reader.current["comments"] = Relationship(
        source="worksheet",
        owner=reader.owner,
        id="note",
        kind="comments",
        target="xl/comments/comment1.xml",
    )
    with pytest.raises(IntakeError):
        check_annotations(reader, Budget())
