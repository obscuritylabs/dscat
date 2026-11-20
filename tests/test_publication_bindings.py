# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Exact-value identity, closed dependencies and independent supplied authority."""

import hashlib
import json
from datetime import date
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from dscat import projection
from dscat import publication_bindings as bindings
from dscat.models.catalog import DatasetRecord
from dscat.models.configuration import ExportConfiguration
from dscat.projection import (
    approve_subject,
    contact_selected,
    eligible_record,
    resolve_subjects,
    source_of,
    subject_approved,
)
from tests.test_dcat_us_3 import configuration, record

if TYPE_CHECKING:
    from dscat.models.base import Target

APPROVED_ON = date(2026, 1, 3)


def approved_fixture(
    *, detailed: bool = False
) -> tuple[DatasetRecord, ExportConfiguration]:
    """Supply synthetic review/disclosure/publication facts and exact scoped grants."""
    source = record(detailed=detailed)
    configuration_values = configuration().model_dump(exclude_none=True)
    targets: tuple[Target, ...] = ("dcat-us-3", "odcs-3.2")
    scopes = [
        subject
        for target in targets
        for subject in resolve_subjects(source, configuration(), target)
    ]
    configuration_values["publication"] = {
        "policy_version": "synthetic-policy-1",
        "authority_reference": "Synthetic publication authority",
        "allowed_subjects": [
            subject.model_dump(exclude={"value"}) for subject in scopes
        ],
    }
    configured = ExportConfiguration.model_validate(configuration_values)
    values = source.model_dump(exclude_none=True)
    values["metadata_review"] = {
        "state": "approved",
        "authority": "Synthetic review authority",
        "reviewed_on": "2026-01-01",
    }
    values["disclosure_determination"] = {
        "state": "unrestricted",
        "authority": "Synthetic disclosure authority",
        "determined_on": "2026-01-02",
        "review_status": "approved",
    }
    values["publication"] = {
        "state": "approved",
        "approvals": [
            approve_subject(
                subject,
                policy_version="synthetic-policy-1",
                authority="Synthetic publication authority",
                approved_on=APPROVED_ON,
            ).model_dump(mode="json")
            for subject in scopes
        ],
    }
    return DatasetRecord.model_validate(values), configured


