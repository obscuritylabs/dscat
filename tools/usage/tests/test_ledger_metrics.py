"""Synthetic receipt overlap, replacement, measurement and projection acceptance."""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dscat_usage.identity import domain, receipt
from dscat_usage.ledger import MergeConflict, canonical_records, contribution_digest, merge
from dscat_usage.metrics import Rate, aggregate, price, validate_rates
from dscat_usage.render import OWNED_PROJECTIONS, render
from dscat_usage.schema import (
    TOKEN_KEYS,
    Contribution,
    Ledger,
    Observation,
    UsageError,
    Vocabulary,
    canonical,
    empty_attribution,
    loads,
)

VOCAB = Vocabulary(
    models=frozenset({"synthetic-model"}),
    providers=frozenset({"synthetic-provider"}),
    tiers=frozenset({"standard", "batch"}),
    efforts=frozenset({"low", "high"}),
    rtm=frozenset({"NFR-006", "NFR-007"}),
    tasks=frozenset({"TASK-001", "TASK-002"}),
    features=frozenset({"FEATURE-001"}),
)
SECRET = bytes(range(32))
DOMAIN = domain(SECRET)
NOW = "2026-01-01T00:01:00Z"
LATER = "2026-02-01T00:01:00Z"
USAGE = {
    "input_tokens": 100,
    "cached_input_tokens": 40,
    "cache_write_input_tokens": 0,
    "output_tokens": 50,
    "reasoning_output_tokens": 20,
    "total_tokens": 150,
}


def response(name: str = "response-a", turn: str = "turn-a", **changes: object) -> Observation:
    """Response."""
    attrs = {
        **empty_attribution(),
        "primary": "NFR-006",
        "phase": "implementation",
        "task": "TASK-001",
        "feature": "FEATURE-001",
        "associated": ["NFR-007"],
    }
    values = {
        "kind": "response",
        "receipt": receipt(SECRET, "response", "thread-a", name),
        "thread": receipt(SECRET, "thread", "thread-a"),
        "turn": receipt(SECRET, "turn", "thread-a", turn),
        "timestamp": "2026-01-01T00:00:05Z",
        "model": "synthetic-model",
        "provider": "synthetic-provider",
        "tier": "standard",
        "effort": "low",
        "usage": USAGE.copy(),
        "attribution": attrs,
    }
    return Observation(**{**values, **changes})


def turn(
    name: str = "turn-a",
    start: str | None = "2026-01-01T00:00:00Z",
    end: str | None = "2026-01-01T00:00:10Z",
    duration: int | None = 10,
    basis: str = "recorded",
    **changes: object,
) -> Observation:
    """Turn."""
    identity = receipt(SECRET, "turn", "thread-a", name)
    values = {
        "kind": "turn",
        "receipt": identity,
        "thread": receipt(SECRET, "thread", "thread-a"),
        "turn": identity,
        "start": start,
        "end": end,
        "duration_seconds": duration,
        "timing_basis": basis,
    }
    return Observation(**{**values, **changes})


def contribution(
    records: tuple[Observation, ...],
    contributor: str = "a" * 32,
    previous: Contribution | None = None,
    **changes: object,
) -> Contribution:
    """Contribution."""
    values = {
        "domain": DOMAIN,
        "contributor": contributor,
        "generation": previous.generation + 1 if previous else 1,
        "predecessor": contribution_digest(previous, VOCAB) if previous else None,
        "observed_at": LATER if previous else NOW,
        "observations": records,
    }
    return Contribution(**{**values, **changes})


def rate(**changes: object) -> Rate:
    """Rate."""
    values = {
        "model": "synthetic-model",
        "provider": "synthetic-provider",
        "currency": "USD",
        "effective_from": "2026-01-01",
        "effective_until": None,
        "input_per_million": "2",
        "cached_input_per_million": "1",
        "output_per_million": "4",
        "reviewed_on": "2026-01-01",
    }
    return Rate(**{**values, **changes})


