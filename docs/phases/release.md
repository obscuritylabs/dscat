# Release phase

The agent MUST first read [AGENTS.md](../../AGENTS.md) and the [planning index](../index.md), inspect Git status, and preserve unrelated changes.

Release preparation and post-release verification MUST use separate fresh invocations under the [workflow](../workflow.md). Each MUST read [git versions and releases](../governance.md#git-versions-and-releases), [local verification and distribution](../governance.md#local-verification-and-distribution), [definition of done](../governance.md#definition-of-done), [engineering constraints](../engineering.md#project-and-engineering-constraints) and [catalog/licensing policy](../engineering.md#catalog-behavior-and-licensing), [planning gates](../planning-gates.md), the approved release plan and applicable acceptance/RTM sections. Each MUST verify the bounded handoff and return exact revision, artifact hashes, commands, results, limitations and next gate.

## Release preparation

The agent MUST verify the remote-main candidate, local checks, manual walkthrough, wheel/source artifacts, checksums, SBOM, vulnerability disposition, licensing and installation/offline evidence. It MUST establish explicit candidate authorization or verify every condition of recorded human release delegation before tagging or publishing. Ordinary plan approval MUST NOT establish release permission. Within that authorization it MUST publish the approved assets and record their identity and release references. Missing authorization MUST leave publication pending with a concrete candidate decision package.

## Post-release verification

A new agent MUST download the actual GitHub Release assets, verify integrity and version, and use a clean environment to install and exercise applicable acceptance, CLI and offline scenarios. It MUST check documentation changes in the released source. Checkout tests and pre-upload builds MUST NOT substitute for these checks. It MUST record download source, released hashes, commands and outcomes, and reconcile all seven stage records before reporting completion. Failures MUST reopen the task through the workflow failure route; a published release MUST NOT conceal failed acceptance.

Documentation changes MUST receive [full documentation QA/QC](../documentation-qa.md). Pending evidence MUST remain pending.
