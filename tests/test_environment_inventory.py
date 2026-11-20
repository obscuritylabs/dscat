# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Installed metadata evidence preserves unknown licenses and actual target context."""

import importlib.metadata
import json
import runpy
from types import SimpleNamespace
from typing import TYPE_CHECKING, NamedTuple

import pytest
from scripts import environment_inventory

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


class ImplementationVersion(NamedTuple):
    """Supply the fields of an explicitly observed prerelease interpreter."""

    major: int
    minor: int
    micro: int
    releaselevel: str
    serial: int


def test_prerelease_marker_retains_observed_implementation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A prerelease implementation must not be silently reported as a final version."""
    monkeypatch.setattr(
        environment_inventory,
        "sys",
        SimpleNamespace(
            implementation=SimpleNamespace(
                name="cpython",
                version=ImplementationVersion(3, 15, 0, "candidate", 2),
            ),
            platform="synthetic-platform",
        ),
    )
    observed = environment_inventory.marker_environment()
    assert observed["implementation_version"] == "3.15.0c2"
    assert observed["sys_platform"] == "synthetic-platform"


def test_metadata_license_precedence_unknowns_and_no_imports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Read distribution metadata without importing packages or inventing licenses."""
    for name, headers in {
        "z-expression": "License-Expression: MIT\nLicense: ignored legacy\n",
        "b-legacy": "License: Apache-2.0\n",
        "c-classifier": (
            "License: UNKNOWN\nClassifier: License :: OSI Approved :: MIT License\n"
            "Classifier: Programming Language :: Python\n"
        ),
        "a-unknown": "License: \n",
    }.items():
        metadata = tmp_path / f"{name}.dist-info"
        metadata.mkdir()
        (metadata / "METADATA").write_text(
            f"Metadata-Version: 2.4\nName: {name}\nVersion: 1.0\n{headers}"
        )
    installed = list(importlib.metadata.Distribution.discover(path=[str(tmp_path)]))

    def distributions() -> Iterator[importlib.metadata.Distribution]:
        return iter(installed)

    monkeypatch.setattr(
        environment_inventory.importlib.metadata, "distributions", distributions
    )
    runpy.run_path(environment_inventory.__file__, run_name="__main__")
    output = capsys.readouterr()
    assert not output.err
    observed = json.loads(output.out)
    packages = observed["distributions"]
    assert [package["name"] for package in packages] == [
        "a-unknown",
        "b-legacy",
        "c-classifier",
        "z-expression",
    ]
    assert [package["licenses"] for package in packages] == [
        [],
        ["Apache-2.0"],
        ["License :: OSI Approved :: MIT License"],
        ["MIT"],
    ]
    assert all(package["requires"] == [] for package in packages)
    assert str(tmp_path) not in output.out


@pytest.mark.parametrize(
    "identity",
    ["Name: synthetic\n", "Version: 1.0\n", "Name: \nVersion: 1.0\n"],
)
def test_incomplete_identity_refuses_before_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, identity: str
) -> None:
    """Broken installed metadata cannot silently disappear from advisory coverage."""
    directory = tmp_path / "synthetic.dist-info"
    directory.mkdir()
    (directory / "METADATA").write_text(f"Metadata-Version: 2.4\n{identity}")
    installed = list(importlib.metadata.Distribution.discover(path=[str(tmp_path)]))

    def distributions() -> Iterator[importlib.metadata.Distribution]:
        return iter(installed)

    monkeypatch.setattr(
        environment_inventory.importlib.metadata, "distributions", distributions
    )
    with pytest.raises(ValueError, match="identity metadata is incomplete"):
        environment_inventory.observe()
