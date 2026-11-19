# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Bounded explicit TOML decoding with fixed failure messages."""

import tomllib

from dscat.models.configuration import ExportConfiguration

MAX_CONFIG_BYTES = 32 * 1024**2
MAX_CONFIG_DEPTH = 64


def check_toml_depth(text: str) -> None:
    """Bound collection nesting before parsing, excluding strings and comments."""
    depth = 0
    quote = ""
    index = 0
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\" and quote.startswith('"'):
                index += 2
                continue
            if text.startswith(quote, index):
                index += len(quote)
                quote = ""
                continue
        elif char == "#":
            newline = text.find("\n", index)
            index = len(text) if newline < 0 else newline
            continue
        elif char in ('"', "'"):
            quote = char * 3 if text.startswith(char * 3, index) else char
            index += len(quote)
            continue
        elif char in "[{":
            depth += 1
            if depth > MAX_CONFIG_DEPTH:
                msg = "Configuration exceeds the supported nesting depth."
                raise ValueError(msg)
        elif char in "]}":
            depth -= 1
        index += 1


def parse_configuration(raw: bytes) -> ExportConfiguration:
    """Validate bounded explicit TOML bytes without external discovery."""
    if len(raw) > MAX_CONFIG_BYTES:
        msg = "Configuration exceeds the supported byte limit."
        raise ValueError(msg)
    try:
        text = raw.decode("utf-8")
        check_toml_depth(text)
        data = tomllib.loads(text)
    except (UnicodeError, tomllib.TOMLDecodeError, RecursionError) as error:
        msg = "Configuration must be valid UTF-8 TOML."
        raise ValueError(msg) from error
    pending: list[tuple[object, int]] = [(data, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > MAX_CONFIG_DEPTH:
            msg = "Configuration exceeds the supported nesting depth."
            raise ValueError(msg)
        if isinstance(item, dict):
            pending.extend((value, depth + 1) for value in item.values())
        elif isinstance(item, list):
            pending.extend((value, depth + 1) for value in item)
    return ExportConfiguration.model_validate(data)
