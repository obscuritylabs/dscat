# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Command-line interface for Dataset Catalog."""

import hashlib
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from dscat import __version__
from dscat.cli_errors import SafeCommand, SafeGroup
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
    OutputReceipt,
)
from dscat.models.requests import CommandRequest
from dscat.reporting import PrivateReport
from dscat.serialization import canonical_bytes
from dscat.storage.singlefile import (
    check_disjoint,
    check_file_destination,
    publish_file,
)
from dscat.validation import assess
from dscat.workbook.generate import create_template

app = typer.Typer(
    cls=SafeGroup,
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
    diagnostics.sort(
        key=lambda item: (
            item.source_token or 0,
            item.sheet or "",
            item.row or 0,
            item.column or 0,
            item.target or "",
            item.code,
        )
    )
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
        **({"receipt": reply.receipt} if reply.receipt is not None else {}),
        exit_code=exit_code,
    )


def render_validation(result: CommandResult, output_format: str) -> None:
    """Render only fixed messages and known ordinal coordinates, never private facts."""
    if output_format == "json":
        typer.echo(result.model_dump_json(exclude_none=True))
        return
    if result.assessment is not None:
        typer.echo(f"Intake validity: {result.assessment.validity}")
        for target in result.assessment.targets:
            typer.echo(f"Target {target.target}: {target.state}")
    typer.echo(
        f"Examined sources: {result.summary.examined_sources}; "
        f"unexamined sources: {result.summary.unexamined_sources}; "
        f"valid records: {result.summary.valid_records}"
    )
    if result.receipt is not None:
        typer.echo(f"Published {result.receipt.kind}: {result.receipt.sha256}")
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
        publication_actions = {
            "PUBLICATION_LOCKED": (
                "Confirm all writers have stopped before explicitly recovering "
                "the lock; preserve existing generations."
            ),
            "RETAINED_OUTPUT": (
                "Prior or uncommitted outputs are retained. Review them before "
                "explicit cleanup; no automatic cleanup occurred."
            ),
        }
        action = publication_actions.get(diagnostic.code, action)
        typer.echo(f"{diagnostic.severity}: {diagnostic.code}{location}. {action}")


def check_output_format(value: str) -> None:
    """Reject unsupported formats without echoing the supplied option value."""
    if value not in {"text", "json"}:
        raise fail(code="INVALID_INVOCATION")


Source = Annotated[Path, typer.Argument(help="Explicit workbook or catalog input.")]
Output = Annotated[Path, typer.Option("--output", help="Explicit output destination.")]
Config = Annotated[
    Path | None, typer.Option("--config", help="Explicit versioned TOML configuration.")
]
Report = Annotated[
    Path | None, typer.Option("--diagnostics", help="Separate private JSON report.")
]
Format = Annotated[str, typer.Option("--format", help="Result format: text or json.")]
Replace = Annotated[
    bool,
    typer.Option("--replace", help="Authorize replacement; retain bundle history."),
]
Recursive = Annotated[
    bool, typer.Option("--recursive", help="Include nested workbook directories.")
]
Targets = Annotated[
    list[str] | None,
    typer.Option("--target", help="Repeatable target: dcat-us-3 or odcs-3.2."),
]
Audience = Annotated[
    str, typer.Option("--audience", help="Output audience: internal or public.")
]


def run_intent(values: dict[str, object], output_format: str) -> None:
    """Validate closed invocation fields without exposing submitted option values."""
    try:
        request = CommandRequest.model_validate(values)
    except ValidationError:
        result = CommandResult.model_validate(
            {
                "schema_version": "1.0",
                "command": values["command"],
                "diagnostics": [fail(code="INVALID_INVOCATION").diagnostic],
                "summary": OperationSummary(),
                "exit_code": 2,
            }
        )
        render_validation(result, "json" if output_format == "json" else "text")
        if (
            output_format != "json"
            and values["command"] == "build"
            and values.get("audience") == "public"
        ):
            typer.echo("Use export with a saved canonical bundle for public output.")
        raise typer.Exit(2) from None
    run_catalog(request, output_format=output_format)


@app.command("template", cls=SafeCommand)
def template_command(
    *, output: Output, replace: Replace = False, diagnostics: Report = None
) -> None:
    """Generate a deterministic, accessible intake workbook."""
    run_intent(
        {
            "command": "template",
            "output": output,
            "replace": replace,
            **({"diagnostics": diagnostics} if diagnostics is not None else {}),
        },
        "text",
    )


