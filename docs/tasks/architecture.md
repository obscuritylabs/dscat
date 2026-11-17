# Architecture preparation handoff

## Identity and revision

Task: full architecture candidate preparation; phase: ARCHITECTURE. Exact correction source: `6cb01d395ffb8cbb25c38576ff30a9fc66766aeb`, tree `9837e2a1ee8ee851d5756190d18a7f0add14fe05`, clean at intake. Dedicated branch: `docs/architecture-candidate`. The exact candidate commit/tree, dirty state and sorted relative-path/NUL/bytes/NUL SHA-256 digests MUST accompany the returned handoff and review evidence; this task MUST NOT embed its own recursive content digest. Prior protected integration evidence remains [PR #20](https://github.com/obscuritylabs/dscat/pull/20), not a new architecture verification claim.

## Scope and authority

DEC-044 approves requirements SPEC-001–SPEC-007, all 42 FR/NFR requirements/acceptance and the impact package at `69b686a3d0b1da49290ca37d577d46fb8b63dbfb` on 2026-11-17. Those two approved artifact byte streams MUST remain unchanged. This task prepares design only: first-release DCAT-US 3.0 followed by ODCS 3.2.0, typed boundaries/canonical/storage/intake/compatibility/security and later-capability extension gates in the approved order. No product implementation, product dependency selection/installation, architecture approval, implementation-plan execution, release, remote policy change or public disclosure is included. Temporary isolated research validators and synthetic resource probes MAY establish architecture evidence; they MUST NOT count as product tests.

## Required reading and ownership

Required reading: AGENTS.md; index/workflow architecture route and bounded handoff; phases/architecture.md; governance authority, approvals, traceability and Git/completion sections; engineering; planning gates; approved requirements/impact; applicable decisions; intake/canonical/research; documentation QA and repository policy. Dependencies MUST be followed as applicable.

Original preparation invocation `/root/architecture_prepare` owned architecture.md, architecture-standards.md, architecture-assurance.md, evidence/architecture resources, this task and dependent RTM/index/gate/research/proposal navigation reconciliation. Fresh delegated standards analysis `/root/architecture_prepare/schema_research` owns standards/evidence; assurance analysis `/root/architecture_prepare/security_design` owns assurance. Shared writes MUST be serialized and reconciled by preparation. Correction invocation `/root/arch_correct` owns targeted core/assurance/standards and task corrections. None of those drafting invocations MUST establish independent review of its own content. The unrelated approved requirements/impact and existing product files MUST remain unchanged.

## Inputs and outputs

| Artifact | Responsibility / evidence |
| --- | --- |
| [Architecture](../architecture.md) | Typed models, normalization, first-release field encodings, capacity, persistence/publication, compatibility and later extension gates |
| [Standards design](../architecture-standards.md) | Exact first-release resource closure/licenses/resolver, target mappings and research-only minimum demonstration; evidence limitations MUST remain explicit |
| [Assurance design](../architecture-assurance.md) | Threat model, measured resource selection, diagnostics, independent review/readiness/projection, privacy/accessibility and secure development/support |
| [RTM](../rtm.md) | All 42 requirement design mappings; implementation/tests/evidence MUST remain PENDING where unperformed |
| [Planning gates](../planning-gates.md), [index](../index.md), [intake](../intake-proposals.md), [canonical](../canonical-model.md) | Authoritative status/navigation and replaced competing partial proposals |

Reproducible preparation checks MUST include `python3 docs/evidence/architecture/verify_documents.py` ([adapted retained PR #19/#20 recipe](../evidence/architecture/verify_documents.py)), all seven synthetic negative controls, `git diff --check`, exact requirements/impact byte comparison with approved source, evidence-resource hash/closure checks, research-only demonstration commands from the standards/assurance documents, and staged privacy/scope review. A recipe referenced only from `/tmp` MUST be retained with final verification evidence before integration. Actual commands/results MUST identify exact tested candidate and resources; an unexecuted command MUST remain PENDING.

## Findings and disposition

The first-release design MUST keep label-only four-field intake valid without inventing export-required facts; shared configuration MUST explicitly supply missing associations/versions. Generic descriptions MUST NOT become unsupported intended-use commitments. Canonical preservation MUST remain independent of projection loss and publication authority. Later capabilities MUST retain milestone-specific detailed approval exits; their missing resource pins MUST NOT imply first-release conformance or delay it.

First-release approval limitation: both initial target mappings intentionally omit even explicitly supplied quality/service commitments, preserve them canonically and report loss. The standards loss matrix explains the FR-004 necessary-condition and FR-018 documented-loss interpretation. The human architecture decision MUST explicitly cover this proposed limitation; no waiver or blanket conformance approval is inferred.

Fresh full semantic coverage at the correction source covered all 90 maintained artifacts in four bounded partitions (5 core, 59 standards/evidence, 7 assurance, 19 controls) against all nine matrix areas, followed by distinct reconciliation. That review confirmed three blocking corrections: inconsistent Details header, missing closed service-link vocabulary, and canonical-only publication approval scope. The candidate now proposes consistent grouped rows, closed service references and canonical/configuration/derived-target approval bindings with planned changed-configuration/mapping rejection cases. This is author correction disposition only: affected independent review and distinct reconciliation MUST rerun against the exact corrected candidate before readiness is claimed. Prior coverage MAY be retained only for byte-identical artifacts with unchanged applicability.

Preparation self-review MUST remain distinct from independent QA. Full bounded semantic QA, distinct reconciliation, exact integration/release evidence and human architecture approval remain PENDING. Product/parser/desktop/platform acceptance MUST NOT be inferred from research-only evidence. Concrete limitations or unresolved material choices discovered by fresh review MUST block the affected gate rather than fabricate readiness.

## Stage ledger and next gate

| Completion stage | Actual current evidence/status |
| --- | --- |
| Planned | Architecture preparation authorized against DEC-044; human architecture and subsequent implementation-plan approval PENDING |
| Implemented | Proposed documentation package prepared on dedicated branch; no product implementation |
| Tested | Preparation self-check PASS: 35 document/license files, 42 requirement/RTM rows, all seven negative controls, whitespace and approved-byte identity; 45-resource/42-schema closure, minimum and detailed offline schema/graph experiments PASS. Exact candidate identities MUST accompany the returned handoff; independent QA PENDING |
| Locally verified | Source full coverage and distinct reconciliation identified three blockers; author corrections prepared; fresh affected review and distinct reconciliation of corrected candidate PENDING; no product acceptance claim |
| Remote-main integration | PENDING protected PR integration of this candidate; prior PR #20 is input evidence only |
| Published release | PENDING explicit human authorization and verified main/artifacts |
| Released-artifact verification | PENDING publication and actual downloaded-source verification |

Next gate: full fresh bounded documentation QA and distinct reconciliation, corrections as needed, protected integration with exact revision evidence, then exact-revision human architecture approval. The coordinator MUST inventory all maintained documents and allocate all nine semantic matrix areas where applicable, with bounded reviewers covering: (A) core architecture/intake/canonical/requirements boundary and compatibility; (B) standards/evidence/research/RTM and mapping semantics; (C) assurance/engineering/delivery/security/accessibility; (D) control/gates/decisions/tasks and any remaining unchanged maintained documents. Identical prior coverage MAY be retained only after byte identity and unchanged applicability are explicitly established. A distinct fresh reconciliation reviewer MUST inspect the combined exact candidate and all dispositions. This task remains incomplete until all seven stages have evidence.
