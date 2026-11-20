# Verifying a candidate

This walkthrough uses synthetic metadata. Record observations against the exact candidate; expected results below are instructions, not claims that the selected desktop checks passed. Current execution and release readiness follow the [planning gates](../planning-gates.md). Use the [installation guide](installation.md) to verify downloaded assets and install the candidate outside its source checkout.

## Prepare the workspace and evidence

Use a fresh disposable local directory on a supported filesystem. Keep the candidate's wheel/source archive, `SHA256SUMS`, SBOM, dependency inventories and verification report. Record source revision, artifact hashes, OS/build/architecture, filesystem, Python/uv and installed package versions. For desktop checks also record Excel for Mac, Terminal, Safari and VoiceOver versions. Keep local account names, host identifiers and private paths out of retained public evidence.

Copy the [walkthrough fixtures](../../tests/fixtures/walkthrough/fixture-manifest.json) from the exact candidate source into the disposable directory. Check their SHA-256 values against that manifest. The workbooks derive from the installed public `template` command; the manifest identifies its template and wheel bytes. All supplied review/publication authorities are explicitly synthetic test facts.

| Fixture | Purpose / expected validation |
| --- | --- |
| [minimum.xlsx](../../tests/fixtures/walkthrough/minimum.xlsx) | Four-field minimum; valid intake, both targets ready with shared configuration |
| [detailed.xlsx](../../tests/fixtures/walkthrough/detailed.xlsx) | Detailed optional metadata and synthetic scoped approvals; valid intake and both targets ready |
| [invalid.xlsx](../../tests/fixtures/walkthrough/invalid.xlsx) | Missing required text, invalid calendar date and unsupported capacity unit; `INVALID_METADATA`, exit 1 |
| [conflict.xlsx](../../tests/fixtures/walkthrough/conflict.xlsx) | Conflicting description for the minimum workbook's identifier; together they produce `DUPLICATE_CONFLICT`, exit 1 |
| [future.xlsx](../../tests/fixtures/walkthrough/future.xlsx) | Unsupported workbook schema; `UNSUPPORTED_VERSION`, exit 2 |
| [formula.xlsx](../../tests/fixtures/walkthrough/formula.xlsx) | Formula in an input title cell; `INVALID_METADATA`, exit 1 |
| [unsafe.xlsx](../../tests/fixtures/walkthrough/unsafe.xlsx) | Unsupported traversal member in its ZIP; `UNSUPPORTED_WORKBOOK_PART`, exit 1 |
| [shared.toml](../../tests/fixtures/walkthrough/shared.toml) | Explicit namespaces, contact association, catalog identity and contract version |
| [approved-public.toml](../../tests/fixtures/walkthrough/approved-public.toml) | Shared facts plus synthetic publication policy and exact allowed scopes |
| [detailed-canonical.json](../../tests/fixtures/walkthrough/detailed-canonical.json) | Expected canonical detailed catalog, including supplied review and publication facts |

Open only the positive minimum/detailed workbooks and newly generated template in Excel. Inspect negative fixtures with DSCat and controlled tests; do not open them in Excel. Use separate directories for positive intake, deliberately conflicting intake, catalog outputs and private reports. Inputs, outputs, configuration and reports cannot overlap.

## Complete the template with keyboard and VoiceOver

Run `dscat --version` and `dscat --no-color --help`. Expect version `0.1.0`, the proprietary notice, plain text and usable command/option descriptions. Run:

```sh
dscat template --output intake.xlsx
```

Open this newly generated synthetic workbook in Excel for Mac. With keyboard and VoiceOver, navigate Instructions → Datasets → Fields → Details_Quality. Check worksheet names, header announcement, logical reading order, frozen panes, prompt/dropdown access and correction feedback without relying on color. Ensure markers and feedback formulas do not trap navigation.

In Datasets row 2, enter `asset-001`, `Synthetic measurements`, `Synthetic metadata.` and `Metadata support` under the four required headers. Leave the optional role references blank. Check optional detail entry against the positive detailed fixture. Deliberately omit a required value, enter a bad unit/date and duplicate an identifier in a separate disposable copy; observe textual feedback and correction with VoiceOver. DSCat validation must still reject invalid values when spreadsheet controls are bypassed.

Repeat the template command without `--replace`: expect exit 3 and unchanged existing bytes. Repeat with `--replace`: expect success and a complete valid workbook. Record actual announcements, keyboard steps, failures and recovery. Missing observations remain pending.

## Validate positive and negative input

```sh
dscat validate minimum.xlsx --config shared.toml --format json
dscat validate detailed.xlsx --config shared.toml --format json
```

Expect exit 0, valid intake and both targets ready. Without `--config`, the minimum remains structurally valid while required target facts are blocked; validation does not claim export.

Validate each negative fixture separately with the shared configuration and compare its exit/code against the table. Invalid metadata is located at Datasets row 2 and Details_Quality rows 2/3; input formula correction is at Datasets row 2. Do not expect a diagnostic for content that could not be safely examined.

Copy minimum and conflict into a new `conflicting-input` directory and validate that directory. Expect conflict and no accepted catalog. Add a separate readable positive file alongside an unsafe input to confirm readable input is examined while the invocation fails. Diagnostics must not echo submitted descriptions, arbitrary error text or local paths.

## Build, replace and recover saved metadata

