# Requirements phase

This role applies only when selected by [proportional routing](../workflow.md#phase-routing). The agent MUST first read [AGENTS.md](../../AGENTS.md) and the [planning index](../index.md), inspect Git status, and preserve unrelated changes.

This agent MUST follow the [workflow handoff](../workflow.md#bounded-handoff), verify its assigned revision and scope, and read [authority and statement conventions](../governance.md#authority-and-statement-conventions), [required sdlc and approval gates](../governance.md#required-sdlc-and-approval-gates), [traceability and change control](../governance.md#traceability-and-change-control), [planning gates](../planning-gates.md), [requirements](../requirements.md), applicable [decisions](../decisions.md) and [RTM](../rtm.md). It MUST load linked details relevant to its assignment rather than unrelated transcript history.

The agent MUST resolve correctness assumptions, define measurable scope and acceptance, and distinguish proposals from approved baselines. It SHOULD seek human approval for new material requirements unless the concrete change is already explicitly authorized or prior explicit approvals entail the only valid solution under governance. It MUST cite the applicable authority and scope; a coordinator MUST NOT be required solely to ask a question.

The return MUST include a revision-specific requirements decision package, traceability changes, unresolved decisions, and the applicable requirements disposition; it MUST NOT authorize dependent implementation. Documentation changes MUST receive [focused documentation QA/QC](../documentation-qa.md). Unavailable applicable evidence MUST remain explicit; separate release work MUST NOT block this task unless included in its scope.
