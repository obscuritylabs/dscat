# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Shared strict model conventions and constrained scalar types."""

from datetime import date
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    StringConstraints,
    model_validator,
)

from dscat.normalization import (
    normalize_https,
    normalize_identifier,
    normalize_namespace,
    normalize_reference,
    normalize_text,
    parse_date,
)

Text = Annotated[str, BeforeValidator(normalize_text), StringConstraints(min_length=1)]
Identifier = Annotated[str, BeforeValidator(normalize_identifier)]
Reference = Annotated[str, BeforeValidator(normalize_reference)]
HttpsReference = Annotated[str, BeforeValidator(normalize_https)]
Namespace = Annotated[str, BeforeValidator(normalize_namespace)]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Target = Literal["dcat-us-3", "odcs-3.2"]
Audience = Literal["internal", "public"]
CalendarDate = Annotated[date, BeforeValidator(parse_date)]


class StrictModel(BaseModel):
    """Reject coercion, undeclared fields and explicitly supplied nulls."""

    model_config = ConfigDict(
        strict=True, extra="forbid", frozen=True, allow_inf_nan=False
    )

    @model_validator(mode="before")
    @classmethod
    def reject_nulls(cls, value: object) -> object:
        """Allow omitted optional fields without accepting explicit null facts."""
        if isinstance(value, dict) and any(item is None for item in value.values()):
            msg = "Omit absent optional fields instead of supplying null."
            raise ValueError(msg)
        return value


def unique_strings(values: list[str]) -> list[str]:
    """Reject duplicate normalized values and establish deterministic set order."""
    if len(values) != len(set(values)):
        msg = "Duplicate normalized value."
        raise ValueError(msg)
    return sorted(values)


TextSet = Annotated[list[Text], AfterValidator(unique_strings)]
ReferenceSet = Annotated[list[Reference], AfterValidator(unique_strings)]
