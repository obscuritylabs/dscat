# Approved requirements

- SPEC-001 [FACT; HUMAN_DERIVED] DSCat MUST enable distribution of dataset metadata intake materials, receipt of completed submissions, validation of metadata, and generation of standards-based exports. Excel workbooks SHOULD provide the initial intake mechanism; Excel MUST NOT be a permanent product constraint. A replacement intake mechanism MAY be selected through the affected requirements, architecture, and implementation-plan approvals if workbook completion becomes too burdensome.
- SPEC-002 The complete requirements baseline in docs/requirements.md at commit `00c3535236028197805c0199401321631c709cd0` is APPROVED by explicit human instruction on 2026-11-16, recorded in [DEC-039](decisions.md#dec-039). Approval covers SPEC-001–SPEC-007, all 30 FR/NFR requirements, and their acceptance criteria. The requirements are ready for architecture planning; dependent implementation MUST still await architecture and implementation-plan approval. RTM approval MUST follow DEC-040; decision-log baseline approval MUST follow DEC-041; release authorization MUST remain separate. The [planning gates](planning-gates.md) MUST identify the remaining deliverables.
- SPEC-003 [FACT; HUMAN_DERIVED] The project MUST use the following capabilities.

| Capability | Name |
| --- | --- |
| CAP-01 | Metadata intake exchange |
| CAP-02 | Typed catalog validation |
| CAP-03 | Standards export |
| CAP-04 | Secure, reproducible engineering |
| CAP-05 | Governed delivery and verification |
| CAP-06 | Capacity planning metadata |

## Requirements and acceptance criteria

Source: consolidated human instructions in [decisions.md](decisions.md), with reconciliation authorized by DEC-038. Approval status MUST be interpreted under SPEC-002, separately from provenance.

### FR-001

DSCat MUST generate human-completable dataset metadata intake materials with instructions, one primary entry per dataset, and OPTIONAL field-schema, detail/quality, and lineage sections. A synthetic completed submission MUST be readable by the intake workflow and the selected completion interface. The current Excel layout MUST follow DEC-023/029 while Excel remains selected.

### FR-002

DSCat MUST parse completed submissions into validated catalog records; invalid input MUST produce actionable diagnostics rather than a successful export. All discoverable failures within safe processing limits MUST be reported in one validation pass and MUST block catalog exports by default. Unsafe, resource-limited, or unreadable inputs MUST receive diagnostics while independent readable inputs continue; content not examined MUST NOT be claimed as validated. Identical records sharing an ID MUST deduplicate; conflicting records sharing an ID MUST block export and identify both source locations.

### FR-003

Version 0.1.0 MUST export schema-valid DCAT-US 3.0; the exporter MUST pass its pinned authoritative schema and semantic acceptance tests. DCAT-US 1.1 SHOULD be supported but MUST NOT block release.

### FR-004

Version 0.1.0 MUST export ODCS contracts using a minimal conforming scope; output MUST pass the selected pinned schema. Per DEC-027, the target MUST be ODCS 3.2.0 with identity, name, description, contract version, and available ownership/field-schema details. Quality and service commitments MUST be included only when explicitly supplied. Validated configuration MAY supply shared export-required metadata; missing required facts MUST block export. Exact mappings and schema pins MUST pass architecture review.

### FR-005

DSCat MUST accept one intake artifact or a directory of intake artifacts and build the full catalog; single-artifact and directory acceptance scenarios MUST be verified. Discovery MUST select artifacts supported by the selected intake technology and ignore its temporary lock artifacts, with recursion only by explicit option (DEC-025). While Excel is selected, discovery MUST select .xlsx files and ignore Excel lock files. Duplicate/conflict handling MUST satisfy FR-002.

### FR-006

Intake fields MUST support ownership, field schemas, provenance, retention, access restrictions, quality, and service commitments, with most details OPTIONAL. The required core MUST be a submitter-supplied stable ID, title, description, and contact/owner (DEC-023). A minimal valid submission, together with sufficient validated shared export configuration where required, MUST export without completing optional detail sections. Missing required export facts MUST block the affected export with actionable diagnostics; defaults MUST NOT invent facts. Architecture MUST demonstrate this minimum for both mandatory targets against pinned schemas before implementation.

### FR-007

Catalog records MUST support current size, average and peak daily ingestion, retention, and measurement date for human capacity planning, allowing explicit Unknown. Quantities MUST have explicit units and measurement context; Unknown MUST remain distinct from zero. Decimal and binary units MUST be accepted and normalized to bytes; logical and physical size MUST be distinguished, ingestion measurement windows MUST be recorded, and retention MUST allow a duration, indefinite, or Unknown (DEC-024). Version 0.1.0 MUST NOT implement forecasts. Verification MUST cover known, Unknown, zero, and invalid quantities without requiring predictions.

### FR-008

A Pydantic-backed canonical JSON catalog MUST be the persisted source of truth, with completed submissions used only as intake and DCAT-US/ODCS derived from the canonical model. Storage MUST use organized flat files for now. Acceptance MUST demonstrate intake-to-canonical validation, JSON save/load without loss of supported metadata, and regeneration of standard exports from saved canonical data without the original submissions or a database.

### FR-010

The selected intake interface MUST provide applicable validation through controlled choices, field constraints, highlighting, and actionable error callouts where practical (DEC-026). Acceptance MUST demonstrate valid entries, missing required values, invalid units/numbers/dates, and duplicate IDs using synthetic inputs; architecture MUST map each check to interface feedback or document its limitation. DSCat MUST independently validate submitted data; bypassed or removed interface controls MUST NOT permit invalid catalog exports. While Excel is selected, generated workbooks MUST use applicable dropdowns, cell validation, highlighting, error callouts, and normal Excel formulas where practical, MUST NOT contain macros or executable code, and DSCat MUST NOT execute formulas or trust cached results.

### FR-011

Builds MUST represent exactly the selected inputs; omitted datasets MUST be absent from the new snapshot without changing previous snapshots. Existing output replacement MUST require an explicit option, and validation/write failures MUST preserve previous output (DEC-025). Acceptance MUST verify omission, refused replacement, successful explicit replacement, and preservation after validation/write failure.

### FR-012

Version 0.1.0 MUST support OPTIONAL manually supplied dataset-and-processing-step lineage through an OPTIONAL lineage section without enlarging the required intake core (DEC-029). Records MUST support upstream and derived dataset references, multiple-input derivation, processing software/tool and version, transformation descriptions, input/output dataset IDs, responsible teams/owners and handoffs, and OPTIONAL timestamps, process references, and supporting documentation. Canonical JSON MUST preserve supported lineage metadata and standards exports MUST include supported mappings. Acceptance MUST demonstrate a synthetic multi-input derivation and multi-step handoff, canonical save/load preservation, applicable export mappings, and validation of malformed references under the architecture-approved reference policy. Automatic lineage discovery MUST remain outside 0.1.0 scope.

### NFR-001

DSCat MUST be a uv-managed Python package using the latest stable Python selected at initial implementation and a Typer entrypoint; Windows, macOS, and Linux MUST be portability targets using ordinary cross-platform Python tooling and standard packaging (DEC-028). Installation MUST use uv tool install with GitHub Release artifacts, with authenticated download when needed; specialized installers MUST NOT be required. Verification MUST record platforms actually tested rather than claim a verified matrix.

### NFR-002

All structured input/output MUST use Pydantic models. Every structured and unstructured input/output boundary MUST have positive and negative tests (DEC-033), including valid, empty, boundary, malformed, unsupported, conflicting, and hostile cases where applicable. Output tests MUST verify valid results and safe rejection or handling of invalid/unrepresentable results, serialization errors, and write failures. Acceptance MUST map each boundary to tests and failure diagnostics/exit behavior; nonapplicable cases MUST have recorded rationale.

### NFR-003

Maintained Python MUST pass Ruff ALL rules with narrow documented conflict resolutions, Ruff formatting, and all available ty diagnostics at error severity; the target MUST be 100% statement and branch coverage, with narrow agent-selected exceptions documented by rationale, scope, risk, and compensating verification. Every business rule, including ordinary business logic, MUST have positive and negative behavior tests, covering applicable limits and failure paths (DEC-033). Regression and compatibility tests MUST protect supported behavior as code and schemas evolve; coverage percentages MUST NOT substitute for these tests.

### NFR-004

Dependency resolution MUST exclude artifacts less than 14 days old; committed configuration and locked dependency evidence MUST demonstrate the restriction.

### NFR-005

Security MUST cover supply-chain vulnerabilities and untrusted intake input; release evidence MUST include vulnerability checks and hostile-input verification against an approved threat model. Failure verification MUST demonstrate preservation of existing data/outputs, bounded safe termination, and recovery or retry where applicable; expected failure modes and remaining limitations MUST be recorded (DEC-033).

### NFR-006

Delivery MUST follow planning gates, complete traceability, semantic versioning, and atomic Conventional Commits. Agents MUST own implementation, testing, local verification, and routine PR review/merging within approved scope without human PR review; a delivery review MUST find no unjustified implementation artifact. Every task MUST remain incomplete until planned, implemented, tested, locally verified, merged into remote main, released, and verified from the released version, with evidence for each stage.

### NFR-007

The human MUST receive a reproducible manual verification walkthrough before candidate-specific release authorization or, where release authority was explicitly delegated conditionally during planning, before those conditions are exercised to publish; each acceptance criterion MUST link to automated or manual evidence. The walkthrough and verification report MUST identify positive and negative scenarios, exact failure triggers, expected diagnostics/exit behavior, data/output preservation, cleanup, and applicable recovery steps (DEC-033).

### NFR-008

Published artifacts MUST use neutral identity and synthetic examples; staged and release artifact review MUST exclude private contextual affiliations and real catalog data.

### NFR-009

Catalog-building operations MUST be idempotent in their resulting catalog content and state effects: repeated builds from the same input content, configuration, and tool/schema versions MUST produce identical catalog results without duplicates or accumulating state. Repeating a command against an existing destination without the explicit replacement option MUST refuse replacement under FR-011; idempotence MUST NOT imply repeated command success or bypass overwrite protection. Canonical JSON and standards exports MUST be byte-identical for unchanged inputs, configuration, and tool/schema versions (DEC-025).

### NFR-010

Installed runtime functions MUST work offline with PyPI-sourced dependencies; intake-material generation, validation, and export MUST succeed with network access disabled and external schema resolution MUST NOT fetch remotely.

### NFR-011

Each release MUST include a machine-readable dependency SBOM identifying the released artifact; format, transitive coverage, and provenance MUST be verified in the release plan.

### NFR-012

Known High or Critical vulnerabilities MUST block release unless evidence establishes non-applicability; applicable findings MUST be fixed and non-applicability MAY be documented in VEX with execution-path evidence. Medium/Low findings MUST be tracked.

### NFR-013

Intake schemas MUST be versioned and supported-version compatibility MUST be tested; unsupported versions MUST produce actionable errors. The compatibility policy MUST prioritize readability of older supported submissions. While Excel is selected, workbook schema compatibility MUST be the principal intake compatibility surface. A replacement decision MUST explicitly address existing submissions and any compatibility impact.

### NFR-014

DSCat MUST use the Obscurity Labs proprietary license. The LICENSE file, Python package metadata, and CLI help MUST provide consistent ownership and licensing information. Verification MUST confirm that this information is present and consistent in the source, built distributions, and CLI help.

### NFR-015

Repository changes MUST follow the active policy documented in docs/repository-policy.md. Verification MUST confirm that the documented policy matches the active repository settings and that changes follow the applicable integration workflow.

### NFR-016

Local verification and testing MUST be the primary quality gate; GitHub Actions MUST remain minimal and supplementary. Verification planning MUST cover all existing checks locally and identify the small CI subset, with evidence tied to the source revision.

### NFR-017

Approved software MUST be distributed through GitHub Releases in installable form. Post-publication verification MUST demonstrate authenticated asset download, integrity/version checks, clean installation, CLI invocation, applicable acceptance scenarios, and offline runtime behavior using the released artifacts rather than the checkout; human authorization MUST precede publication.

### NFR-018

Architecture MUST treat the canonical model as the likely persisted-data migration boundary and MUST separate its logical schema from flat-file persistence to support a future database. The design MUST specify schema version identification, compatibility, and migration safeguards; verification MUST cover canonical round trips and supported/unsupported version handling. A database and speculative migration implementations MUST remain outside initial scope.

### NFR-019

Any RDF export MUST use JSON-LD serialization. Acceptance MUST verify valid JSON-LD and intended RDF graph semantics as well as applicable target-profile constraints; JSON-LD context processing MUST work offline under NFR-010. Non-RDF canonical JSON and other non-RDF exports MUST NOT be required to become RDF.

- SPEC-004 Requirements and acceptance criteria approval alone MUST NOT authorize implementation; model fields, command names, canonical file layout and schema version policy, exact schema pins, compatibility surface, and security verification procedures MUST be settled through subsequent planning.

- SPEC-005 [FACT; HUMAN_DERIVED] Version 0.1.0 scope MUST include FR-001 through FR-008, FR-010 through FR-012, and supporting NFRs. Optional DCAT-US 1.1 support MUST NOT postpone completion of mandatory initial features.
- SPEC-006 [FACT; HUMAN_DERIVED] DEC-023/024 MUST govern the required intake core and capacity policy. The earlier preassigned-ID proposal MUST be superseded by submitter-supplied stable IDs. DEC-027 MUST govern validated shared export metadata configuration; defaults MUST NOT invent facts or data-use commitments.

- SPEC-007 [FACT; HUMAN_DERIVED] Per DEC-031/032, Excel SHOULD be the initial intake technology. Requirements describing intake capabilities MUST remain technology-neutral where practical. Technology-specific MUST clauses MUST apply only while that technology is selected and MUST NOT make its selection mandatory. A technology replacement MUST revise or retire its specific clauses and acceptance criteria, preserve applicable technology-neutral obligations, and resolve compatibility impacts through affected planning approvals. This clarification MUST NOT select or authorize another technology now.
