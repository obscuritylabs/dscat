# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Closed ZIP and OPC validation with actual bounded streaming decompression."""

import io
import re
import stat
import struct
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field, field_validator

from dscat.intake.annotations import (
    ATTACHMENTS,
    REL,
    WORKSHEET_RELS,
    annotation_mime,
    attachment_kind,
    note_refs,
    table_headers,
)
from dscat.intake.limits import (
    CHUNK_BYTES,
    ArchiveStatistics,
    Budget,
    IntakeError,
    fail,
)
from dscat.intake.xml import validate_xml
from dscat.models.base import StrictModel

if TYPE_CHECKING:
    from collections.abc import Iterator


EOCD = struct.Struct("<4s4H2IH")
ZIP64_LOCATOR = struct.Struct("<4sIQI")
ZIP64_END = struct.Struct("<4sQ2H2I4Q")
LOCAL = struct.Struct("<4s5H3I2H")
UINT32_MAX = 2**32 - 1
UINT16_MAX = 2**16 - 1
ZIP64_MINIMUM_SIZE = 44
AES_EXTRA_ID = 0x9901
UINT64_BYTES = 8
DESCRIPTOR32 = struct.Struct("<III")
DESCRIPTOR64 = struct.Struct("<IQQ")
CHILD_DEPTH = 2
REQUIRED_PARTS = frozenset(
    {
        "[Content_Types].xml",
        "_rels/.rels",
        "docProps/core.xml",
        "docProps/app.xml",
        "xl/workbook.xml",
        "xl/_rels/workbook.xml.rels",
        "xl/styles.xml",
    }
)
OPTIONAL_PARTS = frozenset({"xl/sharedStrings.xml", "xl/theme/theme1.xml"})
REL_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"
REL_TYPES = {
    "officeDocument": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
    "core-properties": "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties",
    "extended-properties": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties",
    "worksheet": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
    "styles": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles",
    "sharedStrings": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings",
    "theme": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme",
}
MIME_PREFIX = "application/vnd.openxmlformats-"
MIME_TYPES = {
    "_rels/.rels": MIME_PREFIX + "package.relationships+xml",
    "xl/_rels/workbook.xml.rels": MIME_PREFIX + "package.relationships+xml",
    "docProps/core.xml": MIME_PREFIX + "package.core-properties+xml",
    "docProps/app.xml": MIME_PREFIX + "officedocument.extended-properties+xml",
    "xl/workbook.xml": MIME_PREFIX + "officedocument.spreadsheetml.sheet.main+xml",
    "xl/styles.xml": MIME_PREFIX + "officedocument.spreadsheetml.styles+xml",
    "xl/sharedStrings.xml": MIME_PREFIX
    + "officedocument.spreadsheetml.sharedStrings+xml",
    "xl/theme/theme1.xml": MIME_PREFIX + "officedocument.theme+xml",
}


def supported_part(name: str) -> bool:
    """Recognize only exact approved paths, without normalizing an attacker path."""
    return (
        name in REQUIRED_PARTS | OPTIONAL_PARTS
        or attachment_kind(name) is not None
        or re.fullmatch(WORKSHEET_RELS, name) is not None
        or re.fullmatch(r"xl/worksheets/sheet[1-9][0-9]*\.xml", name) is not None
    )


class XmlPart(StrictModel):
    """Validated immutable XML bytes remain local to one worker."""

    name: str
    content: Annotated[bytes, Field(min_length=1)]

    @field_validator("name")
    @classmethod
    def closed_name(cls, name: str) -> str:
        """Reject unsupported part names at the structured boundary too."""
        if not supported_part(name):
            msg = "Unsupported workbook part."
            raise ValueError(msg)
        return name


