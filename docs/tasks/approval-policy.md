# Approval-policy maintenance handoff

## Identity and revision

Source: `dc87ca2f3698abc881f0bb3c610c1005c0c92cb4`, clean at intake. Phase: directly requested governance implementation, approval-policy implementation invocation. The returned handoff and subsequent verification/PR evidence MUST identify the exact candidate commit/tree and sorted relative-path/NUL/bytes/NUL SHA-256 digests; this record MUST NOT embed its own recursive digest.

## Scope and authority

[DEC-045](../decisions.md#dec-045), human instruction 2026-11-17, directly authorizes this governance change. [Governance](../governance.md#required-sdlc-and-approval-gates) owns approval-request rules and standing release delegation; [planning gates](../planning-gates.md) owns current status. Supporting traceability: CAP-05/NFR-006/NFR-007 and CAP-04/NFR-008/NFR-015/NFR-016/NFR-017. Acceptance is faithful requiredness, prospective reconciliation of current dependent instructions, preserved exact historical authority, and distinct human approval versus agent readiness.

Ownership: governance/control documents, phase instructions, current decision/gate/task/RTM authority metadata, and dependent architecture/delivery/proposal status wording only. Product code, technical architecture, acceptance criteria, requirements/impact bytes at `69b686a3d0b1da49290ca37d577d46fb8b63dbfb`, remote policy and release execution are excluded. No fresh architecture risk assessment or technical disposition is asserted. The supplied quality/service omission limitation remains proposed for the next fresh architecture agent to assess; DEC-045 is no human approval of it.

## Required reading and verification

Agents MUST read AGENTS.md, index/workflow and their assigned phase, governance authority/approval/completion/release policy, planning gates, documentation QA and repository policy, then follow relevant dependencies. Full semantic coverage MUST be divided into bounded fresh-agent assignments covering every maintained artifact across all applicable nine QA areas, followed by distinct fresh reconciliation. Implementation self-checks MUST NOT count as independent verification or review.

Reproduce `python3 docs/evidence/architecture/verify_documents.py` from the checkout root: recursive links/anchors, unique IDs, all 42 requirement/RTM rows and references MUST pass; missing-file, missing-anchor, duplicate-ID, missing-RTM-row, unknown-source, unknown-capability and unanchored-acceptance controls MUST each fail. Run `git diff --check`; compare requirements/impact bytes with the approved source; inspect the full staged diff for privacy, secrets, unsupported authority and scope. Exact results/digests MUST accompany the returned candidate and subsequent review evidence.

Manual walkthrough: read governance approval rules and route synthetic cases through workflow/phase files. Ordinary new requirements SHOULD produce a concrete human approval package. A request omitted under the uniqueness exception MUST cite exact prior explicit approval and prove no valid alternative; silence or agent review MUST fail that exception. Non-high-risk architecture MUST receive an agent disposition after checks; a high-risk architecture approval request MAY proceed only with concrete risk evidence. Plan, implementation, verification, review, integration and release cases MUST NOT ask human approval. A failed release check MUST block readiness despite standing delegation. Stale revisions, unavailable fresh agents and an implementation-origin independent reviewer MUST fail the corresponding gate. Visibility/protection changes or destructive remediation MUST remain outside ordinary delegation. This walkthrough uses document inspection and creates no product data or release; cleanup is unnecessary.

## Stage ledger and next gate

| Completion stage | Actual evidence/status |
| --- | --- |
| Planned | Direct governance instruction DEC-045; bounded implementation scope above; no product-plan approval asserted |
| Implemented | Policy and dependent current authority metadata prepared; RTM architecture-gate wording corrected after fresh review; exact candidate in PR #22 |
| Tested | PASS implementation self-check: 36 document/license files, 42 requirement/RTM rows, all seven negative controls, whitespace and exact approved-byte identity; exact tested candidate/results in returned handoff; no independent verification claimed |
| Locally verified | Initial full fresh bounded QA covered all 91 maintained artifacts across applicable nine matrix areas at `8f18a350e1fd6637d20da624426e93bb09172608`; distinct reconciliation confirmed one medium RTM wording finding, now corrected. Exact coverage/digests and current affected-review/reconciliation outcome: PR #22; no corrected-candidate PASS asserted here |
| Remote-main integration | Authoritative protected PR/rebase integration outcome and exact origin/main identity verification: PR #22; feature-branch publication MUST NOT count as integration |
| Published release | PENDING verified main/artifacts and publication under DEC-045 standing delegation; no additional human approval gate |
| Released-artifact verification | PENDING publication and actual downloaded-source verification |

Current verification, finding disposition and protected integration outcome MUST be read from PR #22; affected corrections MUST receive fresh review and distinct reconciliation before integration. The current work boundary is architecture risk assessment/disposition followed by autonomous implementation planning, then stop; product implementation and release execution are excluded. Governance maintenance MUST NOT substitute for those readiness gates. This task remains incomplete until all seven stages have evidence; release and downloaded-artifact stages remain PENDING.