class LedgerTests(unittest.TestCase):
    """Ledgertests."""

    def assert_code(self, code: int, callback: object, *args: object) -> UsageError:
        """Assert code."""
        with self.assertRaises(UsageError) as caught:
            callback(*args)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_disjoint_and_replay_preserve_other_contributors(self) -> None:
        """Test disjoint and replay preserve other contributors."""
        first = contribution((turn(), response()))
        second = contribution((response("response-b"),), "b" * 32)
        ledger = merge(merge(None, first, VOCAB), second, VOCAB)
        self.assertEqual(len(canonical_records(ledger, VOCAB)), 3)
        self.assertIs(merge(ledger, first, VOCAB), ledger)
        self.assertEqual(ledger.contributions, (first, second))
        self.assertEqual(
            canonical(merge(merge(None, second, VOCAB), first, VOCAB).to_dict()), canonical(ledger.to_dict())
        )

    def test_replacement_removal_is_explicit_and_does_not_erase_overlap(self) -> None:
        """Test replacement removal is explicit and does not erase overlap."""
        first = contribution((response(), response("response-b")))
        copied = contribution((response(),), "b" * 32)
        ledger = merge(merge(None, first, VOCAB), copied, VOCAB)
        next_generation = contribution((response("response-b"),), previous=first)
        self.assert_code(4, merge, ledger, next_generation, VOCAB)
        corrected = replace(next_generation, removals=(response().receipt,))
        updated = merge(ledger, corrected, VOCAB)
        self.assertEqual(len(canonical_records(updated, VOCAB)), 2)
        self.assertEqual(updated.contributions[1], copied)
        empty = contribution((), previous=corrected, removals=(response("response-b").receipt,))
        self.assertEqual(len(canonical_records(merge(updated, empty, VOCAB), VOCAB)), 1)
        self.assertEqual(len(first.observations), 2)

    def test_generation_and_domain_failures(self) -> None:
        """Test generation and domain failures."""
        first = contribution((response(),))
        ledger = merge(None, first, VOCAB)
        for changed in (
            replace(first, observations=()),
            contribution((response(),), previous=first, generation=3),
            contribution((response(),), previous=first, predecessor="f" * 64),
            contribution((response(),), previous=first, observed_at="2025-01-01T00:00:00Z"),
            contribution((response(),), domain="f" * 64),
        ):
            with self.subTest(changed=changed.generation):
                self.assert_code(4, merge, ledger, changed, VOCAB)
        newer = contribution((response(),), previous=first)
        self.assert_code(4, merge, merge(ledger, newer, VOCAB), first, VOCAB)
        self.assert_code(4, merge, None, newer, VOCAB)
        self.assert_code(4, merge, None, replace(first, removals=("f" * 64,)), VOCAB)

    def test_unavailable_and_partial_history_preservation(self) -> None:
        """Test unavailable and partial history preservation."""
        first = contribution((response(),))
        ledger = merge(None, first, VOCAB)
        coverage = {**first.coverage, "unavailable_sources": 1}
        missing = contribution((), previous=first, removals=(response().receipt,), coverage=coverage)
        self.assert_code(3, merge, ledger, missing, VOCAB)
        self.assert_code(3, merge, None, contribution((), coverage=coverage), VOCAB)
        preserved = contribution(first.observations, previous=first, coverage=coverage)
        self.assertEqual(merge(ledger, preserved, VOCAB).contributions[0].coverage["unavailable_sources"], 1)
        partial = {**first.coverage, "partial_lines": 1}
        self.assertEqual(
            merge(None, contribution(first.observations, coverage=partial), VOCAB)
            .contributions[0]
            .coverage["partial_lines"],
            1,
        )
        self.assert_code(3, merge, ledger, replace(missing, coverage=partial), VOCAB)
        self.assertEqual(ledger.contributions, (first,))

    def test_copied_overlap_and_enrichment(self) -> None:
        """Test copied overlap and enrichment."""
        unknown = response(model=None, provider=None, usage=dict.fromkeys(TOKEN_KEYS), attribution=empty_attribution())
        opened = turn(end=None, duration=None, basis="missing")
        first = contribution((unknown, opened))
        second = contribution((response(), turn()), "b" * 32)
        records = canonical_records(merge(merge(None, first, VOCAB), second, VOCAB), VOCAB)
        known_response = next(record for record in records if record.kind == "response")
        known_turn = next(record for record in records if record.kind == "turn")
        self.assertEqual(known_response.usage, USAGE)
        self.assertEqual(known_response.attribution["primary"], "NFR-006")
        self.assertEqual(known_turn.duration_seconds, 10)
        self.assertEqual(len(records), 2)
        self.assertEqual(known_turn.end, "2026-01-01T00:00:10+00:00")

    def test_conflicting_overlap_is_quarantined_and_not_leaked(self) -> None:
        """Test conflicting overlap is quarantined and not leaked."""
        first = contribution((response(), turn()))
        ledger = merge(None, first, VOCAB)
        variants = [
            replace(response(), usage={**USAGE, "input_tokens": 101, "total_tokens": 151}),
            replace(response(), timestamp="2026-01-01T00:00:06Z"),
            replace(response(), attribution={**response().attribution, "primary": "NFR-007"}),
            replace(response(), tier="batch"),
            replace(response(), effort="high"),
        ]
        for variant in variants:
            with self.subTest(variant=variant):
                other = contribution((variant,), "b" * 32)
                with self.assertRaises(MergeConflict) as caught:
                    merge(ledger, other, VOCAB)
                self.assertEqual(caught.exception.count, 1)
                self.assertEqual(caught.exception.receipts, (response().receipt,))
                self.assertNotIn(response().receipt, str(caught.exception))
        two_conflicts = contribution((variants[0], replace(turn(), duration_seconds=11)), "b" * 32)
        with self.assertRaises(MergeConflict) as caught:
            merge(ledger, two_conflicts, VOCAB)
        self.assertEqual(caught.exception.count, 2)
        self.assertEqual(ledger.contributions, (first,))

    def test_contradictory_other_contributor_cannot_be_overwritten(self) -> None:
        """Test contradictory other contributor cannot be overwritten."""
        first = contribution((response(),))
        other = contribution((response(),), "b" * 32)
        ledger = merge(merge(None, first, VOCAB), other, VOCAB)
        changed = contribution(
            (replace(response(), usage={**USAGE, "input_tokens": 101, "total_tokens": 151}),), previous=first
        )
        self.assert_code(4, merge, ledger, changed, VOCAB)
        self.assertEqual(ledger.contributions[0], first)

    def test_known_parent_conflicts_and_equivalent_timestamps(self) -> None:
        """Test known parent conflicts and equivalent timestamps."""
        first = contribution((replace(response(), timestamp="2026-01-01T01:00:05+01:00", parent_known=True),))
        other = contribution((replace(response(), parent_known=True, parent="b" * 64),), "b" * 32)
        self.assert_code(4, merge, merge(None, first, VOCAB), other, VOCAB)
        records = canonical_records(
            merge(merge(None, first, VOCAB), contribution((response(),), "b" * 32), VOCAB), VOCAB
        )
        self.assertEqual(records[0].timestamp, "2026-01-01T00:00:05+00:00")

    def test_enriched_subsets_are_revalidated(self) -> None:
        """Test enriched subsets are revalidated."""
        one = replace(response(), usage={**dict.fromkeys(TOKEN_KEYS), "input_tokens": 2})
        two = replace(response(), usage={**dict.fromkeys(TOKEN_KEYS), "cached_input_tokens": 3})
        self.assert_code(4, merge, merge(None, contribution((one,)), VOCAB), contribution((two,), "b" * 32), VOCAB)

    def test_frozen_u2_ledger_and_rate_fixtures(self) -> None:
        """Test frozen u2 ledger and rate fixtures."""
        fixtures = Path(__file__).parent / "fixtures"
        ledger_bytes = (fixtures / "ledger-v1.json").read_bytes()
        frozen_ledger = Ledger.from_dict(loads(ledger_bytes), VOCAB)
        self.assertEqual(canonical(frozen_ledger.to_dict()), ledger_bytes)
        rates_bytes = (fixtures / "rates-v1.json").read_bytes()
        frozen_rates = loads(rates_bytes)
        self.assertEqual(canonical(frozen_rates), rates_bytes)
        self.assertEqual(Rate.from_dict(frozen_rates["rates"][0], VOCAB), rate())

    def test_transport_strict_roundtrip_and_unknown_key_rejection(self) -> None:
        """Test transport strict roundtrip and unknown key rejection."""
        ledger = merge(None, contribution((response(), turn())), VOCAB)
        self.assertEqual(Ledger.from_dict(loads(canonical(ledger.to_dict())), VOCAB), ledger)
        value = ledger.to_dict()
        value["contributions"][0]["observations"][0]["prompt"] = "synthetic rejected content"
        self.assert_code(2, Ledger.from_dict, value, VOCAB)