class Relationship(StrictModel):
    """Only validated local OPC relationship identities cross this boundary."""

    source: Literal["package", "workbook", "worksheet"]
    owner: str | None = None
    id: str
    kind: Literal[
        "officeDocument",
        "core-properties",
        "extended-properties",
        "worksheet",
        "styles",
        "sharedStrings",
        "theme",
        "table",
        "comments",
        "vmlDrawing",
    ]
    target: str


class SafeArchive(StrictModel):
    """A closed byte package ready for a separate semantic workbook parser."""

    parts: list[XmlPart]
    relationships: list[Relationship]
    statistics: ArchiveStatistics


def directory_bounds(raw: bytes, budget: Budget) -> tuple[int, int]:
    """Bound the central directory before allocating member objects."""
    budget.check("compressed", len(raw), budget.limits.compressed)
    position = raw.rfind(b"PK\x05\x06", max(0, len(raw) - EOCD.size - UINT16_MAX))
    if position < 0 or position + EOCD.size > len(raw):
        raise fail(code="INVALID_WORKBOOK")
    _, disk, directory_disk, disk_count, count, size, offset, comment = (
        EOCD.unpack_from(raw, position)
    )
    if (
        disk
        or directory_disk
        or disk_count != count
        or position + EOCD.size + comment != len(raw)
    ):
        raise fail(code="UNSAFE_INPUT")
    central_end = position
    if count == UINT16_MAX or UINT32_MAX in (size, offset):
        locator_position = position - ZIP64_LOCATOR.size
        if locator_position < 0:
            raise fail(code="INVALID_WORKBOOK")
        signature, disk64, end_offset, total_disks = ZIP64_LOCATOR.unpack_from(
            raw, locator_position
        )
        if (
            signature != b"PK\x06\x07"
            or disk64
            or total_disks != 1
            or end_offset + ZIP64_END.size > locator_position
        ):
            raise fail(code="UNSAFE_INPUT")
        (
            signature,
            record_size,
            _made,
            _needed,
            disk64,
            directory_disk64,
            disk_count64,
            count,
            size,
            offset,
        ) = ZIP64_END.unpack_from(raw, end_offset)
        if (
            signature != b"PK\x06\x06"
            or record_size < ZIP64_MINIMUM_SIZE
            or end_offset + 12 + record_size != locator_position
            or disk64
            or directory_disk64
            or disk_count64 != count
        ):
            raise fail(code="UNSAFE_INPUT")
        central_end = end_offset
    budget.check("members", count, budget.limits.members)
    if offset + size != central_end or offset > len(raw) or not count:
        raise fail(code="INVALID_WORKBOOK")
    return int(offset), int(count)


def extra_fields(extra: bytes) -> Iterator[tuple[int, bytes]]:
    """Validate extra-field framing and refuse AES encryption metadata."""
    cursor = 0
    while cursor < len(extra):
        if cursor + 4 > len(extra):
            raise fail(code="UNSAFE_INPUT")
        kind, length = struct.unpack_from("<HH", extra, cursor)
        cursor += 4
        if cursor + length > len(extra) or kind == AES_EXTRA_ID:
            raise fail(code="UNSAFE_INPUT")
        yield int(kind), extra[cursor : cursor + length]
        cursor += length


def local_sizes(extra: bytes, compressed: int, expanded: int) -> tuple[int, int]:
    """Resolve explicit ZIP64 size fields without allocating payloads."""
    seen = False
    for kind, payload in extra_fields(extra):
        values = payload
        if kind != 1:
            continue
        if seen:
            raise fail(code="UNSAFE_INPUT")
        seen = True
        if expanded == UINT32_MAX:
            if len(values) < UINT64_BYTES:
                raise fail(code="UNSAFE_INPUT")
            expanded = int(struct.unpack_from("<Q", values)[0])
            values = values[UINT64_BYTES:]
        if compressed == UINT32_MAX:
            if len(values) < UINT64_BYTES:
                raise fail(code="UNSAFE_INPUT")
            compressed = int(struct.unpack_from("<Q", values)[0])
    return compressed, expanded


