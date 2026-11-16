# Requirements traceability matrix

- RTM-001 [FACT; LLM_INFERENCE] Each row MUST trace the requirement in [requirements.md](requirements.md) to a capability and artifacts; PENDING MUST indicate work not performed, never a pass. Requirement classifications MUST be inherited from the referenced requirement.
- RTM-002 [FACT; LLM_INFERENCE] Requirement sources MUST reference DEC-001, DEC-006, DEC-010, DEC-012, DEC-018, DEC-019, DEC-020, DEC-021, or DEC-022 and their D-numbers in [decisions.md](decisions.md). Design, code, tests, and evidence MUST be added before a row can become verified.

| Requirement | Capability | Source | Acceptance | Design | Implementation | Tests | Evidence/status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [FR-001](requirements.md) | CAP-01 | D01,D12,D17,DEC-023 | [FR-001](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [FR-002](requirements.md) | CAP-02 | D01,D16,D24,DEC-025 | [FR-002](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [FR-003](requirements.md) | CAP-03 | D03,D11 | [FR-003](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [FR-004](requirements.md) | CAP-03 | D03,D11,DEC-027 | [FR-004](requirements.md) | PENDING | PENDING | PENDING | DRAFT; 0.1.0 |
| [FR-005](requirements.md) | CAP-01 | D15,DEC-025 | [FR-005](requirements.md) | PENDING | PENDING | PENDING | DRAFT; 0.1.0 |
| [FR-006](requirements.md) | CAP-01 | D12,DEC-023 | [FR-006](requirements.md) | PENDING | PENDING | PENDING | DRAFT; 0.1.0 |
| [FR-007](requirements.md) | CAP-06 | D13,D25,DEC-024 | [FR-007](requirements.md) | PENDING | PENDING | PENDING | DRAFT; 0.1.0 |
| [FR-008](requirements.md) | CAP-03 | D14,DEC-020 | [FR-008](requirements.md) | [Canonical model notes](canonical-model.md) | PENDING | PENDING | Direction approved; implementation PENDING |
| [FR-010](requirements.md) | CAP-01 | DEC-026 | [FR-010](requirements.md) | PENDING; INTAKE-019 | PENDING | PENDING | Interview decision accepted; baseline approval PENDING |
| [FR-011](requirements.md) | CAP-02 | DEC-025 | [FR-011](requirements.md) | PENDING; INTAKE-010 | PENDING | PENDING | Interview decision accepted; baseline approval PENDING |
| [FR-012](requirements.md) | CAP-01, CAP-02, CAP-03 | DEC-029 | [FR-012](requirements.md) | [Lineage design impact](canonical-model.md#lineage-scope-and-design-impact); INTAKE-020 | PENDING | PENDING | Interview scope accepted; baseline and architecture approval PENDING |
| [NFR-001](requirements.md) | CAP-04 | D02,DEC-028 | [NFR-001](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [NFR-002](requirements.md) | CAP-02 | D02,DEC-033 | [NFR-002](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [NFR-003](requirements.md) | CAP-04 | D02,D18,DEC-033 | [NFR-003](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [NFR-004](requirements.md) | CAP-04 | D02 | [NFR-004](requirements.md) | [Engineering constraints](../AGENTS.md#project-and-engineering-constraints) | pyproject.toml tool.uv.exclude-newer | TOML parsing; lock checks pending | Configured; lock verification PENDING |
| [NFR-005](requirements.md) | CAP-04 | D06,D19,DEC-033 | [NFR-005](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [NFR-006](requirements.md) | CAP-05 | D04,D05,D08,D09,D10,DEC-016,DEC-017,DEC-019,DEC-022 | [NFR-006](requirements.md) | AGENTS.md | AGENTS.md; docs/index.md; docs/decisions.md; docs/requirements.md; docs/rtm.md; docs/research.md | Document review | DRAFT; human approval pending |
| [NFR-007](requirements.md) | CAP-05 | D07,DEC-033 | [NFR-007](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [NFR-008](requirements.md) | CAP-04 | Human privacy instruction | [NFR-008](requirements.md) | [Privacy policy](../AGENTS.md#authority-and-statement-conventions) | Initial planning documents | Staged artifact review | PENDING release checks |
| [NFR-009](requirements.md) | CAP-02 | D15,DEC-025 | [NFR-009](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [NFR-010](requirements.md) | CAP-04 | D17 | [NFR-010](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [NFR-011](requirements.md) | CAP-04 | D19 | [NFR-011](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [NFR-012](requirements.md) | CAP-04 | D19 | [NFR-012](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [NFR-013](requirements.md) | CAP-01 | D20 | [NFR-013](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [NFR-014](requirements.md) | CAP-05 | D22,DEC-015,DEC-035 | [NFR-014](requirements.md) | [Licensing policy](../AGENTS.md#catalog-behavior-and-licensing) | LICENSE; pyproject.toml | Metadata parsing; built-artifact/help tests PENDING | Source notices added; conventional license text reviewed; CLI pending |
| [NFR-015](requirements.md) | CAP-05 | DEC-010,D26 | [NFR-015](requirements.md) | [Repository policy](repository-policy.md) | [Branch policy](../AGENTS.md#main-branch-protection); active GitHub ruleset 27396943 | [Remote/local verification](repository-policy.md) REPO-012 | ACTIVE; import artifact deleted and untracked |
| [NFR-016](requirements.md) | CAP-04 | DEC-018 | [NFR-016](requirements.md) | [Delivery draft](delivery-plan.md) | AGENTS.md local verification policy; workflows PENDING | Local verification reports PENDING | DRAFT; CI not implemented |
| [NFR-017](requirements.md) | CAP-05 | DEC-018,DEC-019,DEC-028 | [NFR-017](requirements.md) | [Delivery draft](delivery-plan.md) | Release artifacts and installer documentation PENDING | Clean-install/release verification PENDING | DRAFT; no release authorized |
| [NFR-018](requirements.md) | CAP-02 | DEC-020 | [NFR-018](requirements.md) | [Canonical model notes](canonical-model.md) | PENDING | Schema-version, round-trip, and migration-policy checks PENDING | Direction approved; detailed design PENDING |
| [NFR-019](requirements.md) | CAP-03 | DEC-021 | [NFR-019](requirements.md) | [Canonical/export boundary](canonical-model.md) | RDF serializers PENDING | JSON-LD, graph-semantics, and offline-context checks PENDING | Requirement confirmed; design PENDING |

- RTM-003 [FACT; LLM_INFERENCE] [intake proposals](intake-proposals.md) MUST distinguish confirmed decisions from remaining field and behavior assumptions supporting FR-001, FR-002, FR-005, FR-006, FR-007, FR-008, and NFR-009/NFR-013. Confirmed choices in INTAKE-005/006/009 MUST trace to DEC-012 and INTAKE-007/016 MUST trace to DEC-020; remaining assumptions MUST NOT supersede approved requirements.

- The [history remediation plan](privacy-remediation.md) MUST trace to CAP-04/NFR-008 and CAP-05/NFR-006. Revision 1 requirements, architecture, procedure, and bounded process exception are human-approved on 2026-11-16; candidate checks and fresh-clone remote verification passed, protection restoration was verified, and the human accepted residual server retention on 2026-11-16. The plan MUST remain the evidence and scope-exception record; no server-side purge or product release is claimed.

- The standing context-exclusion rule in AGENTS.md MUST trace to CAP-04/NFR-008 and the human instruction recorded in the history remediation plan. Verification MUST review its generic wording, covered artifact surfaces, and pre-publication inspection requirement.

- DEC-023/024 interview decisions MUST trace to CAP-01/FR-001/FR-006 and CAP-06/FR-007 respectively, through docs/requirements.md and INTAKE-002/003/005/018. Full requirements approval, detailed design, implementation, and verification MUST remain PENDING.

- DEC-030/INTAKE-021 workbook feasibility and intake change-control guidance MUST trace to CAP-01/FR-001/FR-012 and CAP-05/NFR-006. Architecture MUST assess synthetic lineage entry complexity before dependent implementation; alternatives MUST retain affected approval gates.

- DEC-031/SPEC-001/SPEC-007/INTAKE-022 intake flexibility MUST trace to CAP-01/FR-001/FR-005/FR-006/FR-010/FR-012 and CAP-05/NFR-006. Current workbook requirements MUST remain the initial implementation plan; alternative intake mechanisms MUST remain unselected and subject to affected planning approvals. The requirements approval candidate MUST be the revised document commit, not the superseded revision 2475300.

- DEC-032/SPEC-007 conditional technology selection MUST govern CAP-01/FR-001/FR-002/FR-005/FR-006/FR-010/FR-012, CAP-03/FR-008, and CAP-01/NFR-013, with CAP-05/NFR-006 governing replacement change control. Existing requirement IDs MUST remain stable; implementation and verification MUST remain PENDING.

- DEC-033 positive/negative boundary and business-rule testing MUST trace to CAP-02/NFR-002, CAP-04/NFR-003/NFR-005, and CAP-05/NFR-007. Durable guidance MUST reside in AGENTS.md and the delivery-plan.md positive/negative verification section; the boundary/rule inventory, tests, failure evidence, and manual walkthrough MUST remain PENDING until their respective phases.
