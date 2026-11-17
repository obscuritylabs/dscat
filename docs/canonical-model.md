# Canonical catalog model and storage

## Approved direction

DEC-020/021 and the requirements approved under DEC-044 establish canonical JSON as the persisted source of truth, flat-file storage separated from the logical model, standards-derived exports and JSON-LD for RDF. [Planning gates](planning-gates.md) owns approval status. These directions MUST NOT be interpreted as architecture approval.

## Proposed organization

The detailed proposed field/schema and persistence design MUST have one authoritative home: [canonical schema](architecture.md#canonical-record-schema), [typed boundaries](architecture.md#typed-boundaries) and [storage/publication](architecture.md#storage-and-deterministic-publication). This page MUST serve as navigation; historical proposals remain available through Git history.

## Proposed migration and verification policy

Independent schema versions, supported-version behavior and future migration safeguards MUST follow the [canonical schema](architecture.md#canonical-record-schema) and [compatibility contract](architecture.md#initial-compatibility-contract). No speculative migration implementation is authorized.

## Proposed RDF verification

Target-specific contexts, graph semantics, schema/resource closure and mapping losses MUST follow [standards architecture](architecture-standards.md). Runtime conformance MUST remain unverified until implementation and fresh verification; research-only demonstrations MUST remain separately attributed.

## Lineage scope and design impact

Manual lineage MUST follow the approved later sequence in [SPEC-005](requirements.md). Its extension boundary and milestone design exit MUST follow [later capability gates](architecture.md#later-capability-extension-gates), with supported PROV-O mapping evidence in [standards architecture](architecture-standards.md). First-release code MUST NOT implement later lineage.

## Draft lineage reference policy

The detailed proposed local/external reference, identity and cycle policy MUST follow the [lineage milestone boundary](architecture.md#later-capability-extension-gates). Milestone-specific serialization/mapping disposition under the [approval policy](governance.md#required-sdlc-and-approval-gates) MUST precede dependent implementation.

## Draft security boundaries

Threats, parser limits, diagnostics, privacy and safe projection MUST follow [assurance architecture](architecture-assurance.md); transactional persistence MUST follow [storage/publication](architecture.md#storage-and-deterministic-publication). Measured research probes MUST NOT count as implemented-parser security evidence.

## Research revision dependencies

Optional review/roles/retention/semantic references and identity/version boundaries MUST follow [canonical schema](architecture.md#canonical-record-schema); mapping loss MUST follow [standards architecture](architecture-standards.md). Requirements approval MUST remain distinct from pending architecture disposition/agent plan readiness, as recorded in [planning gates](planning-gates.md).
