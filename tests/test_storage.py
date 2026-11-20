# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Persisted data is revalidated as hostile input, not trusted local state."""

import hashlib
import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from dscat.intake.limits import IntakeError, Limits
from dscat.models.catalog import Catalog, DatasetRecord, PartyReference
from dscat.serialization import canonical_bytes
from dscat.storage import flatfiles
from dscat.storage.flatfiles import (
    generation_hash,
    load_snapshot,
    prepare,
    read_generation,
    save_snapshot,
)
from dscat.storage.models import CanonicalManifest, DatasetEntry, dataset_path

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"


def catalog(*identifiers: str) -> Catalog:
    """Create synthetic facts with separate business identity and private values."""
    return Catalog(
        schema_version="1.0",
        datasets=[
            DatasetRecord(
                id=identifier,
                title="Synthetic private title",
                description="Synthetic description",
                core_party=PartyReference(label="Support"),
            )
            for identifier in identifiers
        ],
    )


def stored(root: Path, value: Catalog) -> tuple[Path, dict[str, bytes]]:
    """Construct canonical test bytes without relying on the publication writer."""
    _manifest, artifacts = prepare(value)
    digest = generation_hash(artifacts)
    generation = root / "generations" / digest
    (generation / "datasets").mkdir(parents=True)
    for relative, raw in artifacts.items():
        (generation / relative).write_bytes(raw)
    (root / "CURRENT").write_bytes((digest + "\n").encode())
    return generation, artifacts


def write_json(path: Path, value: object) -> None:
    """Keep formatting fixed while mutating untrusted serialized test objects."""
    path.write_bytes(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode() + b"\n"
    )


def test_minimum_detailed_empty_roundtrip_without_workbooks(tmp_path: Path) -> None:
    """Both canonical fixtures and an empty catalog load independently of intake."""
    records = [
        DatasetRecord.model_validate_json((FIXTURES / name).read_bytes())
        for name in ("minimum.json", "detailed.json")
    ]
    for index, record in enumerate(records):
        value = Catalog(schema_version="1.0", datasets=[record])
        root = tmp_path / str(index)
        snapshot = save_snapshot(root, value)
        assert load_snapshot(root).catalog == value
        assert snapshot.manifest.datasets[0].path == dataset_path(record.id)
        assert record.id not in snapshot.manifest.datasets[0].path
    empty = save_snapshot(tmp_path / "empty", catalog())
    assert load_snapshot(tmp_path / "empty") == empty


def test_exact_path_manifest_and_set_order_contract() -> None:
    """The closed manifest rejects extra fields, duplicate IDs, paths and versions."""
    manifest, artifacts = prepare(catalog("z", "a"))
    assert [entry.id for entry in manifest.datasets] == ["a", "z"]
    assert next(iter(artifacts)) == dataset_path("a")
    assert dataset_path("a") == "datasets/" + hashlib.sha256(b"a").hexdigest() + ".json"
    entry = manifest.datasets[0].model_dump()
    for path in (
        "../bad",
        "/absolute/data",
        "datasets/a.json",
        "datasets/" + "A" * 64 + ".json",
    ):
        with pytest.raises(ValidationError):
            DatasetEntry.model_validate(entry | {"path": path})
    data = manifest.model_dump()
    for change in (
        {"datasets": [entry, entry]},
        {"datasets": list(reversed(data["datasets"]))},
        {"schema_version": "9.0"},
        {"unknown": 1},
        {"kind": "projection"},
        {"resource_fingerprints": {"target": "a" * 64}},
        {"configuration_fingerprints": {"target": "a" * 64}},
    ):
        with pytest.raises(ValidationError):
            CanonicalManifest.model_validate(data | change)


