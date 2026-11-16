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
| CAP-06 | Capacity planning metadata |
| CAP-07 | Catalog viewing (0.2.0) |

| ID | Classification | Requirement and acceptance criterion |
| --- | --- | --- |
| FR-001 | FACT; HUMAN_DERIVED | DSCat MUST generate a human-fillable Excel workbook; a synthetic completed .xlsx copy MUST be readable by the import workflow and modern Excel. Workbook layout remains pending. |
| FR-002 | FACT; HUMAN_DERIVED | DSCat MUST parse returned workbooks into validated catalog records; invalid input MUST produce actionable diagnostics rather than a successful export. All discoverable failures MUST be reported in one validation pass and MUST block catalog exports by default. Conflict rules remain pending. |
| FR-003 | FACT; HUMAN_DERIVED | Version 0.1.0 MUST export schema-valid DCAT-US 3.0; the exporter MUST pass its pinned authoritative schema and semantic acceptance tests. DCAT-US 1.1 SHOULD be supported but MUST NOT block release. |
| FR-004 | FACT; HUMAN_DERIVED | Version 0.1.0 MUST export ODCS contracts using a minimal conforming scope; output MUST pass the selected pinned schema. Exact version and useful minimal field mappings MUST be approved before implementation. |
| FR-005 | FACT; HUMAN_DERIVED | DSCat MUST accept one workbook or a directory of workbooks and build the full catalog; single-file and directory acceptance scenarios MUST be verified. Discovery and conflict rules remain pending. |
| FR-006 | FACT; HUMAN_DERIVED | Workbook fields MUST support ownership, field schemas, provenance, retention, access restrictions, quality, and service commitments, with most details OPTIONAL; a minimal valid submission MUST export without completing optional detail sheets. |
| FR-007 | FACT; HUMAN_DERIVED | Catalog records MUST capture dataset volume and ingestion/growth rates for data lake capacity planning; quantities MUST have explicit units and measurement context, and missing values MUST NOT become zero. Mandatory measurements remain pending. |
| FR-008 | FACT; HUMAN_DERIVED | Exports MUST be the persisted catalog source of truth, with workbooks used only as intake; a completed build MUST yield standalone exports without an application database. Canonical export representation remains pending. |
| FR-009 | FACT; HUMAN_DERIVED | Version 0.2.0 MUST provide a CLI-launched web viewer for the exported catalog; acceptance MUST demonstrate opening existing exports offline. This feature MUST remain outside 0.1.0 scope. |
| NFR-001 | FACT; HUMAN_DERIVED | DSCat MUST be a uv-managed Python package using the latest stable Python and a Typer entrypoint; package installation and CLI invocation MUST pass on approved operating systems. |
| NFR-002 | FACT; HUMAN_DERIVED | All structured input/output MUST use Pydantic models; every approved boundary MUST have positive and negative validation tests. |
| NFR-003 | FACT; HUMAN_DERIVED | Maintained Python MUST pass comprehensive Ruff and ty checks; the target MUST be 100% statement and branch coverage, with narrow agent-selected exceptions documented by rationale, scope, risk, and compensating verification. |
| NFR-004 | FACT; HUMAN_DERIVED | Dependency resolution MUST exclude artifacts less than 14 days old; committed configuration and locked dependency evidence MUST demonstrate the restriction. |
| NFR-005 | FACT; HUMAN_DERIVED | Security MUST cover supply-chain vulnerabilities and workbook input; release evidence MUST include vulnerability checks and hostile-input verification against an approved threat model. |
| NFR-006 | FACT; HUMAN_DERIVED | Delivery MUST follow planning gates, complete traceability, semantic versioning, and atomic Conventional Commits; a delivery review MUST find no unjustified implementation artifact. |
| NFR-007 | FACT; HUMAN_DERIVED | The human MUST receive a reproducible manual verification walkthrough before release authorization; each acceptance criterion MUST link to automated or manual evidence. |
| NFR-008 | FACT; HUMAN_DERIVED | Published artifacts MUST use neutral identity and synthetic examples; staged and release artifact review MUST exclude private contextual affiliations and real catalog data. |
| NFR-009 | FACT; HUMAN_DERIVED | All actions MUST be idempotent; repeated builds from the same input content, configuration, and tool/schema versions MUST produce identical catalog results without duplicates or accumulating state. Exact byte-level contract remains pending. |
| NFR-010 | FACT; HUMAN_DERIVED | Installed runtime functions MUST work offline with PyPI-sourced dependencies; template generation, validation, and export MUST succeed with network access disabled and external schema resolution MUST NOT fetch remotely. |
| NFR-011 | FACT; HUMAN_DERIVED | Each release MUST include a machine-readable dependency SBOM identifying the released artifact; format, transitive coverage, and provenance MUST be verified in the release plan. |
| NFR-012 | FACT; HUMAN_DERIVED | Known High or Critical vulnerabilities MUST block release unless evidence establishes non-applicability; applicable findings MUST be fixed and non-applicability MAY be documented in VEX with execution-path evidence. Medium/Low findings MUST be tracked. |
| NFR-013 | FACT; HUMAN_DERIVED | Workbook schemas MUST be versioned and supported-version compatibility MUST be tested; unsupported versions MUST produce actionable errors. The approved compatibility policy MUST prioritize old workbook readability. |
| NFR-014 | FACT; HUMAN_DERIVED | DSCat MUST be proprietary to Obscurity Labs; LICENSE, built Python package metadata, and CLI help MUST carry matching notices. Verification MUST inspect source, built wheel/sdist license metadata, and CLI help output. |
| NFR-015 | FACT; HUMAN_DERIVED | Main MUST have a locally prepared, untracked branch protection import JSON and matching agent instructions; the file MUST target main and MUST remain absent from the Git index. Selected rules MUST follow docs/repository-policy.md; remote activation MUST remain a separate human action. |

- SPEC-004 [FACT; LLM_INFERENCE] Capability and acceptance criteria drafts MUST NOT authorize implementation; model fields, command names, canonical export representation, exact schema pins, compatibility surface, and security verification procedures MUST be settled through subsequent planning.

- SPEC-005 [FACT; HUMAN_DERIVED] Release scope MUST distinguish 0.1.0 (FR-001 through FR-008 and supporting NFRs) from 0.2.0 (FR-009). Optional DCAT-US 1.1 support MUST NOT postpone completion of mandatory initial features.
- SPEC-006 [ASSUMPTION; LLM_ASSUMPTION] The minimum analyst submission SHOULD contain a stable preassigned identifier, dataset title, short description, contact/owner, and known-or-unknown capacity measurements; maintainer-provided defaults MAY supply shared catalog metadata, but MUST NOT invent facts or data-use commitments.
