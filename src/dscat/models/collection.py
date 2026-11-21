# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Typed collection registration facts, distinct from measured capacity."""

import hashlib
import re
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from dscat.models.base import CalendarDate, StrictModel, Text, TextSet
from dscat.normalization import normalize_quantity, normalize_text

RegistrationUnit = Literal["KB", "MB", "GB", "TB", "PB"]
SensitivityState = Literal["yes", "no", "unknown"]
AccessPattern = Literal[
    "Bulk or batch",
    "Interactive search",
    "Record lookup",
    "Streaming",
    "Mixed",
    "Other",
    "Unknown",
]
Period = Literal["day", "week", "month", "year", "On demand", "Unknown"]


def collection_id(name: str) -> str:
    """Derive identity only from the case-sensitive normalized collection name."""
    return (
        "collection-" + hashlib.sha256(normalize_text(name).encode("utf-8")).hexdigest()
    )


def decimal_text(value: str) -> str:
    """Bound plain nonnegative decimals without converting estimates to floats."""
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value) is None:
        msg = "Expected a nonnegative plain decimal."
        raise ValueError(msg)
    whole, _, fraction = value.partition(".")
    if len((whole + fraction).lstrip("0")) > 28 or len(fraction) > 9:  # noqa: PLR2004 -- shared decimal precision bounds.
        msg = "Decimal exceeds supported precision."
        raise ValueError(msg)
    whole = whole.lstrip("0") or "0"
    fraction = fraction.rstrip("0")
    return whole + ("." + fraction if fraction else "")


class RegistrationKnownAmount(StrictModel):
    """A supplied size and reported basis without invented measurement context."""

    state: Literal["known"]
    value: Text
    unit: RegistrationUnit
    basis: Literal["estimate", "measured"]
    normalized_bytes: Annotated[int, Field(ge=0, le=2**63 - 1)]

    @field_validator("value")
    @classmethod
    def canonical_decimal(cls, value: str) -> str:
        """Normalize equivalent decimal spellings for deterministic comparisons."""
        return decimal_text(value)

    @model_validator(mode="after")
    def exact_bytes(self) -> Self:
        """Check normalization while preserving the supplied decimal-only unit."""
        unit = "kB" if self.unit == "KB" else self.unit
        if normalize_quantity(self.value, unit) != self.normalized_bytes:
            msg = "Quantity does not match its normalized bytes."
            raise ValueError(msg)
        return self


class RegistrationUnknownAmount(StrictModel):
    """Explicit uncertainty, without a fabricated unit or zero."""

    state: Literal["unknown"]


RegistrationAmount = Annotated[
    RegistrationKnownAmount | RegistrationUnknownAmount, Field(discriminator="state")
]


class CollectionSensitivity(StrictModel):
    """Independent reported categories, not formal classifications or approvals."""

    pii: SensitivityState
    phi: SensitivityState
    cui: SensitivityState
    pcii: SensitivityState
    isvi: SensitivityState
    other: SensitivityState


class RegistrationRetention(StrictModel):
    """A duration from batch arrival, without disposal authority or enforcement."""

    trigger: Literal["batch_arrival"] = "batch_arrival"
    days: Annotated[int, Field(ge=0, le=2**31 - 1)] | None = None
    status: Literal["not_yet_determined", "proposed", "confirmed"] | None = None

    @model_validator(mode="after")
    def confirmed_duration(self) -> Self:
        """Require a day count for a claimed confirmed duration."""
        if self.status == "confirmed" and self.days is None:
            msg = "Confirmed retention needs a duration."
            raise ValueError(msg)
        return self


class CollectionGeneration(StrictModel):
    """Optional process summary and descriptive source names, not formal edges."""

    process: Text | None = None
    explanation: Text | None = None
    source_names: TextSet | None = None
    typical_runs: Text | None = None
    period: Period | None = None

    @field_validator("typical_runs")
    @classmethod
    def bounded_runs(cls, value: str | None) -> str | None:
        """Canonicalize finite plain-decimal run counts."""
        return None if value is None else decimal_text(value)

    @model_validator(mode="after")
    def frequency(self) -> Self:
        """Require a numeric period for an average count."""
        if self.typical_runs is not None and self.period not in {
            "day",
            "week",
            "month",
            "year",
        }:
            msg = "Run counts need a numeric frequency period."
            raise ValueError(msg)
        return self


class CollectionIntake(StrictModel):
    """Closed preserved answers from a collection-first registration."""

    owner_state: Literal["known", "unknown"]
    sensitivity: CollectionSensitivity
    submitted_by: Text
    completed_on: CalendarDate
    other_explanation: Text | None = None
    location: Text | None = None
    consumers: Text | None = None
    use: Text | None = None
    access_pattern: AccessPattern | None = None
    current_amount: RegistrationAmount | None = None
    per_run_amount: RegistrationAmount | None = None
    retention: RegistrationRetention | None = None
    generation: CollectionGeneration | None = None

    @model_validator(mode="after")
    def explain_other(self) -> Self:
        """Other sensitive data needs a description without underlying records."""
        if self.sensitivity.other == "yes" and self.other_explanation is None:
            msg = "Other sensitive data needs an explanation."
            raise ValueError(msg)
        return self
