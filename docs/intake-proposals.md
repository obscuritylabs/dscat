# Intake design proposals

## Authority and accepted-direction pointers

[Planning gates](planning-gates.md) governs approval status. The exact approved requirements baseline governs accepted scope; the consolidated requirements and research impact scope are approved under DEC-044; [the architecture package](architecture.md) owns detailed unresolved design proposals. Proposals MUST receive applicable architecture/implementation-plan approval before implementation. Workbook-specific obligations apply only while Excel remains selected under SPEC-007. Original notes are available with `git show 0b7b824:docs/intake-proposals.md`.

| Stable source | Current home |
| --- | --- |
| <a id="intake-001"></a>INTAKE-001 | [Planning gates](planning-gates.md): authority; workbook obligations are conditional under SPEC-007. |
| <a id="intake-002"></a>INTAKE-002 | [DEC-023](decisions.md#dec-023): initial Excel layout; [ID normalization](architecture.md#identity-and-normalization); proposed. |
| <a id="intake-003"></a>INTAKE-003 | [FR-006](requirements.md#fr-006): required core and shared configuration; defaults MUST NOT fabricate facts. |
| <a id="intake-005"></a>INTAKE-005 | [FR-007](requirements.md#fr-007): accepted capacity capabilities. |
| <a id="intake-006"></a>INTAKE-006 | [FR-007](requirements.md#fr-007): capacity scope and no forecasts. |
| <a id="intake-007"></a>INTAKE-007 | [FR-008](requirements.md#fr-008); [canonical model proposals](canonical-model.md). |
| <a id="intake-008"></a>INTAKE-008 | [FR-005](requirements.md#fr-005): discovery; separate input/output directories remain proposed below. |
| <a id="intake-009"></a>INTAKE-009 | [FR-002](requirements.md#fr-002): duplicate/conflict behavior. |
| <a id="intake-010"></a>INTAKE-010 | [FR-011](requirements.md#fr-011): snapshots and replacement; [publication design](architecture.md#storage-and-deterministic-publication); proposed. |
| <a id="intake-011"></a>INTAKE-011 | [NFR-009](requirements.md#nfr-009): byte determinism; [deterministic serialization](architecture.md#storage-and-deterministic-publication); proposed. |
| INTAKE-012 | [Current validation policy](#intake-012): safe aggregate validation; detailed limits/diagnostics pending architecture. |
| <a id="intake-014"></a>INTAKE-014 | [NFR-001](requirements.md#nfr-001); [DEC-028](decisions.md#dec-028): deferred Excel verification. |
| <a id="intake-015"></a>INTAKE-015 | [FR-004](requirements.md#fr-004): ODCS scope; mappings/resources pending architecture. |
| <a id="intake-016"></a>INTAKE-016 | [Canonical model proposals](canonical-model.md): detailed shape and migration policy. |
| <a id="intake-017"></a>INTAKE-017 | [FR-002](requirements.md#fr-002), [FR-006](requirements.md#fr-006); [DEC-025](decisions.md#dec-025): [ID normalization](architecture.md#identity-and-normalization); proposed. |
| <a id="intake-018"></a>INTAKE-018 | [FR-007](requirements.md#fr-007); [draft capacity policy](#draft-capacity-policy): unapproved detailed rules. |
| <a id="intake-019"></a>INTAKE-019 | [FR-010](requirements.md#fr-010): workbook controls and safe formula handling. |
| <a id="intake-020"></a>INTAKE-020 | [FR-012](requirements.md#fr-012): optional lineage; references/mappings pending architecture. |
| <a id="intake-021"></a>INTAKE-021 | [DEC-030](decisions.md#dec-030): concrete usability escalation; feasibility proposal below. |
| <a id="intake-022"></a>INTAKE-022 | [SPEC-001](requirements.md): initial Excel SHOULD choice; alternatives unselected. |
| <a id="intake-023"></a>INTAKE-023 | [SPEC-007](requirements.md): conditional workbook obligations and replacement change control. |

## Current validation policy

### INTAKE-012

Per [FR-002](requirements.md#fr-002)/[NFR-005](requirements.md#nfr-005), validation MUST examine every independently readable input within approved safe processing limits and accumulate discoverable file, sheet, row, field, and cross-record errors. Unsafe, resource-limited, or unreadable content MUST produce an explicit diagnostic; dependent checks MUST be reported as unperformed rather than passed or populated with invented cascading failures. Validation MUST continue on independent inputs and MUST block all catalog exports by default on invalid intake. Missing target-specific export facts in otherwise valid intake MUST block only the affected target under FR-004/013. A separate structured diagnostic report MAY be written without publishing catalog outputs. Detailed limits and diagnostic design MUST pass architecture approval.

## Unresolved intake proposals

### INTAKE-004

The proposed field controls, examples and feedback MUST follow the [versioned intake layout](architecture.md#intake-layout-and-field-encodings). Empty commitments MUST remain absent under FR-004/017.

### INTAKE-013

The proposed supported-version and fixture policy MUST follow the [compatibility contract](architecture.md#initial-compatibility-contract). Workbook verification MUST retain actual application/version and accessibility evidence under [assurance](architecture-assurance.md).

## Draft capacity policy

The detailed proposed Unknown/absent/zero states, units, decimal precision, bounds, dates, observation windows and retention encodings MUST have one authoritative home in [capacity encoding](architecture.md#capacity-encoding). These remain architecture proposals, not product implementation.

## Draft minimum-export demonstration

The exact core-plus-configuration mappings, pinned closure and research-only positive/negative evidence MUST follow [standards architecture](architecture-standards.md). Label-only contact MUST remain valid intake; target-specific facts MUST NOT be invented. Executed research validation MUST NOT substitute for product exporter acceptance tests.

## Research revision intake dependencies

The four-field required core MUST remain unchanged under DEC-044. [Canonical schema](architecture.md#canonical-record-schema) and [assessment/projection assurance](architecture-assurance.md) MUST distinguish valid intake, inventory completeness, target readiness and publication authority. Missing publication authority MUST fail closed for public projection without invalidating minimum intake. Prior detailed proposals MUST be retrieved through Git history rather than treated as competing current architecture.
