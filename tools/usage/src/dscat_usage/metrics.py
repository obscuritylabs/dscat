"""One receipt corpus, explicit unknowns, interval unions and dated API estimates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, localcontext
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from collections.abc import Iterable

from .ledger import canonical_records
from .schema import (
    DEFAULT_VOCABULARY,
    TOKEN_KEYS,
    Ledger,
    Observation,
    UsageError,
    Vocabulary,
    integer,
    keys,
    present,
    require,
    text,
    timestamp,
)


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)


def _seconds(value: timedelta) -> Decimal:
    return Decimal(value.days * 86400 + value.seconds) + Decimal(value.microseconds) / 1_000_000


def _number(value: Decimal) -> str:
    return format(value, "f")


def _day(value: object) -> date:
    value = text(value, r"\d{4}-\d{2}-\d{2}")

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        reason = "invalid rate date"
        raise UsageError(reason) from exc


def _decimal(value: object) -> Decimal:
    value = text(value, r"(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,12})?")
    return Decimal(value)


@dataclass(frozen=True)
class Rate:
    """Reviewed public per-million rates. Null constraints mean unconditional.

    Provenance is a fixed public category, never a source URL or private evidence.
    A non-null effort/tier constraint requires the exact recorded setting.
    End dates are exclusive. Unknown cache-write pricing always stays unpriced.
    """

    model: str
    provider: str
    currency: str
    effective_from: str
    effective_until: str | None
    input_per_million: str
    cached_input_per_million: str
    output_per_million: str
    reviewed_on: str
    tier: str | None = None
    effort: str | None = None
    provenance: str = "public-api-list"
    reviewed: bool = True
    schema: int = 1

    def validate(self, vocabulary: Vocabulary = DEFAULT_VOCABULARY) -> None:
        """Validate every rate field against the reviewed public vocabulary."""
        integer(self.schema, 1, 1)
        require(isinstance(self.model, str) and self.model in vocabulary.models, "unknown rate model")
        require(isinstance(self.provider, str) and self.provider in vocabulary.providers, "unknown rate provider")
        text(self.currency, r"[A-Z]{3}")
        start = _day(self.effective_from)
        if self.effective_until is not None:
            require(_day(self.effective_until) > start, "invalid rate interval")
        _day(self.reviewed_on)
        for value in (self.input_per_million, self.cached_input_per_million, self.output_per_million):
            _decimal(value)
        for value, inventory in ((self.tier, vocabulary.tiers), (self.effort, vocabulary.efforts)):
            require(value is None or (isinstance(value, str) and value in inventory), "unknown rate constraint")
        require(self.provenance == "public-api-list" and self.reviewed is True, "reviewed public rates required")

    def to_dict(self) -> dict[str, Any]:
        """Return the complete rate record for canonical serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any], vocabulary: Vocabulary = DEFAULT_VOCABULARY) -> Self:
        """Construct and validate one strict public rate record."""
        keys(value, set(cls.__dataclass_fields__))
        result = cls(**value)
        result.validate(vocabulary)
        return result


def validate_rates(rates: tuple[Rate, ...], vocabulary: Vocabulary = DEFAULT_VOCABULARY) -> None:
    """Reject ambiguous overlapping constraints, even before any response matches."""
    for index, rate in enumerate(rates):
        rate.validate(vocabulary)
        for other in rates[:index]:
            if (rate.model, rate.provider, rate.currency) != (other.model, other.provider, other.currency):
                continue
            constraints_overlap = all(
                a is None or b is None or a == b for a, b in ((rate.tier, other.tier), (rate.effort, other.effort))
            )
            dates_overlap = max(_day(rate.effective_from), _day(other.effective_from)) < min(
                _day(rate.effective_until) if rate.effective_until else date.max,
                _day(other.effective_until) if other.effective_until else date.max,
            )
            require(not (constraints_overlap and dates_overlap), "ambiguous public rate intervals", 4)


