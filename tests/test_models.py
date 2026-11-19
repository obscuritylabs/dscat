# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Canonical, intake, invocation and safe-result contract acceptance tests."""

import json
import socket
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from dscat.models.catalog import (
    ApprovalSubject,
    Catalog,
    Commitment,
    DataService,
    DatasetRecord,
    EntityReference,
    KnownCapacity,
    KnownRetention,
    PartyReference,
    PublicationDecision,
    RecordsManagement,
    RoleAssignment,
)
from dscat.models.diagnostics import CommandResult, CompletenessResult, Diagnostic
from dscat.models.intake import DetailRow, IntakeBatch, WorkbookMetadata
from dscat.models.requests import CommandRequest

if TYPE_CHECKING:
    from dscat.models.base import StrictModel

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"
MINIMUM = json.loads((FIXTURES / "minimum.json").read_text())
LOCATION = {"source_token": 1, "sheet": "Details_Quality", "row": 2}
RATE = {
    "kind": "average_ingestion",
    "state": "known",
    "value": "1",
    "unit": "MB",
    "normalized_bytes": 1000000,
    "basis": "logical",
    "measured_on": "2026-01-01",
    "window_start": "2026-01-01T00:00:00Z",
    "window_end": "2026-01-02T00:00:00Z",
}
APPROVAL = {
    "subject_kind": "canonical",
    "subject_id": "title",
    "target": "dcat-us-3",
    "approved_value_sha256": "a" * 64,
    "policy_version": "1.0",
    "authority": "Synthetic authority",
    "approved_on": "2026-01-01",
}


def test_minimum_does_not_infer_facts() -> None:
    """The four-field minimum is valid without dates, readiness or authority."""
    record = DatasetRecord.model_validate(MINIMUM)
    assert record.core_party.role == "unspecified_contact_or_owner"
    assert record.capacity is None
    assert record.publication is None
    assert record.metadata_review is None
    assert record.contract_version is None
    assert record.roles is None
    assert "capacity" not in record.model_dump(exclude_none=True)


def test_full_canonical_round_trip() -> None:
    """Every optional group survives typed JSON round trip with separate states."""
    record = DatasetRecord.model_validate_json(
        (FIXTURES / "detailed.json").read_bytes()
    )
    serialized = record.model_dump_json(exclude_none=True)
    assert DatasetRecord.model_validate_json(serialized) == record
    assert record.dataset_version != record.contract_version
    assert record.contract_id != record.id
    assert record.publication is not None
    assert record.publication.state == "unknown"
    assert record.access_determination is not None
    assert record.access_determination.state == "partially_restricted"
    assert record.disclosure_determination is not None
    assert record.disclosure_determination.state == "unknown"
    assert record.metadata_review is not None
    assert record.metadata_review.state == "not_reviewed"
    assert "2026-01-01T00:00:00Z" in serialized
    assert "source_token" not in serialized


@pytest.mark.parametrize(
    "changes",
    [
        {"id": ""},
        {"title": "  "},
        {"description": None},
        {"extra": "synthetic"},
        {"lineage": []},
        {"core_party": {"label": "Support", "owner": True}},
        {"core_party": {"label": "Support", "email": "not-an-email"}},
        {"core_party": {"label": "Support", "role": "accountable_owner"}},
        {
            "fields": [
                {
                    "object_name": "x",
                    "field_name": "y",
                    "type": "string",
                    "nullable": "No",
                }
            ]
        },
        {"inventory_added": "2026-02-30"},
        {"inventory_added": "01/01/2026"},
        {"capacity": [{"kind": "size", "state": "unknown", "value": "0"}]},
        {"capacity_retention": {"state": "unknown", "days": 0}},
        {"capacity_retention": {"state": "indefinite", "days": 0}},
        {"capacity_retention": {"state": "known", "days": True}},
        {"capacity_retention": {"state": "known", "days": -1}},
        {"capacity_retention": {"state": "known", "days": 2**31}},
        {"capacity_retention": {"state": "known", "days": 1.5}},
    ],
)
def test_invalid_canonical_facts(changes: dict[str, object]) -> None:
    """Unknown/null/malformed/coerced facts cannot enter canonical storage."""
    with pytest.raises(ValidationError):
        DatasetRecord.model_validate_json(json.dumps(MINIMUM | changes))


