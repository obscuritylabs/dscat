# Tooling verification policy

This package implements the repository's approved maintenance specification and
plan. The source distribution includes exact copies as evidence, not new policy
authorities; the repository documents remain authoritative. The package does
not implement the catalog product.

The frozen development lock uses PyPI artifacts with SHA-256 hashes and uv's
14-day upload exclusion. Runtime uses the standard library and external Git.
Build backend hatchling is pinned in both build requirements and the dev lock;
release builds use the frozen environment with no build isolation to avoid an
unlocked backend transitive resolution. Security/advisory, licensing, artifact
inspection and installed acceptance remain release gates.

Ruff enables ALL rules. D203 conflicts with D211; D213 conflicts with D212;
COM812 conflicts with the formatter. Those three rules are excluded. No
coverage waiver is established by this file. Achieved statement/branch coverage
and any justified narrow exception must be recorded against the exact candidate.
Coverage 7.11.3 defaults exclude seven `if TYPE_CHECKING` guards and their seven
annotation-only imports. These 14 lines have no runtime behavior; the error-level
type check validates their use. No custom exclusion or runtime coverage waiver
is configured. Runtime statement and branch coverage must be reported separately
from these default exclusions.

The plan requires standard-library unittest discovery. Test files retain
unittest assertions and assertRaises context managers; PT009/PT027 suggestions
to replace them with pytest are excluded only for tests. Local noqa annotations
record individual fixed-interface, transaction/parser complexity, controlled
subprocess, console-output and validated dynamic-JSON boundaries. They do not
relax runtime schema validation or typing rules.
