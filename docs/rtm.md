# Requirements traceability matrix

- RTM-001 [FACT; LLM_INFERENCE] Each row MUST trace the requirement in [requirements.md](requirements.md) to a capability and artifacts; PENDING MUST indicate work not performed, never a pass. Requirement classifications MUST be inherited from the referenced requirement.
- RTM-002 [FACT; LLM_INFERENCE] All requirement sources MUST reference DEC-001 and its D-number in [decisions.md](decisions.md). Design, code, tests, and evidence MUST be added before a row can become verified.

| Requirement | Capability | Source | Acceptance | Design | Implementation | Tests | Evidence/status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FR-001 | CAP-01 | D01 | FR-001 | PENDING | PENDING | PENDING | DRAFT |
| FR-002 | CAP-02 | D01 | FR-002 | PENDING | PENDING | PENDING | DRAFT |
| FR-003 | CAP-03 | D03 | FR-003 | PENDING | PENDING | PENDING | DRAFT |
| FR-004 | CAP-03 | D03 | FR-004 | PENDING | PENDING | PENDING | DRAFT; SHOULD |
| NFR-001 | CAP-04 | D02 | NFR-001 | PENDING | PENDING | PENDING | DRAFT |
| NFR-002 | CAP-02 | D02 | NFR-002 | PENDING | PENDING | PENDING | DRAFT |
| NFR-003 | CAP-04 | D02 | NFR-003 | PENDING | PENDING | PENDING | DRAFT |
| NFR-004 | CAP-04 | D02 | NFR-004 | PENDING | PENDING | PENDING | DRAFT |
| NFR-005 | CAP-04 | D06 | NFR-005 | PENDING | PENDING | PENDING | DRAFT |
| NFR-006 | CAP-05 | D04,D05,D08,D09,D10 | NFR-006 | AGENTS.md | AGENTS.md; docs/index.md; docs/decisions.md; docs/requirements.md; docs/rtm.md; docs/research.md | Document review | DRAFT; human approval pending |
| NFR-007 | CAP-05 | D07 | NFR-007 | PENDING | PENDING | PENDING | DRAFT |
| NFR-008 | CAP-04 | Human privacy instruction | NFR-008 | AGENTS.md GOV-007 | Initial planning documents | Staged artifact review | PENDING release checks |
