# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Pinned SBOM schemas and semantic inventory/provenance reconciliation."""

import hashlib
import json
import shutil
import socket
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urljoin

import pytest
from referencing.exceptions import Unresolvable
from scripts import sbom
from scripts.dependency_graph import locked_graph
from scripts.sbom_reconciliation import enrich_sbom, reconcile_sbom

from dscat.resources.registry import DOCUMENT
from tests.test_dependency_graph import LOCK, inventory
from tests.test_release_evidence import candidate

if TYPE_CHECKING:
    from pydantic import JsonValue
    from scripts.dependency_graph import DependencyGraph
    from scripts.evidence_models import ActualBindings, Inventory


def payload() -> tuple[bytes, Inventory, DependencyGraph, ActualBindings]:
    """Generate three synthetic components with explicit archive provenance."""
    installed = inventory()
    distributions = [
        package
        if package.name == "dscat"
        else package.model_copy(
            update={
                "artifact_sha256": hashlib.sha256(package.name.encode()).hexdigest(),
                "artifact_url": f"https://example.org/synthetic/{package.name}-1.whl",
            }
        )
        for package in installed.distributions
    ]
    installed = installed.model_copy(update={"distributions": distributions})
    graph = locked_graph(LOCK, installed.marker_environment)
    _, actual = candidate()
    document = DOCUMENT.validate_python(
        {
            "$schema": sbom.BOM_URI,
            "bomFormat": "CycloneDX",
            "specVersion": "1.6",
            "version": 1,
            "metadata": {
                "component": {
                    "type": "application",
                    "name": "dscat",
                    "version": "0.1.0",
                    "bom-ref": "root",
                    "licenses": [{"license": {"name": "LicenseRef-Proprietary"}}],
                }
            },
            "components": [
                {
                    "type": "library",
                    "name": name,
                    "version": "1",
                    "bom-ref": name,
                    "purl": f"pkg:pypi/{name}@1",
                    "licenses": [{"license": {"id": "MIT"}}],
                }
                for name in ["foo", "baz"]
            ],
            "dependencies": [
                {"ref": "root", "dependsOn": ["foo"]},
                {"ref": "foo", "dependsOn": ["baz"]},
                {"ref": "baz"},
            ],
        }
    )
    enriched = enrich_sbom(document, installed, actual)
    raw = json.dumps(enriched, sort_keys=True).encode()
    actual = actual.model_copy(update={"sbom_sha256": hashlib.sha256(raw).hexdigest()})
    return raw, installed, graph, actual


def test_actual_cyclonedx_schema_and_complete_semantic_graph() -> None:
    """Validate a complete graph against pinned 1.6 resources and exact inventory."""
    raw, installed, graph, actual = payload()
    assert sbom.validate_sbom(raw)["specVersion"] == "1.6"
    reconcile_sbom(raw, installed, graph, actual)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_component",
        "extra_component",
        "duplicate_component",
        "version",
        "purl",
        "license",
        "provenance",
    ],
)
def test_component_mutations_are_refused(mutation: str) -> None:
    """Refuse absent runtime software, licenses and mismatched provenance."""
    raw, installed, graph, actual = payload()
    document = json.loads(raw)
    components = document["components"]
    if mutation == "missing_component":
        components.pop()
    elif mutation == "extra_component":
        components.append(
            components[0] | {"name": "unexpected", "bom-ref": "unexpected"}
        )
    elif mutation == "duplicate_component":
        components.append(components[0] | {"description": "synthetic duplicate"})
    elif mutation == "version":
        components[0]["version"] = "2"
    elif mutation == "purl":
        components[0]["purl"] = "pkg:pypi/another-package@1"
    elif mutation == "license":
        components[0].pop("licenses")
    else:
        components[0]["hashes"][0]["content"] = "0" * 64
    altered = json.dumps(document).encode()
    actual = actual.model_copy(
        update={"sbom_sha256": hashlib.sha256(altered).hexdigest()}
    )
    with pytest.raises(ValueError, match="SBOM"):
        reconcile_sbom(altered, installed, graph, actual)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "unknown_ref",
        "duplicate_ref",
        "missing_edge",
        "unknown_target",
        "duplicate_target",
    ],
)
def test_relationship_mutations_are_refused(mutation: str) -> None:
    """Require all edge records and exact selected dependency relationships."""
    raw, installed, graph, actual = payload()
    document = json.loads(raw)
    dependencies = document["dependencies"]
    if mutation == "missing":
        dependencies.pop()
    elif mutation == "unknown_ref":
        dependencies[0]["ref"] = "unexpected"
    elif mutation == "duplicate_ref":
        dependencies.append(dependencies[0])
    elif mutation == "missing_edge":
        dependencies[0]["dependsOn"] = []
    elif mutation == "unknown_target":
        dependencies[0]["dependsOn"] = ["unexpected"]
    else:
        dependencies[0]["dependsOn"] *= 2
    altered = json.dumps(document).encode()
    actual = actual.model_copy(
        update={"sbom_sha256": hashlib.sha256(altered).hexdigest()}
    )
    with pytest.raises(ValueError, match="SBOM"):
        reconcile_sbom(altered, installed, graph, actual)


