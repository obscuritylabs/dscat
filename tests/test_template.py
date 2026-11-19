# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Inspect self-generated workbook output without treating it as intake validation."""

import hashlib
import io
import json
import socket
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from openpyxl import Workbook, load_workbook
from openpyxl.formula.tokenizer import Tokenizer
from pydantic import ValidationError

from dscat.models.intake import WorkbookMetadata
from dscat.workbook.generate import (
    WorkbookArtifact,
    create_template,
    relative_worksheet_relationships,
    write_text,
)

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
EXPECTED_FORMULAS = 3000
EXPECTED_PARTS = {
    "[Content_Types].xml",
    "_rels/.rels",
    "docProps/app.xml",
    "docProps/core.xml",
    "xl/theme/theme1.xml",
    "xl/styles.xml",
    "xl/workbook.xml",
    "xl/_rels/workbook.xml.rels",
    "xl/worksheets/sheet1.xml",
    "xl/worksheets/sheet2.xml",
    "xl/worksheets/sheet3.xml",
    "xl/worksheets/sheet4.xml",
}


@pytest.fixture(scope="module")
def artifact() -> WorkbookArtifact:
    """Create a trusted output once for structural acceptance inspection."""
    return create_template()


def test_template_layout_and_accessibility_structure(
    artifact: WorkbookArtifact,
) -> None:
    """Instructions precede labeled unmerged input ranges and visible text feedback."""
    workbook = load_workbook(io.BytesIO(artifact.content), data_only=False)
    assert workbook.sheetnames == [
        "Instructions",
        "Datasets",
        "Fields",
        "Details_Quality",
    ]
    assert workbook.active.title == "Instructions"
    assert (
        workbook.defined_names["dscat_workbook_schema"].attr_text
        == "'Instructions'!$B$2"
    )
    assert (
        workbook.defined_names["dscat_workbook_kind"].attr_text == "'Instructions'!$B$3"
    )
    assert workbook["Instructions"]["B2"].value == "1.0"
    assert workbook["Instructions"]["B3"].value == "dataset-intake"
    assert [workbook["Datasets"].cell(1, i).value for i in range(1, 5)] == [
        "id",
        "title",
        "description",
        "core_party",
    ]
    assert workbook["Datasets"]["P1"].value == "feedback"
    assert workbook["Fields"]["H1"].value == "feedback"
    assert workbook["Details_Quality"]["H1"].value == "feedback"
    for sheet in workbook:
        assert sheet.sheet_state == "visible"
        assert not sheet.protection.sheet
        assert not sheet.merged_cells.ranges
    for name in ("Datasets", "Fields", "Details_Quality"):
        sheet = workbook[name]
        assert sheet.freeze_panes == "E2"
        assert sheet["A1"].font.bold
        assert sheet["A2"].number_format == "@"
        assert sheet["A2"].value is None
        assert sheet.auto_filter.ref is not None
    instructions = " ".join(
        str(workbook["Instructions"].cell(row, 2).value) for row in range(1, 20)
    )
    assert "Ctrl+PageDown" in instructions
    assert "feedback" in instructions
    assert "independently checks" in instructions
    assert "Unknown is not zero" in instructions
    assert "Proprietary License" in instructions


def test_controls_and_textual_correction_guidance(artifact: WorkbookArtifact) -> None:
    """Controls and textual feedback identify corrections without color."""
    workbook = load_workbook(io.BytesIO(artifact.content), data_only=False)
    datasets = workbook["Datasets"]
    controls = list(datasets.data_validations.dataValidation)
    assert {control.type for control in controls} == {"textLength", "list", "custom"}
    assert any(control.formula1 == '"contact,owner"' for control in controls)
    for sheet in workbook:
        for control in sheet.data_validations.dataValidation:
            assert control.showInputMessage
            assert control.prompt
            assert control.error
    assert '"Yes,No"' in {
        v.formula1 for v in workbook["Fields"].data_validations.dataValidation
    }
    assert "dscat_sections" in {
        v.formula1 for v in workbook["Details_Quality"].data_validations.dataValidation
    }
    assert "dscat_units" in {
        v.formula1 for v in workbook["Details_Quality"].data_validations.dataValidation
    }
    assert "Complete id, title, description and core_party" in datasets["P2"].value
    assert "EXACT(" in datasets["P2"].value
    assert "Duplicate id" in datasets["P2"].value
    assert "Correct dates using YYYY-MM-DD" in datasets["P2"].value
    assert "MOD(VALUE(LEFT(I2,4)),400)" in datasets["P2"].value
    assert "TEXT(VALUE(LEFT(I2,4))" in datasets["P2"].value
    assert "nonnegative whole days" in workbook["Details_Quality"]["H2"].value
    assert "Choose a supported value" in workbook["Details_Quality"]["H2"].value


