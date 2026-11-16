# Local verification and release delivery

## Confirmed constraints

The following constraints are human-derived facts from DEC-018, DEC-019, and DEC-022; the detailed implementation MUST remain subject to the existing planning gates.

- Local testing and verification MUST be the primary quality gate; GitHub Actions MUST remain minimal and supplementary.
- GitHub Releases MUST provide installable software. Release publication MUST retain explicit human authorization and private repository visibility.
- Agents MUST own implementation, local verification, PR review, and merging within approved scope, without routine human PR review. Planning SHOULD resolve critical decisions and release conditions beforehand.
- Security, coverage, typing, workbook compatibility, and schema-conformance requirements MUST remain mandatory regardless of where checks run.
- Every task MUST remain incomplete until all seven stages in the [Definition of done](../AGENTS.md#definition-of-done) have evidence: planning, implementation, tests, local verification, remote-main merge, publication, and verification from the released version. Tasks MAY share a release but MUST NOT close before their release verification. Human approval gates MUST remain in force.

## Portability and installation decision

Per DEC-028, Windows, macOS, and Linux MUST be portability targets using ordinary cross-platform Python tooling, rather than a mandatory verified-platform matrix. Installation MUST use uv tool install with GitHub Release artifacts; private assets MAY require authenticated download first. Specialized installers MUST NOT be required. Reports MUST identify actual verified environments. Excel verification arrangements MUST remain deferred, without implying successful workbook verification or waiving acceptance.

## Proposed workflow

The following workflow is an LLM proposal and MUST NOT be treated as an approved implementation plan.

- Development SHOULD expose a reproducible local verification command using pinned tools and the committed uv lockfile. The full applicable suite MUST include Ruff checks and formatting, ty, unit/integration/CLI tests, statement/branch coverage, workbook compatibility, hostile-input tests, DCAT-US/ODCS conformance, dependency scanning, and package checks.
- A report MUST identify the exact source commit, dirty-tree state, Python/platform and tool versions, lockfile digest, commands, results, coverage exceptions, vulnerability dispositions, and remaining platform/manual checks. Failed, skipped, or unavailable checks MUST remain explicit. Evidence SHOULD be concise and tracked with the RTM rather than dumping sensitive logs into Git.
- Initial CI SHOULD use one short Linux job on relevant pull-request changes, reusing local commands for fast static checks and a small CLI smoke test once implementation exists. It SHOULD cancel superseded runs and skip irrelevant documentation-only changes. Selected required checks MUST still report a terminal result for every protected PR; path filtering MUST NOT leave a required context permanently pending.
- Broad CI matrices, scheduled full-suite runs, duplicated artifact builds, and automatic release publication SHOULD be omitted. Additional Actions usage MUST require a concrete justification and human agreement. Local platform coverage MUST NOT be claimed without actual evidence.
- Before release preparation, agents MUST verify the task change is merged into origin/main and identify the final main revision. Release preparation SHOULD build a wheel and source distribution locally from that clean, final source revision, test those exact artifacts in a clean environment, inspect proprietary license metadata, and execute the manual verification walkthrough. Release preparation MUST verify supported schemas and offline runtime behavior; dependency installation MAY access PyPI.
- The release candidate SHOULD include wheel, source distribution, SHA-256 checksums, machine-readable SBOM, any justified VEX statements, release notes, workbook compatibility information, and a concise verification report. The manifest MUST bind artifact hashes to the verified source revision. The SBOM MUST describe the distributed artifacts and resolved dependencies.
- Release authorization MUST be explicit before tagging or publication. It MAY be granted during planning for releases meeting agreed scope, version, verification, and security conditions; absent that delegation, human authorization MUST identify the concrete candidate. Agents MUST record the final source revision and hashes and verify they satisfy the authorization. Publication SHOULD upload the already verified artifacts directly from the local environment; it MUST NOT silently rebuild or replace the authorized candidate.
- Private GitHub Release installation instructions SHOULD use authenticated asset download followed by uv tool installation of the downloaded wheel. Documentation MUST distinguish online installation from offline runtime, and MUST NOT embed credentials or assume that private asset URLs are anonymously accessible.
- Post-publication verification MUST download assets from the actual GitHub Release, verify artifact hashes, install in a clean environment, check CLI help/version, and exercise the task-specific acceptance scenarios plus a representative workbook-to-export operation without runtime network access. Documentation changes MUST be verified in the released source archive. A pre-upload local build, draft release, or working checkout MUST NOT substitute for the released version. Remote upload/download verification MUST remain distinct from local candidate checks. Failed post-publication checks MUST be reported and handled under the approved release failure procedure.
- Public package-index publication and bundled standalone executables SHOULD remain outside the initial distribution plan unless separately requested. GitHub Releases MUST NOT make this proprietary project public.
