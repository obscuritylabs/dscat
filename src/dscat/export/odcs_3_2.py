# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""ODCS 3.2.0 descriptive projection with independent contract facts and losses."""

import json
from dataclasses import dataclass, field
from typing import Literal, get_args
from urllib.parse import quote

from jsonschema import Draft201909Validator
from jsonschema.exceptions import SchemaError
from pydantic import ValidationError
from referencing.exceptions import Unresolvable

from dscat.export.dcat_us_3 import contact_for
from dscat.export.loss import ProjectionLoss, omitted_fields, supplied_fields
from dscat.export.odcs_models import (
    LogicalType,
    OdcsDocument,
    OdcsField,
    OdcsObject,
    TeamMember,
)
from dscat.models.base import StrictModel
from dscat.models.catalog import Catalog, DatasetRecord, FieldDefinition, RoleAssignment
from dscat.models.configuration import ExportConfiguration
from dscat.models.diagnostics import Code, TargetReadiness
from dscat.resources.registry import ResourceError, load_registry

ODCS_SCHEMA = "https://raw.githubusercontent.com/bitol-io/open-data-contract-standard/f0bdad95346905d500be5ef4b2c2d9b1d95223b7/schema/odcs-json-schema-v3.2.0.json"
MAPPED = frozenset(
    {
        "id",
        "title",
        "description",
        "contract_id",
        "contract_version",
        "dataset_version",
        "core_party.label",
        "core_party.email",
        "roles.label",
        "roles.email",
        "roles.role",
        "fields.object_name",
        "fields.field_name",
        "fields.type",
        "fields.description",
        "fields.nullable",
        "fields.semantic_references",
        "consumer.intended_uses",
        "consumer.limitations",
        "consumer.semantic_references",
    }
)
LossReason = Literal[
    "unsupported_mapping", "unsupported_cardinality", "unresolved_contact"
]


class OdcsProjection(StrictModel):
    """All contracts are accepted together; blocked catalogs have no partial output."""

    readiness: TargetReadiness
    documents: list[OdcsDocument]
    losses: list[ProjectionLoss]


def loss(record: DatasetRecord, path: str, reason: LossReason) -> ProjectionLoss:
    """Describe missing representation without copying a submitted value."""
    return ProjectionLoss(
        record_id=record.id, field=path, target="odcs-3.2", reason=reason
    )


def contract_facts(
    record: DatasetRecord, configuration: ExportConfiguration
) -> tuple[str | None, str | None, set[Code]]:
    """Only missing identity derives under an explicit rule; version never does."""
    reasons: set[Code] = set()
    namespace = configuration.identity.contract_namespace
    identity = record.contract_id
    if (
        identity is None
        and namespace is not None
        and configuration.identity.contract_identity_rule == "namespace-plus-dataset-id"
    ):
        identity = namespace + quote(record.id, safe="")
    if identity is None:
        reasons.add("target_contract_identity_missing")
    shared_version = configuration.odcs_3_2.contract_version
    if (
        record.contract_version is not None
        and shared_version is not None
        and record.contract_version != shared_version
    ):
        reasons.add("target_fact_conflict")
    version = record.contract_version or shared_version
    if version is None:
        reasons.add("target_contract_version_missing")
    return identity, version, reasons


@dataclass
class MemberFacts:
    """Group explicitly resolved target usernames without guessing a display name."""

    label: str
    roles: set[str] = field(default_factory=set)


def role_email(
    role: RoleAssignment, configuration: ExportConfiguration
) -> tuple[str | None, bool]:
    """Use explicit role contact facts and reject contradictory shared mappings."""
    configured = configuration.identity.parties.get(role.label)
    if configured is not None and (
        (role.email is not None and role.email != configured.role_email)
        or (role.role == "contact" and not configured.contact_association)
    ):
        return None, True
    return role.email or (
        configured.role_email if configured is not None else None
    ), False


def members_for(
    record: DatasetRecord, configuration: ExportConfiguration
) -> tuple[list[TeamMember], list[ProjectionLoss], set[Code]]:
    """Omit unresolved optional members without inventing ownership or usernames."""
    groups: dict[str, MemberFacts] = {}
    losses: list[ProjectionLoss] = []
    reasons: set[Code] = set()
    email, contact_errors = contact_for(record, configuration)
    if "target_fact_conflict" in contact_errors:
        reasons.add("target_fact_conflict")
    if email is not None:
        groups[email] = MemberFacts(record.core_party.label)
    else:
        losses.extend(
            loss(record, path, "unresolved_contact")
            for path in sorted(supplied_fields(record.core_party, "core_party"))
        )
    for role in record.roles or []:
        username, conflict = role_email(role, configuration)
        if conflict:
            reasons.add("target_fact_conflict")
        if username is None:
            losses.extend(
                loss(record, path, "unresolved_contact")
                for path in sorted(supplied_fields(role, "roles"))
            )
            continue
        facts = groups.setdefault(username, MemberFacts(role.label))
        if facts.label != role.label:
            reasons.add("target_fact_conflict")
        facts.roles.add(role.role)
    members: list[TeamMember] = []
    for username, facts in sorted(groups.items()):
        values: dict[str, object] = {"username": username, "name": facts.label}
        if len(facts.roles) == 1:
            values["role"] = next(iter(facts.roles))
        elif len(facts.roles) > 1:
            losses.append(loss(record, "roles.role", "unsupported_cardinality"))
        members.append(TeamMember.model_validate(values))
    return members, losses, reasons