class MeasurementTests(unittest.TestCase):
    """Measurementtests."""

    def ledger(self, *records: Observation) -> Ledger:
        """Ledger."""
        return merge(None, contribution(records), VOCAB)

    def test_closed_global_union_and_no_response_turns(self) -> None:
        """Test closed global union and no response turns."""
        second = turn("turn-b", "2026-01-01T00:00:05Z", "2026-01-01T00:00:15Z", 10, "derived_interval")
        third = turn("turn-c", "2026-01-01T00:00:20Z", "2026-01-01T00:00:25Z", 5)
        report = aggregate(self.ledger(turn(), response(), second, third), VOCAB)
        timing = report["time"]
        self.assertEqual(timing["summed_closed_interval_seconds"], "25")
        self.assertEqual(timing["closed_interval_union_seconds"], "20")
        self.assertEqual(timing["overlap_seconds"], "5")
        self.assertEqual(timing["parallelism"], "1.25")
        self.assertEqual(timing["recorded_duration_seconds"], "15")
        self.assertEqual(timing["derived_fallback_seconds"], "10")
        self.assertEqual(timing["no_response_turns"], 2)
        self.assertEqual(timing["response_bearing_turns"], 1)
        self.assertEqual(timing["observation_span_seconds"], "25")
        self.assertIsNone(timing["model_time_seconds"])
        self.assertIsNone(timing["productive_time_seconds"])

    def test_copied_intervals_recomputed_once(self) -> None:
        """Test copied intervals recomputed once."""
        first = contribution((turn(), response()))
        ledger = merge(merge(None, first, VOCAB), contribution(first.observations, "b" * 32), VOCAB)
        self.assertEqual(aggregate(ledger, VOCAB)["time"]["closed_interval_union_seconds"], "10")
        self.assertEqual(aggregate(ledger, VOCAB)["tokens"]["input_tokens"]["known_subtotal"], 100)

    def test_open_missing_zero_and_response_timestamp_span(self) -> None:
        """Test open missing zero and response timestamp span."""
        opened = turn(end=None, duration=None, basis="missing")
        missing = turn("turn-b", None, None, None, "missing")
        zero = turn("turn-c", "2026-01-01T00:00:10Z", "2026-01-01T00:00:10Z", 0)
        timing = aggregate(self.ledger(opened, missing, zero, response(timestamp="2026-01-01T00:00:15Z")), VOCAB)[
            "time"
        ]
        self.assertEqual(
            (timing["open_turns"], timing["missing_intervals"], timing["missing_duration_count"]), (1, 1, 2)
        )
        self.assertEqual(timing["closed_interval_union_seconds"], "0")
        self.assertIsNone(timing["parallelism"])
        self.assertEqual(timing["observation_span_seconds"], "15")

    def test_views_reconcile_primary_and_mixed_time_allocates_once(self) -> None:
        """Test views reconcile primary and mixed time allocates once."""
        first = response()
        second = response(
            "response-b",
            attribution={**first.attribution, "primary": "NFR-007", "phase": "verification", "task": "TASK-002"},
        )
        report = aggregate(self.ledger(turn(), first, second), VOCAB)
        for dimension in ("primary", "phase", "task", "feature", "model"):
            groups = report["views"][dimension]
            self.assertEqual(sum(item["responses"] for item in groups.values()), 2)
            self.assertEqual(sum(item["tokens"]["input_tokens"]["known_subtotal"] for item in groups.values()), 200)
            self.assertEqual(sum(item["time"]["turns"] for item in groups.values()), 1)
        self.assertEqual(report["views"]["primary"]["mixed"]["time"]["closed_interval_union_seconds"], "10")
        self.assertEqual(report["views"]["primary"]["mixed"]["time"]["response_bearing_turns"], 1)
        self.assertEqual(report["associated_requirements"], {"NFR-007": 2})

    def test_category_unions_are_nonadditive(self) -> None:
        """Test category unions are nonadditive."""
        other_turn = turn("turn-b")
        other_response = response("response-b", "turn-b", attribution={**response().attribution, "primary": "NFR-007"})
        report = aggregate(self.ledger(turn(), response(), other_turn, other_response), VOCAB)
        total = sum(
            float(group["time"]["closed_interval_union_seconds"]) for group in report["views"]["primary"].values()
        )
        self.assertEqual(total, 20)
        self.assertEqual(report["time"]["closed_interval_union_seconds"], "10")

    def test_tokens_known_subtotal_and_unknown_remain_distinct(self) -> None:
        """Test tokens known subtotal and unknown remain distinct."""
        unknown = response("response-b", usage=dict.fromkeys(TOKEN_KEYS), attribution=empty_attribution())
        report = aggregate(self.ledger(response(), unknown), VOCAB)
        for key, known in USAGE.items():
            self.assertEqual(report["tokens"][key], {"known_subtotal": known, "missing_count": 1})
        self.assertEqual(report["counts"]["unmapped_responses"], 1)
        self.assertEqual(report["counts"]["responses_without_turn_record"], 2)
        self.assertEqual(report["coverage"]["active_tail"], "unknown")
        self.assertEqual(report["coverage"]["historical_completeness"], "unknown")

    def test_empty_corpus_and_measurement_clock(self) -> None:
        """Test empty corpus and measurement clock."""
        empty = aggregate(Ledger(DOMAIN, ()), VOCAB)
        self.assertIsNone(empty["measured_as_of"])
        self.assertIsNone(empty["time"]["observation_span_seconds"])
        self.assertIsNone(empty["cost"]["measurement_date_list_counterfactual"])
        with self.assertRaises(UsageError) as caught:
            aggregate(self.ledger(response()), VOCAB, measured_at="2025-01-01T00:00:00Z")
        self.assertEqual(caught.exception.code, 4)

    def test_nested_intervals_and_microsecond_precision(self) -> None:
        """Test nested intervals and microsecond precision."""
        outer = turn("turn-a", "2026-01-01T00:00:00.000001Z", "2026-01-01T00:00:10.000002Z", 9)
        inner = turn("turn-b", "2026-01-01T00:00:01Z", "2026-01-01T00:00:02Z", 1)
        timing = aggregate(self.ledger(outer, inner), VOCAB)["time"]
        self.assertEqual(timing["closed_interval_union_seconds"], "10.000001")
        self.assertEqual(timing["summed_closed_interval_seconds"], "11.000001")
        self.assertEqual(timing["recorded_duration_seconds"], "10")
        self.assertEqual(timing["duration_interval_discrepancies"], 1)


