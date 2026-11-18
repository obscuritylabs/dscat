"""Disposable local Git tests; synthetic reviews do not claim independence."""

from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    import subprocess
    from collections.abc import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dscat_usage import candidate as candidates
from dscat_usage import transport
from dscat_usage.candidate import load, prepare, validate
from dscat_usage.identity import domain, receipt
from dscat_usage.ledger import contribution_digest
from dscat_usage.private import StateStore, atomic_write, read_bytes
from dscat_usage.review import bindings, validate_review
from dscat_usage.schema import (
    Attestation,
    Candidate,
    Contribution,
    Observation,
    ReviewEvidence,
    Status,
    UsageError,
    canonical,
    digest,
    loads,
)

DOMAIN = domain(bytes(range(32)))
VOCAB = {"schema": 1, **{key: [] for key in ("models", "providers", "efforts", "tiers", "rtm", "tasks", "features")}}


def synthetic_review(store: StateStore, directory: Path) -> tuple[Path, Path]:
    """Fixture only: fabricated provenance allowed solely by marked test remotes."""
    candidate = validate(store)
    now = datetime.now(UTC).isoformat()
    evidence = ReviewEvidence(
        "TASK-001",
        candidate.generator_invocation,
        "synthetic-reviewer",
        **bindings(candidate),
        timestamp=now,
        disposition="PASS",
        synthetic=True,
    )
    execution = {
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
            "timestamp": candidate.created_at,
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
    attestation = Attestation(**evidence.to_dict(), execution_evidence_digest=digest(canonical(execution)))
    attestation_path, execution_path = directory / "attestation.json", directory / "execution.json"
    atomic_write(attestation_path, canonical(attestation.to_dict()))
    atomic_write(execution_path, canonical(execution))
    return attestation_path, execution_path


class TransportTests(unittest.TestCase):
    """Transporttests."""

    def setUp(self) -> None:
        """Create a disposable state and local Git remote."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.remote = self.root / "remote.git"
        candidates.git(None, "init", "--bare", str(self.remote))
        (self.remote / "dscat-usage-synthetic").write_bytes(b"disposable synthetic remote\n")
        self.store, self.inputs = self.state("one")

    def state(self, name: str) -> tuple[StateStore, dict[str, Path]]:
        """State."""
        base = self.root / name
        base.mkdir()
        store = StateStore.create(base / "state", DOMAIN)
        inputs = {label: base / (label + ".json") for label in candidates.REQUIRED_INPUTS}
        config = {
            "schema": 1,
            "source_root": str(base / "histories"),
            "project_selector": str(base / "project"),
            "map_path": str(inputs["map"]),
            "rates_path": str(inputs["rates"]),
            "vocabulary_path": str(inputs["vocabulary"]),
            "secret_file": str(base / "secret"),
            "limits": {"file_bytes": 67108864, "total_bytes": 536870912, "records": 1000000, "diagnostics": 100},
        }
        for label, value in (
            ("config", config),
            ("map", {"schema": 1, "entries": []}),
            ("vocabulary", VOCAB),
            ("rates", {"schema": 1, "rates": []}),
        ):
            atomic_write(inputs[label], canonical(value))
        thread = receipt(bytes(range(32)), "thread", name)
        contribution = Contribution(
            DOMAIN,
            store.manifest["contributor"],
            1,
            None,
            "2026-01-01T00:00:00Z",
            (Observation("thread", thread, thread),),
        )
        self.write_contribution(inputs, contribution)
        return store, inputs

    def write_contribution(self, inputs: dict[str, Path], contribution: Contribution) -> None:
        """Write contribution."""
        atomic_write(inputs["contribution"], canonical(contribution.to_dict()))
        atomic_write(
            inputs["capture"],
            canonical(
                {
                    "schema": 1,
                    "domain": DOMAIN,
                    "observed_at": contribution.observed_at,
                    "input_digests": {"synthetic-prefix": digest(b"synthetic captured prefix")},
                    "contribution_digest": digest(canonical(contribution.to_dict())),
                }
            ),
        )

    def prepare(self, store: StateStore | None = None, inputs: dict[str, Path] | None = None) -> Candidate:
        """Prepare."""
        return prepare(
            store or self.store,
            remote=str(self.remote),
            branch="dashboard",
            generator_invocation="synthetic-generator",
            inputs=inputs or self.inputs,
            synthetic=True,
        )

    def review(self, store: StateStore | None = None) -> None:
        """Review."""
        store = store or self.store
        attestation, execution = synthetic_review(store, store.root.parent)
        validate_review(store, attestation=attestation, execution_evidence=execution)

    def submit(self, store: StateStore | None = None) -> Status:
        """Submit."""
        return transport.submit(
            store or self.store,
            remote=str(self.remote),
            branch="dashboard",
            generator_invocation="synthetic-generator",
            synthetic=True,
        )

    def error(self, code: int, function: Callable[..., object], *args: object, **kwargs: object) -> None:
        """Error."""
        with self.assertRaises(UsageError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def publish(self, store: StateStore | None = None, inputs: dict[str, Path] | None = None) -> Status:
        """Publish."""
        self.prepare(store, inputs)
        self.review(store)
        return self.submit(store)

    def test_prepare_check_review_submit_separate_readback(self) -> None:
        """Test prepare check review submit separate readback."""
        candidate = self.prepare()
        before = read_bytes(self.store.root / "manifest.json")
        self.assertEqual(validate(self.store), candidate)
        self.assertEqual(read_bytes(self.store.root / "manifest.json"), before)
        self.assertIsNone(self.store.get("accepted"))
        self.error(5, self.submit)
        self.review()
        result = self.submit()
        self.assertEqual(result.status, "submitted")
        self.assertIsNone(self.store.get("remote_verified"))
        self.error(
            5,
            transport.readback,
            self.store,
            remote=str(self.remote),
            branch="dashboard",
            expected_commit=result.remote_commit,
            reader_invocation="synthetic-generator",
        )
        self.error(
            5,
            transport.readback,
            self.store,
            remote=str(self.remote),
            branch="dashboard",
            expected_commit=result.remote_commit,
            reader_invocation="synthetic-reviewer",
        )
        verified = transport.readback(
            self.store,
            remote=str(self.remote),
            branch="dashboard",
            expected_commit=result.remote_commit,
            reader_invocation="synthetic-reader",
        )
        self.assertEqual(verified.status, "remote_verified")
        self.assertEqual(self.submit().remote_commit, result.remote_commit)

    def test_update_without_candidate_prepares_only(self) -> None:
        """Test update without candidate prepares only."""
        result = transport.submit(
            self.store,
            remote=str(self.remote),
            branch="dashboard",
            generator_invocation="synthetic-generator",
            inputs=self.inputs,
            synthetic=True,
        )
        self.assertEqual(result.status, "review_required")
        self.assertIsNone(candidates.remote_head(self.remote, str(self.remote), "dashboard"))

    def test_complete_tree_and_unrelated_executable_preserved(self) -> None:
        """Test complete tree and unrelated executable preserved."""
        blob = candidates.git(
            self.remote, "hash-object", "-w", "--stdin", data=b"unrelated synthetic page\n"
        ).stdout.strip()
        candidates.git(self.remote, "update-index", "--add", "--cacheinfo", "100755," + blob.decode() + ",Other.md")
        tree = candidates.git(self.remote, "write-tree").stdout.strip().decode()
        parent = (
            candidates.git(self.remote, "commit-tree", tree, data=b"Synthetic seed\n", date="2026-01-01T00:00:00Z")
            .stdout.strip()
            .decode()
        )
        candidates.git(self.remote, "update-ref", "refs/heads/dashboard", parent)
        candidate = self.prepare()
        self.assertIn("Other.md", candidate.files)
        self.review()
        result = self.submit()
        files, modes = candidates.tree_files(self.remote, result.remote_commit)
        self.assertEqual(files["Other.md"], b"unrelated synthetic page\n")
        self.assertEqual(modes["Other.md"], "100755")

    def test_disjoint_stale_parent_requires_new_review(self) -> None:
        """Test disjoint stale parent requires new review."""
        second, second_inputs = self.state("two")
        old = self.prepare()
        old_id = bindings(old)["candidate_digest"]
        self.review()
        self.publish(second, second_inputs)
        result = self.submit()
        self.assertEqual(result.status, "review_required")
        self.assertNotEqual(result.candidate_digest, old_id)
        self.assertTrue((self.store.root / "candidates" / old_id).is_dir())
        self.assertIsNone(self.store.get("accepted"))
        self.assertEqual(len(load(self.store)[0].generations), 2)
        self.error(5, self.submit)
        self.review()
        submitted = self.submit()
        self.assertEqual(submitted.status, "submitted")

    def test_rejected_push_preserves_accepted_pointer(self) -> None:
        """Test rejected push preserves accepted pointer."""
        accepted = self.publish()
        old = Contribution.from_dict(candidates.loads(read_bytes(self.inputs["contribution"])))
        updated = replace(old, generation=2, predecessor=contribution_digest(old), observed_at="2026-01-02T00:00:00Z")
        self.write_contribution(self.inputs, updated)
        self.prepare()
        self.review()
        original = transport.git

        def reject(repo: Path | None, *args: str, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            """Reject."""
            if args and args[0] == "push":
                return original(repo, "rev-parse", "--verify", "refs/heads/absent", allow_failure=True)
            return original(repo, *args, **kwargs)

        with patch.object(transport, "git", side_effect=reject):
            self.error(6, self.submit)
        self.assertEqual(self.store.get("accepted")["commit"], accepted.remote_commit)

    def test_ambiguous_success_is_confirmed_without_force(self) -> None:
        """Test ambiguous success is confirmed without force."""
        self.prepare()
        self.review()
        original = transport.git
        pushes = []

        def ambiguous(repo: Path | None, *args: str, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            """Ambiguous."""
            result = original(repo, *args, **kwargs)
            if args and args[0] == "push":
                pushes.append(args)
                result.returncode = 1
            return result

        with patch.object(transport, "git", side_effect=ambiguous):
            result = self.submit()
        self.assertEqual(result.status, "submitted")
        self.assertEqual(len(pushes), 1)
        self.assertFalse(any("force" in arg or arg.startswith("+") for arg in pushes[0]))

    def test_unresolved_push_identity_preserves_pointer(self) -> None:
        """Test unresolved push identity preserves pointer."""
        self.prepare()
        self.review()
        with patch.object(transport, "_confirmed", side_effect=UsageError("remote identity unresolved", 6)):
            self.error(6, self.submit)
        self.assertIsNone(self.store.get("accepted"))
        self.assertEqual(self.submit().status, "submitted")

    def test_changed_tree_input_metadata_and_transport_frame(self) -> None:
        """Test changed tree input metadata and transport frame."""
        for mutation in ("tree", "input", "metadata", "framing", "extra"):
            with self.subTest(mutation=mutation):
                store, inputs = self.state("mutate-" + mutation)
                candidate = self.prepare(store, inputs)
                self.review(store)
                directory = store.root / "candidates" / bindings(candidate)["candidate_digest"]
                if mutation == "tree":
                    atomic_write(directory / "files" / "Usage.md", b"changed\n")
                elif mutation == "input":
                    atomic_write(inputs["map"], canonical({"schema": 1, "entries": [], "changed": True}))
                elif mutation == "metadata":
                    value = candidate.to_dict()
                    value["metadata"]["message"] = "changed"
                    atomic_write(directory / "candidate.json", canonical(value))
                elif mutation == "framing":
                    value = loads(read_bytes(directory / "bundle.json"))
                    value["parent_modes"]["new"] = "100644"
                    atomic_write(directory / "bundle.json", canonical(value))
                else:
                    atomic_write(directory / "files" / "Extra.md", b"changed\n")
                self.error(5, self.submit, store)
                self.assertIsNone(store.get("accepted"))

    def test_review_provenance_negative_cases(self) -> None:
        """Test review provenance negative cases."""
        self.prepare()
        attestation, execution = synthetic_review(self.store, self.root)

        original = loads(read_bytes(execution))
        for mutation in (
            "same",
            "scope",
            "candidate",
            "parent",
            "metadata",
            "before",
            "fork",
            "return",
            "coordinator",
            "synthetic",
            "unknown",
            "bare",
        ):
            with self.subTest(mutation=mutation):
                value = copy.deepcopy(original)
                if mutation == "bare":
                    value = value["review"]
                elif mutation == "unknown":
                    value["extra"] = True
                else:
                    replacements = {
                        "same": ("review", "reviewer_invocation", "synthetic-generator"),
                        "scope": ("review", "scope", "changed-files"),
                        "candidate": ("review", "candidate_digest", "a" * 64),
                        "metadata": ("review", "metadata_digest", "a" * 64),
                        "parent": ("review", "parent", "a" * 40),
                        "before": ("dispatch", "timestamp", "2000-01-01T00:00:00Z"),
                        "fork": ("dispatch", "fork_turns", "all"),
                        "return": ("return", "disposition", "FAIL"),
                        "coordinator": ("dispatch", "coordinator_invocation", "synthetic-generator"),
                    }
                    if mutation == "synthetic":
                        value["synthetic"] = False
                    else:
                        section, key, replacement = replacements[mutation]
                        value[section][key] = replacement
                atomic_write(execution, canonical(value))
                with self.assertRaises(UsageError):
                    validate_review(self.store, attestation=attestation, execution_evidence=execution)
        atomic_write(execution, canonical(original))
        validate_review(self.store, attestation=attestation, execution_evidence=execution)

    def test_mutation_immediately_before_push_blocks_transport(self) -> None:
        """Test mutation immediately before push blocks transport."""
        self.prepare()
        self.review()
        original = transport.build_commit

        def mutate(*args: object, **kwargs: object) -> str:
            """Mutate."""
            result = original(*args, **kwargs)
            atomic_write(self.inputs["rates"], canonical({"schema": 1, "rates": [], "changed": True}))
            return result

        with patch.object(transport, "build_commit", side_effect=mutate):
            self.error(5, self.submit)
        self.assertIsNone(candidates.remote_head(self.remote, str(self.remote), "dashboard"))

    def test_synthetic_evidence_requires_marked_bare_remote(self) -> None:
        """Test synthetic evidence requires marked bare remote."""
        self.prepare()
        attestation, execution = synthetic_review(self.store, self.root)
        (self.remote / "dscat-usage-synthetic").unlink()
        self.error(3, validate_review, self.store, attestation=attestation, execution_evidence=execution)

    def test_missing_capture_and_symlinks_fail_before_candidate(self) -> None:
        """Test missing capture and symlinks fail before candidate."""
        inputs = self.inputs.copy()
        inputs.pop("capture")
        self.error(2, self.prepare, self.store, inputs)
        self.inputs["map"].unlink()
        self.inputs["map"].symlink_to(self.inputs["rates"])
        self.error(3, self.prepare)
        self.assertIsNone(self.store.get("candidate"))

    def test_same_generation_fork_preserves_remote_and_candidate(self) -> None:
        """Test same generation fork preserves remote and candidate."""
        result = self.publish()
        old_pointer = self.store.get("candidate")
        old = Contribution.from_dict(candidates.loads(read_bytes(self.inputs["contribution"])))
        self.write_contribution(self.inputs, replace(old, observed_at="2026-01-02T00:00:00Z"))
        self.error(4, self.prepare)
        self.assertEqual(self.store.get("candidate"), old_pointer)
        self.assertEqual(candidates.remote_head(self.remote, str(self.remote), "dashboard"), result.remote_commit)


if __name__ == "__main__":
    unittest.main()
