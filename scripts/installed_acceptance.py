# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Exercise an installed wheel using synthetic materials and the public CLI."""

import argparse
import hashlib
import io
import json
import os
import socket
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from openpyxl import load_workbook
from referencing.exceptions import Unresolvable

import dscat
from dscat.models.catalog import Catalog
from dscat.models.diagnostics import CommandResult
from dscat.resources.registry import load_registry
from dscat.storage.flatfiles import load_snapshot, save_snapshot
from dscat.storage.projections import load_projection_snapshot
from dscat.workbook.generate import relative_worksheet_relationships

if TYPE_CHECKING:
    from dscat.models.diagnostics import OutputReceipt


def require(condition: bool, message: str) -> None:  # noqa: FBT001 -- Predicate assertion, not a behavior flag.
    """Keep acceptance checks active even when Python assertions are disabled."""
    if not condition:
        raise ValueError(message)


def require_receipt(result: CommandResult | None) -> OutputReceipt:
    """Require an actual publication receipt and retain its concrete typed identity."""
    if result is None or result.receipt is None:
        msg = "Installed publication omitted its receipt."
        raise ValueError(msg)
    return result.receipt


def confirm_network_guard(log: Path) -> bytes:
    """Prove socket refusal before descriptor creation or any host contact."""
    denied = False
    try:
        with socket.socket():
            pass
    except RuntimeError:
        denied = True
    require(denied, "Installed acceptance requires a real denying network guard.")
    return log.read_bytes()


def invoke(work: Path, arguments: list[str], expected: int) -> CommandResult | None:
    """Invoke only the installed public CLI and check its actual outcome and privacy."""
    completed = subprocess.run(  # noqa: S603 -- Fixed interpreter/CLI and owned synthetic paths.
        [sys.executable, "-I", "-c", "from dscat.cli import app; app()", *arguments],
        cwd=work,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    require(completed.returncode == expected, "Installed command outcome mismatch.")
    require(not completed.stderr, "Installed command produced unexpected stderr.")
    require(str(work) not in completed.stdout, "Installed diagnostics exposed a path.")
    require(
        "Synthetic measurements" not in completed.stdout,
        "Installed diagnostics exposed a value.",
    )
    if arguments[0] == "template":
        return None
    result = CommandResult.model_validate_json(completed.stdout)
    require(result.exit_code == expected, "Installed JSON exit status mismatch.")
    return result


def complete_synthetic_workbook(template: bytes, destination: Path) -> None:
    """Edit a self-generated workbook fixture, never an untrusted submission."""
    workbook = load_workbook(io.BytesIO(template))
    sheet = workbook["Datasets"]
    headers = {cell.value: cell.column for cell in sheet[1] if cell.value is not None}
    for key, value in {
        "id": "asset-001",
        "title": "Synthetic measurements",
        "description": "Synthetic metadata.",
        "core_party": "Metadata support",
    }.items():
        sheet.cell(2, headers[key], value)
    stream = io.BytesIO()
    workbook.save(stream)
    with (
        zipfile.ZipFile(stream) as source,
        zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as output,
    ):
        for name in source.namelist():
            raw = source.read(name)
            if name == "xl/_rels/workbook.xml.rels":
                raw = relative_worksheet_relationships(raw)
            output.writestr(name, raw)


def exercise(materials: Path, work: Path) -> dict[str, object]:
    """Run template/intake/both exports and preserve accepted outputs after denial."""
    require(
        Path(dscat.__file__).is_relative_to(Path(sys.prefix)),
        "Acceptance imported source instead of installed software.",
    )
    work.mkdir(mode=0o700)
    log = Path(os.environ["DSCAT_NETWORK_LOG"])
    guard_probe = confirm_network_guard(log)
    template = work / "template.xlsx"
    invoke(work, ["template", "--output", str(template)], 0)
    source = work / "intake.xlsx"
    complete_synthetic_workbook(template.read_bytes(), source)
    original = source.read_bytes()
    config = ["--config", str(materials / "settings.toml")]
    targets = ["--target", "dcat-us-3", "--target", "odcs-3.2"]
    invoke(work, ["validate", str(source), *config, "--format", "json"], 0)
    build = [
        "build",
        str(source),
        "--output",
        str(work / "built"),
        *config,
        *targets,
        "--format",
        "json",
    ]
    first = require_receipt(invoke(work, build, 0))
    invoke(work, build, 3)
    repeated = invoke(work, [*build, "--replace"], 0)
    require(
        repeated is not None and repeated.receipt == first,
        "Identical build changed output identity.",
    )
    require(
        source.read_bytes() == original, "An installed command changed the intake file."
    )
    source.unlink()
    invoke(
        work,
        [
            "export",
            str(work / "built"),
            "--output",
            str(work / "derived"),
            *config,
            *targets,
            "--format",
            "json",
        ],
        0,
    )
    require(
        load_snapshot(work / "built").catalog
        == load_snapshot(work / "derived").catalog,
        "Saved-catalog export changed canonical facts.",
    )
    approved = Catalog.model_validate_json((materials / "approved.json").read_bytes())
    save_snapshot(work / "approved-source", approved)
    public = [
        "export",
        str(work / "approved-source"),
        "--output",
        str(work / "public"),
        *config,
        *targets,
        "--audience",
        "public",
        "--diagnostics",
        str(work / "private-report.json"),
        "--format",
        "json",
    ]
    published = require_receipt(invoke(work, public, 0))
    require(
        load_projection_snapshot(work / "public").generation == published.sha256,
        "Public export could not reload its exact bytes.",
    )
    again = invoke(work, [*public, "--replace"], 0)
    require(
        again is not None and again.receipt == published,
        "Identical public export changed identity.",
    )
    previous = (work / "public/CURRENT").read_bytes()
    invoke(
        work,
        [
            "export",
            str(work / "built"),
            "--output",
            str(work / "public"),
            *config,
            *targets,
            "--audience",
            "public",
            "--replace",
            "--format",
            "json",
        ],
        1,
    )
    require(
        (work / "public/CURRENT").read_bytes() == previous,
        "Denied public output changed CURRENT.",
    )
    bundle = load_registry()
    denied = False
    try:
        bundle.registry.resolver().lookup("https://example.org/unknown-schema")
    except Unresolvable:
        denied = True
    require(denied, "Unknown schema retrieval was not refused.")
    require(
        log.read_bytes() == guard_probe,
        "Installed workflow attempted network operations.",
    )
    return {
        "schema_version": "1.0",
        "state": "pass",
        "cli_cases": 9,
        "guard_probe_denied": True,
        "workflow_network_attempts": 0,
        "unknown_reference_denied": True,
        "template_sha256": hashlib.sha256(template.read_bytes()).hexdigest(),
        "canonical_generation": first.sha256,
        "public_generation": published.sha256,
    }


def main() -> None:
    """Run only inside the separately installed runtime environment."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--materials", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    arguments = parser.parse_args()
    result = exercise(arguments.materials, arguments.workspace)
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
