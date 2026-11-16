# Intake and catalog proposals

### INTAKE-001

[ASSUMPTION; LLM_ASSUMPTION] The human SHOULD review the following choices before requirements approval; these proposals MUST NOT authorize implementation.
### INTAKE-002

[FACT; HUMAN_DERIVED] Per DEC-023, a workbook MUST contain Instructions and Datasets sheets with OPTIONAL Fields and Details/Quality sheets. Each dataset MUST occupy one main-sheet row. People completing workbooks MUST supply stable IDs; exact ID syntax MUST remain pending.
### INTAKE-003

[FACT; HUMAN_DERIVED] Per DEC-023/024, required fields MUST be stable dataset ID, title, description, and contact/owner. Capacity measurements MUST accept explicit Unknown. Validated shared export-required metadata configuration MAY be used under the accepted DEC-027 direction; its schema and mappings MUST remain pending architecture. Defaults MUST NOT fabricate facts.
### INTAKE-004

[ASSUMPTION; LLM_ASSUMPTION] Optional details SHOULD include field names/types, provenance, retention, access restrictions, quality expectations, and service commitments. Empty quality or service fields MUST NOT be converted into guarantees. Workbook help SHOULD provide short examples and controlled choices where useful.
### INTAKE-005

[FACT; HUMAN_DERIVED] Capacity metadata MUST support current size, average and peak daily ingestion, retention, and measurement date, with explicit Unknown allowed, per DEC-012 D25. Unknown MUST remain distinct from zero. Additional accepted capacity policy MUST follow INTAKE-018 and DEC-024.
### INTAKE-006

[FACT; HUMAN_DERIVED] Version 0.1.0 MUST export capacity metadata for human analysis and MUST NOT calculate forecasts. Explicit Unknown values MUST remain available so missing measurements are visible rather than interpreted as zero.
### INTAKE-007

[FACT; HUMAN_DERIVED] Canonical catalog JSON MUST preserve the validated catalog model, including capacity and optional metadata, and MUST be the authoritative persisted export in organized flat files. DCAT-US and ODCS MUST be derived from the canonical model, per DEC-020. Exact field and file organization choices MUST remain pending architecture approval.
### INTAKE-008

[FACT; HUMAN_DERIVED] Per DEC-025, directory discovery MUST select .xlsx files, ignore Excel lock files, and recurse only with an explicit option. The earlier recommendation to separate input and output directories MUST remain proposed.
### INTAKE-009

[FACT; HUMAN_DERIVED] Identical records with the same dataset ID MUST be deduplicated. Different records sharing an ID MUST block export and report both source locations, per DEC-012 D24. Missing-ID behavior MUST follow DEC-025/INTAKE-017; exact normalization MUST remain pending architecture.
### INTAKE-010

[FACT; HUMAN_DERIVED] Per DEC-025, each build MUST represent exactly the selected inputs; omitted datasets MUST be absent from the new snapshot, and previous snapshots MUST remain untouched. Existing output MUST require an explicit replacement option. Validation or write failures MUST preserve previous output. Atomic publication details MUST be specified in architecture.
### INTAKE-011

[FACT; HUMAN_DERIVED] Per DEC-025, identical inputs, configuration, and tool/schema versions MUST produce byte-identical canonical JSON and standards exports. Serialization and timestamp policies MUST be specified in architecture.
### INTAKE-012

Per FR-002/NFR-005, validation MUST examine every independently readable input within approved safe processing limits and accumulate discoverable file, sheet, row, field, and cross-record errors. Unsafe, resource-limited, or unreadable content MUST produce an explicit diagnostic; dependent checks MUST be reported as unperformed rather than passed or populated with invented cascading failures. Validation MUST continue on independent inputs and MUST block catalog exports by default on any failure. A separate structured diagnostic report MAY be written without publishing catalog outputs. Detailed limits and diagnostic design MUST pass architecture approval.
### INTAKE-013

[ASSUMPTION; LLM_ASSUMPTION] Each workbook MUST identify its schema version independently of the package version. Supported older workbook fixtures MUST remain in regression tests. New optional columns SHOULD be preferred over breaking changes; migrations SHOULD preserve original intake files and require explicit output destinations.
### INTAKE-014

[FACT; HUMAN_DERIVED] DEC-028 MUST supersede the proposed mandatory platform matrix: Windows, macOS, and Linux MUST be portability targets with ordinary Python tooling and uv tool installation from GitHub Release artifacts. Excel verification arrangements MUST remain deferred without claiming verification or waiving acceptance.
### INTAKE-015

[FACT; HUMAN_DERIVED] DEC-027 MUST govern ODCS 3.2.0 scope: identity, name, description, contract version, and available ownership/field-schema details. Quality and service commitments MUST be explicitly supplied. Validated configuration MAY supply shared export-required metadata; missing required facts MUST block export. Exact mappings and pinned resources MUST remain pending architecture.

### INTAKE-016

