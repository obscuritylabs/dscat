# Research scope and impact

## Authority and decision package

[DEC-042](decisions.md#dec-042) records historical authority to prepare and integrate this planning revision. The exact consolidated requirements and impact package, including this document, was approved under [DEC-044](decisions.md#dec-044) on 2026-11-17 at source revision `69b686a3d0b1da49290ca37d577d46fb8b63dbfb`; its embedded renewed-approval PENDING wording is historical. [Planning gates](planning-gates.md) owns current approval status. The exact DEC-039/040/041 baseline approvals remain unchanged. DEC-044 permits architecture preparation against the approved requirements and impact package, not detailed architecture approval, implementation-plan readiness, product implementation, or release. Source evidence is in [research](research.md#research-additions-source-evidence); research guidance MUST NOT be represented as proof that a law applies to a particular installation.

DEC-042 metadata additions below are approved 0.1.0 requirements scope under DEC-044 as optional detail; their detailed designs remain subject to later architecture and planning gates. FR-012 lineage follows the later capability sequence in [SPEC-005](requirements.md), with no enlargement of ID/title/description/contact-or-owner intake. Valid intake MUST remain distinct from inventory completeness, target readiness, and public publication authority. Missing facts MUST remain absent/unknown, never fabricated to make an export pass.

## Requirement changes and acceptance impacts

| Change | Requirement and capability | Acceptance / design impact |
| --- | --- | --- |
| Addition: independent validation/completeness/readiness | FR-013; CAP-02 | Independent state scenarios and per-target missing-fact diagnostics; minimal intake plus shared configuration demonstration remains mandatory. |
| Addition: restriction and disclosure/publication decisions | FR-014; CAP-03 | Separate use/access and metadata decisions, four determination states, authority/rationale/date/review, fail-closed public projection and recursive leakage fixtures. |
| Addition: records metadata | FR-015; CAP-01 | Separate capacity retention and records disposition/trigger/hold round trips; no disposal decision or execution. |
| Addition: stewardship and dates | FR-016; CAP-01 | Distinct accountable owner/contact/maintainer/steward/domain references and metadata/dataset dates; no inferred accountability. |
| Addition: consumer context and local checks | FR-017; CAP-02 | Uses/limitations/definitions/access instructions, explicit commitments, offline semantic references, declared-rule results; no live enforcement or guarantees. |
| Addition: identity/version/mapping boundaries | FR-018; CAP-03 | Distinct dataset/contract/product reference identities, independent version domains, field meaning/cardinality/requiredness/loss mappings and compatibility fixtures. |
| Refinement: manual lineage semantics | FR-012; CAP-01 | PROV-O entities/activities/agents; later capture/export under DEC-043, DCAT dataset/distribution/service distinctions; preservation/mapping tests without complete PROV conformance. |
| Addition: privacy minimization and diagnostics | NFR-020; CAP-04 | Role contacts, no samples/secrets, synthetic nested leakage and safe diagnostics cases; no perfect secret-detection claim. |
| Refinement: machine-readable SBOM | NFR-011; CAP-04 | Selected standard/version, transitive dependency reconciliation, source/artifact bindings, generator provenance and explicit unknowns. |
| Refinement: known exploitation | NFR-012; CAP-04 | Independent release block regardless of severity with artifact applicability evidence; High/Critical gate preserved, no runtime feeds. |
| Addition: security reporting policy | NFR-022; CAP-04 | GitHub Private Vulnerability Reporting route, pre-release enablement/link verification and brief assessment/remediation/coordinated disclosure policy; current authority follows [planning gates](planning-gates.md#confidential-reporting-readiness). |

The previous 30 requirements remain with stable IDs; nine research additions brought that revision to 39. DEC-043 adds three later-capability requirements, bringing this consolidated candidate to 42. No ID is reused; FR-009 remains absent under DEC-034. Earlier acceptance is preserved except for the explicit DEC-043 sequencing and scope changes and proposed research refinements. RTM design, implementation, tests, and verification remain PENDING where not performed.

## Compatibility and security impacts

Architecture MUST define optional field encodings, independent states/version identifiers, canonical preservation, migration boundary, target loss reporting, and old intake compatibility. New optional detail MUST NOT silently invalidate previously supported four-field submissions. Public projections MAY withhold output despite otherwise valid intake; target readiness MUST explain required missing facts. This is a new security behavior requiring explicit acceptance, not a claim that prior local export published data.

The threat model MUST include nested leakage through lineage, contacts, locations, URLs, free text, extensions, and diagnostics as well as existing parser/writer threats. Public allowlists MUST handle unknown/new fields by omission or rejection rather than automatic inclusion. Legal restrictions, records decisions, and publication authorization MUST come from supplied accountable authority; DSCat MUST NOT infer them. Current product implementation and security verification remain unperformed.

## Data-mesh interpretation and explicit boundaries

The original mesh articles and Radar describe domain ownership, data as a product, self-service infrastructure, and federated computational governance. DSCat's proposal supports descriptive ownership, consumer understanding, interoperability, and local machine-readable metadata checks. It MUST NOT claim to provide a complete mesh platform, organizational adoption, distributed enforcement, or operational service guarantees.

The approved interview sequence and later ODPS scope are authoritative in [SPEC-005 and later acceptance](requirements.md#later-capability-acceptance) under DEC-043. ODPS 1.1.0 research is a candidate resource, not an approved runtime target pin. A contract document MUST NOT be equated to a legal agreement, a dataset, or a whole data product. Declared quality/service commitments MUST remain supplied assertions rather than monitored results.

The later W3C DCAT 3, lineage and ODPS capabilities and DCAT-US 1.1 MUST remain outside the first release. External lineage ingestion, automatic discovery, access provisioning, deployment, live endpoint testing, automated legal determinations/deletion, live quality monitoring, federation services, databases and forecasts remain deferred or excluded. Detailed designs MUST pass the affected architecture and implementation-plan readiness gates before implementation.

## Remaining design and verification gates

The requirements and impact package above was approved only at the exact source revision and hashes recorded under DEC-044 and [planning gates](planning-gates.md). The current status clarifications and NFR-017 authority correction form a later requirements source revision; DEC-044 does not approve its changed bytes. Current applicability of first-release architecture readiness DEC-046 and implementation-plan readiness DEC-047 MUST follow the [bounded reconciliation](planning-gates.md#bounded-readiness-reconciliation) before dependent implementation. Detailed schema choices, target mappings, security limits, projection controls, and release evidence tools remain architecture and implementation-plan readiness deliverables, not unresolved invented product facts. The proposed CycloneDX 1.6 JSON implementation choice in the delivery draft remains subject to those gates. Full transitive schema/context closure and licensing MUST be verified before implementation; research hashes alone MUST NOT count as runtime pins. Later detailed designs and release verification remain pending under their applicable gates.