def local_data(raw: bytes, info: zipfile.ZipInfo, central: int) -> tuple[int, int]:
    """Check local headers before reading a compressed extent."""
    if info.header_offset < 0 or info.header_offset + LOCAL.size > central:
        raise fail(code="UNSAFE_INPUT")
    (
        signature,
        _version,
        flags,
        method,
        _time,
        _date,
        crc,
        compressed,
        expanded,
        name_length,
        extra_length,
    ) = LOCAL.unpack_from(raw, info.header_offset)
    start = info.header_offset + LOCAL.size
    data_offset = start + name_length + extra_length
    if (
        signature != b"PK\x03\x04"
        or flags != info.flag_bits
        or method != info.compress_type
        or data_offset + info.compress_size > central
    ):
        raise fail(code="UNSAFE_INPUT")
    name = raw[start : start + name_length].decode(
        "utf-8" if flags & 0x800 else "cp437"
    )
    if name != info.orig_filename or name != info.filename:
        raise fail(code="UNSAFE_INPUT")
    compressed, expanded = local_sizes(
        raw[start + name_length : data_offset], int(compressed), int(expanded)
    )
    if not flags & 8:
        if (crc, compressed, expanded) != (
            info.CRC,
            info.compress_size,
            info.file_size,
        ):
            raise fail(code="UNSAFE_INPUT")
    elif (
        crc not in (0, info.CRC)
        or compressed not in (0, info.compress_size)
        or expanded not in (0, info.file_size)
    ):
        raise fail(code="UNSAFE_INPUT")
    return int(data_offset), int(data_offset + info.compress_size)


def decompressed_chunks(
    raw: bytes, info: zipfile.ZipInfo, start: int, end: int, budget: Budget
) -> Iterator[bytes]:
    """Stream actual stored/deflated bytes without advertised-size truncation."""
    if info.compress_type == zipfile.ZIP_STORED:
        for offset in range(start, end, CHUNK_BYTES):
            budget.check_time()
            yield raw[offset : min(end, offset + CHUNK_BYTES)]
        return
    decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
    for offset in range(start, end, CHUNK_BYTES):
        budget.check_time()
        pending = raw[offset : min(end, offset + CHUNK_BYTES)]
        while pending:
            chunk = decompressor.decompress(pending, CHUNK_BYTES)
            pending = decompressor.unconsumed_tail
            if chunk:
                yield chunk
            if decompressor.unused_data:
                raise fail(code="UNSAFE_INPUT")
    while not decompressor.eof:
        chunk = decompressor.decompress(b"", CHUNK_BYTES)
        if not chunk:
            raise fail(code="UNSAFE_INPUT")
        yield chunk


def check_descriptor(raw: bytes, info: zipfile.ZipInfo, start: int, end: int) -> None:
    """Reject overlaps/hidden gaps; validate streamed data descriptors when present."""
    if not info.flag_bits & 8:
        if start != end:
            raise fail(code="UNSAFE_INPUT")
        return
    descriptor = raw[start:end]
    if descriptor.startswith(b"PK\x07\x08"):
        descriptor = descriptor[4:]
    if len(descriptor) == DESCRIPTOR32.size:
        values = DESCRIPTOR32.unpack(descriptor)
    elif len(descriptor) == DESCRIPTOR64.size:
        values = DESCRIPTOR64.unpack(descriptor)
    else:
        raise fail(code="UNSAFE_INPUT")
    if values != (info.CRC, info.compress_size, info.file_size):
        raise fail(code="UNSAFE_INPUT")


