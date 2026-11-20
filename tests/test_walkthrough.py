# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Frozen synthetic walkthrough inputs preserve their documented acceptance cases."""

import hashlib
from pathlib import Path
from typing import Literal

import pytest

from dscat.configuration import parse_configuration
from dscat.export.dcat_us_3 import project_dcat
from dscat.export.odcs_3_2 import project_odcs
from dscat.intake.limits import IntakeError
from dscat.intake.normalize import normalize_batch
from dscat.models.base import Sha256, StrictModel
from dscat.models.catalog import Catalog
from dscat.public_projection import project_public
from dscat.validation import validate_catalog
from tests.test_intake import batch_from

ROOT = Path(__file__).parent / "fixtures/walkthrough"
FixtureName = Literal[
    "minimum.xlsx",
    "detailed.xlsx",
    "invalid.xlsx",
    "conflict.xlsx",
    "future.xlsx",
    "formula.xlsx",
    "unsafe.xlsx",
    "shared.toml",
    "approved-public.toml",
    "detailed-canonical.json",
]


class WalkthroughManifest(StrictModel):
    """The manifest binds only closed synthetic fixture names and immutable bytes."""

    schema_version: Literal["1.0"]
    source_template_sha256: Sha256
    source_wheel_sha256: Sha256
    files: dict[FixtureName, Sha256]


def test_fixture_inventory_and_exact_byte_identities() -> None:
    """No changed or unlisted fixture can inherit the recorded walkthrough identity."""
    manifest = WalkthroughManifest.model_validate_json(
        (ROOT / "fixture-manifest.json").read_bytes()
    )
    assert set(manifest.files) == {
        path.name for path in ROOT.iterdir() if path.name != "fixture-manifest.json"
    }
    for name, digest in manifest.files.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("name", ["minimum.xlsx", "detailed.xlsx"])
def test_positive_workbooks_support_both_requested_targets(name: str) -> None:
    """Both workbook shapes validate and retain independently ready target outputs."""
    configuration = parse_configuration((ROOT / "shared.toml").read_bytes())
    normalized = normalize_batch(batch_from((ROOT / name).read_bytes()))
    assert not normalized.has_errors
    validated = validate_catalog(normalized.records, configuration.assessment)
    assert validated.catalog is not None
    assert validated.assessment.validity == "valid"
    assert project_dcat(validated.catalog, configuration).readiness.state == "ready"
    assert project_odcs(validated.catalog, configuration).readiness.state == "ready"
    if name == "detailed.xlsx":
        expected = Catalog.model_validate_json(
            (ROOT / "detailed-canonical.json").read_bytes()
        )
        assert validated.catalog == expected
        configured = parse_configuration((ROOT / "approved-public.toml").read_bytes())
        public = project_public(
            validated.catalog, configured, ["dcat-us-3", "odcs-3.2"]
        )
        assert all(item.state == "ready" for item in public.readiness)
        assert public.dcat is not None
        assert public.odcs
    else:
        public = project_public(
            validated.catalog, configuration, ["dcat-us-3", "odcs-3.2"]
        )
        assert all(item.state == "blocked" for item in public.readiness)
        assert public.dcat is None
        assert not public.odcs


@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("future.xlsx", "UNSUPPORTED_VERSION"),
        ("unsafe.xlsx", "UNSUPPORTED_WORKBOOK_PART"),
    ],
)
def test_hostile_or_future_workbooks_refuse_before_acceptance(
    name: str, code: str
) -> None:
    """Unsafe fixtures are inspected by the bounded parser and never opened in Excel."""
    with pytest.raises(IntakeError) as result:
        batch_from((ROOT / name).read_bytes())
    assert result.value.diagnostic.code == code


@pytest.mark.parametrize("name", ["invalid.xlsx", "formula.xlsx"])
def test_invalid_metadata_and_input_formulas_cannot_become_records(name: str) -> None:
    """Bypassed spreadsheet controls and formula input remain invalid intake."""
    normalized = normalize_batch(batch_from((ROOT / name).read_bytes()))
    assert normalized.has_errors
    assert not normalized.records
    assert {item.code for item in normalized.diagnostics} == {"INVALID_METADATA"}


def test_conflicting_fixture_withholds_the_catalog() -> None:
    """Distinct supplied metadata for the same identifier cannot overwrite a record."""
    configuration = parse_configuration((ROOT / "shared.toml").read_bytes())
    records = [
        record
        for name in ["minimum.xlsx", "conflict.xlsx"]
        for record in normalize_batch(batch_from((ROOT / name).read_bytes())).records
    ]
    result = validate_catalog(records, configuration.assessment)
    assert result.catalog is None
    assert "DUPLICATE_CONFLICT" in {item.code for item in result.diagnostics}
