# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Construct fresh minimal public documents only after exact per-value approval."""

from typing import TYPE_CHECKING, Self

from pydantic import model_validator

from dscat.export.dcat_us_3 import assess_dcat, serialize_dcat
from dscat.export.dcat_us_3 import valid_document as valid_dcat
from dscat.export.loss import ProjectionLoss, omitted_fields
from dscat.export.models import DcatDocument
from dscat.export.odcs_3_2 import assess_odcs, serialize_odcs
from dscat.export.odcs_3_2 import valid_document as valid_odcs
from dscat.export.odcs_models import OdcsDocument
from dscat.intake.limits import IntakeError, fail
from dscat.models.base import StrictModel
from dscat.models.catalog import Catalog
from dscat.models.configuration import ExportConfiguration
from dscat.models.diagnostics import TargetReadiness
from dscat.models.public import (
    PublicDcatDataset,
    PublicDcatDocument,
    PublicOdcsDocument,
)
from dscat.projection import (
    contact_selected,
    eligible_record,
    resolve_subjects,
    subject_approved,
)
from dscat.publication_bindings import DerivedBinding

if TYPE_CHECKING:
    from dscat.models.base import Target
    from dscat.models.catalog import DatasetRecord
    from dscat.publication_bindings import ResolvedSubject


class PublicProjection(StrictModel):
    """Keep private assessments/losses separate from the approved document payloads."""

    readiness: list[TargetReadiness]
    dcat: PublicDcatDocument | None = None
    odcs: list[PublicOdcsDocument]
    losses: list[ProjectionLoss]

    @model_validator(mode="after")
    def all_or_nothing(self) -> Self:
        """Withhold every public document when any requested target is blocked."""
        if any(item.state != "ready" for item in self.readiness) and (
            self.dcat is not None or self.odcs
        ):
            msg = "A blocked public target must withhold all public documents."
            raise ValueError(msg)
        return self


def selected_value(subjects: list[ResolvedSubject], kind: str, identifier: str) -> str:
    """Read only a known resolved scalar or a typed derived emitted value."""
    for subject in subjects:
        if subject.subject_kind == kind and subject.subject_id == identifier:
            if kind == "derived_target":
                return DerivedBinding.model_validate(subject.value).value
            if isinstance(subject.value, str):
                return subject.value
    raise fail(code="PUBLIC_PROJECTION_DENIED")


def public_dcat_record(subjects: list[ResolvedSubject]) -> PublicDcatDataset:
    """Copy only individually approved facts into a new closed target model."""
    return PublicDcatDataset.model_validate(
        {
            "@id": selected_value(subjects, "derived_target", "dataset_iri"),
            "identifier": selected_value(subjects, "canonical", "id"),
            "title": selected_value(subjects, "canonical", "title"),
            "description": selected_value(subjects, "canonical", "description"),
            "contactPoint": {
                "fn": selected_value(subjects, "canonical", "core_party.label"),
                "hasEmail": selected_value(
                    subjects, "derived_target", "contact_email_iri"
                ),
            },
        }
    )


def public_odcs_record(
    subjects: list[ResolvedSubject], *, include_contact: bool
) -> PublicOdcsDocument:
    """Exclude private optional roles, fields, consumer and authority children."""
    data: dict[str, object] = {
        "id": selected_value(subjects, "derived_target", "contract_iri"),
        "version": selected_value(subjects, "derived_target", "contract_version"),
        "name": selected_value(subjects, "canonical", "title"),
        "description": {
            "customProperties": [
                {
                    "property": "catalogDescription",
                    "value": selected_value(subjects, "canonical", "description"),
                }
            ]
        },
        "customProperties": [
            {
                "property": "datasetIdentifier",
                "value": selected_value(subjects, "canonical", "id"),
            }
        ],
    }
    if include_contact:
        data["team"] = {
            "members": [
                {
                    "name": selected_value(subjects, "canonical", "core_party.label"),
                    "username": selected_value(
                        subjects, "derived_target", "contact_username"
                    ),
                }
            ]
        }
    return PublicOdcsDocument.model_validate(data)


def approved_subjects(
    record: DatasetRecord,
    configuration: ExportConfiguration,
    target: Target,
    *,
    include_contact: bool,
) -> list[ResolvedSubject]:
    """Check every actual factual and derived scope before output construction."""
    if not eligible_record(record, configuration):
        raise fail(code="PUBLIC_PROJECTION_DENIED")
    subjects = resolve_subjects(
        record, configuration, target, include_contact=include_contact
    )
    if not all(
        subject_approved(record, configuration, subject) for subject in subjects
    ):
        raise fail(code="PUBLIC_PROJECTION_DENIED")
    return subjects


