# Planned dependency selection

## Selection and directly verified evidence

Planning research was performed 2026-11-17 against architecture `ecfc15dfee316ece10a2d74c1a3f26fabed9d4db`; [the evidence manifest](evidence/planning/dependency-research.json) records versioned PyPI metadata response hashes, immutable distribution URLs, actual downloaded-source SHA-256, upload timestamps, Requires-Python, Requires-Dist, classifiers and license metadata. All selected sdists were actually downloaded and hash-matched. This research is not an installed dependency lock, compatibility execution or clean security scan. I01 MUST resolve full transitive dependencies/platform markers into `uv.lock`, verify artifact timestamps/hashes and actual installation; no product lock or package is created in this planning phase.

Latest stable CPython selected for initial implementation is **3.15.2**, released 2026-10-25. Direct sources checked: [downloads](https://www.python.org/downloads/) SHA-256 `997ca3f4db28a8946a9dd16c236436c8a099306b00b3db54ecad23ab18bca7c0`; [release page](https://www.python.org/downloads/release/python-3152/) SHA-256 `e8461d48af91b6184edc5a1a74c0f4d539ad59887a02036922e40aa59003dc59`; downloaded [source archive](https://www.python.org/ftp/python/3.15.2/Python-3.15.2.tar.xz) SHA-256 `8b5536d280142ecf6cdfe15d12a21ba1c65e300bbf7b28a8d0cdb849575797de`; [v3.15.2 license](https://raw.githubusercontent.com/python/cpython/v3.15.2/LICENSE) SHA-256 `b0e25a78cffb43f4d92de8b61ccfa1f1f98ecbc22330b54b5251e7b6ba010231`. Python's PSF and historical notices MUST be retained where redistribution applies. I01 MUST recheck latest stable at execution; a changed Python selection MUST receive impact analysis and compatible resolution, never a silent downgrade.

All pins below have release files older than conservative cutoff `2026-11-03T00:00:00Z`, 14 days before observation date, and none were yanked at observation. This intentionally conservative research cutoff does not exempt the eventual frozen lock or newly resolved transitive artifacts from the actual per-artifact age check.

| Use | Exact selected pin | Upload date UTC | Requires-Python / license |
| --- | --- | --- | --- |
| Environment/resolver/build frontend | uv 0.13.6 | 2026-10-27 | >=3.8; MIT OR Apache-2.0 |
| Runtime CLI | typer 0.27.3 | 2026-10-06 | >=3.10; MIT |
| Runtime strict DTOs | pydantic 2.14.2 | 2026-10-29 | >=3.10; MIT |
| Workbook generation only | openpyxl 3.1.5 | 2024-06-28 | >=3.8; MIT |
| Runtime registry / denial callback | referencing 0.37.0 | 2025-10-13 | >=3.10; MIT |
| Runtime email syntax only | email-validator 2.3.0 | 2025-08-26 | >=3.8; Unlicense |
| Build backend | hatchling 1.33.0 | 2026-10-28 | >=3.10; MIT |
| Runtime schema validation | jsonschema 4.26.0 | 2026-01-07 | >=3.10; MIT |
| Development graph acceptance | rdflib 7.6.0 | 2026-02-13 | >=3.8.1; BSD-3-Clause |
| Lint/format | ruff 0.17.3 | 2026-10-27 | >=3.7; MIT |
| Type analysis | ty 0.0.95 | 2026-10-29 | >=3.8; MIT |
| Test runner | pytest 9.2.0 | 2026-10-27 | >=3.10; MIT |
| Statement/branch coverage | coverage 7.17.0 | 2026-10-22 | >=3.11; Apache-2.0 |
| Development build cross-check | build 1.6.1 | 2026-09-10 | >=3.10; MIT |
| Advisory scanner | pip-audit 2.10.1 | 2026-06-10 | >=3.10; Apache-2.0 |
| CycloneDX generator | cyclonedx-bom 7.6.0 | 2026-10-28 | >=3.9,<4; Apache-2.0 |
| Artifact metadata/version inspection | packaging 26.3 | 2026-08-04 | >=3.9; Apache-2.0 OR BSD-2-Clause |

All Requires-Python ranges admit 3.15.2. Explicit 3.15 classifiers exist for uv/Pydantic/Ruff/ty/pytest/coverage/build/CycloneDX/packaging. Typer/openpyxl/jsonschema/rdflib/pip-audit lack that classifier: compatibility remains an I01 actual execution gate, not a proven support claim. Required Pydantic core 2.50.2 and current rpds-py 2026.9.1 publish cp315 wheels at observation; actual platform-specific transitive wheel selection remains pending. The openpyxl reader MUST NOT process untrusted submissions; safe intake MUST use architecture's bounded ZIP/hardened Expat path. stdlib `pyexpat`/`zipfile` versions are bound to selected CPython; unsafe XML hooks and unsupported package parts MUST be refused before content interpretation. RDFLib MUST be used for offline graph acceptance, not a runtime network resolver. It has no inspected deny-network flag: its context loader can call `source_to_json`. I07 MUST construct contexts only locally, recursively reject remote context strings, `@import` and remote nested/scoped contexts, parse JSON using `data=` rather than URL/location, and prove refusal with network denied. Ordinary vocabulary IRIs MUST remain inert. The verified source `context.py` SHA-256 is `f1ac5b9c822dcec118149bba190fe5aa3e4dbb8533da1f54a53f1d0101f37b0a`. Referencing Registry MUST use an explicit denial callback raising NoSuchResource; verified `_core.py` SHA-256 is `d923c67da4efcc0dec46a6e3ff8476c02fbe7e25e8942515a4b14b249eb3759f`. Pydantic EmailStr uses `check_deliverability=False`, verified `networks.py` SHA-256 `6085ec09a594a84ec533000ee6e8d85c294c2f123728fe9ed8c755c273f95f8b`; I02 MUST retain no-DNS tests.

License metadata for ty and pip-audit was empty; actual downloaded sdists' LICENSE files establish MIT and Apache-2.0 respectively. I01/I10 MUST inspect all resolved transitive notices and wheel/source provenance, distinguish unknowns from verified licenses, include mandatory notices and stop incompatible redistribution. Proprietary application licensing MUST remain separate from permissive dependency/resource notices. Exact resource closure/license pins remain authoritative in [architecture standards](architecture-standards.md#resource-identities-and-offline-resolution); I07 MUST package their bytes unchanged and compare installed artifacts against the manifest.

## Configuration and tool verification

Directly inspected [uv 0.13.6 schema](https://raw.githubusercontent.com/astral-sh/uv/0.13.6/uv.schema.json), SHA-256 `a8370623a465aca2668ca3973552a48f1952dfbbbbf1af82b5c54f45481e6d4a`, supports friendly-duration `exclude-newer` and per-artifact filtering. I01 MUST set `[tool.uv] exclude-newer = "14 days"` and explicit direct/dev/build pins, approved PyPI source, commit the lock and use frozen sync. A lock created with a different cutoff/source MUST be rejected. uv itself MUST be bootstrapped from an eligible pinned verified artifact, not an unversioned curl installer. Development/build tools MUST obey the same age policy.

Directly inspected [ty 0.0.95 configuration](https://raw.githubusercontent.com/astral-sh/ty/0.0.95/docs/reference/configuration.md), SHA-256 `ad28834d6631604fefeb019159adb833c77b034dd403efce4433cdeee0328050`, supports `[tool.ty.rules] all = "error"`. I01 MUST verify actual diagnostic inventory/help, set this without baselines and make warnings/errors fail. Ruff MUST select `ALL` plus formatter checks; I01 MUST verify the pinned rule/formatter conflict documentation and record only actual mutually exclusive or formatter-conflicting narrow ignores with reason and compensation. Planned command flags MUST be validated against installed pinned help; a spelling correction MUST NOT weaken all-rule requirements.

No dependency metadata query establishes vulnerability safety. I10/R MUST execute the [delivery security gate](delivery-plan.md#release-security-sbom-and-support-evidence), including advisory freshness and known exploitation independent of severity. No product runtime MUST require feeds or contact a reference URL.

## Reproduction and resolution gate

The following standard-library research procedure identifies an exact metadata/artifact pair; rerunning a mutable metadata endpoint MUST compare version, timestamps and returned artifact hash rather than assume response-byte stability. All output MUST remain neutral package facts.

```python
import hashlib, json, urllib.request
name, version = "pydantic", "2.14.2"
raw = urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json").read()
metadata = json.loads(raw)
artifact = next(x for x in metadata["urls"] if x["packagetype"] == "sdist")
payload = urllib.request.urlopen(artifact["url"]).read()
assert hashlib.sha256(payload).hexdigest() == artifact["digests"]["sha256"]
print(hashlib.sha256(raw).hexdigest(), artifact["upload_time_iso_8601"])
```

I01 MUST record resolved interpreter/tool/platform compatibility, full transitive lock/source/upload/hash evidence and narrow conflicts. Missing wheels/tool compatibility MUST trigger concrete investigation and an agent plan correction; architectural/acceptance impact MUST return to the earliest affected gate. It MUST NOT be papered over by reducing the latest-stable requirement. Actual lock, platform installations, security scans and release assets remain PENDING.
