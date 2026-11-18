"""Allowlisted aggregate-only pages; no transport receipts enter rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable

from .metrics import Rate, aggregate
from .schema import DEFAULT_VOCABULARY, TOKEN_KEYS, Ledger, Vocabulary

OWNED_PROJECTIONS = frozenset(
    {"Usage.md", "Usage-by-RTM.md", "Usage-by-Task.md", "Usage-Models.md", "Usage-Methodology.md", "Usage-Evidence.md"}
)


def _page(lines: list[str]) -> bytes:
    return ("\n".join(lines) + "\n").encode("utf-8")


def _view(title: str, groups: dict[str, Any]) -> list[str]:
    lines = [
        f"# {title}",
        "",
        (
            "Turn intervals are grouped once per dimension. Conflicting response categories use mixed. "
            "Category interval unions are nonadditive; model time remains unknown."
        ),
        "",
        "| Category | Responses | Turns | Closed interval union (seconds) |",
        "| --- | ---: | ---: | ---: |",
    ]
    lines.extend(
        (
            f"| {label} | {facts['responses']} | {facts['time']['turns']} | "
            f"{facts['time']['closed_interval_union_seconds']} |"
        )
        for label, facts in sorted(groups.items())
    )
    return lines


def render(
    ledger: Ledger,
    vocabulary: Vocabulary = DEFAULT_VOCABULARY,
    *,
    rates: Iterable[Rate] = (),
    measured_at: str | None = None,
) -> dict[str, bytes]:
    """Derive exactly six owned files, leaving all unrelated pages to the caller.

    Only schema-validated public labels and fixed metric fields reach these pages.
    Publication time stays unknown until an independent remote readback exists.
    """
    report = aggregate(ledger, vocabulary, rates=rates, measured_at=measured_at)
    counts, coverage, timing = report["counts"], report["coverage"], report["time"]
    summary = [
        "# Usage",
        "",
        f"Measured as of: {report['measured_as_of'] or 'unknown'}",
        "",
        "Remotely confirmed publication time: unknown",
        "",
        "| Corpus | Count |",
        "| --- | ---: |",
    ]
    summary.extend(
        f"| {label} | {counts[key]} |"
        for key, label in (
            ("responses", "Responses"),
            ("turns", "Source turns"),
            ("threads", "Threads"),
            ("unmapped_responses", "Unmapped responses"),
            ("responses_without_turn_record", "Responses without turn records"),
        )
    )
    summary += [
        "",
        "Historical completeness: unknown. Active final tail: unknown.",
        "",
        f"Unavailable sources: {coverage['unavailable_sources']}. Partial trailing lines: {coverage['partial_lines']}.",
        "",
        "| Token counter | Known subtotal | Missing responses |",
        "| --- | ---: | ---: |",
    ]
    summary.extend(
        f"| {key} | {report['tokens'][key]['known_subtotal']} | {report['tokens'][key]['missing_count']} |"
        for key in TOKEN_KEYS
    )
    summary += [
        "",
        ("Cached input is part of input; reasoning output is part of output. Subsets are not added to their totals."),
        "",
        "| Timing fact | Value |",
        "| --- | ---: |",
    ]
    summary.extend(
        f"| {label} | {timing[key] if timing[key] is not None else 'unknown'} |"
        for key, label in (
            ("duration_interval_discrepancies", "Recorded duration / interval discrepancies"),
            ("response_bearing_turns", "Response-bearing source turns"),
            ("no_response_turns", "Turns without responses"),
            ("open_turns", "Open turns"),
            ("missing_intervals", "Missing intervals"),
            ("missing_duration_count", "Missing durations"),
            ("recorded_duration_count", "Recorded duration count"),
            ("recorded_duration_seconds", "Recorded duration seconds"),
            ("derived_fallback_count", "Derived duration fallback count"),
            ("derived_fallback_seconds", "Derived fallback seconds"),
            ("summed_closed_interval_seconds", "Summed closed interval seconds"),
            ("closed_interval_union_seconds", "Global closed interval union seconds"),
            ("overlap_seconds", "Overlap seconds"),
            ("parallelism", "Closed-interval parallelism"),
            ("observation_span_seconds", "Observation span seconds"),
        )
    )
    summary += [
        "",
        "Model time: unknown. Productive time: unknown.",
        "",
        (
            "Costs are dated public API estimates, not actual bills. Known subtotals exclude unpriced "
            "work; currencies are never combined."
        ),
    ]
    for key, label in (
        ("event_date", "Event-date API estimate"),
        ("measurement_date_list_counterfactual", "Measurement-date list-price counterfactual"),
    ):
        scenario = report["cost"][key]
        summary += ["", f"## {label}", ""]
        if scenario is None:
            summary.append("Unknown measurement date; unavailable.")
            continue
        summary.append(
            f"Priced responses: {scenario['priced_responses']}. Unpriced responses: {scenario['unpriced_responses']}."
        )
        summary += ["", "| Currency | Known estimate subtotal |", "| --- | ---: |"]
        summary.extend(
            f"| {currency} | {amount} |" for currency, amount in scenario["known_estimate_by_currency"].items()
        )
        if not scenario["known_estimate_by_currency"]:
            summary += ["", "Cost: unknown (no priced subtotal available)."]
        if scenario["unpriced_reasons"]:
            summary += ["", "| Unpriced category | Responses |", "| --- | ---: |"]
            summary.extend(f"| {reason} | {count} |" for reason, count in scenario["unpriced_reasons"].items())
    primary = _view("Usage by primary requirement", report["views"]["primary"])
    primary += [
        "",
        "Associated requirements are references only and do not receive a second primary allocation.",
        "",
        "| Associated requirement | Referencing responses |",
        "| --- | ---: |",
    ]
    primary.extend(f"| {label} | {count} |" for label, count in report["associated_requirements"].items())
    primary += ["", *_view("Usage by phase", report["views"]["phase"])]
    tasks = [
        *_view("Usage by task", report["views"]["task"]),
        "",
        *_view("Usage by feature", report["views"]["feature"]),
    ]
    methodology = [
        "# Usage methodology",
        "",
        (
            "The corpus counts each keyed response receipt once across latest contributor observations."
            " Exact overlaps collapse; compatible unknown facts can be enriched. Conflicting "
            "observations block publication. Contributor generations replace only their own prior "
            "observations with explicit reviewed removals."
        ),
        "",
        (
            "Mappings resolve response, then turn, then thread independently for each dimension. "
            "Unreviewed or unsupported mappings remain unallocated. Primary views reconcile to the same"
            " response corpus; associated references are nonadditive."
        ),
        "",
        (
            "Recorded durations, derived fallbacks, interval sums, global interval unions, observation "
            "span and overlap remain separate. Source turns without responses remain visible. Open and "
            "missing intervals contribute no invented closed duration. Category interval unions are "
            "nonadditive. Recorded clock discrepancies can limit timing accuracy. Model time and "
            "productive time remain unknown."
        ),
        "",
        (
            "Token subtotals include only known counters. Missing values are unknown, never zero. "
            "Cached input is within input; reasoning is within output."
        ),
        "",
        (
            "API estimates use reviewed dated per-million rates and Decimal arithmetic. Cached input is"
            " subtracted from ordinary input before pricing. Event-date estimates and measurement-date "
            "list-price counterfactuals are computed independently. Missing exact models, providers, "
            "applicable rates, required constraints or token facts stay unpriced. Unsupported or "
            "unknown cache writes stay unpriced. Currency subtotals are separate and never represent "
            "actual bills."
        ),
        "",
        (
            "Keyed transport receipts enable correlation and are not anonymous. Rendered pages omit "
            "receipts and contributor identifiers. Historical completeness and the active final tail "
            "remain unknown. Measurement time and independently confirmed publication time are "
            "different facts."
        ),
    ]
    evidence = [
        "# Usage evidence",
        "",
        (
            "These pages contain allowlisted aggregates derived from the validated transport ledger. "
            "Local preparation does not establish publication or independent review."
        ),
        "",
        (
            "Every outgoing complete tree requires fresh semantic/privacy review with exact private "
            "execution bindings. Review validators check supplied procedural bindings; they cannot "
            "authenticate reviewer honesty or independence against a process controlling private state."
        ),
        "",
        (
            "Submission and independent remote clone/readback are separate outcomes. Remotely confirmed"
            " publication time is unknown in this prepared projection. Actual histories, contributions "
            "and tracker publication require a separately reviewed protocol transition and are outside "
            "the synthetic tooling demonstration."
        ),
    ]
    return {
        "Usage.md": _page(summary),
        "Usage-by-RTM.md": _page(primary),
        "Usage-by-Task.md": _page(tasks),
        "Usage-Models.md": _page(_view("Usage by model", report["views"]["model"])),
        "Usage-Methodology.md": _page(methodology),
        "Usage-Evidence.md": _page(evidence),
    }
