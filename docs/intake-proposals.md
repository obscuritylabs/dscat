# Intake design proposals

## Authority and accepted-direction pointers

[Planning gates](planning-gates.md) governs approval status. The exact approved requirements baseline governs accepted scope; the consolidated requirements and research impact scope are approved under DEC-044; [the architecture package](architecture.md) owns detailed design. Proposals MUST receive architecture disposition and agent implementation-plan readiness under the [approval policy](governance.md#required-sdlc-and-approval-gates) before implementation. Workbook-specific obligations apply only while Excel remains selected under SPEC-007. Original notes are available with `git show 0b7b824:docs/intake-proposals.md`.

| Stable source | Current home |
| --- | --- |
| <a id="intake-001"></a>INTAKE-001 | [Planning gates](planning-gates.md): authority; workbook obligations are conditional under SPEC-007. |
| <a id="intake-002"></a>INTAKE-002 | [DEC-023](decisions.md#dec-023): initial Excel layout; [ID normalization](architecture.md#identity-and-normalization); disposition follows DEC-046. |
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

The exact core-plus-configuration mappings, pinned closure and research-only positive/negative evidence MUST follow [standards architecture](architecture-standards.md). Label-only contact MUST remain valid intake; target-specific facts MUST NOT be invented. Executed research validation MUST NOT substitute for product exporter acceptance tests.

## Research revision intake dependencies

The four-field required core MUST remain unchanged under DEC-044. [Canonical schema](architecture.md#canonical-record-schema) and [assessment/projection assurance](architecture-assurance.md) MUST distinguish valid intake, inventory completeness, target readiness and publication authority. Missing publication authority MUST fail closed for public projection without invalidating minimum intake. Prior detailed proposals MUST be retrieved through Git history rather than treated as competing current architecture.

## Optional guided example template

### INTAKE-024

This is a proposed extension of [FR-001](requirements.md#fr-001), with current authority and outstanding readiness in [planning gates](planning-gates.md#example-template-planning). The goal is to reduce the effort of starting a workbook through a small worked example and plain-language explanations of its value. This section owns the proposed behavior and acceptance checks; it does not describe an available CLI option.

Proposed command: `dscat template --output example-intake.xlsx --examples`. The flag name remains an agent proposal. The human-selected scope is a small guided example with two synthetic datasets: one containing only the four required core values, and another with a small, coherent set of optional field-schema and detail/quality entries. A comprehensive showcase of every supported field is excluded from this proposal. Detailed example contents remain subject to later design disposition; the selected breadth is recorded in the planning gate.

Under this proposal:

- The generator MUST seed actual editable input cells on Datasets, Fields and Details_Quality, using internally consistent dataset IDs and grouped detail references. The minimal dataset MUST demonstrate that optional sections can remain blank.
- Instructions MUST identify the workbook as a synthetic example, suggest starting with the minimal dataset, explain the links between sheets, and give concrete guidance for replacing or removing all example rows before submitting real metadata. Seed records MUST have visibly synthetic names and IDs. Instructions MUST explain that examples are ordinary records during validation and import; the parser MUST NOT silently discard them.
- Instructions MUST explain why the illustrated values help: core metadata supports discovery and contact, field descriptions support interpretation, and selected quality or ownership details support evaluating suitability and responsibility. Guidance MUST distinguish valid intake from standards-export readiness and publication authority; it MUST NOT promise that example metadata alone authorizes publication or satisfies every export target.
- Examples MUST use only bundled, fixed synthetic values, with no source-workbook import, private metadata, network retrieval, macros, external connections or formulas in input cells. They MUST preserve the supported schema, worksheet layout, validation controls, feedback and input formatting. Existing output replacement and failure-preservation rules MUST apply in both modes.
- Generation without the flag MUST leave dataset and optional-detail input cells blank. Example mode MUST NOT supply defaults to later real submissions, infer publication authority or expand the four-field required core. Repeating generation with the same mode and inputs MUST preserve the existing deterministic generation contract.

Planned acceptance checks:

1. Generate without the flag and verify blank data-entry rows; generate with the flag and verify the expected minimal and detailed records, cross-sheet references, synthetic labels and explanatory instructions.
2. Validate the seeded workbook through the ordinary CLI and parser, confirming two valid datasets and the expected optional details, without relaxed checks. Missing export-specific facts MUST remain separately reported by ordinary target-readiness assessment.
3. Replace example values and remove example records, including their dependent rows, then validate the resulting minimal real-entry shape using synthetic test values. Confirm the instructions cover that editing path and no example entries remain in the parsed result.
4. Confirm existing-file refusal without `--replace`, explicit replacement behavior, failure preservation, package safety, schema compatibility and deterministic output in both modes. Confirm malformed edits still produce ordinary validation diagnostics.
5. Open the generated example in the selected completion application and follow Instructions to locate the minimal example, understand one cross-sheet optional entry, explain its practical benefit and replace/remove the examples. Record the observation and limitations; planning alone MUST NOT claim reduced user burden was demonstrated.

Detailed fixture selection, command/API wiring, compatibility assessment and implementation sequencing remain PENDING architecture and fresh implementation-plan readiness. No new export target, lineage capture, new completion interface or release commitment is included.
