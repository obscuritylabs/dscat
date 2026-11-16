# Intake design proposals

## Authority and accepted-direction pointers

[Planning gates](planning-gates.md) governs approval status. The exact approved requirements baseline governs accepted scope; the current research revision remains proposed under SPEC-002; these notes own unresolved intake design proposals. Proposals MUST receive applicable architecture/implementation-plan approval before implementation. Workbook-specific obligations apply only while Excel remains selected under SPEC-007. Original notes are available with `git show 0b7b824:docs/intake-proposals.md`.

| Stable source | Current home |
| --- | --- |
| <a id="intake-001"></a>INTAKE-001 | [Planning gates](planning-gates.md): authority; workbook obligations are conditional under SPEC-007. |
| <a id="intake-002"></a>INTAKE-002 | [DEC-023](decisions.md#dec-023): initial Excel layout; exact ID syntax pending architecture. |
| <a id="intake-003"></a>INTAKE-003 | [FR-006](requirements.md#fr-006): required core and shared configuration; defaults MUST NOT fabricate facts. |
| <a id="intake-005"></a>INTAKE-005 | [FR-007](requirements.md#fr-007): accepted capacity capabilities. |
| <a id="intake-006"></a>INTAKE-006 | [FR-007](requirements.md#fr-007): capacity scope and no forecasts. |
| <a id="intake-007"></a>INTAKE-007 | [FR-008](requirements.md#fr-008); [canonical model proposals](canonical-model.md). |
| <a id="intake-008"></a>INTAKE-008 | [FR-005](requirements.md#fr-005): discovery; separate input/output directories remain proposed below. |
| <a id="intake-009"></a>INTAKE-009 | [FR-002](requirements.md#fr-002): duplicate/conflict behavior. |
| <a id="intake-010"></a>INTAKE-010 | [FR-011](requirements.md#fr-011): snapshots and replacement; atomic publication pending architecture. |
| <a id="intake-011"></a>INTAKE-011 | [NFR-009](requirements.md#nfr-009): byte determinism; serialization/timestamps pending architecture. |
| INTAKE-012 | [Current validation policy](#intake-012): safe aggregate validation; detailed limits/diagnostics pending architecture. |
| <a id="intake-014"></a>INTAKE-014 | [NFR-001](requirements.md#nfr-001); [DEC-028](decisions.md#dec-028): deferred Excel verification. |
| <a id="intake-015"></a>INTAKE-015 | [FR-004](requirements.md#fr-004): ODCS scope; mappings/resources pending architecture. |
| <a id="intake-016"></a>INTAKE-016 | [Canonical model proposals](canonical-model.md): detailed shape and migration policy. |
| <a id="intake-017"></a>INTAKE-017 | [FR-002](requirements.md#fr-002), [FR-006](requirements.md#fr-006); [DEC-025](decisions.md#dec-025): ID/normalized comparison; exact rules pending architecture. |
| <a id="intake-018"></a>INTAKE-018 | [FR-007](requirements.md#fr-007); [draft capacity policy](#draft-capacity-policy): unapproved detailed rules. |
| <a id="intake-019"></a>INTAKE-019 | [FR-010](requirements.md#fr-010): workbook controls and safe formula handling. |
| <a id="intake-020"></a>INTAKE-020 | [FR-012](requirements.md#fr-012): optional lineage; references/mappings pending architecture. |
| <a id="intake-021"></a>INTAKE-021 | [DEC-030](decisions.md#dec-030): concrete usability escalation; feasibility proposal below. |
| <a id="intake-022"></a>INTAKE-022 | [SPEC-001](requirements.md): initial Excel SHOULD choice; alternatives unselected. |
| <a id="intake-023"></a>INTAKE-023 | [SPEC-007](requirements.md): conditional workbook obligations and replacement change control. |

## Current validation policy

### INTAKE-012

Per [FR-002](requirements.md#fr-002)/[NFR-005](requirements.md#nfr-005), validation MUST examine every independently readable input within approved safe processing limits and accumulate discoverable file, sheet, row, field, and cross-record errors. Unsafe, resource-limited, or unreadable content MUST produce an explicit diagnostic; dependent checks MUST be reported as unperformed rather than passed or populated with invented cascading failures. Validation MUST continue on independent inputs and MUST block catalog exports by default on any failure. A separate structured diagnostic report MAY be written without publishing catalog outputs. Detailed limits and diagnostic design MUST pass architecture approval.

## Unresolved intake proposals

### INTAKE-004

Agent proposal: workbook help SHOULD provide short examples and controlled choices where useful. Optional details follow FR-006; empty quality/service fields MUST NOT become guarantees under FR-004.

### INTAKE-013

Agent proposal: each workbook MUST identify its schema version independently of the package version. Supported older workbook fixtures MUST remain in regression tests. New optional columns SHOULD be preferred over breaking changes; migrations SHOULD preserve original intake files and require explicit output destinations.

Additional proposals: input and output directories SHOULD be separate. Workbook feasibility MUST be assessed during detailed design using synthetic lineage examples. These choices remain unapproved; an alternative intake mechanism requires affected planning approvals.

## Draft capacity policy

The following are agent-proposed detailed rules supporting FR-007 and DEC-024, not approved architecture. They MUST be approved with the field encodings before implementation.

- A blank optional capacity field MUST mean “not supplied”; explicit Unknown MUST mean “supplied as unknown”; numeric zero MUST mean a measured zero. Canonical storage MUST preserve these states separately. Unknown or absent quantities MUST NOT acquire numeric defaults or fabricated dates/units.
- Known sizes and rates MUST be finite, nonnegative decimal values with explicit decimal/binary units. Conversion MUST use decimal arithmetic rather than binary floating-point rounding. Fractional input quantities MAY be accepted; normalized bytes MUST be exact, and a nonintegral byte quantity MUST fail rather than round silently. A rate MUST identify bytes per day and its observation window; architecture MUST specify precision limits and maximum representable values.
- Numeric ingestion rates MUST NOT be interpreted as net storage growth without evidence.
- Logical and physical measurements MUST identify their basis. Average and peak rates MUST identify the same basis/window before comparison; peak MUST NOT be below average when directly comparable. Incomparable windows MUST remain explicit rather than trigger invented comparisons. A known observation window MUST have an end no earlier than its start; zero-duration rate windows MUST fail.
- Measurement dates MUST use valid calendar dates in YYYY-MM-DD form; datetime windows MUST use timezone-aware ISO 8601 timestamps. Numeric retention MUST use a nonnegative integer count of days, with zero distinct from indefinite, Unknown, and absent. Calendar-month/year durations MUST fail with a day-based correction hint rather than use an assumed conversion. These encoding choices MUST receive architecture approval and synthetic boundary tests.

## Draft minimum-export demonstration

FR-006 requires the four-field intake core, not invented facts. Before architecture approval, the mapping MUST demonstrate ID, title, description, and contact/owner plus validated shared configuration producing each mandatory export without optional detail sheets. The DCAT-US mapping MUST resolve contact shape and identifier encoding; an owner label alone MUST NOT be assumed sufficient contact metadata. ODCS MUST supply schema-defined apiVersion/kind constants and an explicitly configured contract version, with description mapped to the correct target shape. Missing facts MUST fail with field/source diagnostics. Synthetic positive and negative fixtures MUST validate against the complete offline pinned schemas; this draft MUST NOT be presented as a completed conformance demonstration.


## Research revision intake dependencies

The proposed additions in [the impact package](research-additions.md) MUST preserve ID, title, description, and contact/owner as the only required intake core. Optional owner/steward/domain, review and dataset dates, restrictions, disposition, consumer documentation, definitions, and lineage detail MUST NOT become hidden intake requirements. Architecture MUST demonstrate separate validity, completeness, and target-readiness diagnostics and an accessible selected-application workflow before implementation. A minimal valid submission MUST NOT be assumed approved for public projection; missing publication authority MUST fail closed under proposed FR-014 without invalidating the minimum intake itself.
