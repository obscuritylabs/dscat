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
- DEC-004 [FACT; LLM_INFERENCE] The next interview MUST resolve identifier allocation and duplicate normalization, capacity unit conventions, minimal workbook fields, schema versions, and verification platform coverage. Later decisions MUST supersede conflicting earlier proposals.
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

- DEC-010 [FACT; HUMAN_DERIVED; 2026-11-16] Agents MUST create an untracked, GitHub-importable protection JSON for main and MUST update operating instructions to match; policy details MAY be selected by the agent for a single-contributor workflow. Agents MUST NOT commit the JSON or assume this request authorizes remote activation.
- DEC-011 [FACT; LLM_INFERENCE] The proposed policy MUST require pull requests, resolved conversations, linear history, and rebase merges with zero required approvals and no bypass actors; it MUST prevent deletion and force pushes. Required status checks MUST be added when stable CI jobs exist. The JSON MUST remain locally excluded from Git.

- DEC-012 [FACT; HUMAN_DERIVED; 2026-11-16] Agents MUST preserve the following round-3 decisions; an explanatory question about the intermediate data model MUST NOT be treated as approval of canonical JSON persistence.

| ID | Confirmed instruction |
| --- | --- |
| D24 | Identical records with the same dataset ID MUST be deduplicated; conflicting records with the same ID MUST block export and report both source locations. |
| D25 | Capacity metadata MUST support current size, average and peak daily ingestion, retention, and measurement date, with explicit Unknown allowed. Version 0.1.0 MUST provide information for human capacity planning and MUST NOT implement forecasts. |
| D26 | Agents MUST recognize that the human activated branch protection and deleted the local import JSON. The deleted JSON MUST NOT be recreated merely to satisfy earlier preparation instructions. |

- DEC-013 [FACT; TOOL_VERIFIED; 2026-11-16] Agents MUST treat branch protection as active based on GET /repos/obscuritylabs/dscat/rulesets/27396943: enforcement=active, target refs/heads/main, deletion and non-fast-forward blocks, linear history, pull requests, rebase-only merges, resolved conversations, and zero required approvals. Local filesystem inspection confirmed local/github/main.ruleset.json absent; Git MUST continue to exclude that path if a future export is explicitly requested.
- DEC-014 [ASSUMPTION; LLM_ASSUMPTION] The architecture SHOULD use a Pydantic catalog model between workbook parsing and serializers so capacity and optional metadata are preserved. This original proposal MUST be read with DEC-020, which approves the canonical model and JSON persistence; exact fields and storage layout MUST still pass architecture/planning review.

- DEC-015 [FACT; HUMAN_DERIVED; 2026-11-16] LICENSE MUST use conventional proprietary license text without LIC identifiers, FACT/ASSUMPTION labels, or provenance assertions. The license MUST retain Obscurity Labs ownership and proprietary terms; provenance and traceability MUST remain in planning documents rather than the legal text. This instruction MUST take precedence over the general document annotation convention for LICENSE.

- DEC-016 [FACT; HUMAN_DERIVED; 2026-11-16] Agents MUST remove planning IDs and fact/provenance assertions from ordinary project artifacts such as pyproject.toml and MUST use conventional formatting in those files. These annotations MUST remain confined to governance and planning documents; configuration values and behavior MUST remain unchanged by this cleanup.

- DEC-017 [FACT; HUMAN_DERIVED; 2026-11-16] Agents MUST use planning IDs and fact/provenance markings sparingly, only in planning documents they maintain and where useful. Agents SHOULD apply shared classifications at section or table level rather than annotate every sentence; ordinary project files and operating instructions MUST use conventional formatting. This instruction MUST supersede earlier blanket annotation requirements while preserving requirement IDs and RTM links.

- DEC-018 [FACT; HUMAN_DERIVED; 2026-11-16] GitHub Actions usage MUST be minimized, with local verification and testing as the primary quality gate. A small CI pipeline MAY provide supplementary checks. GitHub Releases MUST distribute installable software. Existing human release authorization and security requirements MUST remain in force.

