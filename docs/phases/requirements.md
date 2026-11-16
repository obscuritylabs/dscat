# Requirements phase

The agent MUST first read [AGENTS.md](../../AGENTS.md) and the [planning index](../index.md), inspect Git status, and preserve unrelated changes.

This agent MUST follow the [workflow handoff](../workflow.md#bounded-handoff), verify its assigned revision and scope, and read [authority and statement conventions](../governance.md#authority-and-statement-conventions), [required sdlc and approval gates](../governance.md#required-sdlc-and-approval-gates), [traceability and change control](../governance.md#traceability-and-change-control), [planning gates](../planning-gates.md), [requirements](../requirements.md), applicable [decisions](../decisions.md) and [RTM](../rtm.md). It MUST load linked details relevant to its assignment rather than unrelated transcript history.

The agent MUST interview the human through the coordinator, resolve correctness assumptions, define measurable scope and acceptance, and distinguish proposals from approved baselines.

The return MUST include a revision-specific requirements decision package, traceability changes, unresolved decisions, and the human requirements gate; it MUST NOT authorize dependent implementation. Documentation changes MUST receive [full documentation QA/QC](../documentation-qa.md). Unavailable evidence and later completion stages MUST remain explicitly pending.
