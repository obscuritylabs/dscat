# Local verification and release delivery

## Authority and status

This is the release execution portion of [the implementation plan](implementation-plan.md), agent disposition DEC-047, 2026-11-17, contingent on fresh exact-candidate QA/reconciliation. [Governance](governance.md#local-verification-and-distribution) owns standing DEC-045 delegation and seven-stage completion; [planning gates](planning-gates.md) owns candidate status. No candidate release is currently ready or published. Current work MUST stop after architecture/planning and their protected document integration; the future release tasks below MUST NOT execute in this work boundary.

The [dependency plan](implementation-dependencies.md) owns tool/source/age selection. The [verification inventory and selected arrangements](implementation-verification.md) own behavior/manual/platform acceptance. These are ready execution designs, not observed product conformance. Missing actual platform/Excel/NVDA evidence, reporting access, advisory status or artifact identities MUST block applicable release acceptance. Earlier DEC-028 deferred verification is resolved into the owned I11 tasks, without asserting their completion.

## Local gate and supplementary CI

I10 MUST provide `uv run --frozen python scripts/verify.py --full`, using [the explicit local command inventory](implementation-verification.md#planned-verification-commands), with exact source/dirty state, tree, Python/platform/tool versions, lock digest, commands/results, coverage and exceptions, schema resources, vulnerabilities and manual/platform statuses. All implemented acceptance MUST trace to actual tests or walkthrough observations, not only process exit/coverage. Build and artifact acceptance MUST use clean isolated directories and denied runtime networking.

I10 MUST configure one small Linux PR job calling `scripts/verify.py --ci`: frozen sync, Ruff, format, ty and the bounded CLI/package smoke. It MUST report terminal status for every protected PR, including documentation-only changes; cancellation MUST supersede old runs without leaving the required current context pending. Local full checks remain primary. Broad matrices/scheduled scans/redundant release builds and automatic release publication MUST NOT be added without documented need and agent readiness.

## Release security, SBOM and support evidence

R owns candidate assembly and integrity; S independently owns security/licensing applicability; M owns monitored reporting/triage; V owns acceptance evidence. The coordinator MUST assign actual executors and access before I10/I11 execution. P/A dependencies remain explicit hard gates in the verification plan.

| Evidence | Concrete execution task / acceptance |
| --- | --- |
| Dependency and package integrity | I01 locks all runtime/dev/build transitive versions/artifact hashes with eligible upload times and approved sources. I10/V compares frozen environment and built wheel METADATA/RECORD with lock, licenses and third-party resource manifest. R records main revision plus wheel/sdist SHA-256 and checks no secrets/private samples/paths in archives or metadata. |
| SBOM | I10/R uses pinned `cyclonedx-bom` through `cyclonedx-py environment` on a clean runtime-only wheel environment, selecting output CycloneDX **1.6 JSON**. Exact pinned CLI flags MUST be confirmed with `--help` in I10 and recorded in `scripts/release_evidence.py`; missing support MUST require an explicit compatible generator correction. S MUST validate the output against an immutable hash-pinned official CycloneDX 1.6 schema and full offline closure acquired/verified in I10, retaining license notices. Unknown generator defaults MUST NOT establish 1.6 conformance. |
| SBOM reconciliation | R MUST include application identity/version, source commit, wheel/sdist hashes, generator/version, component names/versions/purls/hash/provenance/licenses where available and complete runtime dependency relationships. Reconcile installed `importlib.metadata` distributions, wheel Requires-Dist including platform markers and lock; every extra/missing/unknown component/identity/license/provenance MUST be disclosed and resolved or specifically assessed, never hidden. Separate build/dev inventory MUST not masquerade as runtime. Synthetic negative fixtures MUST reject omitted runtime deps/relations/wrong artifact binding. |
| Advisories and exploitation | S MUST run pinned pip-audit against exact locked runtime and build/dev environments, capturing JSON and advisory sources/times; supplement package advisories with current OSV/PyPA advisory/CVE severity sources and CISA Known Exploited Vulnerabilities catalog matching affected dependencies/CVEs. Public feed references MUST remain generic technical sources. Capture retrieval SHA-256/time and matching/disposition, not private data. Feed evidence MUST be at most 24h old at readiness AND publication; unavailable/stale/unknown status or unscored applicability MUST block release readiness. Age cutoff is not a security scan. |
| Findings | Applicable High/Critical or known-exploited findings at ANY severity MUST block release. S MAY establish non-applicability only from artifact-specific affected-version/execution-path evidence; optional VEX MUST bind affected hashes and precise status/justification. Medium/Low MUST have tracked remediation/revisit; missing severity requires assessment. I10 MUST test exploited Low/unscored, stale feed, missing severity and non-applicability rejection paths. Runtime MUST not depend on live feeds. |
| Reporting route and support | M MUST verify authenticated private-repository issues are enabled and accessible using the actual repository API and assigned maintainer-role access, record a monitored role and test receipt. SECURITY.md MUST state collaborators can read issues; it MUST NOT claim maintainer-only/anonymous GitHub private vulnerability reporting. I10 MUST publish route/owner, synthetic-only report instructions, five-business-day acknowledgment/ten-business-day triage targets, latest-release-only support until successor and explicit end-of-support communication. Unavailable route/owner MUST block release and receive a concrete alternative through affected design/plan gates. |
| Triage rehearsal | M/S MUST create an authorized synthetic security-triage issue in the private repository during I10/I11, acknowledge, assess affected versions/artifacts, severity/exploitation/applicability, assign remediation/regression/root cause, decide release/disclosure and close as synthetic rehearsal with evidence. No real vulnerability/secret payload. Coordinated disclosure MUST follow fix or recorded risk decision; this plan MUST NOT authorize unrelated external messaging or automatic public disclosure. Released-source verification MUST inspect SECURITY.md and CLI/docs pointers. |

SSDF final 1.1 practice evidence MUST use the architecture's practice definitions and the following owners/artifacts; no certification is claimed. I10 MUST maintain a compact actual evidence ledger, not an unbounded execution log. Practice/task nonapplicability MUST state rationale, affected scope and revisit trigger.

| Practices | Owner / concrete evidence |
| --- | --- |
| PO.1, PO.4 | S/V: approved requirements, DEC-046 threat model, B01–B13 acceptance and hard blockers |
| PO.2 | Coordinator/M: fresh role handoffs, verifier separation, actual monitored triage ownership |
| PO.3 | I01/I10: eligible pins, lock/tool evidence and local verification commands |
| PO.5 | I/R: isolated environments, repository/release access checks and staged/built secret exclusion |
| PS.1 | Integration/S: current repository-policy API evidence, protected reviewed PR and verified main |
| PS.2, PS.3 | R/V: source/wheel/sdist/checksum/SBOM bindings, authenticated downloads and retained released evidence |
| PW.1, PW.2 | S: exact architecture/plan reviews, threats, offline closure and closed public projection |
| PW.4 | I01/S: approved package/resource sources, age/hash/lock/notices and fresh advisory dispositions |
| PW.5 | I/V: strict DTOs, bounded parsing/guards, path/formula/privacy behavior B01–B11 |
| PW.6 | I10/R: pinned build configuration, clean build/source inspection/frozen installation |
| PW.7 | V/S: Ruff ALL/ty error evidence and fresh scope/privacy/security review |
| PW.8 | V: business-rule/hostile/failure-preservation tests and platform/manual acceptance |
| PW.9 | V/P: denied-network runtime, safe defaults/replacement and fail-closed public/export guards |
| RV.1 | M/S: verified reporting access, synthetic receipt and current advisory/exploitation assessment |
| RV.2 | M/S/R: applicability/remediation/disclosure decisions, VEX where justified and release blocks |
| RV.3 | M/I/V: rehearsal root cause, regression and systemic-control correction/reverification |

## Candidate assembly and publication

After I11 passes, integration MUST verify the final clean change on origin/main through protected PRs and record the exact main commit. R MUST build wheel/sdist once locally from that source using eligible pinned tools and frozen build constraints; `uv build --no-sources` MUST be supplemented with recorded age-constrained build-environment resolution, not assume isolated backend dependencies inherit project lock. R MUST inspect sdist rebuilding in a clean environment and wheel installation. Original verified artifacts MUST be retained; publication MUST upload those bytes without rebuilding.

The candidate MUST contain `dscat-0.1.0-py3-none-any.whl` (or actual compatible wheel tag), `dscat-0.1.0.tar.gz`, `SHA256SUMS`, CycloneDX1.6 `sbom.cdx.json`, separate build/dev inventory, VEX if applicable, source/artifact-binding manifest, neutral release notes, compatibility/support notices, concise verification report and the executed manual walkthrough. Filenames MUST reflect actual build output. Proprietary LICENSE/package/help and all required third-party notices MUST be verified in source/wheel/sdist. Authenticated private-release download/installation instructions MUST avoid credentials and public anonymous-URL assumptions; no public PyPI or visibility change is authorized.

R MUST record exact main/hash/check identities, versions/project scope and explicit exercise of DEC-045 standing delegation before tagging/publishing. Failed/skipped/stale security, licensing, schema, privacy, platform/desktop or installation checks MUST block that disposition. No further human release approval MUST be requested. R MUST verify remote-main/tag/artifact identities and published release asset list after upload.

## Downloaded-artifact verification and failures

A distinct fresh post-release V MUST use `gh release download v0.1.0 --repo obscuritylabs/dscat --dir <empty-disposable-directory>` with authorized authentication, check all published SHA-256 values/source bindings, install downloaded wheel with `uv tool install --python 3.15.2 <downloaded-wheel>`, verify version/help/notices and execute applicable accepted scenarios plus minimum/detail/reload/both-export offline smoke outside the checkout. Actual filenames, environment and fixture hashes MUST replace placeholders in evidence. Downloaded sdist MUST contain approved planning/source/docs/notices and build/install successfully under frozen eligible constraints. Successful pre-upload testing MUST NOT stand for this stage. Every task/RTM ledger MUST remain incomplete until its downloaded verification passes.

Candidate failure MUST stop publication; normal implementation/fresh verification/PR correction, changed-artifact rebuild and full release-gate recheck MUST precede another readiness disposition. Hash-identical downloads MAY be retried after confirming expected identity. Post-publication failure MUST keep tasks incomplete and promptly notify the human of affected version/assets and safe-use assessment. Assets MUST NOT be silently replaced, versions reused, releases/tags deleted or stored data rolled back. Corrected content MUST receive a new verified versioned release under standing delegation; destructive withdrawal requires its separate explicit authorization. Evidence MUST distinguish the failed release from the correction.
