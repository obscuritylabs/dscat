# Local usage tools

`dscat-usage` 0.1.1 is a separate maintenance package, proprietary to Obscurity
Labs. At the time this source revision was prepared, `usage-v0.1.1` had not yet
been published. It requires Python 3.14 or later and Git on PATH. It has no
Python runtime dependencies. It does not implement catalog commands. Its planned release
tag is `usage-v0.1.1`.

Actual history refresh, real contributions, tracker publication, and migration
of the published Usage-Refresh protocol are excluded from this release task.
Real tracker use needs a separately reviewed protocol transition. The commands
below explain the supported tooling; use disposable synthetic sources/remotes
until that transition. The synthetic walkthrough needs no histories, credentials,
tracker connection, or network access.

The download and rebuild commands below apply after `usage-v0.1.1` is published.
Replace `OWNER/REPOSITORY` with the authorized release repository before
downloading its authenticated assets. The `usage-v0.1.1` release MUST publish
`RELEASE-NOTES.md` as a release asset and include its digest in the published
`SHA256SUMS` asset. It MUST publish `SHA256SUMS` and include an entry for every
other attached release asset, so `sha256sum -c SHA256SUMS` succeeds after
download.

```sh
gh release download usage-v0.1.1 --repo OWNER/REPOSITORY --dir usage-release
cd usage-release
sha256sum -c SHA256SUMS
uv tool install --python 3.14 ./dscat_usage-0.1.1-py3-none-any.whl
dscat-usage --version
dscat-usage --help
```

The `usage-v0.1.0` release has been published. The compatible patch release
`usage-v0.1.1` had not yet been published when this source revision was
prepared. Downloaded-artifact verification is a separate check from publication.
Keep the downloaded source archive for tests and instructions. After
`usage-v0.1.1` is published, rebuild the source package with the frozen build
dependencies:

```sh
tar -xzf dscat_usage-0.1.1.tar.gz
cd dscat_usage-0.1.1
uv sync --frozen
uv build --python .venv/bin/python --no-sources --no-build-isolation
uv run --frozen python tests/walkthrough.py
```

For an installed-wheel walkthrough outside the checkout, create a clean venv,
install only that wheel, and run `tests/walkthrough.py` from the extracted sdist
with that venv's Python. The walkthrough imports the installed package, never
adds the source tree to its import path. It creates two independent computers,
a disposable bare Git remote and one shared synthetic secret; all are deleted
on exit. Its fabricated review evidence is explicitly synthetic, accepted only
for a marked local bare remote, and does not establish independent review.

## Set up each computer

Provision one cryptographically random 32-byte secret privately, outside Git,
and securely supply those same bytes to each participating computer. Do not use
one different secret per computer, a password, hostname, checkout path, or
contributor ID. For disposable testing one can create the file with:

```sh
umask 077
python3 -c 'import secrets; from pathlib import Path; Path("shared-secret.bin").write_bytes(secrets.token_bytes(32))'
```

Each computer keeps its own histories, configuration, reviewed maps and state.
Only the secret is provisioned jointly; do not copy another computer's state or
ignored tooling bundle. Use absolute paths outside any Git checkout for state
and private configuration. For example, with `PRIVATE` set to your own private
directory (and `SECRET` to the absolute secret file):

```sh
dscat-usage setup --state "$PRIVATE/state" --config "$PRIVATE/config.json" --secret-file "$SECRET"
```

The parent directory must already exist; ordinary ancestors may use mode 0755.
Secret, config, configured maps, mapping entries, legacy snapshot/map/registry/
identity-association inputs, review attestations and execution evidence must deny
all group/other access (normally mode 0600). Create these files with `umask 077`
or restore their permissions before retrying. If originals must retain their
permissions, make byte-for-byte copies in a private directory with restricted
file modes and pass those copies explicitly. State directories use mode 0700
and files mode 0600, including frozen candidate inputs and descriptors. Setup,
acceptance and revalidation reject exposed private inputs with exit 3; they do
not repair caller permissions or replace accepted pointers. Native histories and
external reviewed public rates/vocabularies may retain ordinary file modes.

Setup refuses existing state and never
replaces existing configuration. It creates empty map/rates/vocabulary files
and a config template if config is absent. Edit `source_root` to the explicitly
selected local history root and `project_selector` to the exact absolute project
selector recorded by those histories. No default source discovery occurs. The
template deliberately names unavailable sources until edited. Existing valid
caller-authored config is also supported. Config paths must be absolute.

