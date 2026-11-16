# Planning index

- IDX-001 [FACT; TOOL_VERIFIED; 2026-11-16] Readers MUST treat this as an unapproved initial planning baseline; no implementation or release MUST be inferred from these files. Evidence: initial repository inspection found no files or commits.
- IDX-002 [FACT; HUMAN_DERIVED] The initial version MUST be 0.1.0; agents MUST use the following concise artifacts as the planning system.

| Artifact | Purpose | Gate/status |
| --- | --- | --- |
| [Decision log](decisions.md) | Human instructions and open interview decisions | Captured; policy draft awaits review |
| [Requirements](requirements.md) | Charter, capabilities, acceptance criteria | DRAFT; approval pending |
| [RTM](rtm.md) | Requirement and artifact traceability | DRAFT; approval pending |
| [Standards research](research.md) | Neutral public-source evidence and recommendations | Research; selection pending |
| [Intake proposals](intake-proposals.md) | Minimum fields, capacity, conflicts, canonical exports | DRAFT; interview choices pending |
| [Repository policy](repository-policy.md) | Main protections and local import instructions | ACTIVE; API verified; local import JSON deleted |
| [Delivery draft](delivery-plan.md) | Local verification, minimal CI, GitHub Release artifacts | DRAFT; implementation/release gates pending |
| [Canonical model notes](canonical-model.md) | Authoritative JSON, flat-file organization, migration boundary | Direction approved; detailed design pending |
| [History remediation](privacy-remediation.md) | Narrow privacy cleanup, history replacement, and retained-copy verification | History verified; protection restored; retained-copy disposition accepted |
| Architecture | Boundaries, models, schema mappings, security design | PENDING requirements interview |
| Implementation plan | Ordered increments and checks | PENDING architecture |
| Verification plan and reports | Automated tests, manual walkthrough, evidence | PENDING detailed scope |

- IDX-003 [FACT; LLM_INFERENCE] Agents MUST create the pending artifacts as the interview resolves scope, and MUST record explicit approvals against document commits before dependent work.

- IDX-004 [FACT; HUMAN_DERIVED] Readers MUST treat 0.1.0 as metadata intake plus DCAT-US 3.0/ODCS export, with Excel currently selected subject to SPEC-001/SPEC-007; the CLI-launched catalog web viewer MUST be scheduled for 0.2.0. All requirements, architecture, planning, and release approval gates MUST remain in force.
