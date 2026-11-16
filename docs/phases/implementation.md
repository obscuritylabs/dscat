# Implementation phase

The agent MUST first read [AGENTS.md](../../AGENTS.md) and the [planning index](../index.md), inspect Git status, and preserve unrelated changes.

This agent MUST follow the [workflow handoff](../workflow.md#bounded-handoff), verify its assigned revision and scope, and read [required sdlc and approval gates](../governance.md#required-sdlc-and-approval-gates), [traceability and change control](../governance.md#traceability-and-change-control), [definition of done](../governance.md#definition-of-done), [autonomous delivery ownership](../governance.md#autonomous-delivery-ownership), [engineering constraints](../engineering.md#project-and-engineering-constraints) and [catalog/licensing policy](../engineering.md#catalog-behavior-and-licensing), the approved requirements, acceptance, architecture and plan sections for this increment, and applicable [RTM](../rtm.md) rows. It MUST load linked details relevant to its assignment rather than unrelated transcript history.

The agent MUST implement only the approved increment, preserve unrelated changes, update traceability and documentation, self-review, and run applicable checks; it MUST NOT label self-testing independent verification.

The return MUST include the exact implemented revision/digest, changed artifacts/symbols, tests and results, manual verification material, limitations and a handoff to a fresh verification agent. Documentation changes MUST receive [full documentation QA/QC](../documentation-qa.md). Unavailable evidence and later completion stages MUST remain explicitly pending.