The importer reads `sessions/**/*.jsonl`, `archived_sessions/**/*.jsonl`, optional
`state_5.sqlite` thread metadata, and optional `thread_history_1.sqlite` turns
under that explicit root. Native `session_meta`, `turn_context`,
`event_msg/task_started`, `event_msg/task_complete`, `event_msg/token_count`, and
`token_usage_record` records are supported. Token-count events need native turn
identity and either native response identity or a unique recorded timestamp.
Cumulative counters are never counted as per-response usage. Unsupported stable
identity blocks contribution. SQLite reads use read-only transactions and JSONL
uses stable captured prefixes; there is no cross-source transaction guarantee.
Missing databases, partial lines, unknown historical completeness and active
tail remain visible, not a zero-completeness assertion. A first contribution
with unavailable databases is blocked; restore the intended sources. Later
unavailable captures can only preserve all previously accepted observations
unchanged, never replace known history with empty data. Limits default to 64 MiB
per file, 512 MiB total, one million records and 100 diagnostic categories;
config can lower these limits.

Edit the vocabulary JSON arrays to reviewed exact public model/provider/effort/
tier values and current public requirement IDs. Task labels use `TASK-001` and
feature labels `FEATURE-001` style opaque registrations. Do not add names or
private labels. Empty vocabularies keep settings unknown and allocation
unallocated. The default rates file is `{ "schema": 1, "rates": [] }`; costs
stay unpriced until reviewed rates with public provenance are supplied. The
synthetic `tests/fixtures/rates-v1.json` shows the strict rate fields, not current
prices or a recommendation. API cost estimates are not bills; currencies and
dated versus current-list estimates remain separate.

To map a private native thread, turn or response, write a private entry such as:

```json
{"schema":1,"level":"thread","id":"native-synthetic-thread","reviewed":true,"evidence":"private dispatch record","primary":"NFR-006","phase":"implementation","task":"TASK-001"}
```

Register the requirement/task in your vocabulary first. Then:

```sh
dscat-usage map --state "$PRIVATE/state" --config "$PRIVATE/config.json" --entry "$PRIVATE/entry.json"
dscat-usage refresh --state "$PRIVATE/state" --config "$PRIVATE/config.json" --json
```

Response mappings override turn mappings, then thread mappings, independently
per dimension. `map` atomically updates a locked state registry; the configured
map plus this registry becomes the frozen effective map. Conflicting primary
or other dimension assignments fail. Do not edit immutable snapshots/objects.
Refresh freezes config, effective map, source digests, normalized observations,
private associations, rates and vocabulary automatically. Original IDs and
paths stay private. It refuses to silently remove earlier observations when
histories disappear. Restore those sources before retrying; deliberate removals
need an explicit reviewed correction workflow, not deletion of history files.

## Prepare, review, submit, read back

Each computer runs these operations itself; no central map editing is needed.
`REMOTE`, `BRANCH` and invocation labels are explicit. Do not point these at an
actual tracker under the current release-task exclusion.

```sh
dscat-usage contribute --state "$PRIVATE/state" --config "$PRIVATE/config.json" --remote "$REMOTE" --branch "$BRANCH" --generator-invocation generator-001 --json
dscat-usage check --state "$PRIVATE/state" --candidate "$CANDIDATE" --json
```

If any owned dashboard page exists without `usage-ledger.json`, preparation
refuses with exit 3 and preserves the historical pages. Transitioning an existing
aggregate dashboard requires separate reviewed corpus/protocol migration; this
tooling task does not authorize that transition.

Preparation returns exit 5 and `review_required` with a candidate digest. It does
not push. `CANDIDATE` is that returned digest. Private
`state/candidates/<digest>/candidate.json`, `bundle.json`, `inputs/` and `files/`
contain the complete frozen outgoing tree and exact bindings, including unchanged
files, metadata, parent and input closure. Read them privately. The ledger uses
stable keyed receipts that permit correlation; receipts are not anonymous.
Rendered pages omit receipts and contributor IDs. Unrelated remote files are
preserved byte for byte. A candidate cannot sanitize unrelated unsafe content:
review must cover the entire tree.

A coordinator dispatches a distinct fresh reviewer with `fork_turns="none"`,
provides those exact files and bindings, and retains original dispatch/return
records privately. The reviewer inspects every outgoing contribution and the
complete tree, source/input semantics, metadata and privacy; scanners alone do
not satisfy review. `templates/review-contract.json` describes the exact supplied
execution envelope and attestation fields. Copy actual bound values and actual
dispatch/return record digests, canonicalize with sorted keys, compact separators
and UTF-8, then supply the files:

```sh
dscat-usage review --state "$PRIVATE/state" --attestation "$PRIVATE/attestation.json" --execution-evidence "$PRIVATE/execution.json" --json
dscat-usage update --state "$PRIVATE/state" --config "$PRIVATE/config.json" --remote "$REMOTE" --branch "$BRANCH" --generator-invocation generator-001 --json
```