def public_losses(
    record: DatasetRecord, target: Target, *, include_contact: bool
) -> list[ProjectionLoss]:
    """Keep all non-public canonical facts in explicit private omission reports."""
    mapped = {"id", "title", "description"}
    if include_contact:
        mapped.update({"core_party.label", "core_party.email"})
    if target == "odcs-3.2":
        mapped.update({"contract_id", "contract_version"})
    return omitted_fields(record, frozenset(mapped), target)


def project_target(
    catalog: Catalog, configuration: ExportConfiguration, target: Target
) -> PublicProjection:
    """Build one complete approved target without serializing canonical objects."""
    ordinary = (
        assess_dcat(catalog, configuration)
        if target == "dcat-us-3"
        else assess_odcs(catalog, configuration)
    )
    if ordinary.state != "ready":
        return PublicProjection(readiness=[ordinary], odcs=[], losses=[])
    datasets: list[PublicDcatDataset] = []
    catalog_id: str | None = None
    odcs: list[PublicOdcsDocument] = []
    losses: list[ProjectionLoss] = []
    denied = target == "dcat-us-3" and not catalog.datasets
    for record in catalog.datasets:
        include_contact = contact_selected(record, target)
        try:
            subjects = approved_subjects(
                record, configuration, target, include_contact=include_contact
            )
            if target == "dcat-us-3":
                datasets.append(public_dcat_record(subjects))
                catalog_id = selected_value(subjects, "derived_target", "catalog_iri")
            else:
                odcs.append(
                    public_odcs_record(subjects, include_contact=include_contact)
                )
        except IntakeError as error:
            if error.diagnostic.code != "PUBLIC_PROJECTION_DENIED":
                raise
            denied = True
        losses.extend(public_losses(record, target, include_contact=include_contact))
    dcat: PublicDcatDocument | None = None
    if target == "dcat-us-3" and not denied:
        dcat = PublicDcatDocument.model_validate(
            {"@id": catalog_id, "dataset": datasets}
        )
        denied = not valid_dcat(
            DcatDocument.model_validate(
                dcat.model_dump(mode="json", by_alias=True, exclude_none=True)
            )
        )
    if target == "odcs-3.2" and not denied:
        denied = not all(
            valid_odcs(
                OdcsDocument.model_validate(
                    document.model_dump(mode="json", by_alias=True, exclude_none=True)
                )
            )
            for document in odcs
        )
    readiness = TargetReadiness(
        target=target,
        state="blocked" if denied else "ready",
        reasons=["PUBLIC_PROJECTION_DENIED"] if denied else [],
    )
    return PublicProjection.model_validate(
        {"readiness": [readiness], "odcs": [] if denied else odcs, "losses": losses}
        | ({"dcat": dcat} if dcat is not None and not denied else {})
    )


def project_public(
    catalog: Catalog, configuration: ExportConfiguration, targets: list[Target]
) -> PublicProjection:
    """Withhold all public documents if any requested target or scope is blocked."""
    if not targets or len(set(targets)) != len(targets):
        raise fail(code="INVALID_INVOCATION")
    catalog = Catalog.model_validate(catalog.model_dump(exclude_none=True))
    configuration = ExportConfiguration.model_validate(
        configuration.model_dump(exclude_none=True)
    )
    projected = [
        project_target(catalog, configuration, target) for target in sorted(targets)
    ]
    readiness = [item for result in projected for item in result.readiness]
    denied = any(item.state != "ready" for item in readiness)
    dcat = next((result.dcat for result in projected if result.dcat is not None), None)
    return PublicProjection.model_validate(
        {
            "readiness": readiness,
            "odcs": []
            if denied
            else [doc for result in projected for doc in result.odcs],
            "losses": [item for result in projected for item in result.losses],
        }
        | ({"dcat": dcat} if dcat is not None and not denied else {})
    )


def public_dcat_bytes(document: PublicDcatDocument) -> bytes:
    """Validate the closed public shape before the actual target serializer."""
    validated = PublicDcatDocument.model_validate(
        document.model_dump(mode="json", by_alias=True, exclude_none=True)
    )
    return serialize_dcat(
        DcatDocument.model_validate(
            validated.model_dump(mode="json", by_alias=True, exclude_none=True)
        )
    )


def public_odcs_bytes(document: PublicOdcsDocument) -> bytes:
    """Refuse any private optional child before serializing a public contract."""
    validated = PublicOdcsDocument.model_validate(
        document.model_dump(mode="json", by_alias=True, exclude_none=True)
    )
    return serialize_odcs(
        OdcsDocument.model_validate(
            validated.model_dump(mode="json", by_alias=True, exclude_none=True)
        )
    )
