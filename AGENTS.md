# Agent instructions

## Authority and statement conventions

- Agents MUST treat approved requirements and planning documents as the source of truth; code MUST conform to them.
- Normative requirements in planning documents and these operating instructions MUST use RFC 2119 keywords (MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, MAY, OPTIONAL), interpreted with RFC 8174 uppercase semantics.
- Agents MUST use fact/assumption and provenance markings sparingly, only in planning documents they maintain and where the distinction helps assess a requirement, decision, assumption, or evidence. Agents SHOULD label a shared section or table once rather than repeat markings on every sentence. Requirements MUST retain stable IDs for traceability; ordinary prose MUST NOT receive IDs merely for uniformity. Human-provided or third-party documents MUST NOT be annotated without an explicit request.
- FACT MUST mean a directly supported claim or recorded instruction, not automatic human approval. TOOL_VERIFIED claims MUST cite the source or command, observation date, and evidence. Approval status MUST be recorded separately from provenance.
- Agents MUST NOT imply human approval from silence, elapsed time, tool success, or their own review. Human verification MUST record a date and evidence or decision reference; approver identity MAY be omitted.
- Tables MAY inherit classification from a labeled parent statement when all rows share it. Mixed classifications MUST be labeled per row. Headings, IDs, paths, commands, and literal schema examples MAY omit normative wording when their governing statement supplies it.
- Agents MUST NOT persist private conversational context, private organizational affiliations, identifying private-context source URLs, or sensitive real-world examples in repository artifacts, Git history, issues, fixtures, or logs. Agents MUST use neutral descriptions and synthetic examples.

- Source code, tests, configuration, package manifests, LICENSE, user-facing documentation, CLI output, and these operating instructions MUST use their conventional formats without planning IDs or fact/provenance annotations. LICENSE MUST use conventional legal prose rather than RFC 2119 formatting. Classification, provenance, and requirements traceability MUST remain in suitable agent-maintained planning documents; agents MUST NOT inject those annotations into ordinary project artifacts.

## Required SDLC and approval gates

- Agents MUST begin work by reading this file and docs/index.md, checking Git status, and inspecting applicable approved requirements and plans.
- Agents MUST interview the human, record decisions, identify assumptions, and maintain concise on-disk planning documents before implementation. All planning MUST remain on disk until an explicit migration to GitHub issues.
- Agents MUST obtain explicit human approval of requirements, then architecture, then an implementation plan before dependent implementation. Agents MAY prepare clearly labeled drafts before approval. Approval MUST identify the document revision or commit.
- Approved work MAY proceed autonomously within scope. Changes affecting approved requirements, architecture, acceptance criteria, or plan MUST receive impact analysis and renewed approval for the affected gates before dependent implementation.
- Agents MUST implement in small verifiable increments, update traceability and documentation with each increment, and complete testing before requesting human review and release authorization.
- Agents MUST provide a written manual verification walkthrough with setup, synthetic inputs, exact commands, expected results, negative cases, and cleanup. Human authorization MUST precede release, tagging, publishing, or distribution as a release.
- Independent reviews SHOULD occur periodically. The human MAY waive or request agent assistance for an independent review. An agent's self-review MUST NOT be represented as independent review or human approval. Waivers MUST be recorded; review waivers MUST NOT imply release authorization or waived security requirements.
- Completion MUST require satisfied acceptance criteria, passing required checks, current documents and RTM, recorded verification evidence, and no unresolved blocking defects. Untested or blocked work MUST be reported explicitly.

## Traceability and change control

- Every feature and NFR MUST trace to a capability in docs/rtm.md. Each RTM row MUST link a stable requirement ID to its source, acceptance criteria, design, implementation, tests, and verification evidence.
- Governance, dependencies, configuration, infrastructure, tooling, documentation, migrations, and tests MUST trace to a supporting capability and requirement. Agents MUST maintain artifact-level mappings and symbol-level mappings where a file spans multiple requirements; line numbers alone MUST NOT be used as durable identifiers.
- Code without an approved RTM justification MUST be removed. Agents MUST first inspect its purpose and dependencies, record the discrepancy and impact, and preserve unrelated human changes. Agents MUST NOT invent a requirement to justify existing code. Removal that changes approved scope MUST pass the affected approval gates.
- RTM fields MAY say PENDING before the corresponding phase; missing implementation or tests MUST NOT be reported as verified. Removed requirements MUST retain a retirement record and impact links; IDs MUST NOT be reused.
- Assumptions affecting correctness, security, interoperability, or acceptance MUST be resolved or explicitly accepted by the human before dependent implementation. Exceptions MUST document scope, reason, risk, expiration/revisit condition, and authorization. The human-delegated coverage exception under Project and engineering constraints MAY be exercised by agents without additional approval; it MUST NOT waive required behavior or security verification.

## Project and engineering constraints

