# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Closed OPC/ZIP contracts, actual decompression and hostile-byte rejection."""

import io
import random
import stat
import struct
import sys
import zipfile
import zlib
from pathlib import Path
from typing import TYPE_CHECKING, override

import pytest
from pydantic import ValidationError

from dscat.intake.archive import (
    EOCD,
    UINT16_MAX,
    UINT32_MAX,
    ZIP64_END,
    ZIP64_LOCATOR,
    XmlPart,
    check_descriptor,
    decompressed_chunks,
    directory_bounds,
    extra_fields,
    local_sizes,
    read_archive,
)
from dscat.intake.discovery import DiscoveryRequest
from dscat.intake.limits import Budget, IntakeError, Limits
from dscat.intake.worker import CoordinatorRequest, invoke

if TYPE_CHECKING:
    from collections.abc import Mapping

FIXTURE = Path(__file__).parent / "fixtures" / "workbook-1.0" / "template.xlsx"


@pytest.fixture(scope="module")
def parts() -> dict[str, bytes]:
    """Use the independent initial producer fixture as ordinary package content."""
    with zipfile.ZipFile(FIXTURE) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def archive_bytes(
    parts: Mapping[str, bytes], *, compression: int = zipfile.ZIP_DEFLATED
) -> bytes:
    """Construct synthetic containers without extracting any member to disk."""
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w", compression=compression) as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    return raw.getvalue()


