# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Collect source, artifacts, inventories and current advisory inputs."""

import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import tomllib
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Literal, get_args

from pydantic import Field

from dscat.intake.discovery import reject_links
from dscat.models.base import StrictModel
from dscat.serialization import canonical_bytes
from dscat.storage.filesystems import require_local
from dscat.storage.io import read_file, write_file
from scripts.advisories import apply_dispositions, parse_audit, parse_kev
from scripts.artifacts import ARCHIVE_BYTES, MEMBER_BYTES, inspect_artifacts
from scripts.dependency_graph import locked_graph, reconcile_inventory, text_value
from scripts.environment_inventory import observe
from scripts.evidence_models import (
    ActualBindings,
    Artifact,
    ArtifactProvenance,
    Feed,
    Finding,
    Gate,
    GateName,
    InstalledAcceptance,
    Inventory,
    ProjectIdentity,
    ReleaseEvidence,
    SbomReconciliation,
)
from scripts.processes import Execution, run_tool
from scripts.provenance import NoRedirect, download_wheel, selected_wheels
from scripts.sbom import DOCUMENT_BYTES, validate_sbom
from scripts.sbom_reconciliation import (
    active_relationships,
    enrich_sbom,
    reconcile_sbom,
)

if TYPE_CHECKING:
    from scripts.advisories import ObservedAdvisory


KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
UV_VERSION = "0.13.6"
PYTHON_VERSION = "3.15.2"


class Claims(StrictModel):
    """Only explicit observed claims can replace pending acceptance gates."""

    schema_version: Literal["1.0"]
    findings: list[Finding] = Field(default_factory=list, max_length=10000)
    gates: list[Gate] = Field(default_factory=list, max_length=5)


@dataclass
class Collection:
    """Own a new private workspace and a separate allowlisted public asset directory."""

    project: Path
    output: Path
    uv: str
    executions: list[Execution] = field(default_factory=list)
    arguments: dict[str, list[str]] = field(default_factory=dict)

    @property
    def work(self) -> Path:
        """Keep installed environments and local paths outside distributable assets."""
        return self.output / "private"

    @property
    def assets(self) -> Path:
        """Expose assembled generic release evidence and distributions."""
        return self.output / "assets"

    def run(
        self,
        label: str,
        argv: list[str],
        *,
        accepted: frozenset[int] = frozenset({0}),
        directory: Path | None = None,
        environment: dict[str, str] | None = None,
    ) -> Execution:
        """Retain outcome identities and keep raw command output private."""
        execution = run_tool(
            argv,
            label=label,
            directory=self.project if directory is None else directory,
            logs=self.work / "logs",
            accepted=accepted,
            environment=tool_environment() if environment is None else environment,
        )
        self.executions.append(execution)
        self.arguments[label] = self.public_arguments(argv)
        return execution

    def public_arguments(self, argv: list[str]) -> list[str]:
        """Preserve command flags and replace local paths with stable placeholders."""
        result: list[str] = []
        for argument in argv:
            if argument == sys.executable:
                result.append("python")
            elif argument == self.uv:
                result.append("uv")
            elif argument.startswith("file://"):
                result.append("{local-file-uri}")
            elif Path(argument).is_absolute():
                path = Path(argument)
                if path.is_relative_to(self.project):
                    result.append(
                        "{source}/" + path.relative_to(self.project).as_posix()
                    )
                elif path.is_relative_to(self.output):
                    result.append(
                        "{candidate}/" + path.relative_to(self.output).as_posix()
                    )
                else:
                    result.append("{external-file}")
            else:
                result.append(argument)
        return result

    def captured(self, label: str) -> bytes:
        """Read a completed bounded tool result from this invocation's owned logs."""
        return read_file(self.work / "logs" / f"{label}.stdout", DOCUMENT_BYTES)


@dataclass(frozen=True)
class SourceState:
    """Git identity and dirty state are observed independently of candidate claims."""

    commit: str
    tree: str
    dirty: bool
    verified_main: bool


@dataclass(frozen=True)
class CollectedCandidate:
    """Collection does not imply readiness, approval or publication."""

    evidence: ReleaseEvidence
    actual: ActualBindings
    kev_cves: set[str]


