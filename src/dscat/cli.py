# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Command-line interface for Dataset Catalog."""

from pathlib import Path  # noqa: TC003 -- Typer resolves command signatures at runtime.
from typing import Annotated

import typer

from dscat import __version__
from dscat.configuration import MAX_CONFIG_BYTES, parse_configuration
from dscat.intake.discovery import DiscoveryRequest, reject_links
from dscat.intake.limits import IntakeError, diagnostic_exit, dominant_exit, fail
from dscat.intake.worker import CoordinatorRequest, WorkerReply, invoke
from dscat.models.configuration import AssessmentConfiguration, ExportConfiguration
from dscat.models.diagnostics import (
    CommandResult,
    Diagnostic,
    ExitCode,
    OperationSummary,
)
from dscat.validation import assess

app = typer.Typer(
    help=(
        "Dataset Catalog. Copyright (c) 2026 Obscurity Labs. "
        "All rights reserved. Proprietary License."
    ),
    add_completion=False,
    rich_markup_mode=None,
    pretty_exceptions_enable=False,
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    *,
    version: Annotated[
        bool, typer.Option("--version", help="Show the package version.", is_eager=True)
    ] = False,
    no_color: Annotated[
        bool, typer.Option("--no-color", help="Disable colored output.")
    ] = False,
) -> None:
    """Show help or version without reading catalog data."""
    if no_color:
        ctx.color = False
    if version:
        typer.echo(f"dscat {__version__}")
        raise typer.Exit
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


def validation_exit(diagnostics: list[Diagnostic]) -> ExitCode:
    """Apply fixed failure precedence without inspecting arbitrary message text."""
    result: ExitCode = 0
    for diagnostic in diagnostics:
        result = dominant_exit(result, diagnostic_exit(diagnostic))
    return result


def load_explicit_configuration(path: Path | None) -> ExportConfiguration:
    """Read only the explicitly selected bounded configuration before discovery."""
    if path is None:
        return ExportConfiguration(schema_version="1.0")
    reject_links(path)
    with path.open("rb") as stream:
        raw = stream.read(MAX_CONFIG_BYTES + 1)
    try:
        return parse_configuration(raw)
    except ValueError:
        raise fail(code="INVALID_CONFIGURATION") from None


def validation_result(reply: WorkerReply) -> CommandResult:
    """Project private worker facts to the versioned value-free diagnostic result."""
    diagnostics = list(reply.diagnostics)
    for outcome in reply.outcomes:
        diagnostics.extend(outcome.diagnostics)
    exit_code = dominant_exit(reply.failure_exit, validation_exit(diagnostics))
    if reply.has_errors and exit_code == 0:
        exit_code = 1
    assessment = reply.assessment or assess(None, AssessmentConfiguration())
    return CommandResult(
        schema_version="1.0",
        command="validate",
        diagnostics=diagnostics,
        summary=OperationSummary(
            examined_sources=sum(
                outcome.archive_state != "unexamined" for outcome in reply.outcomes
            ),
            unexamined_sources=reply.unexamined_sources,
            valid_records=len(reply.catalog.datasets)
            if reply.catalog is not None
            else 0,
        ),
        assessment=assessment,
        exit_code=exit_code,
    )