- DEC-019 [FACT; HUMAN_DERIVED; 2026-11-16] Agents MUST NOT consider any task complete until it is planned, implemented, tested, verified locally, pushed and merged into remote main, released, and verified from the released version. Agents MUST retain evidence for all seven stages and MUST keep work incomplete while any stage is pending. Earlier completion criteria MUST be read with this stricter rule; existing human approval gates MUST remain in force.

- DEC-020 [FACT; HUMAN_DERIVED; 2026-11-16] DSCat MUST use a canonical JSON catalog model between workbook inputs and standards exports, with organized flat files as the authoritative catalog storage for now. Planning MUST treat this model as the likely data migration boundary and MUST preserve the ability to move its persistence into a database later. This approval MUST resolve the canonical model/persistence choice, but MUST NOT imply approval of the complete requirements baseline, exact fields, file layout, architecture, or implementation plan.

- DEC-021 [FACT; HUMAN_DERIVED; 2026-11-16] Any export expressed as RDF MUST use JSON-LD serialization. This conditional requirement MUST NOT imply that every export or the canonical JSON catalog is RDF, or authorize additional export features.

- DEC-022 [FACT; HUMAN_DERIVED; 2026-11-16] The project MUST operate as an autonomous AI software factory: the human participates in planning, while agents own implementation and routine verification/integration without human PR review. Trunk-based development MUST remain the workflow, with short-lived branches permitted; pull requests MUST be identified as the agent-selected mechanism used by current protection rather than a human requirement. Agents MAY request critical PR review, but SHOULD resolve the relevant decisions beforehand in planning. This instruction MUST supersede routine human implementation-review expectations; explicit planning and release authorization requirements MUST remain distinct from PR review.

- DEC-023 [FACT; HUMAN_DERIVED; 2026-11-16] The human accepted the workbook layout and required core: Instructions and Datasets sheets with OPTIONAL Fields and Details/Quality sheets, one dataset per main-sheet row, and required stable ID, title, description, and contact/owner. People completing workbooks MUST supply stable IDs. This decision MUST supersede the preassigned-ID proposals in INTAKE-002/003 and SPEC-006; exact ID syntax and duplicate normalization MUST remain pending.

- DEC-024 [FACT; HUMAN_DERIVED; 2026-11-16] The human accepted the proposed capacity policy: explicit decimal and binary units MUST be accepted and normalized to bytes; logical and physical size MUST be distinguished; ingestion measurement windows MUST be recorded; retention MUST allow a duration, indefinite, or Unknown. Capacity measurements MUST allow explicit Unknown, distinct from zero. Exact field encodings MUST remain subject to detailed design. These interview decisions MUST NOT imply approval of the complete requirements baseline, architecture, implementation plan, or release.

- DEC-025 [FACT; HUMAN_DERIVED; 2026-11-16] The human approved the five import/output rules presented after commit 6273f5a: directory discovery MUST select .xlsx files and ignore Excel lock files, with recursion only by explicit option; each build MUST represent exactly the selected inputs without modifying previous snapshots; replacement MUST require an explicit option and validation/write failure MUST preserve previous output; unchanged inputs, configuration, and tool/schema versions MUST produce byte-identical canonical JSON and standards exports; missing IDs MUST fail validation and duplicate comparison MUST use validated normalized metadata excluding source locations while preserving all source locations for diagnostics. Exact normalization MUST be specified in architecture. This approval MUST NOT imply approval of the complete requirements baseline or later gates.

- DEC-026 [FACT; HUMAN_DERIVED; 2026-11-16] Generated workbooks MUST implement as much applicable data validation as practical using normal Excel features, including dropdowns, validated fields, highlighting, error callouts, and formulas. Workbooks MUST NOT contain macros or executable code; ordinary Excel formulas are explicitly permitted. DSCat MUST independently validate returned data and MUST NOT execute workbook formulas. Architecture MUST specify formula handling and validation coverage without depending on workbook controls or cached formula results for correctness.