@pytest.mark.parametrize(
    "name",
    [
        "source_sha",
        "source_tree",
        "lock_sha256",
        "wheel_sha256",
        "sdist_sha256",
        "sbom_sha256",
        "version",
    ],
)
def test_source_and_artifact_bindings_are_independent(name: str) -> None:
    """Invalidate provenance when source, lock or either distribution changes."""
    raw, installed, graph, actual = payload()
    values = actual.model_dump()
    values[name] = "9" * len(values[name]) if name != "version" else "0.2.0"
    with pytest.raises(ValueError, match="SBOM"):
        reconcile_sbom(raw, installed, graph, type(actual).model_validate(values))


def test_schema_version_unknown_fields_and_nonobjects_are_refused() -> None:
    """Enforce version 1.6 separately from the official schema version text."""
    for value in (
        {"bomFormat": "CycloneDX", "specVersion": "1.5"},
        {"bomFormat": "CycloneDX", "specVersion": "1.6", "unexpected": True},
        [],
    ):
        with pytest.raises(ValueError, match="SBOM"):
            sbom.validate_sbom(json.dumps(value).encode())


def test_schema_closure_and_unknown_retrieval_are_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve local fragments and deny unknown URIs before networking."""

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Schema validation attempted network access.")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    bundle = sbom.load_schema_bundle()

    def references(value: JsonValue) -> list[str]:
        if isinstance(value, dict):
            reference = value.get("$ref")
            found = [reference] if isinstance(reference, str) else []
            return found + [
                ref for child in value.values() for ref in references(child)
            ]
        if isinstance(value, list):
            return [ref for child in value for ref in references(child)]
        return []

    count = 0
    for identifier, schema in bundle.schemas.items():
        for reference in references(schema):
            bundle.registry.resolver().lookup(urljoin(identifier, reference))
            count += 1
    minimum_references = 100
    assert count > minimum_references
    with pytest.raises(Unresolvable):
        bundle.registry.resolver().lookup("https://example.org/unknown-schema")


@pytest.mark.parametrize(
    "name",
    [
        "resource-manifest.json",
        "bom-1.6.schema.json",
        "spdx.schema.json",
        "jsf-0.82.schema.json",
        "LICENSE",
    ],
)
def test_resource_corruption_stops_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Corrupting any schema or its full license notice invalidates the resource set."""
    source = Path(sbom.__file__).parent / "resources/cyclonedx"
    target = tmp_path / "resources/cyclonedx"
    shutil.copytree(source, target)
    (target / name).write_bytes(b"synthetic corruption")
    monkeypatch.setattr(sbom, "__file__", str(tmp_path / "sbom.py"))
    with pytest.raises(ValueError, match="CycloneDX"):
        sbom.load_schema_bundle()