```sh
dscat build minimum.xlsx --output catalog --config shared.toml --target dcat-us-3 --target odcs-3.2 --format json
dscat build detailed.xlsx --output detailed-catalog --config shared.toml --target dcat-us-3 --target odcs-3.2 --diagnostics detailed-report.json --format json
```

Expect exit 0, a canonical receipt and both successful targets. Inspect CURRENT, the selected manifest/canonical records and target JSON. Independently validate target schemas and JSON-LD graph meaning using the candidate tests. Detailed canonical facts must match the supplied expected catalog after normalization. The private report must identify omitted detailed commitments and unsupported repeated consumer-text cardinality without copying their values into the loss report.

Repeat a build without replacement: expect exit 3 and identical old bytes. Repeat with `--replace`: expect identical canonical, export and generation identities. In a separate positive input directory, create a second synthetic workbook by changing the minimum's ID to `asset-002`. Build two records, move that second workbook outside the selected input, then replace. Expect one current record while the previous generation remains readable.

Move the original positive workbooks outside the selected input and run:

```sh
dscat export catalog --output regenerated --config shared.toml --target dcat-us-3 --target odcs-3.2 --format json
```

Both target outputs must reproduce their original bytes from saved canonical metadata. For detailed metadata, confirm supplied dates, roles, capacity distinctions and retention survive reload. Recovery and retained-generation rules follow the [storage guide](storage.md#recover-and-retry).

## Check independent target and public eligibility

Use copies of the shared configuration. With the contact mapping removed, export the saved minimum catalog: expect internal partial success, exit 1, ready ODCS and no DCAT file. With only the configured contract version removed, expect DCAT ready and ODCS blocked. Do not use the detailed record for this test, because it supplies additional contact/version facts.

Export the saved detailed catalog using the supplied synthetic publication configuration:

```sh
dscat export detailed-catalog --output public --config approved-public.toml --target dcat-us-3 --target odcs-3.2 --audience public --diagnostics public-private-report.json --format json
```

Expect both target documents and a minimal public manifest. The public directory must contain no canonical records, configuration, approvals, private diagnostic report or loss report. Inspect exact field allowlists and synthetic sentinel exclusions with the tests. A separate report has no publication receipt; only the final command result confirms publication.

Changing the namespace, party association, catalog identity, mapping/resource binding or source selection invalidates affected approvals. Exercise the exact mutations in `tests/test_publication_bindings.py` and `tests/test_projection.py`; missing approval must withhold the whole public bundle. Exporting the unapproved minimum catalog to a public audience must also be refused. Preserve the previously accepted public CURRENT bytes after a denied replacement.

## Run controlled failures and offline acceptance

From the exact candidate source environment, run the following test selectors. They inject failures through test-only seams; do not add fault options to production commands.

```sh
uv run --frozen pytest -q tests/test_publication.py::test_each_precommit_failure_preserves_previous_snapshot tests/test_publication.py::test_interruption_and_abandoned_stage_are_safe tests/test_storage_io.py::test_short_write_and_file_flush_failure
uv run --frozen pytest -q tests/test_workers.py::test_entry_never_reads_input_when_guard_unavailable tests/test_workers.py::test_request_pipe_failure_and_interruption_reap tests/test_workers.py::test_request_serialization_refusal_has_zero_work
uv run --frozen pytest -q tests/test_cli_validation.py tests/test_native_transport.py
```

The publication cases cover serialization, mkdir, write, flush, reload, rename, pointer write and CURRENT switch under permission/disk-full/cross-device errors. They require prior-byte preservation, no valid partial marker and corrected retry. Worker/CLI cases require fixed operational/interruption outcomes, termination/reaping and truthful unexamined scope. Internal failure has exit 4; operational failure has exit 3; interruption has exit 130. Record exact selected test IDs and results rather than treating expected failures as successful product operations.

Run the complete local command from the source environment:

```sh
uv run --frozen python scripts/verify.py --full --evidence-dir /new/disposable/evidence-directory
```

Select a new real local directory outside source; the displayed path is a placeholder. The command runs automated quality and package checks, installs a clean runtime, proves its network-denial hook is active, then exercises template → validation → build/reload → both internal and approved public exports. It checks deterministic repeats, refused replacement, public denial preserving CURRENT and unknown remote schema refusal. The deliberate socket probe must be denied and subsequent workflow network attempts must be zero. Raw tool logs stay in private evidence; inspect public assets separately for disclosure.

`--ci` runs bounded static/document/CLI/package checks. `--full` returns 0 only for complete release readiness, 1 for unmet release gates, 2 for an automated/setup failure and 130 for interruption. Missing operator, desktop, independent or verified-main evidence stays blocked even after automated checks pass. Neither command publishes a release.

## Record desktop and final acceptance

In Terminal with VoiceOver, check plain/no-color help, errors, ordinal source/row/column correction, narrow windows, redirected output and keyboard-only invocation. In Safari with VoiceOver, render the exact candidate documentation and check heading/link navigation, logical order and recovery instructions. Record each selected criterion, actual announcements and limitations; headless tests do not establish these observations.

Use the confidential reporting/triage procedure only after its actual setup and access are verified. Retain current advisory/exploitation, SBOM, licensing, privacy and independent acceptance evidence bound to the candidate. An available role label or passing CI cannot supply those observations.

Inspect only the disposable workspace you created before any explicit cleanup. Retain concise neutral results and hashes. After publication, a fresh independent verifier must download the actual released assets, verify checksums/bindings, install in a clean environment and repeat representative offline/source acceptance. Pre-publication testing does not establish downloaded-artifact verification.