@dataclass
class RelationshipReader:
    """Bounded relationship callback state; no target is dereferenced."""

    names: set[str]
    root_source: bool
    output: list[Relationship] = field(default_factory=list)

    @property
    def allowed_targets(self) -> dict[str, str]:
        """Return only the relevant root or workbook relationship vocabulary."""
        if self.root_source:
            return {
                "officeDocument": "xl/workbook.xml",
                "core-properties": "docProps/core.xml",
                "extended-properties": "docProps/app.xml",
            }
        return {
            "styles": "xl/styles.xml",
            "sharedStrings": "xl/sharedStrings.xml",
            "theme": "xl/theme/theme1.xml",
        }

    def start(self, name: str, attributes: dict[str, str], depth: int) -> None:
        """Validate one relationship element without accepting foreign nesting."""
        if depth == 1:
            if name != REL_NAMESPACE + "}Relationships" or attributes:
                raise fail(code="UNSUPPORTED_WORKBOOK_PART")
            return
        if (
            depth != CHILD_DEPTH
            or name != REL_NAMESPACE + "}Relationship"
            or not {"Id", "Type", "Target"} <= attributes.keys()
            or attributes.keys() - {"Id", "Type", "Target", "TargetMode"}
        ):
            raise fail(code="UNSUPPORTED_WORKBOOK_PART")
        if attributes.get("TargetMode", "Internal") != "Internal":
            raise fail(code="UNSAFE_INPUT")
        kind = next(
            (kind for kind, uri in REL_TYPES.items() if uri == attributes["Type"]), None
        )
        if kind is None:
            raise fail(code="UNSUPPORTED_WORKBOOK_PART")
        target = attributes["Target"]
        if (
            not target
            or target.startswith("/")
            or "\\" in target
            or ":" in target
            or ".." in PurePosixPath(target).parts
        ):
            raise fail(code="UNSAFE_INPUT")
        resolved = target if self.root_source else "xl/" + target
        if (
            resolved not in self.names
            or (
                kind == "worksheet"
                and (
                    self.root_source
                    or not re.fullmatch(
                        r"xl/worksheets/sheet[1-9][0-9]*\.xml", resolved
                    )
                )
            )
            or (kind != "worksheet" and self.allowed_targets.get(kind) != resolved)
        ):
            raise fail(code="UNSUPPORTED_WORKBOOK_PART")
        identifier = attributes["Id"]
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,127}", identifier) is None or any(
            item.id == identifier or item.target == resolved for item in self.output
        ):
            raise fail(code="INVALID_WORKBOOK")
        self.output.append(
            Relationship.model_validate(
                {
                    "source": "package" if self.root_source else "workbook",
                    "id": identifier,
                    "kind": kind,
                    "target": resolved,
                }
            )
        )


def read_relationships(
    part: XmlPart, names: set[str], budget: Budget
) -> list[Relationship]:
    """Validate the complete local relationship closure."""
    reader = RelationshipReader(names, part.name == "_rels/.rels")
    validate_xml(part.content, budget, reader.start)
    expected = (
        {"xl/workbook.xml", "docProps/core.xml", "docProps/app.xml"}
        if reader.root_source
        else {
            name
            for name in names
            if name.startswith("xl/")
            and name not in {"xl/workbook.xml", "xl/_rels/workbook.xml.rels"}
            and attachment_kind(name) is None
            and re.fullmatch(WORKSHEET_RELS, name) is None
        }
    )
    if {item.target for item in reader.output} != expected:
        raise fail(code="INVALID_WORKBOOK")
    return reader.output


