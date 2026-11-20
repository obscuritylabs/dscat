# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Resolve exact publication subjects before checking supplied approval scopes."""

from typing import TYPE_CHECKING, Literal
from urllib.parse import quote

from dscat.export.dcat_us_3 import contact_for
from dscat.export.odcs_3_2 import contract_facts
from dscat.models.catalog import DatasetRecord, PublicationApproval
from dscat.publication_bindings import (
    BindingInput,
    ResolvedSubject,
    binding_input,
    derived_subject,
)

if TYPE_CHECKING:
    from datetime import date

    from pydantic import JsonValue

    from dscat.models.base import Target
    from dscat.models.configuration import ExportConfiguration


def approve_subject(
    subject: ResolvedSubject, *, policy_version: str, authority: str, approved_on: date
) -> PublicationApproval:
    """Record supplied authority/date and exact value identity without inference."""
    return PublicationApproval.model_validate(
        subject.model_dump(exclude={"value"})
        | {
            "approved_value_sha256": subject.value_sha256(),
            "policy_version": policy_version,
            "authority": authority,
            "approved_on": approved_on,
        }
    )


def factual_subject(
    target: Target,
    kind: Literal["canonical", "configuration"],
    identifier: str,
    value: JsonValue,
) -> ResolvedSubject:
    """Represent only an actual selected scalar or normalized party-email binding."""
    return ResolvedSubject(
        subject_kind=kind, subject_id=identifier, target=target, value=value
    )


def source_of(subject: ResolvedSubject) -> BindingInput:
    """Bind a factual source; derived subjects cannot be source-approval substitutes."""
    if subject.subject_kind == "derived_target":
        msg = "Derived publication values cannot replace factual source approval."
        raise ValueError(msg)
    return binding_input(subject.subject_kind, subject.subject_id, subject.value)


def resolve_contact(
    record: DatasetRecord, configuration: ExportConfiguration, target: Target
) -> list[ResolvedSubject]:
    """Resolve direct/shared contact inputs and every association dependency first."""
    email, errors = contact_for(record, configuration)
    if email is None or errors:
        return []
    label = factual_subject(
        target, "canonical", "core_party.label", record.core_party.label
    )
    configured = configuration.identity.parties.get(record.core_party.label)
    selected = (
        factual_subject(
            target, "canonical", "core_party.email", record.core_party.email
        )
        if record.core_party.email is not None
        else factual_subject(
            target,
            "configuration",
            "identity.parties.role_email",
            {"label": record.core_party.label, "role_email": email},
        )
    )
    sources = [
        source_of(label),
        source_of(selected),
        binding_input("canonical", "core_party.role", record.core_party.role),
    ]
    if configured is not None:
        sources.append(
            binding_input(
                "configuration",
                "identity.parties.contact_association",
                {
                    "label": record.core_party.label,
                    "contact_association": configured.contact_association,
                },
            )
        )
        if selected.subject_kind == "canonical":
            sources.append(
                binding_input(
                    "configuration",
                    "identity.parties.role_email",
                    {
                        "label": record.core_party.label,
                        "role_email": configured.role_email,
                    },
                )
            )
    identifier = "contact_email_iri" if target == "dcat-us-3" else "contact_username"
    emitted = "mailto:" + email if target == "dcat-us-3" else email
    return [label, selected, derived_subject(target, identifier, emitted, sources)]


