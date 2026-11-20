# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Inspect bounded distribution bytes and compare their actual packaged source."""

import base64
import csv
import gzip
import hashlib
import io
import stat
import tarfile
import unicodedata
import zipfile
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

if TYPE_CHECKING:
    from email.message import Message

    from scripts.evidence_models import ProjectIdentity

ARCHIVE_BYTES = 32 * 1024**2
EXPANDED_BYTES = 256 * 1024**2
MEMBER_BYTES = 32 * 1024**2
MEMBER_COUNT = 4096
RECORD_COLUMNS = 3
FIRST_PRINTABLE = 32
DELETE_CHARACTER = 127


@dataclass(frozen=True)
class ArtifactInspection:
    """Inspection binds exact archives to their source and declared dependencies."""

    wheel_sha256: str
    sdist_sha256: str
    package_files: int
    requirements: tuple[str, ...]


def artifact_name(name: str) -> str:
    """Reject traversal, aliases and platform-specific path interpretation."""
    path = PurePosixPath(name)
    if (
        not name
        or not path.parts
        or path.is_absolute()
        or "\\" in name
        or ":" in name
        or "\x00" in name
        or any(
            ord(character) < FIRST_PRINTABLE or ord(character) == DELETE_CHARACTER
            for character in name
        )
        or path.as_posix() != name
        or any(part in {".", ".."} for part in path.parts)
        or unicodedata.normalize("NFC", name) != name
    ):
        msg = "Distribution member path is unsafe or ambiguous."
        raise ValueError(msg)
    return name


def add_member(
    result: dict[str, bytes], aliases: set[str], name: str, content: bytes
) -> None:
    """Enforce finite distinct members and reject case-folding filename collisions."""
    name = artifact_name(name)
    alias = name.casefold()
    if alias in aliases or len(result) >= MEMBER_COUNT:
        msg = "Distribution member set is ambiguous or exceeds its limit."
        raise ValueError(msg)
    if (
        len(content) > MEMBER_BYTES
        or sum(map(len, result.values())) + len(content) > EXPANDED_BYTES
    ):
        msg = "Distribution expanded bytes exceed their limit."
        raise ValueError(msg)
    aliases.add(alias)
    result[name] = content


def wheel_members(raw: bytes) -> dict[str, bytes]:
    """Inspect regular unencrypted ZIP members without extracting paths or code."""
    if len(raw) > ARCHIVE_BYTES:
        msg = "Wheel archive exceeds its compressed-byte limit."
        raise ValueError(msg)
    result: dict[str, bytes] = {}
    aliases: set[str] = set()
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if len(archive.infolist()) > MEMBER_COUNT:
                msg = "Wheel archive exceeds its member limit."
                raise ValueError(msg)
            for entry in archive.infolist():
                if entry.is_dir():
                    artifact_name(entry.filename.removesuffix("/"))
                    continue
                mode = entry.external_attr >> 16
                if (
                    entry.flag_bits & 1
                    or stat.S_IFMT(mode) not in {0, stat.S_IFREG}
                    or entry.compress_type
                    not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                    or entry.file_size > MEMBER_BYTES
                    or sum(map(len, result.values())) + entry.file_size > EXPANDED_BYTES
                ):
                    msg = "Wheel member type or size is unsupported."
                    raise ValueError(msg)
                with archive.open(entry) as stream:
                    content = stream.read(MEMBER_BYTES + 1)
                add_member(result, aliases, entry.filename, content)
    except OSError, zipfile.BadZipFile, RuntimeError:
        msg = "Wheel archive is unreadable or malformed."
        raise ValueError(msg) from None
    return result


def sdist_members(raw: bytes) -> dict[str, bytes]:
    """Bound gzip expansion before TAR/PAX parsing and reject special files."""
    if len(raw) > ARCHIVE_BYTES:
        msg = "Source archive exceeds its compressed-byte limit."
        raise ValueError(msg)
    result: dict[str, bytes] = {}
    aliases: set[str] = set()
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            expanded = stream.read(EXPANDED_BYTES + 1)
        if len(expanded) > EXPANDED_BYTES:
            msg = "Source archive exceeds its expanded-byte limit."
            raise ValueError(msg)
        with tarfile.open(fileobj=io.BytesIO(expanded), mode="r:") as archive:
            for index, entry in enumerate(archive):
                if index >= MEMBER_COUNT:
                    msg = "Source archive exceeds its member limit."
                    raise ValueError(msg)
                if entry.isdir():
                    artifact_name(entry.name.removesuffix("/"))
                    continue
                if not entry.isfile() or entry.size > MEMBER_BYTES:
                    msg = "Source archive member type or size is unsupported."
                    raise ValueError(msg)
                stream = archive.extractfile(entry)
                if stream is None:
                    msg = "Source archive member could not be read."
                    raise ValueError(msg)
                with stream:
                    content = stream.read(MEMBER_BYTES + 1)
                add_member(result, aliases, entry.name, content)
    except OSError, tarfile.TarError, EOFError:
        msg = "Source archive is unreadable or malformed."
        raise ValueError(msg) from None
    return result


