# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Pure normalization for explicit metadata; no network or filesystem access."""

import re
import unicodedata
from datetime import UTC, date, datetime
from decimal import Decimal, localcontext
from urllib.parse import urlsplit

MAX_BYTES = 2**63 - 1
UNIT_FACTORS = {
    "B": 1,
    "kB": 1000,
    "MB": 1000**2,
    "GB": 1000**3,
    "TB": 1000**4,
    "PB": 1000**5,
    "KiB": 1024,
    "MiB": 1024**2,
    "GiB": 1024**3,
    "TiB": 1024**4,
    "PiB": 1024**5,
}


def normalize_text(value: object) -> str:
    """Normalize text while preserving internal spacing and case."""
    if not isinstance(value, str):
        msg = "Expected text."
        raise ValueError(msg)  # noqa: TRY004 -- Pydantic validators require ValueError.
    return unicodedata.normalize(
        "NFC", value.replace("\r\n", "\n").replace("\r", "\n")
    ).strip()


def normalize_identifier(value: object) -> str:
    """Validate an opaque, case-sensitive identifier without interpreting paths."""
    if not isinstance(value, str):
        msg = "Expected an identifier."
        raise ValueError(msg)  # noqa: TRY004 -- Pydantic validators require ValueError.
    result = unicodedata.normalize("NFC", value.strip(" "))
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", result) is None:
        msg = "Use 1-128 ASCII ID characters, starting with a letter or digit."
        raise ValueError(msg)
    return result


def normalize_reference(value: object) -> str:
    """Accept inert HTTPS or URN references, rejecting credentials and controls."""
    if isinstance(value, str) and any(
        unicodedata.category(c).startswith("C") for c in value
    ):
        msg = "Reference contains unsupported controls."
        raise ValueError(msg)
    result = normalize_text(value)
    if any(c.isspace() or unicodedata.category(c).startswith("C") for c in result):
        msg = "Reference contains unsupported whitespace or controls."
        raise ValueError(msg)
    if "\\" in result or re.search(r"%(?![0-9A-Fa-f]{2})", result):
        msg = "Reference contains invalid URI characters."
        raise ValueError(msg)
    parts = urlsplit(result)
    if (
        parts.scheme == "https"
        and bool(parts.hostname)
        and parts.username is None
        and parts.password is None
    ):
        # Accessing port also validates its syntax and range without making a request.
        _ = parts.port
        return result
    if parts.scheme == "urn" and re.fullmatch(
        r"urn:[A-Za-z0-9][A-Za-z0-9-]*:.+", result
    ):
        return result
    msg = "Expected an absolute HTTPS or URN reference without user information."
    raise ValueError(msg)


def normalize_https(value: object) -> str:
    """Restrict a reference to HTTPS without changing path or query semantics."""
    result = normalize_reference(value)
    if not result.startswith("https://"):
        msg = "Expected an absolute HTTPS reference."
        raise ValueError(msg)
    return result


def normalize_namespace(value: object) -> str:
    """Validate an explicit HTTPS namespace suitable for one escaped ID suffix."""
    result = normalize_https(value)
    parts = urlsplit(result)
    if parts.query or parts.fragment or not result.endswith(("/", "#")):
        msg = "Namespace must have no query and end in a slash or empty fragment."
        raise ValueError(msg)
    return result


def normalize_quantity(value: str, unit: str) -> int:
    """Convert a bounded decimal quantity exactly to integral bytes."""
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value) is None or unit not in UNIT_FACTORS:
        msg = "Expected a nonnegative decimal string and supported byte unit."
        raise ValueError(msg)
    whole, _, fraction = value.partition(".")
    significant = (whole + fraction).lstrip("0")
    if len(significant) > 28 or len(fraction) > 9:  # noqa: PLR2004 -- approved decimal ceilings.
        msg = "Quantity exceeds 28 significant or 9 fractional digits."
        raise ValueError(msg)
    with localcontext() as context:
        context.prec = 60
        normalized = Decimal(value) * UNIT_FACTORS[unit]
        if normalized != normalized.to_integral_value() or normalized > MAX_BYTES:
            msg = "Expected integral normalized bytes within the supported range."
            raise ValueError(msg)
        return int(normalized)


def normalize_timestamp(value: datetime) -> datetime:
    """Represent an explicitly timezone-aware timestamp in UTC."""
    return value.astimezone(UTC)


def parse_date(value: object) -> date:
    """Accept a Gregorian date or its exact versioned YYYY-MM-DD encoding."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return date.fromisoformat(value)
    msg = "Expected a Gregorian YYYY-MM-DD date."
    raise ValueError(msg)


def parse_timestamp(value: object) -> datetime:
    """Accept an explicitly offset timestamp without numeric or date coercion."""
    if isinstance(value, str) and re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
        r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})",
        value,
    ):
        value = datetime.fromisoformat(value)
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        msg = "Expected a timestamp with an explicit timezone offset."
        raise ValueError(msg)
    return normalize_timestamp(value)
