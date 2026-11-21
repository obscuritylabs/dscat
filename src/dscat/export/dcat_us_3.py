# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Deterministic DCAT-US 3.0 projection without inference or remote resolution."""

import json
from urllib.parse import quote

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from pydantic import ValidationError
from referencing.exceptions import Unresolvable

from dscat.export.loss import ProjectionLoss, omitted_fields
from dscat.export.models import DcatContact, DcatDataset, DcatDistribution, DcatDocument
from dscat.models.base import StrictModel
from dscat.models.catalog import Catalog, DatasetRecord
from dscat.models.configuration import ExportConfiguration
from dscat.models.diagnostics import Code, TargetReadiness
from dscat.resources.registry import ResourceError, load_registry

CATALOG_SCHEMA = "https://resources.data.gov/dcat-us/3.0.0/definitions/catalog"
MAPPED = frozenset(
    {
        "id",
        "title",
        "description",
        "core_party.label",
        "core_party.email",
        "dataset_modified",
        "dataset_version",
        "distributions.id",
        "distributions.title",
        "distributions.access_url",
        "distributions.download_url",
    }
)


class DcatProjection(StrictModel):
    """A blocked target never carries a partial accepted standards document."""

    readiness: TargetReadiness
    document: DcatDocument | None = None
    losses: list[ProjectionLoss]


def contact_for(
    record: DatasetRecord, configuration: ExportConfiguration
) -> tuple[str | None, list[Code]]:
    """Resolve only explicit association/email and reject conflicting supplied facts."""
    supplied = record.core_party
    if supplied is None:
        return None, ["target_contact_missing"]
    configured = configuration.identity.parties.get(supplied.label)
    if (
        configured is not None
        and supplied.email is not None
        and supplied.email != configured.role_email
    ):
        return None, ["target_fact_conflict"]
    if (
        supplied.role == "contact"
        and configured is not None
        and not configured.contact_association
    ):
        return None, ["target_fact_conflict"]
    associated = supplied.role == "contact" or (
        configured is not None and configured.contact_association
    )
    email = supplied.email or (
        configured.role_email if configured is not None else None
    )
    if not associated or email is None:
        return None, ["target_contact_missing"]
    return email, []


def dataset_for(record: DatasetRecord, namespace: str, email: str) -> DcatDataset:
    """Use escaped stable suffixes and preserve optional supplied facts unchanged."""
    identity = namespace + quote(record.id, safe="")
    data: dict[str, object] = {
        "@id": identity,
        "identifier": record.id,
        "title": record.title,
        "description": record.description,
        "contactPoint": DcatContact.model_validate(
            {
                "fn": record.core_party.label
                if record.core_party is not None
                else None,
                "hasEmail": "mailto:" + email,
            }
        ),
    }
    if record.dataset_modified is not None:
        data["modified"] = record.dataset_modified
    if record.dataset_version is not None:
        data["version"] = record.dataset_version
    if bool(record.distributions):
        data["distribution"] = [
            DcatDistribution.model_validate(
                {"@id": identity + "/distributions/" + quote(item.id, safe="")}
                | {
                    key: value
                    for key, value in (
                        ("title", item.title),
                        ("accessURL", item.access_url),
                        ("downloadURL", item.download_url),
                    )
                    if value is not None
                }
            )
            for item in record.distributions
        ]
    return DcatDataset.model_validate(data)


def valid_document(document: DcatDocument) -> bool:
    """Check actual pinned dialect/reference semantics with no retrieval fallback."""
    bundle = load_registry()
    try:
        validator = Draft202012Validator(
            bundle.schemas[CATALOG_SCHEMA],
            registry=bundle.registry,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )
        return validator.is_valid(
            document.model_dump(mode="json", by_alias=True, exclude_none=True)
        )
    except SchemaError, Unresolvable:
        raise ResourceError from None


def project_dcat(
    catalog: Catalog | None, configuration: ExportConfiguration
) -> DcatProjection:
    """Separate structural validity, target facts, omission and document validation."""
    reasons: set[Code] = set()
    datasets: list[DcatDataset] = []
    losses: list[ProjectionLoss] = []
    if catalog is None:
        reasons.add("INVALID_METADATA")
    else:
        # Revalidate mutable nested collections before projecting any accepted facts.
        catalog = Catalog.model_validate(catalog.model_dump(exclude_none=True))
        configuration = ExportConfiguration.model_validate(
            configuration.model_dump(exclude_none=True)
        )
        namespace = configuration.identity.dataset_namespace
        if namespace is None or configuration.dcat_us_3.catalog_id is None:
            reasons.add("target_unrepresentable")
        for record in catalog.datasets:
            email, errors = export_facts(record, configuration)
            reasons.update(errors)
            if namespace is not None and email is not None:
                try:
                    datasets.append(dataset_for(record, namespace, email))
                except ValidationError:
                    reasons.add("target_unrepresentable")
            mapped = MAPPED | contact_mapping(record)
            losses.extend(omitted_fields(record, mapped, "dcat-us-3"))
        identities = (
            [configuration.dcat_us_3.catalog_id]
            if configuration.dcat_us_3.catalog_id is not None
            else []
        )
        for dataset in datasets:
            identities.append(dataset.id)
            identities.extend(item.id for item in dataset.distributions or [])
        if len(set(identities)) != len(identities):
            reasons.add("target_fact_conflict")
    document: DcatDocument | None = None
    if not reasons:
        document = DcatDocument.model_validate(
            {"@id": configuration.dcat_us_3.catalog_id, "dataset": datasets}
        )
        if not valid_document(document):
            reasons.add("target_unrepresentable")
            document = None
    readiness = TargetReadiness(
        target="dcat-us-3",
        state="blocked" if reasons else "ready",
        reasons=sorted(reasons),
    )
    return DcatProjection.model_validate(
        {"readiness": readiness, "losses": losses}
        | ({"document": document} if document is not None else {})
    )


def assess_dcat(
    catalog: Catalog | None, configuration: ExportConfiguration
) -> TargetReadiness:
    """Use the same transformation and validation for readiness as for export."""
    return project_dcat(catalog, configuration).readiness


def serialize_dcat(document: DcatDocument) -> bytes:
    """Revalidate nested facts and encode aliases with one deterministic LF."""
    validated = DcatDocument.model_validate(
        document.model_dump(mode="json", by_alias=True, exclude_none=True)
    )
    if not valid_document(validated):
        raise ResourceError
    return (
        json.dumps(
            validated.model_dump(mode="json", by_alias=True, exclude_none=True),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def contact_mapping(record: DatasetRecord) -> frozenset[str]:
    """Map an explicitly supplied contact role only when one exists."""
    return (
        frozenset({"core_party.role"})
        if record.core_party is not None and record.core_party.role == "contact"
        else frozenset[str]()
    )


def export_facts(
    record: DatasetRecord, configuration: ExportConfiguration
) -> tuple[str | None, list[Code]]:
    """Report missing description independently of the contact association."""
    email, reasons = contact_for(record, configuration)
    if record.description is None:
        reasons.append("target_description_missing")
    return email, reasons
