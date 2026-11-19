# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Command-line interface for Dataset Catalog."""

from typing import Annotated

import typer

from dscat import __version__

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
    typer.echo(ctx.get_help())
