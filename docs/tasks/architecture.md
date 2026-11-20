# Architecture readiness handoff

## Scope and authority

The 2026-11-19 explicit user direction selects OS agnostic/macOS primary behavior; [DEC-048](../decisions.md#dec-048) records its requirements authority. Source: `253d9f1c6c96d90e4051fdf3f7cc655c2f89ac0b`. Included: NFR-001/DEC-028 reconciliation, native resource/observer architecture, selected macOS manual arrangements, risk disposition and bounded fresh-plan handoff. Excluded: product edits, tests, dependency resolution, actual manual/platform acceptance, releases and remote changes. Concurrent implementation work MUST be preserved.

## Acceptance and evidence

[Native platform design](../architecture-platform.md) owns the selected kernel-scoped observer, finite map-growth guard, existing finite allocation graph/IPC and required failure evidence. [Architecture disposition](../architecture-disposition.md#native-platform-decision) assesses moderate residual risk and records agent architecture readiness for fresh affected planning, subject to exact-candidate independent review. No strict physical-memory ceiling or product verification PASS is claimed. Existing DEC-044 exact approval and unchanged DEC-046/047 technical decisions remain applicable; affected plan readiness MUST remain PENDING in [planning gates](../planning-gates.md#macos-primary-readiness).

Required documentation checks: repository-wide structural/identifier/RTM/negative-control checker, whitespace check, focused semantic/dependent review and privacy/scope inspection. Independent evidence MUST identify final candidate bytes and remain outside them. Small synthetic native guard/ABI observations MUST remain distinguished from installed-product tests. NFR-005 failure/preservation/retry and NFR-021 keyboard/assistive acceptance remain mandatory.

## Next handoff

A fresh planning agent MUST use the exact reviewed candidate to revise dependent native adapter/observer and platform/manual tasks. The architecture author MUST NOT self-certify independent review or material plan readiness. Completion of this handoff is a concrete documentation candidate and risk disposition; protected integration remains separately assigned. No product implementation, push or release occurs in this architecture task.
