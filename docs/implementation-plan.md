# Implementation plan

## Authority and exact inputs

Agent planning disposition, 2026-11-17, DEC-047: this is the first-release execution plan against clean architecture source `ecfc15dfee316ece10a2d74c1a3f26fabed9d4db`, tree `8f9f1a109d3992b7873855f9a3fa7aff615a0b7e`, DEC-046. Requirements/impact approval is DEC-044 at `69b686a3d0b1da49290ca37d577d46fb8b63dbfb`; their bytes MUST remain unchanged. [Planning gates](planning-gates.md) owns current status; [the task](tasks/implementation-plan.md) owns candidate identity and outstanding review. This plan's readiness is an agent judgment, contingent on exact-candidate fresh QA/reconciliation PASS before execution, never human approval. The assessed architecture, standards and assurance bytes MUST remain unchanged by this plan; their source-stage PENDING plan labels describe architecture preparation, while current plan status follows planning gates.

The current authorized work MUST stop after architecture and implementation planning and protected integration of their documents. No product implementation, product tests, tags or release execution MUST occur in this work boundary. The increments below are executable future handoffs, not claims that files, commands or checks already exist. They MUST begin only in a subsequent implementation assignment after plan QA PASS. Architecture's [reopen conditions](architecture-disposition.md#planning-handoff-and-reopen-conditions) apply; dependencies inside the designed boundaries are routine execution choices. No further routine plan or release approval MUST be requested.

Version 0.1.0 MUST include DCAT-US 3.0 first and ODCS 3.2.0 second, together with all first-release requirements. No intermediate increment MUST be advertised as the complete first release. W3C DCAT 3, manual PROV-O lineage, descriptive ODPS lifecycle/ports and DCAT-US 1.1 MUST follow in that order, each with its own detailed architecture and plan gate. Forecasts, database implementation, executable local rules, automatic/external lineage, provisioning, live endpoint testing and public PyPI publication MUST remain excluded.

## Ownership and increment protocol

Each row below MUST use a fresh implementation agent and distinct fresh acceptance verifier. The coordinator MUST provide the exact integrated predecessor commit, clean/dirty digest, relevant acceptance/design anchors, allowed symbols and applicable tests; a stale or missing handoff MUST stop dependent work. One owner MUST write shared `pyproject.toml`, `uv.lock`, RTM and command wiring at a time. Every increment MUST commit a bounded Conventional Commit, update symbol/test mappings and retain all seven completion stages. Independent review MUST occur for the security/storage/export boundaries and before first-release integration; documentation changes MUST receive full distributed QA/reconciliation. Integration agents MUST follow repository policy, use protected PRs and verify origin/main. Working/source/private fixtures MUST contain synthetic metadata only.

Execution roles are implementation owner (I), fresh verifier (V), fresh security reviewer (S), platform acceptance operator (P), selected desktop/assistive operator (A), release owner (R) and maintainer/triage role (M). The coordinator MUST assign these to actual fresh invocations or accessible execution operators in each handoff; a role name MUST NOT imply acquired host access or observed evidence. V MUST NOT be I for the same increment. Evidence MUST bind commit/tree, lock/tool/platform versions and artifact SHA-256 to commands, outcomes, limitations and unresolved gates.

## Ordered small increments

All `src/`, `tests/`, scripts and ordinary user guides named below are planned locations, not implemented artifacts. Tests MUST verify the observable contract rather than merely repeat implementation. Each increment depends on the prior row unless explicitly narrower; V MUST pass applicable [verification inventory](implementation-verification.md) groups before the next dependent increment. Resources MUST be copied without byte changes from the assessed manifest, not re-fetched from mutable URLs.

