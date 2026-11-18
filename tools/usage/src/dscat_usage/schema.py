"""Strict versioned boundaries shared by the maintenance pipeline."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Self, cast

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet

SCHEMA = 1
MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
MAX_RECORDS = 1_000_000
MAX_DIAGNOSTICS = 100
MAX_DEPTH = 32
MAX_STRING = 16384
MAX_TIMESTAMP = 40
MAX_PATH = 4096
PHASES = frozenset(
    {
        "requirements",
        "architecture",
        "planning",
        "implementation",
        "verification",
        "review",
        "integration",
        "release preparation",
        "post-release verification",
        "coordinator",
        "mixed",
        "unknown",
    }
)
TOKEN_KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)
DIMENSIONS = ("primary", "associated", "phase", "task", "feature")
SPECIAL_PRIMARY = frozenset({"unallocated", "shared", "coordinator"})


class UsageError(ValueError):
    """Bounded diagnostic safe for a human or structured status."""

    def __init__(self, reason: str, code: int = 2) -> None:
        """Initialize and validate the private boundary."""
        super().__init__(reason)
        self.code = code


def require(condition: object, reason: str = "invalid schema", code: int = 2) -> None:
    """Reject a failed boundary condition with a bounded diagnostic."""
    if not condition:
        raise UsageError(reason, code)


def digest(data: bytes) -> str:
    """Return the SHA-256 content identity."""
    return hashlib.sha256(data).hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _finite(value: object, depth: int = 0) -> None:
    require(depth <= MAX_DEPTH, "JSON nesting limit")
    if value is None or type(value) is bool:
        return
    if type(value) is int or type(value) is float:
        # Bound integers before any float conversion: math.isfinite converts
        # an integer to float and can itself overflow on hostile JSON numbers.
        require(abs(value) <= 10**18 and math.isfinite(value), "invalid number")
    elif isinstance(value, str):
        require(len(value) <= MAX_STRING, "string limit")
    elif isinstance(value, (list, tuple)):
        require(len(value) <= MAX_RECORDS, "record limit")
        for item in value:
            _finite(item, depth + 1)
    elif isinstance(value, dict):
        require(len(value) <= MAX_RECORDS and all(isinstance(k, str) for k in value), "invalid object")
        for key, item in value.items():
            _finite(key, depth + 1)
            _finite(item, depth + 1)
    else:
        message = "invalid JSON value"
        raise UsageError(message)


def canonical(value: object) -> bytes:
    """Encode validated JSON deterministically."""
    _finite(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def loads(data: bytes) -> Any:  # noqa: ANN401 - strict generic JSON decoder; every domain boundary validates schema.
    """Decode JSON while rejecting duplicate keys and unsafe values."""
    require(len(data) <= MAX_FILE, "input byte limit", 3)
    try:
        value = json.loads(
            data,
            object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(UsageError("nonfinite number")),
        )
        _finite(value)
    except UsageError:
        raise
    except (UnicodeError, ValueError, RecursionError, OverflowError) as exc:
        message = "invalid JSON"
        raise UsageError(message, 3) from exc
    else:
        return value


def keys(value: object, required: AbstractSet[str], optional: AbstractSet[str] = frozenset()) -> dict[str, Any]:
    """Validate an object boundary and return its checked mapping."""
    if not isinstance(value, dict) or not required <= value.keys() <= required | optional:
        message = "invalid schema"
        raise UsageError(message)
    return cast("dict[str, Any]", value)


def integer(value: object, minimum: int = 0, maximum: int = 10**18) -> int:
    """Validate and return a bounded non-boolean integer."""
    if type(value) is not int or not minimum <= value <= maximum:
        message = "invalid integer"
        raise UsageError(message)
    return value


def text(value: object, pattern: str = r"[A-Za-z0-9_.:-]{1,128}") -> str:
    """Validate and return a bounded label."""
    if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
        message = "invalid label"
        raise UsageError(message)
    return value


def sha(value: object, nullable: bool = False) -> None:  # noqa: FBT001, FBT002 - preserve the validated schema helper interface.
    """Validate a content digest or explicitly permitted null."""
    if nullable and value is None:
        return
    text(value, r"[a-f0-9]{64}")


def timestamp(value: object, nullable: bool = False) -> None:  # noqa: FBT001, FBT002 - preserve the validated schema helper interface.
    """Validate an aware ISO timestamp or explicitly permitted null."""
    if value is None and nullable:
        return
    if not isinstance(value, str) or len(value) > MAX_TIMESTAMP:
        message = "invalid timestamp"
        raise UsageError(message)
    try:
        parsed = datetime.fromisoformat(value)
        require(parsed.tzinfo is not None, "timestamp timezone required")
    except ValueError as exc:
        message = "invalid timestamp"
        raise UsageError(message) from exc


@dataclass(frozen=True)
class Vocabulary:
    """Reviewed inventories; an empty inventory never approves source labels."""

    models: frozenset[str] = frozenset()
    providers: frozenset[str] = frozenset()
    efforts: frozenset[str] = frozenset()
    tiers: frozenset[str] = frozenset()
    rtm: frozenset[str] = frozenset()
    tasks: frozenset[str] = frozenset()
    features: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        """Validate configured immutable field bounds."""
        for name in ("models", "providers", "efforts", "tiers"):
            for value in getattr(self, name):
                text(value, r"[A-Za-z0-9_.:-]{1,80}")
        for value in self.rtm:
            text(value, r"(?:FR|NFR|RTM|ART)-\d{3}")
        for value in self.tasks:
            text(value, r"TASK-\d{3}")
        for value in self.features:
            text(value, r"FEATURE-\d{3}")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Self:
        """Construct and validate the supported schema from a mapping."""
        keys(value, {"schema", "models", "providers", "efforts", "tiers", "rtm", "tasks", "features"})
        require(type(value["schema"]) is int and value["schema"] == 1)
        fields: dict[str, frozenset[str]] = {}
        for key in value.keys() - {"schema"}:
            require(isinstance(value[key], list) and all(isinstance(x, str) for x in value[key]))
            require(len(value[key]) == len(set(value[key])))
            fields[key] = frozenset(value[key])
        return cls(**fields)


DEFAULT_VOCABULARY = Vocabulary()


def present[T](value: T | None, reason: str = "invalid schema", code: int = 3) -> T:
    """Return an available value or raise a bounded missing-input diagnostic."""
    if value is None:
        raise UsageError(reason, code)
    return value


def attribution(value: object, vocabulary: Vocabulary) -> None:
    """Validate all attribution dimensions against reviewed inventories."""
    value = keys(value, set(DIMENSIONS))
    require(
        isinstance(value["primary"], str) and value["primary"] in vocabulary.rtm | SPECIAL_PRIMARY, "unknown primary"
    )
    require(isinstance(value["phase"], str) and value["phase"] in PHASES, "unknown phase")
    require(isinstance(value["associated"], list) and all(isinstance(x, str) for x in value["associated"]))
    require(len(set(value["associated"])) == len(value["associated"]) and set(value["associated"]) <= vocabulary.rtm)
    require(
        value["task"] is None or (isinstance(value["task"], str) and value["task"] in vocabulary.tasks), "unknown task"
    )
    require(
        value["feature"] is None or (isinstance(value["feature"], str) and value["feature"] in vocabulary.features),
        "unknown feature",
    )


def empty_attribution() -> dict[str, Any]:
    """Return the explicit unknown attribution dimensions."""
    return {"primary": "unallocated", "associated": [], "phase": "unknown", "task": None, "feature": None}


def tokens(value: object) -> None:
    """Validate token counts, subsets and totals."""
    value = keys(value, set(TOKEN_KEYS))
    for count in value.values():
        if count is not None:
            integer(count)
    for subset, total in (("cached_input_tokens", "input_tokens"), ("reasoning_output_tokens", "output_tokens")):
        require(
            value[subset] is None or value[total] is None or value[subset] <= value[total], "invalid token subset", 4
        )
    if all(value[k] is not None for k in ("input_tokens", "output_tokens", "total_tokens")):
        require(value["input_tokens"] + value["output_tokens"] == value["total_tokens"], "token total conflict", 4)


@dataclass(frozen=True)
class Observation:
    """Observation schema and validated maintenance operations."""

    kind: str
    receipt: str
    thread: str
    turn: str | None = None
    parent: str | None = None
    root: str | None = None
    parent_known: bool = False
    timestamp: str | None = None
    start: str | None = None
    end: str | None = None
    duration_seconds: float | int | None = None
    timing_basis: str = "missing"
    model: str | None = None
    provider: str | None = None
    effort: str | None = None
    tier: str | None = None
    usage: dict[str, int | None] = field(default_factory=lambda: dict.fromkeys(TOKEN_KEYS))
    attribution: dict[str, Any] = field(default_factory=empty_attribution)

    def validate(self, vocabulary: Vocabulary = DEFAULT_VOCABULARY) -> None:
        """Validate this boundary against the supported schema."""
        require(isinstance(self.kind, str) and self.kind in {"thread", "turn", "response"})
        for value in (self.receipt, self.thread):
            sha(value)
        for value in (self.turn, self.parent, self.root):
            sha(value, nullable=True)
        require(type(self.parent_known) is bool)
        require(self.parent_known or self.parent is None)
        require(self.kind == "thread" or self.turn is not None, "missing turn identity", 4)
        require(self.kind != "thread" or self.receipt == self.thread)
        require(self.kind != "turn" or self.receipt == self.turn)
        for value in (self.timestamp, self.start, self.end):
            timestamp(value, nullable=True)
        require(
            self.start is None
            or self.end is None
            or datetime.fromisoformat(self.end) >= datetime.fromisoformat(self.start),
            "reversed interval",
            4,
        )
        if self.duration_seconds is not None:
            require(
                type(self.duration_seconds) in (float, int)
                and 0 <= self.duration_seconds <= 10**12
                and math.isfinite(self.duration_seconds)
            )
        require(isinstance(self.timing_basis, str) and self.timing_basis in {"missing", "recorded", "derived_interval"})
        require((self.duration_seconds is None) == (self.timing_basis == "missing"))
        for name, inventory in (
            ("model", vocabulary.models),
            ("provider", vocabulary.providers),
            ("effort", vocabulary.efforts),
            ("tier", vocabulary.tiers),
        ):
            value = getattr(self, name)
            require(value is None or (isinstance(value, str) and value in inventory), "unknown model setting")
        tokens(self.usage)
        attribution(self.attribution, vocabulary)
        if self.kind != "response":
            require(
                all(x is None for x in self.usage.values())
                and all(getattr(self, k) is None for k in ("model", "provider", "effort", "tier"))
            )
        else:
            require(self.start is None and self.end is None and self.duration_seconds is None)

    def to_dict(self) -> dict[str, Any]:
        """Return the serializable schema representation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any], vocabulary: Vocabulary = DEFAULT_VOCABULARY) -> Self:
        """Construct and validate the supported schema from a mapping."""
        keys(value, set(cls.__dataclass_fields__))
        result = cls(**value)
        result.validate(vocabulary)
        return result