- DEC-027 [FACT; HUMAN_DERIVED; 2026-11-16] The human accepted ODCS 3.2.0 with identity, name, description, contract version, and available ownership/field-schema details. Quality and service commitments MUST be exported only when explicitly supplied. Validated configuration MAY supply shared export-required metadata; missing required facts MUST block export. Exact mappings and pinned schema resources MUST remain pending architecture.

- DEC-028 [FACT; HUMAN_DERIVED; 2026-11-16] Windows, macOS, and Linux MUST remain portability targets rather than a mandatory verified-platform matrix. Implementation MUST use ordinary cross-platform Python tooling and standard Python packaging; installation MUST use uv tool install with GitHub Release artifacts, with authenticated download where required by private visibility. Specialized installers MUST NOT be required. Actual platform verification MUST be reported accurately. Excel verification arrangements MUST remain deferred; this deferral MUST NOT be represented as successful verification or a waiver of workbook acceptance.

- DEC-029 [FACT; HUMAN_DERIVED; 2026-11-16] The human accepted OPTIONAL manually supplied dataset-and-processing-step lineage for 0.1.0: upstream inputs and derived outputs, including multiple inputs combined into one output; processing software/tool and version, transformation descriptions, input/output dataset IDs; responsible teams/owners and handoffs; and OPTIONAL timestamps, process references, and supporting documentation. An OPTIONAL Lineage sheet MUST capture these relationships without enlarging the required workbook core. Canonical JSON MUST preserve the supported lineage metadata; standards exports MUST include supported mappings. Automatic discovery from processing systems MUST remain outside this approved scope. Detailed fields, reference handling, and mappings MUST pass architecture review.

- DEC-030 [FACT; HUMAN_DERIVED; 2026-11-16] Agents MUST notify the human if workbook intake becomes too complex for practical use and MUST identify the concrete limitation so an alternative intake process can be planned. This instruction MUST NOT authorize replacing or adding an intake mechanism without the affected planning approvals.

- DEC-031 [FACT; HUMAN_DERIVED; 2026-11-16] The human requested that SPEC-001 retain mandatory intake, validation, and standards-export capabilities while loosening Excel to MAY or SHOULD. SPEC-001 MUST use SHOULD for the initial Excel intake choice; workbook-specific requirements MUST describe the current 0.1.0 implementation rather than permanently constrain the product to Excel. Burdensome workbook completion MAY motivate a replacement intake process through affected planning approvals. An alternative guided form workflow MAY be considered later, but no replacement mechanism or state-machine design MUST be inferred as selected or authorized. This revision MUST supersede the stronger Excel wording in SPEC-001; the consolidated requirements baseline MUST remain unapproved.

- DEC-032 [FACT; HUMAN_DERIVED; 2026-11-16] The human clarified that Excel-specific MUST requirements MUST apply only while Excel is selected and MUST NOT override its nonmandatory selection under SPEC-001. Intake requirements SHOULD use technology-neutral language where practical; selection-specific details MAY remain conditional. Replacing Excel MUST revise or retire Excel-specific requirements and acceptance criteria and carry applicable capabilities to the replacement technology through affected planning approvals. This clarification MUST NOT select a replacement or approve the complete baseline.

- DEC-033 [FACT; HUMAN_DERIVED; 2026-11-16] The human requires positive and negative test cases for all inputs, outputs, and ordinary business logic, with evidence of where and how the system fails. Testing and verification MUST support robustness, durability, and safe evolution. AGENTS.md and NFR-002/003/005/007 MUST govern boundary/business-rule coverage, failure behavior, regression protection, and traceable evidence; coverage percentages MUST NOT replace behavior verification. This instruction MUST NOT imply approval of the complete requirements baseline or later gates.