def tool_environment() -> dict[str, str]:
    """Keep explicit tool choices above advisory/format environment options."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("PIP_AUDIT_", "UV_"))
        and key not in {"PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE"}
    }
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return environment


def write_json(path: Path, value: object) -> bytes:
    """Fully serialize generic evidence before exclusively creating its output file."""
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    write_file(path, raw)
    return raw


def initialize(project: Path, output: Path, uv: str) -> Collection:
    """Refuse existing outputs and source overlap before creating private work files."""
    reject_links(output)
    project, output = project.resolve(), output.resolve(strict=False)
    require_local(output.parent)
    if output.is_relative_to(project) or project.is_relative_to(output):
        msg = "Candidate output must be separate from the source checkout."
        raise ValueError(msg)
    output.mkdir(mode=0o700)
    collection = Collection(project=project, output=output, uv=uv)
    collection.work.mkdir(mode=0o700)
    (collection.work / "logs").mkdir(mode=0o700)
    collection.assets.mkdir(mode=0o700)
    return collection


def source_state(collection: Collection, phase: str) -> SourceState:
    """Observe HEAD/tree/status and compare exact HEAD to the actual remote main ref."""
    commands = {
        "commit": ["git", "rev-parse", "HEAD"],
        "tree": ["git", "rev-parse", "HEAD^{tree}"],
        "status": ["git", "status", "--porcelain=v1", "--untracked-files=normal"],
        "remote": ["git", "ls-remote", "origin", "refs/heads/main"],
    }
    values: dict[str, str] = {}
    for name, argv in commands.items():
        label = f"source-{phase}-{name}"
        collection.run(label, argv)
        values[name] = collection.captured(label).decode("utf-8").strip()
    remote = values["remote"].split()
    return SourceState(
        commit=values["commit"],
        tree=values["tree"],
        dirty=bool(values["status"]),
        verified_main=remote == [values["commit"], "refs/heads/main"],
    )


def source_snapshot(collection: Collection) -> dict[str, bytes]:
    """Read only tracked regular reviewed source files, never ignored local material."""
    collection.run("source-files", ["git", "ls-files", "-z"])
    return {
        name.decode("utf-8"): read_file(
            collection.project / name.decode("utf-8"), MEMBER_BYTES
        )
        for name in collection.captured("source-files").split(b"\0")
        if name
    }


def check_tools(collection: Collection) -> dict[str, str]:
    """Compare observed interpreter and tool versions with selected pins."""
    if platform.python_version() != PYTHON_VERSION:
        msg = "The selected verification interpreter is unavailable."
        raise ValueError(msg)
    collection.run("uv-version", [collection.uv, "--version"])
    if collection.captured("uv-version").decode().split()[:2] != ["uv", UV_VERSION]:
        msg = "The selected uv version is unavailable."
        raise ValueError(msg)
    configuration = tomllib.loads((collection.project / "pyproject.toml").read_text())
    versions = {"python": platform.python_version(), "uv": UV_VERSION}
    for requirement in configuration["dependency-groups"]["dev"]:
        name, expected = text_value(requirement).split("==")
        version = importlib.metadata.version(name)
        if version != expected:
            msg = "The verification environment does not match its selected tool pins."
            raise ValueError(msg)
        versions[name] = version
    return versions


def build_artifacts(
    collection: Collection, source: dict[str, bytes]
) -> tuple[Artifact, Artifact]:
    """Build with frozen tools and inspect actual archive/source bytes."""
    project = tomllib.loads(source["pyproject.toml"].decode())["project"]
    identity = ProjectIdentity(
        version=project["version"],
        requires_python=project["requires-python"],
        requirements=project["dependencies"],
    )
    collection.run(
        "build",
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--outdir",
            str(collection.assets),
        ],
    )
    wheel_name = f"dscat-{identity.version}-py3-none-any.whl"
    sdist_name = f"dscat-{identity.version}.tar.gz"
    if {path.name for path in collection.assets.iterdir()} != {wheel_name, sdist_name}:
        msg = "Build outputs do not match the expected wheel and source distribution."
        raise ValueError(msg)
    result = inspect_artifacts(
        read_file(collection.assets / wheel_name, ARCHIVE_BYTES),
        read_file(collection.assets / sdist_name, ARCHIVE_BYTES),
        source,
        identity,
    )
    return Artifact(name=wheel_name, sha256=result.wheel_sha256), Artifact(
        name=sdist_name, sha256=result.sdist_sha256
    )


def export_requirements(collection: Collection) -> dict[str, Path]:
    """Export exact locked hashes without resolving new versions."""
    paths: dict[str, Path] = {}
    for scope, flags in [("runtime", ["--no-dev"]), ("development", ["--all-groups"])]:
        destination = collection.work / f"{scope}-requirements.txt"
        collection.run(
            f"export-{scope}",
            [
                collection.uv,
                "export",
                "--project",
                str(collection.project),
                "--frozen",
                *flags,
                "--no-emit-project",
                "--no-header",
                "--no-annotate",
                "--output-file",
                str(destination),
            ],
        )
        write_file(
            collection.assets / f"{scope}-requirements.txt",
            read_file(destination, DOCUMENT_BYTES),
        )
        paths[scope] = destination
    return paths


def install_runtime(
    collection: Collection, wheel: Artifact, lock: bytes, requirements: Path
) -> tuple[Path, Inventory]:
    """Install verified archives into a clean runtime-only environment."""
    from packaging.tags import sys_tags  # noqa: PLC0415 -- Tag observation belongs to this interpreter boundary.

    observed = Inventory.model_validate(observe())
    expected = locked_graph(lock, observed.marker_environment)
    pins = selected_wheels(lock, expected, list(sys_tags()))
    wheelhouse = collection.work / "wheelhouse"
    wheelhouse.mkdir(mode=0o700)
    for pin in pins.values():
        download_wheel(pin, wheelhouse)
    environment = collection.work / "runtime"
    collection.run(
        "runtime-venv",
        [
            collection.uv,
            "venv",
            str(environment),
            "--python",
            sys.executable,
            "--offline",
        ],
    )
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    collection.run(
        "runtime-install",
        [
            sys.executable,
            "-m",
            "pip",
            "--isolated",
            "--python",
            str(python),
            "install",
            "--no-index",
            "--no-deps",
            "--no-cache-dir",
            "--find-links",
            str(wheelhouse),
            "--require-hashes",
            "--requirement",
            str(requirements),
        ],
    )
    application_requirements = collection.work / "application.txt"
    application_requirements.write_text(
        f"{(collection.assets / wheel.name).as_uri()} --hash=sha256:{wheel.sha256}\n"
    )
    collection.run(
        "application-install",
        [
            sys.executable,
            "-m",
            "pip",
            "--isolated",
            "--python",
            str(python),
            "install",
            "--no-index",
            "--no-deps",
            "--no-cache-dir",
            "--require-hashes",
            "--requirement",
            str(application_requirements),
        ],
    )
    collection.run(
        "runtime-inventory",
        [
            str(python),
            "-I",
            str(collection.project / "scripts/environment_inventory.py"),
        ],
    )
    inventory = Inventory.model_validate_json(collection.captured("runtime-inventory"))
    distributions = [
        package.model_copy(
            update={
                "artifact_sha256": pins[package.name].sha256,
                "artifact_url": pins[package.name].url,
            }
        )
        if package.name in pins
        else package
        for package in inventory.distributions
    ]
    inventory = Inventory.model_validate(
        inventory.model_copy(update={"distributions": distributions}).model_dump(
            exclude_none=True
        )
    )
    reconcile_inventory(inventory, expected)
    return python, inventory


def stamp() -> str:
    """Record retrieval time independently of a feed's last-update date."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def collect_advisories(
    collection: Collection,
    inventories: dict[Literal["runtime", "development"], Inventory],
    requirements: dict[str, Path],
) -> tuple[list[Feed], list[ObservedAdvisory], set[str]]:
    """Capture both advisory services and the complete exploitation catalog."""
    feeds: list[Feed] = []
    advisories: list[ObservedAdvisory] = []
    for scope, inventory in inventories.items():
        for service in ("pypi", "osv"):
            label = f"{service}-{scope}"
            output = collection.assets / f"{label}.json"
            outcome = collection.run(
                label,
                [
                    sys.executable,
                    "-m",
                    "pip_audit",
                    "--vulnerability-service",
                    service,
                    "--require-hashes",
                    "--disable-pip",
                    "--no-deps",
                    "--strict",
                    "--aliases",
                    "on",
                    "--desc",
                    "on",
                    "--format",
                    "json",
                    "--progress-spinner",
                    "off",
                    "--cache-dir",
                    str(collection.work / label),
                    "--requirement",
                    str(requirements[scope]),
                    "--output",
                    str(output),
                ],
                accepted=frozenset({0, 1}),
            )
            raw = read_file(output, DOCUMENT_BYTES)
            observed = parse_audit(raw, inventory, scope)
            if outcome.returncode != int(bool(observed)):
                msg = "Advisory result and scanner exit status disagree."
                raise ValueError(msg)
            advisories.extend(observed)
            feeds.append(
                Feed(
                    source=service,
                    scope=scope,
                    retrieved_at=stamp(),
                    sha256=hashlib.sha256(raw).hexdigest(),
                    state="complete",
                )
            )
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(KEV_URL, timeout=30) as response:
        if response.geturl() != KEV_URL or response.getcode() != HTTPStatus.OK:
            msg = "Known-exploitation retrieval did not retain its selected source."
            raise ValueError(msg)
        raw = response.read(DOCUMENT_BYTES + 1)
    if not isinstance(raw, bytes) or len(raw) > DOCUMENT_BYTES:
        msg = "Known-exploitation response exceeds its supported bounds."
        raise ValueError(msg)
    kev_cves = parse_kev(raw)
    write_file(collection.assets / "cisa-kev.json", raw)
    feeds.append(
        Feed(
            source="cisa-kev",
            scope="catalog",
            retrieved_at=stamp(),
            sha256=hashlib.sha256(raw).hexdigest(),
            state="complete",
        )
    )
    return feeds, advisories, kev_cves


