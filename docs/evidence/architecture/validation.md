# Standards architecture research evidence

## Identity and limits

Research was executed on 2026-11-16 against source `697a0764bbdaebd6574079720d3841a8241076a3`, with the new standards document and evidence files uncommitted. This is a bounded architecture research experiment supporting [the standards proposal](../../architecture-standards.md); it is not product implementation, independent verification, architecture approval or release evidence. The handoff MUST identify the final combined candidate/digests after concurrent disjoint edits are reconciled. All examples are synthetic.

The system CPython is 3.14.10. Initial imports found jsonschema, referencing, PyLD and RDFLib absent, and Node/npm/uv unavailable. After coordinator authorization, an isolated temporary virtual environment was created; no project manifest, lockfile or runtime configuration was changed. Temporary tooling MUST NOT establish product dependency pins, age-policy compliance, vulnerability clearance, portability or installed-artifact behavior.

## Reproduction

Tool installation used `python3 -m venv /tmp/dscat-architecture-validation`, then `/tmp/dscat-architecture-validation/bin/python -m pip install jsonschema referencing pyld`. Selected versions were jsonschema 4.26.0, referencing 0.37.0 and PyLD 3.3.0. The complete nine-package distribution identity, exact PyPI wheel URL and byte SHA-256 are in [research-tooling.json](research-tooling.json). Wheels were downloaded separately using `pip download --only-binary=:all:` and their bytes were checked against PyPI release metadata. A reproducer MUST use those exact package versions and matching wheel hashes in an isolated research environment; platform-specific wheels MUST match the chosen interpreter/platform, or a changed experiment MUST identify its new wheel bytes separately.

Validation command:

```sh
/tmp/dscat-architecture-validation/bin/python docs/evidence/architecture/verify_resources.py
```

Observed exit status: `0`.

```text
PASS hashes: 45; schema documents: 42; referenced document URIs: 42
PASS dcat: positive minimum and 7 negative schema fixtures
PASS odcs: positive minimum and 7 negative schema fixtures
PASS core/configuration derivation; distinct identities; no invented purpose/service guarantees
PASS offline JSON-LD expansion/RDF core graph; rejected remote context, malformed context and unknown schema
PASS dcat: detailed optional mapping and malformed output rejection
PASS odcs: detailed optional mapping and malformed output rejection
```

The runner denies socket connections and registry/document-loader retrieval, checks all resource byte hashes, traverses all schema reference document URIs and JSON Pointer fragments, checks root schema well-formedness using the actual dialect, and validates both targets. DCAT negatives remove required core/contact fields, corrupt an email, or supply wrong title type; ODCS negatives remove required identity/version/constants, corrupt kind/description or add forbidden team-member content. Detailed negatives corrupt a distribution access URL type and an ODCS logical field type. The runner checks equality between minimum core/configuration facts and the manually authored minimum output fixtures; it does not implement a production mapper.

JSON-LD checks expand the inline context and produce N-Quads, then assert catalog membership, dataset type/identifier/description, contact type/name/email IRI, distribution membership/download IRI and typed modification date. Remote context, malformed context and unregistered schema requests are rejected. These graph assertions cover the supported experiment, not every JSON-LD processor behavior. The detailed fixtures demonstrate supplied roles, field schema, nullability custom metadata, consumer limitations/usage and semantic references without inventing quality/service guarantees.

## Retrieval and closure

All entries in [resource-manifest.json](resource-manifest.json) were retrieved directly using Python standard-library HTTPS requests. Reproduction MUST retrieve each manifest URL, compare SHA-256 to its recorded value, and store the bytes at the recorded manifest-relative path; a mismatch MUST fail rather than update the digest silently. JSON Schema hosts initially returned HTTP 403 without a browser-style user agent; requests with `User-Agent: Mozilla/5.0` succeeded. No policy block response was encountered on successful retrievals. A request body's content, not HTTP success alone, determined the resource type.

The exact retrieval algorithm is:

```python
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

root = Path("docs/evidence/architecture")
manifest = json.loads((root / "resource-manifest.json").read_text())
for entry in manifest["resources"]:
    request = Request(entry["url"], headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request) as response:
        payload = response.read()
    assert hashlib.sha256(payload).hexdigest() == entry["sha256"]
    assert payload == (root / entry["path"]).read_bytes()
```

The DCAT tree was discovered with GitHub's recursive Git tree API for the pinned revision, then every `jsonschema/definitions/*.json` was retrieved. Only the definition closure is designated for validation; examples in upstream descriptions are not project fixtures. The ODCS schema's fragment references are internal. The draft meta-schema traversal included `$schema`, `$ref`, `$dynamicRef` and `$recursiveRef`, stripping fragments for retrieval and retaining absolute resolver identities. The 42 schema/meta-schema documents have no unresolved reference documents or JSON Pointer fragments. Anchor semantics remain the actual validator's responsibility. The pinned DCAT tree had no current nondeprecated JSON-LD context, so the proposed finite inline contexts have zero external context dependencies.

## Remaining evidence

Installed-product mapping/diagnostic/loss reports, all supported field combinations, platform portability, hostile byte-input limits, package resource inclusion, deterministic production output and released-artifact validation remain PENDING implementation and fresh verification. This research does not claim full DCAT-US semantic/profile certification, contractual completeness or compliance with any deployment obligation. Human architecture approval remains the next planning gate after package QA/QC and reconciliation.
