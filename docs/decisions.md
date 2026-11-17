# Current decisions and source pointers

## Current authority

[Planning gates](planning-gates.md) is authoritative for current approval status. This record retains decision provenance and rationale; requirements and operating policies own their substantive rules. Human-derived decisions were recorded on 2026-11-16 unless stated otherwise. Accepted directions MUST NOT approve detailed proposals or dependent implementation.

D records below are current consolidated source pointers, not unaltered interview transcripts. Original wording is available through `git show 0b7b824:docs/decisions.md`. Stable anchors MUST remain available; Git history preserves previous wording.

## Decisions

### DEC-001

| Source | Current authoritative home |
| --- | --- |
| <a id="d01"></a>D01 | [SPEC-001](requirements.md) |
| <a id="d02"></a>D02 | [NFR-001](requirements.md#nfr-001), [NFR-002](requirements.md#nfr-002), [NFR-003](requirements.md#nfr-003), [NFR-004](requirements.md#nfr-004); [engineering constraints](engineering.md#project-and-engineering-constraints) |
| <a id="d03"></a>D03 | [FR-003](requirements.md#fr-003), [FR-004](requirements.md#fr-004) |
| <a id="d04"></a>D04 | [NFR-006](requirements.md#nfr-006); [approval and delivery gates](governance.md#required-sdlc-and-approval-gates) |
| <a id="d05"></a>D05 | [NFR-006](requirements.md#nfr-006); [authority and formatting policy](governance.md#authority-and-statement-conventions) |
| <a id="d06"></a>D06 | [NFR-005](requirements.md#nfr-005); [approval and delivery gates](governance.md#required-sdlc-and-approval-gates) |
| <a id="d07"></a>D07 | [NFR-007](requirements.md#nfr-007) |
| <a id="d08"></a>D08 | [NFR-006](requirements.md#nfr-006); [Git/version policy](governance.md#git-versions-and-releases) |
| <a id="d09"></a>D09 | [NFR-006](requirements.md#nfr-006); [Git/version policy](governance.md#git-versions-and-releases) |
| <a id="d10"></a>D10 | [NFR-006](requirements.md#nfr-006); [approval and delivery gates](governance.md#required-sdlc-and-approval-gates) |

### DEC-002

Coverage target and delegated narrow exceptions: [NFR-003](requirements.md#nfr-003) and [engineering constraints](engineering.md#project-and-engineering-constraints).

### DEC-003

On-disk planning and any explicit issue migration: [approval and delivery gates](governance.md#required-sdlc-and-approval-gates).

### DEC-004

Exact ID grammar, normalization, encodings, and offline resource closure remain architecture deliverables under [planning gates](planning-gates.md#required-gate-deliverables).

### DEC-005

Full tool/dependency/build configuration remains subject to implementation-plan approval. Initialization permission covers license metadata and the dependency-age cutoff only; metadata MUST NOT be represented as a completed package or CLI.

### DEC-006

| Source | Current authoritative home |
| --- | --- |
| <a id="d11"></a>D11 | [FR-003](requirements.md#fr-003), [FR-004](requirements.md#fr-004) |
| <a id="d12"></a>D12 | [FR-001](requirements.md#fr-001), [FR-006](requirements.md#fr-006) |
| <a id="d13"></a>D13 | [FR-007](requirements.md#fr-007) |
| <a id="d14"></a>D14 | [FR-008](requirements.md#fr-008) |
| <a id="d15"></a>D15 | [FR-005](requirements.md#fr-005), [NFR-009](requirements.md#nfr-009) |
| <a id="d16"></a>D16 | [FR-002](requirements.md#fr-002) |
| <a id="d17"></a>D17 | [NFR-001](requirements.md#nfr-001), [NFR-010](requirements.md#nfr-010), [NFR-013](requirements.md#nfr-013) |
| <a id="d18"></a>D18 | [NFR-003](requirements.md#nfr-003); [engineering constraints](engineering.md#project-and-engineering-constraints) |
| <a id="d19"></a>D19 | [NFR-011](requirements.md#nfr-011), [NFR-012](requirements.md#nfr-012) |
| <a id="d20"></a>D20 | [NFR-013](requirements.md#nfr-013) |
| <a id="d22"></a>D22 | [NFR-014](requirements.md#nfr-014); [catalog and licensing policy](engineering.md#catalog-behavior-and-licensing) |
| <a id="d23"></a>D23 | [NFR-015](requirements.md#nfr-015); [Git/version policy](governance.md#git-versions-and-releases) |

### DEC-007

Repository access was tool-verified on 2026-11-16: the exact repository invitation was accepted through the GitHub API; permissions reported pull=true and push=true, visibility private, and no initial remote refs. Access MUST NOT imply release or visibility-change authorization.

### DEC-008

Initialization scope and incomplete CLI status: [DEC-005](#dec-005). Licensing requirements: [NFR-014](requirements.md#nfr-014).

### DEC-009

Proprietary ownership and written-authorization terms: [LICENSE](../LICENSE). Required notices and distribution checks: [NFR-014](requirements.md#nfr-014) and [DEC-035](#dec-035).

### DEC-010

Protection export handling and consumed preparation authority: [REPO-001/002](repository-policy.md).

### DEC-011

Active protection and CI-change authorization: [REPO-003–006/012](repository-policy.md).

### DEC-012

| Source | Current authoritative home |
| --- | --- |
| <a id="d24"></a>D24 | [FR-002](requirements.md#fr-002) |
| <a id="d25"></a>D25 | [FR-007](requirements.md#fr-007) |
| <a id="d26"></a>D26 | [NFR-015](requirements.md#nfr-015); [repository policy](repository-policy.md) |

### DEC-013

Dated remote activation and local-file evidence: [REPO-012](repository-policy.md).

### DEC-014

Canonical persistence choice: [DEC-020](#dec-020); detailed design remains at the architecture gate.

### DEC-015

Conventional legal formatting, without planning annotations: [authority and formatting policy](governance.md#authority-and-statement-conventions). Ownership and proprietary terms: [LICENSE](../LICENSE).

### DEC-016

Conventional configuration formatting without planning annotations: [authority and formatting policy](governance.md#authority-and-statement-conventions). This editorial instruction does not change configuration values or behavior.

### DEC-017

Sparse planning provenance and conventional ordinary artifacts: [authority and formatting policy](governance.md#authority-and-statement-conventions). Stable requirements and RTM links remain required.

### DEC-018

Local verification as primary gate, minimal Actions, and installable GitHub Releases: [distribution policy](governance.md#local-verification-and-distribution).

### DEC-019

All seven completion stages: [definition of done](governance.md#definition-of-done).

### DEC-020

Canonical JSON and organized flat-file persistence are the accepted direction in [FR-008](requirements.md#fr-008). Rationale: isolate the canonical migration boundary so a later database adapter can replace persistence. Exact fields, file layout, architecture, and plan are not approved by this decision.

### DEC-021

Conditional JSON-LD serialization for RDF exports: [NFR-019](requirements.md#nfr-019). This selects neither additional RDF exports nor RDF for canonical JSON.

### DEC-022

Agent-owned routine delivery and human planning/release authority: [autonomous delivery ownership](governance.md#autonomous-delivery-ownership). Trunk-based development is human-directed; PRs are the agent-selected protection mechanism in [repository policy](repository-policy.md).

### DEC-023

Accepted initial Excel layout: Instructions and Datasets sheets, OPTIONAL Fields and Details/Quality sheets, one dataset per main-sheet row. Required submitter-supplied core: [FR-006](requirements.md#fr-006). Exact ID syntax and normalization remain architecture work. Excel obligations are conditional under SPEC-007.

### DEC-024

Accepted capacity direction: [FR-007](requirements.md#fr-007). Detailed field encodings remain architecture work; [capacity proposals](intake-proposals.md#draft-capacity-policy) are not approved by this decision.

### DEC-025

Human approval covered the five import/output rules presented after commit `6273f5a`: discovery, exact selected-input snapshots, explicit replacement with failure preservation, byte determinism, and normalized-ID duplicate handling. Current behavior: [FR-002](requirements.md#fr-002), [FR-005](requirements.md#fr-005), [FR-011](requirements.md#fr-011), [NFR-009](requirements.md#nfr-009). Duplicate comparison MUST use validated normalized metadata excluding source locations, while retaining all source locations for diagnostics. Exact normalization and publication design remain architecture work.

### DEC-026

Permitted normal Excel formulas, practical interface validation, and independent safe validation: [FR-010](requirements.md#fr-010). Formula handling and validation coverage remain architecture work.

### DEC-027

Accepted ODCS 3.2.0 scope and validated shared configuration: [FR-004](requirements.md#fr-004). Exact mappings and pinned resources remain architecture work.

### DEC-028

Portability targets and installation: [NFR-001](requirements.md#nfr-001). These are targets, not a mandatory verified-platform matrix. Excel verification arrangements remain deferred without waiving acceptance; reports MUST identify actual verified environments.

### DEC-029

An OPTIONAL Lineage sheet is the accepted Excel layout for the OPTIONAL manually supplied lineage scope: [FR-012](requirements.md#fr-012). Detailed fields, reference handling, and mappings remain architecture work.

### DEC-030

Agents MUST notify the human of a concrete workbook usability/complexity limitation before planning an alternative. Replacement requires affected planning approvals; no replacement is selected.

### DEC-031

Initial Excel SHOULD choice and technology-neutral capability scope: [SPEC-001](requirements.md). A guided form MAY be considered later; no replacement mechanism or state-machine design is selected.

### DEC-032

Conditional workbook obligations and replacement change control: [SPEC-007](requirements.md).

### DEC-033

Positive and negative boundary/business-rule verification and failure evidence: [NFR-002](requirements.md#nfr-002), [NFR-003](requirements.md#nfr-003), [NFR-005](requirements.md#nfr-005), [NFR-007](requirements.md#nfr-007). Coverage totals do not replace behavior verification.

### DEC-034

Current scope excludes the unimplemented catalog viewer; future scope and scheduling are undecided. The human requested clean removal without a requirement retirement entry and preservation of remaining IDs.

### DEC-035

The human individually approved [NFR-014](requirements.md#nfr-014) wording, without changing license terms or approving the complete baseline, implementation, or release. The approved CLI notice MUST read: “© Obscurity Labs. Proprietary software. See LICENSE for terms.” Source/built-distribution notice verification and CLI implementation remain subject to their gates. Legal formatting follows [authority and formatting policy](governance.md#authority-and-statement-conventions).

### DEC-036

The requested NFR-015 editorial wording focuses on active repository policy and alignment verification. It grants no remote-protection change authority; [repository policy](repository-policy.md) retains current safeguards and evidence.

### DEC-037

The full-document QA/QC instruction is implemented by [documentation procedure](documentation-qa.md). Integration evidence: [PR #12](https://github.com/obscuritylabs/dscat/pull/12), main `f77a63193da43f03c2f67ffca7599ce31d21690a`. This is governance authority, not product/release approval.

### DEC-038

The human directly requested planning-document reconciliation and recurrence controls under [documentation procedure](documentation-qa.md). Findings MUST remain conversational; corrected specifications and procedures MAY be maintained on disk. This authority does not approve draft technical policies or any product/release gate.

### DEC-039

[FACT; HUMAN_DERIVED; 2026-11-16] The human explicitly instructed that everything in requirements.md be marked approved and ready to start, with rtm.md review next and decisions.md review afterward. Agents MUST record approval of the complete docs/requirements.md baseline at commit `00c3535236028197805c0199401321631c709cd0`, covering SPEC-001–SPEC-007, all 30 FR/NFR requirements, and their acceptance criteria. This decision MUST supersede prior pending-baseline statements within that scope. Requirements are ready for architecture planning; architecture and implementation-plan approval MUST still precede dependent implementation. This approval MUST NOT authorize release or approve detailed proposals in other documents.

### DEC-040

[FACT; HUMAN_DERIVED; 2026-11-16] The human explicitly approved docs/rtm.md at commit `110b441b60c3404f70ddf1ffde44243f7b934d33` while stating that the individual mappings were not personally verified and relying on agent verification. Agents MUST record approval of the RTM baseline separately from verification evidence; this approval MUST NOT be represented as human verification of the links or mappings. Agents MUST maintain and check traceability under NFR-006 and the documentation QA/QC procedure. Draft designs and unperformed implementation, tests, and acceptance verification MUST retain their existing status. Decision-log review, architecture approval, implementation-plan approval, and release authorization MUST remain pending. This decision MUST supersede prior pending RTM-review statements without changing approved requirements or approving other document proposals.

### DEC-041

[FACT; HUMAN_DERIVED; 2026-11-16] The human explicitly approved docs/decisions.md and clarified that approval covers its committed baseline from [PR #15](https://github.com/obscuritylabs/dscat/pull/15) at commit `0b7b82459a7136922bdc2d8439839553114b6905`, excluding subsequent uncommitted changes. Agents MUST record approval of that decision-log baseline separately from verification evidence. Existing proposal and assumption classifications and historical supersession MUST remain intact; baseline approval MUST NOT convert proposals or assumptions into accepted technical decisions or reactivate superseded instructions. This decision MUST supersede prior pending decision-log-review statements only within that scope. Architecture approval, implementation-plan approval, and release authorization MUST remain PENDING; approval MUST NOT extend to other document proposals or authorize dependent product implementation.


### DEC-042

[FACT; HUMAN_DERIVED; 2026-11-16] The human requested inclusion of the recommended research items and data-mesh findings in project planning. This authorizes preparation, review, and protected-PR integration of the [proposed requirements revision and impact package](research-additions.md), not approval of an exact new requirements revision, architecture, implementation plan, product implementation, or release. The original DEC-039/040/041 approvals MUST remain attributed to their exact baseline revisions. At this decision, new requirements FR-013–FR-018 and NFR-020–NFR-022 and refinements to FR-012/NFR-011/NFR-012 awaited renewed requirements approval; current status follows DEC-044. Optional detail MUST preserve the four-field intake core and ODCS 3.2.0. Explicit scope boundaries MUST follow the impact package; data-mesh guidance MUST NOT be represented as implementation of a mesh platform.

### DEC-043

[FACT; HUMAN_DERIVED; 2026-11-16] The human approved these interview scope decisions: first-release DCAT-US 3.0 followed by ODCS 3.2.0, both required; later a separate W3C DCAT 3 capability; then manually supplied lineage capture/export using PROV-O semantics; then ODPS product metadata/export with dataset/ODCS links, recorded/validated lifecycle states and transitions, and described/validated input/output ports (interfaces/access metadata); lastly DCAT-US 1.1. External lineage ingestion and automatic discovery remain deferred. ODPS excludes provisioning, deployment and live endpoint testing. Valid intake missing target-specific facts blocks only the affected target; invalid intake blocks all exports by default. This decision supersedes the earlier optional-first-release DCAT-US 1.1 direction and first-release lineage scheduling in FR-003/FR-012, and the research-only ODPS boundary, only for this stated scope. It approves these decisions as stated on this date, not an unseen exact consolidated requirements revision, the remaining DEC-042 proposals, architecture, implementation plan, implementation or release. Exact baseline approvals DEC-039/040/041 remain attributed to their original revisions. The consolidated candidate required renewed requirements approval, subsequently recorded in DEC-044. Acceptance and sequencing are maintained in requirements SPEC-005 and FR-012/019/020/021.

### DEC-044

[FACT; HUMAN_DERIVED; 2026-11-17] The human explicitly approved the exact consolidated requirements and research impact package at commit `69b686a3d0b1da49290ca37d577d46fb8b63dbfb`. Approval covers docs/requirements.md SPEC-001–SPEC-007, all 42 FR/NFR requirements and acceptance criteria, and docs/research-additions.md additions, refinements, sequencing, impacts and exclusions. Agents MUST preserve DEC-039/040/041 authority at its original revisions and MUST treat this decision as superseding requirements-approval PENDING/proposed labels in the approved source artifacts and dependent summaries only. Those two artifacts retain their exact approved bytes; their embedded approval-status labels describe the pre-approval source revision, not an unresolved current requirements gate. No technical scope changes are made. This approval permits architecture preparation against the consolidated requirements; it MUST NOT approve detailed architecture proposals, the implementation plan, product implementation, release, or unverified RTM mappings. Current approval status MUST follow [planning gates](planning-gates.md).