def check_record(members: dict[str, bytes], prefix: str) -> None:
    """Verify actual wheel bytes and RECORD completeness independently."""
    name = prefix + "RECORD"
    rows = list(csv.reader(io.StringIO(members[name].decode("utf-8"), newline="")))
    names: set[str] = set()
    for row in rows:
        if len(row) != RECORD_COLUMNS or row[0] in names or row[0] not in members:
            msg = "Wheel RECORD members are ambiguous or incomplete."
            raise ValueError(msg)
        names.add(row[0])
        if row[0] == name:
            if row[1:] != ["", ""]:
                msg = "Wheel RECORD cannot assert its own content hash."
                raise ValueError(msg)
            continue
        content = members[row[0]]
        digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=")
        if row[1] != "sha256=" + digest.decode("ascii") or row[2] != str(len(content)):
            msg = "Wheel RECORD does not match actual member bytes."
            raise ValueError(msg)
    if names != set(members):
        msg = "Wheel RECORD omits distribution members."
        raise ValueError(msg)


def one_header(metadata: Message, name: str) -> str:
    """Reject missing or duplicated authoritative metadata fields."""
    values = metadata.get_all(name, [])
    if len(values) != 1 or not isinstance(values[0], str):
        msg = "Distribution metadata identity is missing or ambiguous."
        raise ValueError(msg)
    return values[0]


def check_metadata(raw: bytes, project: ProjectIdentity) -> tuple[str, ...]:
    """Require the selected proprietary project metadata and exact dependency intent."""
    metadata = BytesParser(policy=policy.default).parsebytes(raw)
    if (
        metadata.defects
        or one_header(metadata, "Name") != "dscat"
        or one_header(metadata, "Version") != project.version
        or SpecifierSet(one_header(metadata, "Requires-Python"))
        != SpecifierSet(project.requires_python)
        or one_header(metadata, "License-Expression") != "LicenseRef-Proprietary"
    ):
        msg = "Distribution metadata does not match the project."
        raise ValueError(msg)
    actual = [
        str(Requirement(value)) for value in metadata.get_all("Requires-Dist", [])
    ]
    expected = [str(Requirement(value)) for value in project.requirements]
    if len(actual) != len(set(actual)) or sorted(actual) != sorted(expected):
        msg = "Distribution runtime requirements do not match the project."
        raise ValueError(msg)
    return tuple(sorted(actual))


def inspect_artifacts(
    wheel: bytes,
    sdist: bytes,
    source: dict[str, bytes],
    project: ProjectIdentity,
) -> ArtifactInspection:
    """Compare actual wheel/sdist/source bytes and reject missing or unrelated files."""
    wheel_files, source_files = wheel_members(wheel), sdist_members(sdist)
    wheel_prefix = f"dscat-{project.version}.dist-info/"
    source_prefix = f"dscat-{project.version}/"
    required = {
        wheel_prefix + name
        for name in ["METADATA", "WHEEL", "RECORD", "licenses/LICENSE"]
    }
    if not required <= set(wheel_files) or any(
        not name.startswith(("dscat/", wheel_prefix)) for name in wheel_files
    ):
        msg = "Wheel members do not match the expected distribution layout."
        raise ValueError(msg)
    check_record(wheel_files, wheel_prefix)
    dependencies = check_metadata(wheel_files[wheel_prefix + "METADATA"], project)
    if any(not name.startswith(source_prefix) for name in source_files):
        msg = "Source archive has an unexpected root."
        raise ValueError(msg)
    archived_source = {
        name.removeprefix(source_prefix): raw for name, raw in source_files.items()
    }
    pkg_info = archived_source.pop("PKG-INFO", None)
    if pkg_info is None or archived_source != source:
        msg = "Source distribution does not match the reviewed source snapshot."
        raise ValueError(msg)
    check_metadata(pkg_info, project)
    packaged = {
        "src/" + name: raw
        for name, raw in wheel_files.items()
        if name.startswith("dscat/")
    }
    expected = {
        name: raw for name, raw in source.items() if name.startswith("src/dscat/")
    }
    if packaged != expected or wheel_files[
        wheel_prefix + "licenses/LICENSE"
    ] != source.get("LICENSE"):
        msg = "Wheel source or proprietary license does not match reviewed source."
        raise ValueError(msg)
    return ArtifactInspection(
        wheel_sha256=hashlib.sha256(wheel).hexdigest(),
        sdist_sha256=hashlib.sha256(sdist).hexdigest(),
        package_files=len(packaged),
        requirements=dependencies,
    )
