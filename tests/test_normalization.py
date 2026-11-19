# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Observable normalization, identifier, reference and exact-quantity behavior."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from dscat.normalization import (
    MAX_BYTES,
    normalize_https,
    normalize_identifier,
    normalize_namespace,
    normalize_quantity,
    normalize_reference,
    normalize_text,
    normalize_timestamp,
)


def test_text_preserves_meaning() -> None:
    """Normalize Unicode/newlines/outer space without rewriting internal text."""
    assert normalize_text("  Cafe\u0301\r\nA  B\rC  ") == "Café\nA  B\nC"
    assert normalize_text(" Unknown ") == "Unknown"
    assert normalize_text("") == ""


@pytest.mark.parametrize("value", [None, True, 12, b"text", [], {}])
def test_text_and_identifier_reject_nontext(value: object) -> None:
    """Typed boundaries cannot quietly stringify arbitrary values."""
    with pytest.raises(ValueError, match="Expected text"):
        normalize_text(value)
    with pytest.raises(ValueError, match="Expected an identifier"):
        normalize_identifier(value)


@pytest.mark.parametrize("value", ["a", "A" * 128, "  A-0._:B  ", "1"])
def test_valid_identifiers(value: str) -> None:
    """The inclusive ID length and ASCII grammar preserve case."""
    assert normalize_identifier(value) == value.strip(" ")


@pytest.mark.parametrize(
    "value",
    [
        "",
        " ",
        "a" * 129,
        ".",
        "..",
        "_a",
        "a/b",
        "a\\b",
        "a%2fb",
        "a b",
        "a\n",
        "\ta",
        "é",
        "a\x00",
    ],
)
def test_invalid_identifiers(value: str) -> None:
    """Paths, controls, whitespace, Unicode and oversized IDs fail closed."""
    with pytest.raises(ValueError, match="ASCII ID"):
        normalize_identifier(value)


@pytest.mark.parametrize(
    "value",
    [
        "https://example.org/a?b=c#d",
        "urn:example:dataset-001",
        "https://example.org:443/a%20b",
        "https://example.org/#",
    ],
)
def test_valid_references(value: str) -> None:
    """References are inert and retain path, query, fragment and port spelling."""
    assert normalize_reference(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "http://example.org",
        "file:///a",
        "javascript:alert(1)",
        "relative",
        "https:///a",
        "urn:missing",
        "https://u:p@example.org/",
        "https://@example.org/",
        "https://example.org/a b",
        "https://example.org/\n",
        "https://example.org/\x00",
        "https://example.org:bad/",
        "https://example.org:99999/",
        "https://example.org\\bad",
        "https://example.org/%zz",
        "https://[invalid]/",
        "https://host<>/",
        "https://host|x/",
        "https://example.org/{value}",
        "https://example.org/array[0]",
        "https://example.org/?q=[]",
        "https://example.org/#part#extra",
    ],
)
def test_invalid_references(value: str) -> None:
    """No credentials, unsafe scheme, control or malformed URI is accepted."""
    with pytest.raises(
        ValueError, match=r"Reference|reference|URI|Port|port|address|IPv"
    ):
        normalize_reference(value)


def test_https_and_namespace_constraints() -> None:
    """Namespaces require distinct concatenation syntax without hidden query state."""
    assert normalize_https("https://example.org/a?b=c") == "https://example.org/a?b=c"
    assert (
        normalize_namespace("https://example.org/datasets/")
        == "https://example.org/datasets/"
    )
    assert (
        normalize_namespace("https://example.org/vocab#")
        == "https://example.org/vocab#"
    )
    for value in (
        "urn:example:test",
        "https://example.org/data",
        "https://example.org/?a=b",
        "https://example.org/#part/",
        "https://example.org/?a=b#",
        "https://example.org/fragment#part#",
    ):
        with pytest.raises(ValueError, match=r"HTTPS|Namespace|Reference"):
            normalize_namespace(value)


@pytest.mark.parametrize(
    ("unit", "factor"),
    [
        ("B", 1),
        ("kB", 1000),
        ("MB", 1000**2),
        ("GB", 1000**3),
        ("TB", 1000**4),
        ("PB", 1000**5),
        ("KiB", 1024),
        ("MiB", 1024**2),
        ("GiB", 1024**3),
        ("TiB", 1024**4),
        ("PiB", 1024**5),
    ],
)
def test_exact_units(unit: str, factor: int) -> None:
    """Every supported decimal/binary unit has exact independent conversion."""
    assert normalize_quantity("1", unit) == factor
    assert normalize_quantity("0", unit) == 0


def test_quantity_boundaries() -> None:
    """Exact fractional conversion, digit ceilings and maximum bytes are inclusive."""
    assert normalize_quantity("0.001", "kB") == 1
    assert normalize_quantity("0.000000001", "GB") == 1
    assert normalize_quantity("9223372036854775807.000000000", "B") == MAX_BYTES
    assert normalize_quantity("000.00", "B") == 0


@pytest.mark.parametrize(
    ("value", "unit"),
    [
        ("-1", "B"),
        ("+1", "B"),
        ("1e3", "B"),
        ("NaN", "B"),
        ("Infinity", "B"),
        ("1,000", "B"),
        (".1", "B"),
        ("1.", "B"),
        ("0.1", "B"),
        ("1", "KB"),
        ("1", "months"),
        ("1.0000000000", "B"),
        ("9223372036854775808", "B"),
        ("10000000000000000000.000000000", "B"),
    ],
)
def test_invalid_quantities(value: str, unit: str) -> None:
    """Malformed, imprecise or unrepresentable values never round or become zero."""
    with pytest.raises(ValueError, match=r"Expected|Quantity"):
        normalize_quantity(value, unit)


def test_timestamps_normalize_to_utc() -> None:
    """Explicit offset conversion preserves the instant."""
    value = datetime(2026, 1, 1, 2, tzinfo=timezone(timedelta(hours=2)))
    assert normalize_timestamp(value) == datetime(2026, 1, 1, tzinfo=UTC)
