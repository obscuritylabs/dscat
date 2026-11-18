"""Ordinary Git submission and separately evidenced fresh clone readback."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

from .candidate import (
    METADATA,
    _models,
    build_commit,
    fetch,
    git,
    load,
    prepare,
    remote_head,
    target,
    tree_binding,
    tree_files,
    validate,
)
from .ledger import canonical_records
from .private import StateStore, locked
from .render import render
from .review import bindings
from .schema import Candidate, Ledger, Status, UsageError, digest, loads, present, require, text


def _confirmed(repo: Path, candidate: Candidate, commit: str, files: dict[str, bytes], modes: dict[str, str]) -> bool:
    """Resolve even an ambiguous push by exact remote identity and object readback."""
    if remote_head(repo, candidate.remote, candidate.branch) != commit:
        return False
    fetched = fetch(repo, candidate.remote, candidate.branch)
    if fetched != commit:
        return False
    actual_files, actual_modes = tree_files(repo, commit)
    require(actual_files == files and actual_modes == modes, "remote tree identity mismatch", 6)
    verify_metadata(repo, commit, candidate)
    return True


def verify_metadata(repo: Path, commit: str, candidate: Candidate) -> None:
    """Validate generic commit metadata and the exact expected parent."""
    raw = git(repo, "cat-file", "commit", commit).stdout
    headers, message = raw.split(b"\n\n", 1)
    lines = headers.decode("utf-8").splitlines()
    parents = [line[7:] for line in lines if line.startswith("parent ")]
    require(parents == ([] if candidate.parent is None else [candidate.parent]), "remote ancestry mismatch", 6)
    expected_epoch = str(int(datetime.fromisoformat(candidate.created_at).timestamp()))
    identity = METADATA["name"] + " <" + METADATA["email"] + "> " + expected_epoch + " +0000"
    require(
        len(lines) == 3 + len(parents)
        and "author " + identity in lines
        and "committer " + identity in lines
        and message == (METADATA["message"] + "\n").encode(),
        "generic remote metadata mismatch",
        6,
    )


def submit(  # noqa: PLR0913 - Frozen transport command bindings remain explicit.
    store: StateStore,
    *,
    remote: str,
    branch: str,
    generator_invocation: str,
    inputs: dict[str, Path] | None = None,
    synthetic: bool = False,
) -> Status:
    """Prepare or push a reviewed candidate; stale parents create a new review gate."""
    if store.get("candidate") is None:
        inputs = present(inputs, "complete private input closure required", 2)
        candidate = prepare(
            store,
            remote=remote,
            branch=branch,
            generator_invocation=generator_invocation,
            inputs=inputs,
            synthetic=synthetic,
        )
        return Status("review_required", candidate_digest=bindings(candidate)["candidate_digest"])
    stale_inputs: dict[str, Path] | None = None
    with locked(store.root):
        candidate = validate(store, require_review=True)
        require(
            (remote, branch, generator_invocation, synthetic)
            == (candidate.remote, candidate.branch, candidate.generator_invocation, candidate.synthetic),
            "frozen transport binding mismatch",
            5,
        )
        target(remote, branch, synthetic)
        candidate, bundle, files, _frozen = load(store)
        with tempfile.TemporaryDirectory(prefix="submit-", dir=store.root) as temporary:
            repo = Path(temporary) / "repo.git"
            git(None, "init", "--bare", str(repo))
            current = fetch(repo, remote, branch)
            # Idempotent retry after an acknowledged or ambiguous successful push.
            if current is not None and current == bundle["commit"]:
                require(_confirmed(repo, candidate, current, files, bundle["modes"]), "remote identity unresolved", 6)
                validate(store, require_review=True)
                store.put_locked(
                    "accepted",
                    {"schema": 1, "candidate_digest": bindings(candidate)["candidate_digest"], "commit": current},
                )
                return Status(
                    "submitted", candidate_digest=bindings(candidate)["candidate_digest"], remote_commit=current
                )
            if current != candidate.parent:
                stale_inputs = {label: Path(path) for label, path in bundle["paths"].items()}
            else:
                old_files, old_modes = tree_files(repo, current)
                require(
                    {name: digest(value) for name, value in old_files.items()} == bundle["parent_files"]
                    and old_modes == bundle["parent_modes"],
                    "parent tree changed",
                    5,
                )
                commit = build_commit(repo, candidate, files, bundle["modes"])
                require(commit == bundle["commit"], "commit identity changed", 5)
                # Last operation before push revalidates every frozen input/tree/review.
                validate(store, require_review=True)
                git(repo, "push", "--porcelain", "--", remote, commit + ":refs/heads/" + branch, allow_failure=True)
                if not _confirmed(repo, candidate, commit, files, bundle["modes"]):
                    # A race after the preflight fetch is also a stale-parent case.
                    head = remote_head(repo, remote, branch)
                    if head is not None and head != candidate.parent:
                        stale_inputs = {label: Path(path) for label, path in bundle["paths"].items()}
                    else:
                        reason = "submission unconfirmed; accepted state preserved"
                        raise UsageError(reason, 6)
                else:
                    validate(store, require_review=True)
                    store.put_locked(
                        "accepted",
                        {"schema": 1, "candidate_digest": bindings(candidate)["candidate_digest"], "commit": commit},
                    )
                    return Status(
                        "submitted", candidate_digest=bindings(candidate)["candidate_digest"], remote_commit=commit
                    )
    require(stale_inputs is not None, "remote identity unresolved", 6)
    new = prepare(
        store,
        remote=remote,
        branch=branch,
        generator_invocation=generator_invocation,
        inputs=stale_inputs,
        synthetic=synthetic,
    )
    return Status("review_required", candidate_digest=bindings(new)["candidate_digest"])


def readback(store: StateStore, *, remote: str, branch: str, expected_commit: str, reader_invocation: str) -> Status:
    """Separate invocation clones actual published objects and validates all content.

    The orchestration coordinator establishes reader freshness. Invocation bindings
    enforce separation here, but cannot cryptographically prove process independence.
    """
    text(reader_invocation)
    text(expected_commit, r"(?:[a-f0-9]{40}|[a-f0-9]{64})")
    with locked(store.root):
        candidate = validate(store, require_review=True)
        accepted = store.get("accepted")
        require(
            accepted is not None
            and accepted.get("commit") == expected_commit
            and accepted.get("candidate_digest") == bindings(candidate)["candidate_digest"],
            "submitted identity unavailable",
            6,
        )
        require(remote == candidate.remote and branch == candidate.branch, "readback target mismatch", 6)
        review = present(store.get("review"), "independent review required", 5)
        require(
            reader_invocation not in {candidate.generator_invocation, review["attestation"]["reviewer_invocation"]},
            "separate readback invocation required",
            5,
        )
        target(remote, branch, candidate.synthetic)
        candidate, bundle, files, frozen = load(store)
        with tempfile.TemporaryDirectory(prefix="readback-") as temporary:
            repo = Path(temporary) / "readback.git"
            git(None, "clone", "--bare", "--no-local", "--single-branch", "--branch", branch, "--", remote, str(repo))
            require(
                remote_head(repo, remote, branch) == expected_commit
                and git(repo, "rev-parse", "refs/heads/" + branch).stdout.decode().strip() == expected_commit,
                "published identity changed",
                6,
            )
            actual, modes = tree_files(repo, expected_commit)
            require(
                actual == files and modes == bundle["modes"] and tree_binding(actual, modes) == candidate.tree_digest,
                "readback tree mismatch",
                6,
            )
            verify_metadata(repo, expected_commit, candidate)
            _contribution, vocabulary, rates, measured = _models(frozen)
            ledger = Ledger.from_dict(loads(actual["usage-ledger.json"]), vocabulary)
            canonical_records(ledger, vocabulary)
            require(
                all(
                    actual.get(name) == data
                    for name, data in render(ledger, vocabulary, rates=rates, measured_at=measured).items()
                ),
                "readback projection mismatch",
                6,
            )
            if candidate.parent is not None:
                git(repo, "merge-base", "--is-ancestor", candidate.parent, expected_commit)
            # Capture remote advancement during clone/validation conservatively.
            require(remote_head(repo, remote, branch) == expected_commit, "published identity changed", 6)
        store.put_locked(
            "remote_verified",
            {
                "schema": 1,
                "candidate_digest": bindings(candidate)["candidate_digest"],
                "commit": expected_commit,
                "reader_invocation": reader_invocation,
                "verified_at": datetime.now(UTC).isoformat(),
            },
        )
        return Status(
            "remote_verified", candidate_digest=bindings(candidate)["candidate_digest"], remote_commit=expected_commit
        )
