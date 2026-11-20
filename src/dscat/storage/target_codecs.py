# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Revalidate exact stored target bytes without fetching any described resources."""

import hashlib
from typing import TYPE_CHECKING

from pydantic import ValidationError

from dscat.export.dcat_us_3 import serialize_dcat
from dscat.export.models import DcatDocument
from dscat.export.odcs_3_2 import serialize_odcs
from dscat.export.odcs_models import OdcsDocument
from dscat.intake.limits import MAX_REQUEST_BYTES, fail
from dscat.json_guard import check_json
from dscat.models.public import PublicDcatDocument, PublicOdcsDocument
from dscat.public_projection import public_dcat_bytes, public_odcs_bytes
from dscat.storage.models import export_path

if TYPE_CHECKING:
    from dscat.models.catalog import Catalog
    from dscat.storage.models import ExportEntry, ProjectionEntry


def validate_internal(raw: bytes, entry: ExportEntry, catalog: Catalog) -> None:
    """Check schema, deterministic encoding and canonical dataset association."""
    check_json(raw, MAX_REQUEST_BYTES)
    try:
        if entry.target == "dcat-us-3":
            document = DcatDocument.model_validate_json(raw)
            encoded = serialize_dcat(document)
            if [item.identifier for item in document.datasets] != [
                record.id for record in catalog.datasets
            ]:
                raise fail(code="PUBLICATION_FAILURE")
        else:
            contract = OdcsDocument.model_validate_json(raw)
            encoded = serialize_odcs(contract)
            identifiers = [
                item.value
                for item in contract.custom_properties
                if item.property == "datasetIdentifier"
            ]
            if identifiers != [entry.dataset_id]:
                raise fail(code="PUBLICATION_FAILURE")
    except ValidationError, ValueError:
        raise fail(code="PUBLICATION_FAILURE") from None
    if encoded != raw or hashlib.sha256(raw).hexdigest() != entry.sha256:
        raise fail(code="PUBLICATION_FAILURE")


def validate_public(raw: bytes, entry: ProjectionEntry) -> None:
    """Reject any optional private child, noncanonical encoding or filename alias."""
    check_json(raw, MAX_REQUEST_BYTES)
    try:
        if entry.path == export_path("dcat-us-3"):
            document = PublicDcatDocument.model_validate_json(raw)
            encoded = public_dcat_bytes(document)
        else:
            contract = PublicOdcsDocument.model_validate_json(raw)
            encoded = public_odcs_bytes(contract)
            if entry.path != export_path("odcs-3.2", contract.id):
                raise fail(code="PUBLICATION_FAILURE")
    except ValidationError, ValueError:
        raise fail(code="PUBLICATION_FAILURE") from None
    if encoded != raw or hashlib.sha256(raw).hexdigest() != entry.sha256:
        raise fail(code="PUBLICATION_FAILURE")
