# Verifying the collection intake workflow

Use only synthetic metadata in a disposable local directory. Automated and installed evidence identifies its exact candidate and environment; these instructions alone do not claim execution or application compatibility.

## Generate and inspect

```sh
dscat template --output blank.xlsx
dscat template --output example.xlsx --examples
```

Open the blank workbook in Excel. Confirm Start here precedes Intake, the visible markers are `2.1` / `collection-intake`, headers are on row 5, data starts on row 6, and collection name remains visible while scrolling. Inspect header notes, topic bands, the retention authorizer column and the size-only dropdowns. Move complete table columns, including headers and values, into a different order and confirm validation/build preserves the same facts. No process information is required to register a collection.

The worked example contains seven synthetic collection rows with FTK Imager, Plaso, MISP and Timesketch process summaries. Every quantity and responsible party is invented. Source names describe the derivation and indicator-reference input; they are not a formally resolved lineage graph or automatic tool integration. The first retention duration is a fictional Confirmed example with a fictional authorizer; the others are Proposed examples rather than recommendations or disposal authority.

## Complete and validate

In blank.xlsx enter a collection name, Unknown owner, six Unknown sensitivity responses, a synthetic submitter and completion date. Leave optional groups blank, save and run:

```sh
dscat validate blank.xlsx --format json
dscat validate example.xlsx --format json
```

Both should be valid; standards targets can remain blocked for missing facts. The blank-derived submission should contain one collection and the unchanged example seven. In the example, remove all seeded input rows to obtain a valid empty workbook, then enter a different minimum synthetic collection. No example records should remain after removal.

Try a known zero current amount with KB and Estimate; separately enter a positive new amount per run with GB and Measured. Confirm Unknown requires blank amount/unit, and blank optional groups remain absent. Reported Measured does not create an instrumented measurement observation. Add optional semicolon-separated source names, including one not registered locally; descriptive unresolved names remain valid.

For each negative trial, use a separate copy. Clear a required sensitivity response; choose Other = Yes without an explanation; supply a negative amount, unsupported count unit, invalid date, fractional retention, Confirmed retention without days, numeric run count without a numeric period, or input formula. Validation should return metadata failure with actionable cell locations. Restore the bad value and confirm successful retry. Unknown markers should report unsupported version; missing or conflicting markers should fail workbook validation. Never open hostile package fixtures in Excel.

## Save and regenerate

```sh
dscat build blank.xlsx --output catalog --format json
```

Inspect the internal canonical `1.1` registration: absent description/contact stay absent; owner uncertainty, six sensitivities, submission identity/date and supplied optional groups survive. Repeating without `--replace` should refuse output replacement. A failed edited submission with `--replace` should preserve the earlier CURRENT pointer and generation. Correct it and retry explicitly.

After supplying target-required metadata through supported canonical fields and explicit configuration, export DCAT-US 3.0 and ODCS 3.2.0 from the saved bundle after moving the original workbook away. Both targets should validate against their bundled schemas. Missing target facts should affect their own readiness, not fabricate catalog values. Public projection needs separate exact supplied approvals; sensitivity answers and successful intake do not grant them.

The installed acceptance harness performs a synthetic target-ready `2.1` round trip and public-output preservation under a runtime network guard. Legacy workbook fixtures remain isolated security/regression inputs; they are not current user forms. Canonical `1.0` preservation and richer-field regressions are verified separately. Application observations should record the actual Excel version and limits; automated layout assertions do not substitute for an observed open/edit/save trial.