@dataclass(frozen=True)
class Contribution:
    """Contribution schema and validated maintenance operations."""

    domain: str
    contributor: str
    generation: int
    predecessor: str | None
    observed_at: str
    observations: tuple[Observation, ...]
    removals: tuple[str, ...] = ()
    coverage: dict[str, Any] = field(
        default_factory=lambda: {
            "historical_completeness": "unknown",
            "active_tail": "unknown",
            "unavailable_sources": 0,
            "partial_lines": 0,
        }
    )
    schema: int = SCHEMA

    def validate(self, vocabulary: Vocabulary = DEFAULT_VOCABULARY) -> None:
        """Validate this boundary against the supported schema."""
        integer(self.schema, 1, 1)
        sha(self.domain)
        text(self.contributor, r"[a-f0-9]{32}")
        integer(self.generation, 1)
        sha(self.predecessor, nullable=True)
        require((self.generation == 1) == (self.predecessor is None), "generation predecessor conflict", 4)
        timestamp(self.observed_at)
        require(len(self.observations) <= MAX_RECORDS)
        receipts: set[str] = set()
        for record in self.observations:
            record.validate(vocabulary)
            require(record.receipt not in receipts, "duplicate observation", 4)
            receipts.add(record.receipt)
        for value in self.removals:
            sha(value)
        require(len(set(self.removals)) == len(self.removals) and not receipts.intersection(self.removals))
        keys(self.coverage, {"historical_completeness", "active_tail", "unavailable_sources", "partial_lines"})
        require(self.coverage["historical_completeness"] == "unknown" and self.coverage["active_tail"] == "unknown")
        integer(self.coverage["unavailable_sources"], 0, MAX_RECORDS)
        integer(self.coverage["partial_lines"], 0, MAX_RECORDS)

    def to_dict(self) -> dict[str, Any]:
        """Return the serializable schema representation."""
        result = asdict(self)
        result["observations"] = [r.to_dict() for r in self.observations]
        result["removals"] = list(self.removals)
        return result

    @classmethod
    def from_dict(cls, value: dict[str, Any], vocabulary: Vocabulary = DEFAULT_VOCABULARY) -> Self:
        """Construct and validate the supported schema from a mapping."""
        keys(value, set(cls.__dataclass_fields__))
        require(isinstance(value["observations"], list) and isinstance(value["removals"], list))
        result = cls(
            domain=value["domain"],
            contributor=value["contributor"],
            generation=value["generation"],
            predecessor=value["predecessor"],
            observed_at=value["observed_at"],
            observations=tuple(Observation.from_dict(r, vocabulary) for r in value["observations"]),
            removals=tuple(value["removals"]),
            coverage=value["coverage"],
            schema=value["schema"],
        )
        result.validate(vocabulary)
        return result


