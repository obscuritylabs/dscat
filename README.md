# DSCat

DSCat (Dataset Catalog) turns Excel metadata workbooks into a validated local
catalog and standards-based exports. It generates intake templates, checks
completed workbooks, saves canonical JSON, and exports DCAT-US 3.0 JSON-LD and
ODCS 3.2.0 JSON. Runtime processing works offline.

The current development version is 0.1.0. Release acceptance is still pending;
see the [current status](docs/planning-gates.md#implementation-execution).
macOS is the primary target. DSCat is proprietary software; see [LICENSE](LICENSE).

## Install from source

Use Python 3.15.2 and uv 0.13.6. From a checkout of this repository:

```sh
uv sync --frozen --no-dev
uv run --frozen --no-dev dscat --version
```

The first installation needs internet access or cached dependencies. Prefix the
commands below with `uv run --frozen --no-dev` when using the checkout, or activate
the environment first (`source .venv/bin/activate` on macOS/Linux).

For verified wheel installation and dependency hash checks, see the
[installation guide](docs/user/installation.md).

## Usage

Generate a blank intake workbook:

```sh
dscat template --output intake.xlsx
```

Open it in Excel, read **Instructions**, and enter one dataset per row on
**Datasets**. The required columns are `id`, `title`, `description`, and
`core_party` (a contact or owner label). **Fields** and **Details_Quality** capture
optional metadata. Save the completed workbook before running:

```sh
dscat validate intake.xlsx
dscat build intake.xlsx --output catalog --format json
```

Build saves a canonical catalog bundle. Export from that saved bundle without
needing the original workbook:

```sh
dscat export catalog --output exported --target dcat-us-3 --target odcs-3.2 --config settings.toml
```

`settings.toml` is an explicitly supplied, schema-versioned export configuration.
Export readiness also needs target-specific facts: DCAT-US needs catalog and
dataset identities and a resolved contact/email; ODCS needs a contract identity
or namespace rule and a contract version. The four intake columns alone do not
guarantee export readiness. See the [intake guide](docs/user/intake.md) and
[storage/export guide](docs/user/storage.md) for configuration and readiness rules.

Use a fresh output path for each operation, or explicitly pass `--replace` where
supported. Keep input files and output directories separate. Run `dscat --help`
or `dscat <command> --help` for options. Add `--format json` to validation, build,
or export for structured results.

See [compatibility](docs/user/compatibility.md) for formats, exit codes and
platform limits, and the [documentation index](docs/index.md) for further detail.
