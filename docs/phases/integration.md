# Integration phase

The agent MUST first read [AGENTS.md](../../AGENTS.md) and the [planning index](../index.md), inspect Git status, and preserve unrelated changes.

This agent MUST follow the [workflow handoff](../workflow.md#bounded-handoff), verify its assigned revision and scope, and read [git versions and releases](../governance.md#git-versions-and-releases), [local verification and distribution](../governance.md#local-verification-and-distribution), [definition of done](../governance.md#definition-of-done), [autonomous delivery ownership](../governance.md#autonomous-delivery-ownership), [repository policy](../repository-policy.md), agent-authorized plan, exact verified artifacts and review dispositions. It MUST load linked details relevant to its assignment rather than unrelated transcript history.

The agent MUST own scoped atomic commits, staged privacy/scope/traceability inspection, push, PR lifecycle and rebase merge under active protection; it MUST obtain affected re-verification after conflicts or content changes and MUST NOT bypass main protection.

The return MUST include PR and merge references, verified origin/main revision, exact retained verification scope and remaining release stages; routine human PR review MUST NOT be introduced. Documentation changes MUST receive [full documentation QA/QC](../documentation-qa.md). Unavailable evidence and later completion stages MUST remain explicitly pending.