- DSCat (Dataset Catalog) MUST be a uv-managed Python package with a Typer CLI. All structured boundary input and output MUST pass through Pydantic models, including workbook records, exports, configuration, and structured diagnostics. Ordinary CLI help and human-readable rendering MAY be derived from those models.
- DSCat MUST generate Excel workbooks for human completion, validate returned workbooks, and export validated catalog metadata to DCAT-US. The initial release MUST export DCAT-US 3.0 and ODCS; DCAT-US 1.1 SHOULD be supported without blocking release. Exact ODCS version and minimal conforming scope MUST be approved before implementation.
- The project MUST select the latest stable Python at initial implementation and MUST verify dependency/tool compatibility. Agents MUST report incompatibility rather than silently downgrade. Python upgrades thereafter MUST receive impact analysis.
- uv MUST exclude dependency artifacts uploaded less than 14 days before resolution, including development dependencies. The implementation SHOULD use exclude-newer = "14 days" after verifying support in the pinned uv release. Lockfiles MUST be committed and routine verification MUST use frozen synchronization. The age policy MUST NOT be treated as vulnerability protection by itself.
- Ruff MUST enable ALL rules and formatting checks. ty MUST enable all available diagnostics at error severity. Agents MUST verify current configuration syntax and tool support. Mutually exclusive rules and formatter conflicts MUST receive narrow documented resolutions; blanket ignores, diagnostic baselines, and unchecked typing escapes MUST NOT conceal defects.
- All maintained Python code MUST be typed and compliant with the configured checks. The verification plan MUST target 100% statement and branch coverage and behavior-based acceptance tests. Agents MAY make narrow coverage exceptions with recorded rationale, scope, risk, and compensating verification; coverage alone MUST NOT establish correctness.
- Security MUST be a hard requirement. Agents MUST plan and verify dependency vulnerability checks, lock integrity, approved package sources, secret exclusion, safe workbook parsing, and safe output generation. Agents MUST NOT execute workbook macros, formulas, external links, or untrusted content.
- Tests MUST cover malformed and hostile inputs, validation failures, interoperability with pinned external schemas, and failure without corrupting outputs. External schemas and dependencies MUST have recorded versions and provenance. Unknown vulnerability status MUST NOT be reported as a clean scan.
- Accessibility and performance MAY remain without dedicated targets unless a requirement or security constraint warrants them.

## Git, versions, and releases

- Agents MUST use trunk-based development with short-lived feature branches and Conventional Commits. Agents MUST create atomic commits frequently, including at least one commit per individual feature and per human interaction producing version-controlled artifacts. A commit MUST NOT combine unrelated work or include unrelated human changes.
- Agents MUST inspect staged diffs for private information, secrets, scope, and traceability before committing. Planning artifacts SHOULD be committed now; future issue migration MUST preserve stable IDs, approval history, and local navigation.
- The initial version MUST be 0.1.0. Pre-1.0 breaking changes MAY occur with documented impacts. From 1.0.0 onward, backward compatibility MUST be preserved within a major version. Breaking major releases MUST be avoided and MUST receive explicit human approval before work requiring them.
- The approved compatibility contract MUST enumerate CLI commands/options, exit codes, structured outputs, configuration, workbook schemas, persisted data, and any public Python API. Breaking changes MUST NOT be hidden in minor or patch releases after 1.0.0.
- Agents MUST use judgment to place durable specifications in files and execution tracking in future issues; origin MUST be https://github.com/obscuritylabs/dscat. Repository visibility MUST remain private unless the human explicitly authorizes a change.

## Catalog behavior and licensing

- Workbooks MUST be intake artifacts; exported catalog data MUST be the persisted source of truth. DSCat MUST accept individual workbooks or a directory and MUST rebuild deterministically and idempotently from unchanged inputs without requiring an application database.
- Validation MUST examine all readable inputs and collect all discoverable failures before returning failure; catalog exports MUST be blocked by default on any failure. Fatal unreadable files MUST be reported while validation continues on other inputs; agents MUST NOT claim to validate unreadable content.
- Workbooks MUST prioritize participation through a small required core and optional detail fields. Capacity metadata MUST support current size, average and peak daily ingestion, retention, and measurement date, with explicit Unknown allowed. Unknown MUST NOT become zero. Version 0.1.0 MUST NOT implement forecasts.
- Installed runtime operations MUST work offline. Network-dependent dependency/security checks MAY run during development or release preparation; authoritative schema validation MUST NOT require runtime downloads.
- Releases MUST include a dependency SBOM. Known High or Critical vulnerabilities MUST block release unless evidence establishes non-applicability; VEX MAY document non-applicability supported by execution-path analysis. Severity assessment, affected artifacts, and supporting evidence MUST be recorded; scanner absence or missing severity MUST NOT silently establish safety.
- Workbook schema compatibility MUST be explicitly versioned, tested, and tracked as the principal compatibility surface. A CLI-launched catalog web viewer MUST be planned for 0.2.0 and MUST NOT enter 0.1.0 without approved scope changes.
- The project MUST be proprietary to Obscurity Labs. LICENSE and Python project metadata MUST express the proprietary license and CLI help MUST display a matching notice. Agents MUST NOT substitute an open-source license or publish proprietary artifacts without release authorization.

## Main branch protection

- Agents MUST follow the active ruleset documented in docs/repository-policy.md. The human deleted local/github/main.ruleset.json after activation; agents MUST NOT recreate it without a new request and MUST keep the path excluded from Git. Remote protection changes MUST require explicit human instructions.
- Main MUST accept changes through pull requests with resolved review conversations and rebase merges preserving atomic Conventional Commits. Agents MUST NOT directly push, force-push, delete, or bypass protections on main. The one-time bootstrap has been consumed and MUST NOT be used again.
- Required GitHub approval count MUST be zero in the single-contributor workflow; human planning and release approval gates MUST remain mandatory. CI checks MUST be run and recorded before merge, and required-check rules MUST be added once stable CI check names exist.

- Identical dataset records sharing an ID MUST deduplicate; conflicting records sharing an ID MUST block export with both source locations. Neither duplicate handling nor canonical storage proposals MUST bypass complete validation or the human architecture gate.