@dataclass(frozen=True)
class Ledger:
    """Ledger schema and validated maintenance operations."""

    domain: str
    contributions: tuple[Contribution, ...]
    schema: int = SCHEMA

    def validate(self, vocabulary: Vocabulary = DEFAULT_VOCABULARY) -> None:
        """Validate this boundary against the supported schema."""
        integer(self.schema, 1, 1)
        sha(self.domain)
        seen: set[str] = set()
        for contribution in self.contributions:
            contribution.validate(vocabulary)
            require(contribution.domain == self.domain, "receipt domain mismatch", 4)
            require(contribution.contributor not in seen, "duplicate contributor", 4)
            seen.add(contribution.contributor)

    def to_dict(self) -> dict[str, Any]:
        """Return the serializable schema representation."""
        return {
            "schema": self.schema,
            "domain": self.domain,
            "contributions": [c.to_dict() for c in self.contributions],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any], vocabulary: Vocabulary = DEFAULT_VOCABULARY) -> Self:
        """Construct and validate the supported schema from a mapping."""
        keys(value, {"schema", "domain", "contributions"})
        require(isinstance(value["contributions"], list))
        result = cls(
            value["domain"],
            tuple(Contribution.from_dict(c, vocabulary) for c in value["contributions"]),
            value["schema"],
        )
        result.validate(vocabulary)
        return result


