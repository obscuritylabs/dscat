# History remediation disposition

The bounded revision 1 procedure (2026-11-16) is historical and its one-time history-update authorization is consumed. The complete approved procedure and candidate evidence remain available with `git show 0b7b824:docs/privacy-remediation.md`. This disposition supports CAP-04/NFR-008 and CAP-05/NFR-006; it MUST NOT authorize another rewrite, remote protection change, or product release.

Research identifiers S04, S05, RES-006, and RES-011 remain retired and MUST NOT be reused. Private identities, match terms, and local paths MUST NOT enter repository evidence. The repository MUST remain private; future work MUST follow normal protected PR integration.

## Approval and stage record

Requirements: APPROVED. Architecture: APPROVED. Implementation plan: APPROVED. One-time history-update authorization: APPROVED. Completion-process exception: APPROVED. Candidate: VERIFIED. Remote update: VERIFIED. Protection restoration: VERIFIED. Server retention review: residual retention explicitly accepted by the human; no Support submission requested. Local cleanup: verification recorded below.

Human approval recorded 2026-11-16: the human replied "Approved" to the request covering revision 1 requirements, architecture, procedure, one-time force-push, and completion-process exception. This approval MUST remain limited to this remediation.

Rewritten counterpart of the baseline inspected on 2026-11-16: main f0d2aabf08dab8e3d9995ae0a5a1c5846fc0514c; one GitHub pull request; no tags or releases; Protect main ruleset 27396943 active. Evidence commands: `git ls-remote origin` and read-only GitHub repository/ruleset API inspection. Approval MUST identify this document revision or its commit and MUST NOT be inferred from these observations.

## Local candidate verification

Recorded 2026-11-16 against candidate `6cbb38c059d71c8298f55c09d447f469b2f3e6a2`: approved transformation, metadata/messages/parent ordering checks across 15 commits; identifying-content scans across 123 objects and historical paths; both original research versions detected by negative controls; links/anchors across 11 Markdown files and all 28 RTM rows checked. Private tooling and the commit map were outside the repository and later deleted; this is historical evidence, not a fresh replay. Runtime tests were not applicable to the history-only change.

## Remote verification and accepted retention

On 2026-11-16 the agent updated remote main to 2ccc7a73456f3329100946a061c9580fcd47b4ff using an explicit expected-old-head lease. A fresh GitHub clone of that revision passed scans across 16 commits and 128 objects, document file links and anchors, and all 28 requirement mappings. Repository visibility remained private. Evidence: `git ls-remote origin`, fresh `git clone`, and local object/document verification tooling.

On 2026-11-16 the human confirmed protection restoration and declined the prepared Support escalation after being told old commits and the original pull-request head remained accessible. Read-only GitHub API inspection confirmed ruleset 27396943 active, deletion and non-fast-forward blocks, linear history, rebase-only pull requests, resolved conversations, and zero required approvals.

This explicit human decision MUST supersede the server-purge completion condition for this task only. Scope: retained historical GitHub objects and the original closed pull-request reference. Reason: the human declined further escalation. Residual risk: repository-authorized readers MAY retrieve removed historical content through those retained references. No server-side purge MUST be claimed. This disposition MUST be revisited before a visibility change, broader repository distribution, or a new disclosure finding; all other privacy requirements MUST remain in force. The agent MUST NOT submit a Support request or alter GitHub-managed references for this task without a new instruction.

The one-time history-replacement authorization is consumed. Subsequent maintenance MUST follow restored protection and normal PR integration. The neutral closeout required integration through an agent-reviewed PR; the approved exception from release and released-artifact verification remains limited to this remediation.

Local cleanup on 2026-11-16: obsolete local refs were removed, all checkout reflogs expired, and unreachable objects pruned. The isolated mirrors, fresh audit clone, recovery bundle, private commit map, scan scripts, and unsubmitted Support draft were deleted. The deleted private verification tooling is unavailable for independent replay; agents MUST NOT claim a fresh replay or reconstruct private match terms. This cleanup does not establish secure physical erasure or GitHub server-side removal.

## Integration evidence boundary

Read-only verification on 2026-11-16 using `gh pr view 2 --json state,mergeCommit` identifies PR #2 as MERGED at ad1b1f6f3149eb5dc436885401bb403f4b1b5fc3. This supports closeout integration only, not a fresh identifying-content scan, secure erasure, or GitHub server-side purge. The historical release exception MUST remain limited to this remediation; later documentation work MUST follow the ordinary completion stages.
