# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Supplied optional facts survive canonically with value-free per-target losses."""

import pytest
from pydantic import ValidationError

from dscat.export.dcat_us_3 import project_dcat
from dscat.export.loss import ProjectionLoss, supplied_fields
from dscat.models.catalog import Catalog, DatasetRecord
from tests.test_dcat_us_3 import catalog, configuration, record


def test_detailed_omissions_are_complete_and_preserve_input() -> None:
    """Every intentionally unsupported group is reported without its contents."""
    source = catalog(detailed=True)
    before = source.model_dump_json(exclude_none=True)
    projected = project_dcat(source, configuration())
    roots = {loss.field.split(".")[0] for loss in projected.losses}
    assert roots == {
        "core_party",
        "contract_id",
        "contract_version",
        "product_reference",
        "roles",
        "domain",
        "inventory_added",
        "metadata_reviewed",
        "update_frequency",
        "distributions",
        "services",
        "fields",
        "consumer",
        "commitments",
        "access_determination",
        "disclosure_determination",
        "metadata_review",
        "publication",
        "records",
        "capacity",
        "capacity_retention",
    }
    assert all(loss.target == "dcat-us-3" for loss in projected.losses)
    assert all(loss.code == "projection_omitted" for loss in projected.losses)
    assert all(loss.record_id == "asset-001" for loss in projected.losses)
    assert source.model_dump_json(exclude_none=True) == before
    assert len({loss.field for loss in projected.losses}) == len(projected.losses)
    assert [loss.field for loss in projected.losses] == sorted(
        loss.field for loss in projected.losses
    )


def test_omission_report_never_copies_values_or_invents_commitments() -> None:
    """Supplied commitments remain canonical while no guarantee is projected."""
    values = record().model_dump(exclude_none=True)
    values["commitments"] = [
        {
            "id": "assertion",
            "kind": "quality",
            "subject": "synthetic-sensitive-subject",
            "description": "synthetic-sensitive-assertion",
        }
    ]
    source = Catalog(
        schema_version="1.0", datasets=[DatasetRecord.model_validate(values)]
    )
    result = project_dcat(source, configuration())
    assert result.document is not None
    assert result.losses
    losses = "".join(item.model_dump_json() for item in result.losses)
    exported = result.document.model_dump_json(by_alias=True, exclude_none=True)
    assert "synthetic-sensitive" not in losses
    assert "synthetic-sensitive" not in exported
    assert "synthetic-sensitive" in source.model_dump_json()
    assert "quality" not in exported
    assert "slaProperties" not in exported
    assert not any(
        item.field.startswith("commitments")
        for item in project_dcat(catalog(), configuration()).losses
    )


def test_supplied_fields_keep_false_zero_and_empty_collections() -> None:
    """Unknown/zero/absent distinctions are not reduced to truthiness."""
    assert supplied_fields(value=False, path="flag") == {"flag"}
    assert supplied_fields(0, "count") == {"count"}
    assert supplied_fields([], "items") == {"items"}
    assert supplied_fields(None, "absent") == set()
    assert supplied_fields([False, 0], "items") == {"items"}


def test_loss_boundary_rejects_arbitrary_field_or_target() -> None:
    """Submitted values cannot be substituted for known field paths."""
    base = {
        "record_id": "item",
        "field": "title",
        "target": "dcat-us-3",
        "reason": "unsupported_mapping",
    }
    for change in (
        {"field": "synthetic-sensitive-title"},
        {"target": "unrecognized"},
        {"code": "arbitrary"},
        {"extra": "untyped"},
    ):
        with pytest.raises(ValidationError):
            ProjectionLoss.model_validate(base | change)
