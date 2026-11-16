# Canonical catalog model and storage

## Approved direction

The following direction is a human-derived fact from DEC-020 and DEC-021. Detailed fields, filenames, schema versions, and migration behavior MUST still pass the requirements, architecture, and implementation-plan gates.

- Workbook intake MUST validate into a Pydantic canonical catalog model, which MUST serialize to organized JSON flat files as the catalog source of truth.
- DCAT-US and ODCS MUST be derived from that model; their target schemas MUST NOT force loss of capacity measurements or other supported optional catalog metadata.
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
