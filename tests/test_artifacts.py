# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Wheel/source identity, RECORD integrity and safe bounded archive inspection."""

import base64
import csv
import hashlib
import io
import tarfile
import zipfile

import pytest
from scripts import artifacts
from scripts.evidence_models import ProjectIdentity

PREFIX = "dscat-0.1.0.dist-info/"
SOURCE_PREFIX = "dscat-0.1.0/"
METADATA = (
    b"Metadata-Version: 2.4\nName: dscat\nVersion: 0.1.0\n"
    b"Requires-Python: >=3.15,<3.16\n"
    b"License-Expression: LicenseRef-Proprietary\n"
    b"Requires-Dist: foo==1\n\nSynthetic description.\n"
)
PROJECT = ProjectIdentity(
    version="0.1.0", requires_python=">=3.15,<3.16", requirements=["foo==1"]
)
SOURCE = {
    "src/dscat/__init__.py": b'__version__ = "0.1.0"\n',
    "LICENSE": b"Synthetic proprietary license.\n",
    "README.md": b"Synthetic project.\n",
}


def wheel_files() -> dict[str, bytes]:
    """Provide actual metadata/license and one synthetic package source file."""
    return {
        "dscat/__init__.py": SOURCE["src/dscat/__init__.py"],
        PREFIX + "METADATA": METADATA,
        PREFIX
        + "WHEEL": b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        PREFIX + "licenses/LICENSE": SOURCE["LICENSE"],
    }


def zipped(files: dict[str, bytes], *, record: bool = True) -> bytes:
    """Construct a consistent wheel for corruption tests at each boundary."""
    files = dict(files)
    if record:
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        for name, content in files.items():
            digest = (
                base64.urlsafe_b64encode(hashlib.sha256(content).digest())
                .rstrip(b"=")
                .decode()
            )
            writer.writerow([name, "sha256=" + digest, str(len(content))])
        writer.writerow([PREFIX + "RECORD", "", ""])
        files[PREFIX + "RECORD"] = stream.getvalue().encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()


def tarred(files: dict[str, bytes] | None = None) -> bytes:
    """Provide reviewed source plus standard generated PKG-INFO without extraction."""
    if files is None:
        files = {
            SOURCE_PREFIX + name: content
            for name, content in (SOURCE | {"PKG-INFO": METADATA}).items()
        }
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return output.getvalue()


def test_real_record_metadata_and_source_comparison() -> None:
    """Exact wheel/source bytes, dependency intent and proprietary notice all agree."""
    wheel, sdist = zipped(wheel_files()), tarred()
    result = artifacts.inspect_artifacts(wheel, sdist, SOURCE, PROJECT)
    assert result.package_files == 1
    assert result.wheel_sha256 == hashlib.sha256(wheel).hexdigest()
    assert result.sdist_sha256 == hashlib.sha256(sdist).hexdigest()
    assert result.requirements == ("foo==1",)


@pytest.mark.parametrize(
    "mutation",
    [
        "source",
        "license",
        "layout",
        "metadata_version",
        "metadata_license",
        "metadata_requirements",
        "metadata_duplicate",
    ],
)
def test_wheel_content_mismatch_is_refused(mutation: str) -> None:
    """Reject unrelated source or project intent even with a recomputed RECORD."""
    files = wheel_files()
    if mutation in {"source", "license", "layout"}:
        key = {
            "source": "dscat/__init__.py",
            "license": PREFIX + "licenses/LICENSE",
            "layout": "unexpected/file",
        }[mutation]
        files[key] = b"synthetic changed content"
    else:
        old, new = {
            "metadata_version": (b"Version: 0.1.0", b"Version: 0.2.0"),
            "metadata_license": (b"LicenseRef-Proprietary", b"MIT"),
            "metadata_requirements": (b"foo==1", b"foo==2"),
            "metadata_duplicate": (b"Name: dscat", b"Name: dscat\nName: another"),
        }[mutation]
        files[PREFIX + "METADATA"] = METADATA.replace(old, new)
    with pytest.raises(ValueError, match=r"[Dd]istribution|Wheel"):
        artifacts.inspect_artifacts(zipped(files), tarred(), SOURCE, PROJECT)


