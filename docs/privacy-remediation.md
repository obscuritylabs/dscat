# History remediation plan

Revision: 1 (2026-11-16). Status: APPROVED for this bounded maintenance operation. This document MUST NOT record the private identity, matching search terms, or local checkout path.

## Requirements and acceptance

This maintenance task MUST support CAP-04/NFR-008 and CAP-05/NFR-006. The human requested removal of identifying context from history and permitted general federal requirements, existing ownership, and contributor metadata. Approval of this procedure is recorded below; it MUST NOT imply approval of the product requirements baseline.

- The rewrite MUST remove research table rows S04 and S05, paragraph RES-006, and paragraph RES-011 from every historical version of docs/research.md. These identifiers MUST remain retired and MUST NOT be reused. RES-011 is included because its source link names an agency.
- General federal requirements and standards references MUST remain. Ownership, contributor metadata, unrelated content, commit messages, and commit ordering MUST remain unchanged unless a specific additional disclosure is found and its removal is approved.
- Verification MUST examine all rewritten commit trees, paths, commit metadata, and live GitHub surfaces for prohibited identifying content and absolute local checkout paths. Private match terms MUST remain outside version-controlled artifacts and reports.
- The repository MUST remain private. This task MUST NOT create a release, tag, distribution, or public artifact.

## Architecture and impact

- The agent MUST prepare an isolated local mirror and apply a deterministic content transformation to the affected file. A candidate MUST remain local until approval and remote protection changes are confirmed.
- Existing main has 13 commits. The agent MUST preserve logical commits and parent ordering; affected commit hashes and descendants MUST change. References to rewritten commit hashes in maintained documentation MUST be reconciled without reintroducing removed material.
- The agent MUST compare each rewritten tree against its original tree with only the approved transformation applied, and MUST verify author/committer metadata and commit messages. Documentation checks MUST validate links, retained requirement mappings, and retired identifiers.
- The maintenance plan and final evidence MUST use neutral language. A temporary recovery copy MAY exist outside the repository until verification succeeds; it MUST NOT be pushed or released.
- GitHub-managed pull-request refs and cached objects cannot be rewritten through ordinary branch pushes. The agent MUST inspect the existing pull request and old commit accessibility after the rewrite and prepare a support escalation when necessary. A fresh clone alone MUST NOT establish server-side erasure.

## Implementation sequence and security window

1. The human MUST approve this revision's requirements, architecture, and implementation sequence before dependent implementation. Approval MUST explicitly authorize the one-time non-fast-forward main update, local replacement of the old history after verification, and the completion-process exception below.
2. The agent MUST build and verify the isolated candidate, retaining an outside-repository old/new commit map for reconciliation and support. The agent MUST report the candidate revision and verification before requesting a protection change.
3. The human MUST temporarily disable the existing protection ruleset once the candidate is ready. Disabling rather than deleting SHOULD preserve its configuration. The agent MUST NOT change GitHub security settings. Concurrent pushes MUST stop during the update window.
4. Immediately before pushing, the agent MUST recheck remote refs and protection state. The agent MUST push only the approved branch with an explicit force-with-lease tied to the observed old main hash. Unexpected remote changes MUST stop the update for reconciliation. The agent MUST NOT use a mirror push or attempt to overwrite GitHub-managed refs.
5. The human MUST restore the original protection ruleset promptly after the branch update. The agent MUST verify private visibility, the restored controls, and remote main's exact candidate hash.
6. The agent MUST make a fresh clone, scan all fetched history, validate documentation, and inspect GitHub pull-request refs and old commit access. The agent MUST prepare any required GitHub Support request; the human MAY need to submit it with owner authority. The task MUST remain pending while accessible server-side copies require removal, except for the explicit retained-copy disposition recorded below.
7. Once remote verification succeeds, the agent MUST replace stale local history, expire obsolete reflogs and unreachable objects in this checkout and temporary audit copies, and verify the resulting object inventory. Other clone holders MUST replace stale clones rather than merge or push old history. Recovery-copy disposal MUST follow verification, not precede it.

## Approved completion-process exception

Explicit human approval MUST authorize direct history replacement instead of a PR merge for this maintenance operation and MUST exempt this task from release and released-artifact verification. Publishing another source copy would conflict with the remediation purpose. This exception MUST NOT authorize software release, waive customer-context exclusion, relax normal future protections, or count as server-side purge evidence.

## Verification walkthrough

