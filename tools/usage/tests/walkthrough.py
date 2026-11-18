"""Offline installed-package walkthrough, using fabricated synthetic reviews only.

Never imports checkout source. Every remote and secret is temporary; generated
review evidence is not an actual fresh independent review.
"""

from __future__ import annotations

import contextlib
import copy
import io
import shutil
import sqlite3
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dscat_usage import candidate
from dscat_usage.cli import main
from dscat_usage.ledger import canonical_records
from dscat_usage.private import StateStore, atomic_write, read_bytes
from dscat_usage.review import bindings
from dscat_usage.schema import Attestation, Ledger, ReviewEvidence, Vocabulary, canonical, digest, loads

EXPECTED_PROMOTED = 3
EXPECTED_RESPONSES = 4


def _emit(message: str) -> None:
    sys.stdout.write(message + "\n")


FIXTURES = Path(__file__).parent / "fixtures"


def run(*args: object, expected: int = 0) -> dict[str, Any]:
    """Execute the actual CLI and assert its strict status and stable exit code."""
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = main([*(str(arg) for arg in args), "--json"])
    result = loads(output.getvalue().encode())
    if code != expected:
        main([str(arg) for arg in args])
        raise RuntimeError("walkthrough CLI expectation failed: " + str(result))
    return result


def synthetic_review(store: StateStore, directory: Path) -> tuple[Path, Path]:
    """Fabricated test-only provenance; never use for actual publication."""
    frozen = candidate.validate(store)
    now = datetime.now(UTC).isoformat()
    evidence = ReviewEvidence(
        "TASK-001",
        frozen.generator_invocation,
        "synthetic-reviewer",
        **bindings(frozen),
        timestamp=now,
        disposition="PASS",
        synthetic=True,
    )
    envelope = {
        "schema": 1,
        "synthetic": True,
        "review": evidence.to_dict(),
        "dispatch": {
            "event": "fresh-dispatch",
            "tool": "collaboration.spawn_agent",
            "coordinator_invocation": "synthetic-coordinator",
            "task": evidence.task,
            "generator_invocation": evidence.generator_invocation,
            "reviewer_invocation": evidence.reviewer_invocation,
            "fork_turns": "none",
            "candidate_digest": evidence.candidate_digest,
            "timestamp": frozen.created_at,
            "record_digest": digest(b"synthetic dispatch"),
        },
        "return": {
            "event": "fresh-return",
            "tool": "collaboration.final_answer",
            "task": evidence.task,
            "reviewer_invocation": evidence.reviewer_invocation,
            "candidate_digest": evidence.candidate_digest,
            "disposition": "PASS",
            "scope": "complete-candidate",
            "timestamp": now,
            "record_digest": digest(b"synthetic return"),
        },
    }
    attestation = Attestation(**evidence.to_dict(), execution_evidence_digest=digest(canonical(envelope)))
    attestation_path, evidence_path = directory / "attestation.json", directory / "execution.json"
    atomic_write(attestation_path, canonical(attestation.to_dict()))
    atomic_write(evidence_path, canonical(envelope))
    return attestation_path, evidence_path


def review(state: Path, directory: Path) -> None:
    """Feed the explicitly synthetic fixture through the public review command."""
    attestation, evidence = synthetic_review(StateStore(state), directory)
    run("review", "--state", state, "--attestation", attestation, "--execution-evidence", evidence)


def native_source(root: Path, project: str, *, thread: str, closed: bool) -> Path:
    """Write supported native token-count events, with optional open turn."""
    sessions = root / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    records = [loads(line) for line in read_bytes(FIXTURES / "native-token-count-v1.jsonl").splitlines()]
    records[0]["payload"].update(id=thread, cwd=project)
    if not closed:
        records.pop()
    path = sessions / (thread + ".jsonl")
    atomic_write(path, b"".join(canonical(row) + b"\n" for row in records))
    return path


def computer(root: Path, secret: Path, number: int) -> tuple[Path, Path, Path]:
    """Create an independently configured synthetic computer."""
    private = root / ("computer-" + str(number))
    private.mkdir(mode=0o700)
    state, config = private / "state", private / "config.json"
    run("setup", "--state", state, "--config", config, "--secret-file", secret)
    value = loads(read_bytes(config))
    source = private / "history"
    source.mkdir()
    for name, statements in (
        (
            "state_5.sqlite",
            (
                "CREATE TABLE threads(id TEXT,cwd TEXT)",
                "CREATE TABLE thread_spawn_edges(parent_thread_id TEXT,child_thread_id TEXT)",
            ),
        ),
        ("thread_history_1.sqlite", ("CREATE TABLE thread_turns(thread_id TEXT,turn_id TEXT)",)),
    ):
        with contextlib.closing(sqlite3.connect(source / name)) as connection:
            for statement in statements:
                connection.execute(statement)
            connection.commit()
    value.update(source_root=str(source), project_selector="/synthetic/project")
    atomic_write(config, canonical(value))
    vocabulary = {
        "schema": 1,
        "models": ["synthetic-model"],
        "providers": ["synthetic-provider"],
        "efforts": [],
        "tiers": [],
        "rtm": ["FR-001", "NFR-006"],
        "tasks": ["TASK-001"],
        "features": [],
    }
    atomic_write(state / "vocabulary.json", canonical(vocabulary))
    return state, config, source