@pytest.mark.parametrize("mutation", ["root", "missing", "extra", "source", "pkg_info"])
def test_source_archive_mismatch_is_refused(mutation: str) -> None:
    """The source archive must preserve reviewed files and its actual metadata."""
    source = SOURCE | {"PKG-INFO": METADATA}
    if mutation == "missing":
        source.pop("README.md")
    elif mutation == "extra":
        source["unexpected"] = b"synthetic"
    elif mutation == "source":
        source["src/dscat/__init__.py"] = b"synthetic changed source"
    elif mutation == "pkg_info":
        source.pop("PKG-INFO")
    prefix = "unexpected/" if mutation == "root" else SOURCE_PREFIX
    raw = tarred({prefix + name: content for name, content in source.items()})
    with pytest.raises(ValueError, match="Source"):
        artifacts.inspect_artifacts(zipped(wheel_files()), raw, SOURCE, PROJECT)


@pytest.mark.parametrize(
    "mutation", ["hash", "size", "missing", "duplicate", "self", "shape"]
)
def test_record_integrity_is_independent_of_archive_validity(mutation: str) -> None:
    """Reject altered bytes, missing rows and self-certifying RECORD data."""
    members = artifacts.wheel_members(zipped(wheel_files()))
    rows = list(csv.reader(io.StringIO(members[PREFIX + "RECORD"].decode())))
    if mutation == "hash":
        rows[0][1] = "sha256=" + "0" * 43
    elif mutation == "size":
        rows[0][2] = "999"
    elif mutation == "missing":
        rows.pop(0)
    elif mutation == "duplicate":
        rows.append(rows[0])
    elif mutation == "self":
        rows[-1][1] = "sha256=self"
    else:
        rows[0].pop()
    record = io.StringIO(newline="")
    csv.writer(record).writerows(rows)
    members[PREFIX + "RECORD"] = record.getvalue().encode()
    with pytest.raises(ValueError, match="RECORD"):
        artifacts.check_record(members, PREFIX)


@pytest.mark.parametrize(
    "name",
    [
        "../escape",
        "/absolute",
        "a/../b",
        "a//b",
        "a/./b",
        "C:/drive",
        "a\\b",
        ".",
        "",
        "a\x00b",
        "a\nb",
        "e\u0301.txt",
    ],
)
def test_unsafe_archive_member_paths(name: str) -> None:
    """Refuse traversal, aliases, controls and platform-specific separators."""
    with pytest.raises(ValueError, match="member path"):
        artifacts.artifact_name(name)


def test_archive_corruption_case_alias_and_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Corrupt formats, ambiguous names and compressed/expanded limits fail closed."""
    with pytest.raises(ValueError, match="Wheel archive"):
        artifacts.wheel_members(b"synthetic invalid")
    with pytest.raises(ValueError, match="Source archive"):
        artifacts.sdist_members(b"synthetic invalid")
    with pytest.raises(ValueError, match="ambiguous"):
        artifacts.wheel_members(zipped({"a": b"one", "A": b"two"}, record=False))
    monkeypatch.setattr(artifacts, "ARCHIVE_BYTES", 1)
    with pytest.raises(ValueError, match="compressed-byte"):
        artifacts.wheel_members(zipped(wheel_files()))
    with pytest.raises(ValueError, match="compressed-byte"):
        artifacts.sdist_members(tarred())
    monkeypatch.setattr(artifacts, "ARCHIVE_BYTES", 32 * 1024**2)
    monkeypatch.setattr(artifacts, "EXPANDED_BYTES", 1)
    with pytest.raises(ValueError, match="expanded-byte"):
        artifacts.sdist_members(tarred())
    with pytest.raises(ValueError, match="member type or size"):
        artifacts.wheel_members(zipped(wheel_files()))
