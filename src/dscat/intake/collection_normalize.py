# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Convert registration answers without creating contacts, measurements or edges."""

from typing import TYPE_CHECKING

from pydantic import ValidationError

from dscat.intake.limits import DiagnosticCollector, IntakeError
from dscat.intake.normalize import (
    LocatedRecord,
    NormalizedBatch,
    integer_days,
    located_error,
)
from dscat.models.catalog import DatasetRecord
from dscat.models.collection import (
    CollectionGeneration,
    CollectionIntake,
    RegistrationRetention,
    collection_id,
)
from dscat.normalization import normalize_quantity, normalize_text

if TYPE_CHECKING:
    from dscat.models.intake import CollectionRow, IntakeBatch


def amount(
    value: str | None, unit: str | None, basis: str | None
) -> dict[str, object] | None:
    """Keep omitted, unknown and known registration quantities distinct."""
    if value is None and unit is None and basis is None:
        return None
    if basis == "Unknown" and value is None and unit is None:
        return {"state": "unknown"}
    if value is None or unit is None or basis not in {"Estimate", "Measured"}:
        msg = "Supply a known quantity/unit/basis, or Unknown with no amount/unit."
        raise ValueError(msg)
    return {
        "state": "known",
        "value": value,
        "unit": unit,
        "basis": basis.lower(),
        "normalized_bytes": normalize_quantity(value, "kB" if unit == "KB" else unit),
    }


def optional_groups(
    row: CollectionRow, collector: DiagnosticCollector
) -> dict[str, object]:
    """Accumulate independent amount, frequency and retention failures."""
    result: dict[str, object] = {}
    for prefix, column in [("current", 14), ("per_run", 25)]:
        try:
            value = amount(
                getattr(row, prefix + "_value"),
                getattr(row, prefix + "_unit"),
                getattr(row, prefix + "_basis"),
            )
            if value is not None:
                result[prefix + "_amount"] = value
        except ValueError:
            collector.add(
                located_error(
                    row.location.model_copy(update={"column": column}),
                    expected="quantity",
                )
            )
    retention: dict[str, object] = {}
    try:
        if row.retention_days is not None:
            retention["days"] = integer_days(row.retention_days)
        if row.retention_status is not None:
            retention["status"] = {
                "Not yet determined": "not_yet_determined",
                "Proposed": "proposed",
                "Confirmed": "confirmed",
            }[row.retention_status]
        if retention:
            result["retention"] = RegistrationRetention.model_validate(retention)
    except ValueError, IntakeError:
        collector.add(
            located_error(
                row.location.model_copy(update={"column": 20}), expected="days"
            )
        )
    try:
        generation = generation_values(row)
        if generation is not None:
            result["generation"] = generation
    except ValidationError:
        collector.add(
            located_error(
                row.location.model_copy(update={"column": 28}), expected="quantity"
            )
        )
    return result


def generation_values(row: CollectionRow) -> CollectionGeneration | None:
    """Normalize optional process descriptions and descriptive source names."""
    generation: dict[str, object] = {
        k: v
        for k, v in {
            "process": row.process,
            "explanation": row.explanation,
            "typical_runs": row.typical_runs,
            "period": row.period,
        }.items()
        if v is not None
    }
    if row.source_names is not None:
        names = sorted(
            {
                normalize_text(name)
                for name in row.source_names.split(";")
                if normalize_text(name)
            }
        )
        if names:
            generation["source_names"] = names
    return CollectionGeneration.model_validate(generation) if generation else None


def collection_record(
    row: CollectionRow, collector: DiagnosticCollector
) -> LocatedRecord | None:
    """Preserve raw response meanings while deriving only declared identity/bytes."""
    before = len(collector.items)
    answers: dict[str, object] = {
        "owner_state": "unknown" if row.owner.casefold() == "unknown" else "known",
        "sensitivity": {
            name: getattr(row, name).lower()
            for name in ["pii", "phi", "cui", "pcii", "isvi", "other"]
        },
        "submitted_by": row.submitted_by,
        "completed_on": row.completed_on,
    }
    answers.update(
        {
            k: v
            for k, v in {
                "location": row.location_label,
                "consumers": row.consumers,
                "use": row.use,
                "access_pattern": row.access_pattern,
                "other_explanation": row.other_explanation,
            }.items()
            if v is not None
        }
    )
    answers.update(optional_groups(row, collector))
    values: dict[str, object] = {"id": collection_id(row.name), "title": row.name}
    if row.description is not None:
        values["description"] = row.description
    if answers["owner_state"] == "known":
        values["core_party"] = {"label": row.owner, "role": "owner"}
    try:
        values["collection_intake"] = CollectionIntake.model_validate(answers)
        record = DatasetRecord.model_validate(values)
    except ValidationError as error:
        for item in error.errors(include_input=False, include_context=False):
            field = item["loc"][0] if item["loc"] else ""
            column = {"": 11, "access_pattern": 19, "per_run_amount": 25}.get(
                str(field), 14
            )
            collector.add(
                located_error(
                    row.location.model_copy(update={"column": column}), expected="text"
                )
            )
        return None
    return (
        LocatedRecord(record=record, location=row.location)
        if len(collector.items) == before
        else None
    )


def normalize_collections(batch: IntakeBatch) -> NormalizedBatch:
    """Normalize all readable rows without trusting spreadsheet controls."""
    collector = DiagnosticCollector()
    for item in batch.diagnostics:
        collector.add(item)
    collector.has_errors |= batch.has_errors
    records = []
    for row in batch.collections:
        record = collection_record(row, collector)
        if record is not None:
            records.append(record)
    return NormalizedBatch(
        records=records, diagnostics=collector.items, has_errors=collector.has_errors
    )
