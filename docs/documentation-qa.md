# Documentation QA/QC procedure

## Scope and authority

This procedure implements documentation quality under [AGENTS.md](../AGENTS.md#documentation-lifecycle) and the human-authorized proportional workflow revision of 2026-11-19. Documentation changes MUST receive repository-wide structural checks and semantic review of changed content and identified dependents. Full semantic sweeps MUST be reserved for broad cross-cutting policy changes or explicitly scheduled audits; a small edit MUST NOT trigger a full-document audit. Privacy, authority, and substantive acceptance constraints MUST remain mandatory.

## Change procedure

1. Agents MUST inspect Git status and read applicable policy, the changed authoritative sections, and directly affected references. They MUST state the requested outcome and checks, preserve unrelated work, and identify affected dependents by links and targeted searches. A full inventory or coverage ledger MUST NOT be required for ordinary edits.
2. Agents MUST update the authoritative statement and reconcile affected summaries, examples, links, RTM mappings, and verification procedures in scope. Unrelated stale prose or technical defects MUST remain separate follow-ups. Material new decisions MUST follow the approval policy; editorial changes MUST NOT reopen unchanged decisions.
3. Agents MUST run reproducible repository-wide structural checks for local links/anchors, unique requirement/decision IDs, requirement/RTM membership, and RTM source/capability/acceptance references, plus `git diff --check`. Existing checkers SHOULD be reused. A changed checker MUST reject synthetic missing-link, missing-anchor, duplicate-ID, missing-RTM-row, and unknown-reference cases. Documentation edits MUST NOT acquire product build, package, or release checks without an affected dependency.
4. Semantic review MUST cover the actual changes and identified dependents using applicable areas of the matrix below. [Review applicability](workflow.md#review-applicability) determines whether a fresh independent reviewer is required. One reviewer MAY also reconcile cross-document consistency. Broad audits MAY be partitioned across fresh reviewers, with reconciliation by a reviewer who independently inspects the combined interfaces; a separate reconciliation invocation MUST NOT be mandatory for a bounded change.
5. Agents MUST correct in-scope blocking findings and repeat only affected checks/review. Unchanged evidence MAY be retained when content and applicability remain unchanged; a different commit identity alone MUST NOT invalidate it. Review findings MUST identify concrete unmet criteria or risks. Optional improvements MUST NOT become new acceptance criteria.
6. Before delivery, agents MUST inspect the diff for scope, unsupported authority or execution claims, private context, secrets, and unrelated changes. Evidence MUST follow the stopping rule below. Integration MUST use the protected PR/rebase workflow when it is the requested delivery. Task and release completion MUST follow [governance](governance.md#definition-of-done).

## Reusable structural verification

The standard-library recipe is available at [`docs/evidence/architecture/verify_documents.py`](evidence/architecture/verify_documents.py); earlier recipes and negative controls remain in PR #13 evidence. Agents SHOULD use the checked-in checker from the current checkout root with `python3 docs/evidence/architecture/verify_documents.py`, adapting it only when the structure requires it. The checker MUST inventory maintained nested Markdown and entry documentation, verify current identifiers/memberships, and reject its synthetic negative controls. It MUST NOT substitute for semantic review or imply product/CI enforcement. Existing unrelated structural failures MUST be reported separately; only failures introduced by or genuinely blocking the requested change MUST expand correction scope.

## Full semantic review matrix

The matrix names review concerns, not a requirement to load every document. Reviewers MUST apply relevant areas to changed sections and affected dependents; irrelevant areas MAY be omitted without a separate waiver.

| Area | Required review |
| --- | --- |
| Authority | Explicit human scope versus agent proposal/readiness; no implied approval or invented gate |
| Meaning | Consistent scope, requiredness, terminology, defaults, success and failure semantics |
| Completeness | Measurable acceptance for this task; applicable dependencies and limitations explicit |
| Change control | Current navigation, preserved stable IDs and authority; no consumed exception reused |
| Traceability | Changed behavior mapped to existing requirements; maintenance cites direct authority without fabricated requirements |
| Evidence | Correct candidate, reproducible commands/results, historical versus current observations, stopping rule |
| Technical details | Affected versions, schemas, units, paths, limits, preservation, retries, compatibility and examples agree |
| Delivery and security | Applicable privacy/security/licensing controls retained; task and release boundaries explicit |
| Privacy and format | Generic capabilities and synthetic examples; no identifying context or secrets; conventional formats |

## Evidence conventions

Review evidence MUST identify a frozen commit or a digest of the relevant changed files and dependencies. It MUST live outside the candidate it certifies, such as a PR review, external verification record, or private handoff. A record MUST NOT contain its own digest. Review records MUST NOT become recursively reviewed candidate inputs merely because they report a disposition.

After a pass, agents MAY record factual status, evidence links, observed hashes, check results, or merge identity in task/gate/RTM summaries without another independent review. They MUST self-check accuracy and run applicable whitespace/link checks, then stop. Such recording MUST NOT change scope, acceptance, authority, technical decisions, or the reported result. A changed substantive claim MUST receive only its affected review. Unsupported pass claims and fabricated evidence MUST remain prohibited.

A commit change alone MUST NOT invalidate unchanged evidence. Reports MUST distinguish tested content from later factual status recording and identify historical, unavailable, and unverified observations accurately. Corrections to evidence wording MUST preserve the original observation date and scope.

Public research used to choose technical resources MUST identify immutable upstream revisions and digests where available. Mutable discovery pages MUST NOT serve as runtime pins. Relevant implementation MUST verify transitive schema/context closure and licensing before claiming offline conformance; ordinary documentation maintenance MUST NOT repeat that research without a changed dependency.
