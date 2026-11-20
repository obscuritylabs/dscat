# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Select dependencies using recorded target markers and transitive extras."""

import pytest
from scripts.dependency_graph import (
    array_value,
    locked_graph,
    object_value,
    read_lock,
    reconcile_inventory,
    text_value,
)
from scripts.environment_inventory import marker_environment
from scripts.evidence_models import Inventory

LOCK = b"""
version = 1
[[package]]
name = "dscat"
version = "0.1.0"
source = {editable = "."}
dependencies = [{name = "foo", extra = ["detail"]}]
[package.dev-dependencies]
dev = [{name = "tool"}]
[[package]]
name = "foo"
version = "1"
source = {registry = "https://pypi.org/simple"}
dependencies = [{name = "bar", marker = "sys_platform == 'win32'"}]
[package.optional-dependencies]
detail = [{name = "baz"}]
[[package]]
name = "bar"
version = "1"
source = {registry = "https://pypi.org/simple"}
[[package]]
name = "baz"
version = "1"
source = {registry = "https://pypi.org/simple"}
[[package]]
name = "tool"
version = "1"
source = {registry = "https://pypi.org/simple"}
"""


def environment(platform: str = "darwin") -> dict[str, str]:
    """Specify every marker even when the target differs from the executing host."""
    return marker_environment() | {
        "sys_platform": platform,
        "python_full_version": "3.15.2",
        "python_version": "3.15",
    }


def inventory(*, windows: bool = False, development: bool = False) -> Inventory:
    """Provide installed metadata for selected synthetic dependencies."""
    requires = {
        "dscat": ["foo[detail]==1"],
        "foo": ["bar==1; sys_platform == 'win32'", "baz==1; extra == 'detail'"],
        "baz": [],
    }
    if windows:
        requires["bar"] = []
    if development:
        requires["tool"] = []
    return Inventory.model_validate(
        {
            "python_version": "3.15.2",
            "marker_environment": environment("win32" if windows else "darwin"),
            "distributions": [
                {
                    "name": name,
                    "version": "0.1.0" if name == "dscat" else "1",
                    "requires": dependencies,
                    "licenses": [
                        "LicenseRef-Proprietary" if name == "dscat" else "MIT"
                    ],
                }
                for name, dependencies in requires.items()
            ],
        }
    )


@pytest.mark.parametrize("windows", [False, True])
@pytest.mark.parametrize("development", [False, True])
def test_platform_extras_and_development_roots(
    *, windows: bool, development: bool
) -> None:
    """Select development tools without inventing application Requires-Dist edges."""
    installed = inventory(windows=windows, development=development)
    graph = locked_graph(LOCK, installed.marker_environment, development=development)
    expected = (
        {"dscat", "foo", "baz"}
        | ({"bar"} if windows else set())
        | ({"tool"} if development else set())
    )
    assert set(graph.versions) == expected
    assert graph.edges["dscat"] == {"foo"}
    assert graph.edges["foo"] == {"baz"} | ({"bar"} if windows else set())
    assert graph.extras["foo"] == {"detail"}
    reconcile_inventory(installed, graph)


@pytest.mark.parametrize(
    "mutation", ["missing", "extra", "version", "edges", "constraint", "url"]
)
def test_installed_inventory_mismatches_are_refused(mutation: str) -> None:
    """Refuse missing packages, extra packages and unsatisfied requirements."""
    installed = inventory()
    graph = locked_graph(LOCK, installed.marker_environment)
    values = installed.model_dump(exclude_none=True)
    if mutation == "missing":
        values["distributions"].pop()
    elif mutation == "extra":
        values["distributions"].append(
            {"name": "unexpected", "version": "1", "requires": [], "licenses": ["MIT"]}
        )
    elif mutation == "version":
        values["distributions"][0]["version"] = "2"
    else:
        values["distributions"][0]["requires"] = {
            "edges": [],
            "constraint": ["foo>=2"],
            "url": ["foo @ https://example.org/unapproved.whl"],
        }[mutation]
    with pytest.raises(ValueError, match="Installed"):
        reconcile_inventory(Inventory.model_validate(values), graph)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (b'name = "dscat"', b'name = "missing-app"'),
        (b"https://pypi.org/simple", b"https://example.org/unapproved"),
        (b'extra = ["detail"]', b'extra = ["unknown"]'),
        (b'name = "baz"}', b'name = "missing-package"}'),
    ],
)
def test_incomplete_or_unapproved_lock_refusal(old: bytes, new: bytes) -> None:
    """Unknown roots, sources, extras and dangling lock references stop selection."""
    with pytest.raises(ValueError, match=r"lock|Lock"):
        locked_graph(LOCK.replace(old, new), environment())


def test_duplicate_lock_versions_and_incomplete_marker_context() -> None:
    """Ambiguous versions and missing target context cannot borrow host assumptions."""
    duplicate = (
        LOCK
        + b'\n[[package]]\nname="foo"\nversion="2"\nsource={registry="https://pypi.org/simple"}\n'
    )
    with pytest.raises(ValueError, match="Lock package identity"):
        read_lock(duplicate)
    with pytest.raises(ValueError, match="complete target marker"):
        locked_graph(LOCK, {})


@pytest.mark.parametrize("requirement", ["foo==1", "foo[other]==1"])
def test_installed_extra_requests_must_match_each_lock_edge(requirement: str) -> None:
    """Matching installed names and versions cannot conceal changed requested extras."""
    installed = inventory()
    graph = locked_graph(LOCK, installed.marker_environment)
    packages = [
        package.model_copy(update={"requires": [requirement]})
        if package.name == "dscat"
        else package
        for package in installed.distributions
    ]
    changed = installed.model_copy(update={"distributions": packages})
    with pytest.raises(ValueError, match="relationships do not match"):
        reconcile_inventory(changed, graph)
    reconcile_inventory(installed, graph)


def test_shared_dependency_cycle_reaches_a_stable_extra_set() -> None:
    """A back edge cannot loop forever or erase extras requested by another edge."""
    cyclic = LOCK.replace(
        b'name = "baz"\nversion = "1"\nsource = {registry = "https://pypi.org/simple"}',
        b'name = "baz"\nversion = "1"\nsource = {registry = "https://pypi.org/simple"}\n'
        b'dependencies = [{name = "foo"}]',
    )
    graph = locked_graph(cyclic, environment())
    assert graph.edges["baz"] == {"foo"}
    assert graph.extras["foo"] == {"detail"}


@pytest.mark.parametrize("kind", ["object", "array", "text"])
def test_wrong_json_shapes_do_not_coerce_to_evidence(kind: str) -> None:
    """Missing values cannot silently become empty containers or identity strings."""
    boundary = {"object": object_value, "array": array_value, "text": text_value}[kind]
    with pytest.raises((ValueError, TypeError), match="Expected"):
        boundary(None)


def test_lock_requires_an_application_package() -> None:
    """An empty valid TOML lock cannot certify the application dependency inventory."""
    with pytest.raises(ValueError, match="does not identify the application"):
        read_lock(b"package=[]")
