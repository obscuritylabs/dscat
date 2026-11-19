# Release phase

This role applies only when selected by [proportional routing](../workflow.md#phase-routing). The agent MUST first read [AGENTS.md](../../AGENTS.md) and the [planning index](../index.md), inspect Git status, and preserve unrelated changes.

Release preparation and post-release verification MUST use separate fresh invocations under the [workflow](../workflow.md). Each MUST read [git versions and releases](../governance.md#git-versions-and-releases), [local verification and distribution](../governance.md#local-verification-and-distribution), [definition of done](../governance.md#definition-of-done), [engineering constraints](../engineering.md#project-and-engineering-constraints) and [catalog/licensing policy](../engineering.md#catalog-behavior-and-licensing), [planning gates](../planning-gates.md), the agent-authorized release plan and applicable acceptance/RTM sections. Each MUST verify the bounded handoff and return exact revision, artifact hashes, commands, results, limitations and next gate.

## Release preparation

The agent MUST verify the remote-main candidate, local checks, manual walkthrough, wheel/source artifacts, checksums, SBOM, vulnerability disposition, licensing and installation/offline evidence. It MUST verify every applicable readiness condition and record exercise of DEC-045 standing release delegation before tagging or publishing. It MUST NOT request human release approval. It MUST publish the verified assets and record their identity and release references; missing or failed evidence MUST leave publication pending until corrected and reverified.

## Post-release verification

A new agent MUST download the actual GitHub Release assets, verify integrity and version, and use a clean environment to install and exercise applicable acceptance, CLI and offline scenarios. It MUST check documentation changes in the released source. Checkout tests and pre-upload builds MUST NOT substitute for these checks. It MUST record download source, released hashes, commands and outcomes, and reconcile the release task evidence before reporting release completion. Failures MUST reopen affected release work through the workflow failure route; a published release MUST NOT conceal failed acceptance.

Documentation changes MUST receive [focused documentation QA/QC](../documentation-qa.md). Pending evidence MUST remain pending.
