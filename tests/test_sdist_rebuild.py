# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""An extracted source archive rebuilds without duplicate generated metadata."""

import tarfile
from email.parser import BytesParser
from pathlib import Path

from hatchling.builders.sdist import SdistBuilder
from scripts.artifacts import sdist_members

ROOT = Path(__file__).parents[1]


def test_extracted_sdist_rebuild_preserves_source_and_one_metadata_entry(
    tmp_path: Path,
) -> None:
    """Build backend archives and rebuild their extracted generated metadata."""
    project = tmp_path / "source"
    package = project / "src/dscat"
    package.mkdir(parents=True)
    (project / "pyproject.toml").write_bytes((ROOT / "pyproject.toml").read_bytes())
    (project / "LICENSE").write_bytes((ROOT / "LICENSE").read_bytes())
    (package / "__init__.py").write_text('__version__ = "0.1.0"\n')
    # The exclusion is anchored: a nested ordinary source resource survives.
    nested = package / "resources/PKG-INFO"
    nested.parent.mkdir()
    nested.write_bytes(b"Synthetic ordinary resource.\n")
    first = Path(
        next(SdistBuilder(str(project)).build(directory=str(tmp_path / "first")))
    )
    prefix = "dscat-0.1.0/"
    metadata_name = prefix + "PKG-INFO"
    with tarfile.open(first, "r:gz") as archive:
        assert archive.getnames().count(metadata_name) == 1
    original = sdist_members(first.read_bytes())
    metadata = BytesParser().parsebytes(original[metadata_name])
    assert metadata["Name"] == "dscat"
    assert metadata["Version"] == "0.1.0"
    assert metadata["License-Expression"] == "LicenseRef-Proprietary"
    assert original[prefix + "src/dscat/resources/PKG-INFO"] == nested.read_bytes()

    extracted = tmp_path / "extracted"
    for name, raw in original.items():
        destination = extracted / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    second = Path(
        next(
            SdistBuilder(str(extracted / "dscat-0.1.0")).build(
                directory=str(tmp_path / "second")
            )
        )
    )
    with tarfile.open(second, "r:gz") as archive:
        assert archive.getnames().count(metadata_name) == 1
    assert sdist_members(second.read_bytes()) == original
    assert second.read_bytes() == first.read_bytes()
