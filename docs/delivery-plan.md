# Local verification and release delivery

## Confirmed constraints

The following constraints are human-derived facts from DEC-018; the detailed implementation MUST remain subject to the existing planning gates.

- Local testing and verification MUST be the primary quality gate; GitHub Actions MUST remain minimal and supplementary.
- GitHub Releases MUST provide installable software. Release publication MUST retain explicit human authorization and private repository visibility.
- Security, coverage, typing, workbook compatibility, and schema-conformance requirements MUST remain mandatory regardless of where checks run.

## Proposed workflow

The following workflow is an LLM proposal and MUST NOT be treated as an approved implementation plan.

- Development SHOULD expose a reproducible local verification command using pinned tools and the committed uv lockfile. The full applicable suite MUST include Ruff checks and formatting, ty, unit/integration/CLI tests, statement/branch coverage, workbook compatibility, hostile-input tests, DCAT-US/ODCS conformance, dependency scanning, and package checks.
- A report MUST identify the exact source commit, dirty-tree state, Python/platform and tool versions, lockfile digest, commands, results, coverage exceptions, vulnerability dispositions, and remaining platform/manual checks. Failed, skipped, or unavailable checks MUST remain explicit. Evidence SHOULD be concise and tracked with the RTM rather than dumping sensitive logs into Git.
- Initial CI SHOULD use one short Linux job on relevant pull-request changes, reusing local commands for fast static checks and a small CLI smoke test once implementation exists. It SHOULD cancel superseded runs and skip irrelevant documentation-only changes. Selected required checks MUST still report a terminal result for every protected PR; path filtering MUST NOT leave a required context permanently pending.
- Broad CI matrices, scheduled full-suite runs, duplicated artifact builds, and automatic release publication SHOULD be omitted. Additional Actions usage MUST require a concrete justification and human agreement. Local platform coverage MUST NOT be claimed without actual evidence.
- Release preparation SHOULD build a wheel and source distribution locally from a clean, final source revision, test those exact artifacts in a clean environment, inspect proprietary license metadata, and execute the manual verification walkthrough. Release preparation MUST verify supported schemas and offline runtime behavior; dependency installation MAY access PyPI.
- The release candidate SHOULD include wheel, source distribution, SHA-256 checksums, machine-readable SBOM, any justified VEX statements, release notes, workbook compatibility information, and a concise verification report. The manifest MUST bind artifact hashes to the verified source revision. The SBOM MUST describe the distributed artifacts and resolved dependencies.
- The human MUST authorize the version, source revision, and exact candidate artifact hashes before tagging or publication. Publication SHOULD upload the already verified artifacts directly from the local environment; it MUST NOT silently rebuild or replace the authorized candidate.
- Private GitHub Release installation instructions SHOULD use authenticated asset download followed by uv tool installation of the downloaded wheel. Documentation MUST distinguish online installation from offline runtime, and MUST NOT embed credentials or assume that private asset URLs are anonymously accessible.
- A release smoke check MUST verify downloaded artifact hashes, clean installation, CLI help/version, and a representative workbook-to-export operation without runtime network access. Remote upload/download verification MUST remain distinct from local candidate checks. Failed post-publication checks MUST be reported and handled under the approved release failure procedure.
- Public package-index publication and bundled standalone executables SHOULD remain outside the initial distribution plan unless separately requested. GitHub Releases MUST NOT make this proprietary project public.
