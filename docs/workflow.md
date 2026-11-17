# Phase routing and handoffs

## Coordinator boundary

The coordinator MUST read [AGENTS.md](../AGENTS.md), [index.md](index.md), this workflow, the applicable rows and approval records in [planning-gates.md](planning-gates.md), and the current task record. It MUST route work and report evidence and gates; it MUST NOT perform phase analysis, implementation, verification, or review itself. Detailed policy MUST be loaded by the responsible phase agent through [governance.md](governance.md), [engineering.md](engineering.md), and its phase file. The coordinator MUST route missing decisions under the [approval policy](governance.md#required-sdlc-and-approval-gates), using concrete phase-agent decision packages only for ordinary requirements approval or agent-assessed high-risk architecture approval.

Each phase and each implementation increment MUST use a distinct fresh agent invocation with `fork_turns="none"`. The coordinator MUST provide the bounded handoff below, without inherited transcript, conversational summaries, or unrelated private context. A later phase MUST independently read its cited artifacts rather than treat a previous agent's conclusions as proof. An implementation agent MUST NOT serve as its own verification or independent-review agent. A retry after substantive correction MUST use fresh phase agents and updated revision/evidence references.

If fresh-agent tooling is unavailable or capacity prevents dispatch, the coordinator MUST report the affected phase as blocked and retain the next gate. It MUST NOT simulate freshness through role switching, context-reset claims, or a second pass by the same agent. It MAY resume dispatch when capacity becomes available; a human MAY explicitly revise the workflow, but missing tooling MUST NOT silently waive it.

## Bounded handoff

Each dispatch and return MUST identify the following sections in the task record or a linked handoff artifact. Handoffs MUST contain only routing context and artifact references plus concise unresolved decisions; full documents and transcripts MUST NOT be copied into them.

| Section | Required content |
| --- | --- |
| Identity and revision | Task/increment, phase, exact source commit, dirty state and content digest where applicable |
| Scope and authority | Requirement/capability IDs, acceptance anchors, included work, excluded work, approved or agent-authorized document revisions, decision references and dates; unavailable dispositions explicitly PENDING |
| Required reading | Exact document paths and section anchors needed for this phase, including the phase file and shared policy |
| Ownership | Allowed files/symbols, shared-file constraints, assigned agent/invocation identity, permitted mutations |
| Inputs and outputs | Source artifacts, required deliverables, locations, exact artifact hashes and reproducible evidence commands/results or PENDING |
| Findings and disposition | Failures, limitations, unresolved assumptions, superseded evidence and affected gates; privacy-sensitive findings only where authorized |
| Next gate | Pass/fail/blocked result, actual completion stage, next phase, applicable requirements/high-risk architecture decision or autonomous readiness gate |

The receiving agent MUST verify the revision and authority scope before dependent work and reject an incomplete or stale handoff. A dirty-tree digest MUST identify all relevant inputs; a commit alone MUST NOT stand for concurrent uncommitted edits.

## Phase routing

The coordinator MUST use the following routing table. Each phase MUST return its handoff before the next dependent phase starts. Existing approvals MAY be reused only for their recorded scope and revision; routing MUST NOT reopen unchanged approved product decisions merely to satisfy a phase name.

| Phase | Agent instructions | Exit and next gate |
| --- | --- | --- |
| Requirements | [requirements](phases/requirements.md) | Exact scope and acceptance ready for requirements disposition under the approval policy |
| Architecture | [architecture](phases/architecture.md) | Requirements disposition satisfied; exact design risk assessment and architecture disposition |
| Planning | [planning](phases/planning.md) | Architecture disposition satisfied; increments ready for agent plan authorization |
| Implementation | [implementation](phases/implementation.md) | One agent-authorized increment implemented and self-tested; fresh verification |
| Verification | [verification](phases/verification.md) | Acceptance evidence for exact increment; fresh review when due, then integration |
| Review | [review](phases/review.md) | Independent findings/disposition or existing explicitly scoped waiver; integration when applicable checks pass |
| Integration | [integration](phases/integration.md) | PR/rebase merge verified on remote main; release preparation |
| Release preparation | [release](phases/release.md) | Verified candidate and recorded standing-delegation exercise before publishing |
| Post-release verification | [release](phases/release.md) in a separate fresh invocation | Downloaded released artifacts verified; completion only after all seven stages |

Independent review SHOULD occur periodically under [governance.md](governance.md). Review routing MUST record whether review is required for this increment, already satisfied for the exact applicable content, or covered by an existing explicit human waiver. The coordinator MUST NOT invent a waiver or call self-review independent review.

## Failure, reopening, and shared state

A failed verification or review MUST return the affected increment to implementation; changes to scope, acceptance, architecture, or plan MUST first return to the earliest affected phase gate with impact analysis under the approval policy. Corrections MUST invalidate affected downstream evidence. Integration conflicts or changed artifacts MUST trigger affected verification again. Release or post-release failure MUST leave the task incomplete, follow the approved failure policy, and route corrections through implementation, verification, integration, and a new verified release under standing delegation as applicable. Historical evidence MUST remain attributed rather than rewritten as current success.

Agents share the filesystem. The coordinator MUST serialize dependent mutations and shared-file writes, assign disjoint ownership before parallel work, preserve unrelated human changes, and recheck Git status/revision at handoff. It MUST NOT change branches or integrate while another agent relies on the same checkout state. Parallel reads MAY proceed against a stable identified revision; concurrent disjoint writes MUST be reconciled and verified as one identified result before dependent work.

All tasks, including documentation tasks, MUST retain the seven completion stages in [governance.md](governance.md): planning readiness, implementation, tests, local acceptance verification, remote-main PR integration, authorized published release, and verification from downloaded released artifacts. A phase pass, merge, or draft release MUST NOT mean completion. Human approval requests MUST follow only the requirements and high-risk architecture rules; implementation-plan and all other SDLC readiness gates MUST remain autonomous.