def _scenario(records: tuple[Observation, ...], rates: tuple[Rate, ...], day: date | None) -> dict[str, Any]:
    totals: dict[str, Decimal] = {}
    reasons: dict[str, int] = {}
    priced = 0
    for record in records:
        reason: str | None = None
        event_day = day or (_instant(record.timestamp).date() if record.timestamp is not None else None)
        if event_day is None:
            reason = "missing_event_time"
        elif record.model is None or record.provider is None:
            reason = "unknown_model_or_provider"
        elif record.usage["cache_write_input_tokens"] not in (None, 0):
            reason = "unsupported_cache_write"
        elif any(record.usage[key] is None for key in ("input_tokens", "cached_input_tokens", "output_tokens")):
            reason = "missing_tokens"
        # A missing cache-write count is unknown, rather than proof of no writes.
        elif record.usage["cache_write_input_tokens"] is None:
            reason = "unknown_cache_write"
        matched = (
            []
            if reason
            else [
                rate
                for rate in rates
                if rate.model == record.model
                and rate.provider == record.provider
                and (rate.tier is None or rate.tier == record.tier)
                and (rate.effort is None or rate.effort == record.effort)
                and event_day is not None
                and _day(rate.effective_from) <= event_day
                and (rate.effective_until is None or event_day < _day(rate.effective_until))
            ]
        )
        if reason is None and not matched:
            reason = "missing_exact_rate_or_constraint"
        if reason is not None:
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        priced += 1
        with localcontext() as context:
            context.prec = 80
            for rate in matched:
                input_count = record.usage["input_tokens"]
                cached_count = record.usage["cached_input_tokens"]
                output_count = record.usage["output_tokens"]
                input_count = present(input_count, "invalid schema", 2)
                cached_count = present(cached_count, "invalid schema", 2)
                output_count = present(output_count, "invalid schema", 2)
                estimate = (
                    Decimal(input_count - cached_count) * Decimal(rate.input_per_million)
                    + Decimal(cached_count) * Decimal(rate.cached_input_per_million)
                    + Decimal(output_count) * Decimal(rate.output_per_million)
                ) / 1_000_000
                totals[rate.currency] = totals.get(rate.currency, Decimal(0)) + estimate
    return {
        "priced_responses": priced,
        "unpriced_responses": len(records) - priced,
        "unpriced_reasons": dict(sorted(reasons.items())),
        "known_estimate_by_currency": {key: _number(value) for key, value in sorted(totals.items())},
        "complete": priced == len(records),
    }


def price(
    records: Iterable[Observation],
    rates: Iterable[Rate] = (),
    measured_at: str | None = None,
    vocabulary: Vocabulary = DEFAULT_VOCABULARY,
) -> dict[str, Any]:
    """Independently price event-date and measurement-date API counterfactuals.

    Known currency subtotals are estimates, never actual bills or a total for
    unpriced work. An empty currency map means unavailable, not zero cost.
    """
    corpus = tuple(records)
    for record in corpus:
        record.validate(vocabulary)
    require(len({record.receipt for record in corpus}) == len(corpus), "duplicate pricing corpus", 4)
    responses = tuple(record for record in corpus if record.kind == "response")
    rate_set = tuple(rates)
    validate_rates(rate_set, vocabulary)
    if measured_at is not None:
        timestamp(measured_at)
    current = _scenario(responses, rate_set, _instant(measured_at).date()) if measured_at is not None else None
    return {
        "basis": "public_api_estimate",
        "actual_bill": None,
        "event_date": _scenario(responses, rate_set, None),
        "measurement_date_list_counterfactual": current,
    }


def _union(intervals: list[tuple[datetime, datetime]]) -> Decimal:
    end: datetime | None = None
    total = Decimal(0)
    for start, stop in sorted(intervals):
        if end is None or start > end:
            total += _seconds(stop - start)
            end = stop
        elif stop > end:
            total += _seconds(stop - end)
            end = stop
    return total


def _time(turns: tuple[Observation, ...], responses: tuple[Observation, ...]) -> dict[str, Any]:
    intervals = [
        (_instant(turn.start), _instant(turn.end)) for turn in turns if turn.start is not None and turn.end is not None
    ]
    summed = sum((_seconds(end - start) for start, end in intervals), Decimal(0))
    union = _union(intervals)
    starts = [_instant(turn.start) for turn in turns if turn.start is not None]
    ends = [_instant(turn.end) for turn in turns if turn.end is not None]
    discrepancies = sum(
        turn.timing_basis == "recorded"
        and turn.start is not None
        and turn.end is not None
        and Decimal(str(turn.duration_seconds)) != _seconds(_instant(turn.end) - _instant(turn.start))
        for turn in turns
    )
    recorded = [Decimal(str(turn.duration_seconds)) for turn in turns if turn.timing_basis == "recorded"]
    derived = [Decimal(str(turn.duration_seconds)) for turn in turns if turn.timing_basis == "derived_interval"]
    response_turns = {response.turn for response in responses}
    events = starts + ends + [_instant(record.timestamp) for record in responses if record.timestamp is not None]
    return {
        "turns": len(turns),
        "response_bearing_turns": sum(turn.receipt in response_turns for turn in turns),
        "no_response_turns": sum(turn.receipt not in response_turns for turn in turns),
        "closed_intervals": len(intervals),
        "duration_interval_discrepancies": discrepancies,
        "open_turns": sum(turn.start is not None and turn.end is None for turn in turns),
        "missing_intervals": sum(turn.start is None for turn in turns),
        "recorded_duration_count": len(recorded),
        "recorded_duration_seconds": _number(sum(recorded, Decimal(0))),
        "derived_fallback_count": len(derived),
        "derived_fallback_seconds": _number(sum(derived, Decimal(0))),
        "missing_duration_count": sum(turn.duration_seconds is None for turn in turns),
        "summed_closed_interval_seconds": _number(summed),
        "closed_interval_union_seconds": _number(union),
        "overlap_seconds": _number(summed - union),
        "parallelism": _number(summed / union) if union else None,
        "observation_span_seconds": _number(_seconds(max(events) - min(events))) if events else None,
        "model_time_seconds": None,
        "productive_time_seconds": None,
    }


