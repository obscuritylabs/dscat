# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Private reports are explicitly selected and independent of public artifacts."""

from typing import Literal

from pydantic import Field

from dscat.export.loss import ProjectionLoss
from dscat.models.diagnostics import DiagnosticReport, ValidationAssessment


class PrivateReport(DiagnosticReport):
    """Assessment and omissions without a premature publication success receipt."""

    kind: Literal["private-report"] = "private-report"
    assessment: ValidationAssessment | None = None
    losses: list[ProjectionLoss] = Field(default_factory=list, max_length=10000)
