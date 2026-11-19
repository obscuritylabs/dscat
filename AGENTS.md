# Agent instructions

## Startup and scope

- Agents MUST read this file and [the index](docs/index.md), inspect Git status, and preserve unrelated changes. They MUST classify the task under [task scope and proportionality](docs/governance.md#task-scope-and-proportionality) before selecting a [workflow route](docs/workflow.md#phase-routing).
- Agents MUST identify the requested outcome, included and excluded work, acceptance checks, and completion condition. They MUST implement only that scope. Read-only answers MUST NOT require repository records, phase dispatch, commits, or releases.
- Ordinary maintenance and implementation within an approved design MAY use one implementer. A coordinator is OPTIONAL; fresh phase agents MUST be reserved for material requirements, architecture, or planning decisions and independent review where required. [Review applicability](docs/workflow.md#review-applicability) determines independence; agents MUST NOT label self-review independent.
- Requirements, architecture, and implementation-plan readiness MUST precede dependent product implementation only where a material decision requires new or revised readiness under the [approval policy](docs/governance.md#required-sdlc-and-approval-gates). Agents MUST reuse unchanged applicable approvals and design decisions; a changed file hash alone MUST NOT reopen them.
- Agents MUST own applicable implementation, checks, commits, PR review, and rebase integration. They MUST NOT directly push, force-push, delete, or bypass protection on main, change repository visibility, or alter remote protection without explicit authorization. Integration MUST follow [repository policy](docs/repository-policy.md).
- Task completion MUST follow the [definition of done](docs/governance.md#definition-of-done) for its class and requested delivery. Release preparation, publication, and downloaded-artifact verification MUST be tracked separately unless release delivery is explicitly included in the task. Standing release delegation MUST remain subject to required release checks.
- Routine private local usage refreshes MUST remain self-service. Shared tracker contributions and publication MUST follow [usage tracking checkpoints](docs/workflow.md#usage-tracking-checkpoints); unrelated tasks MUST NOT acquire tracker work.

## Privacy and authority

- Agents MUST describe this project only through generic capabilities, technical requirements, and synthetic examples. Agents MUST NOT persist private conversational context, customer or agency identity, intended users or groups, operational purpose, deployment context, identifying private source URLs, local private paths, or identifying combinations in repository artifacts, Git history, issues, fixtures, logs, branches, PRs, or releases. Public standards MAY be cited when technically necessary without connecting them to private context. Before committing or publishing, agents MUST inspect proposed artifacts and diffs for disclosures and secrets.
- Requirements and agent-authorized plans MUST govern implementation. Agents MUST stop only dependent work on unresolved material scope, compatibility, or security decisions and route them under the approval policy; routine technical choices within scope MUST remain autonomous.
- Normative instructions MUST use uppercase RFC 2119 keywords with RFC 8174 semantics. Planning provenance MUST remain sparse and separate from approval. Ordinary code, configuration, LICENSE, user documentation, and these instructions MUST use conventional formats without planning IDs or fact/provenance annotations.

## Documentation lifecycle

- Current documents MUST state current policy, decisions, and open proposals. Agents MUST replace or remove obsolete prose in ordinary Git commits instead of appending deprecation narratives. Git history MUST preserve previous versions; agents MUST NOT rewrite history as documentation cleanup.
- Each fact, rule, or status MUST have one authoritative home. Other documents SHOULD link to it rather than restate it. Active approval records, exceptions, residual risks, compatibility commitments, stable requirement IDs, and necessary evidence references MUST remain discoverable. IDs MUST NOT be reused; retirement records MUST be compact and link to impacts/history.
- Documentation changes MUST receive repository-wide structural checks and semantic review of changed content and identified dependents under [the documentation procedure](docs/documentation-qa.md). Full semantic sweeps MUST be reserved for broad cross-cutting changes or explicitly scheduled audits.
- Review evidence MUST identify the reviewed candidate and live outside the artifacts it certifies. Factual status recording MUST follow the [evidence stopping rule](docs/documentation-qa.md#evidence-conventions), without recursive review of review records.
- Phase/task records MUST replace current state in place. Completed execution detail MUST remain in exact-revision evidence or Git history, with compact current references. Agents MUST NOT grow task logs, status summaries, or decision logs by appending every interaction.

## Read when applicable

| Work | Required policy |
| --- | --- |
| Scope, planning, approval records | [Governance](docs/governance.md#task-scope-and-proportionality), relevant [gates](docs/planning-gates.md), affected requirements and RTM rows |
| Product design, implementation, testing | [Engineering policy](docs/engineering.md), relevant approved design and acceptance criteria |
| Documentation changes or review | [Documentation QA/QC](docs/documentation-qa.md) |
| Commits, PRs, integration | [Git policy](docs/governance.md#git-versions-and-releases), [repository policy](docs/repository-policy.md) |
| Release preparation and verification | [Delivery policy](docs/governance.md#local-verification-and-distribution), [delivery plan](docs/delivery-plan.md) |

Agents MUST load only applicable policy and dependencies. Missing evidence MUST be reported accurately; unrelated defects and optional improvements MUST remain separate follow-ups.
