# Requirements draft

- SPEC-001 [FACT; HUMAN_DERIVED] DSCat MUST enable a maintainer to distribute an Excel dataset inventory workbook, receive completed copies, validate metadata, and generate standards-based exports.
- SPEC-002 [FACT; LLM_INFERENCE] Requirements below MUST remain DRAFT until the human approves a revision. Acceptance criteria MUST be refined where interview decisions remain open.
- SPEC-003 [FACT; HUMAN_DERIVED] The project MUST use the following capabilities.

| Capability | Name |
| --- | --- |
| CAP-01 | Workbook exchange |
| CAP-02 | Typed catalog validation |
| CAP-03 | Standards export |
| CAP-04 | Secure, reproducible engineering |
| CAP-05 | Governed delivery and verification |

| ID | Classification | Requirement and acceptance criterion |
| --- | --- | --- |
| FR-001 | FACT; HUMAN_DERIVED | DSCat MUST generate a human-fillable Excel workbook; a synthetic completed copy MUST be readable by the import workflow. Workbook layout remains pending. |
| FR-002 | FACT; HUMAN_DERIVED | DSCat MUST parse returned workbooks into validated catalog records; invalid input MUST produce actionable diagnostics rather than a successful export. Merge/persistence behavior remains pending. |
| FR-003 | FACT; HUMAN_DERIVED | DSCat MUST export schema-valid DCAT-US metadata; each supported profile MUST pass its pinned authoritative schema and semantic acceptance tests. Version selection remains pending. |
| FR-004 | FACT; HUMAN_DERIVED | DSCat SHOULD export ODCS contracts; scope, version, and required contract fields MUST be approved before implementation. |
| NFR-001 | FACT; HUMAN_DERIVED | DSCat MUST be a uv-managed Python package using the latest stable Python and a Typer entrypoint; package installation and CLI invocation MUST pass on approved operating systems. |
| NFR-002 | FACT; HUMAN_DERIVED | All structured input/output MUST use Pydantic models; every approved boundary MUST have positive and negative validation tests. |
| NFR-003 | FACT; HUMAN_DERIVED | Maintained Python MUST pass comprehensive Ruff and ty checks and be fully covered; exact coverage metrics MUST be approved and enforced. |
| NFR-004 | FACT; HUMAN_DERIVED | Dependency resolution MUST exclude artifacts less than 14 days old; committed configuration and locked dependency evidence MUST demonstrate the restriction. |
| NFR-005 | FACT; HUMAN_DERIVED | Security MUST cover supply-chain vulnerabilities and workbook input; release evidence MUST include vulnerability checks and hostile-input verification against an approved threat model. |
| NFR-006 | FACT; HUMAN_DERIVED | Delivery MUST follow planning gates, complete traceability, semantic versioning, and atomic Conventional Commits; a delivery review MUST find no unjustified implementation artifact. |
| NFR-007 | FACT; HUMAN_DERIVED | The human MUST receive a reproducible manual verification walkthrough before release authorization; each acceptance criterion MUST link to automated or manual evidence. |
| NFR-008 | FACT; HUMAN_DERIVED | Published artifacts MUST use neutral identity and synthetic examples; staged and release artifact review MUST exclude private contextual affiliations and real catalog data. |

- SPEC-004 [FACT; LLM_INFERENCE] Capability and acceptance criteria drafts MUST NOT authorize implementation; model fields, command names, persistence, profiles, compatibility surface, and security thresholds MUST be settled through subsequent planning.