@dataclass
class ContentTypeReader:
    """Retain only unique known MIME mappings for actual closed package parts."""

    names: set[str]
    defaults: dict[str, str] = field(default_factory=dict)
    overrides: dict[str, str] = field(default_factory=dict)
    namespace: str = "http://schemas.openxmlformats.org/package/2006/content-types}"

    def start(self, name: str, attributes: dict[str, str], depth: int) -> None:
        """Validate one exact content-type declaration."""
        if depth == 1:
            if name != self.namespace + "Types" or attributes:
                raise fail(code="UNSUPPORTED_WORKBOOK_PART")
            return
        if depth != CHILD_DEPTH:
            raise fail(code="UNSUPPORTED_WORKBOOK_PART")
        if name == self.namespace + "Default" and attributes.keys() == {
            "Extension",
            "ContentType",
        }:
            key, value = attributes["Extension"], attributes["ContentType"]
            if key in self.defaults or (key, value) not in {
                ("xml", "application/xml"),
                ("rels", MIME_TYPES["_rels/.rels"]),
                ("vml", ATTACHMENTS["vmlDrawing"][1]),
            }:
                raise fail(code="UNSUPPORTED_WORKBOOK_PART")
            self.defaults[key] = value
        elif name == self.namespace + "Override" and attributes.keys() == {
            "PartName",
            "ContentType",
        }:
            key = attributes["PartName"]
            if (
                not key.startswith("/")
                or key == "/[Content_Types].xml"
                or key[1:] not in self.names
                or key[1:] in self.overrides
            ):
                raise fail(code="UNSUPPORTED_WORKBOOK_PART")
            self.overrides[key[1:]] = attributes["ContentType"]
        else:
            raise fail(code="UNSUPPORTED_WORKBOOK_PART")


def check_content_types(part: XmlPart, names: set[str], budget: Budget) -> None:
    """Require an exact supported MIME mapping for every actual part."""
    reader = ContentTypeReader(names)
    validate_xml(part.content, budget, reader.start)
    for name in names - {"[Content_Types].xml"}:
        expected = annotation_mime(name) or (
            MIME_TYPES["_rels/.rels"]
            if re.fullmatch(WORKSHEET_RELS, name)
            else MIME_TYPES.get(
                name, MIME_PREFIX + "officedocument.spreadsheetml.worksheet+xml"
            )
        )
        actual = reader.overrides.get(
            name,
            reader.defaults.get(
                "rels"
                if name.endswith(".rels")
                else PurePosixPath(name).suffix.removeprefix(".")
            ),
        )
        if expected != actual:
            raise fail(code="UNSUPPORTED_WORKBOOK_PART")


def checked_extent(
    raw: bytes, info: zipfile.ZipInfo, central: int, parents: set[str]
) -> tuple[zipfile.ZipInfo, int, int]:
    """Validate one member's flags, physical kind, extras and local header."""
    mode_type = stat.S_IFMT(info.external_attr >> 16)
    allowed_modes = (0, stat.S_IFDIR) if info.is_dir() else (0, stat.S_IFREG)
    if (
        info.orig_filename != info.filename
        or info.flag_bits & ~0x80E
        or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
        or mode_type not in allowed_modes
    ):
        raise fail(code="UNSAFE_INPUT")
    if info.is_dir() and (info.orig_filename not in parents or info.file_size):
        raise fail(code="UNSAFE_INPUT")
    # Validate central extras as well as local extras, including encryption metadata.
    for _kind, _payload in extra_fields(info.extra):
        pass
    start, end = local_data(raw, info, central)
    return info, start, end


