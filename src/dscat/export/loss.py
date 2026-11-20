# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Value-free omissions identify only a record, known canonical field and target."""

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, field_validator

from dscat.models.base import Identifier, StrictModel, Target
from dscat.models.configuration import canonical_paths

if TYPE_CHECKING:
    from dscat.models.catalog import DatasetRecord

CANONICAL_FIELDS = canonical_paths()


class ProjectionLoss(StrictModel):
    """A stable field location explains an intentional omission without its value."""

    record_id: Identifier
    field: str
    target: Target
    code: Literal["projection_omitted"] = "projection_omitted"
    reason: Literal[
        "unsupported_mapping", "unsupported_cardinality", "unresolved_contact"
    ]

    @field_validator("field")
    @classmethod
    def known_field(cls, value: str) -> str:
        """Never use an arbitrary label or submitted scalar as a field path."""
        if value not in CANONICAL_FIELDS:
            msg = "Projection losses require a known canonical field."
            raise ValueError(msg)
        return value


def supplied_fields(value: object, path: str = "") -> set[str]:
    """Walk typed facts, including false, zero and explicit empty collections."""
    if value is None:
        return set()
    if isinstance(value, BaseModel):
        return {
            field
            for name in type(value).model_fields
            for field in supplied_fields(
                getattr(value, name), f"{path}.{name}" if path else name
            )
        }
    if isinstance(value, list) and value:
        return {field for item in value for field in supplied_fields(item, path)}
    return {path}


def omitted_fields(
    record: DatasetRecord, mapped: frozenset[str], target: Target
) -> list[ProjectionLoss]:
    """Report each supplied unmapped leaf once, independent of private contents."""
    return [
        ProjectionLoss(
            record_id=record.id,
            field=field,
            target=target,
            reason="unsupported_mapping",
        )
        for field in sorted(supplied_fields(record) - mapped)
    ]
