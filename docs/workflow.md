# Phase routing and handoffs

## Coordinator boundary

Agents MUST classify work using [task scope and proportionality](governance.md#task-scope-and-proportionality) and its completion condition before dispatch. One implementer MAY complete ordinary maintenance or approved implementation directly. A coordinator is OPTIONAL; when used, it MAY also implement and run checks, but MUST NOT claim independent review of its own work.

Fresh phase agents with `fork_turns="none"` MUST be used only for material requirements, architecture, and implementation-plan decisions, and required independent review or release verification. Routine increments and corrections MAY retain their implementer. Reviewers MUST independently inspect relevant artifacts; they MUST NOT inherit an implementer's conclusions as proof. One independent reviewer MAY perform acceptance verification, semantic review, and cross-document reconciliation for a bounded change.

Unavailable fresh-agent tooling MUST block only the phase that requires independence. Other authorized work MAY continue. Agents MUST report unavailable independent evidence rather than simulate it. Read-only questions and routine low-risk edits MUST NOT be blocked on fresh-agent capacity.

## Bounded handoff

A handoff is REQUIRED only when work crosses agent ownership. It MUST state the requested outcome, included/excluded scope, source revision or relevant file identities, allowed mutations, acceptance checks, known blocking findings, and the next completion condition. Existing applicable requirements/design authority MUST be linked where relevant. Conversation transcripts and unrelated private context MUST NOT be copied.

A concise dispatch message or PR MAY supply the handoff; an additional repository task record MUST NOT be required for ordinary work. A committed candidate SHOULD use its commit identity. Uncommitted review inputs MUST use a digest of the relevant files, not the entire unrelated dirty tree. A stale affected input MUST invalidate only the evidence that depends on it. Read-only advice MAY describe the observed working state without an exact-candidate readiness claim.

## Phase routing

The task class determines applicable phases; this table is navigation, not a checklist requiring every task to execute every phase. Read-only advice ends with an answer. Maintenance uses implementation, applicable checks/review, and the requested delivery. Approved product implementation reuses existing requirements and design readiness. A material decision enters only the earliest affected phase below; unaffected phases and approvals MUST NOT reopen.

| Phase | Agent instructions | Applicable exit |
| --- | --- | --- |
| Requirements | [requirements](phases/requirements.md) | Material scope/acceptance decision receives the disposition required by approval policy |
| Architecture | [architecture](phases/architecture.md) | Material design decision receives risk assessment and disposition |
| Planning | [planning](phases/planning.md) | Material new/revised execution plan is ready under existing scope |
| Implementation | [implementation](phases/implementation.md) | Bounded change and applicable self-checks complete |
| Verification | [verification](phases/verification.md) | Applicable acceptance checks pass; MAY be combined with independent review |
| Review | [review](phases/review.md) | Required independent findings resolved for the affected candidate |
| Integration | [integration](phases/integration.md) | Requested protected PR/rebase delivery verified on remote main |
| Release preparation | [release](phases/release.md) | Separate release task has verified assets and standing-delegation evidence |
| Post-release verification | [release](phases/release.md) | Independent verification of downloaded released artifacts completes that release task |

## Review applicability

Independent review MUST cover changes to security/privacy controls, destructive or persistent data behavior, supported compatibility contracts, substantive governance policy, and release artifacts. One fresh reviewer MAY cover all applicable concerns for an ordinary bounded change. Mechanical edits and low-risk fixes within approved behavior MAY use self-review plus focused checks; agents MUST identify that review accurately. Broader or specialist review SHOULD be used only for a concrete risk or explicit acceptance requirement.

A review finding MUST identify an unmet authorized criterion, a concrete defect introduced or exposed by the change, or a material security/compatibility dependency. Suggestions and unrelated defects MUST remain nonblocking follow-ups. Reviewers MUST NOT add acceptance criteria or reopen approved decisions merely to satisfy a phase name. Corrections MUST receive affected rechecks; a new reviewer is REQUIRED only if independence was lost or specialist expertise is needed, not for every retry.

## Failure, reopening, and shared state

A failed check MUST return only the affected work to correction. Material changes to scope, acceptance, compatibility, or security design MUST receive impact analysis and route to the earliest affected decision under the approval policy. Editorial changes, factual status updates, unrelated dirty files, and commit/hash changes alone MUST NOT restart planning or invalidate unchanged evidence. Agents MUST rerun affected checks after a correction or integration conflict; successful checks MUST NOT be repeated without changed inputs or a concrete unresolved concern.

Agents MUST stop expanding scope once the requested acceptance and delivery conditions are satisfied. After two unsuccessful correction/review cycles for the same blocker, they MUST identify the root cause and either make a concrete bounded correction or report the exact blocker and completed work. They MUST NOT repeat the same approach, invent gates, or claim success. A time or iteration budget MUST NOT waive security or acceptance criteria. Unrelated findings MUST remain separate follow-ups; agents MUST obtain a scope decision only when a genuine dependency prevents the requested outcome.

Agents share the filesystem. Dependent mutations and shared-file writes MUST be serialized, unrelated changes preserved, and affected inputs rechecked before handoff or integration. Agents MUST NOT change another worker's checkout state; isolated branches/worktrees SHOULD be used for concurrent work. Disjoint changes MAY proceed independently. Read-only diagnosis MUST NOT chase unrelated concurrent edits through repeated digest gates.

The [definition of done](governance.md#definition-of-done) owns task and release completion. Existing phase/task records MUST be read under this current routing policy: historical full-review, fresh-phase, seven-stage, and metadata-review instructions MUST NOT reintroduce superseded universal obligations. Explicit product acceptance criteria, actual release commitments, failed checks, and privacy/security constraints MUST remain in force. Existing records MUST NOT be mass-rewritten or relabeled PASS merely to apply the new policy.
