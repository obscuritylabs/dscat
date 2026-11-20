# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Reconcile CycloneDX identities, relationships, provenance and artifact bindings."""

import hashlib
from copy import deepcopy
from typing import TYPE_CHECKING

from packaging.utils import canonicalize_name

from scripts.dependency_graph import (
    array_value,
    object_value,
    reconcile_inventory,
    text_value,
)
from scripts.evidence_models import RelationshipCorrection
from scripts.sbom import validate_sbom

if TYPE_CHECKING:
    from pydantic import JsonValue

    from scripts.dependency_graph import DependencyGraph
    from scripts.evidence_models import (
        ActualBindings,
        ArtifactProvenance,
        Distribution,
        Inventory,
    )


def binding_properties(actual: ArtifactProvenance) -> dict[str, str]:
    """Keep source, lock and both distribution identities out of mutable timestamps."""
    return {
        "dscat:source-commit": actual.source_sha,
        "dscat:source-tree": actual.source_tree,
        "dscat:lock-sha256": actual.lock_sha256,
        "dscat:wheel-sha256": actual.wheel_sha256,
        "dscat:sdist-sha256": actual.sdist_sha256,
    }


def component_objects(document: dict[str, JsonValue]) -> list[dict[str, JsonValue]]:
    """Include the application and keep generator tools outside runtime inventory."""
    metadata = object_value(document.get("metadata"))
    root = object_value(metadata.get("component"))
    return [
        root,
        *(object_value(item) for item in array_value(document.get("components"))),
    ]


def properties_of(component: dict[str, JsonValue]) -> dict[str, str]:
    """Reject ambiguous duplicate provenance properties before comparing identities."""
    properties: dict[str, str] = {}
    for raw in array_value(component.get("properties", [])):
        entry = object_value(raw)
        name = text_value(entry.get("name"))
        if name in properties:
            msg = "SBOM provenance properties must be unique."
            raise ValueError(msg)
        properties[name] = text_value(entry.get("value"))
    return properties


def declared_license(value: str) -> str:
    """Normalize only the observed MIT classifier and explicit ISC legacy label."""
    value = value.strip()
    aliases = {
        "License :: OSI Approved :: MIT License": "MIT",
        "ISC License": "ISC",
    }
    if value.casefold() in {"unknown", "noassertion", "none", ""}:
        msg = "SBOM installed license declaration is unknown."
        raise ValueError(msg)
    return aliases.get(value, value)


def component_licenses(component: dict[str, JsonValue]) -> set[str]:
    """Compare license IDs, names and expressions without inferring an assessment."""
    values: set[str] = set()
    for raw in array_value(component.get("licenses", [])):
        choice = object_value(raw)
        if "expression" in choice:
            value = text_value(choice["expression"])
        else:
            license_entry = object_value(choice.get("license"))
            value = text_value(license_entry.get("id", license_entry.get("name")))
        values.add(declared_license(value))
    return values


def component_identity(
    component: dict[str, JsonValue], inventory: dict[str, Distribution]
) -> tuple[str, str]:
    """Require exact installed version, package URL and declared license metadata."""
    name = canonicalize_name(text_value(component.get("name")), validate=True)
    version = text_value(component.get("version"))
    if name not in inventory or inventory[name].version != version:
        msg = "SBOM component does not match installed distribution metadata."
        raise ValueError(msg)
    kind = "generic" if name == "dscat" else "pypi"
    if component.get("purl") != f"pkg:{kind}/{name}@{version}":
        msg = "SBOM package URL does not match its component identity."
        raise ValueError(msg)
    expected_licenses = {declared_license(value) for value in inventory[name].licenses}
    if (
        not expected_licenses
        or component_licenses(component) != expected_licenses
        or (name == "dscat" and expected_licenses != {"LicenseRef-Proprietary"})
    ):
        msg = "SBOM component licenses do not match installed declarations."
        raise ValueError(msg)
    return name, text_value(component.get("bom-ref"))


def check_distribution_provenance(
    component: dict[str, JsonValue], package: Distribution
) -> None:
    """Bind a dependency to its verified selected immutable distribution archive."""
    if package.artifact_sha256 is None or package.artifact_url is None:
        msg = "Selected dependency artifact provenance is unavailable."
        raise ValueError(msg)
    hashes = array_value(component.get("hashes", []))
    expected_hash = {"alg": "SHA-256", "content": package.artifact_sha256}
    references = array_value(component.get("externalReferences", []))
    if expected_hash not in hashes or not any(
        object_value(reference).get("type") == "distribution"
        and object_value(reference).get("url") == package.artifact_url
        and expected_hash in array_value(object_value(reference).get("hashes", []))
        for reference in references
    ):
        msg = "SBOM dependency provenance does not match the selected distribution."
        raise ValueError(msg)