def publish(state: Path, config: Path, remote: Path, invocation: str) -> str:
    """Prepare, synthetic-review, ordinary push and separate clone readback."""
    common = (
        "--state",
        state,
        "--config",
        config,
        "--remote",
        remote,
        "--branch",
        "dashboard",
        "--generator-invocation",
        invocation,
    )
    prepared = run("contribute", *common, expected=5)
    run("check", "--state", state, "--candidate", prepared["candidate_digest"])
    run("update", *common, expected=5)
    review(state, state.parent)
    submitted = run("update", *common)
    commit = submitted["remote_commit"]
    run(
        "readback",
        "--state",
        state,
        "--remote",
        remote,
        "--branch",
        "dashboard",
        "--expected-commit",
        commit,
        "--reader-invocation",
        "synthetic-reader",
    )
    return commit


def migrate_legacy(root: Path, secret: Path) -> None:
    """Archive and associate an explicit supported legacy-format fixture."""
    state, config, source = computer(root, secret, 3)
    legacy = root / "legacy"
    legacy.mkdir(mode=0o700)
    for path in (FIXTURES / "legacy-v1").iterdir():
        atomic_write(legacy / path.name, read_bytes(path))
    paths = {name: root / name for name in ("phase-map-v1.json", "registry-v1.json", "identity-map-v1.json")}
    for name, path in paths.items():
        atomic_write(path, read_bytes(FIXTURES / name))
    original = {path: read_bytes(path) for path in legacy.iterdir()}
    # These fixtures bind the explicit token_usage_record native response ID.
    account = loads(read_bytes(legacy / "accounting.json"))
    records = [
        {
            "type": "session_meta",
            "payload": {"id": "native-thread", "cwd": "/synthetic/project", "parent_thread_id": None},
        },
        {
            "type": "event_msg",
            "timestamp": account["turns"][0]["start"],
            "payload": {"type": "task_started", "turn_id": "native-turn"},
        },
        {
            "type": "token_usage_record",
            "timestamp": account["responses"][0]["timestamp"],
            "payload": {
                "turn_id": "native-turn",
                "response_id": "native-response",
                "usage": account["responses"][0]["usage"],
                "model": "synthetic-model",
                "model_provider": "synthetic-provider",
            },
        },
        {
            "type": "event_msg",
            "timestamp": account["turns"][0]["end"],
            "payload": {"type": "task_complete", "turn_id": "native-turn"},
        },
    ]
    (source / "sessions").mkdir()
    atomic_write(source / "sessions" / "legacy.jsonl", b"".join(canonical(row) + b"\n" for row in records))
    common = (
        "--state",
        state,
        "--config",
        config,
        "--snapshot",
        legacy,
        "--phase-map",
        paths["phase-map-v1.json"],
        "--registry",
        paths["registry-v1.json"],
    )
    historical = run("migrate", *common)
    if (
        historical["counts"]["migrated"] != 0
        or StateStore(state).get("migration")["legacy_additivity"] != "historical-nonadditive"
    ):
        reason = "legacy archive boundary failed"
        raise RuntimeError(reason)
    promoted = run("migrate", *common, "--identity-map", paths["identity-map-v1.json"])
    replay = run("migrate", *common, "--identity-map", paths["identity-map-v1.json"])
    if (
        promoted["counts"]["migrated"] != EXPECTED_PROMOTED
        or replay != promoted
        or any(read_bytes(path) != raw for path, raw in original.items())
    ):
        reason = "legacy preservation/promotion failed"
        raise RuntimeError(reason)
    run("refresh", "--state", state, "--config", config)


