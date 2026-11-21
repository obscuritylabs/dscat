# Building and exporting a catalog

Canonical storage is implemented in this development build. DCAT-US 3.0 and ODCS 3.2.0 exports are implemented with separate readiness checks. Native intake availability and outstanding verification follow the [current execution status](../planning-gates.md#implementation-execution).

Run `dscat build intake.xlsx --output catalog --format json` to validate a workbook and publish an internal canonical bundle. You can select a directory instead; use `--recursive` to include nested directories and `--config settings.toml` for explicitly selected configuration. An empty directory creates a valid empty catalog. Inputs and output must be separate, with neither inside the other.

Without a target option, the build contains canonical facts only. It contains no standards document and grants no publication authority. The separate assessment reports readiness for implemented targets. Invalid, unreadable or resource-limited input prevents publication. The structured command result contains fixed diagnostics, counts, assessment and the generation hash; it does not print canonical values or local paths.

Collection-first intake produces canonical `1.1` records, preserving missing descriptions, explicit owner uncertainty, sensitivity, submission responsibility, registration quantities, retention status and optional generation summaries. These are separate from richer measured-capacity and records-authority metadata. Existing genuine canonical `1.0` bundles retain their version and facts on load/save; they are not rewritten automatically. Old software cannot read `1.1` bundles. See [compatibility](compatibility.md) for the version boundary.

## Select targets and reports

Add `--target dcat-us-3 --target odcs-3.2 --config settings.toml` to build the requested standards outputs with canonical data. Missing export facts do not invalidate intake. A blocked target has no placeholder file; ready requested targets and canonical facts can be saved together, with exit status 1 and a receipt listing only successful targets. An I/O or serialization failure prevents the entire bundle switch.

Run `dscat export catalog --output derived --target dcat-us-3 --target odcs-3.2 --config settings.toml --format json` to derive a new internal bundle from saved canonical data. Original workbooks are unnecessary. The source bundle remains unchanged. Configuration is explicitly selected, versioned TOML; no home-directory or environment configuration is discovered.

An explicitly selected `--diagnostics report.json` saves a private assessment and omission report. It can contain record identifiers and known field paths, but excludes other submitted field values. Keep it outside input, output and configuration paths. Reports have independent overwrite protection; commands supporting `--replace` apply it to both selected output and report. Validation has no replacement option, so select a fresh report path. A report contains no publication receipt: it is written before a bundle switch, and only the final command result states whether publication succeeded. A failed report write prevents publication and returns operational failure. A completed report can remain when a subsequent bundle operation fails.

## Public projection

Use `dscat export catalog --output public-derived --target dcat-us-3 --target odcs-3.2 --audience public --config settings.toml --format json` for a local public projection. This creates local artifacts; it does not upload them. Public output requires supplied metadata review, unrestricted metadata disclosure and publication decisions, plus exact current approvals for each emitted canonical/configuration fact and derived identity. Configuration allowlists restrict eligible scopes; they do not grant approval. Hashes identify approved content and dependencies; authentic authority is verified outside this tool. Data access and reuse rights remain separate supplied facts.

The initial public shape is deliberately small: approved dataset ID, title, description, selected contact facts, and target-required identities/version. Optional fields, roles, consumer details, commitments and other private children are excluded. A changed source, namespace, identity rule, contact association, mapping revision or policy version invalidates affected approvals. Missing or stale approval for any selected target withholds the entire public bundle. Build supports internal output; create public output by exporting the saved canonical bundle.

Public generations contain only target JSON and a minimal manifest of target names, relative paths and byte hashes. They contain no canonical records, configuration fingerprints, authorities, assessment or loss reports. Choose a separate private report destination when needed. A public destination cannot replace a canonical bundle or retain private history. Extra root files, abandoned stages or invalid retained generations prevent public replacement until explicitly inspected and resolved.

## Read the bundle

The bundle has a `CURRENT` file and a `generations` directory. `CURRENT` selects one immutable generation by its full SHA-256 hash. Each internal generation contains `manifest.json` and a `datasets` directory, plus `exports` for successful requested targets. Dataset filenames use full hashes of normalized business identifiers. The manifest maps those filenames to their identities, schema versions and content hashes.

Canonical JSON preserves the supplied metadata, including private metadata. Keep the bundle in an appropriate local location. Hashed filenames are a portability measure, not encryption. The internal storage interface can reload the catalog without the original workbook; a public Python API is not promised for this version.

Stored content is checked again when loaded. Missing, extra, modified, noncanonical, linked or unsupported-version artifacts are refused. Copy the complete bundle rather than selected dataset files. Do not edit generated files in place or follow their descriptive references as instructions.

## Replace a catalog

An existing destination requires `--replace`, even for identical content. For example, run `dscat build intake.xlsx --output catalog --replace --format json`. A successful replacement retains previous generations and switches `CURRENT` only after writing, flushing and validating the new one. Omitted datasets disappear from the new generation while prior generations remain intact. Unchanged inputs produce identical canonical and generation bytes.

Publication uses a writer lock and staging on the same local filesystem. Supported publication filesystems are local APFS/HFS on macOS, local ext2/ext3/ext4/XFS/Btrfs/tmpfs on Linux, and fixed local NTFS on Windows. Unknown filesystems, network shares, cross-device paths and linked destinations are refused. Native verification is reported separately from this implementation list. In particular, an overlay filesystem is not assumed local merely because it belongs to a container.

The guarantee is atomic visibility on process failure. It is not a guarantee against arbitrary hardware failure or power loss. File and directory flush failures, permission errors, full disks and failed renames return operational failure. A failure before the pointer switch preserves the previously accepted generation.

## Recover and retry

`PUBLICATION_LOCKED` means another writer or an abandoned `.writer.lock` prevents a new write. First confirm that all writers have stopped and verify the intended bundle. Only then explicitly remove that lock and retry. The program never steals a stale lock automatically.

`RETAINED_OUTPUT` reports retained generations or abandoned staging outputs. Prior generations may be useful history; an uncommitted generation can have the same valid structure. Readers use only `CURRENT`. Review `.stage-*`, `.pointer-*` and noncurrent generations before any explicit cleanup. The program does not automatically delete history or abandoned outputs.

A failed initial creation can leave a directory with no valid `CURRENT`. It is not silently adopted, even with `--replace`. Preserve and inspect it, then explicitly select a fresh destination or move the abandoned directory aside before retrying. Do not remove unrelated files as recovery.

All resource ceilings apply together: individual JSON is at most 32 MiB and depth 64; snapshots, including the manifest, are at most 256 MiB; catalogs contain at most 100,000 datasets. Private worker messages have their own 32 MiB ceiling. Reaching one ceiling can prevent a build before another ceiling is reached. A resource-limited result does not claim that unexamined content was valid.
