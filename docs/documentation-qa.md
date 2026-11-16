# Documentation QA/QC procedure

## Scope and authority

DEC-037/038 directly request this procedure, supporting CAP-05/NFR-006 and NFR-007. Every documentation change, including this procedure and AGENTS.md, MUST receive the full-document review required by [AGENTS.md](../AGENTS.md#documentation-lifecycle). Automated checks MUST supplement semantic review; neither establishes that future defects are impossible.

## Change procedure

1. Agents MUST read AGENTS.md, the planning index, their assigned phase route, this procedure, and the bounded document sections assigned for their review. The coordinator MUST inventory all maintained documentation, including nested phase/task files, and divide full semantic coverage into bounded fresh-agent assignments. Each assignment MUST identify documents/sections, applicable matrix areas, source revision/digest, and dependencies; no single reviewer MUST be required to load every document. They MUST inspect `git status --short --branch` and preserve unrelated changes. Before editing, they MUST identify governing decisions, approval boundaries, and affected requirements/artifacts.
2. Agents MUST update the authoritative statement first and reconcile every dependent summary, RTM row, index status, example, and verification procedure in the same change. A changed decision MUST identify superseded statements and scope. Historical instructions MUST remain explicitly historical; current summaries MUST NOT instruct readers to perform consumed operations.
3. The assigned reviewers MUST collectively review every maintained document against every applicable matrix area below and return coverage and findings. A distinct fresh reconciliation reviewer MUST inspect cross-document authority, terminology, links, mappings, and unresolved findings against the identified combined candidate; a coverage ledger MUST identify reviewed sections, reviewers, matrix coverage, and dispositions. Agents MUST perform reproducible repository-wide structural checks. Before committing they MUST run `git diff --check`, verify all local Markdown links and anchors, confirm unique requirement/decision IDs and complete requirement/RTM membership, and resolve every RTM decision/capability/acceptance reference. Requirement links MUST target stable heading anchors. A changed structural checker MUST be exercised on synthetic missing-link, missing-anchor, duplicate-ID, missing-RTM-row, and unknown-reference cases; every defective case MUST fail. Automated tooling implementation MUST follow its applicable engineering gates and MUST NOT be claimed to exist merely because this procedure specifies checks.
4. Agents MUST immediately correct discovered issues within authorized scope and rerun repository-wide structural checks plus affected semantic assignments and cross-document reconciliation; unaffected coverage MAY be retained only for identical content and applicability. New technical choices MUST remain labeled proposals until the affected gates approve them. An unresolved material decision MUST block dependent work; a human deferral MUST remain explicit without fabricating a pass.
5. Agents MUST inspect the staged diff for scope, traceability, private context, secrets, unsupported claims, and unrelated changes. They MUST record concise check commands/results against the exact tested commit and artifact/tree hashes in the authorized task/verification record or PR. Findings MUST remain conversational when the human requests that restriction; verification evidence MUST NOT reproduce those findings.
6. Agents MUST self-review and integrate through the active PR/rebase workflow, verify the merged revision on origin/main, and accurately report remaining approval/release stages. They MUST rerun affected checks after any post-verification edit or integration conflict. An unchanged, verified result MAY be reused only when its exact content and applicability are established.

## Reusable structural verification

The standard-library structural verification recipe and seven in-memory negative controls are retained with [PR #13 verification evidence](https://github.com/obscuritylabs/dscat/pull/13). Agents MUST retrieve and run that recipe from the current checkout root for every documentation change, adapting it when document structure changes and retaining the exact revised recipe with the new verification evidence. The adapted recipe MUST recursively inventory maintained Markdown, including docs/phases/ and docs/tasks/, plus repository entry documentation. They MUST verify current document/requirement counts rather than trust historical output labels. The recipe checks local links/anchors, identifier uniqueness, RTM membership, and source/capability/acceptance references; it MUST NOT replace the full semantic review below. It is a local audit recipe, not an installed product command or a configured CI enforcement claim.

## Full semantic review matrix

| Area | Required review |
| --- | --- |
| Authority | Human instruction versus agent proposal; approval scope/date/revision; consolidated baseline versus individually accepted decisions; no implicit approval |
| Meaning | Same terminology, scope, requiredness, conditional technology obligations, defaults, and success/failure semantics across all documents |
| Completeness | Acceptance measurable at the current stage; later-stage work assigned to a named gate; no missing fact concealed by a fabricated default |
| Change control | Supersession explicit in current navigation; historical instructions not actionable; no consumed exceptions reused; stable IDs preserved |
| Traceability | Every requirement has capability, decision source, anchored acceptance, design, implementation, tests, and evidence or explicit PENDING; all maintained artifacts mapped |
| Evidence | Authoritative sources, date, exact revision/hash, reproducible command and result; unavailable, historical, unverified, and current observations distinguished |
| Technical details | Versions, schemas and offline references, units, Unknown/empty/zero, paths, normalization, limits, invalid inputs, preservation, retry, compatibility, and examples agree |
| Delivery and security | Threat model, safe parsing/output, dependency provenance/age/vulnerabilities, licensing, SBOM, authorization, artifact identity, and released-version verification agree |
| Privacy and format | Neutral capabilities and synthetic data only; no identifying combinations; conventional legal/code formats; sparse provenance and stable requirement IDs |

## Evidence conventions

Reports MUST identify the tested source commit plus dirty-tree state and a content/tree digest where edits are not committed. Generic labels such as “Document review” or “Metadata parsing” MUST NOT count as execution evidence. Historical evidence MAY remain attributed but MUST NOT be silently upgraded to a fresh verification. Corrections to evidence wording MUST preserve the original observation date and scope.

Public research used to choose a technical resource MUST identify an immutable upstream revision and content digest where available. A mutable discovery page MAY identify a candidate, but MUST NOT serve as the runtime resource pin. Before implementation, agents MUST verify the full transitive schema/context closure and licensing; a top-level schema digest alone MUST NOT imply offline conformance.
