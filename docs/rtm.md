# Requirements traceability matrix

- RTM-001 [FACT; LLM_INFERENCE] Each row MUST trace the requirement in [requirements.md](requirements.md) to a capability and artifacts; PENDING MUST indicate work not performed, never a pass. Requirement classifications MUST be inherited from the referenced requirement.
- RTM-002 [FACT; LLM_INFERENCE] Requirement sources MUST reference DEC-001 or DEC-006 and their D-numbers in [decisions.md](decisions.md). Design, code, tests, and evidence MUST be added before a row can become verified.

| Requirement | Capability | Source | Acceptance | Design | Implementation | Tests | Evidence/status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [FR-001](requirements.md) | CAP-01 | D01,D12,D17 | [FR-001](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [FR-002](requirements.md) | CAP-02 | D01,D16 | [FR-002](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [FR-003](requirements.md) | CAP-03 | D03,D11 | [FR-003](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [FR-004](requirements.md) | CAP-03 | D03,D11 | [FR-004](requirements.md) | PENDING | PENDING | PENDING | DRAFT; 0.1.0 |
| [FR-005](requirements.md) | CAP-01 | D15 | [FR-005](requirements.md) | PENDING | PENDING | PENDING | DRAFT; 0.1.0 |
| [FR-006](requirements.md) | CAP-01 | D12 | [FR-006](requirements.md) | PENDING | PENDING | PENDING | DRAFT; 0.1.0 |
| [FR-007](requirements.md) | CAP-06 | D13 | [FR-007](requirements.md) | PENDING | PENDING | PENDING | DRAFT; 0.1.0 |
| [FR-008](requirements.md) | CAP-03 | D14 | [FR-008](requirements.md) | PENDING | PENDING | PENDING | DRAFT; 0.1.0 |
| [FR-009](requirements.md) | CAP-07 | D21 | [FR-009](requirements.md) | PENDING | PENDING | PENDING | DEFERRED; 0.2.0 |
| [NFR-001](requirements.md) | CAP-04 | D02 | [NFR-001](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [NFR-002](requirements.md) | CAP-02 | D02 | [NFR-002](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [NFR-003](requirements.md) | CAP-04 | D02,D18 | [NFR-003](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [NFR-004](requirements.md) | CAP-04 | D02 | [NFR-004](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [NFR-005](requirements.md) | CAP-04 | D06,D19 | [NFR-005](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [NFR-006](requirements.md) | CAP-05 | D04,D05,D08,D09,D10 | [NFR-006](requirements.md) | AGENTS.md | AGENTS.md; docs/index.md; docs/decisions.md; docs/requirements.md; docs/rtm.md; docs/research.md | Document review | DRAFT; human approval pending |
| [NFR-007](requirements.md) | CAP-05 | D07 | [NFR-007](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [NFR-008](requirements.md) | CAP-04 | Human privacy instruction | [NFR-008](requirements.md) | AGENTS.md GOV-007 | Initial planning documents | Staged artifact review | PENDING release checks |
| [NFR-009](requirements.md) | CAP-02 | D15 | [NFR-009](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [NFR-010](requirements.md) | CAP-04 | D17 | [NFR-010](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [NFR-011](requirements.md) | CAP-04 | D19 | [NFR-011](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [NFR-012](requirements.md) | CAP-04 | D19 | [NFR-012](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [NFR-013](requirements.md) | CAP-01 | D20 | [NFR-013](requirements.md) | PENDING | PENDING | PENDING | DRAFT |
| [NFR-014](requirements.md) | CAP-05 | D22 | [NFR-014](requirements.md) | AGENTS.md GOV-056 | PENDING | PENDING | Direct artifact creation authorized; CLI pending |

- RTM-003 [FACT; LLM_INFERENCE] [intake proposals](intake-proposals.md) MUST be treated as unapproved field and behavior proposals supporting FR-001, FR-002, FR-005, FR-006, FR-007, FR-008, and NFR-009/NFR-013. They MUST NOT supersede approved requirements.