def test_absent_unknown_zero_and_indefinite_are_distinct() -> None:
    """Explicit unknown and zero values never collapse into absence."""
    values = [
        DatasetRecord.model_validate_json(json.dumps(MINIMUM | change))
        for change in [
            {},
            {"capacity_retention": {"state": "unknown"}},
            {"capacity_retention": {"state": "known", "days": 0}},
            {"capacity_retention": {"state": "indefinite"}},
        ]
    ]
    assert len({r.model_dump_json(exclude_none=True) for r in values}) == len(values)
    assert KnownRetention(state="known", days=2**31 - 1).days == 2**31 - 1
    assert RecordsManagement(duration_days=0).duration_days == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"normalized_bytes": 0},
        {"normalized_bytes": True},
        {"value": "1e6"},
        {"measured_on": "2026-13-01"},
        {"window_start": "2026-01-01T00:00:00"},
        {"window_start": "2026-01-02T00:00:00Z"},
        {"window_end": "2025-12-01T00:00:00Z"},
        {"window_start": None},
        {"window_end": None},
        {"kind": "size"},
    ],
)
def test_invalid_quantity_context(changes: dict[str, object]) -> None:
    """Rates require exact bytes and a valid explicitly offset measurement window."""
    with pytest.raises(ValidationError):
        KnownCapacity.model_validate_json(json.dumps(RATE | changes))


def test_known_size_and_missing_rate_windows() -> None:
    """Known zero size needs no rate window; rates need both endpoints."""
    size = {key: value for key, value in RATE.items() if not key.startswith("window_")}
    size |= {"kind": "size", "value": "0", "normalized_bytes": 0}
    assert KnownCapacity.model_validate_json(json.dumps(size)).normalized_bytes == 0
    for removed in ("window_start", "window_end"):
        data = {key: value for key, value in RATE.items() if key != removed}
        with pytest.raises(ValidationError, match="window"):
            KnownCapacity.model_validate_json(json.dumps(data))
    for endpoint in ("window_start", "window_end"):
        with pytest.raises(ValidationError, match="Size"):
            KnownCapacity.model_validate_json(
                json.dumps(size | {endpoint: RATE[endpoint]})
            )


def test_comparable_and_incomparable_rates() -> None:
    """Only equal bases and windows constrain peak versus average ingestion."""
    peak = RATE | {"kind": "peak_ingestion", "value": "0", "normalized_bytes": 0}
    with pytest.raises(ValidationError, match="peak"):
        DatasetRecord.model_validate_json(
            json.dumps(MINIMUM | {"capacity": [RATE, peak]})
        )
    for changed in (
        {"basis": "physical"},
        {"window_end": "2026-01-03T00:00:00Z"},
        {"value": "1", "normalized_bytes": 1000000},
    ):
        record = DatasetRecord.model_validate_json(
            json.dumps(MINIMUM | {"capacity": [RATE, peak | changed]})
        )
        assert record.capacity is not None
    assert (
        DatasetRecord.model_validate_json(
            json.dumps(MINIMUM | {"capacity": [peak]})
        ).capacity
        is not None
    )


@pytest.mark.parametrize(
    ("field", "item"),
    [
        ("distributions", {"id": "one"}),
        ("services", {"id": "one"}),
        (
            "roles",
            {
                "party_id": "p",
                "role": "contact",
                "label": "Support",
                "reference_kind": "local",
            },
        ),
        ("fields", {"object_name": "o", "field_name": "f", "type": "string"}),
        (
            "commitments",
            {
                "id": "c",
                "kind": "service",
                "subject": "o",
                "description": "Supplied assertion",
            },
        ),
        ("capacity", {"kind": "size", "state": "unknown"}),
        ("capacity", RATE),
    ],
)
def test_duplicate_collection_keys(field: str, item: dict[str, object]) -> None:
    """Ambiguous object/role/field/measurement keys cannot overwrite facts."""
    with pytest.raises(ValidationError, match="Duplicate"):
        DatasetRecord.model_validate_json(json.dumps(MINIMUM | {field: [item, item]}))