def central_records(raw: bytes) -> dict[str, int]:
    """Locate known central records independently for targeted metadata corruption."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        position = archive.start_dir
    result: dict[str, int] = {}
    while raw[position : position + 4] == b"PK\x01\x02":
        name_size = int.from_bytes(raw[position + 28 : position + 30], "little")
        extra_size = int.from_bytes(raw[position + 30 : position + 32], "little")
        comment_size = int.from_bytes(raw[position + 32 : position + 34], "little")
        name = raw[position + 46 : position + 46 + name_size].decode()
        result[name] = position
        position += 46 + name_size + extra_size + comment_size
    return result


def patch_uint(raw: bytes, offset: int, value: int, *, size: int = 4) -> bytes:
    """Replace one fixed-width test field without regenerating consistent metadata."""
    return raw[:offset] + value.to_bytes(size, "little") + raw[offset + size :]


@pytest.mark.parametrize("compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
def test_complete_stored_and_deflated_packages(
    parts: dict[str, bytes], compression: int
) -> None:
    """Retain exact XML and local relationships without extraction."""
    result = read_archive(archive_bytes(parts, compression=compression), Budget())
    assert {part.name: part.content for part in result.parts} == parts
    assert result.statistics.members == len(parts)
    assert result.statistics.expanded_bytes == sum(map(len, parts.values()))
    assert all(
        not relationship.target.startswith("/") for relationship in result.relationships
    )


@pytest.mark.parametrize(
    "name",
    [
        "../escape.xml",
        "/absolute.xml",
        "xl\\styles.xml",
        "xl/vbaProject.bin",
        "xl/externalLinks/externalLink1.xml",
        "xl/worksheets/_rels/sheet1.xml.rels",
        "xl/tables/table1.xml",
        "xl/connections.xml",
        "xl/calcChain.xml",
        "xl/activeX/activeX1.bin",
        "xl/embeddings/oleObject1.bin",
    ],
)
def test_unknown_active_and_escaping_parts(parts: dict[str, bytes], name: str) -> None:
    """Unsupported package parts cannot be silently ignored or extracted."""
    with pytest.raises(IntakeError) as caught:
        read_archive(archive_bytes(parts | {name: b"synthetic"}), Budget())
    expected = (
        "INVALID_WORKBOOK"
        if name in {"xl/worksheets/_rels/sheet1.xml.rels", "xl/tables/table1.xml"}
        else "UNSUPPORTED_WORKBOOK_PART"
    )
    assert caught.value.diagnostic.code == expected


def test_missing_and_duplicate_parts(parts: dict[str, bytes]) -> None:
    """Required members must exist exactly once, even if duplicate bytes agree."""
    missing = {
        name: content for name, content in parts.items() if name != "xl/workbook.xml"
    }
    with pytest.raises(IntakeError, match="UNSUPPORTED_WORKBOOK_PART"):
        read_archive(archive_bytes(missing), Budget())
    output = io.BytesIO(archive_bytes(parts))
    with (
        zipfile.ZipFile(output, "a") as archive,
        pytest.warns(UserWarning, match="Duplicate name"),
    ):
        archive.writestr("xl/workbook.xml", parts["xl/workbook.xml"])
    with pytest.raises(IntakeError, match="UNSAFE_INPUT"):
        read_archive(output.getvalue(), Budget())


@pytest.mark.parametrize("compression", [zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA])
def test_unsupported_compression(parts: dict[str, bytes], compression: int) -> None:
    """Only stored and deflated member data can reach a decompressor."""
    with pytest.raises(IntakeError, match="UNSAFE_INPUT"):
        read_archive(archive_bytes(parts, compression=compression), Budget())


@pytest.mark.parametrize("flags", [1, 64, 8192, 32])
def test_encryption_and_unsupported_flags(parts: dict[str, bytes], flags: int) -> None:
    """Reject encryption and unsupported ZIP features before decompression."""
    raw = archive_bytes(parts)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        info = archive.getinfo("docProps/core.xml")
    central = central_records(raw)[info.filename]
    raw = patch_uint(raw, info.header_offset + 6, flags, size=2)
    raw = patch_uint(raw, central + 8, flags, size=2)
    with pytest.raises(IntakeError, match="UNSAFE_INPUT"):
        read_archive(raw, Budget())


def test_special_file_and_aes_extras(parts: dict[str, bytes]) -> None:
    """A normal part name does not authorize a symlink or encrypted member."""
    for mode, extra in (
        (stat.S_IFLNK | 0o777, b""),
        (stat.S_IFDIR | 0o755, b""),
        (stat.S_IFREG | 0o600, struct.pack("<HH", 0x9901, 0)),
    ):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            for name, content in parts.items():
                info = zipfile.ZipInfo(name)
                if name == "docProps/core.xml":
                    info.external_attr = mode << 16
                    info.extra = extra
                archive.writestr(info, content)
        with pytest.raises(IntakeError, match="UNSAFE_INPUT"):
            read_archive(output.getvalue(), Budget())


def test_parent_directories_may_be_stored_or_deflated(parts: dict[str, bytes]) -> None:
    """Only empty entries for actual supported parents are allowed."""
    for compression in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
        result = read_archive(
            archive_bytes(
                {"xl/": b"", "xl/worksheets/": b""} | parts, compression=compression
            ),
            Budget(),
        )
        assert len(result.parts) == len(parts)
    for name, content in (("unrelated/", b""), ("xl/", b"payload")):
        with pytest.raises(IntakeError, match="UNSAFE_INPUT"):
            read_archive(archive_bytes({name: content} | parts), Budget())


def test_crc_actual_sizes_and_recovery(parts: dict[str, bytes]) -> None:
    """Actual decompression rejects forged advertised sizes and CRCs."""
    raw = archive_bytes(parts)
    name = "docProps/core.xml"
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        info = archive.getinfo(name)
    central = central_records(raw)[name]
    new_size = len(parts[name]) - 1
    crc = zlib.crc32(parts[name][:new_size])
    forged = patch_uint(raw, info.header_offset + 22, new_size)
    forged = patch_uint(forged, info.header_offset + 14, crc)
    forged = patch_uint(forged, central + 24, new_size)
    forged = patch_uint(forged, central + 16, crc)
    with pytest.raises(IntakeError, match="UNSAFE_INPUT"):
        read_archive(forged, Budget())
    bad_crc = patch_uint(raw, info.header_offset + 14, 0)
    bad_crc = patch_uint(bad_crc, central + 16, 0)
    with pytest.raises(IntakeError, match="UNSAFE_INPUT"):
        read_archive(bad_crc, Budget())
    assert read_archive(raw, Budget()).statistics.members == len(parts)


@pytest.mark.parametrize(
    "raw", [b"", b"not a zip", b"PK\x05\x06", b"PK\x03\x04" + b"x" * 100]
)
def test_malformed_archive_fixed_failure(raw: bytes) -> None:
    """Malformed byte boundaries never expose exception text or payload values."""
    with pytest.raises(IntakeError) as caught:
        read_archive(raw, Budget())
    assert caught.value.diagnostic.code == "INVALID_WORKBOOK"


def test_directory_preflight_limits_and_multivolume(parts: dict[str, bytes]) -> None:
    """Bound central counts and refuse inconsistent or multipart ZIPs."""
    raw = archive_bytes(parts)
    position = raw.rfind(b"PK\x05\x06")
    for offset, value, size in (
        (4, 1, 2),
        (6, 1, 2),
        (8, 1, 2),
        (12, 0, 4),
        (16, len(raw) + 1, 4),
        (20, 1, 2),
    ):
        corrupted = patch_uint(raw, position + offset, value, size=size)
        with pytest.raises(IntakeError):
            read_archive(corrupted, Budget())
    with pytest.raises(IntakeError) as count:
        directory_bounds(raw, Budget(limits=Limits(members=len(parts) - 1)))
    assert count.value.diagnostic.limit == "members"
    assert directory_bounds(raw, Budget(limits=Limits(members=len(parts))))[1] == len(
        parts
    )
    with pytest.raises(IntakeError) as compressed:
        directory_bounds(raw, Budget(limits=Limits(compressed=len(raw) - 1)))
    assert compressed.value.diagnostic.limit == "compressed"
    assert directory_bounds(raw, Budget(limits=Limits(compressed=len(raw))))[1] == len(
        parts
    )


def zip64_container(raw: bytes) -> bytes:
    """Promote a complete ordinary container to valid ZIP64 directory framing."""
    position = raw.rfind(b"PK\x05\x06")
    values = EOCD.unpack_from(raw, position)
    count, size, offset = int(values[4]), int(values[5]), int(values[6])
    end = ZIP64_END.pack(b"PK\x06\x06", 44, 45, 45, 0, 0, count, count, size, offset)
    locator = ZIP64_LOCATOR.pack(b"PK\x06\x07", 0, position, 1)
    legacy = EOCD.pack(
        b"PK\x05\x06", 0, 0, UINT16_MAX, UINT16_MAX, UINT32_MAX, UINT32_MAX, 0
    )
    return raw[:position] + end + locator + legacy


def test_zip64_valid_and_corrupt_framing(parts: dict[str, bytes]) -> None:
    """Small ZIP64 containers retain all ceilings and single-volume/offset checks."""
    raw = zip64_container(archive_bytes(parts))
    assert read_archive(raw, Budget()).statistics.members == len(parts)
    position = raw.rfind(b"PK\x05\x06")
    for offset, value, size in (
        (position - 20, 0, 4),
        (position - 16, 1, 4),
        (position - 12, len(raw) + 1, 8),
        (position - 4, 2, 4),
        (position - 76, 0, 4),
        (position - 72, 43, 8),
        (position - 60, 1, 4),
    ):
        with pytest.raises(IntakeError):
            read_archive(patch_uint(raw, offset, value, size=size), Budget())
    missing = EOCD.pack(
        b"PK\x05\x06", 0, 0, UINT16_MAX, UINT16_MAX, UINT32_MAX, UINT32_MAX, 0
    )
    with pytest.raises(IntakeError, match="INVALID_WORKBOOK"):
        directory_bounds(missing, Budget())


class StreamingOutput(io.BytesIO):
    """A test-only non-seekable writer forces actual ZIP data descriptors."""

    @override
    def seekable(self) -> bool:
        """Report the actual simulated stream capability."""
        return False

    @override
    def seek(self, _offset: int, _whence: int = 0, /) -> int:
        """Refuse seek so the standard writer emits streamed headers/descriptors."""
        msg = "Synthetic non-seekable stream"
        raise OSError(msg)


@pytest.mark.parametrize("zip64", [False, True])
def test_actual_streamed_descriptors(parts: dict[str, bytes], *, zip64: bool) -> None:
    """Validate actual 32/64-bit data descriptors against observed data."""
    output = StreamingOutput()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            with archive.open(name, "w", force_zip64=zip64) as member:
                member.write(content)
    assert read_archive(output.getvalue(), Budget()).statistics.members == len(parts)


def test_extra_fields_and_descriptor_shape() -> None:
    """Malformed extra fields and truncated/mismatched descriptors fail closed."""
    for raw in (b"x", struct.pack("<HH", 2, 10) + b"x", struct.pack("<HH", 0x9901, 0)):
        with pytest.raises(IntakeError, match="UNSAFE_INPUT"):
            list(extra_fields(raw))
    assert list(extra_fields(struct.pack("<HH", 2, 1) + b"x")) == [(2, b"x")]
    for extra, compressed, expanded in (
        (struct.pack("<HH", 1, 0), 0, UINT32_MAX),
        (struct.pack("<HH", 1, 0), UINT32_MAX, 0),
        (struct.pack("<HH", 1, 0) * 2, 0, 0),
    ):
        with pytest.raises(IntakeError, match="UNSAFE_INPUT"):
            local_sizes(extra, compressed, expanded)
    info = zipfile.ZipInfo("xl/workbook.xml")
    info.flag_bits = 8
    info.CRC = 1
    info.compress_size = 2
    info.file_size = 3
    for raw in (b"x", struct.pack("<III", 0, 2, 3)):
        with pytest.raises(IntakeError, match="UNSAFE_INPUT"):
            check_descriptor(raw, info, 0, len(raw))
    for raw in (struct.pack("<III", 1, 2, 3), struct.pack("<IQQ", 1, 2, 3)):
        check_descriptor(raw, info, 0, len(raw))


def test_truncated_and_trailing_deflate_streams() -> None:
    """Require actual end-of-stream without hidden trailing data."""
    compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
    raw = compressor.compress(b"<a>synthetic</a>") + compressor.flush()
    info = zipfile.ZipInfo("xl/workbook.xml")
    info.compress_type = zipfile.ZIP_DEFLATED
    assert (
        b"".join(decompressed_chunks(raw, info, 0, len(raw), Budget()))
        == b"<a>synthetic</a>"
    )
    for corrupted in (raw[:-1], raw + b"trailing"):
        with pytest.raises(IntakeError, match="UNSAFE_INPUT"):
            list(decompressed_chunks(corrupted, info, 0, len(corrupted), Budget()))


@pytest.mark.parametrize(
    ("part", "before", "after"),
    [
        (
            "xl/_rels/workbook.xml.rels",
            b'Target="worksheets/sheet1.xml"',
            b'Target="https://example.org/" TargetMode="External"',
        ),
        (
            "xl/_rels/workbook.xml.rels",
            b'Target="worksheets/sheet1.xml"',
            b'Target="/xl/worksheets/sheet1.xml"',
        ),
        (
            "xl/_rels/workbook.xml.rels",
            b'Target="worksheets/sheet1.xml"',
            b'Target="../worksheets/sheet1.xml"',
        ),
        (
            "xl/_rels/workbook.xml.rels",
            b'Target="worksheets/sheet1.xml"',
            b'Target="missing.xml"',
        ),
        ("xl/_rels/workbook.xml.rels", b'Id="rId1"', b'Id="rId2"'),
        (
            "xl/_rels/workbook.xml.rels",
            b'/relationships/worksheet"',
            b'/relationships/unknown"',
        ),
        (
            "[Content_Types].xml",
            b"spreadsheetml.sheet.main+xml",
            b"spreadsheetml.macroEnabled.main+xml",
        ),
        ("[Content_Types].xml", b'Extension="xml"', b'Extension="exe"'),
    ],
)
def test_relationship_and_mime_boundaries(
    parts: dict[str, bytes], part: str, before: bytes, after: bytes
) -> None:
    """No external, escaping, unknown, duplicate or falsely typed target is accepted."""
    assert before in parts[part]
    with pytest.raises(IntakeError):
        read_archive(
            archive_bytes(parts | {part: parts[part].replace(before, after, 1)}),
            Budget(),
        )


def test_structured_part_names_are_closed() -> None:
    """Typed archive parts cannot reintroduce a path rejected by preflight."""
    with pytest.raises(ValidationError, match="Unsupported workbook part"):
        XmlPart(name="../synthetic", content=b"x")


@pytest.fixture(scope="module")
def padding_bits() -> bytes:
    """Provide deterministic low-entropy comment bytes without long imported text."""
    noise = random.Random(17).randbytes(2 * 1024**2)  # noqa: S311 -- synthetic padding.
    return b"".join(f"{value:08b}".encode() for value in noise)


def padded_parts(
    parts: dict[str, bytes], target: int, padding: bytes
) -> dict[str, bytes]:
    """Pad existing XML with inert comments within every part cap."""
    result = dict(parts)
    remaining = target - sum(map(len, result.values()))
    comment_size = len(b"<!---->")
    for name in parts:
        if name.endswith(".rels") or name == "[Content_Types].xml" or remaining == 0:
            continue
        room = 16 * 1024**2 - len(result[name])
        if remaining < comment_size:
            addition = b" " * remaining
        else:
            amount = min(remaining, room) - comment_size
            addition = b"<!--" + padding[:amount] + b"-->"
        result[name] += addition
        remaining -= len(addition)
    assert remaining == 0
    assert all(len(data) <= 16 * 1024**2 for data in result.values())
    return result


def test_actual_compressed_byte_ceiling(
    parts: dict[str, bytes], padding_bits: bytes
) -> None:
    """A complete valid package accepts exactly 32 MiB and rejects the next byte."""
    maximum = 32 * 1024**2
    baseline = archive_bytes(parts, compression=zipfile.ZIP_STORED)
    overhead = len(baseline) - sum(map(len, parts.values()))
    padded = padded_parts(parts, maximum - overhead, padding_bits)
    raw = archive_bytes(padded, compression=zipfile.ZIP_STORED)
    assert len(raw) == maximum
    assert read_archive(raw, Budget()).statistics.compressed_bytes == maximum
    changed = dict(padded)
    name = next(name for name, data in changed.items() if len(data) < 16 * 1024**2)
    changed[name] += b" "
    with pytest.raises(IntakeError) as caught:
        read_archive(archive_bytes(changed, compression=zipfile.ZIP_STORED), Budget())
    assert caught.value.diagnostic.limit == "compressed"


def test_actual_expanded_byte_ceiling(
    parts: dict[str, bytes], padding_bits: bytes
) -> None:
    """Accept 128 MiB expansion with all other ceilings satisfied."""
    maximum = 128 * 1024**2
    padded = padded_parts(parts, maximum, padding_bits)
    raw = archive_bytes(padded)
    assert len(raw) < 32 * 1024**2
    assert read_archive(raw, Budget()).statistics.expanded_bytes == maximum
    changed = dict(padded)
    name = next(
        name
        for name, data in changed.items()
        if not name.endswith(".rels")
        and name != "[Content_Types].xml"
        and len(data) < 16 * 1024**2
    )
    changed[name] += b" "
    with pytest.raises(IntakeError) as caught:
        read_archive(archive_bytes(changed), Budget())
    assert caught.value.diagnostic.limit == "expanded"


def test_remaining_invocation_expansion_is_inclusive(parts: dict[str, bytes]) -> None:
    """The coordinator's remaining aggregate budget is enforced on actual bytes."""
    size = sum(map(len, parts.values()))
    raw = archive_bytes(parts)
    assert (
        read_archive(raw, Budget(remaining_expanded=size)).statistics.expanded_bytes
        == size
    )
    with pytest.raises(IntakeError) as caught:
        read_archive(raw, Budget(remaining_expanded=size - 1))
    assert caught.value.diagnostic.limit == "expanded"