def test_hash_encoding_is_compact_nfc_sorted_and_has_no_lf() -> None:
    """Normalize equivalent text while preserving scalar types and list order."""
    expected = json.dumps(
        {"a": "é", "z": False},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert (
        bindings.value_hash({"z": False, "a": "e\u0301"})
        == hashlib.sha256(expected).hexdigest()
    )
    assert bindings.value_hash(value=True) != bindings.value_hash(1)
    assert bindings.value_hash(["a", "b"]) != bindings.value_hash(["b", "a"])
    assert bindings.value_hash(None) != bindings.value_hash("")
    with pytest.raises(ValueError, match="Out of range float"):
        bindings.value_hash(float("nan"))
    with pytest.raises(ValueError, match="Duplicate normalized"):
        bindings.value_hash({"é": 1, "e\u0301": 2})


def test_closed_source_kinds_and_unique_dependencies() -> None:
    """A dependency name cannot migrate between canonical and configuration meaning."""
    source = bindings.binding_input("canonical", "id", "asset-001")
    assert source.value_sha256 == bindings.value_hash("asset-001")
    with pytest.raises(ValidationError):
        bindings.BindingInput(
            subject_kind="canonical",
            subject_id="identity.dataset_namespace",
            value_sha256=source.value_sha256,
        )
    with pytest.raises(ValidationError):
        bindings.BindingInput(
            subject_kind="configuration",
            subject_id="unknown",
            value_sha256=source.value_sha256,
        )
    with pytest.raises(ValidationError):
        bindings.DerivedBinding(
            value="https://example.org/asset",
            mapping_version="test",
            sources=[source, source],
        )
    with pytest.raises(ValidationError):
        bindings.DerivedBinding(
            value="https://example.org/asset", mapping_version="test", sources=[]
        )


def test_derived_approval_binds_mapping_value_and_every_source() -> None:
    """Same emitted text under a different actual source cannot reuse a grant."""
    direct = bindings.binding_input("canonical", "contract_id", "contract-001")
    configured = bindings.binding_input(
        "configuration", "identity.contract_namespace", "https://example.org/contracts/"
    )
    first = bindings.derived_subject(
        "odcs-3.2", "contract_iri", "contract-001", [direct]
    )
    second = bindings.derived_subject(
        "odcs-3.2", "contract_iri", "contract-001", [configured]
    )
    assert first.value_sha256() != second.value_sha256()
    with pytest.raises(ValueError, match="Derived publication values"):
        source_of(first)
    grant = approve_subject(
        first,
        policy_version="synthetic-policy-1",
        authority="Synthetic authority",
        approved_on=APPROVED_ON,
    )
    assert grant.approved_value_sha256 == first.value_sha256()
    assert grant.authority == "Synthetic authority"
    assert grant.approved_on == APPROVED_ON


def test_explicit_grants_match_only_current_allowed_subjects() -> None:
    """Neither policy alone nor stale/hash-mismatched record approval grants access."""
    source, configured = approved_fixture()
    assert eligible_record(source, configured)
    for target in ("dcat-us-3", "odcs-3.2"):
        assert all(
            subject_approved(source, configured, item)
            for item in resolve_subjects(source, configured, target)
        )
    subject = resolve_subjects(source, configured, "dcat-us-3")[0]
    assert not subject_approved(record(), configured, subject)
    assert not subject_approved(source, configuration(), subject)
    data = configured.model_dump(exclude_none=True)
    data["publication"]["allowed_subjects"] = []
    assert not subject_approved(
        source, ExportConfiguration.model_validate(data), subject
    )
    data = configured.model_dump(exclude_none=True)
    data["publication"]["policy_version"] = "changed-policy"
    assert not subject_approved(
        source, ExportConfiguration.model_validate(data), subject
    )
    changed = DatasetRecord.model_validate(
        source.model_dump(exclude_none=True) | {"id": "changed"}
    )
    assert not subject_approved(
        changed, configured, resolve_subjects(changed, configured, "dcat-us-3")[0]
    )


@pytest.mark.parametrize(
    "control",
    [
        "review",
        "review_authority",
        "review_date",
        "disclosure",
        "disclosure_authority",
        "disclosure_date",
        "disclosure_review",
        "publication",
        "policy",
    ],
)
def test_independent_controls_must_permit_projection(control: str) -> None:
    """Validation or a supplied publication flag cannot replace independent controls."""
    source, configured = approved_fixture()
    values = source.model_dump(exclude_none=True)
    if control == "review":
        values["metadata_review"]["state"] = "not_reviewed"
    elif control == "review_authority":
        del values["metadata_review"]["authority"]
    elif control == "review_date":
        del values["metadata_review"]["reviewed_on"]
    elif control == "disclosure":
        values["disclosure_determination"]["state"] = "unknown"
    elif control == "disclosure_authority":
        del values["disclosure_determination"]["authority"]
    elif control == "disclosure_date":
        del values["disclosure_determination"]["determined_on"]
    elif control == "disclosure_review":
        values["disclosure_determination"]["review_status"] = "in_review"
    elif control == "publication":
        values["publication"]["state"] = "unknown"
    else:
        configured = configuration()
    assert not eligible_record(DatasetRecord.model_validate(values), configured)


def test_data_access_state_does_not_establish_metadata_disclosure() -> None:
    """Keep metadata disclosure independent from underlying data access."""
    source, configured = approved_fixture()
    restricted = DatasetRecord.model_validate(
        source.model_dump(exclude_none=True)
        | {"access_determination": {"state": "fully_restricted"}}
    )
    assert eligible_record(restricted, configured)
    assert not eligible_record(record(), configured)


def test_optional_contact_selection_requires_actual_contact_scopes() -> None:
    """Leave unselected ODCS members omitted while requiring DCAT contact."""
    assert contact_selected(record(), "dcat-us-3")
    assert not contact_selected(record(), "odcs-3.2")
    source, _configured = approved_fixture()
    assert contact_selected(source, "odcs-3.2")
    values = source.model_dump(exclude_none=True)
    values["publication"]["approvals"] = [
        item
        for item in values["publication"]["approvals"]
        if item["target"] == "dcat-us-3"
    ]
    assert not contact_selected(DatasetRecord.model_validate(values), "odcs-3.2")


def test_missing_resolution_inputs_do_not_fabricate_derived_subjects() -> None:
    """A partial factual resolution is never a derived-value approval substitute."""
    for target in ("dcat-us-3", "odcs-3.2"):
        subjects = resolve_subjects(
            record(), ExportConfiguration(schema_version="1.0"), target
        )
        assert not any(item.subject_kind == "derived_target" for item in subjects)


def test_direct_contact_without_shared_mapping_uses_its_canonical_source() -> None:
    """A direct declared contact does not depend on an invented shared mapping."""
    values = record().model_dump(exclude_none=True)
    values["core_party"] = {
        "label": "Metadata support",
        "role": "contact",
        "email": "direct@example.org",
    }
    configured = configuration().model_dump(exclude_none=True)
    configured["identity"]["parties"] = {}
    subjects = resolve_subjects(
        DatasetRecord.model_validate(values),
        ExportConfiguration.model_validate(configured),
        "dcat-us-3",
    )
    assert any(item.subject_id == "core_party.email" for item in subjects)
    derived = next(item for item in subjects if item.subject_id == "contact_email_iri")
    binding = bindings.DerivedBinding.model_validate(derived.value)
    assert binding.value == "mailto:direct@example.org"
    assert all(item.subject_kind == "canonical" for item in binding.sources)


def test_inconsistent_resolver_result_cannot_invent_missing_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A trusted resolver regression still cannot manufacture identity dependencies."""
    monkeypatch.setattr(
        projection, "contract_facts", lambda *_args: ("contract", "1", set())
    )
    with pytest.raises(
        ValueError, match="Missing selected contract identity dependencies"
    ):
        resolve_subjects(
            record(), ExportConfiguration(schema_version="1.0"), "odcs-3.2"
        )
