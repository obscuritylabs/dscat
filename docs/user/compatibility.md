# Compatibility

DSCat 0.1.0 is a command-line application for workbook intake, canonical catalog storage and local standards exports. Python 3.15.2 and uv 0.13.6 are the selected verification toolchain. A public Python API is not provided; internal modules and development scripts can change.

## Versioned formats

| Surface | Initial version or behavior |
| --- | --- |
| Application | 0.1.0, proprietary license |
| Workbook schema and kind markers | Schema `2.0`, kind `collection-intake` |
| Explicit TOML configuration | `schema_version = "1.0"` |
| Canonical catalog, canonical manifests and dataset entries | `1.1` for new collection registrations; genuine `1.0` retained on load/save |
| Configuration, structured command reports and public projection manifests | Schema `1.0` |
| DCAT-US export | 3.0, JSON-LD with bundled offline context and schema closure |
| ODCS export | 3.2.0 JSON with bundled offline schema closure |
| Public Python API | None |

Unsupported versions and populated unknown fields are refused. Existing canonical `1.0` bundles retain their original required description/contact facts and closed vocabulary. Loading does not rewrite source generations or upgrade their version. Canonical `1.1` permits absent descriptions/contacts and preserves the new typed registration answers; old software cannot read it. Adding registration fields to an old catalog requires an explicit in-memory version change before saving to a separately selected destination. The undistributed workbook `1.0` is not a compatibility obligation; any retained parser fixtures are regression materials rather than the current template. Keep complete canonical bundles and original intake files when upgrading. Application version, workbook schema, dataset version and contract version are distinct; one does not supply another.

## Command behavior

`dscat template` creates the collection-first workbook; `--examples` seeds fixed synthetic records. `dscat validate` reports validity and target readiness. `dscat build` creates an internal canonical bundle and requested ready exports. `dscat export` derives exports from a saved canonical bundle without the original workbooks. Use `--help` on the installed command for its exact options; examples and replacement/recovery procedures are in the [intake](intake.md) and [storage](storage.md) guides.

| Exit status | Meaning |
| --- | --- |
| 0 | Requested operation succeeded |
| 1 | Intake or target/publication eligibility did not satisfy the requested operation; an internal build can still contain canonical facts and ready requested targets |
| 2 | Invalid invocation, configuration or unsupported version |
| 3 | Operational failure, including refused replacement, unavailable resource protection or unsafe output paths |
| 4 | Unexpected internal failure |
| 130 | Interrupted operation |

Use `--format json` for a single structured result on validation, build and export. Check its exit code, diagnostics and receipt together. A separate private report does not establish publication success. `--no-color` keeps terminal output plain. Generated output replacement requires the command's explicit `--replace` option; validation reports instead need a new destination.

## Platforms and storage

The implementation is OS agnostic, with macOS as the primary target. Required first-release acceptance includes native macOS installation and workflow. Their actual evidence and remaining dependencies are tracked in [macOS readiness](../planning-gates.md#macos-primary-readiness). Windows and Linux checks support claims only for environments actually verified; absence of Windows access does not block the macOS-first release.

Publication needs a supported local filesystem and refuses unknown filesystems, network shares, linked paths and overlapping inputs/outputs. The [storage guide](storage.md#replace-a-catalog) lists filesystem support and atomic-visibility limits. Resource-limited results do not claim that unexamined inputs were valid.

Workbook generation can use different XML serializers when optional development dependencies are installed. Namespace prefixes and empty-tag spelling can differ while workbook contents remain equivalent. Repeated generation in the same pinned environment remains byte deterministic. Canonical catalog and export identities follow their normalized content and selected schema/mapping versions.

Before 1.0, breaking changes can occur with documented impacts. From 1.0 onward, supported compatibility changes follow major-version policy. Future standards, migrations and database adapters are outside this release's compatibility promise.
