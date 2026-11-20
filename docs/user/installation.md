# Installing DSCat

Use a candidate or release whose verification report identifies the exact source revision, wheel, source archive and checksums. Current readiness is recorded in the [release gate](../planning-gates.md); these instructions do not establish release acceptance. DSCat is proprietary software; the included LICENSE applies.

The selected toolchain is Python 3.15.2 and uv 0.13.6. macOS is the primary target. See [compatibility](compatibility.md) for supported formats, portability and verification limits.

## Obtain and check the assets

When the verified release is available, download its complete asset set into a new directory using an authorized GitHub session:

```sh
gh release download v0.1.0 --repo obscuritylabs/dscat --dir dscat-release
cd dscat-release
```

Keep the wheel, `runtime-requirements.txt`, `application-requirements.txt` and `SHA256SUMS` together. On macOS, check every listed asset:

```sh
shasum -a 256 -c SHA256SUMS
```

On Linux, use `sha256sum -c SHA256SUMS`. On Windows, compare the SHA-256 from PowerShell `Get-FileHash -Algorithm SHA256 <filename>` against each entry. Stop if any file is missing or differs. A checksum establishes byte identity; obtain the checksum file from the same authorized release source and confirm the verification report's source/artifact bindings.

## Install with dependency hash checks

Run these commands from the downloaded asset directory, using a fresh environment name:

```sh
uv --no-config venv --python 3.15.2 dscat-env
uv --no-config pip install --python dscat-env --require-hashes --only-binary :all: --default-index https://pypi.org/simple -r runtime-requirements.txt -r application-requirements.txt
```

The requirement files pin the application and runtime dependency versions and accepted archive hashes. Installation refuses an unexpected archive hash or a missing compatible wheel. It does not build dependency source archives. Internet access is needed for dependencies unless their verified wheels are already cached; add `--offline` to the install command when using that cache.

Activate the environment on macOS or Linux:

```sh
source dscat-env/bin/activate
```

On Windows PowerShell, activate with `dscat-env\Scripts\Activate.ps1`. Then check the installed command:

```sh
dscat --version
dscat --no-color --help
```

The version is `0.1.0`; help includes the proprietary notice. Continue with the [intake guide](intake.md) and [catalog/export guide](storage.md). Installed template generation, validation, persistence and export operate offline; descriptive references are not fetched.

## Tool installation alternative

A verified wheel can also be installed as a uv tool:

```sh
uv --no-config tool install --python 3.15.2 --constraints runtime-requirements.txt --no-build ./dscat-0.1.0-py3-none-any.whl
```

The constraints select the tested runtime versions. This command does not enforce the hashes in the constraints file; use the environment installation above when dependency archive hash enforcement is required. Verify the downloaded wheel and inspect the resulting installed versions against the release inventory. The tool environment is separate from project environments.

To leave an activated environment, run `deactivate`. Preserve catalog bundles separately; uninstalling the package does not migrate or remove them. Do not replace existing application files or catalog data as part of installation recovery. Resolve an installation failure in a fresh disposable environment and retain the previous working installation until verification succeeds.
