# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Package-local resource integrity, resolver closure and network denial."""

import hashlib
import json
import shutil
import socket
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urldefrag, urljoin

import pytest
from referencing.exceptions import Unresolvable

from dscat.resources import registry

if TYPE_CHECKING:
    from pydantic import JsonValue

RESOURCE_COUNT = 45
RESEARCH = Path(__file__).parents[1] / "docs/evidence/architecture"
VENDOR = Path(__file__).parents[1] / "src/dscat/resources/vendor"


def references(value: JsonValue, base: str) -> list[str]:
    """Enumerate all reference types, retaining explicit nested base identities."""
    result: list[str] = []
    if isinstance(value, dict):
        identity = value.get("$id")
        if isinstance(identity, str):
            base = urljoin(base, identity)
        for key, child in value.items():
            if key in {
                "$schema",
                "$ref",
                "$dynamicRef",
                "$recursiveRef",
            } and isinstance(child, str):
                result.append(urljoin(base, child))
            else:
                result.extend(references(child, base))
    elif isinstance(value, list):
        for child in value:
            result.extend(references(child, base))
    return result


def test_complete_package_bytes_and_every_reference_are_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All45 exact resources/42schemas and reference fragments resolve locally."""

    def denied(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Resource loader attempted a network operation.")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    assert (VENDOR / "resource-manifest.json").read_bytes() == (
        RESEARCH / "resource-manifest.json"
    ).read_bytes()
    bundle = registry.load_registry()
    assert len(bundle.schemas) == registry.SCHEMA_COUNT
    manifest = registry.ResourceManifest.model_validate_json(
        (VENDOR / "resource-manifest.json").read_bytes()
    )
    assert len(manifest.resources) == RESOURCE_COUNT
    for entry in manifest.resources:
        assert (VENDOR / entry.path).read_bytes() == (
            RESEARCH / entry.path
        ).read_bytes()
    seen: set[str] = set()
    for uri, schema in bundle.schemas.items():
        resolver = bundle.registry.resolver(uri)
        for reference in references(schema, uri):
            document, _fragment = urldefrag(reference)
            assert document in bundle.schemas
            resolver.lookup(reference)
            seen.add(document)
    assert len(seen) == registry.SCHEMA_COUNT
    with pytest.raises(Unresolvable):
        bundle.registry.resolver().lookup("https://example.org/unbundled.json")


@pytest.mark.parametrize(
    "mutation", ["manifest", "missing_manifest", "resource", "missing_resource"]
)
def test_missing_or_modified_package_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    """Neither a corrupt manifest nor an altered resource can become trusted input."""
    shutil.copytree(VENDOR, tmp_path / "vendor")
    monkeypatch.setattr(registry, "files", lambda _package: tmp_path)
    path = (
        tmp_path
        / "vendor"
        / (
            "resource-manifest.json"
            if mutation.endswith("manifest")
            else "resources/dcat-Catalog.json"
        )
    )
    if mutation.startswith("missing"):
        path.unlink()
    else:
        path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(registry.ResourceError, match="Packaged validation resources"):
        registry.load_registry()


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate_path",
        "duplicate_uri",
        "wrong_id",
        "missing_uri",
        "invalid_json",
        "unknown_dialect",
        "bad_shape",
    ],
)
def test_malformed_new_candidate_manifest_cannot_register_resources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    """Even a newly pinned candidate must satisfy structural and resolver fences."""
    shutil.copytree(VENDOR, tmp_path / "vendor")
    monkeypatch.setattr(registry, "files", lambda _package: tmp_path)
    manifest_path = tmp_path / "vendor/resource-manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    entries = manifest["resources"]
    if mutation == "duplicate_path":
        entries[1] = entries[0]
    elif mutation == "duplicate_uri":
        entries[1]["resolver_uri"] = entries[0]["resolver_uri"]
    elif mutation == "missing_uri":
        del entries[0]["resolver_uri"]
    elif mutation == "bad_shape":
        manifest["extra"] = "synthetic"
    else:
        path = tmp_path / "vendor" / entries[0]["path"]
        schema = json.loads(path.read_bytes())
        if mutation == "wrong_id":
            schema["$id"] = "https://example.org/incorrect"
        elif mutation == "unknown_dialect":
            schema["$schema"] = "https://example.org/unbundled-dialect"
        raw = (
            b'{"duplicate":1,"duplicate":2}'
            if mutation == "invalid_json"
            else json.dumps(schema).encode()
        )
        path.write_bytes(raw)
        entries[0]["sha256"] = hashlib.sha256(raw).hexdigest()
    raw_manifest = json.dumps(manifest).encode()
    manifest_path.write_bytes(raw_manifest)
    monkeypatch.setattr(
        registry, "MANIFEST_SHA256", hashlib.sha256(raw_manifest).hexdigest()
    )
    with pytest.raises(registry.ResourceError):
        registry.load_registry()