def raw_deflate(payload: bytes) -> bytes:
    """Measure the same standard raw-deflate format independently of the reader."""
    compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
    return compressor.compress(payload) + compressor.flush()


def test_actual_member_ratio_exact_and_just_over(parts: dict[str, bytes]) -> None:
    """An actual 100:1 member is accepted; an additional emitted byte is rejected."""
    original = parts["docProps/core.xml"]
    noise = random.Random(31).randbytes(2500).hex().encode()  # noqa: S311 -- synthetic fixture.
    length = 100000
    compressed_length = 1000
    payload = None
    for index in range(len(noise)):
        candidate = (
            original
            + b"<!--"
            + noise[:index]
            + b"x" * (length - len(original) - index - 7)
            + b"-->"
        )
        bigger = candidate[:-3] + b"x-->"
        if (
            len(raw_deflate(candidate)) == compressed_length
            and len(raw_deflate(bigger)) == compressed_length
        ):
            payload = candidate
            break
    assert payload is not None
    positive = archive_bytes(parts | {"docProps/core.xml": payload})
    assert read_archive(positive, Budget()).statistics.expanded_bytes > 0
    with pytest.raises(IntakeError) as caught:
        read_archive(
            archive_bytes(parts | {"docProps/core.xml": payload[:-3] + b"x-->"}),
            Budget(),
        )
    assert caught.value.diagnostic.limit == "ratio"