def reconcile_sbom(
    raw: bytes,
    inventory: Inventory,
    expected: DependencyGraph,
    actual: ActualBindings,
) -> None:
    """Reject missing components, edges, licenses or source/artifact identities."""
    if hashlib.sha256(raw).hexdigest() != actual.sbom_sha256:
        msg = "SBOM byte identity does not match the candidate."
        raise ValueError(msg)
    document = validate_sbom(raw)
    installed = {package.name: package for package in inventory.distributions}
    references: dict[str, str] = {}
    names: set[str] = set()
    components = component_objects(document)
    for component in components:
        name, reference = component_identity(component, installed)
        if reference in references or name in names:
            msg = "SBOM component identities must be unique."
            raise ValueError(msg)
        references[reference] = name
        names.add(name)
        if name != "dscat":
            check_distribution_provenance(component, installed[name])
    if names != set(expected.versions):
        msg = "SBOM component set does not match the selected runtime environment."
        raise ValueError(msg)
    root = components[0]
    if root.get("name") != "dscat" or root.get("version") != actual.version:
        msg = "SBOM root application identity does not match the release."
        raise ValueError(msg)
    properties = properties_of(root)
    if any(
        properties.get(key) != value
        for key, value in binding_properties(actual).items()
    ):
        msg = "SBOM source or distribution binding does not match the candidate."
        raise ValueError(msg)
    edges = sbom_edges(document, references)
    if edges != expected.edges:
        msg = "SBOM dependency relationships do not match the selected runtime graph."
        raise ValueError(msg)


def sbom_edges(
    document: dict[str, JsonValue], references: dict[str, str]
) -> dict[str, set[str]]:
    """Require one edge record for each component and only known distinct targets."""
    edges: dict[str, set[str]] = {}
    for raw in array_value(document.get("dependencies")):
        entry = object_value(raw)
        reference = text_value(entry.get("ref"))
        targets = [
            text_value(value) for value in array_value(entry.get("dependsOn", []))
        ]
        if (
            reference not in references
            or references[reference] in edges
            or len(targets) != len(set(targets))
            or not set(targets) <= set(references)
        ):
            msg = "SBOM dependency references are ambiguous or unresolved."
            raise ValueError(msg)
        edges[references[reference]] = {references[target] for target in targets}
    return edges


def enrich_sbom(
    document: dict[str, JsonValue], inventory: Inventory, actual: ArtifactProvenance
) -> dict[str, JsonValue]:
    """Add verified provenance to an owned generator result without private paths."""
    document = deepcopy(document)
    installed = {package.name: package for package in inventory.distributions}
    components = component_objects(document)
    root = components[0]
    root["purl"] = f"pkg:generic/dscat@{actual.version}"
    root["properties"] = [
        {"name": key, "value": value}
        for key, value in binding_properties(actual).items()
    ]
    for component in components[1:]:
        name = canonicalize_name(text_value(component.get("name")), validate=True)
        if name not in installed:
            msg = "Generator returned an unknown dependency component."
            raise ValueError(msg)
        package = installed[name]
        if package.artifact_sha256 is None or package.artifact_url is None:
            msg = "Cannot enrich a dependency without verified archive provenance."
            raise ValueError(msg)
        digest: dict[str, JsonValue] = {
            "alg": "SHA-256",
            "content": package.artifact_sha256,
        }
        component["hashes"] = [digest]
        references = array_value(component.get("externalReferences", []))
        references.append(
            {"type": "distribution", "url": package.artifact_url, "hashes": [digest]}
        )
        component["externalReferences"] = references
    return document


def active_relationships(
    document: dict[str, JsonValue], inventory: Inventory, expected: DependencyGraph
) -> tuple[dict[str, JsonValue], list[RelationshipCorrection]]:
    """Resolve generator over-approximations using independently verified metadata."""
    reconcile_inventory(inventory, expected)
    document = deepcopy(document)
    references: dict[str, str] = {}
    for component in component_objects(document):
        name = canonicalize_name(text_value(component.get("name")), validate=True)
        reference = text_value(component.get("bom-ref"))
        if reference in references or name in references.values():
            msg = "Generator component identities must be unique."
            raise ValueError(msg)
        references[reference] = name
    if set(references.values()) != set(expected.versions):
        msg = "Generator components do not match the verified installed environment."
        raise ValueError(msg)
    generated = sbom_edges(document, references)
    if set(generated) != set(expected.edges):
        msg = "Generator omitted a runtime relationship record."
        raise ValueError(msg)
    if any(not targets <= generated[name] for name, targets in expected.edges.items()):
        msg = "Generator omitted an active runtime dependency relationship."
        raise ValueError(msg)
    corrections = [
        RelationshipCorrection(
            package=name,
            generated=sorted(generated[name]),
            installed=sorted(targets),
        )
        for name, targets in sorted(expected.edges.items())
        if generated[name] != targets
    ]
    by_name = {name: reference for reference, name in references.items()}
    document["dependencies"] = [
        {
            "ref": by_name[name],
            "dependsOn": [by_name[target] for target in sorted(targets)],
        }
        for name, targets in sorted(expected.edges.items())
    ]
    return document, corrections
