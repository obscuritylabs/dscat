# Local Codex usage refresh

`codex_refresh.py` reads one computer's local Codex history and writes a private
accounting snapshot. It uses only the Python standard library. Each computer
runs it against its own history; it does not send or publish data.

Run its synthetic verification from the repository root:

```sh
python3 -m unittest discover -s tools/local-usage/tests -v
```

The source directory, exact project path, output directory, phase map, and rate
file are explicit command arguments. Keep the output and maps in a private
directory outside Git checkouts. Do not commit generated snapshots or personal
mapping/rate files.

## Run

From the repository root, set `CODEX_HISTORY` to the local history directory
and `PRIVATE` to an absolute private directory outside every Git checkout. For
example, replace these placeholders with paths on the current computer:

```sh
CODEX_HISTORY="/absolute/path/to/codex-history"
PRIVATE="/absolute/path/to/private-usage"
```

Create the empty map/rates files and restrict the private directory:

```sh
mkdir -m 700 -p "$PRIVATE"
if [ ! -e "$PRIVATE/phase-map.json" ]; then
  cp -n tools/local-usage/templates/phase-map.json "$PRIVATE/phase-map.json"
  chmod 600 "$PRIVATE/phase-map.json"
fi
if [ ! -e "$PRIVATE/prices.json" ]; then
  cp -n tools/local-usage/templates/prices.json "$PRIVATE/prices.json"
  chmod 600 "$PRIVATE/prices.json"
fi
```

This leaves existing private files and their permissions unchanged. If you use
an existing directory, ensure that the directory and files remain accessible
only to you.

Then run with the local Codex history root and the exact project path recorded
in its session metadata:

```sh
python3 tools/local-usage/codex_refresh.py \
  --source-root "$CODEX_HISTORY" \
  --project-root "$PWD" \
  --output "$PRIVATE/accounting" \
  --phase-map "$PRIVATE/phase-map.json" \
  --prices "$PRIVATE/prices.json"
```

The `--project-root` value must match the exact project path recorded in the
local history; replace `$PWD` if those paths differ. The script does not guess
paths and refuses a nonexistent source or project directory. Run it again to
create a new immutable snapshot and update the private `current.json` pointer. A refresh lock prevents
concurrent writes; if a process was killed, confirm no refresh is active before
removing `.refresh.lock` from the output directory.

## Interpretation

`current.json` points to the latest snapshot. Its `report.md`, `accounting.json`,
and CSV files contain alternate views of the same local history; do not add
those views together. Token subtotals preserve missing values, cached input is
within input, and reasoning is within output. Recorded duration, interval-derived
duration, and closed interval unions are reported separately. Time also
distinguishes overlapping turns and open turns. Accessible history may be incomplete. Before
interpreting zero counts, verify the configured source directory and inspect
the snapshot's `included_threads`, `discovered_threads`, and diagnostics for
missing or inaccessible inputs.

Prices are optional. The empty template leaves costs unpriced. If rates are
added, provide exact logged model/provider, currency, effective UTC dates,
decimal-string prices, and dated public-source or manual provenance. Results
are estimated API-equivalent usage costs, not invoices or subscription charges;
this script does not calculate account billing or enforce a budget limit.

The phase map accepts opaque local response, turn, or thread IDs. Keep it
private. Unmapped work stays unknown, and inferred phases are low confidence.
The script exports metadata and token counts only; it does not export prompt or
response text. No source paths are written to the accounting outputs.