def test_actual_deflate_bomb_and_xml_bytes_are_not_header_only(
    parts: dict[str, bytes],
) -> None:
    """Reject actual high-ratio output despite consistent ZIP headers."""
    bomb = parts["docProps/core.xml"] + b"<!--" + b"x" * (1024**2) + b"-->"
    with pytest.raises(IntakeError) as caught:
        read_archive(archive_bytes(parts | {"docProps/core.xml": bomb}), Budget())
    assert caught.value.diagnostic.limit == "ratio"
    large = parts["docProps/core.xml"] + b"<!--" + b"x" * (16 * 1024**2) + b"-->"
    with pytest.raises(IntakeError) as xml:
        read_archive(
            archive_bytes(
                parts | {"docProps/core.xml": large}, compression=zipfile.ZIP_STORED
            ),
            Budget(),
        )
    assert xml.value.diagnostic.limit == "xml"


def test_sheet_part_count_and_no_worksheet(parts: dict[str, bytes]) -> None:
    """Sheet count includes all actual parts, not only declared or visible sheets."""
    missing = {
        name: data
        for name, data in parts.items()
        if not name.startswith("xl/worksheets/")
    }
    with pytest.raises(IntakeError, match="INVALID_WORKBOOK"):
        read_archive(archive_bytes(missing), Budget())
    extended = parts | {
        f"xl/worksheets/sheet{index}.xml": b"<a/>" for index in range(5, 34)
    }
    with pytest.raises(IntakeError) as sheets:
        read_archive(archive_bytes(extended), Budget())
    assert sheets.value.diagnostic.limit == "sheets"


