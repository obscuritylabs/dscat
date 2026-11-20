# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Reconcile actual installed requirements with the lock's selected dependency graph."""

import json
import tomllib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from packaging.markers import Marker
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from dscat.resources.registry import DOCUMENT
from scripts.evidence_models import MARKER_FIELDS, Inventory, LockPackage

if TYPE_CHECKING:
    from pydantic import JsonValue

    from scripts.evidence_models import LockDependency


@dataclass(frozen=True)
class DependencyGraph:
    """Names, exact versions and complete selected direct edges are separate facts."""

    versions: dict[str, str]
    edges: dict[str, set[str]]
    extras: dict[str, set[str]]
    requested_extras: dict[str, dict[str, set[str]]]


def object_value(value: JsonValue) -> dict[str, JsonValue]:
    """Require an actual object before reading selected standard fields."""
    if not isinstance(value, dict):
        msg = "Expected an evidence object."
        raise TypeError(msg)
    return value


def array_value(value: JsonValue) -> list[JsonValue]:
    """Reject scalars or objects where a complete array is required."""
    if not isinstance(value, list):
        msg = "Expected an evidence array."
        raise TypeError(msg)
    return value


def text_value(value: JsonValue) -> str:
    """Do not coerce arbitrary JSON values into identities or reference strings."""
    if not isinstance(value, str) or not value:
        msg = "Expected a nonempty evidence string."
        raise ValueError(msg)
    return value


def read_lock(raw: bytes) -> dict[str, LockPackage]:
    """Require unique package versions and only the approved registry/source form."""
    document = DOCUMENT.validate_json(json.dumps(tomllib.loads(raw.decode())))
    packages: dict[str, LockPackage] = {}
    for entry in array_value(document.get("package")):
        values = object_value(entry)
        package = LockPackage.model_validate(
            {
                key: value
                for key, value in values.items()
                if key
                in {
                    "name",
                    "version",
                    "source",
                    "dependencies",
                    "optional-dependencies",
                    "dev-dependencies",
                }
            }
        )
        expected_source = (
            {"editable": "."}
            if package.name == "dscat"
            else {"registry": "https://pypi.org/simple"}
        )
        if package.name in packages or package.source != expected_source:
            msg = "Lock package identity or source is unsupported."
            raise ValueError(msg)
        packages[package.name] = package
    if "dscat" not in packages:
        msg = "The lock does not identify the application."
        raise ValueError(msg)
    return packages


def selected_dependencies(
    package: LockPackage,
    extras: set[str],
    environment: dict[str, str],
    *,
    development: bool,
) -> list[LockDependency]:
    """Select only applicable platform edges and explicitly requested extras."""
    dependencies = list(package.dependencies)
    for extra in extras:
        if extra not in package.optional_dependencies:
            msg = "The lock does not contain a requested dependency extra."
            raise ValueError(msg)
        dependencies.extend(package.optional_dependencies[extra])
    if package.name == "dscat" and development:
        dependencies.extend(package.dev_dependencies.get("dev", []))
    return [
        entry
        for entry in dependencies
        if entry.marker is None or Marker(entry.marker).evaluate(environment)
    ]


def locked_graph(
    raw: bytes, environment: dict[str, str], *, development: bool = False
) -> DependencyGraph:
    """Resolve a finite fixed point so transitive extras never vanish from inventory."""
    if set(environment) != MARKER_FIELDS:
        msg = "Dependency selection requires the complete target marker context."
        raise ValueError(msg)
    packages = read_lock(raw)
    extras: dict[str, set[str]] = {"dscat": set()}
    edges: dict[str, set[str]] = {}
    requests: dict[str, dict[str, set[str]]] = {}
    pending = ["dscat"]
    while pending:
        name = pending.pop()
        if name not in packages:
            msg = "A selected lock dependency is missing."
            raise ValueError(msg)
        selected = selected_dependencies(
            packages[name], extras[name], environment, development=development
        )
        relationships = selected
        if name == "dscat" and development:
            # Development-group roots select tools but are not wheel Requires-Dist.
            relationships = selected_dependencies(
                packages[name], extras[name], environment, development=False
            )
        edges[name] = {entry.name for entry in relationships}
        requests[name] = {}
        for entry in relationships:
            requests[name].setdefault(entry.name, set()).update(
                canonicalize_name(extra) for extra in entry.extra
            )
        for dependency in selected:
            before = extras.get(dependency.name)
            requested = set(dependency.extra)
            if before is None or not requested <= before:
                extras[dependency.name] = (before or set()) | requested
                pending.append(dependency.name)
    return DependencyGraph(
        versions={name: packages[name].version for name in edges},
        edges=edges,
        extras=extras,
        requested_extras=requests,
    )


def reconcile_inventory(inventory: Inventory, expected: DependencyGraph) -> None:
    """Reject missing or wrong packages and incomplete installed requirement edges."""
    installed = {package.name: package for package in inventory.distributions}
    if {name: item.version for name, item in installed.items()} != expected.versions:
        msg = "Installed distributions do not match the selected lock."
        raise ValueError(msg)
    for package in inventory.distributions:
        edges: set[str] = set()
        requests: dict[str, set[str]] = {}
        for raw in package.requires:
            requirement = Requirement(raw)
            selected_extras = {"", *expected.extras[package.name]}
            applicable = requirement.marker is None or any(
                requirement.marker.evaluate(
                    inventory.marker_environment | {"extra": extra}
                )
                for extra in selected_extras
            )
            if not applicable:
                continue
            name = canonicalize_name(requirement.name)
            if (
                requirement.url is not None
                or name not in installed
                or not requirement.specifier.contains(
                    installed[name].version, prereleases=True
                )
            ):
                msg = "Installed dependency requirements are unsatisfied or unapproved."
                raise ValueError(msg)
            edges.add(name)
            requests.setdefault(name, set()).update(
                canonicalize_name(extra) for extra in requirement.extras
            )
        if (
            edges != expected.edges[package.name]
            or requests != expected.requested_extras[package.name]
        ):
            msg = "Installed dependency relationships do not match the lock."
            raise ValueError(msg)