def field_for(source: FieldDefinition) -> OdcsField:
    """Preserve unknown type spellings and nullable booleans as named properties."""
    values: dict[str, object] = {"name": source.field_name}
    properties: list[dict[str, object]] = []
    if source.type in get_args(LogicalType):
        values["logicalType"] = source.type
    else:
        properties.append({"property": "catalogFieldType", "value": source.type})
    if source.nullable is not None:
        properties.append({"property": "canonicalNullable", "value": source.nullable})
    if properties:
        values["customProperties"] = properties
    if source.description is not None:
        values["description"] = source.description
    if bool(source.semantic_references):
        values["authoritativeDefinitions"] = [
            {"url": uri} for uri in source.semantic_references
        ]
    return OdcsField.model_validate(values)


def document_for(
    record: DatasetRecord, identity: str, version: str, members: list[TeamMember]
) -> tuple[OdcsDocument, list[ProjectionLoss]]:
    """Map supplied semantics and report unsupported scalar cardinality."""
    description: dict[str, object] = {
        "customProperties": [
            {"property": "catalogDescription", "value": record.description}
        ]
    }
    losses: list[ProjectionLoss] = []
    if record.consumer is not None:
        for path, key, values in (
            ("consumer.intended_uses", "usage", record.consumer.intended_uses),
            ("consumer.limitations", "limitations", record.consumer.limitations),
        ):
            if values is not None and len(values) == 1:
                description[key] = values[0]
            elif bool(values):
                losses.append(loss(record, path, "unsupported_cardinality"))
        if bool(record.consumer.semantic_references):
            description["authoritativeDefinitions"] = [
                {"url": uri} for uri in record.consumer.semantic_references
            ]
    custom: list[dict[str, object]] = [
        {"property": "datasetIdentifier", "value": record.id}
    ]
    if record.dataset_version is not None:
        custom.append({"property": "datasetVersion", "value": record.dataset_version})
    data: dict[str, object] = {
        "id": identity,
        "version": version,
        "name": record.title,
        "description": description,
        "customProperties": custom,
    }
    if members:
        data["team"] = {"members": members}
    objects: dict[str, list[OdcsField]] = {}
    for source in record.fields or []:
        objects.setdefault(source.object_name, []).append(field_for(source))
    if objects:
        data["schema"] = [
            OdcsObject(name=name, properties=properties)
            for name, properties in sorted(objects.items())
        ]
    return OdcsDocument.model_validate(data), losses


def valid_document(document: OdcsDocument) -> bool:
    """Use the pinned actual 2019-09 schema with unevaluated-property semantics."""
    bundle = load_registry()
    try:
        validator = Draft201909Validator(
            bundle.schemas[ODCS_SCHEMA],
            registry=bundle.registry,
            format_checker=Draft201909Validator.FORMAT_CHECKER,
        )
        return validator.is_valid(
            document.model_dump(mode="json", by_alias=True, exclude_none=True)
        )
    except SchemaError, Unresolvable:
        raise ResourceError from None


def project_odcs(
    catalog: Catalog | None, configuration: ExportConfiguration
) -> OdcsProjection:
    """Keep contracts, dataset facts and metadata/publication decisions independent."""
    reasons: set[Code] = set()
    documents: list[OdcsDocument] = []
    losses: list[ProjectionLoss] = []
    if catalog is None:
        reasons.add("INVALID_METADATA")
    else:
        catalog = Catalog.model_validate(catalog.model_dump(exclude_none=True))
        configuration = ExportConfiguration.model_validate(
            configuration.model_dump(exclude_none=True)
        )
        for record in catalog.datasets:
            identity, version, errors = contract_facts(record, configuration)
            reasons.update(errors)
            members, member_losses, errors = members_for(record, configuration)
            reasons.update(errors)
            extra = list(member_losses)
            if identity is not None and version is not None:
                try:
                    document, scalar_losses = document_for(
                        record, identity, version, members
                    )
                    extra.extend(scalar_losses)
                    if valid_document(document):
                        documents.append(document)
                    else:
                        reasons.add("target_unrepresentable")
                except ValidationError:
                    reasons.add("target_unrepresentable")
            excluded = {item.field for item in extra}
            losses.extend(
                item
                for item in omitted_fields(record, MAPPED, "odcs-3.2")
                if item.field not in excluded
            )
            losses.extend(extra)
        identities = [document.id for document in documents]
        namespace = configuration.identity.dataset_namespace
        dataset_ids = (
            {namespace + quote(record.id, safe="") for record in catalog.datasets}
            if namespace is not None
            else set()
        )
        if len(set(identities)) != len(identities) or set(identities) & dataset_ids:
            reasons.add("target_fact_conflict")
    unique_losses = {(item.record_id, item.field, item.reason): item for item in losses}
    return OdcsProjection(
        readiness=TargetReadiness(
            target="odcs-3.2",
            state="blocked" if reasons else "ready",
            reasons=sorted(reasons),
        ),
        documents=[] if reasons else documents,
        losses=[unique_losses[key] for key in sorted(unique_losses)],
    )


def assess_odcs(
    catalog: Catalog | None, configuration: ExportConfiguration
) -> TargetReadiness:
    """Readiness and emitted contract validation share one transformation."""
    return project_odcs(catalog, configuration).readiness


def serialize_odcs(document: OdcsDocument) -> bytes:
    """Revalidate aliased structured facts before deterministic UTF-8 encoding."""
    validated = OdcsDocument.model_validate(
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