def test_set_order_and_ordered_fields() -> None:
    """Set-like metadata is deterministic; ordered schemas preserve submitted order."""
    changes = {
        "distributions": [{"id": "z"}, {"id": "a"}],
        "services": [{"id": "z"}, {"id": "a"}],
        "consumer": {"intended_uses": ["Z", " A "]},
        "roles": [
            {
                "party_id": "p",
                "role": role,
                "label": "Support",
                "reference_kind": "local",
            }
            for role in ("steward", "contact")
        ],
        "fields": [
            {"object_name": "o", "field_name": field, "type": "string"}
            for field in ("z", "a")
        ],
    }
    record = DatasetRecord.model_validate(MINIMUM | changes)
    assert record.distributions is not None
    assert record.distributions[0].id == "a"
    assert record.services is not None
    assert record.services[0].id == "a"
    assert record.consumer is not None
    assert record.consumer.intended_uses == ["A", "Z"]
    assert record.roles is not None
    assert record.roles[0].role == "contact"
    assert record.fields is not None
    assert record.fields[0].field_name == "z"
    with pytest.raises(ValidationError, match="Duplicate normalized"):
        DatasetRecord.model_validate(
            MINIMUM | {"consumer": {"intended_uses": ["A", " A "]}}
        )


def test_catalog_links_and_identity_order() -> None:
    """Local references resolve case-sensitively; external references remain inert."""
    first = MINIMUM | {"id": "A"}
    second = MINIMUM | {
        "id": "a",
        "services": [
            {
                "id": "s",
                "served_datasets": [
                    {"reference_kind": "local", "id": "A"},
                    {"reference_kind": "external", "id": "urn:example:external"},
                ],
            }
        ],
    }
    catalog = Catalog.model_validate(
        {"schema_version": "1.0", "datasets": [second, first]}
    )
    assert [r.id for r in catalog.datasets] == ["A", "a"]
    assert Catalog(schema_version="1.0", datasets=[]).datasets == []
    with pytest.raises(ValidationError, match="Unresolved"):
        Catalog.model_validate({"schema_version": "1.0", "datasets": [second]})
    with pytest.raises(ValidationError, match="Duplicate dataset"):
        Catalog.model_validate({"schema_version": "1.0", "datasets": [first, first]})
    with pytest.raises(ValidationError):
        Catalog.model_validate({"schema_version": "2.0", "datasets": []})


def test_explicit_reference_kind_controls_normalization() -> None:
    """Local IDs and external references use distinct rules without kind inference."""
    assert EntityReference(reference_kind="local", id=" asset-001 ").id == "asset-001"
    external = RoleAssignment(
        reference_kind="external",
        party_id="urn:example:party",
        role="contact",
        label="External support",
    )
    assert external.party_id == "urn:example:party"
    with pytest.raises(ValidationError):
        RoleAssignment(
            reference_kind="external",
            party_id="local-party",
            role="contact",
            label="Support",
        )
    with pytest.raises(ValidationError):
        EntityReference.model_validate(
            {"reference_kind": "inferred", "id": "asset-001"}
        )


