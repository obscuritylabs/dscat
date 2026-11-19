# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Actual streaming XML ceilings and active-content rejection."""

import socket

import pytest

from dscat.intake.limits import Budget, IntakeError, Limits
from dscat.intake.xml import XmlGuard, forbidden, validate_xml


def test_xml_depth_inclusive_boundary() -> None:
    """Accept 64 open elements and reject the first additional element."""
    validate_xml(b"<a>" * 64 + b"</a>" * 64, Budget())
    with pytest.raises(IntakeError) as caught:
        validate_xml(b"<a>" * 65 + b"</a>" * 65, Budget())
    assert caught.value.diagnostic.limit == "depth"


def test_text_runs_attributes_and_rich_strings() -> None:
    """The full text budget includes chunks and every rich-string child."""
    validate_xml(b"<a>" + b"x" * 32767 + b"</a>", Budget())
    for raw in (
        b"<a>" + b"x" * 32768 + b"</a>",
        b'<a v="' + b"x" * 32768 + b'"/>',
        b"<si><r><t>"
        + b"x" * 20000
        + b"</t></r><r><t>"
        + b"x" * 12768
        + b"</t></r></si>",
    ):
        with pytest.raises(IntakeError) as caught:
            validate_xml(raw, Budget())
        assert caught.value.diagnostic.limit == "text"
    budget = Budget()
    validate_xml(b"<si><t>abc</t></si>", budget)
    assert budget.max_text >= len("abc")
    with pytest.raises(IntakeError, match="INVALID_WORKBOOK"):
        validate_xml(b"<si><is>x</is></si>", Budget())


def test_sheet_and_cell_boundaries_count_actual_elements() -> None:
    """Ceilings count all actual cells/sheets, including hidden or feedback content."""
    validate_xml(b"<a>" + b"<c/>" * 200000 + b"</a>", Budget())
    with pytest.raises(IntakeError) as cells:
        validate_xml(b"<a>" + b"<c/>" * 200001 + b"</a>", Budget())
    assert cells.value.diagnostic.limit == "cells"
    validate_xml(b"<a>" + b'<sheet state="hidden"/>' * 32 + b"</a>", Budget())
    with pytest.raises(IntakeError) as sheets:
        validate_xml(b"<a>" + b"<sheet/>" * 33 + b"</a>", Budget())
    assert sheets.value.diagnostic.limit == "sheets"


def test_xml_byte_boundary() -> None:
    """Actual bytes include ignored comments and reject the first byte over 16 MiB."""
    maximum = 16 * 1024**2
    raw = b"<a><!--" + b"x" * (maximum - len(b"<a><!----></a>")) + b"--></a>"
    assert len(raw) == maximum
    validate_xml(raw, Budget())
    with pytest.raises(IntakeError) as caught:
        validate_xml(raw + b" ", Budget())
    assert caught.value.diagnostic.limit == "xml"


@pytest.mark.parametrize(
    "raw",
    [
        b'<!DOCTYPE a [<!ENTITY e "x">]><a>&e;</a>',
        b'<!DOCTYPE a SYSTEM "https://example.org/external"><a/>',
        b'<!DOCTYPE a [<!ENTITY e SYSTEM "file:///synthetic">]><a/>',
        b'<a xmlns:xi="http://www.w3.org/2001/XInclude"><xi:include href="https://example.org/"/></a>',
        b'<?xml-stylesheet href="https://example.org/style"?><a/>',
    ],
)
def test_active_xml_never_resolves(raw: bytes, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject active XML before any network operation."""

    def deny(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Unexpected XML network operation")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)
    with pytest.raises(IntakeError, match="UNSAFE_INPUT"):
        validate_xml(raw, Budget())


@pytest.mark.parametrize(
    "raw", [b"", b"<a>", b"<a/><b/>", b"<a>&unknown;</a>", b"\xff"]
)
def test_malformed_xml_has_fixed_diagnostic(raw: bytes) -> None:
    """Parser exception strings and payloads are never returned."""
    with pytest.raises(IntakeError) as caught:
        validate_xml(raw, Budget())
    assert caught.value.diagnostic.code == "INVALID_WORKBOOK"
    assert str(caught.value) == "INVALID_WORKBOOK"


def test_monotonic_budget_boundary_and_callback() -> None:
    """Exactly 30 seconds is allowed; elapsed over the ceiling is rejected."""
    current = [0.0]
    budget = Budget(clock=lambda: current[0])
    current[0] = 30.0
    budget.check_time()
    current[0] = 30.001
    with pytest.raises(IntakeError) as caught:
        budget.check_time()
    assert caught.value.diagnostic.limit == "workbook_time"
    observed: list[tuple[str, int]] = []

    def record(name: str, _attrs: dict[str, str], depth: int) -> None:
        observed.append((name, depth))

    validate_xml(b"<root><child/></root>", Budget(), record)
    assert observed == [("root", 1), ("child", 2)]
    with pytest.raises(IntakeError, match="UNSAFE_INPUT"):
        forbidden("ignored")


def test_rich_text_chunks_and_namespace_names_are_bounded() -> None:
    """Split character callbacks cannot reset a rich-string or plain-text ceiling."""
    guard = XmlGuard(Budget(limits=Limits(text=3)))
    guard.start("si", {})
    guard.text("ab")
    with pytest.raises(IntakeError) as caught:
        guard.text("cd")
    assert caught.value.diagnostic.limit == "text"
    with pytest.raises(IntakeError) as name:
        validate_xml(b"<longname/>", Budget(limits=Limits(text=3)))
    assert name.value.diagnostic.limit == "text"
