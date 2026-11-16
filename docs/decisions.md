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

- DEC-002 [FACT; HUMAN_DERIVED] The original 100% statement and branch coverage proposal MUST be read with D18 below, which authorizes narrowly justified agent-selected exceptions.
- DEC-003 [ASSUMPTION; LLM_ASSUMPTION] Agents SHOULD initially commit all durable planning documents rather than leave an untracked issue backlog; later migration SHOULD preserve links and IDs.
- DEC-004 [FACT; LLM_INFERENCE] The next interview MUST resolve remaining identity/conflict rules, capacity measurement semantics, minimal workbook fields, schema versions, and verification platform coverage. D11–D22 below MUST supersede conflicting earlier proposals.
- DEC-005 [FACT; LLM_INFERENCE] Full Ruff, ty, Python, dependency, and build configuration MUST remain pending the engineering plan gate. Initial license metadata and the uv dependency-age cutoff MAY be configured during initialization; they MUST NOT be represented as a completed package or CLI.

- DEC-006 [FACT; HUMAN_DERIVED; 2026-11-16] Agents MUST preserve the following round-2 instructions; they MUST NOT infer approval of the complete written requirements, architecture, or plan.

| ID | Confirmed instruction |
| --- | --- |
| D11 | Version 0.1.0 MUST export DCAT-US 3.0 and ODCS; DCAT-US 1.1 SHOULD be supported but MUST NOT block release. ODCS MAY use a minimal conforming subset. |
| D12 | Workbooks MUST support dataset descriptions, owners, field schemas, provenance, retention, access restrictions, quality, and service commitments; most fields SHOULD be optional to encourage participation. |
| D13 | DSCat MUST capture current dataset volume and ingestion/growth rates sufficient to support data lake capacity planning. |
| D14 | Workbooks MUST serve as intake only; exports MUST be the persisted catalog source of truth. DSCat MUST NOT require a separate database for this workflow. |
| D15 | DSCat MUST accept a single workbook or a folder and assemble the full catalog. Actions MUST be idempotent and repeated runs over unchanged inputs MUST produce the same results. Conflict/failure semantics MUST be settled together. |
| D16 | Validation MUST collect all discoverable failures across inputs before reporting failure, and MUST block catalog exports by default when any validation failure exists. |
| D17 | DSCat MUST use modern Excel workbooks and portable Python; installed runtime functionality MUST work offline after installation from PyPI dependencies. |
| D18 | Maintained Python SHOULD achieve 100% statement and branch coverage. Agents MAY make narrow justified coverage exceptions; exceptions MUST record rationale, scope, residual risk, and compensating verification. |
| D19 | Known High or Critical vulnerabilities MUST block release unless evidence establishes non-applicability. The project MUST produce an SBOM and MAY produce VEX statements supported by code execution-path analysis. |
| D20 | Workbook schema compatibility MUST be the principal backward-compatibility surface; agents MUST explicitly track supported versions and migrations. |
| D21 | Version 0.2.0 MUST include a simple web viewer launched through the CLI to view the exported catalog. Viewer work MUST remain outside 0.1.0 implementation scope. |
| D22 | DSCat MUST be proprietary to Obscurity Labs. A standard LICENSE file, Python project license metadata, and CLI help notice MUST express that ownership and license. |
| D23 | Agents MUST use https://github.com/obscuritylabs/dscat as origin and MUST accept the granted collaborator access and verify required permissions. |

- DEC-007 [FACT; TOOL_VERIFIED; 2026-11-16] Agents MUST treat repository access as verified: the invitation for the exact target repository was accepted through the GitHub API; repository permissions reported pull=true and push=true, visibility private, and the initial remote contained no refs. This MUST NOT imply authorization to release or change visibility.
- DEC-008 [FACT; LLM_INFERENCE] Directly requested licensing artifacts and dependency-age configuration MAY be created during initialization; CLI behavior, dependency selection, and build configuration MUST remain pending the implementation gates. The metadata-only pyproject MUST NOT be presented as a completed installable CLI.

- DEC-009 [FACT; LLM_INFERENCE] The initial proprietary license MUST reserve rights to Obscurity Labs and require separate written authorization for use or distribution; detailed wording MUST remain available for human review. The CLI help notice and built-distribution license checks MUST remain pending implementation.