@pytest.mark.parametrize(
    ("model", "data"),
    [
        (EntityReference, {"reference_kind": "local", "id": "a/b"}),
        (EntityReference, {"reference_kind": "external", "id": "local-id"}),
        (EntityReference, {"reference_kind": "external", "id": "https://a.example/\n"}),
        (
            RoleAssignment,
            {
                "party_id": "a/b",
                "reference_kind": "local",
                "role": "contact",
                "label": "Support",
            },
        ),
        (
            DataService,
            {
                "id": "s",
                "served_datasets": [
                    {"reference_kind": "local", "id": "a"},
                    {"reference_kind": "local", "id": "a"},
                ],
            },
        ),
        (Commitment, {"id": "c", "kind": "quality", "subject": "o"}),
        (
            Commitment,
            {
                "id": "c",
                "kind": "service",
                "subject": "o",
                "description": "Supplied",
                "unit": "percent",
            },
        ),
        (
            ApprovalSubject,
            {"subject_kind": "canonical", "subject_id": "*", "target": "dcat-us-3"},
        ),
        (
            ApprovalSubject,
            {
                "subject_kind": "derived_target",
                "subject_id": "catalog_iri",
                "target": "odcs-3.2",
            },
        ),
        (
            ApprovalSubject,
            {
                "subject_kind": "derived_target",
                "subject_id": "contract_iri",
                "target": "dcat-us-3",
            },
        ),
    ],
)
def test_invalid_reference_assertion_and_approval_boundaries(
    model: type[StrictModel], data: dict[str, object]
) -> None:
    """No implicit references, empty assertions or unknown approval scopes pass."""
    with pytest.raises(ValidationError):
        model.model_validate(data)


def test_publication_scope_and_dates() -> None:
    """Approval tuples are unique and hashes/dates/authority are supplied facts."""
    good = {"state": "approved", "approvals": [APPROVAL]}
    assert PublicationDecision.model_validate_json(json.dumps(good)).state == "approved"
    for change in (
        {"authority": ""},
        {"approved_on": "tomorrow"},
        {"approved_value_sha256": "A" * 64},
        {"target": "all"},
        {"policy_version": None},
    ):
        with pytest.raises(ValidationError):
            PublicationDecision.model_validate_json(
                json.dumps(good | {"approvals": [APPROVAL | change]})
            )
    with pytest.raises(ValidationError, match="Duplicate publication"):
        PublicationDecision.model_validate_json(
            json.dumps(good | {"approvals": [APPROVAL, APPROVAL]})
        )
    assert PublicationDecision(state="unknown").approvals is None
    for target, subject in (("dcat-us-3", "dataset_iri"), ("odcs-3.2", "contract_iri")):
        assert (
            ApprovalSubject.model_validate(
                {
                    "subject_kind": "derived_target",
                    "subject_id": subject,
                    "target": target,
                }
            ).subject_id
            == subject
        )