@pytest.mark.parametrize(
    "pointer",
    [
        b"",
        b"a" * 64,
        b"A" * 64 + b"\n",
        b"../bad\n",
        b"a" * 64 + b"\r",
        b"a" * 64 + b"\n\n",
    ],
)
def test_invalid_pointer_never_selects_generation(
    tmp_path: Path, pointer: bytes
) -> None:
    """Only the exact full lower-case digest plus one LF is accepted."""
    tmp_path.joinpath("CURRENT").write_bytes(pointer)
    with pytest.raises(IntakeError):
        load_snapshot(tmp_path)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "extra",
        "root_extra",
        "hash",
        "id",
        "invalid",
        "noncanonical",
        "generation",
    ],
)
def test_generation_member_and_content_rejection(tmp_path: Path, mutation: str) -> None:
    """Each dataset and the full generation have independent exact-byte checks."""
    generation, _artifacts = stored(tmp_path, catalog("a"))
    data = generation / dataset_path("a")
    if mutation == "missing":
        data.unlink()
    elif mutation == "extra":
        (generation / "datasets" / "extra.json").write_bytes(b"{}")
    elif mutation == "root_extra":
        (generation / "exports").mkdir()
    elif mutation in {"id", "invalid", "hash"}:
        value = json.loads(data.read_bytes())
        key, replacement = {
            "id": ("id", "other"),
            "invalid": ("title", None),
            "hash": ("title", "changed"),
        }[mutation]
        value[key] = replacement
        write_json(data, value)
    elif mutation == "noncanonical":
        data.write_bytes(data.read_bytes().rstrip())
        manifest = json.loads((generation / "manifest.json").read_bytes())
        manifest["datasets"][0]["sha256"] = hashlib.sha256(
            data.read_bytes()
        ).hexdigest()
        write_json(generation / "manifest.json", manifest)
    else:
        new = generation.with_name("b" * 64)
        generation.rename(new)
        (tmp_path / "CURRENT").write_bytes(b"b" * 64 + b"\n")
    with pytest.raises(IntakeError, match="PUBLICATION_FAILURE"):
        load_snapshot(tmp_path)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"schema_version":"1.0","schema_version":"1.0"}',
        b'{"schema_version":NaN}',
        b"\xff",
        b"[]",
        b'{"schema_version":"1.0","kind":"canonical","datasets":null}',
        b"[" * 65 + b"]" * 65,
    ],
)
def test_hostile_manifest_json(tmp_path: Path, raw: bytes) -> None:
    """Duplicate keys, nonfinite numbers, invalid encoding/null and depth fail."""
    generation, _artifacts = stored(tmp_path, catalog())
    (generation / "manifest.json").write_bytes(raw)
    with pytest.raises(IntakeError):
        load_snapshot(tmp_path)


def test_manifest_format_future_version_and_dangling_catalog(tmp_path: Path) -> None:
    """Unknown versions refuse upgrades; formatting cannot alias persisted bytes."""
    generation, artifacts = stored(tmp_path, catalog("a"))
    manifest_path = generation / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["schema_version"] = "9.0"
    write_json(manifest_path, manifest)
    with pytest.raises(IntakeError, match="UNSUPPORTED_VERSION"):
        load_snapshot(tmp_path)
    manifest_path.write_bytes(artifacts["manifest.json"].rstrip())
    with pytest.raises(IntakeError, match="PUBLICATION_FAILURE"):
        load_snapshot(tmp_path)
    # A valid record's local service links become invalid when its referenced dataset
    # is omitted from a manifest. Recompute hashes to exercise semantic validation.
    manifest_path.write_bytes(artifacts["manifest.json"])
    data = json.loads(artifacts[dataset_path("a")])
    data["services"] = [
        {
            "id": "service",
            "served_datasets": [{"id": "missing", "reference_kind": "local"}],
        }
    ]
    write_json(generation / dataset_path("a"), data)
    manifest = json.loads(artifacts["manifest.json"])
    manifest["datasets"][0]["sha256"] = hashlib.sha256(
        (generation / dataset_path("a")).read_bytes()
    ).hexdigest()
    write_json(manifest_path, manifest)
    changed = {name: (generation / name).read_bytes() for name in artifacts}
    with pytest.raises(IntakeError, match="PUBLICATION_FAILURE"):
        read_generation(generation, generation_hash(changed))


@pytest.mark.parametrize(
    "location",
    ["CURRENT", "generations", "generation", "datasets", "dataset", "manifest"],
)
def test_links_are_not_trusted(tmp_path: Path, location: str) -> None:
    """Reject linked ancestors, data, manifests and pointer files."""
    root = tmp_path / "bundle"
    generation, _artifacts = stored(root, catalog("a"))
    selected = {
        "CURRENT": root / "CURRENT",
        "generations": root / "generations",
        "generation": generation,
        "datasets": generation / "datasets",
        "dataset": generation / dataset_path("a"),
        "manifest": generation / "manifest.json",
    }[location]
    real = selected.with_name(selected.name + "-real")
    selected.rename(real)
    selected.symlink_to(real, target_is_directory=real.is_dir())
    with pytest.raises(IntakeError):
        load_snapshot(root)