def walkthrough() -> None:  # noqa: PLR0915 - explicit sequential end-to-end acceptance scenario.
    """Run disposable two-computer native ingestion and failure preservation."""
    with tempfile.TemporaryDirectory(prefix="usage-walkthrough-") as temporary:
        root = Path(temporary)
        secret = root / "secret.bin"
        atomic_write(secret, bytes(range(32)))
        remote = root / "remote.git"
        candidate.git(None, "init", "--bare", str(remote))
        atomic_write(remote / "dscat-usage-synthetic", b"disposable synthetic remote\n")
        seed = root / "seed"
        candidate.git(None, "init", str(seed))
        atomic_write(seed / "Unrelated.md", b"Synthetic unrelated page.\n")
        candidate.git(seed / ".git", "--work-tree", str(seed), "add", "Unrelated.md")
        candidate.git(
            seed / ".git",
            "-c",
            "user.name=Synthetic",
            "-c",
            "user.email=synthetic@example.invalid",
            "commit",
            "-m",
            "Synthetic seed",
        )
        candidate.git(seed / ".git", "push", str(remote), "HEAD:refs/heads/dashboard")
        first, config1, source1 = computer(root, secret, 1)
        second, config2, source2 = computer(root, secret, 2)
        native_source(source1, "/synthetic/project", thread="thread-one", closed=False)
        native_source(source2, "/synthetic/project", thread="thread-two", closed=True)
        entry = first.parent / "entry.json"
        atomic_write(
            entry,
            canonical(
                {
                    "schema": 1,
                    "level": "thread",
                    "id": "thread-one",
                    "reviewed": True,
                    "evidence": "synthetic-dispatch",
                    "primary": "NFR-006",
                    "phase": "implementation",
                    "task": "TASK-001",
                }
            ),
        )
        run("map", "--state", first, "--config", config1, "--entry", entry)
        for state, config in ((first, config1), (second, config2)):
            run("refresh", "--state", state, "--config", config)
        # Prepare both against the same parent to exercise stale-parent remerge.
        common2 = (
            "--state",
            second,
            "--config",
            config2,
            "--remote",
            remote,
            "--branch",
            "dashboard",
            "--generator-invocation",
            "generator-two",
        )
        run("contribute", *common2, expected=5)
        review(second, second.parent)
        publish(first, config1, remote, "generator-one")
        run("update", *common2, expected=5)
        run("update", *common2, expected=5)
        review(second, second.parent)
        submitted = run("update", *common2)
        run(
            "readback",
            "--state",
            second,
            "--remote",
            remote,
            "--branch",
            "dashboard",
            "--expected-commit",
            submitted["remote_commit"],
            "--reader-invocation",
            "synthetic-reader",
        )
        # Copied history has identical receipts; open-to-closed refinement counts once.
        native_source(source1, "/synthetic/project", thread="thread-one", closed=True)
        shutil.copy2(source2 / "sessions" / "thread-two.jsonl", source1 / "sessions" / "thread-two.jsonl")
        run("refresh", "--state", first, "--config", config1)
        commit = publish(first, config1, remote, "generator-three")
        _, _, files, _ = candidate.load(StateStore(first))
        vocabulary = Vocabulary.from_dict(loads(read_bytes(first / "vocabulary.json")))
        ledger = Ledger.from_dict(loads(files["usage-ledger.json"]), vocabulary)

        responses = sum(row.kind == "response" for row in canonical_records(ledger, vocabulary))
        if responses != EXPECTED_RESPONSES or files["Unrelated.md"] != b"Synthetic unrelated page.\n":
            reason = "deduplication or unrelated preservation failed"
            raise RuntimeError(reason)
        accepted = copy.deepcopy(StateStore(first).get("accepted"))
        # Conflicting observation cannot replace accepted remote state.
        path = source1 / "sessions" / "thread-two.jsonl"
        rows = [loads(line) for line in read_bytes(path).splitlines()]
        for row in rows[3:5]:
            row["payload"]["info"]["last_token_usage"].update(input_tokens=11, total_tokens=16)
        atomic_write(path, b"".join(canonical(row) + b"\n" for row in rows))
        run("refresh", "--state", first, "--config", config1)
        run(
            "contribute",
            "--state",
            first,
            "--config",
            config1,
            "--remote",
            remote,
            "--branch",
            "dashboard",
            "--generator-invocation",
            "generator-conflict",
            expected=4,
        )
        if (
            StateStore(first).get("accepted") != accepted
            or candidate.remote_head(remote, str(remote), "dashboard") != commit
        ):
            reason = "failure preservation failed"
            raise RuntimeError(reason)
        migrate_legacy(root, secret)
        _emit(
            "PASS: synthetic native ingestion, two computers, stale review, "
            "overlap, closure, migration and preservation"
        )
        _emit("Canonical responses: 4; accepted commit: " + commit)
        _emit("Review fixtures are synthetic only; actual independent review remains a procedural prerequisite.")


if __name__ == "__main__":
    walkthrough()