def test_email_validation_never_queries_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Syntactic role email checks do not attempt deliverability or DNS resolution."""

    def deny(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Unexpected DNS or socket operation")

    monkeypatch.setattr(socket, "getaddrinfo", deny)
    monkeypatch.setattr(socket, "socket", deny)
    assert (
        PartyReference(label="Support", email="metadata@example.org").email
        == "metadata@example.org"
    )


def test_all_detail_properties_and_duplicate_rejection() -> None:
    """Fixtures derived from the approved table exercise every closed property."""
    rows = [
        DetailRow.model_validate(
            {"location": LOCATION, "dataset_id": "asset-001"} | row
        )
        for row in json.loads((FIXTURES / "details-vocabulary.json").read_text())
    ]
    batch = IntakeBatch(
        metadata=WorkbookMetadata(schema_version="1.0", kind="dataset-intake"),
        datasets=[],
        fields=[],
        details=rows,
    )
    assert len(batch.details) == len(rows)
    with pytest.raises(ValidationError, match="Repeated detail"):
        IntakeBatch.model_validate(
            batch.model_dump(exclude_none=True) | {"details": [rows[0], rows[0]]}
        )
    for changes in (
        {"section": "lineage"},
        {"property": "extra"},
        {"entry_id": "other"},
        {"unit": "B"},
        {"reference": "urn:example:ref"},
        {"value": None},
    ):
        with pytest.raises(ValidationError):
            DetailRow.model_validate(rows[0].model_dump(exclude_none=True) | changes)
    assert (
        DetailRow.model_validate(
            {
                "location": LOCATION,
                "dataset_id": "asset-001",
                "section": "records",
                "entry_id": "conflict-001",
                "property": "conflict",
                "value": "Supplied conflict",
            }
        ).entry_id
        == "conflict-001"
    )
    assert (
        DetailRow.model_validate(
            {
                "location": LOCATION,
                "dataset_id": "asset-001",
                "section": "commitment",
                "entry_id": "q",
                "property": "value",
                "value": "99",
                "unit": "percent",
                "reference": "urn:example:assertion",
            }
        ).unit
        == "percent"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"command": "validate"},
        {"command": "build", "input": Path("in.xlsx")},
        {"command": "template", "output": Path("out.xlsx"), "input": Path("in.xlsx")},
        {
            "command": "template",
            "output": Path("out.xlsx"),
            "config": Path("config.toml"),
        },
        {"command": "template", "output": Path("out.xlsx"), "targets": ["dcat-us-3"]},
        {"command": "template", "output": Path("out.xlsx"), "recursive": True},
        {"command": "validate", "input": Path("in.xlsx"), "output": Path("out")},
        {"command": "validate", "input": Path("in.xlsx"), "targets": ["dcat-us-3"]},
        {"command": "validate", "input": Path("in.xlsx"), "replace": True},
        {"command": "export", "input": Path("catalog"), "output": Path("out")},
        {
            "command": "export",
            "input": Path("catalog"),
            "output": Path("out"),
            "targets": ["dcat-us-3"],
            "recursive": True,
        },
        {
            "command": "build",
            "input": Path("in.xlsx"),
            "output": Path("out"),
            "audience": "public",
        },
        {
            "command": "build",
            "input": Path("in.xlsx"),
            "output": Path("out"),
            "targets": ["dcat-us-3", "dcat-us-3"],
        },
    ],
)
def test_invalid_command_shapes(changes: dict[str, object]) -> None:
    """Invalid invocations fail before config, input, discovery or output work."""
    with pytest.raises(ValidationError):
        CommandRequest.model_validate(changes)


def test_command_and_result_round_trip() -> None:
    """Valid invocations/results remain typed and independently versioned."""
    request = CommandRequest(
        command="export",
        input=Path("catalog"),
        output=Path("out"),
        targets=["dcat-us-3"],
        audience="public",
    )
    assert (
        CommandRequest.model_validate_json(request.model_dump_json(exclude_none=True))
        == request
    )
    for data in (
        {"command": "template", "output": Path("out.xlsx")},
        {"command": "validate", "input": Path("in.xlsx")},
        {"command": "build", "input": Path("in.xlsx"), "output": Path("out")},
    ):
        assert CommandRequest.model_validate(data).audience == "internal"
    result = CommandResult.model_validate(
        {
            "schema_version": "1.0",
            "command": "validate",
            "exit_code": 0,
            "diagnostics": [],
            "summary": {},
            "assessment": {
                "validity": "valid",
                "targets": [
                    {
                        "target": "dcat-us-3",
                        "state": "blocked",
                        "reasons": ["target_contact_missing"],
                    }
                ],
            },
        }
    )
    assert (
        CommandResult.model_validate_json(result.model_dump_json(exclude_none=True))
        == result
    )
    with pytest.raises(ValidationError):
        CommandResult.model_validate(
            result.model_dump(exclude_none=True) | {"exit_code": -1}
        )
    for data in (
        {"code": "UNTRUSTED", "severity": "error", "message_key": "correct_metadata"},
        {
            "code": "INVALID_METADATA",
            "severity": "error",
            "message_key": "raw sensitive text",
        },
        {
            "code": "INVALID_METADATA",
            "severity": "error",
            "message_key": "correct_metadata",
            "source_token": "/private/path",
        },
    ):
        with pytest.raises(ValidationError):
            Diagnostic.model_validate(data)


def test_completeness_locations_are_schema_defined() -> None:
    """Assessment output cannot reflect an arbitrary path or supplied content."""
    assert (
        CompletenessResult(path="core_party.email", state="absent").path
        == "core_party.email"
    )
    with pytest.raises(ValidationError, match="Unknown canonical"):
        CompletenessResult(path="/synthetic/private-path", state="present")