class PricingTests(unittest.TestCase):
    """Pricingtests."""

    def estimate(
        self, records: tuple[Observation, ...] = (), rates: tuple[Rate, ...] = (), measured_at: str | None = LATER
    ) -> dict[str, object]:
        """Estimate."""
        return price(records, rates, measured_at, VOCAB)

    def test_cache_subtraction_and_reasoning_subset_not_double_charged(self) -> None:
        """Test cache subtraction and reasoning subset not double charged."""
        result = self.estimate((response(),), (rate(),))
        self.assertEqual(result["event_date"]["known_estimate_by_currency"], {"USD": "0.00036"})
        self.assertEqual(
            result["measurement_date_list_counterfactual"]["known_estimate_by_currency"], {"USD": "0.00036"}
        )
        self.assertEqual(result["event_date"]["priced_responses"], 1)
        self.assertIsNone(result["actual_bill"])

    def test_historical_rates_and_current_counterfactual_separate(self) -> None:
        """Test historical rates and current counterfactual separate."""
        old = rate(effective_until="2026-02-01")
        new = rate(
            effective_from="2026-02-01", input_per_million="4", cached_input_per_million="2", output_per_million="8"
        )
        result = self.estimate((response(),), (new, old))
        self.assertEqual(result["event_date"]["known_estimate_by_currency"], {"USD": "0.00036"})
        self.assertEqual(
            result["measurement_date_list_counterfactual"]["known_estimate_by_currency"], {"USD": "0.00072"}
        )

    def test_currency_subtotals_never_combined(self) -> None:
        """Test currency subtotals never combined."""
        result = self.estimate((response(),), (rate(), rate(currency="EUR", input_per_million="1")))
        self.assertEqual(result["event_date"]["known_estimate_by_currency"], {"EUR": "0.0003", "USD": "0.00036"})
        self.assertEqual(result["event_date"]["priced_responses"], 1)

    def test_missing_unknown_and_unsupported_remain_unpriced(self) -> None:
        """Test missing unknown and unsupported remain unpriced."""
        cases = [
            (replace(response(), timestamp=None), "missing_event_time"),
            (replace(response(), model=None), "unknown_model_or_provider"),
            (replace(response(), provider=None), "unknown_model_or_provider"),
            (replace(response(), usage={**USAGE, "cache_write_input_tokens": 1}), "unsupported_cache_write"),
            (replace(response(), usage={**USAGE, "cache_write_input_tokens": None}), "unknown_cache_write"),
            (replace(response(), usage={**USAGE, "cached_input_tokens": None}), "missing_tokens"),
        ]
        for record, reason in cases:
            with self.subTest(reason=reason):
                result = self.estimate((record,), (rate(),))["event_date"]
                self.assertEqual(result["unpriced_reasons"], {reason: 1})
                self.assertEqual(result["known_estimate_by_currency"], {})
                self.assertEqual(result["unpriced_responses"], 1)
                self.assertFalse(result["complete"])
        result = self.estimate((response(),), ())["event_date"]
        self.assertEqual(result["known_estimate_by_currency"], {})
        self.assertEqual(result["unpriced_reasons"], {"missing_exact_rate_or_constraint": 1})

    def test_missing_event_time_can_price_independent_current_scenario(self) -> None:
        """Test missing event time can price independent current scenario."""
        result = self.estimate((replace(response(), timestamp=None),), (rate(),))
        self.assertEqual(result["event_date"]["unpriced_responses"], 1)
        self.assertEqual(result["measurement_date_list_counterfactual"]["priced_responses"], 1)
        self.assertIsNone(self.estimate((response(),), (rate(),), None)["measurement_date_list_counterfactual"])

    def test_tier_effort_and_effective_boundaries(self) -> None:
        """Test tier effort and effective boundaries."""
        constrained = rate(tier="batch", effort="high")
        self.assertEqual(self.estimate((response(),), (constrained,))["event_date"]["unpriced_responses"], 1)
        matched = replace(response(), tier="batch", effort="high")
        self.assertEqual(self.estimate((matched,), (constrained,))["event_date"]["priced_responses"], 1)
        self.assertEqual(
            self.estimate((response(timestamp="2025-12-31T23:59:59Z"),), (rate(),))["event_date"]["unpriced_responses"],
            1,
        )
        self.assertEqual(
            self.estimate((response(timestamp="2026-02-01T00:00:00Z"),), (rate(effective_until="2026-02-01"),))[
                "event_date"
            ]["unpriced_responses"],
            1,
        )
        self.assertEqual(
            self.estimate((response(timestamp="2026-01-01T01:00:05+01:00"),), (rate(),))["event_date"][
                "priced_responses"
            ],
            1,
        )

    def test_rate_boundary_rejects_arbitrary_labels_numeric_escapes_and_overlap(self) -> None:
        """Test rate boundary rejects arbitrary labels numeric escapes and overlap."""
        self.assertEqual(Rate.from_dict(rate().to_dict(), VOCAB), rate())
        invalid = [
            replace(rate(), model="private-label"),
            replace(rate(), provider="private-label"),
            replace(rate(), currency="usd"),
            replace(rate(), input_per_million="NaN"),
            replace(rate(), input_per_million="-1"),
            replace(rate(), input_per_million=True),
            replace(rate(), effective_from="2026-02-31"),
            replace(rate(), effective_until="2026-01-01"),
            replace(rate(), tier="private-label"),
            replace(rate(), reviewed=False),
            replace(rate(), provenance="https://invalid.example/private"),
            replace(rate(), schema=True),
        ]
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(UsageError):
                item.validate(VOCAB)
        with self.assertRaises(UsageError):
            Rate.from_dict({**rate().to_dict(), "evidence": "not permitted"}, VOCAB)
        with self.assertRaises(UsageError) as caught:
            validate_rates((rate(), rate(tier="standard")), VOCAB)
        self.assertEqual(caught.exception.code, 4)
        validate_rates((rate(tier="standard"), rate(tier="batch")), VOCAB)
        with self.assertRaises(UsageError):
            self.estimate((response(), response()), (rate(),))

    def test_known_cost_subtotal_does_not_claim_unpriced_work_is_zero(self) -> None:
        """Test known cost subtotal does not claim unpriced work is zero."""
        missing = response("response-b", usage=dict.fromkeys(TOKEN_KEYS))
        result = self.estimate((response(), missing), (rate(),))["event_date"]
        self.assertEqual(result["known_estimate_by_currency"], {"USD": "0.00036"})
        self.assertEqual((result["priced_responses"], result["unpriced_responses"]), (1, 1))
        self.assertFalse(result["complete"])


