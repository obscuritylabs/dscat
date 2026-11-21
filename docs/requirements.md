# Requirements and current authority status

- SPEC-001 [FACT; HUMAN_DERIVED] DSCat MUST enable distribution of dataset metadata intake materials, receipt of completed submissions, validation of metadata, and generation of standards-based exports. Excel workbooks SHOULD provide the initial intake mechanism; Excel MUST NOT be a permanent product constraint. A replacement intake mechanism MAY be selected through the affected requirements, architecture, and implementation-plan approvals if workbook completion becomes too burdensome.
- SPEC-002 The historical approved baseline remains docs/requirements.md at `00c3535236028197805c0199401321631c709cd0` (2026-11-16, [DEC-039](decisions.md#dec-039)), covering SPEC-001–SPEC-007 and its original 30 FR/NFR requirements. The consolidated requirements and research impact package at `69b686a3d0b1da49290ca37d577d46fb8b63dbfb` was approved on 2026-11-17 under [DEC-044](decisions.md#dec-044), covering that revision's SPEC-001–SPEC-007, all 42 FR/NFR requirements and acceptance criteria, and the impact package additions, refinements, sequencing, impacts and exclusions. DEC-042 and [DEC-043](decisions.md#dec-043) remain historical preparation and interview-decision provenance; their source-revision PENDING/proposed labels do not describe current requirements status. Unchanged requirements retain their original authority within the exact DEC-039 baseline scope. Requirements approval MUST NOT authorize dependent implementation. Current authority MUST follow [planning gates](planning-gates.md).
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

Source: consolidated human instructions in [decisions.md](decisions.md); proposed additions and refinements follow DEC-042 and the [research impact package](research-additions.md). Approval status MUST be interpreted under SPEC-002, separately from provenance.

### FR-001

DSCat MUST generate human-completable collection metadata intake materials with instructions and one primary table containing one row per collection. The selected Excel interface MUST use the collection-first layout in [INTAKE-024](intake-proposals.md#intake-024), replacing the DEC-023/029 multi-sheet input layout. A collection MUST remain registerable without a known generating process. Optional input details MUST NOT require separate linked worksheets or collection duplication. This simplification MUST preserve applicable canonical catalog and export capabilities independently of the input layout; later FR-012 lineage remains separately sequenced under SPEC-005.

Template generation MUST offer `--examples` to seed editable synthetic worked-example rows and guidance explaining completion and the value of the metadata. Generation without the flag MUST retain the blank-input default. Examples MAY name real public tools, but quantities, people, teams, locations, dates, sensitivity and retention decisions MUST be invented and clearly identified as illustrative. Example rows MUST pass ordinary intake validation without special exemptions and MUST be removable or replaceable. Acceptance MUST verify blank generation, seeded ordinary validation, editing/removal, deterministic output, existing-file refusal, explicit replacement and failure preservation. [INTAKE-024](intake-proposals.md#intake-024) owns detailed example acceptance; [planning gates](planning-gates.md#collection-intake-readiness) owns current authority and readiness.

### FR-002

DSCat MUST parse completed submissions into validated catalog records; invalid input MUST produce actionable diagnostics rather than a successful export. All discoverable failures within safe processing limits MUST be reported in one validation pass and MUST block catalog exports by default. Unsafe, resource-limited, or unreadable inputs MUST receive diagnostics while independent readable inputs continue; content not examined MUST NOT be claimed as validated. Identical records sharing an ID MUST deduplicate; conflicting records sharing an ID MUST block export and identify both source locations.

### FR-003

Version 0.1.0 MUST export schema-valid DCAT-US 3.0; the exporter MUST pass its pinned authoritative schema and semantic acceptance tests. DCAT-US 3.0 MUST precede ODCS 3.2.0 implementation, and both MUST be available for the first release. Later export targets MUST follow SPEC-005. Acceptance MUST validate both mandatory targets independently with synthetic minimum and detailed records.

### FR-004

Version 0.1.0 MUST export ODCS contracts using a minimal conforming scope; output MUST pass the selected pinned schema. Per DEC-027, the target MUST be ODCS 3.2.0 with identity, name, description, contract version, and available ownership/field-schema details. Quality and service commitments MUST be included only when explicitly supplied. Validated configuration MAY supply shared export-required metadata; missing target-required facts in otherwise valid intake MUST block only the affected target. Invalid intake MUST block all catalog exports by default under FR-002. Exact mappings and schema pins MUST pass architecture review.

### FR-005

DSCat MUST accept one intake artifact or a directory of intake artifacts and build the full catalog; single-artifact and directory acceptance scenarios MUST be verified. Discovery MUST select artifacts supported by the selected intake technology and ignore its temporary lock artifacts, with recursion only by explicit option (DEC-025). While Excel is selected, discovery MUST select .xlsx files and ignore Excel lock files. Duplicate/conflict handling MUST satisfy FR-002.

### FR-006

Catalog metadata MUST continue to support ownership, field schemas, provenance, retention, access restrictions, quality, and service commitments, with most details OPTIONAL. The collection intake required core MUST be collection name, accountable data owner/team response, six independent sensitivity responses under FR-014, submitter/accountable person for the entry, and completion date. Accountable owner/team MAY be Unknown. Collection description and current location MUST be OPTIONAL; submitters MUST NOT be required to supply a technical stable ID. Architecture MUST define deterministic catalog identity and preservation of submitted answers without inventing ownership or export facts.

A valid collection submission with sufficient supplied target-required facts and validated shared export configuration where required MUST export without completing unrelated optional details. Missing required export facts MUST block only the affected export with actionable diagnostics; defaults MUST NOT invent facts. Acceptance MUST distinguish valid minimum intake from incomplete inventory and target readiness, test each missing required response, and demonstrate both mandatory targets with sufficient supplied facts against pinned schemas. Absent description and Unknown accountable ownership MUST remain explicit in the catalog; the intake adapter MUST NOT fabricate a description, contact or owner to satisfy an older model. Rich catalog metadata MUST remain representable independently of this simplified workbook.

### FR-007

Collection intake MUST distinguish current amount held from the new amount of that collection produced per generating-process run. Both quantities MUST be OPTIONAL, nonnegative when supplied, and independently qualified as Estimate, Measured, or Unknown. Unknown MUST remain distinct from zero. The workbook MUST accept only decimal KB, MB, GB, TB, or PB; supplied known quantities MUST include a unit and basis. Optional generation frequency MUST describe typical runs and its period without treating input volume as produced output. No automatic forecasts or cost estimation are included.

Collection retention intake MUST support an OPTIONAL nonnegative whole-day duration measured from each batch's arrival at its destination, with Not yet determined, Proposed, or Confirmed status. Blank duration MUST remain undetermined; zero MUST mean immediate expiry. Derived collections MUST have independent retention answers. Intake MUST NOT require a separate confirmer or escalation-team field, enforce storage acceptance, authorize deletion, or implement deletion. Acceptance MUST cover absent, Unknown, known zero, positive and invalid quantities, decimal-only intake units, independent current/per-run values, fractional/negative retention rejection, and retention status consistency.

Existing canonical capacity capabilities MUST remain supported independently: current size, average/peak daily ingestion, measurement context/date, logical versus physical size, decimal and binary units normalized to bytes, ingestion windows, and duration/indefinite/Unknown retention. Registration estimates MUST remain distinct from measurements with logical/physical context, measurement dates or observation windows; omitted measurement context MUST NOT be fabricated. Simplified input MUST NOT erase or reinterpret saved capacity metadata. Version 0.1.0 MUST NOT implement forecasts.

### FR-008

A Pydantic-backed canonical JSON catalog MUST be the persisted source of truth, with completed submissions used only as intake and DCAT-US/ODCS derived from the canonical model. Storage MUST use organized flat files for now. Acceptance MUST demonstrate intake-to-canonical validation, JSON save/load without loss of supported metadata, and regeneration of standard exports from saved canonical data without the original submissions or a database.

### FR-010

The selected intake interface MUST provide applicable validation through controlled choices, field constraints, highlighting, and actionable error callouts where practical (DEC-026). Acceptance MUST demonstrate valid entries, missing required values, invalid units/numbers/dates, and duplicate IDs using synthetic inputs; architecture MUST map each check to interface feedback or document its limitation. DSCat MUST independently validate submitted data; bypassed or removed interface controls MUST NOT permit invalid catalog exports. While Excel is selected, generated workbooks MUST use applicable dropdowns, cell validation, highlighting, error callouts, and normal Excel formulas where practical, MUST NOT contain macros or executable code, and DSCat MUST NOT execute formulas or trust cached results.

### FR-011

Builds MUST represent exactly the selected inputs; omitted datasets MUST be absent from the new snapshot without changing previous snapshots. Existing output replacement MUST require an explicit option, and validation/write failures MUST preserve previous output (DEC-025). Acceptance MUST verify omission, refused replacement, successful explicit replacement, and preservation after validation/write failure.

### FR-012

The collection intake MAY capture a generating-process name, plain-language explanation, and semicolon-separated source collection names before this later capability. Sources need not already be registered. These free-text answers MUST be preserved without requiring resolved lineage links, automatic discovery, full PROV-O behavior, or full ODPS capability.

After the separate W3C DCAT 3 capability in SPEC-005, DSCat MUST support OPTIONAL manually supplied dataset-and-processing-step lineage through an OPTIONAL lineage section without enlarging the required intake core (DEC-029). Records MUST support upstream and derived dataset references, multiple-input derivation, processing software/tool and version, transformation descriptions, input/output dataset IDs, responsible teams/owners and handoffs, and OPTIONAL timestamps, process references, and supporting documentation. Canonical JSON MUST preserve supported lineage metadata and standards exports MUST include supported mappings. Acceptance MUST demonstrate a synthetic multi-input derivation and multi-step handoff, canonical save/load preservation, applicable export mappings, and validation of malformed references under the architecture-approved reference policy. External lineage ingestion and automatic discovery MUST remain deferred. Manually supplied lineage capture and export MUST distinguish dataset entities, processing activities, and responsible agents using PROV-O semantics, and MUST distinguish DCAT datasets, distributions, and data services in mappings. Acceptance MUST preserve those distinctions through round trips and exports, document unmapped relationships, and MUST NOT claim complete PROV-O conformance. Acceptance MUST include an explicit lineage export using the supported PROV-O terms and verify its intended graph relationships offline; serialization and exact supported term mappings remain architecture deliverables.

### NFR-001

DSCat MUST be an OS-agnostic, uv-managed Python package using the latest stable Python selected at initial implementation and a Typer entrypoint, with macOS as its primary target. Windows and Linux MUST remain portability targets using ordinary cross-platform Python tooling and standard packaging (DEC-028). Installation MUST use uv tool install with GitHub Release artifacts, with authenticated download when needed; specialized installers MUST NOT be required. First-release acceptance MUST demonstrate successful native macOS installation and the supported end-to-end workflow, including intake, canonical persistence and both mandatory exports. Verification MUST identify the operating systems, versions and environments actually tested and their limitations; Windows/Linux portability targets MUST NOT imply a mandatory verified-platform matrix or verified support without evidence.

### NFR-002

All structured input/output MUST use Pydantic models. Every structured and unstructured input/output boundary MUST have positive and negative tests (DEC-033), including valid, empty, boundary, malformed, unsupported, conflicting, and hostile cases where applicable. Output tests MUST verify valid results and safe rejection or handling of invalid/unrepresentable results, serialization errors, and write failures. Acceptance MUST map each boundary to tests and failure diagnostics/exit behavior; nonapplicable cases MUST have recorded rationale.

### NFR-003

Maintained Python MUST pass Ruff ALL rules with narrow documented conflict resolutions, Ruff formatting, and all available ty diagnostics at error severity; the target MUST be 100% statement and branch coverage, with narrow agent-selected exceptions documented by rationale, scope, risk, and compensating verification. Every business rule, including ordinary business logic, MUST have positive and negative behavior tests, covering applicable limits and failure paths (DEC-033). Regression and compatibility tests MUST protect supported behavior as code and schemas evolve; coverage percentages MUST NOT substitute for these tests.

### NFR-004

Dependency resolution MUST exclude artifacts less than 14 days old; committed configuration and locked dependency evidence MUST demonstrate the restriction.

### NFR-005

Security MUST cover supply-chain vulnerabilities and untrusted intake input; release evidence MUST include vulnerability checks and hostile-input verification against an approved threat model. Failure verification MUST demonstrate preservation of existing data/outputs, bounded safe termination, and recovery or retry where applicable; expected failure modes and remaining limitations MUST be recorded (DEC-033).

### NFR-006

Delivery MUST follow applicable planning gates, complete traceability for changed behavior, semantic versioning, and atomic Conventional Commits. Agents MUST own implementation, testing, local verification, and routine PR review/merging within approved scope without human PR review. Completion MUST follow the [task-class and delivery conditions](governance.md#definition-of-done). Ordinary source/documentation tasks MUST NOT require release publication or downloaded-release verification unless release delivery is explicitly included; release tasks MUST retain all applicable release acceptance and independent downloaded-artifact checks. Maintenance MUST NOT invent product requirements or reopen unchanged approved decisions.

### NFR-007

The human MUST receive a reproducible manual verification walkthrough before candidate-specific release authorization or, where release authority was explicitly delegated conditionally during planning, before those conditions are exercised to publish; each acceptance criterion MUST link to automated or manual evidence. The walkthrough and verification report MUST identify positive and negative scenarios, exact failure triggers, expected diagnostics/exit behavior, data/output preservation, cleanup, and applicable recovery steps (DEC-033).

### NFR-008

Published artifacts MUST use neutral identity and synthetic examples; staged and release artifact review MUST exclude private contextual affiliations and real catalog data.

### NFR-009

Catalog-building operations MUST be idempotent in their resulting catalog content and state effects: repeated builds from the same input content, configuration, and tool/schema versions MUST produce identical catalog results without duplicates or accumulating state. Repeating a command against an existing destination without the explicit replacement option MUST refuse replacement under FR-011; idempotence MUST NOT imply repeated command success or bypass overwrite protection. Canonical JSON and standards exports MUST be byte-identical for unchanged inputs, configuration, and tool/schema versions (DEC-025).

### NFR-010

Installed runtime functions MUST work offline with PyPI-sourced dependencies; intake-material generation, validation, and export MUST succeed with network access disabled and external schema resolution MUST NOT fetch remotely.

### NFR-011

Each release MUST include a machine-readable dependency SBOM identifying the released artifact; format, transitive coverage, and provenance MUST be verified in the release plan. Proposed refinement: the release plan MUST select a public machine-readable SBOM standard and version, validate the SBOM, cover resolved transitive runtime dependencies, bind it to wheel/sdist hashes and source revision, identify generator/version and dependency relationships, separate build/development components, and disclose missing/unknown identity, license or provenance fields. Acceptance MUST check completeness against the lock and installed artifact rather than equate generator success with coverage.

### NFR-012

Known High or Critical vulnerabilities MUST block release unless evidence establishes non-applicability; applicable findings MUST be fixed and non-applicability MAY be documented in VEX with execution-path evidence. Medium/Low findings MUST be tracked. Proposed refinement: known exploitation MUST independently block release at any severity unless artifact-specific applicability evidence establishes non-applicability. Release evidence MUST record advisory provenance/freshness, affected versions, assessment, remediation or execution-path non-applicability, and revisit conditions. Unknown status MUST NOT count as a clean assessment. These checks MUST occur during engineering/release preparation; installed runtime MUST NOT require live feeds.

### NFR-013

Intake schemas MUST be versioned and supported-version compatibility MUST be tested; unsupported versions MUST produce actionable errors. The compatibility policy MUST prioritize readability of older supported submissions. The undistributed workbook-1.0 format need not remain supported by the replacement collection intake; unsupported input MUST receive an actionable schema error. This intake compatibility change MUST NOT imply permission to discard or silently reinterpret persisted canonical catalogs; canonical compatibility and migration MUST be assessed separately. While Excel is selected, workbook schema compatibility MUST be the principal intake compatibility surface. A replacement decision MUST explicitly address existing submissions and any compatibility impact.

### NFR-014

DSCat MUST use the Obscurity Labs proprietary license. The LICENSE file, Python package metadata, and CLI help MUST provide consistent ownership and licensing information. Verification MUST confirm that this information is present and consistent in the source, built distributions, and CLI help.

### NFR-015

Repository changes MUST follow the active policy documented in docs/repository-policy.md. Verification MUST confirm that the documented policy matches the active repository settings and that changes follow the applicable integration workflow.

### NFR-016

Local verification and testing MUST be the primary quality gate; GitHub Actions MUST remain minimal and supplementary. Verification planning MUST cover all existing checks locally and identify the small CI subset, with evidence tied to the source revision.

### NFR-017

Approved software MUST be distributed through GitHub Releases in installable form. Under the standing human delegation recorded in [DEC-045](decisions.md#dec-045) (2026-11-17), agents MUST publish project-scope software releases after all applicable scope, verification, security, licensing, and artifact-identity checks; no further human authorization is required for that publication. Post-publication verification MUST demonstrate authenticated asset download, integrity/version checks, clean installation, CLI invocation, applicable acceptance scenarios, and offline runtime behavior using the released artifacts rather than the checkout.

### NFR-018

Architecture MUST treat the canonical model as the likely persisted-data migration boundary and MUST separate its logical schema from flat-file persistence to support a future database. The design MUST specify schema version identification, compatibility, and migration safeguards; verification MUST cover canonical round trips and supported/unsupported version handling. A database and speculative migration implementations MUST remain outside initial scope.

### NFR-019

Any RDF export MUST use JSON-LD serialization. Acceptance MUST verify valid JSON-LD and intended RDF graph semantics as well as applicable target-profile constraints; JSON-LD context processing MUST work offline under NFR-010. Non-RDF canonical JSON and other non-RDF exports MUST NOT be required to become RDF.

- SPEC-004 Requirements and acceptance criteria approval alone MUST NOT authorize implementation; model fields, command names, canonical file layout and schema version policy, exact schema pins, compatibility surface, and security verification procedures MUST be settled through subsequent planning.

- SPEC-005 Under DEC-043, version 0.1.0 MUST deliver DCAT-US 3.0 followed by ODCS 3.2.0, with both required for release. FR-001–FR-008, FR-010/011 and supporting NFRs remain initial capabilities; FR-013–FR-018 and NFR-020 and NFR-022 were included in the consolidated requirements approved under DEC-044 for that release. FR-012 lineage MUST follow a later, separate W3C DCAT 3 capability (FR-019), then ODPS metadata/export (FR-020), and lastly DCAT-US 1.1 (FR-021). These later capabilities MUST NOT block the first release. Later version numbers and detailed designs remain PENDING; capability ordering MUST NOT imply release authorization. Current requirements approval is recorded under DEC-044 and in [planning gates](planning-gates.md); downstream readiness and evidence remain governed by their applicable gates.
- SPEC-006 [FACT; HUMAN_DERIVED] DEC-023/024 MUST govern the required intake core and capacity policy. Stable IDs MUST be supplied by submitters. DEC-027 MUST govern validated shared export metadata configuration; defaults MUST NOT invent facts or data-use commitments.

- SPEC-007 [FACT; HUMAN_DERIVED] Per DEC-031/032, Excel SHOULD be the initial intake technology. Requirements describing intake capabilities MUST remain technology-neutral where practical. Technology-specific MUST clauses MUST apply only while that technology is selected and MUST NOT make its selection mandatory. A technology replacement MUST revise or retire its specific clauses and acceptance criteria, preserve applicable technology-neutral obligations, and resolve compatibility impacts through affected planning approvals. This clarification MUST NOT select or authorize another technology now.


## Research additions and refinements

The requirements additions and explicitly marked refinements above were approved as part of the exact consolidated package under [DEC-044](decisions.md#dec-044) on 2026-11-17; the approved source revision is `69b686a3d0b1da49290ca37d577d46fb8b63dbfb`. Their source-revision PENDING/proposed approval wording is historical. Optional metadata MUST NOT enlarge the FR-006 core. The authorized collection-intake replacement in [planning gates](planning-gates.md#collection-intake-readiness) governs the current required responses; historical four-field wording does not govern the replacement interface. Acceptance applies to version 0.1.0; detailed encodings and controls MUST pass architecture and planning gates.

### FR-013

DSCat MUST distinguish valid intake, inventory completeness, and readiness for each export target. A submission satisfying the FR-006 collection core MUST remain valid without optional details; absent export-required facts MUST block only readiness for the affected target without fabricating values. Inventory completeness MUST be assessed against explicitly selected criteria and supplied evidence, not inferred from parser success. Acceptance MUST independently demonstrate valid-but-incomplete, valid-but-target-unready, ready, and invalid submissions, including sufficient shared configuration.

### FR-014

Collection intake MUST require independent Yes, No, or Unknown responses for PII, PHI, CUI, PCII, ISVI, and Other sensitive data. Multiple Yes responses MUST be allowed. Other sensitive data = Yes MUST require a category description; uncertainty explanation MAY be supplied otherwise. These responses MUST preserve reported status without establishing formal designation, certification, permission to disclose, or storage/access authorization. Acceptance MUST test all six response constraints, overlapping Yes responses, missing responses and conditional Other descriptions.

Records MUST separately represent data access/use restrictions, metadata disclosure restrictions, and metadata publication approval. Optional supplied determinations MUST distinguish unknown, partially restricted, fully restricted, and unrestricted, with authority/reference, rationale, determination date, and review status; missing decisions MUST remain unknown. Publication approval MUST NOT imply access authorization or a legal determination. Public projections MUST fail closed: only explicitly approved records and allowlisted fields/values MAY be emitted; unknown approval MUST prevent public projection. Acceptance MUST test nested lineage, contacts, locations, URLs, free text, and extension fields for leakage, including new unknown fields, and distinguish safe schema-valid output from approval to publish it. Local export MUST NOT itself publish or grant access.

### FR-015

Optional records-management metadata MUST support disposition authority/reference, retention trigger, duration or instruction, and legal-hold/review status independently of FR-007 capacity retention. Conflicting or unknown instructions MUST remain explicit. Acceptance MUST round-trip separate capacity and records-retention values, unknowns, and holds without deriving destruction dates from capacity estimates. DSCat MUST NOT authorize disposition or automatically delete datasets or records.

### FR-016

Optional metadata MUST support inventory-added date, metadata-review date, dataset-modified date, update frequency, accountable owner, steward, and contact/maintainer as distinct roles; domain identifiers MAY be supplied. Dataset-modified dates MUST NOT be substituted for metadata review or inventory addition dates. The entry submitter and completion date MUST remain distinct from the accountable data owner/team, dataset modification, metadata review, inventory addition, and batch arrival. Unknown accountable ownership MUST remain explicit; a submitter label MUST NOT become inferred data ownership. Acceptance MUST round-trip distinct supplied roles/dates, preserve absent values, validate dates and role references, and demonstrate no inferred ownership from a contact label.

### FR-017

Optional consumer documentation MUST support intended uses, limitations, field meanings, access instructions, semantic definition references, and explicitly supplied quality/service commitments. Empty commitment fields MUST NOT become guarantees; an ODCS document MUST NOT imply agreement, provisioned access, or live enforcement. Semantic references MUST be preserved offline without dereferencing. Local machine-readable governance checks MUST report conformity to declared metadata rules and unperformed checks, without claiming organizational policy enforcement. Acceptance MUST preserve references and consumer detail, reject malformed supplied values, distinguish absent commitments from invalid supplied commitment metadata, and demonstrate offline checking without contacting referenced services.

### FR-018

Dataset, contract, and data-product identities MUST remain distinct; an optional product reference MUST NOT imply that a dataset is a complete data product. Application, intake schema, canonical schema, contract, and dataset versions MUST have independent meanings and MUST NOT be substituted for one another or for the ODCS specification version. Each mandatory target mapping MUST specify canonical-to-target field meaning, cardinality, requiredness, transformations, and loss/omission behavior. Acceptance MUST demonstrate distinct identity/version values, supported/unsupported schema versions, canonical preservation of unmappable metadata, and positive/negative mapping fixtures against complete pinned offline schemas. ODCS MUST remain 3.2.0 under FR-004.

### NFR-020

Metadata collection and diagnostics MUST minimize personal and sensitive information. Intake guidance MUST prefer role-based contacts; submissions MUST NOT contain data samples, credentials, secrets, or unnecessary personal details. Public projection under FR-014 and operational diagnostics MUST use explicit safe fields; errors MUST identify actionable locations without echoing arbitrary submitted contents or secret/private paths. Acceptance MUST use synthetic nested sensitive strings, formula-like values, role contacts, and hostile error inputs to verify safe output and redaction without claiming perfect detection of arbitrary secrets.

### NFR-022

The project MUST document GitHub Private Vulnerability Reporting as its security reporting route. Before release, verification MUST confirm that the feature is enabled and the documented reporting link is correct.

The security policy MUST briefly describe assessing reports, addressing confirmed issues as appropriate, and coordinating disclosure with reporters.

## Later capability acceptance

DEC-043 approved the capability scope and sequence below before this consolidated revision existed; DEC-044 later approved the exact consolidated requirements package at its recorded source revision and hashes. This current NFR-017 authority clarification relies on DEC-045's explicit human delegation of project-scope release publication after required checks; under the governance prior-approval uniqueness exception, no separate human publication authorization is a valid additional gate. DEC-044 does not approve the revised bytes. Current applicability of first-release architecture and implementation-plan readiness under DEC-046/047 MUST follow the [bounded reconciliation](planning-gates.md#bounded-readiness-reconciliation) before dependent implementation. Each capability MUST pass applicable requirements, architecture, implementation-plan and release gates before dependent execution.

### FR-019

After the first release, DSCat MUST provide a separate W3C DCAT 3 export capability, distinct from DCAT-US profiles. Acceptance MUST verify intended DCAT 3 graph semantics, JSON-LD serialization and offline resource closure using synthetic dataset, distribution and data-service cases; target-specific missing facts MUST affect only that target. Exact supported terms, resource pins and mappings MUST pass architecture approval.

### FR-020

After FR-012 lineage, DSCat MUST capture, validate, preserve and export ODPS product metadata with distinct product identities, dataset references and ODCS contract links. Product lifecycle states and supplied transitions MUST be recorded and validated; input/output ports MUST describe and validate interfaces and access metadata. Acceptance MUST cover synthetic valid and invalid product links, lifecycle transitions and port metadata, canonical round trips and conforming ODPS exports. Exact ODPS version, state vocabulary, allowed transitions, link/reference policy and port field mappings MUST be settled through architecture approval rather than invented here. Access provisioning, deployment and live endpoint testing MUST remain outside this capability.

### FR-021

After FR-020, DSCat MUST provide DCAT-US 1.1 export. Acceptance MUST verify the selected pinned profile and semantic mappings offline, identify unrepresentable metadata without losing canonical information, and keep its readiness independent of other targets. This later capability MUST NOT delay the mandatory first release.

## Retired requirement IDs

NFR-021 was removed in full by explicit user direction on 2026-11-20. The ID MUST NOT be reused. Its former text and acceptance remain available in [the preceding requirements revision](https://github.com/obscuritylabs/dscat/blob/9634f0a/docs/requirements.md#nfr-021); affected design, plan, traceability and release obligations are reconciled under [the removal disposition](planning-gates.md#requirement-removal). Historical approvals and observations remain attributed to their exact candidates.