def container_members(
    raw: bytes, central: int, count: int, budget: Budget
) -> tuple[set[str], int, list[tuple[zipfile.ZipInfo, int, int]]]:
    """Bound member objects and establish their exact closed physical extents."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
    budget.members = len(members)
    if len(members) != count or len({info.orig_filename for info in members}) != count:
        raise fail(code="UNSAFE_INPUT")
    names = {info.orig_filename for info in members if not info.is_dir()}
    if not names >= REQUIRED_PARTS or any(not supported_part(name) for name in names):
        raise fail(code="UNSUPPORTED_WORKBOOK_PART")
    parents = {
        str(parent) + "/"
        for name in names
        for parent in PurePosixPath(name).parents
        if str(parent) != "."
    }
    sheets = sum(name.startswith("xl/worksheets/") for name in names)
    budget.worksheets = sheets
    budget.check("sheets", sheets, budget.limits.sheets)
    if not sheets:
        raise fail(code="INVALID_WORKBOOK")
    extents = []
    for info in members:
        budget.check_time()
        extents.append(checked_extent(raw, info, central, parents))
    extents.sort(key=lambda item: item[0].header_offset)
    if extents[0][0].header_offset != 0:
        raise fail(code="UNSAFE_INPUT")
    return names, sheets, extents


def read_member(
    raw: bytes, info: zipfile.ZipInfo, bounds: tuple[int, int], budget: Budget
) -> XmlPart:
    """Count actual expanded bytes, verify CRC and reject advertised-size forgeries."""
    data = bytearray()
    crc = 0
    for chunk in decompressed_chunks(raw, info, *bounds, budget):
        budget.expand(len(chunk))
        budget.check("xml", len(data) + len(chunk), budget.limits.xml)
        budget.check(
            "ratio",
            len(data) + len(chunk),
            max(1, info.compress_size) * budget.limits.ratio,
        )
        budget.check("ratio", budget.expanded, max(1, len(raw)) * budget.limits.ratio)
        crc = zlib.crc32(chunk, crc)
        data.extend(chunk)
    if len(data) != info.file_size or crc & UINT32_MAX != info.CRC:
        raise fail(code="UNSAFE_INPUT")
    content = bytes(data)
    validate_xml(content, budget)
    return XmlPart(name=info.filename, content=content)


def check_directory(
    raw: bytes, info: zipfile.ZipInfo, bounds: tuple[int, int], budget: Budget
) -> None:
    """Accept empty stored/deflated parent entries, rejecting actual hidden payloads."""
    for chunk in decompressed_chunks(raw, info, *bounds, budget):
        budget.expand(len(chunk))
        raise fail(code="UNSAFE_INPUT")
    if info.CRC != 0:
        raise fail(code="UNSAFE_INPUT")


def read_archive(raw: bytes, budget: Budget) -> SafeArchive:
    """Validate a bounded package without extraction or workbook readers."""
    budget.compressed = len(raw)
    central, count = directory_bounds(raw, budget)
    parts: list[XmlPart] = []
    try:
        names, _sheets, extents = container_members(raw, central, count, budget)
        for index, (info, start, end) in enumerate(extents):
            next_header = (
                extents[index + 1][0].header_offset
                if index + 1 < len(extents)
                else central
            )
            if end > next_header:
                raise fail(code="UNSAFE_INPUT")
            check_descriptor(raw, info, end, next_header)
            if not info.is_dir():
                parts.append(read_member(raw, info, (start, end), budget))
            else:
                check_directory(raw, info, (start, end), budget)
    except IntakeError:
        raise
    except (
        zipfile.BadZipFile,
        struct.error,
        UnicodeError,
        zlib.error,
        NotImplementedError,
    ):
        raise fail(code="INVALID_WORKBOOK") from None
    by_name = {part.name: part for part in parts}
    check_content_types(by_name["[Content_Types].xml"], names, budget)
    relationships = [
        item
        for name in ("_rels/.rels", "xl/_rels/workbook.xml.rels")
        for item in read_relationships(by_name[name], names, budget)
    ]
    relationships.extend(read_annotation_relationships(by_name, budget))
    return SafeArchive(
        parts=sorted(parts, key=lambda part: part.name),
        relationships=relationships,
        statistics=budget.statistics(),
    )


@dataclass
class AnnotationRelationships:
    """Collect only local table and inert-note worksheet relationships."""

    owner: str
    parts: dict[str, XmlPart]
    owned: set[str]
    current: dict[str, Relationship] = field(default_factory=dict)
    identifiers: set[str] = field(default_factory=set)
    refs: dict[str, str] = field(default_factory=dict)

    def start(self, tag: str, attrs: dict[str, str], depth: int) -> None:
        """Validate an exact owned relationship declaration."""
        if depth == 1:
            if tag != REL + "Relationships" or attrs:
                raise fail(code="UNSUPPORTED_WORKBOOK_PART")
            return
        if (
            depth != CHILD_DEPTH
            or tag != REL + "Relationship"
            or attrs.keys() - {"Id", "Type", "Target", "TargetMode"}
            or not {"Id", "Type", "Target"} <= attrs.keys()
        ):
            raise fail(code="UNSUPPORTED_WORKBOOK_PART")
        if attrs.get("TargetMode", "Internal") != "Internal":
            raise fail(code="UNSAFE_INPUT")
        kind = attrs["Type"].removeprefix(
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
        )
        target = attrs["Target"]
        # Exactly one prescribed parent step is valid OPC syntax here.
        resolved = "xl/" + target.removeprefix("../")
        if (
            kind not in ATTACHMENTS
            or not target.startswith("../")
            or target != "../" + resolved.removeprefix("xl/")
            or attachment_kind(resolved) != kind
            or resolved not in self.parts
        ):
            raise fail(code="UNSUPPORTED_WORKBOOK_PART")
        identifier = attrs["Id"]
        if (
            re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,127}", identifier) is None
            or identifier in self.identifiers
            or kind in self.current
            or resolved in self.owned
        ):
            raise fail(code="INVALID_WORKBOOK")
        self.identifiers.add(identifier)
        self.owned.add(resolved)
        self.current[kind] = Relationship.model_validate(
            {
                "source": "worksheet",
                "owner": self.owner,
                "id": identifier,
                "kind": kind,
                "target": resolved,
            }
        )

    def sheet_reference(self, tag: str, attrs: dict[str, str], _depth: int) -> None:
        """Match table and legacy-note references to their local bindings."""
        for local, kind in [
            ("legacyDrawing", "vmlDrawing"),
            ("tablePart", "table"),
        ]:
            if (
                tag
                == "http://schemas.openxmlformats.org/spreadsheetml/2006/main}" + local
            ):
                if kind in self.refs:
                    raise fail(code="INVALID_WORKBOOK")
                self.refs[kind] = attrs.get(
                    "http://schemas.openxmlformats.org/officeDocument/2006/relationships}id",
                    "",
                )


def read_annotation_relationships(
    parts: dict[str, XmlPart], budget: Budget
) -> list[Relationship]:
    """Bind each closed attachment to exactly one existing worksheet owner."""
    result: list[Relationship] = []
    owned: set[str] = set()
    for name in parts:
        if re.fullmatch(WORKSHEET_RELS, name) is not None:
            owner = "xl/worksheets/" + name.rsplit("/", 1)[1].removesuffix(".rels")
            if owner not in parts:
                raise fail(code="INVALID_WORKBOOK")
    for owner, part in parts.items():
        if re.fullmatch(r"xl/worksheets/sheet[1-9][0-9]*\.xml", owner) is None:
            continue
        name = "xl/worksheets/_rels/" + owner.rsplit("/", 1)[1] + ".rels"
        reader = AnnotationRelationships(owner, parts, owned)
        if name in parts:
            validate_xml(parts[name].content, budget, reader.start)
        validate_xml(part.content, budget, reader.sheet_reference)
        check_annotations(reader, budget)
        result.extend(reader.current.values())
    if owned != {n for n in parts if attachment_kind(n) is not None}:
        raise fail(code="INVALID_WORKBOOK")
    return result


def check_annotations(reader: AnnotationRelationships, budget: Budget) -> None:
    """Check closure, note anchors and table grammar independently of cells."""
    current, parts = reader.current, reader.parts
    if reader.refs != {
        k: r.id for k, r in current.items() if k in {"table", "vmlDrawing"}
    }:
        raise fail(code="INVALID_WORKBOOK")
    if ("comments" in current) != ("vmlDrawing" in current):
        raise fail(code="INVALID_WORKBOOK")
    if "comments" in current:
        note_refs(
            parts[current["comments"].target].content,
            parts[current["vmlDrawing"].target].content,
            budget,
        )
    if "table" in current:
        table_headers(parts[current["table"].target].content, budget)
