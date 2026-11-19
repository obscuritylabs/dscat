# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Canonical conversion fences and actual invocation accumulation ceilings."""

import json
from typing import TYPE_CHECKING

import pytest

import dscat.intake.worker as workers
from dscat.cli import validation_result
from dscat.intake.discovery import DiscoveryRequest
from dscat.intake.limits import ArchiveStatistics, DiagnosticCollector, IntakeError
from dscat.intake.normalize import (
    LocatedRecord,
    RecordBuilder,
    group_properties,
    merge_facts,
    property_conversion,
)
from dscat.models.catalog import DatasetRecord
from dscat.models.intake import DatasetRow, DetailRow, SourceLocation

if TYPE_CHECKING:
    from pathlib import Path


def record_with_description(text: str) -> LocatedRecord:
    """Create an explicit valid canonical candidate outside any source pathname."""
    record = DatasetRecord.model_validate(
        {
            "id": "asset-001",
            "title": "Synthetic",
            "description": text,
            "core_party": {"label": "Metadata support"},
        }
    )
    return LocatedRecord(
        record=record, location=SourceLocation(source_token=1, sheet="Datasets", row=2)
    )


def test_actual_dataset_candidate_count_is_inclusive() -> None:
    """The real100,000 candidate ceiling is applied before duplicate comparison."""
    maximum = 100000
    item = record_with_description("Synthetic metadata")
    retained = workers.CandidateRecords()
    collector = DiagnosticCollector()
    assert retained.retain([item] * maximum, collector)
    assert len(retained.records) == maximum
    assert not retained.retain([item], collector)
    assert len(retained.records) == maximum
    assert collector.items[0].limit == "datasets"


def test_actual_canonical_candidate_bytes_are_inclusive() -> None:
    """Exactly256MiB of deterministic canonical records fits; the next does not."""
    unit = 32768
    baseline = record_with_description("x")
    encoded = (
        json.dumps(
            baseline.record.model_dump(mode="json", exclude_none=True),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ).encode()
        + b"\n"
    )
    item = record_with_description("x" * (unit - len(encoded) + 1))
    maximum = 256 * 1024**2
    retained = workers.CandidateRecords()
    collector = DiagnosticCollector()
    assert retained.retain([item] * (maximum // unit), collector)
    assert retained.serialized_bytes == maximum
    assert not retained.retain([baseline], collector)
    assert retained.serialized_bytes == maximum
    assert collector.items[0].limit == "snapshot"


def test_accumulation_failure_stops_remaining_sources_without_double_counting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fully inspected source and later unexamined sources are counted separately."""
    for name in ("a.xlsx", "b.xlsx", "c.xlsx"):
        (tmp_path / name).touch()
    requested: list[int] = []

    def execute(
        request: workers.CoordinatorRequest | workers.ArchiveRequest, _timeout: float
    ) -> workers.WorkerReply:
        assert isinstance(request, workers.ArchiveRequest)
        requested.append(request.source.source_token)
        outcome = workers.ArchiveOutcome(
            source_token=request.source.source_token,
            archive_state="safe",
            statistics=ArchiveStatistics(),
            records=[record_with_description("Synthetic")],
        )
        return workers.WorkerReply(
            schema_version="1.0",
            role="archive",
            outcomes=[outcome],
            has_errors=False,
            selection_complete=True,
        )

    monkeypatch.setattr(workers, "invoke", execute)
    monkeypatch.setattr(
        workers,
        "DEFAULT_LIMITS",
        workers.DEFAULT_LIMITS.model_copy(update={"datasets": 0}),
    )
    reply = workers.inspect_selection(
        workers.CoordinatorRequest(
            schema_version="1.0",
            role="coordinator",
            discovery=DiscoveryRequest(input=tmp_path),
        )
    )
    result = validation_result(reply)
    assert requested == [1]
    assert result.summary.examined_sources == 1
    assert result.summary.unexamined_sources == len(["b", "c"])
    assert reply.catalog is None
    assert reply.diagnostics[0].limit == "datasets"


def test_auxiliary_properties_merge_only_when_consistent() -> None:
    """Supplied unit and reference facts cannot overwrite conflicting values."""
    location = SourceLocation(source_token=1, sheet="Details_Quality", row=2)
    value = DetailRow(
        location=location,
        dataset_id="asset-001",
        section="commitment",
        entry_id="assertion",
        property="value",
        value="10",
        unit="percent",
        reference="urn:example:assertion",
    )
    unit = DetailRow(
        location=location,
        dataset_id="asset-001",
        section="commitment",
        entry_id="assertion",
        property="unit",
        value="percent",
    )
    expected = {"value": "10", "unit": "percent", "reference": "urn:example:assertion"}
    assert group_properties([value, unit]) == expected
    with pytest.raises(IntakeError):
        group_properties([value, unit.model_copy(update={"value": "other"})])
    with pytest.raises(IntakeError):
        group_properties([value, value])
    with pytest.raises(IntakeError):
        merge_facts({"state": "unknown"}, {"state": "approved"})
    assert property_conversion("records", {"duration_days": 0}) == {"duration_days": 0}


def test_internal_unknown_section_and_invalid_scalar_are_rejected() -> None:
    """Future adapter mistakes cannot silently omit an unsupported group."""
    builder = RecordBuilder(
        DatasetRow(
            location=SourceLocation(source_token=1, sheet="Datasets", row=2),
            id="asset-001",
            title="Synthetic",
            description="Synthetic",
            core_party="Metadata support",
        ),
        [],
    )
    with pytest.raises(IntakeError):
        builder.add_complex("unknown", "entry", {})
    with pytest.raises(IntakeError):
        builder.add_descriptive("consumer", {"intended_use": False})
