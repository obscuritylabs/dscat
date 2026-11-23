# Intake design proposals

## Authority and accepted-direction pointers

[Planning gates](planning-gates.md) governs approval status. The exact approved requirements baseline governs accepted scope; the consolidated requirements and research impact scope are approved under DEC-044; [the architecture package](architecture.md) and [collection-intake design](collection-intake-design.md) own detailed design. Proposals MUST receive architecture disposition and agent implementation-plan readiness under the [approval policy](governance.md#required-sdlc-and-approval-gates) before implementation. Workbook-specific obligations apply only while Excel remains selected under SPEC-007. Original notes are available with `git show 0b7b824:docs/intake-proposals.md`.

| Stable source | Current home |
| --- | --- |
| <a id="intake-001"></a>INTAKE-001 | [Planning gates](planning-gates.md): authority; workbook obligations are conditional under SPEC-007. |
| <a id="intake-002"></a>INTAKE-002 | [FR-001](requirements.md#fr-001): replacement collection layout; [DEC-023](decisions.md#dec-023): historical initial layout; [ID normalization](architecture.md#identity-and-normalization); disposition follows DEC-046. |
| <a id="intake-003"></a>INTAKE-003 | [FR-006](requirements.md#fr-006): required core and shared configuration; defaults MUST NOT fabricate facts. |
| <a id="intake-005"></a>INTAKE-005 | [FR-007](requirements.md#fr-007): accepted capacity capabilities. |
| <a id="intake-006"></a>INTAKE-006 | [FR-007](requirements.md#fr-007): capacity scope and no forecasts. |
| <a id="intake-007"></a>INTAKE-007 | [FR-008](requirements.md#fr-008); [canonical model proposals](canonical-model.md). |
| <a id="intake-008"></a>INTAKE-008 | [FR-005](requirements.md#fr-005): discovery and disjoint paths follow the [compatibility contract](architecture.md#initial-compatibility-contract), dispositioned under DEC-046. |
| <a id="intake-009"></a>INTAKE-009 | [FR-002](requirements.md#fr-002): duplicate/conflict behavior. |
| <a id="intake-010"></a>INTAKE-010 | [FR-011](requirements.md#fr-011): snapshots and replacement; [publication design](architecture.md#storage-and-deterministic-publication); disposition follows DEC-046. |
| <a id="intake-011"></a>INTAKE-011 | [NFR-009](requirements.md#nfr-009): byte determinism; [deterministic serialization](architecture.md#storage-and-deterministic-publication); disposition follows DEC-046. |
| INTAKE-012 | [Current validation policy](#intake-012): safe aggregate validation; detailed limits/diagnostics dispositioned under DEC-046. |
| <a id="intake-014"></a>INTAKE-014 | [NFR-001](requirements.md#nfr-001); [DEC-028](decisions.md#dec-028): deferred Excel verification. |
| <a id="intake-015"></a>INTAKE-015 | [FR-004](requirements.md#fr-004): ODCS scope; first-release mappings/resources dispositioned under DEC-046. |
| <a id="intake-016"></a>INTAKE-016 | [Canonical model proposals](canonical-model.md): detailed shape and migration policy. |
| <a id="intake-017"></a>INTAKE-017 | [FR-002](requirements.md#fr-002), [FR-006](requirements.md#fr-006); [DEC-025](decisions.md#dec-025): [ID normalization](architecture.md#identity-and-normalization); disposition follows DEC-046. |
| <a id="intake-018"></a>INTAKE-018 | [FR-007](requirements.md#fr-007); [draft capacity policy](#draft-capacity-policy): detailed rules dispositioned under DEC-046. |
| <a id="intake-019"></a>INTAKE-019 | [FR-010](requirements.md#fr-010): workbook controls and safe formula handling. |
| <a id="intake-020"></a>INTAKE-020 | [FR-012](requirements.md#fr-012): optional lineage; references/mappings pending architecture. |
| <a id="intake-021"></a>INTAKE-021 | [DEC-030](decisions.md#dec-030): concrete usability escalation; feasibility proposal below. |
| <a id="intake-022"></a>INTAKE-022 | [SPEC-001](requirements.md): initial Excel SHOULD choice; alternatives unselected. |
| <a id="intake-023"></a>INTAKE-023 | [SPEC-007](requirements.md): conditional workbook obligations and replacement change control. |

## Current validation policy

### INTAKE-012

Per [FR-002](requirements.md#fr-002)/[NFR-005](requirements.md#nfr-005), validation MUST examine every independently readable input within approved safe processing limits and accumulate discoverable file, sheet, row, field, and cross-record errors. Unsafe, resource-limited, or unreadable content MUST produce an explicit diagnostic; dependent checks MUST be reported as unperformed rather than passed or populated with invented cascading failures. Validation MUST continue on independent inputs and MUST block all catalog exports by default on invalid intake. Missing target-specific export facts in otherwise valid intake MUST block only the affected target under FR-004/013. A separate structured diagnostic report MAY be written without publishing catalog outputs. Detailed limits and diagnostic design MUST pass architecture disposition under that policy.

## Intake design navigation

### INTAKE-004

The proposed field controls, examples and feedback MUST follow the [versioned intake layout](architecture.md#intake-layout-and-field-encodings). Empty commitments MUST remain absent under FR-004/017.

### INTAKE-013

The proposed supported-version and fixture policy MUST follow the [compatibility contract](architecture.md#initial-compatibility-contract). Workbook verification MUST retain applicable compatibility evidence under [the compatibility contract](architecture.md#initial-compatibility-contract).

## Draft capacity policy

The detailed proposed Unknown/absent/zero states, units, decimal precision, bounds, dates, observation windows and retention encodings MUST have one authoritative home in [capacity encoding](architecture.md#capacity-encoding). DEC-046 included these designs in its architecture readiness; current applicability follows the [bounded reconciliation](planning-gates.md#bounded-readiness-reconciliation). Product implementation remains PENDING.

## Draft minimum-export demonstration

The exact core-plus-configuration mappings, pinned closure and research-only positive/negative evidence MUST follow [standards architecture](architecture-standards.md). The FR-006 collection core MUST remain valid intake; target-specific facts MUST NOT be invented. Executed research validation MUST NOT substitute for product exporter acceptance tests.

## Research revision intake dependencies

The current required intake responses MUST follow [FR-006](requirements.md#fr-006) and the [authorized replacement](planning-gates.md#collection-intake-readiness); historical DEC-044 attribution remains unchanged. [Canonical schema](architecture.md#canonical-record-schema) and [assessment/projection assurance](architecture-assurance.md) MUST distinguish valid intake, inventory completeness, target readiness and publication authority. Missing publication authority MUST fail closed for public projection without invalidating minimum intake. Prior detailed proposals MUST be retrieved through Git history rather than treated as competing current architecture.

## Collection-first intake and worked example

### INTAKE-024

This section specifies the authorized replacement interface under [FR-001](requirements.md#fr-001), [FR-006](requirements.md#fr-006), [FR-007](requirements.md#fr-007) and [FR-014](requirements.md#fr-014). [Planning gates](planning-gates.md#collection-intake-readiness) owns authority and readiness. The workbook MUST contain instructions and one primary Intake table; required responses MUST follow FR-006. Description, location, current volume, consumer/use/access, retention and generation details MUST be optional. No collection registration MUST depend on a known generating process. Several generating processes MAY be described in one row; source collection names MUST be optional semicolon-separated plain text, without mandatory registration or linking.

The input groups MUST be collection identity/description/location; accountable owner/team and six sensitivity responses with Other explanation; entry submitter and completion date; current quantity/unit/basis; consumers/use/access pattern; retention days/status/decision authorizer; and optional generating process/explanation/sources/per-run amount/unit/basis/typical runs/period. Access pattern describes use and MUST NOT grant authorization. Completion MUST use ordinary Excel editing without required macros or runtime scripts. The workbook MUST offer optional `Retention decision authorized by` text without requiring a separate retention confirmer or an escalation-team field. Supplied attribution MUST remain descriptive metadata under FR-007 and MUST NOT grant disposal or publication authority.

`dscat template --output example-intake.xlsx --examples` MUST seed a small coherent worked example using real public tool names with invented metadata. It MUST demonstrate distinct collections, several inputs, optional generation details, known and Unknown amounts/ownership/sensitivity, distinct current/per-run volumes, and independently proposed retention durations. It MUST explain that source-name text is descriptive rather than a complete formal lineage graph. Comprehensive population of every catalog capability is excluded.

- Instructions MUST identify all seeded rows as synthetic ordinary records and explain how to replace or remove them. Examples MUST NOT be silently discarded on intake or become defaults for later submissions.
- Instructions MUST explain that collection names aid discovery, owner/team responses identify accountability or its uncertainty, sensitivity answers flag review needs, quantity/basis distinguish size from uncertainty, and separate current/per-run amounts avoid confusing holdings with production. These values MUST NOT imply publication approval, storage permissions, deletion authority, benchmarks or capacity guarantees.
- Seed values MUST be fixed and bundled, with no live service integration, imported private metadata, macros, external connections or formulas in input cells. Public documentation references MAY explain tools without requiring runtime access.
- Generation without `--examples` MUST leave all input rows blank. Both modes MUST preserve input controls, formatting, deterministic generation, overwrite refusal, explicit replacement and failure-preservation behavior.

Acceptance MUST cover:

1. Blank and seeded generation, one-table layout, required core and optional groups, coherent invented examples, explanatory instructions and ordinary parser validation with no special exemptions.
2. Removal/replacement of examples, including a valid minimum collection row with optional details blank; no seeded records remaining after removal.
3. Each missing required response, independent sensitivity states and overlap, conditional Other explanation, missing versus Unknown owner/team, valid/invalid completion dates and preserved distinct submitter responsibility.
4. Decimal-only units, negative/malformed values, Unknown versus zero, separate current/per-run amounts, fractional retention rejection, independently supplied retention statuses, and optional attribution preserved without inferring authorization. Target-required missing facts MUST remain ordinary target-readiness diagnostics.
5. Existing-file refusal, explicit replacement, output preservation on failure, package safety, unsupported-version errors and deterministic output in both modes.
6. Ordinary Excel completion and navigation using the accepted layout. The explicit instruction to proceed without another prototype review MUST NOT create a repeated human workbook approval gate; product verification MUST still record its actual observations and limitations.

The prior multi-sheet workbook layout is undistributed and need not be read by the replacement parser. Supported collection workbook revisions and the bounded form alias MUST follow the [collection compatibility design](collection-intake-design.md#workbook-and-typed-boundaries). This does not waive persisted canonical catalog compatibility. Catalog/export capability preservation, exact field encodings, canonical evolution and implementation sequencing MUST receive the affected architecture and plan dispositions before dependent implementation. No new export target, automatic lineage discovery, live integration, forecast, cost model or release commitment is included.
