# Current planning gates

## Authority and status

This is the consolidated navigation for approval status, derived from the decision record. The requirements baseline, full architecture, implementation plan, and product release authorization remain PENDING. Accepted directions MUST NOT be described as approval of those gates. The reconciliation instruction in DEC-038 authorizes documentation corrections, not dependent product implementation.

| Subject | Recorded authority | Status and boundary |
| --- | --- | --- |
| Required intake core and capacity direction | DEC-023/024 | Accepted direction; encodings and field-level rules pending architecture. |
| Discovery, snapshots, replacement, determinism, duplicates | DEC-025 | Accepted behavior; normalization and publication design pending architecture. |
| ODCS 3.2.0 and shared export configuration | DEC-027 | Accepted target and capability; exact schema closure and mappings pending architecture. |
| Canonical JSON and separate persistence boundary | DEC-020/021 | Accepted direction; detailed schema and storage design pending architecture. |
| Portability and installation | DEC-028 | Accepted policy; actual platform and Excel verification pending. |
| Optional lineage and conditional Excel selection | DEC-029/031/032 | Accepted scope; detailed reference policy and mappings pending architecture. |
| Proprietary licensing requirement wording | DEC-035; NFR-014 | Individually approved wording; CLI notice and distribution verification pending implementation. |
| Documentation QA/QC and reconciliation | DEC-037/038 | Directly requested governance work; product and release gates remain unchanged. |
| Historical remediation | [Bounded approval record](privacy-remediation.md#approval-and-stage-record) | Separate maintenance approval and consumed exception; not a product approval. |

An approval MUST identify an exact document revision or commit, its scope, the human decision date/reference, and affected requirements. Subsequent evidence or editorial corrections MUST NOT inherit approval of new technical choices. Each approval request MUST identify changes since the last approved revision and their requirement, compatibility, security, and acceptance impacts.

## Required gate deliverables

The following table specifies gate completeness, not additional product features. Drafts MAY be prepared before approval; dependent implementation MUST wait for requirements, architecture, and implementation-plan approval in that order.

| Gate | Required content before approval | Governing requirements |
| --- | --- | --- |
| Requirements | Consolidated scope and acceptance, minimum intake plus shared configuration, deterministic-result and overwrite semantics, accepted decisions distinguished from proposals, no unresolved correctness assumptions | FR-001–FR-008, FR-010–FR-012; NFR-001–NFR-019 |
| Architecture | Typed models and boundaries; ID normalization; field encodings; capacity and lineage policies; safe parser limits; failure diagnostics; canonical schema/storage/publication; exact offline schema/context closure and target mappings; compatibility contract and threat model | FR-002/004/006/007/008/010/011/012; NFR-002/005/009/010/013/018/019 |
| Implementation plan | Small ordered increments; artifact/symbol RTM mappings; dependency/tool versions and sources; age policy; local verification commands; boundary/business-rule test inventory; compatibility fixtures; coverage and security evidence procedures; manual verification arrangements | NFR-001–NFR-007, NFR-011–NFR-017 |
| Candidate release authorization or exercise of explicit planning delegation | Verified main revision and exact artifact hashes; wheel/sdist, checksums, SBOM; vulnerability disposition; proprietary notices; completed manual walkthrough; tested installation/offline behavior; release failure policy; authorized scope/version | NFR-005/006/007/010/011/012/014/017 |
| Post-release verification | Actual released asset download, integrity/version, clean installation and applicable acceptance, offline runtime and released-source document checks | NFR-006/017 |

The initial compatibility contract MUST enumerate CLI commands/options, exit codes, human-readable guarantees and structured outputs, configuration keys and precedence, workbook versions/layouts, canonical schema versions, and the public Python API or its explicit absence. It MUST identify supported and unsupported behavior and required regression fixtures. Portability targets MUST remain distinct from environments actually verified.

Concrete architecture proposals are in [intake policies](intake-proposals.md#draft-capacity-policy), [lineage policy](canonical-model.md#draft-lineage-reference-policy), and [security policy](canonical-model.md#draft-security-boundaries). Release proposals are in the [delivery draft](delivery-plan.md#draft-release-evidence-and-failure-policy). These proposals MUST NOT be represented as approved or implemented.
