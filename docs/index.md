# Documentation index

Agents MUST start with [AGENTS.md](../AGENTS.md), then use the [phase routing manifest](workflow.md#phase-routing). This index is navigation, not a requirement to load every linked document. [Planning gates](planning-gates.md) are authoritative for current approval status.

| Read when | Document and authoritative content |
| --- | --- |
| Coordinating work | [Workflow](workflow.md): phase routes, handoffs, transitions and escalation |
| Checking authorization | [Planning gates](planning-gates.md): exact human approval or agent authorization scope/revisions and pending deliverables |
| Planning or changing behavior | [Requirements](requirements.md): capabilities and stable acceptance criteria; [RTM](rtm.md): artifact/evidence mappings |
| Resolving current decisions or rationale | [Decisions](decisions.md): current decisions and necessary provenance; older wording through Git |
| Designing or verifying product behavior | [Engineering](engineering.md): toolchain, security, catalog and licensing constraints |
| Maintaining planning or delivery records | [Governance](governance.md): authority conventions, traceability, versioning and completion obligations |
| Reviewing proposed full architecture | [Architecture](architecture.md): typed model, intake, storage and compatibility; [standards](architecture-standards.md): offline closure and mappings; [assurance](architecture-assurance.md): threats, privacy and accessibility; [architecture task](tasks/architecture.md): current gate handoff |
| Designing intake | [Intake proposals](intake-proposals.md): unresolved detailed policies and minimum-export demonstration |
| Designing persistence, lineage or parsing | [Canonical model](canonical-model.md): storage, migration, RDF, lineage and security proposals |
| Assessing consolidated research scope | [Research additions](research-additions.md): consolidated impact and explicit exclusions; [research task](tasks/research-additions.md): historical integration evidence; [scope decisions](tasks/scope-decisions.md): current requirements decision handoff |
| Selecting standards/tools | [Research](research.md): upstream observations, revisions and hashes; not final runtime pins |
| Reviewing documentation | [Documentation QA/QC](documentation-qa.md): distributed coverage, semantic matrix and structural checks |
| Integrating changes | [Repository policy](repository-policy.md): active protection and PR/rebase procedure |
| Preparing or verifying a release | [Delivery plan](delivery-plan.md): draft checks, artifact and failure procedures; standing delegation and candidate readiness remain in the gate record |
| Assessing the retained historical exception | [Remediation disposition](privacy-remediation.md): consumed authority, accepted retention and evidence references |
| Inspecting approval-policy maintenance | [Approval-policy task](tasks/approval-policy.md): current scope, stage and verification handoff |
| Inspecting workflow maintenance | [Workflow task](tasks/documentation-workflow.md): scope, acceptance, current stage and evidence |

The architecture candidate MUST remain proposed until fresh exact-revision risk assessment and disposition under the [approval policy](governance.md#required-sdlc-and-approval-gates). The implementation plan and product verification deliverables MUST be prepared at their respective gates; partial notes and research-only demonstrations MUST NOT be treated as approved or implemented deliverables. Agents MUST follow relevant links only as their assignment and dependencies require.
