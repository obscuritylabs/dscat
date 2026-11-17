# Agent instructions

## Startup and delegation

- Every agent MUST read this file, [the index](docs/index.md), and its assigned [workflow route](docs/workflow.md#phase-routing), then check Git status and preserve unrelated changes.
- The coordinator MUST read only these control documents, relevant [gate entries](docs/planning-gates.md), and the current task handoff for routine routing. It MUST delegate domain analysis and execution to fresh phase agents with no inherited conversation transcript. Each phase agent MUST read the baseline sections assigned by its role and follow discovered dependencies; progressive disclosure MUST NOT omit applicable requirements.
- Requirements, architecture, and implementation-plan readiness MUST precede dependent product implementation in that order under the [approval policy](docs/governance.md#required-sdlc-and-approval-gates). Requirements SHOULD require human approval subject only to its explicit-prior-approval uniqueness exception; architecture MAY require it only for agent-assessed high risk. Implementation plans and all other SDLC stages MUST NOT require human approval. Dispositions MUST identify revision, date, scope and whether authority is human approval or agent readiness; agents MUST NOT infer human approval from silence, tools, integration or their own review.
- Agents MUST own routine implementation, verification, commits, PR review and rebase integration within approved scope. They MUST NOT directly push, force-push, delete, or bypass protection on main, change repository visibility, or alter remote protection without explicit authorization. Integration agents MUST read [repository policy](docs/repository-policy.md).
- Release tags and publication MUST proceed under the [standing release delegation](docs/governance.md#local-verification-and-distribution) after required checks; agents MUST NOT request further human approval for those stages. A task MUST remain incomplete until all seven [completion stages](docs/governance.md#definition-of-done) have evidence. The coordinator MUST check the stage ledger and artifact identities before transitions; a worker's success summary alone MUST NOT establish completion.

## Privacy and authority

- Agents MUST describe this project only through generic capabilities, technical requirements, and synthetic examples. Agents MUST NOT persist private conversational context, customer or agency identity, intended users or groups, operational purpose, deployment context, identifying private source URLs, local private paths, or identifying combinations in repository artifacts, Git history, issues, fixtures, logs, branches, PRs, or releases. Public standards MAY be cited when technically necessary without connecting them to private context. Before committing or publishing, agents MUST inspect proposed artifacts and diffs for disclosures and secrets.
- Requirements and agent-authorized plans MUST govern implementation. Agents MUST stop dependent work on unresolved material scope, compatibility or security decisions and route them under the approval policy; routine technical decisions within scope MUST remain autonomous.
- Normative instructions MUST use uppercase RFC 2119 keywords with RFC 8174 semantics. Planning provenance MUST remain sparse and separate from approval. Ordinary code, configuration, LICENSE, user documentation, and these instructions MUST use conventional formats without planning IDs or fact/provenance annotations.

## Documentation lifecycle

- Current documents MUST state current policy, decisions, and open proposals. Agents MUST replace or remove obsolete prose in ordinary Git commits instead of appending deprecation narratives. Git history MUST preserve previous versions; agents MUST NOT rewrite history as documentation cleanup.
- Each fact, rule, or status MUST have one authoritative home. Other documents SHOULD link to it rather than restate it. Active approval records, exceptions, residual risks, compatibility commitments, stable requirement IDs, and necessary evidence references MUST remain discoverable. IDs MUST NOT be reused; retirement records MUST be compact and link to impacts/history.
- Every documentation change MUST receive repository-wide structural checks and full semantic QA/QC coverage under [the documentation procedure](docs/documentation-qa.md). Coverage MUST be divided into bounded fresh-agent assignments, followed by cross-document reconciliation; it MUST NOT require each agent to load every document.
- Phase/task records MUST replace current state in place. Completed execution detail MUST remain in exact-revision evidence or Git history, with compact current references. Agents MUST NOT grow task logs, status summaries, or decision logs by appending every interaction.

## Read when applicable

| Work | Required policy |
| --- | --- |
| Planning, traceability, approval records | [Governance: authority](docs/governance.md#authority-and-statement-conventions), [gates](docs/planning-gates.md), relevant requirements and RTM rows |
| Product design, implementation, testing | [Engineering policy](docs/engineering.md), relevant approved design and acceptance criteria |
| Documentation changes or review | [Documentation QA/QC](docs/documentation-qa.md) |
| Commits, PRs, integration | [Git policy](docs/governance.md#git-versions-and-releases), [repository policy](docs/repository-policy.md) |
| Release preparation and verification | [Delivery policy](docs/governance.md#local-verification-and-distribution), [delivery plan](docs/delivery-plan.md), [completion stages](docs/governance.md#definition-of-done) |

Detailed role instructions and handoff requirements MUST follow [the phase workflow](docs/workflow.md). Missing required evidence or unavailable fresh-agent capability MUST be reported explicitly; agents MUST NOT silently simulate a fresh or independent review.
