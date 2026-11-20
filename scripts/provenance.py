# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Select compatible locked wheels and verify their actual approved download bytes."""

import hashlib
import json
import os
import tomllib
import urllib.request
from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated, Self, override
from urllib.parse import unquote, urlsplit

from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version
from pydantic import Field, model_validator

from dscat.models.base import HttpsReference, Sha256, StrictModel, Text
from dscat.resources.registry import DOCUMENT
from scripts.artifacts import ARCHIVE_BYTES
from scripts.dependency_graph import array_value, object_value, text_value

if TYPE_CHECKING:
    from email.message import Message
    from pathlib import Path
    from typing import IO

    from packaging.tags import Tag
    from pydantic import JsonValue

    from scripts.dependency_graph import DependencyGraph


class PinnedWheel(StrictModel):
    """Bind a safe wheel basename to an approved source and exact archive bytes."""

    package: Text
    version: Text
    filename: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.+!-]*\.whl$")]
    url: HttpsReference
    sha256: Sha256
    size: Annotated[int, Field(gt=0, le=ARCHIVE_BYTES)]

    @model_validator(mode="after")
    def approved_source(self) -> Self:
        """Reject changed hosts, URL parameters and mismatched local basenames."""
        parsed = urlsplit(self.url)
        if (
            parsed.netloc != "files.pythonhosted.org"
            or not parsed.path.startswith("/packages/")
            or parsed.query
            or parsed.fragment
            or self.filename != unquote(parsed.path.rsplit("/", 1)[-1])
        ):
            msg = "Pinned wheel source or filename is unapproved."
            raise ValueError(msg)
        return self


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """An approved immutable URL cannot delegate a request to another endpoint."""

    @override
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: Message,
        newurl: str,
    ) -> urllib.request.Request | None:
        """Let urllib fail a redirect rather than follow its new target."""
        return None


def wheel_pin(package: str, version: str, value: JsonValue) -> PinnedWheel:
    """Refuse unapproved hosts, non-SHA256 hashes and URL credentials/parameters."""
    entry = object_value(value)
    url = text_value(entry.get("url"))
    parsed = urlsplit(url)
    digest = text_value(entry.get("hash"))
    if (
        parsed.scheme != "https"
        or parsed.netloc != "files.pythonhosted.org"
        or not parsed.path.startswith("/packages/")
        or parsed.query
        or parsed.fragment
        or not digest.startswith("sha256:")
    ):
        msg = "Locked wheel source or hash algorithm is unapproved."
        raise ValueError(msg)
    return PinnedWheel.model_validate(
        {
            "package": package,
            "version": version,
            "filename": unquote(parsed.path.rsplit("/", 1)[-1]),
            "url": url,
            "sha256": digest.removeprefix("sha256:"),
            "size": entry.get("size"),
        }
    )


def selected_wheels(
    raw: bytes, expected: DependencyGraph, tags: list[Tag]
) -> dict[str, PinnedWheel]:
    """Use the target interpreter's tag preference without resolving new versions."""
    document = DOCUMENT.validate_json(json.dumps(tomllib.loads(raw.decode())))
    packages = {
        text_value(object_value(entry).get("name")): object_value(entry)
        for entry in array_value(document.get("package"))
    }
    ranks = {tag: rank for rank, tag in enumerate(tags)}
    selected: dict[str, PinnedWheel] = {}
    for name, version in expected.versions.items():
        if name == "dscat":
            continue
        package = packages.get(name)
        if package is None or package.get("version") != version:
            msg = "Selected dependency is absent from the exact lock."
            raise ValueError(msg)
        candidates: list[tuple[int, str, PinnedWheel]] = []
        for value in array_value(package.get("wheels", [])):
            pin = wheel_pin(name, version, value)
            wheel_name, wheel_version, _build, wheel_tags = parse_wheel_filename(
                pin.filename
            )
            if canonicalize_name(wheel_name) != name or wheel_version != Version(
                version
            ):
                msg = "Locked wheel filename does not match its package identity."
                raise ValueError(msg)
            compatible = wheel_tags & ranks.keys()
            if compatible:
                candidates.append(
                    (min(ranks[tag] for tag in compatible), pin.filename, pin)
                )
        if not candidates:
            msg = "No compatible locked wheel is available for this environment."
            raise ValueError(msg)
        selected[name] = min(candidates, key=lambda candidate: candidate[:2])[2]
    return selected


def download_wheel(pin: PinnedWheel, directory: Path) -> None:
    """Verify status, source, size and SHA256 before creating any installable file."""
    pin = PinnedWheel.model_validate(pin.model_dump())
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(pin.url, timeout=30) as response:
        final_url: object = response.geturl()
        status: object = response.getcode()
        if final_url != pin.url or status != HTTPStatus.OK:
            msg = "Wheel download did not retain its approved source."
            raise ValueError(msg)
        raw: object = response.read(ARCHIVE_BYTES + 1)
    if (
        not isinstance(raw, bytes)
        or len(raw) != pin.size
        or hashlib.sha256(raw).hexdigest() != pin.sha256
    ):
        msg = "Downloaded wheel bytes do not match the selected lock artifact."
        raise ValueError(msg)
    with (directory / pin.filename).open("xb") as stream:
        if stream.write(raw) != len(raw):
            msg = "Verified wheel could not be written completely."
            raise OSError(msg)
        stream.flush()
        os.fsync(stream.fileno())
