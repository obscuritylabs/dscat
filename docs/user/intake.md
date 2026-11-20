# Completing a dataset workbook

Template generation, workbook validation and [canonical catalog persistence](storage.md) are implemented in this development build. Standards exports are still in development. The [current schema 1.0 template](../../tests/fixtures/workbook-1.0/current.xlsx) is available for inspection; native macOS intake and manual accessibility acceptance remain pending while the memory guard is corrected. Implementation availability does not establish platform acceptance.

## Start with the required core

Read Instructions, then open Datasets. Enter one dataset per row using these four columns:

| Column | Example | Meaning |
| --- | --- | --- |
| `id` | `asset-001` | A stable, case-sensitive identifier: 1–128 ASCII letters, digits, dots, underscores, colons or hyphens, starting with a letter or digit. |
| `title` | `Synthetic measurements` | A short dataset title. |
| `description` | `Synthetic measurement metadata.` | A description of the dataset. |
| `core_party` | `Metadata support` | The supplied contact or owner label. Prefer a role contact rather than unnecessary personal information. |

The optional `core_role` dropdown offers `contact` and `owner`. A blank role means unspecified contact/owner. A label alone establishes neither accountable ownership nor an export-ready contact association. Leave other absent values blank; do not substitute zero or `Unknown` into ordinary text fields.

## Add optional details

Fields describes an ordered field schema. Supply `dataset_id`, `object_name`, `field_name` and `type`; description, nullable and semantic reference are optional. Use `Yes` or `No` for a supplied nullable value. A blank nullable cell means absent.

Details_Quality uses one scalar per row. Choose a section and property, repeat the dataset ID, and use a stable `entry_id` to group properties belonging to the same object. Single-value dataset properties use `dataset`; repeated roles, services, distributions, assertions, consumer values and records conflicts use distinct entry IDs. Repeating a property in one group is an error, even if its values agree. The visible lists on Instructions show the supported vocabulary.

The optional Datasets `owner`, `steward` and `maintainer` columns reference a role group’s `entry_id` for that dataset in the same workbook. For example, `owner=ownership-1` references a Details_Quality `role` group with entry ID `ownership-1`, `party_id=governance-team`, `reference_kind=local`, `role=accountable_owner` and `label=Metadata governance`. Supply each property on its own row. Use matching `steward` or `maintainer` roles for those columns. Leave the columns blank when you only use the detail groups; each group is imported once. These cells do not accept party labels or create identities.

Capacity uses explicit size or ingestion kind, known/unknown state and measurement context. A known quantity needs decimal text, one of the supplied byte units, logical/physical basis and a measurement date. Ingestion also needs an explicitly offset start/end window. Unknown is distinct from a known zero; unknown quantities have no invented unit, date or window. Retention uses whole days, indefinite or unknown. It does not establish records disposition authority.

Use `YYYY-MM-DD` date text. Input cells use text formatting to preserve identifiers and date spelling. References remain descriptive text; the template creates no hyperlinks or live connections.

## Navigate and correct entries

Use the completion application's keyboard commands to change sheets and open dropdowns, and Tab or Shift+Tab to move between input cells. macOS is the primary target; exact application and assistive-technology versions and observed keyboard behavior are recorded during manual acceptance. Instructions comes first; the input sheets have a frozen header and key columns, with no merged, hidden or protected input cells.

Read the `feedback` column for missing fields, duplicate IDs, unsupported choices, date errors and invalid day counts. These messages work without color. `Ready for CLI validation` describes preliminary workbook feedback, not completed validation or export readiness. Keep feedback cells separate from input cells; they are never catalog facts.

The first 1,000 input rows include controls and feedback. Excel copy/fill can extend them; the CLI will independently enforce overall resource limits. Spreadsheet controls provide prompts and preliminary checks. Full type/precision validation, cross-file conflicts, reference resolution, supplied authority and target readiness belong to CLI validation. Bypassing or removing a spreadsheet control does not authorize invalid metadata.

Keep the schema/kind markers unchanged. Do not add formulas to input cells, macros, external relationships, embedded objects or unsupported semantic sections. Lineage is outside workbook schema 1.0. Use only synthetic materials for testing the template.


## Validate a completed workbook

Run `dscat validate intake.xlsx --format json` for a structured assessment, or omit `--format json` for plain text. Use `--recursive` only when you want to include nested directories; an explicitly supplied `--config settings.toml` is checked before any workbook processing. Validation reads submissions without modifying them and publishes no catalog artifacts.

Reports identify sources by deterministic discovery ordinal and known worksheet, row and column locations. Correct the reported type, vocabulary or reference errors and retry. Checks that depend on unreadable or invalid inputs remain explicitly unperformed; they do not create guessed dangling-reference errors.

Structural validity, optional completeness and declared local conformity remain separate results. Review and publication remain supplied decisions. Target readiness is explicitly unexamined while standards exporters are in development.
