# Proposed research scope and impact

## Authority and decision package

[DEC-042](decisions.md#dec-042) authorizes preparing and integrating this proposed planning revision. [Planning gates](planning-gates.md) owns approval status. The exact DEC-039/040/041 baseline approvals remain unchanged; renewed requirements approval is PENDING. Approval MUST identify the final reviewed revision, date, and scope. Architecture and implementation-plan approval MUST follow in order before dependent product work. Source evidence is in [research](research.md#research-additions-source-evidence); research guidance MUST NOT be represented as proof that a law applies to a particular installation.

DEC-042 metadata additions below remain proposed 0.1.0 scope as optional detail; FR-012 lineage follows the later capability sequence in [SPEC-005](requirements.md), with no enlargement of ID/title/description/contact-or-owner intake. Valid intake MUST remain distinct from inventory completeness, target readiness, and public publication authority. Missing facts MUST remain absent/unknown, never fabricated to make an export pass.

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
| Addition: accessibility | NFR-021; CAP-01 | Textual feedback, keyboard/no-color tests and manual selected-application/assistive-technology evidence; removes prior absence of dedicated accessibility targets. |
| Refinement: machine-readable SBOM | NFR-011; CAP-04 | Selected standard/version, transitive dependency reconciliation, source/artifact bindings, generator provenance and explicit unknowns. |
| Refinement: known exploitation | NFR-012; CAP-04 | Independent release block regardless of severity with artifact applicability evidence; High/Critical gate preserved, no runtime feeds. |
| Addition: secure-development/support policy | NFR-022; CAP-04 | Final SSDF 1.1 practice mapping and reporting, remediation/disclosure, support/version policy; synthetic report exercise. |

The previous 30 requirements remain with stable IDs; nine research additions brought that revision to 39. DEC-043 adds three later-capability requirements, bringing this consolidated candidate to 42. No ID is reused; FR-009 remains absent under DEC-034. Earlier acceptance is preserved except for the explicit DEC-043 sequencing and scope changes and proposed research refinements. RTM design, implementation, tests, and verification remain PENDING where not performed.

## Compatibility and security impacts

Architecture MUST define optional field encodings, independent states/version identifiers, canonical preservation, migration boundary, target loss reporting, and old intake compatibility. New optional detail MUST NOT silently invalidate previously supported four-field submissions. Public projections MAY withhold output despite otherwise valid intake; target readiness MUST explain required missing facts. This is a new security behavior requiring explicit acceptance, not a claim that prior local export published data.

The threat model MUST include nested leakage through lineage, contacts, locations, URLs, free text, extensions, and diagnostics as well as existing parser/writer threats. Public allowlists MUST handle unknown/new fields by omission or rejection rather than automatic inclusion. Legal restrictions, records decisions, and publication authorization MUST come from supplied accountable authority; DSCat MUST NOT infer them. Current product implementation and security verification remain unperformed.

## Data-mesh interpretation and explicit boundaries

The original mesh articles and Radar describe domain ownership, data as a product, self-service infrastructure, and federated computational governance. DSCat's proposal supports descriptive ownership, consumer understanding, interoperability, and local machine-readable metadata checks. It MUST NOT claim to provide a complete mesh platform, organizational adoption, distributed enforcement, or operational service guarantees.

The approved interview sequence and later ODPS scope are authoritative in [SPEC-005 and later acceptance](requirements.md#later-capability-acceptance) under DEC-043. ODPS 1.1.0 research is a candidate resource, not an approved runtime target pin. A contract document MUST NOT be equated to a legal agreement, a dataset, or a whole data product. Declared quality/service commitments MUST remain supplied assertions rather than monitored results.

The later W3C DCAT 3, lineage and ODPS capabilities and DCAT-US 1.1 MUST remain outside the first release. External lineage ingestion, automatic discovery, access provisioning, deployment, live endpoint testing, automated legal determinations/deletion, live quality monitoring, federation services, databases and forecasts remain deferred or excluded. Detailed designs MUST pass affected human planning gates before implementation.

## Remaining gate decisions

The human MUST approve or revise the exact consolidated requirements revision, including the additions/refinements and boundaries above. Detailed schema choices, target mappings, security limits, accessibility criteria/environments, projection controls, and release evidence tools remain architecture/planning deliverables, not unresolved invented product facts. The proposed CycloneDX 1.6 JSON implementation choice in the delivery draft remains subject to those gates. Full transitive schema/context closure and licensing MUST be verified before implementation; research hashes alone MUST NOT count as runtime pins.