@pytest.mark.parametrize(
    ("part", "before", "after"),
    [
        ("_rels/.rels", b"<Relationships ", b'<Relationships extra="x" '),
        ("_rels/.rels", b"<Relationship ", b"<Unknown "),
        (
            "_rels/.rels",
            b"http://schemas.openxmlformats.org/package/2006/relationships",
            b"urn:synthetic",
        ),
        ("[Content_Types].xml", b"<Types ", b'<Types extra="x" '),
        ("[Content_Types].xml", b"<Default ", b"<Unknown "),
        (
            "[Content_Types].xml",
            b'PartName="/xl/styles.xml"',
            b'PartName="xl/styles.xml"',
        ),
        (
            "[Content_Types].xml",
            b"http://schemas.openxmlformats.org/package/2006/content-types",
            b"urn:synthetic",
        ),
    ],
)
def test_package_metadata_has_exact_structure(
    parts: dict[str, bytes], part: str, before: bytes, after: bytes
) -> None:
    """Foreign roots, attributes and child shapes cannot bypass package closure."""
    assert before in parts[part]
    with pytest.raises(IntakeError):
        read_archive(
            archive_bytes(parts | {part: parts[part].replace(before, after, 1)}),
            Budget(),
        )


def test_missing_relationship_and_nested_content_type(parts: dict[str, bytes]) -> None:
    """The complete local relationship closure and flat MIME structure are required."""
    part = "_rels/.rels"
    original = parts[part]
    start = original.index(b"<Relationship ")
    end = original.index(b"/>", start) + 2
    with pytest.raises(IntakeError, match="INVALID_WORKBOOK"):
        read_archive(
            archive_bytes(parts | {part: original[:start] + original[end:]}), Budget()
        )
    part = "[Content_Types].xml"
    original = (
        parts[part]
        .replace(b"<Default ", b"<nest><Default ", 1)
        .replace(b"/>", b"/></nest>", 1)
    )
    with pytest.raises(IntakeError):
        read_archive(archive_bytes(parts | {part: original}), Budget())


