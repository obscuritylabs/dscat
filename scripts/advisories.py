# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Reconcile complete scanner results and CISA matching."""

from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field, JsonValue

from dscat.json_guard import check_json
from dscat.models.base import StrictModel, Text
from dscat.resources.registry import DOCUMENT
from scripts.dependency_graph import array_value, object_value
from scripts.evidence_models import (
    AdvisoryIdentifier,
    Finding,
    canonical_advisory_identifier,
)

if TYPE_CHECKING:
    from scripts.evidence_models import Inventory

FEED_BYTES = 32 * 1024**2


class AuditVulnerability(StrictModel):
    """The pinned scanner's JSON shape has no severity or applicability assertion."""

    id: AdvisoryIdentifier
    fix_versions: list[Text]
    aliases: list[AdvisoryIdentifier]
    description: str


class AuditDependency(StrictModel):
    """A successfully queried exact package version and all returned advisories."""

    name: Text
    version: Text
    vulns: list[AuditVulnerability]


class SkippedDependency(StrictModel):
    """Skipped dependencies are missing security coverage, never zero findings."""

    name: Text
    skip_reason: Text


class AuditOutput(StrictModel):
    """No automatic dependency mutation is authorized by an advisory check."""

    dependencies: Annotated[
        list[AuditDependency | SkippedDependency], Field(min_length=1, max_length=1000)
    ]
    fixes: Annotated[list[JsonValue], Field(max_length=0)]


class ObservedAdvisory(StrictModel):
    """An observed affected-package report retains every authoritative alias."""

    package: Text
    version: Text
    scope: Literal["runtime", "development"]
    identifiers: Annotated[list[AdvisoryIdentifier], Field(min_length=1)]


class KevCatalog(StrictModel):
    """Only CVE identities and count are needed from the captured full catalog."""

    count: Annotated[int, Field(gt=0, le=100000)]
    identifiers: Annotated[
        list[Annotated[str, Field(pattern=r"^CVE-[0-9]{4}-[0-9]{4,}$")]],
        Field(min_length=1, max_length=100000),
    ]


def parse_audit(
    raw: bytes, inventory: Inventory, scope: Literal["runtime", "development"]
) -> list[ObservedAdvisory]:
    """Require exact dependency coverage without skipped audit work."""
    check_json(raw, FEED_BYTES)
    document = AuditOutput.model_validate_json(raw)
    expected = {
        package.name: package.version
        for package in inventory.distributions
        if package.name != "dscat"
    }
    observed: dict[str, str] = {}
    advisories: list[ObservedAdvisory] = []
    for package in document.dependencies:
        if isinstance(package, SkippedDependency):
            msg = "Advisory collection skipped a selected dependency."
            raise TypeError(msg)
        if package.name in observed:
            msg = "Advisory collection returned duplicate dependency identities."
            raise ValueError(msg)
        observed[package.name] = package.version
        advisories.extend(
            ObservedAdvisory(
                package=package.name,
                version=package.version,
                scope=scope,
                identifiers=sorted({vulnerability.id, *vulnerability.aliases}),
            )
            for vulnerability in package.vulns
        )
    if observed != expected:
        msg = "Advisory collection does not cover the exact selected environment."
        raise ValueError(msg)
    return advisories


def parse_kev(raw: bytes) -> set[str]:
    """Reject truncated catalogs, malformed CVEs and duplicate entries."""
    check_json(raw, FEED_BYTES)
    document = DOCUMENT.validate_json(raw)
    catalog = KevCatalog.model_validate(
        {
            "count": document.get("count"),
            "identifiers": [
                object_value(value).get("cveID")
                for value in array_value(document.get("vulnerabilities"))
            ],
        }
    )
    identifiers = set(catalog.identifiers)
    if catalog.count != len(catalog.identifiers) or len(identifiers) != catalog.count:
        msg = "Known-exploitation catalog count or identities are inconsistent."
        raise ValueError(msg)
    return identifiers


def merge_advisories(advisories: list[ObservedAdvisory]) -> list[ObservedAdvisory]:
    """Join only alias-connected reports for the same scope, package and version."""
    merged: list[ObservedAdvisory] = []
    for advisory in advisories:
        identifiers = {
            canonical_advisory_identifier(item) for item in advisory.identifiers
        }
        untouched: list[ObservedAdvisory] = []
        for group in merged:
            if (
                group.scope == advisory.scope
                and group.package == advisory.package
                and group.version == advisory.version
                and identifiers & set(group.identifiers)
            ):
                identifiers.update(group.identifiers)
            else:
                untouched.append(group)
        merged = [
            *untouched,
            advisory.model_copy(update={"identifiers": sorted(identifiers)}),
        ]
    return sorted(merged, key=lambda item: (item.scope, item.package, item.identifiers))


def apply_dispositions(
    advisories: list[ObservedAdvisory],
    dispositions: list[Finding],
    kev_cves: set[str],
) -> list[Finding]:
    """Keep unassessed findings unknown and reject conflicting overrides."""
    result: list[Finding] = []
    kev_cves = {canonical_advisory_identifier(item) for item in kev_cves}
    used: set[int] = set()
    for advisory in merge_advisories(advisories):
        identities = set(advisory.identifiers)
        matches = [
            index
            for index, disposition in enumerate(dispositions)
            if disposition.scope == advisory.scope
            and disposition.package == advisory.package
            and disposition.version == advisory.version
            and canonical_advisory_identifier(disposition.id) in identities
        ]
        if len(matches) > 1:
            msg = "Conflicting dispositions refer to the same observed advisory."
            raise ValueError(msg)
        primary = advisory.identifiers[0]
        aliases = advisory.identifiers[1:]
        if matches:
            index = matches[0]
            disposition = dispositions[index]
            if (
                not {
                    canonical_advisory_identifier(item) for item in disposition.aliases
                }
                <= identities
            ):
                msg = "Advisory disposition references an unobserved identity."
                raise ValueError(msg)
            used.add(index)
            result.append(
                disposition.model_copy(update={"id": primary, "aliases": aliases})
            )
        else:
            result.append(
                Finding(
                    id=primary,
                    package=advisory.package,
                    version=advisory.version,
                    scope=advisory.scope,
                    aliases=aliases,
                    severity="unknown",
                    known_exploited=bool(identities & kev_cves),
                    applicability="under_investigation",
                )
            )
    if used != set(range(len(dispositions))):
        msg = "An advisory disposition does not match current observed findings."
        raise ValueError(msg)
    return result
