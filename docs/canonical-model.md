# Canonical catalog model and storage

## Approved direction

The following direction is a human-derived fact from DEC-020 and DEC-021. Detailed fields, filenames, schema versions, and migration behavior MUST conform to the DEC-039 approved requirements and still pass the architecture and implementation-plan gates.

- Workbook intake MUST validate into a Pydantic canonical catalog model, which MUST serialize to organized JSON flat files as the catalog source of truth.
- DCAT-US and ODCS MUST be derived from that model. Canonical persistence MUST preserve all supported capacity and optional metadata; a target projection MAY omit metadata its standard cannot represent, with omissions documented in the approved mapping. Projection limitations MUST NOT cause loss from canonical storage or unsupported conformance claims.
- Any RDF export MUST use JSON-LD. Canonical JSON MUST remain distinct from standards-specific RDF projections.
- The canonical model MUST be treated as the likely migration boundary as stored data evolves. Architecture MUST preserve the option of moving this layer into a database in the future; a database MUST NOT be required now.

## Proposed organization

The following details are LLM design proposals, not approved architecture. They MUST be reviewed before implementation.

- Each catalog SHOULD have a root manifest and a datasets directory containing one JSON record per stable dataset ID. Generated DCAT-US and ODCS projections SHOULD live in a separate exports directory. Exact names and ID-to-filename encoding MUST be settled in architecture; record identifiers MUST NOT become unchecked filesystem paths.
- The manifest SHOULD identify the canonical schema version and dataset files. References SHOULD be relative and portable. The loader MUST validate all records and catalog-wide constraints before exporting; missing records, duplicate IDs, inconsistent versions, and unsafe paths MUST produce diagnostics.
- Shared metadata SHOULD have one authoritative location. Projection files MUST NOT be treated as independently editable catalog state. Real catalog data SHOULD live in a user-selected data directory outside this source repository; repository examples and fixtures MUST remain synthetic.
- Catalog schema versions SHOULD be independent of application versions, workbook versions, and the DCAT-US/ODCS specification versions. These version domains MUST NOT be assumed to change together.
- Core validation, export mapping, and business identifiers SHOULD operate on the canonical model. Storage SHOULD expose a small load/save boundary; a future database adapter SHOULD implement that boundary rather than change exporter semantics. Agents MUST NOT build an unused database framework or speculative migrations.

## Proposed migration and verification policy

These safeguards are LLM proposals and MUST receive architecture approval before implementation.

- Readers SHOULD identify the stored schema version and reject unsupported versions with actionable diagnostics. Unknown future versions MUST NOT be silently rewritten as current data.
- Any future migration SHOULD declare source and target versions, preserve stable IDs and supported metadata, validate the entire result, and write to a separate destination by default. Failed migrations MUST NOT corrupt the source catalog.
- Migration tests SHOULD use representative saved canonical fixtures, verify semantic preservation and deterministic results, and regenerate standard exports. Re-running a migration on the target version SHOULD have explicitly defined no-op or refusal behavior; it MUST NOT transform the data twice.
- Initial verification MUST cover workbook-to-model conversion, canonical JSON save/load, preservation of capacity and optional fields, cross-record validation, version handling, deterministic export from saved JSON, and independence from the original intake files.
- Migration support MUST be planned when an actual stored-schema change requires it. Initial schema-version metadata and compatibility tests SHOULD establish the foundation without implementing hypothetical transforms.

## Proposed RDF verification

These implementation details are LLM proposals and MUST pass architecture review before implementation.

- JSON-LD serializers SHOULD use pinned, locally available contexts or embedded context definitions. Processing MUST NOT require remote context fetches, including indirectly referenced contexts; unavailable contexts MUST produce diagnostics rather than trigger network requests.
- Verification MUST assess JSON syntax, JSON-LD processing, intended IRIs/types/relationships, and target-profile conformance. Schema validation alone MUST NOT establish RDF semantic correctness. The serializer design MUST reconcile JSON-LD context handling with the selected DCAT-US schema/profile rather than assume arbitrary context fields are accepted.

