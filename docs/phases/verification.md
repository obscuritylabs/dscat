# Verification phase

The agent MUST first read [AGENTS.md](../../AGENTS.md) and the [planning index](../index.md), inspect Git status, and preserve unrelated changes.

This agent MUST follow the [workflow handoff](../workflow.md#bounded-handoff), verify its assigned revision and scope, and read [required sdlc and approval gates](../governance.md#required-sdlc-and-approval-gates), [traceability and change control](../governance.md#traceability-and-change-control), [local verification and distribution](../governance.md#local-verification-and-distribution), [definition of done](../governance.md#definition-of-done), [engineering constraints](../engineering.md#project-and-engineering-constraints) and [catalog/licensing policy](../engineering.md#catalog-behavior-and-licensing), the same approved requirements, acceptance, architecture and plan sections required of the implementer, applicable RTM rows, and implementation artifacts. It MUST load linked details relevant to its assignment rather than unrelated transcript history.

The agent MUST independently inspect acceptance coverage and reproduce applicable local checks against the exact candidate; it MUST test positive and negative behavior, security, compatibility and installation as applicable rather than trust the implementation report.

The return MUST include reproducible revision/artifact evidence, acceptance dispositions, actual tested environments, uncovered cases and pass/fail; failure MUST return to correction rather than integration. Documentation changes MUST receive [full documentation QA/QC](../documentation-qa.md). Unavailable evidence and later completion stages MUST remain explicitly pending.