def _tokens(records: tuple[Observation, ...]) -> dict[str, Any]:
    return {
        key: {
            "known_subtotal": sum(record.usage[key] for record in records if record.usage[key] is not None),
            "missing_count": sum(record.usage[key] is None for record in records),
        }
        for key in TOKEN_KEYS
    }


def _label(record: Observation, dimension: str) -> str:
    if dimension == "model":
        return record.model or "unknown"
    return record.attribution[dimension] or "unallocated"


def _view(turns: tuple[Observation, ...], responses: tuple[Observation, ...], dimension: str) -> dict[str, Any]:
    by_turn: dict[str, list[Observation]] = {}
    for response in responses:
        by_turn.setdefault(present(response.turn, "missing turn identity", 4), []).append(response)
    grouped_turns: dict[str, list[Observation]] = {}
    for turn in turns:
        labels = {_label(record, dimension) for record in by_turn.get(turn.receipt, [])}
        label = next(iter(labels)) if len(labels) == 1 else "mixed" if labels else _label(turn, dimension)
        grouped_turns.setdefault(label, []).append(turn)
    grouped_responses: dict[str, list[Observation]] = {}
    for record in responses:
        grouped_responses.setdefault(_label(record, dimension), []).append(record)
    labels = sorted(set(grouped_turns) | set(grouped_responses))
    response_turns = {record.turn for record in responses}
    result: dict[str, Any] = {}
    for label in labels:
        selected = tuple(grouped_responses.get(label, []))
        selected_turns = tuple(grouped_turns.get(label, []))
        timing = _time(selected_turns, selected)
        timing["response_bearing_turns"] = sum(turn.receipt in response_turns for turn in selected_turns)
        timing["no_response_turns"] = sum(turn.receipt not in response_turns for turn in selected_turns)
        result[label] = {"responses": len(selected), "tokens": _tokens(selected), "time": timing}
    return result


def aggregate(
    ledger: Ledger,
    vocabulary: Vocabulary = DEFAULT_VOCABULARY,
    *,
    rates: Iterable[Rate] = (),
    measured_at: str | None = None,
) -> dict[str, Any]:
    """Return a sanitized, receipt-free measurement object from one canonical corpus."""
    records = canonical_records(ledger, vocabulary)
    turns = tuple(record for record in records if record.kind == "turn")
    responses = tuple(record for record in records if record.kind == "response")
    turn_receipts = {turn.receipt for turn in turns}
    times = [contribution.observed_at for contribution in ledger.contributions]
    if measured_at is None:
        measured_at = max(times, key=_instant) if times else None
    if measured_at is not None:
        timestamp(measured_at)
        require(
            not times or _instant(measured_at) >= max(map(_instant, times)), "measurement clock precedes observation", 4
        )
    return {
        "schema": 1,
        "measured_as_of": measured_at,
        "remotely_confirmed_publication_at": None,
        "counts": {
            "responses": len(responses),
            "turns": len(turns),
            "threads": sum(record.kind == "thread" for record in records),
            "unmapped_responses": sum(record.attribution["primary"] == "unallocated" for record in responses),
            "responses_without_turn_record": sum(record.turn not in turn_receipts for record in responses),
        },
        "coverage": {
            "historical_completeness": "unknown",
            "active_tail": "unknown",
            "unavailable_sources": sum(c.coverage["unavailable_sources"] for c in ledger.contributions),
            "partial_lines": sum(c.coverage["partial_lines"] for c in ledger.contributions),
        },
        "tokens": _tokens(responses),
        "time": _time(turns, responses),
        "views": {
            dimension: _view(turns, responses, dimension)
            for dimension in ("primary", "phase", "task", "feature", "model")
        },
        "associated_requirements": {
            label: sum(label in record.attribution["associated"] for record in responses)
            for label in sorted({label for record in responses for label in record.attribution["associated"]})
        },
        "cost": price(responses, rates, measured_at, vocabulary),
    }
