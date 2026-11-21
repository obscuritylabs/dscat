# Completing a collection intake workbook

Generate a blank workbook with:

```sh
dscat template --output intake.xlsx
```

For an editable worked example, add `--examples`. Existing output requires explicit `--replace`. Both modes use workbook schema `2.0`, with instructions on Start here and a single Intake table. Keep the visible schema/kind markers unchanged. The example uses public tool names and invented quantities, people, teams, locations, sensitivity answers and retention decisions. Its rows are ordinary records: remove or replace them before submitting other metadata.

## Start with one collection

Enter one recurring collection per row, starting at row 6. Describe collections rather than individual files, runs or devices. A shared collection appears once even when several processes use it. Collection name, accountable data owner/team response, all six sensitivity responses, entry submitter/accountable person and completion date are required. Description, current location and all other groups are optional.

Use Unknown when accountable ownership is not known. The owner/team identifies who has authority over the data; the submitter is responsible for the answers in this entry. Those are distinct responsibilities. Completion date records when the entry was completed or reviewed, not when its data arrived or was modified. Enter a normal Excel date or exact `YYYY-MM-DD` date text.

PII, PHI, CUI, PCII, ISVI and Other sensitive data each take Yes, No or Unknown; several categories may apply. Other = Yes needs an explanation of the category. These are reported responses, not formal classification, validation or publication decisions. No does not mean approved for release. Do not paste underlying data, credentials, sensitive samples or unnecessary personal details into the form.

## Add optional information

Color bands group current volume, collection use, retention and how the collection is generated. Hover a column header for guidance. The collection name remains visible while scrolling. Headers are filterable; input cells remain editable and unprotected. The first 200 rows have controls; ordinary copy/fill can extend them. The importer examines all populated bounded input rows, including rows below the table's displayed range.

Current amount held and new amount produced per run are separate quantities. For each supplied known quantity, enter a nonnegative number, one of KB/MB/GB/TB/PB, and Estimate or Measured. Units use decimal multiples: 1 GB = 1,000 MB. For Unknown, leave amount and unit blank and select Unknown as its basis. A completely blank group remains absent. Zero is a known quantity, not an unknown answer. Measured is the contributor's reported basis; it does not supply a measurement date or logical/physical storage context.

Who uses this collection, Used for and Access pattern describe consumers, purpose and technical use. They do not grant access. Retention uses optional whole days from each batch arriving at its destination, with an optional Not yet determined, Proposed or Confirmed status. Confirmed needs a duration; zero means immediate expiry. Each derived collection has its own answer. The form does not authorize deletion or enforce storage acceptance.

The generating process is optional. Describe how the collection is produced, known source collections, typical new output per run and frequency where useful. Separate source names with semicolons; names can refer outside the submission. They are descriptive provenance, not validated formal lineage edges. Multiple generating processes can be described in the same row; leave per-run averages blank if one meaningful average cannot describe them. Numeric run counts need a day/week/month/year period; use On demand or Unknown without a numeric count. No forecasts or costs are calculated.

## Identity, validation and correction

Collection identity is derived deterministically from its normalized name, preserving case and internal spacing. Reuse names consistently. Renaming or changing case creates a different identity; no automatic rename reconciliation occurs. Identical normalized records deduplicate; conflicting answers with the same collection identity block the build rather than overwrite one another.

Validate without modifying the workbook:

```sh
dscat validate intake.xlsx --format json
```

Diagnostics identify the source ordinal, sheet, row and column without echoing submitted values. Correct the indicated required response, choice, date, quantity or group and retry. Dropdowns are preliminary assistance: pasting can bypass them, so the CLI independently checks the submission. Input formulas are refused regardless of their cached results. Do not add macros, external links, connections or arbitrary embedded objects. Ordinary table and header-note parts are checked through a closed package vocabulary.

Valid registration, optional completeness, target readiness and publication authority remain separate. Missing description/contact/contract facts can block a standards export while a minimum collection registration remains valid. Shared configuration can supply its explicit supported target facts, not invented descriptions or ownership. Example quantities are teaching assumptions, not benchmarks or capacity guarantees; every illustrated retention duration is a fictional proposal.

Build a canonical bundle using the [storage guide](storage.md). New collection registrations use canonical `1.1`; existing genuine `1.0` bundles remain readable and retain their versions. See [compatibility](compatibility.md) for format boundaries. Workbook `1.0` fixtures are isolated regression materials, not the current form. Automated checks do not establish that a particular Excel application/version has been manually observed; current product evidence states that limitation separately.
