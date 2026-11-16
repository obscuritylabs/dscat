# Consolidated scope decision handoff

## Identity and authority

Requirements/documentation correction; source `c1a50ff563afa34d987e70f377997b44a6099c4a`, clean at intake. Preparation invocation `/root/resolve_planning` owns the requirements, decisions, gates, RTM, dependent scope summaries and current task references. DEC-038/042 authorize documentation maintenance; DEC-043 records only the human-approved scope decisions dated 2026-11-16. No product code, downstream gate approval, release or remote-policy change is included. Exact candidate commit/tree and document-set digest MUST be retained in the change PR and bounded review handoff; a dirty digest MUST use sorted relative path + NUL + bytes + NUL.

Required reading: AGENTS.md, index/workflow requirements route, requirements phase, governance authority/approval/traceability/Git/completion, documentation QA, requirements/decisions/RTM/gates, research impact, canonical/intake/delivery proposals, engineering and repository policy. Proposed details remain proposals.

## Decision package and acceptance

The human MUST approve or revise the exact reviewed consolidated requirements revision. The decision package consists of requirements SPEC-002/005, FR-003/004/012/013/019/020/021, the DEC-042 research additions/refinements and the research impact package. DEC-039/040/041 retain their exact earlier baseline authority; DEC-043 does not approve remaining research additions or this consolidated revision. First-release and later scope/acceptance are authoritative in requirements; detailed schemas, mappings, ODPS version, lifecycle vocabulary/transitions, reference policies, accessibility arrangements and security controls remain subsequent architecture deliverables. Renewed requirements approval MUST precede architecture approval, followed by implementation-plan approval; release authority remains separate.

Correction acceptance: reconcile scope/exclusions and target readiness; preserve stable IDs and historical approval counts; map new privacy/accessibility/reporting duties into gate deliverables and supporting-artifact RTM mappings; replace stale integration status using retained PR #17/#18 merge evidence. The reusable walkthrough MUST enumerate current requirements dynamically; historical 30/39-count evidence MUST remain attributed. No product verification is claimed.

## Verification and next gate

Self-check recipe: `git diff --check`; retrieve the standard-library recipe from PR #13, recursively inventory Markdown plus LICENSE, calculate counts dynamically, and execute its seven in-memory negative controls. Inspect full diff for privacy, secrets, unsupported authority and unrelated changes. Exact commands, recipe, results and artifact digests MUST remain in the change PR. Structural checks supplement rather than replace independent semantic QA.

Fresh reviewers MUST cover all maintained documentation in bounded partitions under the nine-area documentation QA matrix, followed by a distinct fresh cross-document reconciliation. Suggested scope partitions: requirements/decisions/RTM/gates/research/impact; AGENTS/index/workflow/governance/engineering/QA/all phase roles; canonical/intake/delivery/repository/privacy/all task records/LICENSE/manifest. Corrections MUST invalidate affected review evidence. A reviewer MUST report exact candidate identity and every assigned file/section; unavailable evidence remains PENDING.

| Completion stage | Current evidence/status |
| --- | --- |
| Planned | Authorized documentation preparation and stated interview decisions; exact consolidated requirements approval PENDING |
| Implemented | Documentation candidate; product implementation unperformed |
| Tested | Author structural self-check evidence supplied in bounded handoff; fresh verification PENDING |
| Locally verified | Author self-review only; fresh bounded QA and reconciliation PENDING |
| Remote-main integration | PENDING protected rebase PR |
| Published release | PENDING explicit human authorization |
| Released-artifact verification | PENDING publication and downloaded-source checks |

Next gate: fresh bounded QA/reconciliation of the identified candidate, correction if necessary, protected PR integration, then exact-revision renewed human requirements decision. No full completion is claimed.