- Setup: the agent MUST capture the old remote main hash, live refs, private visibility, active rules, and clean working-tree state without recording local paths.
- Positive checks: the agent MUST verify transformed content in every candidate revision, unchanged unrelated trees and metadata, valid local Markdown links, and maintained RTM mappings. No runtime behavior changes are planned; package tests MUST NOT be represented as executed.
- Negative checks: a scan against the original research versions MUST detect the targeted passages; a scan against the rewritten versions MUST find none. Unexpected remote-head movement MUST fail the lease check. Old GitHub refs and object URLs MUST be checked separately from the fresh-clone scan.
- Remote commands MUST include `git ls-remote origin`, a fresh `git clone`, and read-only GitHub API inspection. The final report MUST identify the verified main revision, scans and document checks performed, protection state, remaining retained copies, and any support case status.
- Cleanup MUST remove temporary mirrors, private scan tooling, recovery copies, and obsolete local objects only after their recovery purpose is satisfied. Private search terms and removed passages MUST NOT be copied into repository evidence or issue comments.

## Approval and stage record

Requirements: APPROVED. Architecture: APPROVED. Implementation plan: APPROVED. One-time history-update authorization: APPROVED. Completion-process exception: APPROVED. Candidate: VERIFIED. Remote update: VERIFIED. Protection restoration: VERIFIED. Server retention review: residual retention explicitly accepted by the human; no Support submission requested. Local cleanup: verification recorded below.

Human approval recorded 2026-11-16: the human replied "Approved" to the request covering revision 1 requirements, architecture, procedure, one-time force-push, and completion-process exception. This approval MUST remain limited to this remediation.

Rewritten counterpart of the baseline inspected on 2026-11-16: main f0d2aabf08dab8e3d9995ae0a5a1c5846fc0514c; one GitHub pull request; no tags or releases; Protect main ruleset 27396943 active. Evidence commands: `git ls-remote origin` and read-only GitHub repository/ruleset API inspection. Approval MUST identify this document revision or its commit and MUST NOT be inferred from these observations.

## Local candidate verification

Evidence recorded 2026-11-16 against candidate 6cbb38c059d71c8298f55c09d447f469b2f3e6a2: all 15 commits were compared against the approved transformation, with author/committer headers, messages, and parent ordering preserved. All 123 candidate Git objects and all historical paths passed the identifying-content scan. Both original research versions triggered the negative-control scan. All 11 Markdown files passed relative file-link and anchor checks; all 28 RTM requirement rows remain present. Local rewrite and verification scripts executed outside the repository produced a passing report and a private old/new commit map.

This evidence MUST NOT be treated as a remote update or server-side purge. Package behavior tests were not run because this change alters documentation history only. The next metadata-only evidence commit MUST receive the same object, link, and traceability checks before pushing. Protection changes MUST remain the human responsibility; the agent MUST wait for confirmation and verify the live state.

## Remote verification and accepted retention

On 2026-11-16 the agent updated remote main to 2ccc7a73456f3329100946a061c9580fcd47b4ff using an explicit expected-old-head lease. A fresh GitHub clone of that revision passed scans across 16 commits and 128 objects, document file links and anchors, and all 28 requirement mappings. Repository visibility remained private. Evidence: `git ls-remote origin`, fresh `git clone`, and local object/document verification tooling.

On 2026-11-16 the human confirmed protection restoration and declined the prepared Support escalation after being told old commits and the original pull-request head remained accessible. Read-only GitHub API inspection confirmed ruleset 27396943 active, deletion and non-fast-forward blocks, linear history, rebase-only pull requests, resolved conversations, and zero required approvals.

This explicit human decision MUST supersede the server-purge completion condition for this task only. Scope: retained historical GitHub objects and the original closed pull-request reference. Reason: the human declined further escalation. Residual risk: repository-authorized readers MAY retrieve removed historical content through those retained references. No server-side purge MUST be claimed. This disposition MUST be revisited before a visibility change, broader repository distribution, or a new disclosure finding; all other privacy requirements MUST remain in force. The agent MUST NOT submit a Support request or alter GitHub-managed references for this task without a new instruction.

The one-time history-replacement authorization is consumed. Subsequent maintenance MUST follow restored protection and normal PR integration. This neutral closeout MUST be integrated through an agent-reviewed PR; the approved exception from release and released-artifact verification remains limited to this remediation.

Local cleanup on 2026-11-16: obsolete local refs were removed, all checkout reflogs expired, and unreachable objects pruned. The isolated mirrors, fresh audit clone, recovery bundle, private commit map, scan scripts, and unsubmitted Support draft were deleted. A complete remaining-object scan and closeout document checks MUST pass before PR integration. This cleanup does not establish secure physical erasure or GitHub server-side removal.
