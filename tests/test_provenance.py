# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Select compatible wheels and verify approved source downloads."""

import hashlib
import io
import urllib.error
import urllib.request
import urllib.response
from email.message import Message
from typing import TYPE_CHECKING, override

import pytest
from packaging.tags import Tag
from pydantic import ValidationError
from scripts import provenance
from scripts.dependency_graph import DependencyGraph

if TYPE_CHECKING:
    from pathlib import Path

RAW = b"synthetic wheel bytes"
BASE = "https://files.pythonhosted.org/packages/synthetic/"
FILENAME = "foo-1-py3-none-any.whl"
URL = BASE + FILENAME


def wheel() -> provenance.PinnedWheel:
    """Bind a synthetic byte sequence to a safe selected wheel name."""
    return provenance.PinnedWheel(
        package="foo",
        version="1",
        filename=FILENAME,
        url=URL,
        sha256=hashlib.sha256(RAW).hexdigest(),
        size=len(RAW),
    )


def test_compatible_tags_choose_target_preference_without_resolution() -> None:
    """A preferred native wheel wins over a compatible generic wheel at the same pin."""
    native_name = "foo-1-cp315-cp315-macosx_11_0_arm64.whl"
    digest = "a" * 64
    raw = (
        '[[package]]\nname="foo"\nversion="1"\nwheels=[\n'
        f'{{url="{URL}",hash="sha256:{digest}",size=12}},\n'
        f'{{url="{BASE + native_name}",hash="sha256:{digest}",size=12}}]\n'
    ).encode()
    graph = DependencyGraph(
        versions={"dscat": "0.1.0", "foo": "1"},
        edges={"dscat": {"foo"}, "foo": set()},
        extras={"dscat": set(), "foo": set()},
        requested_extras={"dscat": {"foo": set()}, "foo": {}},
    )
    selected = provenance.selected_wheels(
        raw,
        graph,
        [Tag("cp315", "cp315", "macosx_11_0_arm64"), Tag("py3", "none", "any")],
    )
    assert selected["foo"].filename == native_name
    with pytest.raises(ValueError, match="compatible locked wheel"):
        provenance.selected_wheels(raw, graph, [])
    with pytest.raises(ValueError, match="absent from the exact lock"):
        provenance.selected_wheels(
            raw.replace(b'version="1"', b'version="2"'),
            graph,
            [Tag("py3", "none", "any")],
        )
    with pytest.raises(ValueError, match="filename does not match"):
        provenance.selected_wheels(
            raw.replace(b"foo-1-", b"bar-1-"), graph, [Tag("py3", "none", "any")]
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://files.pythonhosted.org/packages/synthetic/" + FILENAME,
        "https://example.org/packages/" + FILENAME,
        URL + "?token=synthetic",
        URL + "#fragment",
        "https://files.pythonhosted.org/unapproved/" + FILENAME,
    ],
)
def test_unapproved_lock_sources_are_refused(url: str) -> None:
    """A hash does not authorize fetching alternate schemes, hosts or URL parameters."""
    with pytest.raises(ValueError, match="unapproved"):
        provenance.wheel_pin(
            "foo", "1", {"url": url, "hash": "sha256:" + "a" * 64, "size": 12}
        )


class Reply(urllib.response.addinfourl):
    """A real urllib response wrapper keeps the test on the ordinary opener path."""

    msg = "Synthetic reply"


class Transport(urllib.request.BaseHandler):
    """Intercept HTTPS without opening sockets and record attempted request targets."""

    handler_order = 100

    def __init__(self, *, raw: bytes = RAW, status: int = 200, url: str = URL) -> None:
        """Supply a controlled body/status and retain only the observed URL list."""
        self.raw = raw
        self.status = status
        self.url = url
        self.calls: list[str] = []

    def https_open(self, request: urllib.request.Request) -> Reply:
        """Serve an in-memory HTTPS response through urllib's real processors."""
        self.calls.append(request.full_url)
        headers = Message()
        headers["Location"] = "https://example.org/unapproved-target"
        return Reply(io.BytesIO(self.raw), headers, self.url, self.status)


def attach(monkeypatch: pytest.MonkeyPatch, transport: Transport) -> None:
    """Keep default urllib processing and install only the socket-free transport."""
    original = urllib.request.build_opener

    def build(handler: provenance.NoRedirect) -> urllib.request.OpenerDirector:
        return original(handler, transport)

    monkeypatch.setattr(urllib.request, "build_opener", build)


def test_actual_response_hash_and_exclusive_verified_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Install only verified bytes and preserve any existing wheel file."""
    transport = Transport()
    attach(monkeypatch, transport)
    provenance.download_wheel(wheel(), tmp_path)
    assert (tmp_path / FILENAME).read_bytes() == RAW
    with pytest.raises(FileExistsError):
        provenance.download_wheel(wheel(), tmp_path)
    assert (tmp_path / FILENAME).read_bytes() == RAW


@pytest.mark.parametrize("kind", ["size", "hash", "source", "status", "redirect"])
def test_changed_response_never_creates_installable_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """Wrong bytes, origins and redirects cannot silently change approved provenance."""
    raw = RAW[:-1] if kind == "size" else b"x" * len(RAW) if kind == "hash" else RAW
    transport = Transport(
        raw=raw,
        url="https://example.org/unapproved" if kind == "source" else URL,
        status=201 if kind == "status" else 302 if kind == "redirect" else 200,
    )
    attach(monkeypatch, transport)
    if kind == "redirect":
        with pytest.raises(urllib.error.HTTPError):
            provenance.download_wheel(wheel(), tmp_path)
        assert transport.calls == [URL]
    else:
        with pytest.raises(ValueError, match=r"[Ww]heel|Downloaded"):
            provenance.download_wheel(wheel(), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_revalidate_model_copy_before_any_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An invalid typed-object mutation cannot bypass the source allowlist."""
    transport = Transport()
    attach(monkeypatch, transport)
    changed = wheel().model_copy(update={"url": "https://example.org/unapproved"})
    with pytest.raises(ValidationError):
        provenance.download_wheel(changed, tmp_path)
    assert transport.calls == []


def test_partial_verified_archive_write_is_an_operational_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Successful retrieval cannot conceal an incomplete local archive write."""

    class ShortWriter(io.BytesIO):
        """Simulate a filesystem that accepts fewer bytes than requested."""

        @override
        def write(self, buffer: object, /) -> int:
            """Report a short write without committing any artifact."""
            assert isinstance(buffer, bytes)
            return len(buffer) - 1

    attach(monkeypatch, Transport())
    monkeypatch.setattr(
        type(tmp_path), "open", lambda *_args, **_options: ShortWriter()
    )
    with pytest.raises(OSError, match="written completely"):
        provenance.download_wheel(wheel(), tmp_path)
