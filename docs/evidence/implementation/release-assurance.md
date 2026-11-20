# Release assurance evidence

This is the compact implementation evidence ledger for the selected [SSDF 1.1 practices](../../architecture-assurance.md#ssdf-and-reportingsupport-design). It records available evidence and missing release observations; it is not a certification or a completed release assessment. Practice definitions and assigned roles remain in the architecture and [delivery plan](../../delivery-plan.md#release-security-sbom-and-support-evidence). Current availability and acceptance decisions remain in [planning gates](../../planning-gates.md).

## Verified implementation candidate

The last full automated candidate was `c5526f541346ba6c951e7e3816c3483380340904`, tree `14026bae405d40a7062f346f3e2ab6af803fa6a9`. Protected integration at `4a234eeb0e5723b950e5d1f7a4c090418b9f5975` had identical reviewed contents. [PR #52](https://github.com/obscuritylabs/dscat/pull/52) records 1,288 passing tests, three platform-specific skips, 100% of 6,100 statements/1,938 branches, static/document checks, hosted Verify, archive checks, installed offline acceptance and advisory collection. The [independent review record](https://github.com/obscuritylabs/dscat/pull/52#issuecomment-7032515329) separates fresh correction checks from retained earlier evidence.

That candidate's wheel SHA-256 was `e3aecab5767efec843ce4a8dbbbdd0de37e72681f5eba4ed0c3c1b49d62d0025`; its source archive SHA-256 was `7cd3fd39030c4ffc410df0a8f74428068e04b055c3972169e54fbe0d5aaa8f58`. These identify that candidate, not a published release or a source archive containing later documentation. Final assembly needs its own main/source/artifact bindings. Recorded advisory observations are time-limited; their use follows the delivery plan's freshness and release-block rules.

## Practice evidence and remaining work

| Practice / owner | Available implementation evidence | Remaining release evidence |
| --- | --- | --- |
| PO.1 / S,V | Approved [requirements](../../requirements.md), threat model and [RTM](../../rtm.md); retained architecture/planning readiness | Confirm final candidate applicability and unresolved acceptance dependencies |
| PO.2 / coordinator,M | Fresh independent architecture/implementation reviews and scoped handoffs; [PR #52 review](https://github.com/obscuritylabs/dscat/pull/52#issuecomment-7032515329) | Actual monitored maintainer/triage executor, access and notification responsibility remain unverified |
| PO.3 / I,R | [Toolchain audit](i01-toolchain.json), [I10 additions](i10-dependencies.json), frozen lock and implemented verification entrypoint | Bind final tool/version/lock observations to release assembly |
| PO.4 / S,V | B01–B13 acceptance inventory, typed release blockers and positive/negative evidence tests in PR #52 | Manual walkthrough/operator observations and final independent acceptance |
| PO.5 / I,R | Owned external build/log directories, clean runtime installation, active network refusal and source/archive privacy inspection in PR #52 | Final build/release access and proposed asset privacy check |
| PS.1 / integration,S | Protected reviewed integration of PR #52; current [repository policy](../../repository-policy.md) | Recheck applicable source/tag/publication identity; current protection is retained without required-status enforcement |
| PS.2 / R,V | Exact source/wheel/sdist/lock/SBOM/checksum bindings and archive integrity tests | Final candidate identities and authenticated retrieval of actual published assets |
| PS.3 / R,V | Candidate evidence and immutable source/review references retained in PR #52 | Published artifact retention, actual asset list, checksums/SBOM and post-publication evidence |
| PW.1 / S | Approved threat model, offline schema/context closure, closed public projections; PRs [#47](https://github.com/obscuritylabs/dscat/pull/47), [#48](https://github.com/obscuritylabs/dscat/pull/48), [#50](https://github.com/obscuritylabs/dscat/pull/50) | Confirm unchanged design applicability or review affected final changes |
| PW.2 / S | Fresh exact-candidate design/security dispositions and corrected I10 independent review | Final candidate assessment, with prior results scoped to unchanged content |
| PW.4 / I,S | Approved package/resource sources, age/hash/lock/notices, complete runtime/development advisory and KEV collection in PR #52 | Fresh final feed assessment and explicit disposition of any new finding |
| PW.5 / I,V | Typed input/output, bounded ZIP/XML/native guards, safe paths, no input-formula evaluation and public eligibility controls; full candidate tests | Final source/artifact applicability and manual walkthrough correction observations |
| PW.6 / I,R | Pinned build frontend/backend, wheel built from inspected sdist, full source/METADATA/RECORD/license comparisons, hash-enforced clean runtime install | Final clean source rebuild/assembly and retained upload bytes |
| PW.7 / V,S | Ruff ALL/format and ty passed; fresh independent scope/privacy/security review passed for c5526f5 | Affected final diff/privacy checks and final independent acceptance |
| PW.8 / V | Hostile-boundary, business-rule, preservation/retry and native macOS automated tests; frozen walkthrough fixtures | Final candidate walkthrough evidence remains pending |
| PW.9 / V,P | Active socket-denial probe and zero workflow network attempts; explicit replacement, saved-catalog reload and fail-closed public guards | Representative offline verification of final installed and actual downloaded release artifacts |
| RV.1 / M,S | Complete engineering advisory/exploitation collection and case-normalized CVE matching | Enabled confidential route, real monitoring/access, synthetic incoming notification/receipt and acknowledgment |
| RV.2 / M,S,R | Assessed severity/applicability/artifact bindings, VEX-shape validation, any-severity exploitation blocks and remediation/revisit requirements implemented | Actual synthetic triage, artifact assessment, remediation/disclosure decisions; VEX only if justified by a final finding |
| RV.3 / M,I,V | I10 review reproduced license-substitution and CVE-case defects; corrections and independently rechecked regressions are recorded in PR #52 | Operational rehearsal root cause, regression/systemic-control disposition and explicit unpublished closure |

No selected practice is declared inapplicable. VEX emission is conditional on actual findings and supported non-applicability evidence; no VEX exemption was needed for the recorded zero-finding package scans. Any new finding reopens that assessment. A synthetic operational rehearsal has not been performed, and engineering regression evidence does not stand for it.

## Current release limits

The available evidence supports verified implementation and tooling integration. It does not establish a monitored confidential reporting service, final candidate release acceptance, publication or actual downloaded-artifact verification. Support/reporting instructions that claim an available route remain dependent on verified setup and receipt/triage evidence. No prior or current evidence grants publication while required release checks are missing.