| Increment | Allowed files / symbols and bounded output | Requirements / exit evidence |
| --- | --- | --- |
| I01 toolchain and package seam | `pyproject.toml`, `uv.lock`, `.python-version`, `src/dscat/__init__.py`, `cli.py:app/version/help`, `tests/test_package.py`, `tests/test_cli.py`; proprietary LICENSE retained. Extend the existing metadata/age-policy stub while preserving its proprietary fields; configure selected Python, age cutoff, explicit tool pins, package entrypoint and Ruff/ty/coverage; no parser or exporters. | NFR-001/003/004/014/016; clean frozen sync; help/version/license/install wheel smoke, CLI invalid option code 2; actual tool syntax and all-diagnostic audit. |
| I02 typed contracts and closed vocabulary | `models/{diagnostics,requests,configuration,catalog,intake}.py`: strict `CommandRequest`, `CommandResult`, `DiagnosticReport`, `ExportConfiguration`, `Catalog`, `DatasetRecord`, `IntakeBatch`; `normalization.py`; `tests/{test_models,test_normalization,test_configuration}.py`; `tests/fixtures/contracts/` including every Details_Quality section/property and rejected combinations. | FR-006/007/008/013/015/016/017/018; NFR-002/018/020; B02/B05/B06. Materialize explicit typed fields and full positive/negative vocabulary before I05 parser; no generic extension dictionaries. |
| I03 workbook generation | `workbook/generate.py:create_template`, `workbook/layout.py`; `tests/test_template.py`, `tests/fixtures/workbook-1.0/`; planned `docs/user/intake.md`. Produce supported-package-part matrix from actual synthetic generator output and reserve feedback cells. | FR-001/010; NFR-013/020/021; B03 generation/structural accessibility and formula-inertness; generated package-part inventory fixture is I05 prerequisite. Selected Excel observations remain I11. |
| I04 discovery and safe byte/worker gate | `intake/{discovery,archive,xml,worker,limits}.py`, `platform/{posix,windows}.py:ResourceGuard`; `tests/{test_discovery,test_archive,test_xml,test_workers}.py`, synthetic hostile fixtures; no unchecked workbook library reader. Implement serial guarded workers and all assurance ceilings. | FR-002/005; NFR-002/005/010/020; B01/B04, fail closed where a hard guard cannot be installed; actual Linux guard probe before accepting that adapter, P probes for other systems in I11. |
| I05 workbook parsing and validation | `workbook/parse.py:parse_workbook`, `intake/normalize.py:normalize_batch`, `validation.py:validate_catalog/deduplicate/assess`; `tests/{test_intake,test_validation,test_capacity,test_assessment}.py`. Only matrix-approved package parts and typed section/property conversion; no formula evaluation. Wire `validate`. | FR-002/005/006/007/010/013/015/016/017/018; NFR-002/009/013/020; B03–B07 including grouped service reference policy and independent readiness placeholders marked unperformed until exporters exist. |
| I06 canonical storage and publication | `storage/{models,flatfiles,publication}.py:load_snapshot/save_snapshot/publish`, `serialization.py:canonical_bytes`; `tests/{test_storage,test_publication,test_determinism}.py`; wire canonical-only `build`. | FR-008/011; NFR-002/005/009/018; B08/B11. Immutable generations/CURRENT lock and every injected write stage failure preserve previous pointer/content; cross-platform claims wait I11. |
| I07 offline DCAT-US 3.0 | `resources/registry.py:load_registry`, `resources/vendor/` plus manifest/licenses; `export/{models,dcat_us_3,readiness,loss}.py:project_dcat/assess_dcat`; `tests/{test_resources,test_dcat_us_3,test_graphs,test_losses}.py`; wire target `dcat-us-3`. | FR-003/006/018; NFR-002/009/010/019; B09. Package all 45 exact resources/42 schema documents; minimum/detail schema and intended offline graph validation, all omissions; MUST pass before I08 begins. |
| I08 ODCS 3.2.0 | `export/odcs_3_2.py:project_odcs/assess_odcs`, target DTOs; `tests/{test_odcs_3_2,test_readiness,test_losses}.py`; wire `odcs-3.2` after I07 acceptance. | FR-004/006/017/018; NFR-002/009/010; B09/B10. Independent schema/readiness, explicit roles/fields; supplied commitment loss, singleton versus repeated consumer-text loss, distinct identities/versions. Both targets required for release. |
| I09 public projection and safe result/report integration | `projection.py:approve_subject/project_public`, `diagnostics.py:render_text/render_json`, `cli.py:template/validate/build/export`; `tests/{test_projection,test_diagnostics,test_cli_contract,test_end_to_end}.py`. Finalize target-aware partial internal behavior versus all-or-nothing public behavior. | FR-013/014; NFR-002/008/020/021; B07/B10/B11, recursively seeded sentinels and all derived/source approval mutations; S fresh review is mandatory. |
| I10 secure engineering and delivery materials | `scripts/verify.py`, `scripts/release_evidence.py`, `tests/test_release_evidence.py`, `SECURITY.md`, `docs/user/{installation,verification,compatibility}.md`, `.github/workflows/verify.yml`, third-party notices and SBOM configuration. No automatic publication. | NFR-003–007/008/011/012/014–017/022; B12/B13, SSDF mapping/report rehearsal; source/package/help license checks; minimal CI and full local gate. |
| I11 platform/manual acceptance and 0.1.0 candidate | P executes platform gates; A executes selected desktop walkthrough; V independently verifies built wheel/sdist and full RTM; R prepares artifact evidence only after merged verified main. `docs/evidence/releases/0.1.0/` and concise actual RTM evidence. | All applicable first-release requirements; B01–B13; [manual arrangements](implementation-verification.md#owned-platform-and-desktop-gates). Missing selected environment/access/evidence or unresolved defects MUST block applicable acceptance and first release. R then follows [delivery plan](delivery-plan.md); downloaded-release verification is separate fresh invocation. |

I10 tooling MUST itself receive tests for substantive artifact/security decisions, including missing SBOM component, mismatched wheel/source hash, stale advisory data and exploited Low-severity findings. Reversible document edits MUST use document QA rather than mirror-text tests. No release script MUST turn a tag or passing CI into automatic publication.

## Complete requirement and artifact map

Each row supplements the stable acceptance/design references in [RTM](rtm.md). The symbols and tests are planned internal implementation boundaries; they MUST NOT create a public Python API. Evidence is PENDING until the named increment and independent verification execute. Cross-cutting artifacts MUST retain the indicated justification; unsupported code MUST NOT be justified retroactively by inventing requirements.

| Requirement | Increments | Planned file / symbol or artifact | Verification inventory |
| --- | --- | --- | --- |
| FR-001 | I03/I11 | `workbook/generate.py:create_template`; intake guide | B03, desktop A |
| FR-002 | I04/I05/I09 | `validation.py:validate_catalog/deduplicate`; `intake/worker.py`; diagnostic DTOs | B01/B03/B04/B05/B11 |
| FR-003 | I07 | `export/dcat_us_3.py:project_dcat`; resource manifest | B09 |
| FR-004 | I08 | `export/odcs_3_2.py:project_odcs`; `readiness.py:assess_odcs` | B09/B10 |
| FR-005 | I04/I05 | `intake/discovery.py:discover`; `cli.py:build` | B01/B03 |
| FR-006 | I02/I05/I07/I08 | `models/catalog.py:DatasetRecord`; both readiness functions | B02/B05/B09 |
| FR-007 | I02/I05 | `models/catalog.py:CapacityObservation`; `normalization.py:normalize_quantity` | B06 |
| FR-008 | I02/I06 | `models/catalog.py:Catalog`; `storage/flatfiles.py:load_snapshot/save_snapshot` | B08 |
| FR-010 | I03/I05 | `workbook/layout.py`; `workbook/parse.py:parse_workbook` | B03, desktop A |
| FR-011 | I06/I09 | `storage/publication.py:publish`; CURRENT/manifest | B08/B11, P |
| FR-012 | later L02 | Planned `lineage.py:ProcessingActivity/EntityReference/ResponsibleAgent`, optional Lineage table/PROV exporter after detailed gate | Later multi-input/handoff/cycle/graph tests PENDING |
| FR-013 | I02/I05/I09 | `validation.py:assess`; `models/diagnostics.py:ValidationAssessment` | B07/B10 |
| FR-014 | I09 | `projection.py:project_public/approve_subject`; public-only manifest | B10/B11 |
| FR-015 | I02/I05 | `models/catalog.py:RecordsManagement`; records vocabulary | B05/B06 |
| FR-016 | I02/I05 | `models/catalog.py:RoleAssignment`; typed dates/references | B05 |
| FR-017 | I02/I05/I08 | `ConsumerDetail/Commitment`; local `assess`; loss report | B05/B07/B09 |
| FR-018 | I02/I07/I08 | distinct identity/version DTOs; `export/loss.py:ProjectionLoss` | B05/B09/B10 |
| FR-019 | later L01 | Planned separate `export/w3c_dcat_3.py`, JSON-LD registry; no initial stub | Later Dataset/Distribution/DataService offline graphs PENDING |
| FR-020 | later L03 | Planned `models/product.py:Product/LifecycleEvent/Port`; ODPS exporter | Later link/state/transition/port/schema tests PENDING |
| FR-021 | later L04 | Planned `export/dcat_us_1_1.py` and independent resource registry entry | Later schema/semantic/loss/readiness tests PENDING |
| NFR-001 | I01/I10/I11 | Python/uv pins, entrypoint, wheel/sdist, installation guide | B12, P |
| NFR-002 | I02–I09 | strict request/config/intake/canonical/target/diagnostic/publication DTOs | B01–B11 |
| NFR-003 | I01/I10 | Ruff ALL/formatter, ty error rules, branch coverage config; full tests | B12 |
| NFR-004 | I01/I10 | uv age configuration, lock and artifact upload evidence | B12/B13 |
| NFR-005 | I04/I06/I09/I10/I11 | guards, safe parser, atomic writer, vulnerability evidence | B04/B08/B10/B13, P |
| NFR-006 | all | RTM, commits/PR/source identities, stage ledger | All groups, protected integration/release gates |
| NFR-007 | I10/I11 | `docs/user/verification.md`, actual walkthrough evidence | Manual and B11–B13 |
| NFR-008 | all | synthetic fixtures, staged/artifact privacy inspection | B10/B13 |
| NFR-009 | I05–I09 | canonical serializer/order rules, immutable publication | B05/B08/B09/B11 |
| NFR-010 | I04/I07–I11 | denying registry, finite inline context, packaged resources | B04/B09/B12 offline install/runtime |
| NFR-011 | I10/I11 | CycloneDX 1.6 JSON, release manifest/lock reconciliation | B13 |
| NFR-012 | I10/I11 | advisory/exploitation/VEX applicability evidence | B13 |
| NFR-013 | I02/I03/I05 | workbook/config/report/canonical 1.0 fixtures/version rejection | B03/B05/B08/B11 |
| NFR-014 | I01/I10/I11 | LICENSE, project license metadata, help/build notices | B12/B13 |
| NFR-015 | every integration | repository-policy API check, protected PR/main identity | B13 |
| NFR-016 | I01/I10 | `scripts/verify.py`, one small supplementary Linux CI job | B12 |
| NFR-017 | I10/I11 | wheel/sdist/checksums/private download guide/release evidence | B12/B13, fresh downloaded verification |
| NFR-018 | I02/I06 | canonical `schema_version`, storage port, refusal hint | B05/B08 |
| NFR-019 | I07 | inline finite context, graph fixtures, denying registry | B09 |
| NFR-020 | I02–I05/I09–I11 | role-contact guidance, minimized diagnostics, public DTOs | B03/B04/B10/B11 |
| NFR-021 | I03/I09/I10/I11 | workbook labels, no-color CLI, user guide headings/links | B03/B11, selected desktop A |
| NFR-022 | I10/I11 | SECURITY.md, SSDF control/evidence ledger, synthetic triage | B13, M |

## First independent implementation handoff

The next model MUST start only I01 after exact plan QA and an explicit subsequent implementation assignment. It MUST read AGENTS/index/workflow implementation route, engineering, governance, this plan, [dependency selection](implementation-dependencies.md), verification B11/B12, architecture compatibility/help/exit contract, NFR-001/003/004/014/016, repository policy and current gates. Its source MUST be the integrated combined architecture/plan revision supplied by the coordinator, not the pre-plan architecture hash above. Allowed mutations are I01 files and a compact increment evidence/RTM update only. It MUST acquire selected Python and uv in an isolated development environment, verify newer-runtime policy at execution, resolve eligible hashes into the first lock, inspect tool help/schema for Ruff/ty configuration, build/install the package and return exact source/lock/artifact hashes and commands. No workbook parsing, target exporter, release or automatic CI publication belongs to I01. A dependency incompatibility MUST be reported and resolved without silently downgrading Python. V MUST independently verify these artifacts before I02. No product artifact is authorized merely by merging this planning PR.

## Later milestone handoffs

L01 MUST follow accepted 0.1.0 delivery and separately design W3C DCAT 3 exact supported terms, closure/licenses, independent readiness and graph fixtures. L02 MUST follow L01 and design optional manual entity/activity/agent capture, explicit local/external references, multi-input/multi-step handoff, cycle/self-reference rejection and explicit supported PROV-O JSON-LD export. L03 MUST follow L02 and select ODPS version/closure, distinct product identities, allowed lifecycle transitions and descriptive input/output ports with dataset/contract links; no provisioning/live tests. L04 MUST follow L03 and select DCAT-US 1.1 closure/required facts/mappings/losses. Each MUST obtain fresh architecture risk disposition and detailed ordered plan, compatibility/schema impact, test and delivery evidence before implementation. These are sequenced gates, not ready first-release increments or selected later runtime pins.
