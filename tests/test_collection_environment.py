# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Collection refuses mismatched tools and reconciles clean installed metadata."""

import hashlib
import json
from pathlib import Path

import pytest
from scripts import candidate_collection as collection
from scripts.processes import Execution
from scripts.provenance import PinnedWheel

from tests.test_collection_boundaries import context
from tests.test_dependency_graph import LOCK, inventory


@pytest.mark.parametrize("mismatch", ["none", "python", "uv", "dependency"])
def test_tool_pins_are_observed_not_assumed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mismatch: str
) -> None:
    """Each tool's observed version must match its explicit project pin."""
    candidate = context(tmp_path)
    (candidate.project / "pyproject.toml").write_text(
        '[dependency-groups]\ndev=["synthetic-tool==1"]\n'
    )
    monkeypatch.setattr(
        collection.platform,
        "python_version",
        lambda: "3.14.0" if mismatch == "python" else collection.PYTHON_VERSION,
    )
    monkeypatch.setattr(
        collection.importlib.metadata,
        "version",
        lambda _name: "2" if mismatch == "dependency" else "1",
    )

    def run(argv: list[str], **options: object) -> Execution:
        del argv
        label = str(options["label"])
        version = "0.0.0" if mismatch == "uv" else collection.UV_VERSION
        (candidate.work / "logs/uv-version.stdout").write_text(f"uv {version}\n")
        return Execution(label, 0, "a" * 64, "b" * 64, 0.1)

    monkeypatch.setattr(collection, "run_tool", run)
    if mismatch == "none":
        assert collection.check_tools(candidate) == {
            "python": collection.PYTHON_VERSION,
            "uv": collection.UV_VERSION,
            "synthetic-tool": "1",
        }
    else:
        with pytest.raises(ValueError, match=r"unavailable|tool pins"):
            collection.check_tools(candidate)


def test_source_snapshot_includes_only_tracked_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Untracked private material cannot enter an archive identity snapshot."""
    candidate = context(tmp_path)
    (candidate.project / "tracked").write_bytes(b"synthetic tracked")
    (candidate.project / "untracked").write_bytes(b"synthetic private")

    def run(argv: list[str], **options: object) -> Execution:
        del argv
        label = str(options["label"])
        (candidate.work / "logs/source-files.stdout").write_bytes(b"tracked\0")
        return Execution(label, 0, "a" * 64, "b" * 64, 0.1)

    monkeypatch.setattr(collection, "run_tool", run)
    assert collection.source_snapshot(candidate) == {"tracked": b"synthetic tracked"}


def test_requirement_exports_retain_hashes_without_source_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Public requirement assets preserve exact exported pins and hide local paths."""
    candidate = context(tmp_path)
    raw = b"synthetic==1 --hash=sha256:" + b"a" * 64 + b"\n"

    def run(argv: list[str], **options: object) -> Execution:
        label = str(options["label"])
        assert "--frozen" in argv
        assert {"--no-header", "--no-annotate", "--no-emit-project"} <= set(argv)
        Path(argv[argv.index("--output-file") + 1]).write_bytes(raw)
        return Execution(label, 0, "a" * 64, "b" * 64, 0.1)

    monkeypatch.setattr(collection, "run_tool", run)
    exports = collection.export_requirements(candidate)
    for scope, private in exports.items():
        assert private.read_bytes() == raw
        assert (candidate.assets / f"{scope}-requirements.txt").read_bytes() == raw


@pytest.mark.parametrize("missing", [True, False])
def test_installed_runtime_metadata_cannot_drop_locked_components(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, missing: bool
) -> None:
    """Actual installed inventory must match the selected runtime and archive pins."""
    candidate = context(tmp_path)
    observed = inventory()
    monkeypatch.setattr(
        collection, "observe", lambda: observed.model_dump(exclude_none=True)
    )
    contents = b"synthetic selected archive"
    pins = {
        name: PinnedWheel(
            package=name,
            version="1",
            filename=f"{name}-1-py3-none-any.whl",
            url=f"https://files.pythonhosted.org/packages/synthetic/{name}-1-py3-none-any.whl",
            sha256=hashlib.sha256(contents).hexdigest(),
            size=len(contents),
        )
        for name in ["foo", "baz"]
    }

    def select(*_args: object) -> dict[str, PinnedWheel]:
        return pins

    monkeypatch.setattr(collection, "selected_wheels", select)

    def download(pin: PinnedWheel, destination: Path) -> Path:
        path = destination / pin.filename
        path.write_bytes(contents)
        return path

    monkeypatch.setattr(collection, "download_wheel", download)
    calls: list[str] = []

    def run(argv: list[str], **options: object) -> Execution:
        label = str(options["label"])
        calls.append(label)
        if label in {"runtime-install", "application-install"}:
            assert {"--no-index", "--require-hashes", "--no-deps"} <= set(argv)
        if label == "runtime-inventory":
            actual = observed.model_dump(exclude_none=True)
            if missing:
                actual["distributions"].pop()
            (candidate.work / "logs/runtime-inventory.stdout").write_text(
                json.dumps(actual)
            )
        return Execution(label, 0, "a" * 64, "b" * 64, 0.1)

    monkeypatch.setattr(collection, "run_tool", run)
    requirements = candidate.work / "requirements.txt"
    requirements.write_text("synthetic pins")
    wheel = collection.Artifact(name="dscat-0.1.0-py3-none-any.whl", sha256="c" * 64)
    if missing:
        with pytest.raises(ValueError, match="do not match the selected lock"):
            collection.install_runtime(candidate, wheel, LOCK, requirements)
    else:
        _, actual = collection.install_runtime(candidate, wheel, LOCK, requirements)
        for package in actual.distributions:
            if package.name != "dscat":
                assert package.artifact_sha256 == pins[package.name].sha256
                assert package.artifact_url == pins[package.name].url
        assert calls == [
            "runtime-venv",
            "runtime-install",
            "application-install",
            "runtime-inventory",
        ]
