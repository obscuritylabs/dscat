# Release assurance evidence

This compact ledger retains useful implementation security/delivery evidence and missing release observations. The [delivery plan](../../delivery-plan.md#release-security-sbom-and-reporting-evidence) owns the required checks; [planning gates](../../planning-gates.md) owns current authority and readiness. Historical observations below certify only their identified candidate.

## Verified implementation candidate

The last full automated candidate was `c5526f541346ba6c951e7e3816c3483380340904`, tree `14026bae405d40a7062f346f3e2ab6af803fa6a9`. Protected integration at `4a234eeb0e5723b950e5d1f7a4c090418b9f5975` had identical reviewed contents. [PR #52](https://github.com/obscuritylabs/dscat/pull/52) records 1,288 passing tests, three platform-specific skips, 100% of 6,100 statements/1,938 branches, static/document checks, hosted Verify, archive checks, installed offline acceptance and advisory collection. The [independent review record](https://github.com/obscuritylabs/dscat/pull/52#issuecomment-7032515329) separates fresh correction checks from retained earlier evidence.

That candidate's wheel SHA-256 was `e3aecab5767efec843ce4a8dbbbdd0de37e72681f5eba4ed0c3c1b49d62d0025`; its source archive SHA-256 was `7cd3fd39030c4ffc410df0a8f74428068e04b055c3972169e54fbe0d5aaa8f58`. These identify that candidate, not a published release or a source archive containing later documentation. Final assembly needs its own main/source/artifact bindings. Recorded advisory observations are time-limited; their use follows the delivery plan's freshness and release-block rules.

## Security evidence and remaining work

| Area | Available implementation evidence | Remaining release evidence |
| --- | --- | --- |
| Requirements and review | Approved requirements, threat model, RTM and independent reviews at the historical candidates; PR #52 corrected/rechecked security defects | Confirm final candidate applicability, affected review and unresolved acceptance dependencies |
| Dependencies and advisories | [Toolchain audit](i01-toolchain.json), [I10 additions](i10-dependencies.json), frozen lock, approved sources/age/hash/notices and complete runtime/development advisory and KEV collection in PR #52 | Bind final tools/lock to assembly; fresh feed assessment and finding dispositions under the separate advisory/exploitation gates |
| Source and package integrity | PR #52 source/wheel/sdist/lock/SBOM/checksum bindings, archive integrity/license tests, clean source rebuild and hash-enforced installation | Final source/artifact identities, privacy/license inspection, actual published asset list and authenticated downloaded-asset verification |
| Runtime safety and offline acceptance | Typed boundaries, bounded ZIP/XML/native guards, safe paths, no formula evaluation, closed public projections; hostile/preservation tests, active socket-denial probe and installed offline workflow in PR #52 | Final candidate applicability, native workflow, reproducible positive/negative walkthrough and independent acceptance |
| Repository delivery | Protected reviewed integration of PR #52 and current [repository policy](../../repository-policy.md) | Applicable source/tag/publication identity and protected integration verification |
| Security reporting | [SECURITY.md](../../../SECURITY.md) documents the route and brief assessment/remediation/coordinated disclosure process | Pre-release enabled/link check recorded as `confidential_reporting` evidence against the exact candidate; current disabled observation follows planning gates |

VEX remains conditional on actual findings and supported artifact-specific non-applicability evidence; no VEX exemption was needed for the historical zero-finding scans. Any new finding requires the applicable advisory/exploitation disposition.

## Current release limits

Available historical evidence supports the identified implementation/tooling candidate. It does not establish current reporting enablement, final release acceptance, publication or downloaded-artifact verification. Required remaining release checks MUST block publication until satisfied; no current or prior evidence waives them.