BINDINGS = {"candidate_digest", "tree_digest", "input_digest", "metadata_digest", "parent"}


@dataclass(frozen=True)
class Candidate:
    """Private immutable candidate framing, including complete-tree bindings."""

    domain: str
    generator_invocation: str
    created_at: str
    parent: str | None
    tree_digest: str
    input_digest: str
    metadata_digest: str
    files: dict[str, str]
    inputs: dict[str, str]
    generations: dict[str, int]
    remote: str
    branch: str
    metadata: dict[str, str]
    synthetic: bool = False
    schema: int = SCHEMA

    def validate(self) -> None:
        """Validate this boundary against the supported schema."""
        integer(self.schema, 1, 1)
        for value in (self.domain, self.tree_digest, self.input_digest, self.metadata_digest):
            sha(value)
        if self.parent is not None:
            text(self.parent, r"(?:[a-f0-9]{40}|[a-f0-9]{64})")
        text(self.generator_invocation)
        timestamp(self.created_at)
        require(isinstance(self.files, dict) and isinstance(self.inputs, dict) and isinstance(self.generations, dict))
        for path, value in self.files.items():
            text(path, r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*")
            require(all(part not in {".", "..", ".git"} for part in path.split("/")))
            sha(value)
        for label, value in self.inputs.items():
            text(label)
            sha(value)
        for contributor, generation in self.generations.items():
            text(contributor, r"[a-f0-9]{32}")
            integer(generation, 1)
        require(isinstance(self.remote, str) and 0 < len(self.remote) <= MAX_PATH)
        text(self.branch, r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*")
        require(
            self.metadata
            == {
                "name": "Usage Dashboard",
                "email": "usage-dashboard@users.noreply.github.com",
                "message": "Update aggregate usage dashboard",
            }
        )
        require(type(self.synthetic) is bool)

    def to_dict(self) -> dict[str, Any]:
        """Return the serializable schema representation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Self:
        """Construct and validate the supported schema from a mapping."""
        keys(value, set(cls.__dataclass_fields__))
        result = cls(**value)
        result.validate()
        return result


@dataclass(frozen=True)
class ReviewEvidence:
    """ReviewEvidence schema and validated maintenance operations."""

    task: str
    generator_invocation: str
    reviewer_invocation: str
    candidate_digest: str
    tree_digest: str
    input_digest: str
    metadata_digest: str
    parent: str | None
    timestamp: str
    disposition: str
    scope: str = "complete-candidate"
    synthetic: bool = False
    schema: int = SCHEMA

    def validate(self) -> None:
        """Validate this boundary against the supported schema."""
        integer(self.schema, 1, 1)
        for value in (self.task, self.generator_invocation, self.reviewer_invocation):
            text(value)
        require(self.generator_invocation != self.reviewer_invocation, "independent review required", 5)
        for key in BINDINGS - {"parent"}:
            sha(getattr(self, key))
        if self.parent is not None:
            text(self.parent, r"(?:[a-f0-9]{40}|[a-f0-9]{64})")
        timestamp(self.timestamp)
        require(
            isinstance(self.disposition, str)
            and self.disposition in {"PASS", "FAIL"}
            and self.scope == "complete-candidate",
            "invalid review scope",
            5,
        )
        require(type(self.synthetic) is bool)

    def to_dict(self) -> dict[str, Any]:
        """Return the serializable schema representation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Self:
        """Construct and validate the supported schema from a mapping."""
        keys(value, set(cls.__dataclass_fields__))
        result = cls(**value)
        result.validate()
        return result


@dataclass(frozen=True)
class Attestation(ReviewEvidence):
    """Attestation schema and validated maintenance operations."""

    execution_evidence_digest: str = ""

    def validate(self) -> None:
        """Validate this boundary against the supported schema."""
        super().validate()
        sha(self.execution_evidence_digest)


@dataclass(frozen=True)
class Status:
    """Status schema and validated maintenance operations."""

    status: str
    counts: dict[str, int] = field(default_factory=dict)
    candidate_digest: str | None = None
    remote_commit: str | None = None
    schema: int = SCHEMA
    COUNT_KEYS: ClassVar[frozenset[str]] = frozenset(
        {
            "responses",
            "turns",
            "threads",
            "open",
            "missing",
            "unmapped",
            "conflicts",
            "unavailable",
            "partial_lines",
            "migrated",
            "archived",
        }
    )

    def validate(self) -> None:
        """Validate this boundary against the supported schema."""
        integer(self.schema, 1, 1)
        require(
            isinstance(self.status, str)
            and self.status
            in {"prepared", "review_required", "submitted", "remote_verified", "unavailable", "conflict", "failed"}
        )
        require(isinstance(self.counts, dict) and self.counts.keys() <= self.COUNT_KEYS)
        for value in self.counts.values():
            integer(value, 0, MAX_RECORDS)
        sha(self.candidate_digest, nullable=True)
        if self.remote_commit is not None:
            text(self.remote_commit, r"(?:[a-f0-9]{40}|[a-f0-9]{64})")

    def to_dict(self) -> dict[str, Any]:
        """Return the serializable schema representation."""
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Self:
        """Construct and validate the supported schema from a mapping."""
        keys(value, {"schema", "status", "counts", "candidate_digest", "remote_commit"})
        result = cls(**value)
        result.validate()
        return result