def collect_sbom(
    collection: Collection,
    python: Path,
    inventory: Inventory,
    provenance: ArtifactProvenance,
) -> bytes:
    """Generate 1.6 JSON and validate its schema and archive provenance."""
    output = collection.work / "generator-sbom.json"
    collection.run(
        "sbom-generator",
        [
            sys.executable,
            "-m",
            "cyclonedx_py",
            "environment",
            str(python),
            "-E",
            "--spec-version",
            "1.6",
            "--output-format",
            "JSON",
            "--output-reproducible",
            "--pyproject",
            str(collection.project / "pyproject.toml"),
            "--output-file",
            str(output),
        ],
    )
    raw = read_file(output, DOCUMENT_BYTES)
    document = validate_sbom(raw)
    enriched = enrich_sbom(document, inventory, provenance)
    enriched, corrections = active_relationships(
        enriched,
        inventory,
        locked_graph(
            read_file(collection.project / "uv.lock", DOCUMENT_BYTES),
            inventory.marker_environment,
        ),
    )
    write_file(
        collection.assets / "sbom-reconciliation.json",
        canonical_bytes(
            SbomReconciliation(
                schema_version="1.0",
                generator_sha256=hashlib.sha256(raw).hexdigest(),
                relationship_source="installed-requires-dist-and-lock",
                corrections=corrections,
            )
        ),
    )
    return write_json(
        collection.assets / "sbom.cdx.json",
        enriched,
    )


