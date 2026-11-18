"""Explicit local configuration and executable maintenance commands."""

from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, NoReturn

from . import __version__, candidate, mapping, migration, transport
from .identity import domain, load_secret
from .importer import Config, capture
from .ledger import contribution_digest
from .metrics import Rate, validate_rates
from .private import StateStore, atomic_write, locked, read_bytes, read_json, safe_path
from .review import bindings, validate_review
from .schema import Contribution, Status, UsageError, Vocabulary, canonical, digest, integer, keys, loads, require, sha

NOTICE = "Proprietary to Obscurity Labs. All rights reserved."
EMPTY_VOCAB = {
    "schema": 1,
    **{name: [] for name in ("models", "providers", "efforts", "tiers", "rtm", "tasks", "features")},
}


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        del message
        reason = "invalid command arguments"
        raise UsageError(reason, 2)


def _parser() -> argparse.ArgumentParser:  # noqa: C901 - explicit fixed subcommand option matrix.
    parser = _Parser(description="Private local usage accounting. " + NOTICE)
    parser.add_argument("--version", action="version", version=__version__ + " — " + NOTICE)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("setup", "map", "migrate", "refresh", "contribute", "check", "review", "update", "readback"):
        command = commands.add_parser(name, description=NOTICE)
        command.add_argument("--state", type=Path, required=True)
        command.add_argument("--json", action="store_true", dest="json_output")
        if name in {"setup", "map", "migrate", "refresh", "contribute", "update"}:
            command.add_argument("--config", type=Path, required=True)
        if name == "setup":
            command.add_argument("--secret-file", type=Path, required=True)
        if name == "map":
            command.add_argument("--entry", type=Path, required=True)
        if name == "migrate":
            for option in ("snapshot", "phase-map", "registry"):
                command.add_argument("--" + option, type=Path, required=True)
            command.add_argument("--identity-map", type=Path)
        if name in {"contribute", "update", "readback"}:
            command.add_argument("--remote", required=True)
            command.add_argument("--branch", required=True)
        if name in {"contribute", "update"}:
            command.add_argument("--generator-invocation", required=True)
        if name == "check":
            command.add_argument("--candidate")
        if name == "review":
            command.add_argument("--attestation", type=Path, required=True)
            command.add_argument("--execution-evidence", type=Path, required=True)
        if name == "readback":
            command.add_argument("--expected-commit", required=True)
            command.add_argument("--reader-invocation", required=True)
    return parser


def _outside_transport(root: Path) -> None:
    for parent in (root, *root.parents):
        require(
            not (parent / ".git").exists() and not ((parent / "HEAD").exists() and (parent / "objects").is_dir()),
            "state must be outside transport checkout",
            3,
        )


def _config(path: Path) -> tuple[Config, bytes]:
    raw = read_bytes(path, private=True)
    return Config.from_dict(loads(raw)), raw


def _inventory(config: Config) -> tuple[Vocabulary, bytes, bytes]:
    vocabulary_raw, rates_raw = read_bytes(config.vocabulary_path), read_bytes(config.rates_path)
    vocabulary = Vocabulary.from_dict(loads(vocabulary_raw))
    rates = loads(rates_raw)
    keys(rates, {"schema", "rates"})
    integer(rates["schema"], 1, 1)
    require(isinstance(rates["rates"], list))
    validate_rates(tuple(Rate.from_dict(row, vocabulary) for row in rates["rates"]), vocabulary)
    return vocabulary, vocabulary_raw, rates_raw


def _entries(value: dict[str, Any], vocabulary: Vocabulary) -> list[dict[str, Any]]:
    keys(value, {"schema", "entries"})
    integer(value["schema"], 1, 1)
    mapping.validate_entries(value["entries"], vocabulary)
    return value["entries"]


def _secret(store: StateStore, config: Config) -> bytes:
    secret = load_secret(config.secret_file)
    require(domain(secret) == store.manifest["domain"], "receipt domain mismatch", 4)
    return secret


def _setup(args: argparse.Namespace) -> Status:
    root = safe_path(args.state, exists=False)
    _outside_transport(root)
    path = safe_path(args.config, exists=False)
    secret_path = safe_path(args.secret_file)
    secret = load_secret(secret_path)
    # Existing caller-authored config is accepted, never replaced. A generated
    # template deliberately points to unavailable sources until explicitly edited.
    if path.exists():
        config, _ = _config(path)
        require(config.secret_file == secret_path, "secret configuration mismatch")
        _inventory(config)
        _entries(
            loads(read_bytes(config.map_path, private=True)), Vocabulary.from_dict(read_json(config.vocabulary_path))
        )
    else:
        safe_path(path.parent)
        config = Config(
            root / "unconfigured-history",
            str(root / "unconfigured-project"),
            root / "map.json",
            root / "rates.json",
            root / "vocabulary.json",
            secret_path,
        )
    store = StateStore.create(root, domain(secret))
    if not path.exists():
        for name, value in (
            ("map.json", {"schema": 1, "entries": []}),
            ("rates.json", {"schema": 1, "rates": []}),
            ("vocabulary.json", EMPTY_VOCAB),
        ):
            atomic_write(root / name, canonical(value))
        atomic_write(path, canonical(_config_dict(config)))
    store.put("map", {"schema": 1, "entries": []})
    return Status("prepared")