The CLI never authors PASS evidence. Generator/reviewer/coordinator invocation
IDs must differ. The evidence binds the exact candidate/tree/input/metadata/
parent; candidate creation <= dispatch <= review <= return. The attestation
repeats the review fields and includes SHA-256 of the exact canonical execution
envelope. Real evidence uses `synthetic:false`. The validator checks procedural
shape and bindings; it cannot authenticate independence or honesty against a
process with access to private state. The coordinator establishes actual fresh
execution. An alternate reviewer string is insufficient.

Resume uses frozen inputs, never refreshes implicitly. Stale parent regenerates
from the newly fetched ledger, retains the rejected candidate, and returns 5;
repeat fresh review for the new digest. Failed pushes preserve accepted state.
An ambiguous successful push is confirmed by exact remote commit/tree identity;
unresolved identity returns 6. A confirmed submission is `submitted`, not a
claim of independently verified publication. Use a separate fresh reader
execution and distinct invocation for:

```sh
dscat-usage readback --state "$PRIVATE/state" --remote "$REMOTE" --branch "$BRANCH" --expected-commit "$COMMIT" --reader-invocation reader-001 --json
```

This creates a separate no-local clone, validates exact ledger/projections/
metadata/ancestry and records `remote_verified` separately. The coordinator
establishes reader freshness. Resolve any uncertain submission by retrying
`update`; refresh returns 5 while such an attempt remains unresolved. Before
any submission attempt, refresh may replace a pending capture in the same next
unpublished generation slot, retaining prior immutable snapshots. Confirmed
submission advances the next generation. A newer capture needs `contribute` and
a new fresh review; `update` refuses to submit an older frozen candidate for it.
Before later observations, refresh again and run
`contribute` for the new contribution, then review/update/readback. Do not reuse
an older candidate for a newer refresh. `check` is read-only and performs no
fetch, refresh or repair. Review/input/metadata changes require new review.

## Explicit private legacy migration

Setup never migrates. For a supported schema-v1 legacy snapshot bundle and maps:

```sh
dscat-usage migrate --state "$PRIVATE/state" --config "$PRIVATE/config.json" --snapshot "$LEGACY_SNAPSHOT" --phase-map "$LEGACY_PHASE_MAP" --registry "$LEGACY_REGISTRY" --json
```

This validates manifest/output hashes and archives original bytes separately,
preserving every legacy input and pointer. Without `--identity-map`, legacy
observations remain historical/nonadditive with unknown corpus coverage; they
are never added to the receipt corpus. Optional `--identity-map PATH` supplies
unique private associations verified against configured original histories.
Only matching supported native identities/facts permit promotion of reviewed
attribution. See the synthetic identity-map fixture. Truncated/derived legacy
IDs alone cannot establish native identity; unsupported or ambiguous input
fails closed. Migration never refreshes or publishes; run the explicit refresh
and reviewed contribution flow afterward. Rebuild the intended corpus from
available originals or retain the old dashboard separately; do not sum dashboards.
Secret rotation/domain changes require an explicit dedup migration and currently
fail closed. No legacy tooling or private state is packaged.

## Status and recovery

Every operation takes `--state`; configuration consumers also take `--config`.
`python -m dscat_usage` exposes the identical command surface. `--json` emits only
`schema`, `status`, `counts`, `candidate_digest`, `remote_commit`, with null for
unavailable identities. Generic diagnostics never print raw IDs, source paths,
URLs, prompts or private labels.

| Exit | Meaning |
| --- | --- |
| 0 | Operation successful; submission and remote verification remain distinct |
| 2 | Arguments, schema or config invalid |
| 3 | Source unavailable/unsupported, unsafe or corrupt state |
| 4 | Mapping, receipt domain, identity, generation or measurement conflict |
| 5 | Independent review needed, absent, changed or stale |
| 6 | Transport failed or remote identity unresolved |
| 7 | Lock contention/recovery needed |

Restore unavailable sources/configuration and retry. Preserve accepted pointers
and candidate directories when diagnosing conflicts; do not erase state to
create a second contributor. A lock is not automatically stolen: after checking
that its recorded local process is inactive, the private `recover_lock` routine
can validate inactivity before removal. There is no CLI lock override. Generic
failures preserve prior accepted publication. Never force push, bypass review,
or merge different receipt domains. Cleanup disposable state only after its
test finishes; retain real private state securely for contributor continuity.

Development checks use the frozen tooling-only lock: `uv run --project
tools/usage --frozen ruff check tools/usage`, `ruff format --check`, `ty check
tools/usage/src`, unit/branch coverage and the synthetic walkthrough. Exact
results and unresolved release checks belong in verification evidence; the
presence of these commands does not imply they passed.
