# Decisions and interview record

- DEC-001 [FACT; HUMAN_DERIVED; 2026-11-16] Agents MUST preserve the following confirmed direction from interview round 1; captured instructions MUST NOT imply approval of an agent-written requirements baseline.

| ID | Confirmed instruction |
| --- | --- |
| D01 | DSCat MUST manage a dataset catalog through generated and returned Excel workbooks. |
| D02 | Implementation MUST use Python, uv, Typer, Pydantic, comprehensive Ruff and ty checks, and a 14-day dependency artifact age restriction. |
| D03 | DCAT-US export MUST be supported; ODCS SHOULD be considered as a data contract format. |
| D04 | Requirements, architecture, and implementation plans MUST receive human approval; release MUST receive authorization after implementation and testing. |
| D05 | Documents MUST distinguish facts/assumptions and provenance; verification MAY use tool evidence and MUST remain separate from human approval. |
| D06 | Security MUST be enforced, particularly supply-chain security; independent reviews MAY be waived by the human. |
| D07 | The human MUST receive a practical written verification walkthrough. |
| D08 | Versioning MUST begin at 0.1.0; post-1.0 compatibility MUST hold within each major, and breaking major releases MUST require prior human agreement. |
| D09 | Work MUST use short-lived branches and atomic Conventional Commits, including commits for human interactions producing tracked artifacts. |
| D10 | Planning MUST initially exist entirely on disk; agents MAY later propose issue tracking without losing traceability. |

- DEC-002 [ASSUMPTION; LLM_ASSUMPTION] Agents SHOULD use 100% statement and branch coverage for maintained Python code, with no blanket exclusions; the human MUST confirm the target before verification planning is approved.
- DEC-003 [ASSUMPTION; LLM_ASSUMPTION] Agents SHOULD initially commit all durable planning documents rather than leave an untracked issue backlog; later migration SHOULD preserve links and IDs.
- DEC-004 [FACT; LLM_INFERENCE] The next interview MUST resolve target DCAT-US profile(s), ODCS release scope, workbook content, persistence/merge semantics, operating systems, network behavior, dependency security blocking policy, and coverage.
- DEC-005 [FACT; LLM_INFERENCE] Ruff, ty, Python, and uv configuration MUST remain pending the engineering plan gate; this documentation change MUST NOT be represented as implemented tooling configuration.