def _config_dict(config: Config) -> dict[str, Any]:
    return {
        **asdict(config),
        **{
            key: str(getattr(config, key))
            for key in ("source_root", "map_path", "rates_path", "vocabulary_path", "secret_file")
        },
    }


def _next_generation(store: StateStore, vocabulary: Vocabulary) -> tuple[int, str | None]:
    accepted = store.get("accepted")
    attempt = store.get("submission-attempt")
    if attempt is not None:
        keys(attempt, {"schema", "candidate_digest"})
        integer(attempt["schema"], 1, 1)
        sha(attempt["candidate_digest"])
        require(
            accepted is not None and accepted.get("candidate_digest") == attempt["candidate_digest"],
            "pending submission unresolved; review and retry update before refresh",
            5,
        )
    if accepted is None:
        return 1, None
    keys(accepted, {"schema", "candidate_digest", "commit"})
    integer(accepted["schema"], 1, 1)
    _, _, _, frozen = candidate.load(store, accepted["candidate_digest"])
    committed = Contribution.from_dict(loads(frozen["contribution"]), vocabulary)
    require(committed.contributor == store.manifest["contributor"], "accepted contributor mismatch", 4)
    return committed.generation + 1, contribution_digest(committed, vocabulary)


def _refresh(store: StateStore, config_path: Path) -> Status:
    with locked(store.root):
        config, original_config = _config(config_path)
        secret = _secret(store, config)
        vocabulary, vocabulary_raw, rates_raw = _inventory(config)
        original_map = read_bytes(config.map_path, private=True)
        entries = list(_entries(loads(original_map), vocabulary))
        for entry in _entries(store.get("map") or {"schema": 1, "entries": []}, vocabulary):
            if entry not in entries:
                entries.append(entry)
        mapping.validate_entries(entries, vocabulary)
        captured = capture(config, secret, entries, vocabulary)
        previous_value = store.get("contribution")
        previous = Contribution.from_dict(previous_value, vocabulary) if previous_value is not None else None
        old = {row.receipt for row in previous.observations} if previous else set()
        present = {row.receipt for row in captured.observations}
        # Missing local history is never an implicit correction/removal.
        require(old <= present, "previous observations unavailable; restore sources before refresh", 3)
        generation, predecessor = _next_generation(store, vocabulary)
        contribution = Contribution(
            captured.domain,
            store.manifest["contributor"],
            generation,
            predecessor,
            captured.observed_at,
            captured.observations,
            coverage=captured.coverage,
        )
        contribution.validate(vocabulary)
        observations = [row.to_dict() for row in captured.observations]
        associations = [asdict(row) for row in captured.associations]
        closure = {
            "original-config": original_config,
            "original-map": original_map,
            "map": canonical({"schema": 1, "entries": entries}),
            "vocabulary": vocabulary_raw,
            "rates": rates_raw,
            "contribution": canonical(contribution.to_dict()),
            "capture": canonical(
                {
                    "schema": 1,
                    "domain": captured.domain,
                    "observed_at": captured.observed_at,
                    "input_digests": captured.input_digests,
                    "contribution_digest": digest(canonical(contribution.to_dict())),
                }
            ),
            "normalized": canonical(
                {
                    "schema": 1,
                    "observations": observations,
                    "associations": associations,
                    "diagnostics": captured.diagnostics,
                    "coverage": captured.coverage,
                }
            ),
            "source-descriptor": canonical(
                {
                    "schema": 1,
                    "source_root": str(config.source_root),
                    "project_selector": config.project_selector,
                    "input_digests": captured.input_digests,
                    "consistency": "separate-stable-prefixes-and-readonly-transactions",
                    "domain": captured.domain,
                }
            ),
        }
        migrated = store.get("migration")
        if migrated is not None:
            closure["migration"] = canonical(migrated)
        snapshots = store.root / "snapshots"
        if not snapshots.exists():
            snapshots.mkdir(mode=0o700)
        safe_path(snapshots)
        # The directory is private and remains immutable after its pointer commits.
        with tempfile.TemporaryDirectory(prefix=".refresh-", dir=snapshots) as temporary:
            staging = Path(temporary)
            destination = snapshots / digest(canonical({name: digest(raw) for name, raw in closure.items()}))
            frozen_config = {
                **_config_dict(config),
                **{key + "_path": str(destination / key) for key in ("map", "rates", "vocabulary")},
            }
            closure["config"] = canonical(frozen_config)
            for name, raw in closure.items():
                atomic_write(staging / name, raw)
            paths = {name: str(destination / name) for name in closure}
            require(not destination.exists(), "snapshot collision", 3)
            staging.rename(destination)
            # TemporaryDirectory cleanup tolerates a directory moved into place.
        store.put_many_locked(
            {
                "contribution": contribution.to_dict(),
                "refresh": {"schema": 1, "paths": paths, "config_digest": digest(original_config)},
            }
        )
        return Status(
            "prepared",
            {
                "responses": sum(row.kind == "response" for row in captured.observations),
                "turns": sum(row.kind == "turn" for row in captured.observations),
                "threads": sum(row.kind == "thread" for row in captured.observations),
                "unavailable": captured.coverage["unavailable_sources"],
                "partial_lines": captured.coverage["partial_lines"],
            },
        )


