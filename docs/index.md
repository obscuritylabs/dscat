# Documentation index

Agents MUST start with [AGENTS.md](../AGENTS.md), then classify the task under [scope and proportionality](governance.md#task-scope-and-proportionality) and use only applicable [phase routes](workflow.md#phase-routing). This index is navigation, not a requirement to load every linked document. [Planning gates](planning-gates.md) are authoritative for current approval status.

| Read when | Document and authoritative content |
| --- | --- |
| Coordinating work | [Governance](governance.md#task-scope-and-proportionality): task classes and stopping conditions; [workflow](workflow.md): applicable routes, bounded handoffs and risk-based review |
| Checking authorization | [Planning gates](planning-gates.md): exact human approval or agent authorization scope/revisions and pending deliverables |
| Planning or changing behavior | [Requirements](requirements.md): capabilities and stable acceptance criteria; [RTM](rtm.md): artifact/evidence mappings |
| Resolving current decisions or rationale | [Decisions](decisions.md): current decisions and necessary provenance; older wording through Git |
| Designing or verifying product behavior | [Engineering](engineering.md): toolchain, security, catalog and licensing constraints |
| Maintaining planning or delivery records | [Governance](governance.md): authority conventions, traceability, versioning and completion obligations |
| Reviewing architecture and disposition | [Architecture](architecture.md): typed model, intake, storage and compatibility; [standards](architecture-standards.md): offline closure and mappings; [assurance](architecture-assurance.md): threats, privacy and accessibility; [architecture task](tasks/architecture.md): current gate handoff |
| Executing approved first-release scope | [Implementation plan](implementation-plan.md): increments/all42 mappings and I01 handoff; [dependencies](implementation-dependencies.md): verified direct pins/provenance; [verification](implementation-verification.md): boundaries/manual/platform hard gates; [planning task](tasks/implementation-plan.md): exact candidate and review status |
| Designing intake | [Intake proposals](intake-proposals.md): versioned detailed policies and minimum-export demonstration |
| Designing persistence, lineage or parsing | [Canonical model](canonical-model.md): storage, migration, RDF, lineage and security proposals |
| Assessing consolidated research scope | [Research additions](research-additions.md): consolidated impact and explicit exclusions; [research task](tasks/research-additions.md): historical integration evidence; [scope decisions](tasks/scope-decisions.md): current requirements decision handoff |
| Selecting standards/tools | [Research](research.md): upstream observations, revisions and hashes; not final runtime pins |
| Reviewing documentation | [Documentation QA/QC](documentation-qa.md): distributed coverage, semantic matrix and structural checks |
| Integrating changes | [Repository policy](repository-policy.md): active protection and PR/rebase procedure |
| Preparing or verifying a release | [Delivery plan](delivery-plan.md): draft checks, artifact and failure procedures; standing delegation and candidate readiness remain in the gate record |
| Assessing the retained historical exception | [Remediation disposition](privacy-remediation.md): consumed authority, accepted retention and evidence references |
| Inspecting approval-policy maintenance | [Approval-policy task](tasks/approval-policy.md): current scope, stage and verification handoff |
| Inspecting workflow maintenance | [Workflow task](tasks/documentation-workflow.md): scope, acceptance, current stage and evidence |

The [architecture disposition](architecture-disposition.md) and [implementation plan](implementation-plan.md) retain DEC-046/047 technical decisions. [Planning gates](planning-gates.md#bounded-readiness-reconciliation) owns their current applicability, affected review and integration status. The subsequent implementation assignment is recorded in [planning gates](planning-gates.md#implementation-execution); product work MUST follow the ordered increments and applicable verification. Later detailed capability designs retain their milestone gates. Planned commands and research-only demonstrations MUST NOT be treated as implemented or executed deliverables. Agents MUST follow relevant links only as their assignment and dependencies require.