def resolve_subjects(
    record: DatasetRecord,
    configuration: ExportConfiguration,
    target: Target,
    *,
    include_contact: bool = True,
) -> list[ResolvedSubject]:
    """Resolve the initial minimal public mapping without optional private children."""
    subjects = [
        factual_subject(target, "canonical", name, getattr(record, name))
        for name in ("id", "title", "description")
    ]
    if include_contact:
        subjects.extend(resolve_contact(record, configuration, target))
    if target == "dcat-us-3":
        namespace = configuration.identity.dataset_namespace
        catalog_id = configuration.dcat_us_3.catalog_id
        if namespace is None or catalog_id is None:
            return subjects
        namespace_subject = factual_subject(
            target, "configuration", "identity.dataset_namespace", namespace
        )
        catalog_subject = factual_subject(
            target, "configuration", "dcat_us_3.catalog_id", catalog_id
        )
        subjects.extend(
            [
                namespace_subject,
                catalog_subject,
                derived_subject(
                    target,
                    "dataset_iri",
                    namespace + quote(record.id, safe=""),
                    [source_of(subjects[0]), source_of(namespace_subject)],
                ),
                derived_subject(
                    target, "catalog_iri", catalog_id, [source_of(catalog_subject)]
                ),
            ]
        )
    else:
        identity, version, errors = contract_facts(record, configuration)
        if identity is None or version is None or errors:
            return subjects
        if record.contract_id is not None:
            identity_source = factual_subject(
                target, "canonical", "contract_id", record.contract_id
            )
            identity_sources = [source_of(identity_source)]
        else:
            # contract_facts verified both explicit namespace and identity rule.
            namespace = configuration.identity.contract_namespace
            rule = configuration.identity.contract_identity_rule
            if namespace is None or rule is None:
                msg = "Missing selected contract identity dependencies."
                raise ValueError(msg)
            identity_source = factual_subject(
                target, "configuration", "identity.contract_namespace", namespace
            )
            identity_sources = [
                source_of(subjects[0]),
                source_of(identity_source),
                binding_input("configuration", "identity.contract_identity_rule", rule),
            ]
        version_source = (
            factual_subject(
                target, "canonical", "contract_version", record.contract_version
            )
            if record.contract_version is not None
            else factual_subject(
                target, "configuration", "odcs_3_2.contract_version", version
            )
        )
        version_sources = [source_of(version_source)]
        if (
            record.contract_version is not None
            and configuration.odcs_3_2.contract_version is not None
        ):
            version_sources.append(
                binding_input(
                    "configuration",
                    "odcs_3_2.contract_version",
                    configuration.odcs_3_2.contract_version,
                )
            )
        subjects.extend(
            [
                identity_source,
                version_source,
                derived_subject(target, "contract_iri", identity, identity_sources),
                derived_subject(target, "contract_version", version, version_sources),
            ]
        )
    return subjects


def eligible_record(record: DatasetRecord, configuration: ExportConfiguration) -> bool:
    """Require independent review, metadata disclosure and publication controls."""
    review = record.metadata_review
    disclosure = record.disclosure_determination
    publication = record.publication
    return (
        configuration.publication is not None
        and publication is not None
        and publication.state == "approved"
        and review is not None
        and review.state == "approved"
        and review.authority is not None
        and review.reviewed_on is not None
        and disclosure is not None
        and disclosure.state == "unrestricted"
        and disclosure.authority is not None
        and disclosure.determined_on is not None
        and disclosure.review_status == "approved"
    )


def subject_approved(
    record: DatasetRecord, configuration: ExportConfiguration, subject: ResolvedSubject
) -> bool:
    """Restrict exact supplied grants without treating policy as a new grant."""
    policy = configuration.publication
    publication = record.publication
    if policy is None or publication is None:
        return False
    key = (subject.subject_kind, subject.subject_id, subject.target)
    if key not in {
        (item.subject_kind, item.subject_id, item.target)
        for item in policy.allowed_subjects
    }:
        return False
    return any(
        (item.subject_kind, item.subject_id, item.target) == key
        and item.policy_version == policy.policy_version
        and item.approved_value_sha256 == subject.value_sha256()
        for item in publication.approvals or []
    )


def contact_selected(record: DatasetRecord, target: Target) -> bool:
    """Select an optional ODCS member only through supplied contact scopes."""
    publication = record.publication
    return target == "dcat-us-3" or (
        publication is not None
        and any(
            item.target == target
            and item.subject_id
            in {
                "core_party.label",
                "core_party.email",
                "identity.parties.role_email",
                "contact_username",
            }
            for item in publication.approvals or []
        )
    )
