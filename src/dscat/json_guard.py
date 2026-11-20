# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Bound JSON syntax and nesting before validating typed boundaries."""

import json
from dataclasses import dataclass

from dscat.intake.limits import DEFAULT_LIMITS, fail


def reject_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate object keys before Pydantic could silently overwrite one."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise fail(code="INVALID_INVOCATION")
        result[key] = value
    return result


def reject_constant(_value: str) -> None:
    """Reject JSON NaN/Infinity spellings without echoing their input."""
    raise fail(code="INVALID_INVOCATION")


@dataclass
class JsonNesting:
    """Track JSON delimiters without interpreting quoted content."""

    depth: int = 0
    quoted: bool = False
    escaped: bool = False

    def feed(self, char: int) -> None:
        """Count only unquoted container delimiters and enforce the depth ceiling."""
        if self.quoted:
            if self.escaped:
                self.escaped = False
            elif char == ord("\\"):
                self.escaped = True
            elif char == ord('"'):
                self.quoted = False
        elif char == ord('"'):
            self.quoted = True
        elif char in (ord("["), ord("{")):
            self.depth += 1
            if self.depth > DEFAULT_LIMITS.depth:
                raise fail(code="INPUT_LIMIT", limit="depth")
        elif char in (ord("]"), ord("}")):
            self.depth -= 1


def check_json(raw: bytes, maximum: int) -> None:
    """Bound JSON bytes/depth and reject duplicate keys/nonfinite constants."""
    if len(raw) > maximum:
        raise fail(code="INPUT_LIMIT", limit="json_bytes")
    nesting = JsonNesting()
    for char in raw:
        nesting.feed(char)
    try:
        json.loads(raw, object_pairs_hook=reject_pairs, parse_constant=reject_constant)
    except ValueError, RecursionError:
        raise fail(code="INVALID_INVOCATION") from None
