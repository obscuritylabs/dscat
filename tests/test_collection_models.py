# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Check independent registration facts and strict persisted schema versions."""

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from dscat.models.catalog import Catalog, DatasetRecord
from dscat.models.collection import (
    CollectionGeneration,
    CollectionIntake,
    RegistrationKnownAmount,
    RegistrationRetention,
    collection_id,
    decimal_text,
)
from dscat.storage.flatfiles import load_snapshot, save_snapshot
from tests.test_dcat_us_3 import catalog

if TYPE_CHECKING:
    from pathlib import Path


def intake() -> CollectionIntake:
    """Create a minimum synthetic entry with explicit unknown ownership."""
    return CollectionIntake.model_validate(
        {
            "owner_state": "unknown",
            "sensitivity": dict.fromkeys(
                ["pii", "phi", "cui", "pcii", "isvi", "other"], "unknown"
            ),
            "submitted_by": "Example Contributor",
            "completed_on": "2026-01-15",
        }
    )


def registered() -> Catalog:
    """Build registration without a description, contact or measurement context."""
    return Catalog(
        schema_version="1.1",
        datasets=[
            DatasetRecord(
                id=collection_id("Example collection"),
                title="Example collection",
                collection_intake=intake(),
            )
        ],
    )


def test_collection_identity_and_absent_facts() -> None:
    """Base identity on normalized name, preserving meaningful case and spacing."""
    assert collection_id(" Example collection ") == collection_id("Example collection")
    assert collection_id("Example collection") != collection_id("example collection")
    data = registered().model_dump(exclude_none=True)
    assert "description" not in data["datasets"][0]
    assert "core_party" not in data["datasets"][0]
    assert "capacity" not in data["datasets"][0]
    assert CollectionGeneration().typical_runs is None


@pytest.mark.parametrize("value", ["-1", "NaN", "1e3", "1.0000000001", "9" * 29])
def test_registration_decimal_bounds(value: str) -> None:
    """Reject malformed, negative, scientific and excessive precision values."""
    with pytest.raises(ValueError, match=r"decimal|Decimal"):
        decimal_text(value)


def test_registration_decimal_and_exact_bytes() -> None:
    """Preserve known zero, normalize spelling and reject mismatched byte counts."""
    assert decimal_text("000.000") == "0"
    assert decimal_text("001.2500") == "1.25"
    row = RegistrationKnownAmount(
        state="known",
        value="001.250",
        unit="KB",
        basis="estimate",
        normalized_bytes=1250,
    )
    assert row.value == "1.25"
    with pytest.raises(ValidationError):
        RegistrationKnownAmount(
            state="known", value="1", unit="GB", basis="measured", normalized_bytes=1
        )


@pytest.mark.parametrize(
    "changes", [{"owner_state": "known"}, {"owner_state": "unknown", "party": True}]
)
def test_owner_consistency(changes: dict[str, object]) -> None:
    """Do not invent owner labels or reinterpret submitter identity."""
    values = intake().model_dump(exclude_none=True) | {
        "owner_state": changes["owner_state"]
    }
    record = {"id": "example", "title": "Example", "collection_intake": values}
    if changes.get("party"):
        record["core_party"] = {"label": "Example team", "role": "owner"}
    with pytest.raises(ValidationError):
        DatasetRecord.model_validate(record)


def test_other_sensitivity_requires_explanation_and_known_owner() -> None:
    """Require conditional text while keeping independent overlapping categories."""
    values = intake().model_dump(exclude_none=True)
    values["sensitivity"]["other"] = "yes"
    with pytest.raises(ValidationError):
        CollectionIntake.model_validate(values)
    values |= {"other_explanation": "Example restricted notes", "owner_state": "known"}
    record = DatasetRecord.model_validate(
        {
            "id": "example",
            "title": "Example",
            "collection_intake": values,
            "core_party": {"label": "Example team", "role": "owner"},
        }
    )
    assert record.core_party is not None


def test_retention_and_frequency_constraints() -> None:
    """Keep durations, unknown state and frequency periods independent."""
    assert RegistrationRetention(days=0).days == 0
    assert RegistrationRetention(status="not_yet_determined").days is None
    with pytest.raises(ValidationError):
        RegistrationRetention(status="confirmed")
    assert RegistrationRetention(status="confirmed", days=0).days == 0
    with pytest.raises(ValidationError):
        CollectionGeneration(typical_runs="1", period="On demand")
    assert (
        CollectionGeneration(typical_runs="001.50", period="week").typical_runs == "1.5"
    )


@pytest.mark.parametrize("version", ["1.0", "1.1"])
def test_version_preserving_snapshot_roundtrip(tmp_path: Path, version: str) -> None:
    """Retain old exact facts and new incomplete answers without rewriting sources."""
    source = catalog() if version == "1.0" else registered()
    root = tmp_path / "catalog"
    first = save_snapshot(root, source)
    current = (root / "CURRENT").read_bytes()
    loaded = load_snapshot(root)
    assert loaded.catalog == source
    assert loaded.manifest.schema_version == version
    assert all(e.schema_version == version for e in loaded.manifest.datasets)
    assert (root / "CURRENT").read_bytes() == current
    assert (
        save_snapshot(root, loaded.catalog, replace=True).generation == first.generation
    )


def test_old_schema_rejects_new_or_missing_core() -> None:
    """Do not accept new vocabulary or loosen old persisted core constraints."""
    with pytest.raises(ValidationError):
        Catalog(schema_version="1.0", datasets=registered().datasets)
    with pytest.raises(ValidationError):
        Catalog(
            schema_version="1.0",
            datasets=[DatasetRecord(id="example", title="Example")],
        )