def candidate_gates(claims: Claims, source: SourceState, wheel: Artifact) -> list[Gate]:
    """Leave every unobserved acceptance item explicitly pending and unassigned."""
    existing = {gate.name: gate for gate in claims.gates}
    if len(existing) != len(claims.gates):
        msg = "Acceptance claims contain duplicate gate identities."
        raise ValueError(msg)
    return [
        existing[name]
        if name in existing
        else Gate(
            name=name,
            state="pending",
            executor_role="unassigned",
            source_sha=source.commit,
            wheel_sha256=wheel.sha256,
        )
        for name in get_args(GateName)
    ]


def collect_candidate(
    project: Path, output: Path, uv: str, claims: Claims
) -> CollectedCandidate:
    """Assemble actual evidence without authorizing or publishing a release."""
    collection = initialize(project, output, uv)
    tools = check_tools(collection)
    before = source_state(collection, "before")
    source = source_snapshot(collection)
    lock = source["uv.lock"]
    development = Inventory.model_validate(observe())
    reconcile_inventory(
        development,
        locked_graph(lock, development.marker_environment, development=True),
    )
    wheel, sdist = build_artifacts(collection, source)
    write_file(
        collection.assets / "application-requirements.txt",
        f"./{wheel.name} --hash=sha256:{wheel.sha256}\n".encode(),
    )
    write_file(
        collection.assets / "development-inventory.json", canonical_bytes(development)
    )
    requirements = export_requirements(collection)
    python, runtime = install_runtime(collection, wheel, lock, requirements["runtime"])
    installed_acceptance(collection, python)
    provenance = ArtifactProvenance(
        source_sha=before.commit,
        source_tree=before.tree,
        version=tomllib.loads(source["pyproject.toml"].decode())["project"]["version"],
        lock_sha256=hashlib.sha256(lock).hexdigest(),
        wheel_sha256=wheel.sha256,
        sdist_sha256=sdist.sha256,
    )
    sbom = collect_sbom(collection, python, runtime, provenance)
    feeds, observed, kev_cves = collect_advisories(
        collection, {"runtime": runtime, "development": development}, requirements
    )
    after = source_state(collection, "after")
    if (before.commit, before.tree) != (after.commit, after.tree):
        msg = "Source identity changed during candidate collection."
        raise ValueError(msg)
    tool_report = write_json(
        collection.assets / "tool-executions.json",
        {
            "source_sha": before.commit,
            "tools": tools,
            "commands": [
                execution.record() | {"argv": collection.arguments[execution.check]}
                for execution in collection.executions
            ],
        },
    )
    actual = ActualBindings(
        **provenance.model_dump(),
        verified_main=before.verified_main and after.verified_main,
        source_dirty=before.dirty or after.dirty,
        sbom_sha256=hashlib.sha256(sbom).hexdigest(),
        tool_evidence_sha256=hashlib.sha256(tool_report).hexdigest(),
    )
    reconcile_sbom(
        sbom, runtime, locked_graph(lock, runtime.marker_environment), actual
    )
    evidence = ReleaseEvidence.model_validate(
        {
            "schema_version": "1.0",
            "source_sha": actual.source_sha,
            "source_tree": actual.source_tree,
            "source_dirty": actual.source_dirty,
            "version": actual.version,
            "lock_sha256": actual.lock_sha256,
            "wheel": wheel,
            "sdist": sdist,
            "sbom_sha256": actual.sbom_sha256,
            "tool_evidence_sha256": actual.tool_evidence_sha256,
            "generator_version": tools["cyclonedx-bom"],
            "scanner_version": tools["pip-audit"],
            "runtime": runtime,
            "development": development,
            "feeds": feeds,
            "findings": apply_dispositions(observed, claims.findings, kev_cves),
            "gates": candidate_gates(claims, before, wheel),
        }
    )
    write_file(collection.assets / "release-evidence.json", canonical_bytes(evidence))
    return CollectedCandidate(evidence=evidence, actual=actual, kev_cves=kev_cves)


