# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Typed invocation intent; no filesystem operation occurs during validation."""

from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from dscat.models.base import Audience, StrictModel, Target


class CommandRequest(StrictModel):
    """Explicit inputs/options, with command-specific shape constraints."""

    command: Literal["template", "validate", "build", "export"]
    input: Path | None = None
    output: Path | None = None
    config: Path | None = None
    diagnostics: Path | None = None
    recursive: bool = False
    replace: bool = False
    examples: bool = False
    targets: list[Target] = Field(default_factory=list)
    audience: Audience = "internal"
    format: Literal["text", "json"] = "text"

    @model_validator(mode="after")
    def command_shape(self) -> Self:
        """Require applicable paths/options before any data processing."""
        if self.command != "template" and self.examples:
            msg = "Examples are only supported by template generation."
            raise ValueError(msg)
        if self.command != "template" and self.input is None:
            msg = "This command requires an explicit input."
            raise ValueError(msg)
        if self.command != "validate" and self.output is None:
            msg = "This command requires an explicit output."
            raise ValueError(msg)
        if self.command == "template" and (
            self.input is not None
            or self.config is not None
            or self.targets
            or self.recursive
        ):
            msg = "Template generation does not accept intake or export options."
            raise ValueError(msg)
        if self.command == "validate" and (
            self.output is not None or self.targets or self.replace
        ):
            msg = "Validation does not publish or replace output."
            raise ValueError(msg)
        if self.command == "export" and (not self.targets or self.recursive):
            msg = "Export requires a target and does not discover workbooks."
            raise ValueError(msg)
        if self.command != "export" and self.audience != "internal":
            msg = "Public projection requires export from a saved canonical bundle."
            raise ValueError(msg)
        if len(set(self.targets)) != len(self.targets):
            msg = "Duplicate target selection."
            raise ValueError(msg)
        return self