class ProjectionTests(unittest.TestCase):
    """Projectiontests."""

    def test_owned_projection_allowlist_no_receipts_or_contributors(self) -> None:
        """Test owned projection allowlist no receipts or contributors."""
        records = (turn(), response())
        first = contribution(records)
        ledger = merge(None, first, VOCAB)
        pages = render(ledger, VOCAB)
        self.assertEqual(set(pages), OWNED_PROJECTIONS)
        rendered = b"\n".join(pages.values()).decode()
        for forbidden in (
            first.contributor,
            DOMAIN,
            "thread-a",
            "response-a",
            *(record.receipt for record in records),
            "source_root",
            "secret_file",
            "evidence_digest",
        ):
            self.assertNotIn(forbidden, rendered)
        self.assertIn("Cost: unknown", rendered)
        self.assertIn("Active final tail: unknown", rendered)
        self.assertIn("not anonymous", rendered)
        self.assertIn("Known subtotal", rendered)
        self.assertEqual(render(ledger, VOCAB), pages)
        copy = contribution(records, "b" * 32)
        self.assertEqual(render(merge(ledger, copy, VOCAB), VOCAB), pages)

    def test_render_prices_empty_and_negative_schemas(self) -> None:
        """Test render prices empty and negative schemas."""
        pages = render(merge(None, contribution((response(),)), VOCAB), VOCAB, rates=(rate(),))
        self.assertIn(b"| USD | 0.00036 |", pages["Usage.md"])
        empty = render(Ledger(DOMAIN, ()), VOCAB)
        self.assertIn(b"Measured as of: unknown", empty["Usage.md"])
        self.assertIn(b"Unknown measurement date", empty["Usage.md"])
        invalid = replace(response(), model="unreviewed-label")
        with self.assertRaises(UsageError):
            render(Ledger(DOMAIN, (contribution((invalid,)),)), VOCAB)


if __name__ == "__main__":
    unittest.main()
