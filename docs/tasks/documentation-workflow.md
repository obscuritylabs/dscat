# Documentation workflow task

## Scope and authority

Human instruction, 2026-11-16: implement the proposed progressive-disclosure and Git-history cleanup together with distinct fresh sub-agents per SDLC phase. The follow-up explicitly includes both parts. This directly requested governance maintenance supports CAP-05/NFR-006/NFR-007 and CAP-04/NFR-008/NFR-015/NFR-016. Product requirements, architecture/implementation approval, and release authority MUST remain unchanged. The instruction MUST NOT be represented as approval of an exact new product baseline or as release authorization.

## Maintenance plan and acceptance

The authorized design separates compact control documents, phase role instructions, and domain references. Implementation MUST preserve substantive constraints while moving them to authoritative homes. The change MUST:

1. Provide a minimal coordinator route and a distinct fresh context for each phase, bounded handoffs, prerequisite checks, failure/reopening routes, and shared behavioral baselines for implementation and verification.
2. Retain all seven completion stages and explicit human planning/release gates; independent review MUST be distinguished from self-review and fresh context.
3. Replace duplicated scope/status and superseded narration with current statements and Git retrieval references; preserve stable IDs, approval evidence, residual risks, security, licensing, and traceability.
4. Cover the complete maintained documentation set through bounded semantic review assignments and cross-document reconciliation, plus links/anchors, identifiers, RTM membership/references and negative-control checks.
5. Supply a reproducible manual walkthrough, exact candidate identity and results. Integrate through an agent-reviewed rebase PR after verification. Release and post-release stages MUST remain pending without separate authorization.

## Current handoff

Phase: remote-main integration verified; PR #17 is MERGED at `55dcd0a6e052361112c467c9e06876c8d541d088` (read-only GitHub PR query, 2026-11-16). Release and downloaded-artifact stages remain PENDING; the linked PR retains exact verification evidence. Original source baseline: `0b7b82459a7136922bdc2d8439839553114b6905`; integration baseline: `67c56cd56dd01b6bc03ae2f33e0e7720f28fa860`, incorporating DEC-041 approval of the original committed decision baseline only. Implementation commit: `f14a70ffd5cdfa2063a8b7acf6e768eb5ca4f608`. [PR #17](https://github.com/obscuritylabs/dscat/pull/17) retains exact structural recipe, candidate identity, review coverage and verification results. Historical final task-status review evidence is retained in PR #17; current corrections MUST receive fresh affected review. Existing product requirements retain their approved behavior; editorial updates do not extend original approval scope.

Bootstrap implementation: the parent prepared entry points, extracted policy and this task record before activating the new coordinator boundary. Fresh agents implemented workflow/roles and current-state cleanup. A fresh reconciliation agent owns governance, engineering, QA, gates, requirements and RTM. Fresh reviewers cover the current-state documents and the control/policy/role set separately, followed by cross-document reconciliation. Subsequent execution MUST follow the new coordinator boundary; this bootstrap MUST NOT be described as an entirely phase-isolated run. Findings MUST be corrected before integration; summaries MUST NOT substitute for reading assigned sections.

## Verification walkthrough

Setup: use a clean clone with Python and Git; check out the exact candidate revision recorded in PR evidence. Read AGENTS.md, the index and workflow only to route the synthetic task “verify explicit output replacement.” The coordinator MUST assign the verification role; that role MUST retrieve FR-011, relevant NFR-002/005/009 acceptance, RTM rows and approved publication design. Missing approved design MUST block product execution rather than be guessed.

Positive: inspect every phase route and handoff field; confirm all seven stages map to an owner. Retrieve historical procedure with `git show 0b7b824:docs/privacy-remediation.md` without treating it as current authority. Run `git diff --check 0b7b824 HEAD` and the exact structural recipe retained in the change PR; all local links, anchors, unique IDs, dynamically enumerated current requirement/RTM memberships (30 belongs only to historical PR #17 evidence) and decision/capability references MUST pass.

Negative: run the recipe's in-memory missing-file, missing-anchor, duplicate-ID, missing-RTM-row, unknown-source, unknown-capability and unanchored-acceptance controls; each MUST fail verification. Inspect workflow handling of missing approval, stale candidate revision, unavailable fresh-agent tooling and an implementation-origin reviewer; none MUST advance as a successful phase. A release assignment without authorization MUST remain blocked.

Cleanup: synthetic structural mutations MUST remain in memory. Delete any temporary audit script or clone after retaining its exact recipe and results with the PR. No workbook, package, runtime acceptance or release test MUST be claimed for this documentation-only change.

## Review coverage

Coverage uses all nine areas of the [semantic matrix](../documentation-qa.md#full-semantic-review-matrix); retained coverage applies only to identical content and applicability. Review identities refer to distinct fresh invocations. Findings remain outside this record.

| Assignment and reviewed scope | Reviewer | Candidate evidence and disposition |
| --- | --- | --- |
| Historical control set: AGENTS.md; docs/index.md; docs/workflow.md; docs/tasks/documentation-workflow.md; docs/governance.md; docs/engineering.md; docs/documentation-qa.md; docs/planning-gates.md; docs/requirements.md; docs/rtm.md; all eight phase files (architecture, implementation, integration, planning, release, requirements, review, verification; 18 documents, complete sections) | `/root/review_control` | All nine matrix areas reviewed; SHA-256 `b69182b1e279dc0473a60b0053ebc5810e4cab93c07d20968591e2196990cd11` over sorted relative path + NUL + file bytes + NUL; retained only for identical content and applicability; synchronized approval and task sections reviewed by `/root/verify_synced`; subsequent task-status metadata requires fresh affected review |
| Domain set: decisions, intake proposals, canonical model, research, delivery plan, privacy remediation, repository policy; LICENSE and pyproject.toml (complete files) | `/root/review_current`; final `/root/review_compaction` | All nine matrix areas where applicable; corrected candidate reconciled by `/root/verify_synced`; no README exists in this checkout |
| Combined candidate: cross-document authority, terminology, links, mappings and review dispositions | `/root/final_reconciliation` | Corrections checked by `/root/verify_corrections`; final `/root/verify_synced` PASS at SHA-256 `6369dcade9fd6ed4ceeb07b3d2ad63ca46aa30308ae695d030af22f503bd80c4`; exact scope/results retained in PR #17 |

## Stage ledger

| Stage | Current evidence/status |
| --- | --- |
| Planned | Direct maintenance instruction and scope/acceptance above; product gates unchanged |
| Implemented | DONE: implementation commit and reviewed scope linked above |
| Tested | PASS: final structural recipe, all seven in-memory negative controls and whitespace checks; exact commands/results in PR #17 |
| Locally verified | PASS: bounded semantic coverage, final fresh affected review/reconciliation and walkthrough at recorded candidate; historical task-status metadata review retained in PR #17; this correction requires fresh affected review |
| Remote-main integration | [PR #17](https://github.com/obscuritylabs/dscat/pull/17) holds the protected rebase-merge outcome and origin/main revision verification; MERGED at `55dcd0a6e052361112c467c9e06876c8d541d088`, verified through read-only GitHub PR merge metadata and local Git ancestry on 2026-11-16 |
| Published release | PENDING human release authorization |
| Released-artifact verification | PENDING publication and downloaded-source checks |

This record MUST be updated in place. Exact candidate hashes, commands/results and integration evidence MUST be retained with the PR; this ledger MUST link that evidence rather than accumulate execution transcripts.
