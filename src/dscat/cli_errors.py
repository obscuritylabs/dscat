# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Parser failures cannot echo arbitrary submitted command or option strings."""

from typing import TYPE_CHECKING, override

from typer import _click as click
from typer._click.exceptions import UsageError
from typer.core import TyperCommand, TyperGroup

from dscat.intake.limits import fail
from dscat.models.diagnostics import CommandResult, OperationSummary

if TYPE_CHECKING:
    from typing import IO


class SafeUsageError(UsageError):
    """Render one fixed error, using JSON for a recognized command's JSON request."""

    def __init__(self, command: str | None, arguments: list[str]) -> None:
        """Retain only a known command and the presence of a supported format flag."""
        super().__init__("Invalid command invocation.")
        self.command = command if command in {"validate", "build", "export"} else None
        self.json_requested = any(
            argument == "--format=json"
            or (argument == "--format" and arguments[index + 1 : index + 2] == ["json"])
            for index, argument in enumerate(arguments)
        )

    @override
    def show(self, file: IO[str] | None = None) -> None:
        """Exclude usage context, paths and submitted values from parser errors."""
        if self.command is not None and self.json_requested:
            result = CommandResult.model_validate(
                {
                    "schema_version": "1.0",
                    "command": self.command,
                    "diagnostics": [fail(code="INVALID_INVOCATION").diagnostic],
                    "summary": OperationSummary(),
                    "exit_code": 2,
                }
            )
            click.echo(result.model_dump_json(exclude_none=True))
        else:
            click.echo("Invalid command invocation.", file=file, err=True)


class SafeCommand(TyperCommand):
    """Convert parser errors before Click renders submitted tokens."""

    @override
    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        """Preserve recognized JSON intent before the parser consumes arguments."""
        original = list(args)
        try:
            return super().parse_args(ctx, args)
        except UsageError:
            raise SafeUsageError(self.name, original) from None


class SafeGroup(TyperGroup):
    """Keep top-level option and unknown-command errors generic."""

    @override
    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        """Sanitize failures before a known subcommand is selected."""
        try:
            return super().parse_args(ctx, args)
        except UsageError:
            raise SafeUsageError(None, []) from None

    @override
    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        """Never echo an unknown submitted command."""
        try:
            return super().resolve_command(ctx, args)
        except UsageError:
            raise SafeUsageError(None, []) from None