@app.command("validate", cls=SafeCommand)
def validate_command(
    source: Source,
    *,
    recursive: Recursive = False,
    config: Config = None,
    diagnostics: Report = None,
    output_format: Format = "text",
) -> None:
    """Validate intake and assess both targets without publishing catalog data."""
    run_intent(
        {
            "command": "validate",
            "input": source,
            "recursive": recursive,
            **({"config": config} if config is not None else {}),
            **({"diagnostics": diagnostics} if diagnostics is not None else {}),
            "format": "json" if output_format == "json" else "text",
        },
        output_format,
    )


@app.command("build", cls=SafeCommand)
def build_command(  # noqa: PLR0913 -- Approved CLI options form one invocation.
    source: Source,
    *,
    output: Output,
    recursive: Recursive = False,
    config: Config = None,
    target: Targets = None,
    audience: Audience = "internal",
    replace: Replace = False,
    diagnostics: Report = None,
    output_format: Format = "text",
) -> None:
    """Build canonical data and any ready requested internal targets."""
    run_intent(
        {
            "command": "build",
            "input": source,
            "output": output,
            "recursive": recursive,
            "replace": replace,
            "targets": target or [],
            "audience": audience,
            **({"config": config} if config is not None else {}),
            **({"diagnostics": diagnostics} if diagnostics is not None else {}),
            "format": "json" if output_format == "json" else "text",
        },
        output_format,
    )


@app.command("export", cls=SafeCommand)
def export_command(  # noqa: PLR0913 -- Approved CLI options form one invocation.
    source: Source,
    *,
    output: Output,
    target: Targets = None,
    config: Config = None,
    audience: Audience = "internal",
    replace: Replace = False,
    diagnostics: Report = None,
    output_format: Format = "text",
) -> None:
    """Export saved canonical data to internal or approved public target bundles."""
    run_intent(
        {
            "command": "export",
            "input": source,
            "output": output,
            "targets": target or [],
            "audience": audience,
            "replace": replace,
            **({"config": config} if config is not None else {}),
            **({"diagnostics": diagnostics} if diagnostics is not None else {}),
            "format": "json" if output_format == "json" else "text",
        },
        output_format,
    )


def execute_catalog(request: CommandRequest) -> CommandResult:
    """Require command shape and a publication receipt before claiming build success."""
    check_disjoint(
        [
            path
            for path in (
                request.input,
                request.output,
                request.config,
                request.diagnostics,
            )
            if path is not None
        ]
    )
    if request.diagnostics is not None:
        check_file_destination(request.diagnostics, replace=request.replace)
    if request.command == "template":
        return execute_template(request)
    configuration = load_explicit_configuration(request.config)
    if request.input is None:
        raise fail(code="INVALID_INVOCATION")
    reply = invoke(
        CoordinatorRequest(
            schema_version="1.0",
            role="coordinator",
            discovery=DiscoveryRequest(
                input=request.input,
                recursive=request.recursive,
                **({"output": request.output} if request.output is not None else {}),
            ),
            operation="export" if request.command == "export" else "intake",
            targets=request.targets,
            audience=request.audience,
            **(
                {"diagnostics": request.diagnostics}
                if request.diagnostics is not None
                else {}
            ),
            replace=request.replace,
            assessment=configuration.assessment,
            configuration=configuration,
        ),
        300.0,
    )
    result = validation_result(reply)
    if (
        request.command in {"build", "export"}
        and result.exit_code == 0
        and reply.receipt is None
    ):
        raise fail(code="INTERNAL_FAILURE")
    return result


def execute_template(request: CommandRequest) -> CommandResult:
    """Finish workbook bytes and a separate report before exposing the output file."""
    if request.output is None:
        raise fail(code="INVALID_INVOCATION")
    check_file_destination(request.output, replace=request.replace)
    artifact = create_template()
    if request.diagnostics is not None:
        report = PrivateReport(
            schema_version="1.0", diagnostics=[], summary=OperationSummary()
        )
        publish_file(
            request.diagnostics, canonical_bytes(report), replace=request.replace
        )
    publish_file(request.output, artifact.content, replace=request.replace)
    return CommandResult(
        schema_version="1.0",
        command="template",
        diagnostics=[],
        summary=OperationSummary(),
        exit_code=0,
        receipt=OutputReceipt(
            kind="template", sha256=hashlib.sha256(artifact.content).hexdigest()
        ),
    )


def run_catalog(request: CommandRequest, *, output_format: str) -> None:
    """Execute the bounded coordinator and render one value-free command result."""
    try:
        check_output_format(output_format)
        result = execute_catalog(request)
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
    result = result.model_copy(update={"command": request.command})
    render_validation(result, request.format)
    raise typer.Exit(result.exit_code)