def test_actual_package_matrix_and_formula_boundary(artifact: WorkbookArtifact) -> None:
    """The generated archive has only approved parts and feedback-cell formulas."""
    with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
        assert set(archive.namelist()) == EXPECTED_PARTS
        assert len(archive.namelist()) == len(EXPECTED_PARTS)
        assert archive.testzip() is None
        for name in archive.namelist():
            payload = archive.read(name)
            assert b"/Users/" not in payload
            assert b"vbaProject" not in payload
            assert b'TargetMode="External"' not in payload
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))  # noqa: S314 -- trusted generated output.
        for relationship in relationships:
            target = relationship.attrib["Target"]
            assert not target.startswith("/")
            assert ".." not in target
            assert "xl/" + target in EXPECTED_PARTS
        formulas = 0
        for number, column in ((1, ""), (2, "P"), (3, "H"), (4, "H")):
            root = ET.fromstring(  # noqa: S314 -- trusted generated output.
                archive.read(f"xl/worksheets/sheet{number}.xml")
            )
            for cell in root.findall(".//s:c", NS):
                formula = cell.find("s:f", NS)
                if formula is not None:
                    formulas += 1
                    assert column
                    assert cell.attrib["r"].startswith(column)
                    assert formula.text is not None
                    assert "Ready for CLI validation" in formula.text
                    assert Tokenizer("=" + formula.text).items
        assert formulas == EXPECTED_FORMULAS


def test_template_compatibility_fixture_and_determinism(
    artifact: WorkbookArtifact,
) -> None:
    """The initial fixture protects output and future intake compatibility."""
    fixture = Path(__file__).parent / "fixtures" / "workbook-1.0"
    content = (fixture / "template.xlsx").read_bytes()
    assert content == artifact.content == create_template().content
    matrix = json.loads((fixture / "package-parts.json").read_text())
    assert matrix["template_sha256"] == hashlib.sha256(content).hexdigest()
    assert set(matrix["parts"]) == EXPECTED_PARTS


@pytest.mark.parametrize(
    "text", ["=1+1", "+1", "-1", "@SUM(A1)", "https://example.org/", "x" * 32767]
)
def test_text_remains_inert(text: str) -> None:
    """Formula prefixes and references do not become formulas or hyperlinks."""
    workbook = Workbook()
    cell = workbook.active["A1"]
    write_text(cell, text)
    assert cell.value == text
    assert cell.data_type == "s"
    assert cell.hyperlink is None
    raw = io.BytesIO()
    workbook.save(raw)
    with zipfile.ZipFile(raw) as archive:
        xml = archive.read("xl/worksheets/sheet1.xml")
        assert b"<f>" not in xml
        assert "xl/worksheets/_rels/sheet1.xml.rels" not in archive.namelist()


def test_overlong_text_does_not_truncate_or_mutate() -> None:
    """Reject unsupported text before openpyxl could silently truncate it."""
    cell = Workbook().active["A1"]
    write_text(cell, "Preserve this value")
    with pytest.raises(ValueError, match="character limit"):
        write_text(cell, "x" * 32768)
    assert cell.value == "Preserve this value"


def test_invalid_generated_artifact_is_rejected(artifact: WorkbookArtifact) -> None:
    """Empty, corrupt, incorrectly typed and hash-mismatched output fails safely."""
    for content, digest in (
        (b"", artifact.sha256),
        (b"invalid zip", hashlib.sha256(b"invalid zip").hexdigest()),
        (artifact.content, "a" * 64),
    ):
        with pytest.raises(ValidationError):
            WorkbookArtifact(
                metadata=WorkbookMetadata(schema_version="1.0", kind="dataset-intake"),
                content=content,
                sha256=digest,
            )
    with pytest.raises(ValidationError):
        WorkbookArtifact.model_validate(
            {
                "metadata": {"schema_version": "1.0", "kind": "dataset-intake"},
                "content": "not bytes",
                "sha256": artifact.sha256,
            }
        )


def test_generation_has_no_network_or_filesystem_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Generation returns bytes without network or implicit output paths."""

    def deny(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Unexpected runtime network operation")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)
    monkeypatch.chdir(tmp_path)
    assert create_template().metadata.schema_version == "1.0"
    assert list(tmp_path.iterdir()) == []


def test_writer_failure_returns_no_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    """An in-memory library failure cannot publish a partial workbook."""

    def fail(_writer: object) -> None:
        msg = "Synthetic writer failure"
        raise OSError(msg)

    monkeypatch.setattr("dscat.workbook.generate.ExcelWriter.save", fail)
    with pytest.raises(OSError, match="Synthetic writer failure"):
        create_template()


def test_generator_refuses_unexpected_absolute_relationship() -> None:
    """Normalization cannot silently widen the approved package matrix."""
    payload = (
        b'<Relationships><Relationship Target="/unexpected.xml" /></Relationships>'
    )
    with pytest.raises(ValueError, match="unsupported absolute"):
        relative_worksheet_relationships(payload)


def test_invalid_relationship_serialization_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unexpected serializer output cannot become a generated workbook member."""

    def invalid(*_args: object, **_kwargs: object) -> str:
        return "Unexpected text output"

    monkeypatch.setattr("dscat.workbook.generate.ET.tostring", invalid)
    with pytest.raises(TypeError, match="did not produce bytes"):
        relative_worksheet_relationships(b"<Relationships />")