## Lineage scope and design impact

DEC-029 establishes OPTIONAL manually supplied lineage in 0.1.0, governed by FR-012. The canonical model MUST preserve dataset relationships, processing steps, software versions, responsibility/handoffs, and supplied evidence. Automatic discovery MUST remain outside scope.

The architecture draft MUST specify stable processing-step identities, relationship/reference validation, treatment of upstream datasets outside the selected catalog, and standards mappings without claiming unsupported conformance. These details MUST remain unapproved until architecture review. Tests MUST cover multi-input derivation, multi-step handoffs, canonical round trips, malformed references, and applicable exports. Workbook design MUST assess these examples for practical entry and MUST raise concrete complexity limitations under DEC-030. Requirements are approved under DEC-039; architecture and implementation-plan approval gates MUST remain pending.

## Draft lineage reference policy

The following agent proposals support FR-012 and MUST receive architecture approval before implementation.

- Processing-step IDs MUST be nonempty and unique within the catalog. Dataset and step references MUST use the architecture-approved identifier grammar; filesystem paths MUST NOT be inferred from identifiers. Normalization MUST be identical across intake, canonical loading, duplicate comparison, and exports.
- Each supplied processing step MUST identify at least one input and one output. Multiple inputs/outputs and multiple handoff steps MUST be supported. A dataset reference outside the selected snapshot MUST be explicitly marked external; an unmarked unresolved local reference MUST fail. External references MUST be preserved without runtime network resolution and MUST NOT create synthetic local dataset records.
- Duplicate/conflicting step IDs, malformed references, self-dependency, and cycles among internal derivation steps MUST fail with relevant source locations. Cyclic or iterative processing without distinct versioned dataset identities MUST remain unsupported under this proposed initial policy. Tests MUST exercise these failures and valid external references; this limitation MUST be approved rather than inferred from lineage scope.
- Optional lineage remains optional, but supplied invalid lineage MUST block export under FR-002. Supported target mappings and omitted unmappable fields MUST be listed per standard; canonical round trips MUST preserve every supported lineage field even when a target lacks an equivalent.

## Draft security boundaries

The following agent proposals support NFR-005/010 and FR-002/010/011. They MUST receive threat-model and architecture approval, including measured resource limits, before parser or writer implementation.

- Parsing MUST treat XLSX as untrusted ZIP/XML. Archive member count, compressed/uncompressed totals, expansion ratio, individual XML size/depth, worksheet count, cell count/string length, and processing time MUST have finite approved limits with documented diagnostics. Exact numeric limits MUST be selected using synthetic boundary/resource tests before architecture approval. Encrypted or unsupported archives, path traversal, duplicate archive paths, entity expansion, and unsafe external resources MUST be rejected without executing content or writing extracted paths.
- Formula cells in intake data fields MUST be rejected, never evaluated or accepted through cached values. Generated feedback formulas MAY exist only in designated non-input cells and MUST NOT supply imported metadata. Macros, external links/connections, embedded executable content, and network resolution MUST be rejected or disabled according to the approved parser matrix. Formula-like user strings in generated text cells MUST be written as inert strings and verified as such.
- Source discovery MUST define symlink handling and reject unsafe input/output overlap. Canonical manifests MUST reject absolute/traversal paths and unsupported versions. Publication MUST stage validated outputs separately and preserve prior snapshots on validation, serialization, permission, disk-space, interrupted-write, and replacement failures. The platform-specific atomicity and recovery contract MUST be demonstrated before implementation-plan approval; an incomplete multi-file write MUST NOT become a valid published snapshot.
- Runtime schema/JSON-LD processing MUST use only the approved local resource registry, including transitive references. Unknown references MUST fail offline. Diagnostics MUST identify failure locations without echoing secrets, arbitrary workbook contents, or private paths into repository evidence. Logs and structured diagnostics MUST follow the approved Pydantic boundary and privacy policy.