@pytest.mark.parametrize(
    ("offset", "value", "size"),
    [(0, 0, 4), (6, 1, 2), (8, 0, 2), (14, 1, 4), (26, 65535, 2)],
)
def test_local_header_disagreement(
    parts: dict[str, bytes], offset: int, value: int, size: int
) -> None:
    """Local headers must agree with the central record before decompression."""
    raw = archive_bytes(parts)
    with pytest.raises(IntakeError):
        read_archive(patch_uint(raw, offset, value, size=size), Budget())


def test_local_filename_offset_prefix_and_overlapping_extent(
    parts: dict[str, bytes],
) -> None:
    """Refuse prefixes, aliases, out-of-range offsets and overlapping extents."""
    raw = archive_bytes(parts)
    changed = raw[:30] + b"!" + raw[31:]
    with pytest.raises(IntakeError):
        read_archive(changed, Budget())
    records = central_records(raw)
    central = next(iter(records.values()))
    with pytest.raises(IntakeError):
        read_archive(patch_uint(raw, central + 42, len(raw)), Budget())
    prefixed = io.BytesIO(b"synthetic-prefix")
    prefixed.seek(0, io.SEEK_END)
    with zipfile.ZipFile(prefixed, "a", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    with pytest.raises(IntakeError):
        read_archive(prefixed.getvalue(), Budget())
    size = int.from_bytes(raw[18:22], "little") + 1
    overlap = patch_uint(patch_uint(raw, 18, size), central + 20, size)
    with pytest.raises(IntakeError):
        read_archive(overlap, Budget())


def test_harmless_unknown_extras_and_corrupt_deflate(parts: dict[str, bytes]) -> None:
    """Framed inert extras are accepted; malformed deflate emits a fixed failure."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            info = zipfile.ZipInfo(name)
            info.extra = struct.pack("<HH", 1234, 1) + b"x"
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
    assert read_archive(output.getvalue(), Budget()).statistics.members == len(parts)
    raw = archive_bytes(parts)
    offset = 30 + len(next(iter(parts)).encode())
    malformed = raw[:offset] + b"\xff" + raw[offset + 1 :]
    with pytest.raises(IntakeError, match="INVALID_WORKBOOK"):
        read_archive(malformed, Budget())


def test_directory_actual_payload_and_crc_are_rejected(parts: dict[str, bytes]) -> None:
    """Empty directory metadata cannot hide emitted bytes or a false CRC."""
    for payload in (b"x", b""):
        raw = archive_bytes(parts | {"xl/": payload})
        central = central_records(raw)["xl/"]
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            offset = archive.getinfo("xl/").header_offset
        crc = 0 if payload else 1
        changed = patch_uint(patch_uint(raw, central + 24, 0), offset + 22, 0)
        changed = patch_uint(patch_uint(changed, central + 16, crc), offset + 14, crc)
        with pytest.raises(IntakeError, match="UNSAFE_INPUT"):
            read_archive(changed, Budget())


@pytest.mark.skipif(
    sys.platform != "linux", reason="Requires native Linux hard memory guard."
)
def test_guarded_exact_aggregate_expansion(
    parts: dict[str, bytes], padding_bits: bytes, tmp_path: Path
) -> None:
    """Two real 128 MiB workers fit the guard and the inclusive 256 MiB invocation."""
    padded = padded_parts(parts, 128 * 1024**2, padding_bits)
    raw = archive_bytes(padded)
    for name in ("a.xlsx", "b.xlsx", "c.xlsx"):
        (tmp_path / name).write_bytes(raw)
    reply = invoke(
        CoordinatorRequest(
            schema_version="1.0",
            role="coordinator",
            discovery=DiscoveryRequest(input=tmp_path),
        ),
        120.0,
    )
    assert [outcome.archive_state for outcome in reply.outcomes] == ["safe", "safe"]
    assert (
        sum(outcome.statistics.expanded_bytes for outcome in reply.outcomes)
        == 256 * 1024**2
    )
    assert reply.unexamined_sources == 1
    assert any(item.limit == "expanded" for item in reply.diagnostics)
    (tmp_path / "c.xlsx").unlink()
    positive = invoke(
        CoordinatorRequest(
            schema_version="1.0",
            role="coordinator",
            discovery=DiscoveryRequest(input=tmp_path),
        ),
        120.0,
    )
    assert not positive.has_errors
    assert positive.unexamined_sources == 0


def test_descriptor_local_sizes_and_hidden_gap(parts: dict[str, bytes]) -> None:
    """Streaming headers cannot advertise conflicting sizes; gaps cannot hide data."""
    output = StreamingOutput()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    raw = output.getvalue()
    with pytest.raises(IntakeError):
        read_archive(patch_uint(raw, 14, 1), Budget())
    ordinary = archive_bytes(parts)
    records = central_records(ordinary)
    central = next(iter(records.values()))
    size = int.from_bytes(ordinary[18:22], "little") - 1
    gapped = patch_uint(patch_uint(ordinary, 18, size), central + 20, size)
    with pytest.raises(IntakeError):
        read_archive(gapped, Budget())


def test_content_type_children_cannot_nest(parts: dict[str, bytes]) -> None:
    """A supported MIME element still cannot contain deeper child declarations."""
    part = "[Content_Types].xml"
    original = parts[part]
    start = original.index(b"<Default ")
    end = original.index(b"/>", start)
    element = original[start:end]
    nested = original[:end] + b">" + element + b"/></Default>" + original[end + 2 :]
    with pytest.raises(IntakeError):
        read_archive(archive_bytes(parts | {part: nested}), Budget())


def test_decompressor_drains_buffered_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """The stream adapter accepts output buffered until its final empty-input drain."""

    class BufferedDecoder:
        """Controlled decoder honoring the incremental decompressor interface."""

        unconsumed_tail = b""
        unused_data = b""
        eof = False

        def decompress(self, payload: bytes, _maximum: int) -> bytes:
            if payload:
                return b""
            self.eof = True
            return b"x"

    monkeypatch.setattr(zlib, "decompressobj", lambda _window: BufferedDecoder())
    info = zipfile.ZipInfo("synthetic.xml")
    info.compress_type = zipfile.ZIP_DEFLATED
    assert b"".join(decompressed_chunks(b"x", info, 0, 1, Budget())) == b"x"


def test_member_ceiling_precedes_closed_part_allocation() -> None:
    """Count valid central entries before constructing package-member objects."""
    maximum = 4096
    raw = archive_bytes({f"synthetic-{index}": b"" for index in range(maximum)})
    assert directory_bounds(raw, Budget())[1] == maximum
    with pytest.raises(IntakeError, match="UNSUPPORTED_WORKBOOK_PART"):
        read_archive(raw, Budget())
    oversized = archive_bytes(
        {f"synthetic-{index}": b"" for index in range(maximum + 1)}
    )
    with pytest.raises(IntakeError) as caught:
        directory_bounds(oversized, Budget())
    assert caught.value.diagnostic.limit == "members"


@pytest.mark.parametrize("mime", ["application/x-unknown-active", "application/xml"])
def test_content_types_cannot_declare_its_own_type(
    parts: dict[str, bytes], mime: str
) -> None:
    """The package's content-type control part cannot override its own type."""
    part = "[Content_Types].xml"
    declaration = (
        '<Override PartName="/[Content_Types].xml" ContentType="' + mime + '"/>'
    ).encode()
    changed = parts[part].replace(b"</Types>", declaration + b"</Types>")
    with pytest.raises(IntakeError, match="UNSUPPORTED_WORKBOOK_PART"):
        read_archive(archive_bytes(parts | {part: changed}), Budget())