def _inputs(store: StateStore, config_path: Path) -> dict[str, Path]:
    refresh = store.get("refresh")
    if refresh is None:
        reason = "refresh required before contribution"
        raise UsageError(reason, 3)
    keys(refresh, {"schema", "paths", "config_digest"})
    integer(refresh["schema"], 1, 1)
    require(
        digest(read_bytes(config_path, private=True)) == refresh["config_digest"],
        "configuration changed; refresh required",
        5,
    )
    # Bind only immutable captured files, never live histories or live secrets.
    return {label: safe_path(Path(path)) for label, path in refresh["paths"].items()}


def _run(args: argparse.Namespace) -> Status:  # noqa: PLR0911 - one explicit return per fixed command.
    if args.command == "setup":
        return _setup(args)
    root = safe_path(args.state)
    _outside_transport(root)
    store = StateStore(root)
    if args.command == "refresh":
        return _refresh(store, args.config)
    if args.command in {"map", "migrate"}:
        config, _ = _config(args.config)
        _secret(store, config)
        vocabulary, _, _ = _inventory(config)
        if args.command == "map":
            # Check external entries as well as the locked local registry.
            entry = loads(read_bytes(args.entry, private=True))
            mapping.validate_entries(
                [*_entries(loads(read_bytes(config.map_path, private=True)), vocabulary), entry], vocabulary
            )
            mapping.upsert(store, entry, vocabulary)
            return Status("prepared")
        result = migration.migrate(
            store,
            args.snapshot,
            args.phase_map,
            args.registry,
            identity_map=args.identity_map,
            config=config,
            secret=_secret(store, config),
            vocabulary=vocabulary,
        )
        return Status("prepared", {"archived": result.archived, "migrated": len(result.promoted)})
    if args.command == "contribute":
        value = candidate.prepare(
            store,
            remote=args.remote,
            branch=args.branch,
            generator_invocation=args.generator_invocation,
            inputs=_inputs(store, args.config),
            synthetic=_synthetic(args.remote),
        )
        return Status("review_required", candidate_digest=bindings(value)["candidate_digest"])
    if args.command == "check":
        value = candidate.validate(store, args.candidate)
        return Status("prepared", candidate_digest=bindings(value)["candidate_digest"])
    if args.command == "review":
        value = validate_review(store, attestation=args.attestation, execution_evidence=args.execution_evidence)
        return Status("prepared", candidate_digest=bindings(value)["candidate_digest"])
    if args.command == "update":
        if store.get("candidate") is not None:
            frozen = candidate.validate(store, require_review=True)
            _, _, _, inputs = candidate.load(store)
            require(
                inputs["contribution"] == canonical(store.get("contribution")),
                "new capture requires contribute and fresh review",
                5,
            )
            store.put("submission-attempt", {"schema": 1, "candidate_digest": bindings(frozen)["candidate_digest"]})
        return transport.submit(
            store,
            remote=args.remote,
            branch=args.branch,
            generator_invocation=args.generator_invocation,
            inputs=_inputs(store, args.config) if store.get("candidate") is None else None,
            synthetic=_synthetic(args.remote),
        )
    return transport.readback(
        store,
        remote=args.remote,
        branch=args.branch,
        expected_commit=args.expected_commit,
        reader_invocation=args.reader_invocation,
    )


def _synthetic(remote: str) -> bool:
    path = Path(remote)
    return path.is_absolute() and (path / "dscat-usage-synthetic").exists()


def _emit(message: str) -> None:
    sys.stdout.write(message + "\n")


def main(argv: list[str] | None = None) -> int:
    """Return the stable command exit code; diagnostics never reveal raw inputs."""
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except UsageError:
        if "--json" in (sys.argv[1:] if argv is None else argv):
            _emit(canonical(Status("failed").to_dict()).decode())
        else:
            _emit("invalid command arguments")
        return 2
    try:
        status = _run(args)
        code = 5 if status.status == "review_required" else 0
    except UsageError as exc:
        code = exc.code
        status = Status({3: "unavailable", 4: "conflict", 5: "review_required"}.get(code, "failed"))
        if not args.json_output:
            _emit(str(exc))
    except OSError:
        code, status = 3, Status("unavailable")
        if not args.json_output:
            _emit("local input or private state unavailable")
    if args.json_output:
        _emit(canonical(status.to_dict()).decode())
    else:
        _emit(status.status)
    return code
