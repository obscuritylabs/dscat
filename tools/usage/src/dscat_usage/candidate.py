"""Immutable complete-tree candidates from explicit captured private inputs.

Input paths refer to capture artifacts, not live histories. Appending a live
history therefore does not invalidate a frozen prefix observation. The caller
supplies the complete private input closure, including config, map and capture.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .importer import Config
from .ledger import MergeConflict, canonical_records, merge
from .metrics import Rate, validate_rates
from .private import StateStore, atomic_write, locked, read_bytes, safe_path
from .render import OWNED_PROJECTIONS, render
from .schema import (
    MAX_PATH,
    MAX_TOTAL,
    Candidate,
    Contribution,
    Ledger,
    UsageError,
    Vocabulary,
    canonical,
    digest,
    integer,
    keys,
    loads,
    present,
    require,
    sha,
    text,
)

METADATA = {
    "name": "Usage Dashboard",
    "email": "usage-dashboard@users.noreply.github.com",
    "message": "Update aggregate usage dashboard",
}
REQUIRED_INPUTS = frozenset({"config", "map", "capture", "contribution", "vocabulary", "rates"})
REMOTE_REF_FIELDS = 2
OWNED = OWNED_PROJECTIONS | {"usage-ledger.json"}


def instant(value: str) -> datetime:
    """Instant."""
    return datetime.fromisoformat(value).astimezone(UTC)


def git(
    repo: Path | None, *args: str, data: bytes | None = None, date: str | None = None, allow_failure: bool = False
) -> subprocess.CompletedProcess[bytes]:
    """Run Git without user configuration, hooks, prompts or inherited Git state."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_NAME": METADATA["name"],
            "GIT_AUTHOR_EMAIL": METADATA["email"],
            "GIT_COMMITTER_NAME": METADATA["name"],
            "GIT_COMMITTER_EMAIL": METADATA["email"],
        }
    )
    if date is not None:
        env.update({"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date})
    command = [
        "git",
        "-c",
        "core.hooksPath=" + os.devnull,
        "-c",
        "protocol.ext.allow=never",
        "-c",
        "protocol.file.allow=always",
        "-c",
        "credential.helper=",
        "-c",
        "commit.gpgSign=false",
    ]
    if repo is not None:
        command += ["--git-dir", str(repo)]
    try:
        result = subprocess.run(  # noqa: S603 - fixed Git executable, argument arrays and validated targets; no shell.
            [*command, *args],
            input=data,
            capture_output=True,
            env=env,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        message = "transport unavailable"
        raise UsageError(message, 6) from exc
    require(allow_failure or result.returncode == 0, "transport failed", 6)
    require(len(result.stdout) <= MAX_TOTAL, "transport output limit", 3)
    return result


def target(remote: str, branch: str, synthetic: bool) -> None:  # noqa: FBT001 - preserve the transport validation interface.
    """Validate an explicit transport target and branch."""
    require(
        isinstance(remote, str)
        and 0 < len(remote) <= MAX_PATH
        and not remote.startswith("-")
        and not any(c in remote for c in "\r\n\x00"),
        "invalid remote",
    )
    text(branch, r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*")
    if synthetic:
        path = safe_path(Path(remote))
        require(path.is_absolute() and path.is_dir(), "synthetic local remote required", 5)
        require(
            read_bytes(path / "dscat-usage-synthetic") == b"disposable synthetic remote\n",
            "synthetic local remote required",
            5,
        )
        require(git(path, "rev-parse", "--is-bare-repository").stdout == b"true\n", "synthetic bare remote required", 5)


def remote_head(repo: Path, remote: str, branch: str) -> str | None:
    """Read the exact remote branch identity."""
    result = git(repo, "ls-remote", "--heads", "--", remote, "refs/heads/" + branch)
    lines = result.stdout.splitlines()
    require(len(lines) <= 1, "remote identity unresolved", 6)
    if not lines:
        return None
    fields = lines[0].split(b"\t")
    require(
        len(fields) == REMOTE_REF_FIELDS and fields[1] == ("refs/heads/" + branch).encode(),
        "remote identity unresolved",
        6,
    )
    identity = fields[0].decode("ascii")
    text(identity, r"(?:[a-f0-9]{40}|[a-f0-9]{64})")
    return identity


def fetch(repo: Path, remote: str, branch: str) -> str | None:
    """Fetch the explicit remote parent into an isolated checkout."""
    head = remote_head(repo, remote, branch)
    if head is None:
        return None
    git(repo, "fetch", "--no-tags", "--", remote, "refs/heads/" + branch)
    fetched = git(repo, "rev-parse", "FETCH_HEAD").stdout.decode().strip()
    require(fetched == head, "remote changed during fetch; retry", 6)
    return head


def tree_files(repo: Path, revision: str | None) -> tuple[dict[str, bytes], dict[str, str]]:
    """Tree files."""
    files: dict[str, bytes] = {}
    modes: dict[str, str] = {}
    if revision is None:
        return files, modes
    listing = git(repo, "ls-tree", "-rz", "--full-tree", revision).stdout
    total = 0
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        header, path_bytes = entry.split(b"\t", 1)
        mode, kind, identity = header.split()
        try:
            path = path_bytes.decode("utf-8")
        except UnicodeError as exc:
            message = "unsupported outgoing path"
            raise UsageError(message, 3) from exc
        text(path, r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*")
        require(all(part not in {".", "..", ".git"} for part in path.split("/")), "unsafe outgoing path", 3)
        require(mode in {b"100644", b"100755"} and kind == b"blob", "unsupported outgoing file type", 3)
        size = int(git(repo, "cat-file", "-s", identity.decode()).stdout)
        require(size <= 64 * 1024 * 1024, "outgoing file limit", 3)
        total += size
        require(total <= MAX_TOTAL, "outgoing tree limit", 3)
        files[path] = git(repo, "cat-file", "blob", identity.decode()).stdout
        modes[path] = mode.decode()
    return files, modes


def tree_binding(files: dict[str, bytes], modes: dict[str, str]) -> str:
    """Tree binding."""
    require(files.keys() == modes.keys(), "tree modes mismatch", 3)
    return digest(
        canonical({name: {"mode": modes[name], "digest": digest(value)} for name, value in sorted(files.items())})
    )


def commit_identity(candidate: Candidate, files: dict[str, bytes], modes: dict[str, str]) -> str:
    """Recompute Git's SHA-1 tree/commit framing without writing any objects."""

    def object_hash(kind: str, data: bytes) -> bytes:
        """Object hash."""
        return hashlib.sha1(
            kind.encode() + b" " + str(len(data)).encode() + b"\0" + data, usedforsecurity=False
        ).digest()

    root: dict[str, Any] = {}
    for path, data in files.items():
        node = root
        parts = path.split("/")
        for part in parts[:-1]:
            child = node.setdefault(part, {})
            require(isinstance(child, dict), "outgoing path collision", 3)
            node = child
        require(parts[-1] not in node, "outgoing path collision", 3)
        node[parts[-1]] = (modes[path], object_hash("blob", data))

    def tree_hash(node: dict[str, Any]) -> bytes:
        """Tree hash."""
        entries = []
        for name, item in node.items():
            directory = isinstance(item, dict)
            mode, identity = ("40000", tree_hash(item)) if directory else item
            entries.append(
                ((name + ("/" if directory else "")).encode(), mode.encode() + b" " + name.encode() + b"\0" + identity)
            )
        return object_hash("tree", b"".join(data for _, data in sorted(entries)))

    tree = tree_hash(root).hex()
    parent = "" if candidate.parent is None else "parent " + candidate.parent + "\n"
    identity = (
        METADATA["name"]
        + " <"
        + METADATA["email"]
        + "> "
        + str(int(instant(candidate.created_at).timestamp()))
        + " +0000"
    )
    return object_hash(
        "commit",
        (
            "tree "
            + tree
            + "\n"
            + parent
            + "author "
            + identity
            + "\ncommitter "
            + identity
            + "\n\n"
            + METADATA["message"]
            + "\n"
        ).encode(),
    ).hex()


def build_commit(repo: Path, candidate: Candidate, files: dict[str, bytes], modes: dict[str, str]) -> str:
    """Build an index directly from blobs; no checkout, filters or source execution."""
    git(repo, "read-tree", "--empty")
    index = bytearray()
    for name, value in sorted(files.items()):
        blob = git(repo, "hash-object", "-w", "--stdin", data=value).stdout.strip()
        index.extend(modes[name].encode() + b" " + blob + b"\t" + name.encode() + b"\0")
    git(repo, "update-index", "-z", "--index-info", data=bytes(index))
    tree = git(repo, "write-tree").stdout.decode().strip()
    parents = [] if candidate.parent is None else ["-p", candidate.parent]
    return (
        git(repo, "commit-tree", tree, *parents, data=(METADATA["message"] + "\n").encode(), date=candidate.created_at)
        .stdout.decode()
        .strip()
    )


def _inputs(paths: dict[str, Path]) -> dict[str, bytes]:
    require(isinstance(paths, dict) and paths.keys() >= REQUIRED_INPUTS, "complete private input closure required")
    result = {}
    total = 0
    for label, path in paths.items():
        text(label)
        value = read_bytes(path, private=True)
        total += len(value)
        require(total <= MAX_TOTAL, "candidate input limit", 3)
        result[label] = value
    return result


def _models(inputs: dict[str, bytes]) -> tuple[Contribution, Vocabulary, tuple[Rate, ...], str]:
    vocabulary = Vocabulary.from_dict(loads(inputs["vocabulary"]))
    rate_data = loads(inputs["rates"])
    keys(rate_data, {"schema", "rates"})
    integer(rate_data["schema"], 1, 1)
    require(isinstance(rate_data["rates"], list))
    rates = tuple(Rate.from_dict(item, vocabulary) for item in rate_data["rates"])
    validate_rates(rates, vocabulary)
    contribution = Contribution.from_dict(loads(inputs["contribution"]), vocabulary)
    config = Config.from_dict(loads(inputs["config"]))
    # These path associations prevent substituting an unrelated reviewed map,
    # vocabulary or price inventory while claiming to bind a different config.
    require(config.schema == 1)
    map_value = loads(inputs["map"])
    require(isinstance(map_value, (dict, list)), "invalid private map")
    capture = loads(inputs["capture"])
    keys(capture, {"schema", "domain", "observed_at", "input_digests", "contribution_digest"})
    integer(capture["schema"], 1, 1)
    require(
        capture["domain"] == contribution.domain and capture["observed_at"] == contribution.observed_at,
        "capture binding mismatch",
        3,
    )
    require(capture["contribution_digest"] == digest(canonical(contribution.to_dict())), "capture binding mismatch", 3)
    require(
        isinstance(capture["input_digests"], dict) and bool(capture["input_digests"]), "capture provenance required", 3
    )
    for label, value in capture["input_digests"].items():
        require(isinstance(label, str) and 0 < len(label) <= MAX_PATH, "invalid private capture label")
        sha(value)
    return contribution, vocabulary, rates, contribution.observed_at


def _directory(store: StateStore, identity: str) -> Path:
    sha(identity)
    return safe_path(store.root / "candidates" / identity)


def load(
    store: StateStore, identity: str | None = None
) -> tuple[Candidate, dict[str, Any], dict[str, bytes], dict[str, bytes]]:
    """Load the frozen candidate and its verified private bundle."""
    pointer = store.get("candidate")
    pointer = present(pointer, "candidate unavailable", 3)
    candidate = (
        Candidate.from_dict(pointer)
        if identity is None
        else Candidate.from_dict(loads(read_bytes(_directory(store, identity) / "candidate.json", private=True)))
    )
    actual = digest(canonical(candidate.to_dict()))
    require(identity is None or identity == actual, "candidate identity mismatch", 3)
    directory = _directory(store, actual)
    require(
        read_bytes(directory / "candidate.json", private=True) == canonical(candidate.to_dict()), "candidate changed", 5
    )
    bundle = loads(read_bytes(directory / "bundle.json", private=True))
    keys(bundle, {"schema", "paths", "modes", "commit", "parent_files", "parent_modes"})
    integer(bundle["schema"], 1, 1)
    require(
        isinstance(bundle["paths"], dict) and set(bundle["paths"]) == candidate.inputs.keys() - {"transport"},
        "input closure changed",
        5,
    )
    require(isinstance(bundle["modes"], dict) and bundle["modes"].keys() == candidate.files.keys(), "tree changed", 5)
    for mode in bundle["modes"].values():
        require(mode in {"100644", "100755"}, "unsupported tree mode", 3)
    text(bundle["commit"], r"(?:[a-f0-9]{40}|[a-f0-9]{64})")
    files = {name: read_bytes(directory / "files" / name, private=True) for name in candidate.files}
    inputs = {name: read_bytes(directory / "inputs" / name, private=True) for name in candidate.inputs}
    expected = (
        {"candidate.json", "bundle.json"} | {"files/" + name for name in files} | {"inputs/" + name for name in inputs}
    )
    actual_paths = set()
    for path in directory.rglob("*"):
        safe_path(path)
        require(path.is_file() or path.is_dir(), "unsafe candidate file", 3)
        if path.is_file():
            actual_paths.add(path.relative_to(directory).as_posix())
    require(actual_paths == expected, "candidate file set changed", 5)
    return candidate, bundle, files, inputs


def validate(store: StateStore, identity: str | None = None, *, require_review: bool = False) -> Candidate:
    """Read-only validation; never fetch, repair, refresh or write pointers."""
    candidate, bundle, files, inputs = load(store, identity)
    candidate.validate()
    require({key: digest(value) for key, value in files.items()} == candidate.files, "candidate tree changed", 5)
    require({key: digest(value) for key, value in inputs.items()} == candidate.inputs, "candidate inputs changed", 5)
    require(
        inputs["transport"]
        == canonical({name: bundle[name] for name in ("paths", "modes", "parent_files", "parent_modes")}),
        "transport framing changed",
        5,
    )
    require(tree_binding(files, bundle["modes"]) == candidate.tree_digest, "candidate tree changed", 5)
    require(
        digest(canonical(candidate.inputs)) == candidate.input_digest
        and digest(canonical(candidate.metadata)) == candidate.metadata_digest,
        "candidate bindings changed",
        5,
    )
    for label, path in bundle["paths"].items():
        require(isinstance(path, str) and Path(path).is_absolute(), "invalid private input path", 3)
        require(digest(read_bytes(Path(path), private=True)) == candidate.inputs[label], "reviewed input changed", 5)
    config = Config.from_dict(loads(inputs["config"]))
    for label, path in (("map", config.map_path), ("rates", config.rates_path), ("vocabulary", config.vocabulary_path)):
        require(str(safe_path(path)) == bundle["paths"][label], "config input binding mismatch", 3)
    contribution, vocabulary, rates, measured = _models(inputs)
    require(
        contribution.contributor == store.manifest["contributor"]
        and contribution.domain == store.manifest["domain"] == candidate.domain,
        "state identity mismatch",
        4,
    )
    ledger = Ledger.from_dict(loads(files["usage-ledger.json"]), vocabulary)
    canonical_records(ledger, vocabulary)
    require(
        ledger.domain == candidate.domain
        and {c.contributor: c.generation for c in ledger.contributions} == candidate.generations,
        "ledger framing changed",
        5,
    )
    require(any(c.to_dict() == contribution.to_dict() for c in ledger.contributions), "pending contribution missing", 5)
    require(canonical(ledger.to_dict()) == files["usage-ledger.json"], "noncanonical transport ledger", 3)
    projections = render(ledger, vocabulary, rates=rates, measured_at=measured)
    require(all(files.get(name) == value for name, value in projections.items()), "projections changed", 5)
    require(
        isinstance(bundle["parent_files"], dict) and isinstance(bundle["parent_modes"], dict),
        "invalid parent framing",
        3,
    )
    for name, value in bundle["parent_files"].items():
        require(
            name in OWNED
            or (candidate.files.get(name) == value and bundle["modes"].get(name) == bundle["parent_modes"].get(name)),
            "unrelated page changed",
            5,
        )
    require(set(candidate.files) - set(bundle["parent_files"]) <= OWNED, "unowned file added", 5)
    require(commit_identity(candidate, files, bundle["modes"]) == bundle["commit"], "commit identity changed", 5)
    review = store.get("review")
    if require_review or (review is not None and "pending" not in review):
        from .review import checked_review  # noqa: PLC0415 - review imports candidate binding helpers.

        checked_review(store, candidate)
    return candidate


def prepare(  # noqa: PLR0913, PLR0915 - one locked freeze transaction with explicit immutable bindings.
    store: StateStore,
    *,
    remote: str,
    branch: str,
    generator_invocation: str,
    inputs: dict[str, Path],
    synthetic: bool = False,
) -> Candidate:
    """Fetch, merge and freeze; callers report review_required (exit 5)."""
    target(remote, branch, synthetic)
    text(generator_invocation)
    require("transport" not in inputs, "reserved input label")
    for parent in (store.root, *store.root.parents):
        require(not (parent / ".git").exists(), "private state nested in checkout", 3)
    with locked(store.root):
        raw = _inputs(inputs)
        contribution, vocabulary, rates, measured = _models(raw)
        manifest = store.manifest
        require(
            contribution.contributor == manifest["contributor"] and contribution.domain == manifest["domain"],
            "contribution state mismatch",
            4,
        )
        for label, path in inputs.items():
            inputs[label] = safe_path(path)
        config = Config.from_dict(loads(raw["config"]))
        require(
            all(
                inputs[label] == safe_path(path)
                for label, path in (
                    ("map", config.map_path),
                    ("rates", config.rates_path),
                    ("vocabulary", config.vocabulary_path),
                )
            ),
            "config input binding mismatch",
            3,
        )
        with tempfile.TemporaryDirectory(prefix="transport-", dir=store.root) as temporary:
            repo = Path(temporary) / "repo.git"
            git(None, "init", "--bare", str(repo))
            parent = fetch(repo, remote, branch)
            files, modes = tree_files(repo, parent)
            require(
                "usage-ledger.json" in files or not OWNED_PROJECTIONS.intersection(files),
                "legacy projection transition required",
                3,
            )
            parent_files, parent_modes = {name: digest(value) for name, value in files.items()}, modes.copy()
            previous = (
                Ledger.from_dict(loads(files["usage-ledger.json"]), vocabulary)
                if "usage-ledger.json" in files
                else None
            )
            try:
                ledger = merge(previous, contribution, vocabulary)
            except MergeConflict as exc:
                store.put_locked(
                    "quarantine", {"schema": 1, "receipts": list(exc.receipts), "count": len(exc.receipts)}
                )
                raise
            files.update(render(ledger, vocabulary, rates=rates, measured_at=measured))
            files["usage-ledger.json"] = canonical(ledger.to_dict())
            modes.update(dict.fromkeys(OWNED, "100644"))
            framing = {
                "paths": {label: str(path) for label, path in inputs.items()},
                "modes": modes,
                "parent_files": parent_files,
                "parent_modes": parent_modes,
            }
            raw["transport"] = canonical(framing)
            input_hashes = {label: digest(value) for label, value in raw.items()}
            created = datetime.now(UTC).replace(microsecond=0).isoformat()
            candidate = Candidate(
                ledger.domain,
                generator_invocation,
                created,
                parent,
                tree_binding(files, modes),
                digest(canonical(input_hashes)),
                digest(canonical(METADATA)),
                {name: digest(value) for name, value in files.items()},
                input_hashes,
                {c.contributor: c.generation for c in ledger.contributions},
                remote,
                branch,
                METADATA.copy(),
                synthetic,
            )
            candidate.validate()
            identity = digest(canonical(candidate.to_dict()))
            commit = build_commit(repo, candidate, files, modes)
            require(commit == commit_identity(candidate, files, modes), "commit framing mismatch", 3)
            bundle = {"schema": 1, **framing, "commit": commit}
            root = store.root / "candidates"
            safe_path(root, exists=False).mkdir(mode=0o700, exist_ok=True)
            final = root / identity
            # Revalidate even when an identical frozen bundle already exists.
            require(
                _inputs(inputs) == {name: value for name, value in raw.items() if name != "transport"},
                "input changed during preparation",
                5,
            )
            if final.exists():
                require(
                    read_bytes(final / "candidate.json", private=True) == canonical(candidate.to_dict()),
                    "candidate identity collision",
                    3,
                )
                store.put_many_locked({"candidate": candidate.to_dict(), "review": {"schema": 1, "pending": identity}})
                return candidate
            with tempfile.TemporaryDirectory(prefix="freeze-", dir=root) as frozen:
                directory = Path(frozen)
                payload = {
                    "candidate.json": canonical(candidate.to_dict()),
                    "bundle.json": canonical(bundle),
                    **{"inputs/" + name: value for name, value in raw.items()},
                    **{"files/" + name: value for name, value in files.items()},
                }
                for name, value in payload.items():
                    path = directory / name
                    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    atomic_write(path, value)
                # Recheck the supplied frozen inputs before committing the pointer.
                require(
                    _inputs(inputs) == {name: value for name, value in raw.items() if name != "transport"},
                    "input changed during preparation",
                    5,
                )
                directory.rename(final)
                directory.mkdir(mode=0o700)
            store.put_many_locked({"candidate": candidate.to_dict(), "review": {"schema": 1, "pending": identity}})
            return candidate