[FACT; HUMAN_DERIVED] Workbook intake MUST validate into the canonical Pydantic catalog model before JSON persistence and standards serialization. Approval of this direction MUST be distinguished from pending approval of its precise shape and migration policy. The [canonical model notes](canonical-model.md) MUST separate approved direction from proposed design details.
### INTAKE-017

[FACT; HUMAN_DERIVED] Per DEC-023/025, submitters MUST supply stable IDs and missing IDs MUST fail validation. Duplicate comparison MUST operate on validated normalized metadata excluding source locations, while preserving all source locations for diagnostics. Exact ID syntax and normalization rules MUST remain pending architecture.
### INTAKE-018

[FACT; HUMAN_DERIVED] Per DEC-024, capacity fields MUST distinguish logical from physical sizes, accept explicit decimal and binary units normalized to bytes, and record the observation window for average/peak ingestion. Retention MUST allow a duration, indefinite, or Unknown. Exact encodings MUST remain pending detailed design. The additional proposal that numeric rates MUST NOT be interpreted as net storage growth without evidence MUST remain unapproved.

### INTAKE-019

[FACT; HUMAN_DERIVED] Per DEC-026, workbook generation MUST use normal Excel validation features and formulas where practical, without macros or executable code. FR-010 MUST govern acceptance and independent import validation.

### INTAKE-020

[FACT; HUMAN_DERIVED] Per DEC-029, an OPTIONAL Lineage sheet MUST capture manually supplied dataset relationships and processing steps, including multi-input derivation, processing tools/versions, transformations, responsibility, handoffs, and OPTIONAL supporting evidence. FR-012 MUST govern scope and acceptance. Exact row structure, references, and validation feedback MUST remain pending architecture.
### INTAKE-021

[FACT; HUMAN_DERIVED] Per DEC-030, agents MUST raise concrete workbook usability or complexity limitations with the human before proposing an alternative intake process. Workbook feasibility MUST be assessed during detailed design using synthetic lineage examples; a different intake process MUST require affected planning approvals.

### INTAKE-022

[FACT; HUMAN_DERIVED] Per DEC-031/SPEC-001/SPEC-007, Excel SHOULD be the initial intake mechanism and MUST NOT permanently constrain the product. Current workbook requirements MUST apply to the planned workbook implementation. A guided form workflow MAY be considered when evaluating alternatives, without selecting a replacement now or bypassing affected approval gates.

### INTAKE-023

[FACT; HUMAN_DERIVED] DEC-032/SPEC-007 MUST govern all workbook-specific decisions and proposals in this document: their technology-specific obligations MUST apply only while Excel remains selected. Replacement planning MUST revise or retire those details and preserve applicable technology-neutral intake capabilities; historical decisions MUST remain as history rather than make Excel permanently mandatory.

## Draft capacity policy

The following are agent-proposed detailed rules supporting FR-007 and DEC-024, not approved architecture. They MUST be approved with the field encodings before implementation.

- A blank optional capacity field MUST mean “not supplied”; explicit Unknown MUST mean “supplied as unknown”; numeric zero MUST mean a measured zero. Canonical storage MUST preserve these states separately. Unknown or absent quantities MUST NOT acquire numeric defaults or fabricated dates/units.
- Known sizes and rates MUST be finite, nonnegative decimal values with explicit decimal/binary units. Conversion MUST use decimal arithmetic rather than binary floating-point rounding. Fractional input quantities MAY be accepted; normalized bytes MUST be exact, and a nonintegral byte quantity MUST fail rather than round silently. A rate MUST identify bytes per day and its observation window; architecture MUST specify precision limits and maximum representable values.
- Logical and physical measurements MUST identify their basis. Average and peak rates MUST identify the same basis/window before comparison; peak MUST NOT be below average when directly comparable. Incomparable windows MUST remain explicit rather than trigger invented comparisons. A known observation window MUST have an end no earlier than its start; zero-duration rate windows MUST fail.
- Measurement dates MUST use valid calendar dates in YYYY-MM-DD form; datetime windows MUST use timezone-aware ISO 8601 timestamps. Numeric retention MUST use a nonnegative integer count of days, with zero distinct from indefinite, Unknown, and absent. Calendar-month/year durations MUST fail with a day-based correction hint rather than use an assumed conversion. These encoding choices MUST receive architecture approval and synthetic boundary tests.

## Draft minimum-export demonstration

FR-006 requires the four-field intake core, not invented facts. Before architecture approval, the mapping MUST demonstrate ID, title, description, and contact/owner plus validated shared configuration producing each mandatory export without optional detail sheets. The DCAT-US mapping MUST resolve contact shape and identifier encoding; an owner label alone MUST NOT be assumed sufficient contact metadata. ODCS MUST supply schema-defined apiVersion/kind constants and an explicitly configured contract version, with description mapped to the correct target shape. Missing facts MUST fail with field/source diagnostics. Synthetic positive and negative fixtures MUST validate against the complete offline pinned schemas; this draft MUST NOT be presented as a completed conformance demonstration.
