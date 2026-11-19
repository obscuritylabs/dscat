# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Privacy-safe result and assessment boundaries without arbitrary message text."""

from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, field_validator

from dscat.models.base import Identifier, Sha256, StrictModel, Target
from dscat.models.configuration import canonical_paths

CheckState = Literal["conforms", "does_not_conform", "unperformed"]


def require_integer(value: object) -> int:
    """Reject bool/float equality coercion before numeric Literal validation."""
    if type(value) is not int:
        msg = "Expected an integer exit code without coercion."
        raise ValueError(msg)
    return value


ExitCode = Annotated[Literal[0, 1, 2, 3, 4, 130], BeforeValidator(require_integer)]
Code = Literal[
    "INVALID_INVOCATION",
    "INVALID_CONFIGURATION",
    "UNSUPPORTED_VERSION",
    "INPUT_LIMIT",
    "UNREADABLE_INPUT",
    "WORKER_FAILURE",
    "IGNORED_WORKSHEET",
    "UNSAFE_INPUT",
    "INVALID_WORKBOOK",
    "UNSUPPORTED_WORKBOOK_PART",
    "INVALID_METADATA",
    "DUPLICATE_CONFLICT",
    "DUPLICATE_IDENTICAL",
    "UNRESOLVED_REFERENCE",
    "RESOURCE_GUARD_UNAVAILABLE",
    "IO_FAILURE",
    "PUBLICATION_FAILURE",
    "INTERNAL_FAILURE",
    "INTERRUPTED",
    "DIAGNOSTICS_TRUNCATED",
    "UNEXAMINED_INPUT",
    "INCOMPARABLE_CAPACITY",
    "RECORDS_CONFLICT",
    "target_contact_missing",
    "target_contract_identity_missing",
    "target_contract_version_missing",
    "target_fact_conflict",
    "target_unrepresentable",
    "projection_omitted",
    "PUBLIC_PROJECTION_DENIED",
]
Sheet = Literal["Instructions", "Datasets", "Fields", "Details_Quality"]
Limit = Literal[
    "files",
    "compressed",
    "members",
    "expanded",
    "ratio",
    "xml",
    "depth",
    "sheets",
    "cells",
    "text",
    "workbook_time",
    "invocation_time",
    "json_bytes",
    "snapshot",
    "datasets",
    "diagnostics",
    "memory",
]


class Diagnostic(StrictModel):
    """Fixed codes and ordinal locations cannot echo untrusted input values."""

    code: Code
    severity: Literal["info", "warning", "error"]
    message_key: Literal[
        "correct_metadata",
        "check_configuration",
        "retry_operation",
        "review_readiness",
        "review_scope",
    ]
    source_token: Annotated[int, Field(ge=1)] | None = None
    related_source_token: Annotated[int, Field(ge=1)] | None = None
    sheet: Sheet | None = None
    row: Annotated[int, Field(ge=1)] | None = None
    column: Annotated[int, Field(ge=1)] | None = None
    target: Target | None = None
    check_state: CheckState = "does_not_conform"
    limit: Limit | None = None


class TargetReadiness(StrictModel):
    """Target readiness is independent of structural intake validity."""

    target: Target
    state: Literal["ready", "blocked", "unexamined"]
    reasons: list[Code] = Field(default_factory=list)


class CompletenessResult(StrictModel):
    """A schema field's optional presence, without invented factual defaults."""

    path: str
    state: Literal["present", "absent", "unknown"]

    @field_validator("path")
    @classmethod
    def known_path(cls, value: str) -> str:
        """Output locations must be known schema paths, never arbitrary input text."""
        if value not in canonical_paths():
            msg = "Unknown canonical field path."
            raise ValueError(msg)
        return value


class RuleResult(StrictModel):
    """A declared local check's result, never an enforcement claim."""

    rule_id: Identifier
    state: CheckState
    severity: Literal["info", "warning", "error"] = "warning"


class ValidationAssessment(StrictModel):
    """Derived status is kept outside canonical facts and publication authority."""

    validity: Literal["valid", "invalid", "unexamined"]
    completeness: list[CompletenessResult] = Field(default_factory=list)
    targets: list[TargetReadiness] = Field(default_factory=list)
    rules: list[RuleResult] = Field(default_factory=list)


class OperationSummary(StrictModel):
    """Bounded nonnegative counts describe examined and unexamined scope."""

    examined_sources: Annotated[int, Field(ge=0)] = 0
    unexamined_sources: Annotated[int, Field(ge=0)] = 0
    valid_records: Annotated[int, Field(ge=0)] = 0
    invalid_records: Annotated[int, Field(ge=0)] = 0


class OutputReceipt(StrictModel):
    """An output identity without private paths or configuration contents."""

    kind: Literal["canonical", "projection", "template"]
    sha256: Sha256
    targets: list[Target] = Field(default_factory=list)


class DiagnosticReport(StrictModel):
    """A versioned diagnostic list and examined-scope summary."""

    schema_version: Literal["1.0"]
    diagnostics: list[Diagnostic]
    summary: OperationSummary


class CommandResult(DiagnosticReport):
    """Exactly one structured result can be rendered for a command invocation."""

    command: Literal["template", "validate", "build", "export"]
    exit_code: ExitCode
    assessment: ValidationAssessment | None = None
    receipt: OutputReceipt | None = None