def render_validation(result: CommandResult, output_format: str) -> None:
    """Render only fixed messages and known ordinal coordinates, never private facts."""
    if output_format == "json":
        typer.echo(result.model_dump_json(exclude_none=True))
        return
    if result.assessment is not None:
        typer.echo(f"Intake validity: {result.assessment.validity}")
    for diagnostic in result.diagnostics:
        location = ""
        if diagnostic.source_token is not None:
            location += f" source {diagnostic.source_token}"
        if diagnostic.sheet is not None:
            location += f" {diagnostic.sheet}"
        if diagnostic.row is not None:
            location += f" row {diagnostic.row}"
        if diagnostic.column is not None:
            location += f" column {diagnostic.column}"
        actions = {
            "correct_metadata": (
                "Correct the metadata or restore the supported template layout."
            ),
            "check_configuration": "Check the configuration and command options.",
            "retry_operation": "Resolve the environment or I/O failure, then retry.",
            "review_readiness": "Supply the facts required by the selected target.",
            "review_scope": "Review incomplete checks and the selected input scope.",
        }
        expected_actions = {
            "dataset_reference": (
                "Use a dataset ID declared in this workbook; "
                "complete all inputs before checking catalog links."
            ),
            "core": (
                "Complete id, title, description and the contact/owner "
                "label using the supported types."
            ),
            "identifier": (
                "Use 1-128 case-sensitive ASCII ID characters, starting "
                "with a letter or digit."
            ),
            "text": "Supply nonempty text in this field.",
            "date": "Use a valid Gregorian YYYY-MM-DD date.",
            "email": "Supply a syntactically valid role email address.",
            "https_reference": (
                "Supply an absolute HTTPS reference without credentials."
            ),
            "reference": (
                "Supply an absolute HTTPS or URN reference without credentials."
            ),
            "core_role": "Choose contact or owner, or leave the optional role blank.",
            "nullable": "Choose Yes or No, or leave the optional nullable value blank.",
            "detail_property": (
                "Choose a supported section/property and its permitted "
                "unit/reference cells."
            ),
            "detail_group": (
                "Complete the supported properties of this detail "
                "group; avoid repeated or conflicting facts."
            ),
            "quantity": (
                "Use nonnegative decimal text and a supported byte "
                "unit; normalized bytes must be integral."
            ),
            "days": (
                "Use whole days from zero through 2147483647, unknown "
                "or indefinite as applicable."
            ),
            "capacity": (
                "Use a supported kind/state, decimal value, byte unit, "
                "basis, date and applicable rate window."
            ),
            "role_reference": (
                "Supply a complete explicit role group and reference "
                "its matching entry_id for this dataset."
            ),
            "service_reference": (
                "Supply valid service IDs and explicit local/external "
                "references using one link form."
            ),
            "workbook_schema": (
                "Restore the supported worksheet headers and visible "
                "schema/kind markers."
            ),
        }
        action = (
            expected_actions[diagnostic.expected]
            if diagnostic.expected is not None
            else actions[diagnostic.message_key]
        )
        typer.echo(f"{diagnostic.severity}: {diagnostic.code}{location}. {action}")


def check_output_format(value: str) -> None:
    """Reject unsupported formats without echoing the supplied option value."""
    if value not in {"text", "json"}:
        raise fail(code="INVALID_INVOCATION")


@app.command("validate")
def validate_command(
    source: Annotated[Path, typer.Argument(help="Workbook or directory to validate.")],
    *,
    recursive: Annotated[
        bool, typer.Option("--recursive", help="Include nested directories.")
    ] = False,
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Explicit versioned TOML configuration."),
    ] = None,
    output_format: Annotated[
        str, typer.Option("--format", help="Result format: text or json.")
    ] = "text",
) -> None:
    """Validate intake without publishing catalog or export artifacts."""
    try:
        check_output_format(output_format)
        configuration = load_explicit_configuration(config)
        reply = invoke(
            CoordinatorRequest(
                schema_version="1.0",
                role="coordinator",
                discovery=DiscoveryRequest(input=source, recursive=recursive),
                assessment=configuration.assessment,
            ),
            300.0,
        )
        result = validation_result(reply)
    except IntakeError as error:
        result = CommandResult(
            schema_version="1.0",
            command="validate",
            diagnostics=[error.diagnostic],
            summary=OperationSummary(),
            exit_code=validation_exit([error.diagnostic]),
            assessment=assess(None, AssessmentConfiguration()),
        )
    except OSError:
        diagnostic = fail(code="IO_FAILURE").diagnostic
        result = CommandResult(
            schema_version="1.0",
            command="validate",
            diagnostics=[diagnostic],
            summary=OperationSummary(),
            exit_code=3,
            assessment=assess(None, AssessmentConfiguration()),
        )
    except KeyboardInterrupt:
        diagnostic = fail(code="INTERRUPTED").diagnostic
        result = CommandResult(
            schema_version="1.0",
            command="validate",
            diagnostics=[diagnostic],
            summary=OperationSummary(),
            exit_code=130,
            assessment=assess(None, AssessmentConfiguration()),
        )
    except Exception:  # noqa: BLE001 -- privacy-safe boundary for CLI operational failures.
        diagnostic = fail(code="INTERNAL_FAILURE").diagnostic
        result = CommandResult(
            schema_version="1.0",
            command="validate",
            diagnostics=[diagnostic],
            summary=OperationSummary(),
            exit_code=4,
            assessment=assess(None, AssessmentConfiguration()),
        )
    render_validation(result, output_format)
    raise typer.Exit(result.exit_code)
