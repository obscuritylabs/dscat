# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Verify registration readiness, preservation and closed public projections."""

from typing import TYPE_CHECKING

from dscat.export.dcat_us_3 import project_dcat
from dscat.export.odcs_3_2 import project_odcs
from dscat.models.catalog import Catalog, DatasetRecord
from dscat.models.configuration import AssessmentConfiguration
from dscat.projection import approve_subject, resolve_subjects
from dscat.public_projection import project_public
from dscat.serialization import canonical_bytes
from dscat.storage.flatfiles import load_snapshot, save_snapshot
from dscat.validation import validate_catalog
from tests.test_collection_intake import edited, minimum, parsed
from tests.test_collection_models import intake, registered
from tests.test_dcat_us_3 import configuration, record
from tests.test_projection import public_bytes
from tests.test_publication_bindings import APPROVED_ON, approved_fixture

if TYPE_CHECKING:
    from pathlib import Path

    from dscat.models.base import Target


def test_minimum_registration_unready_but_saved(tmp_path: Path) -> None:
    """Separate missing target facts from valid intake and persisted uncertainty."""
    source = registered()
    for result in [
        project_dcat(source, configuration()),
        project_odcs(source, configuration()),
    ]:
        assert result.readiness.state == "blocked"
        assert "target_description_missing" in result.readiness.reasons
    result = project_dcat(source, configuration())
    assert "target_contact_missing" in result.readiness.reasons
    assert result.document is None
    save_snapshot(tmp_path / "catalog", source)
    assert load_snapshot(tmp_path / "catalog").catalog == source
    normalized = parsed(edited(minimum()))
    validation = validate_catalog(normalized.records, AssessmentConfiguration())
    assert validation.catalog is not None
    assert validation.catalog.schema_version == "1.1"
    assert validation.assessment.validity == "valid"


def test_sufficient_facts_and_detailed_old_metadata_survive(tmp_path: Path) -> None:
    """Export new rich catalogs without erasing original capacity or schema facts."""
    values = record(detailed=True).model_dump(exclude_none=True)
    values["core_party"]["role"] = "owner"
    values["collection_intake"] = intake().model_dump(exclude_none=True) | {
        "owner_state": "known",
        "location": "Synthetic location sentinel",
        "retention": {"authorized_by": "PRIVATE-AUTHORIZER-SENTINEL"},
        "submitted_by": "Synthetic submitter sentinel",
    }
    source = Catalog(
        schema_version="1.2", datasets=[DatasetRecord.model_validate(values)]
    )
    for result in [
        project_dcat(source, configuration()),
        project_odcs(source, configuration()),
    ]:
        assert result.readiness.state == "ready"
        assert any(
            item.field == "collection_intake.submitted_by" for item in result.losses
        )
        assert any(
            item.field == "collection_intake.retention.authorized_by"
            for item in result.losses
        )
        assert b"PRIVATE-AUTHORIZER" not in canonical_bytes(result)
    save_snapshot(tmp_path / "catalog", source)
    assert load_snapshot(tmp_path / "catalog").catalog == source


def test_registration_private_fields_omitted_with_valid_public_approvals() -> None:
    """Publish allowed original facts while withholding all registration context."""
    source, configured = approved_fixture(detailed=True)
    values = source.model_dump(exclude_none=True)
    values["core_party"]["role"] = "owner"
    values["collection_intake"] = intake().model_dump(exclude_none=True) | {
        "owner_state": "known",
        "submitted_by": "PRIVATE-SUBMITTER-SENTINEL",
        "location": "PRIVATE-LOCATION-SENTINEL",
        "retention": {"authorized_by": "PRIVATE-AUTHORIZER-SENTINEL"},
        "generation": {
            "process": "PRIVATE-PROCESS-SENTINEL",
            "source_names": ["PRIVATE-SOURCE-SENTINEL"],
        },
    }
    changed = DatasetRecord.model_validate(values)
    targets: tuple[Target, ...] = ("dcat-us-3", "odcs-3.2")
    values["publication"]["approvals"] = [
        approve_subject(
            subject,
            policy_version="synthetic-policy-1",
            authority="Synthetic publication authority",
            approved_on=APPROVED_ON,
        ).model_dump(mode="json")
        for target in targets
        for subject in resolve_subjects(changed, configured, target)
    ]
    catalog = Catalog(
        schema_version="1.2", datasets=[DatasetRecord.model_validate(values)]
    )
    projection = project_public(catalog, configured, list(targets))
    assert all(r.state == "ready" for r in projection.readiness)
    output = public_bytes(projection)
    assert output
    assert b"PRIVATE-" not in output
    assert b"collection_intake" not in output


def test_old_multirecord_links_remain_valid(tmp_path: Path) -> None:
    """Validate old links at catalog scope instead of rejecting individual records."""
    first = record().model_dump(exclude_none=True)
    second = record().model_dump(exclude_none=True) | {
        "id": "asset-002",
        "title": "Second collection",
    }
    first["services"] = [
        {
            "id": "service-001",
            "served_datasets": [{"reference_kind": "local", "id": "asset-002"}],
        }
    ]
    source = Catalog.model_validate(
        {"schema_version": "1.0", "datasets": [first, second]}
    )
    save_snapshot(tmp_path / "old", source)
    assert load_snapshot(tmp_path / "old").catalog == source