def installed_acceptance(collection: Collection, python: Path) -> None:
    """Prepare synthetic materials and execute the installed workflow outside source."""
    import tomli_w  # noqa: PLC0415 -- Development-only material preparation.
    from tests.test_publication_bindings import (  # noqa: PLC0415 -- Shared explicit synthetic approvals.
        approved_fixture,
    )

    from dscat.models.catalog import Catalog  # noqa: PLC0415 -- Synthetic fixture boundary.

    materials = collection.work / "materials"
    materials.mkdir(mode=0o700)
    record, configuration = approved_fixture(detailed=True)
    catalog = Catalog(schema_version="1.0", datasets=[record])
    (materials / "approved.json").write_bytes(canonical_bytes(catalog))
    (materials / "settings.toml").write_text(
        tomli_w.dumps(configuration.model_dump(mode="json", exclude_none=True))
    )
    acceptance = collection.work / "acceptance"
    task_home = collection.work / "home"
    task_home.mkdir(mode=0o700)
    task_cache = collection.work / "runtime-cache"
    task_cache.mkdir(mode=0o700)
    environment = tool_environment() | {
        "HOME": str(task_home),
        "USERPROFILE": str(task_home),
        "XDG_CONFIG_HOME": str(task_home / "config"),
        "XDG_CACHE_HOME": str(task_cache),
        "APPDATA": str(task_home / "appdata"),
        "LOCALAPPDATA": str(task_home / "localappdata"),
    }
    log = collection.work / "network-events"
    guard = (
        "import os, sys\n"
        "def deny(event,args):\n"
        " if event.startswith('socket.') and event != 'socket.gethostname':\n"
        "  with open(os.environ['DSCAT_NETWORK_LOG'],'a') as stream:\n"
        "   stream.write(event+'\\n')\n"
        "  raise RuntimeError('Runtime network denied')\n"
        "sys.addaudithook(deny)\n"
    )
    site = (
        python.parent.parent / "Lib/site-packages"
        if os.name == "nt"
        else python.parent.parent
        / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
    )
    hook = site / "_dscat_acceptance_network_guard.py"
    startup = site / "_dscat_acceptance_network_guard.pth"
    environment["DSCAT_NETWORK_LOG"] = str(log)
    with hook.open("x") as stream:
        stream.write(guard)
    try:
        with startup.open("x") as stream:
            stream.write("import _dscat_acceptance_network_guard\n")
        try:
            collection.run(
                "installed-acceptance",
                [
                    str(python),
                    "-I",
                    str(collection.project / "scripts/installed_acceptance.py"),
                    "--materials",
                    str(materials),
                    "--workspace",
                    str(acceptance),
                ],
                directory=collection.work,
                environment=environment,
            )
        finally:
            startup.unlink()
    finally:
        hook.unlink()
    observed = InstalledAcceptance.model_validate_json(
        collection.captured("installed-acceptance")
    )
    write_file(
        collection.assets / "installed-acceptance.json", canonical_bytes(observed)
    )