def test_bounds_orphans_and_current_read_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A single pointer resolution cannot mix with a concurrent valid switch."""
    root = tmp_path / "bundle"
    first = save_snapshot(root, catalog("a"))
    second = save_snapshot(root, catalog("b"), replace=True)
    (root / "CURRENT").write_bytes((first.generation + "\n").encode())
    (root / ".stage-abandoned").mkdir()
    original = flatfiles.read_file
    pointers: list[Path] = []

    def switching(path: Path, maximum: int) -> bytes:
        raw = original(path, maximum)
        if path.name == "CURRENT":
            pointers.append(path)
            path.write_bytes((second.generation + "\n").encode())
        return raw

    monkeypatch.setattr(flatfiles, "read_file", switching)
    loaded = load_snapshot(root)
    assert loaded.catalog == first.catalog
    assert loaded.orphan_count == 1
    assert loaded.retained_generation_count == 1
    assert pointers == [root / "CURRENT"]
    monkeypatch.setattr(flatfiles, "DEFAULT_LIMITS", Limits(datasets=0))
    with pytest.raises(IntakeError, match="INPUT_LIMIT"):
        load_snapshot(root)


def test_snapshot_byte_ceiling_and_mutable_model_revalidation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Serialization and loading include manifest bytes in the total byte budget."""
    generation, artifacts = stored(tmp_path, catalog("a"))
    total = sum(map(len, artifacts.values()))
    monkeypatch.setattr(flatfiles, "DEFAULT_LIMITS", Limits(snapshot=total))
    assert load_snapshot(tmp_path).catalog == catalog("a")
    monkeypatch.setattr(flatfiles, "DEFAULT_LIMITS", Limits(snapshot=total - 1))
    with pytest.raises(IntakeError, match="INPUT_LIMIT"):
        read_generation(generation, generation.name)
    with pytest.raises(IntakeError, match="INPUT_LIMIT"):
        prepare(catalog("a"))
    value = catalog("a")
    value.datasets.append(value.datasets[0])
    with pytest.raises(IntakeError, match="PUBLICATION_FAILURE"):
        save_snapshot(tmp_path / "new", value)
    assert not (tmp_path / "new").exists()


def test_canonical_bytes_are_utf8_lf_and_stable() -> None:
    """Non-ASCII normalized facts and semantic field order survive exact encoding."""
    record = catalog("a").datasets[0].model_copy(update={"title": "Résumé"})
    raw = canonical_bytes(record)
    assert b"R\xc3\xa9sum\xc3\xa9" in raw
    assert raw.endswith(b"\n")
    assert not raw.endswith(b"\n\n")
    assert b"\r" not in raw
    assert canonical_bytes(DatasetRecord.model_validate_json(raw)) == raw
    assert generation_hash({"b": b"2", "a": b"1"}) == generation_hash(
        {"a": b"1", "b": b"2"}
    )
    assert generation_hash({"a": b"12"}) != generation_hash({"a1": b"2"})


def test_unknown_retained_generation_name_is_rejected(tmp_path: Path) -> None:
    """Uncommitted generations cannot introduce arbitrary names into the bundle."""
    stored(tmp_path, catalog())
    (tmp_path / "generations" / "unexpected").mkdir()
    with pytest.raises(IntakeError, match="PUBLICATION_FAILURE"):
        load_snapshot(tmp_path)


@pytest.mark.parametrize("fault", ["device", "growth"])
def test_snapshot_device_and_growth_observations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    """Cross-device files and growth after the early size check are rejected."""
    generation, artifacts = stored(tmp_path, catalog("a"))
    total = sum(map(len, artifacts.values()))
    monkeypatch.setattr(flatfiles, "DEFAULT_LIMITS", Limits(snapshot=total - 1))
    lstat = Path.lstat
    observed = False

    def changed(path: Path) -> os.stat_result:
        nonlocal observed
        attributes = lstat(path)
        if path == generation / dataset_path("a") and not observed:
            observed = True
            values = list(attributes)
            if fault == "device":
                values[2] += 1
            else:
                values[6] = 0
            return os.stat_result(values)
        return attributes

    monkeypatch.setattr(Path, "lstat", changed)
    with pytest.raises(IntakeError):
        read_generation(generation, generation.name)
