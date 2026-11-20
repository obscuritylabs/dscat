# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Independent ODCS identity/version, optional mappings, cardinality and losses."""

import json
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from dscat.export import odcs_3_2 as odcs
from dscat.export.odcs_models import OdcsDocument
from dscat.models.catalog import Catalog, DatasetRecord
from dscat.models.configuration import ExportConfiguration
from dscat.resources.registry import (
    DOCUMENT,
    ResourceBundle,
    ResourceError,
    load_registry,
)
from dscat.storage.flatfiles import load_snapshot
from dscat.storage.publication import publish
from tests.test_dcat_us_3 import catalog, configuration, record

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("detailed", [False, True])
def test_minimum_detail_actual_schema_and_repeat_after_reload(
    tmp_path: Path, *, detailed: bool
) -> None:
    """Contract identity/version and optional facts survive deterministic projection."""
    source = catalog(detailed=detailed)
    before = source.model_dump_json(exclude_none=True)
    result = odcs.project_odcs(source, configuration())
    assert result.readiness.state == "ready"
    assert len(result.documents) == 1
    raw = odcs.serialize_odcs(result.documents[0])
    payload = json.loads(raw)
    assert payload["apiVersion"] == "v3.2.0"
    assert payload["kind"] == "DataContract"
    assert payload["id"] == (
        "contract-001" if detailed else "https://example.org/contracts/asset-001"
    )
    assert payload["version"] == "2.7.0"
    assert payload["name"] == source.datasets[0].title
    assert payload["description"]["customProperties"] == [
        {"property": "catalogDescription", "value": source.datasets[0].description}
    ]
    assert "purpose" not in payload["description"]
    assert "quality" not in payload
    assert "slaProperties" not in payload
    assert "servers" not in payload
    assert raw.endswith(b"\n")
    publish(tmp_path / "bundle", source)
    repeated = odcs.project_odcs(
        load_snapshot(tmp_path / "bundle").catalog, configuration()
    )
    assert odcs.serialize_odcs(repeated.documents[0]) == raw
    assert repeated.losses == result.losses
    assert source.model_dump_json(exclude_none=True) == before
    if detailed:
        assert {
            item["property"]: item["value"] for item in payload["customProperties"]
        } == {"datasetIdentifier": "asset-001", "datasetVersion": "2026-Q1"}
        assert payload["description"]["usage"] == "Synthetic evaluation"
        assert payload["description"]["limitations"] == "Synthetic data only"
        assert payload["description"]["authoritativeDefinitions"] == [
            {"url": "urn:example:measurement", "type": "semanticReference"}
        ]
        assert any(item.field.startswith("commitments.") for item in result.losses)
    else:
        assert payload["team"] == {
            "members": [
                {"username": "metadata@example.org", "name": "Metadata support"}
            ]
        }
        assert "schema" not in payload


@pytest.mark.parametrize("missing", ["identity", "rule", "version", "all", "invalid"])
def test_missing_contract_facts_do_not_invent_defaults(missing: str) -> None:
    """Dataset/application/workbook versions cannot become a contract version."""
    values = configuration().model_dump(exclude_none=True)
    if missing in {"identity", "all"}:
        del values["identity"]["contract_namespace"]
    if missing == "rule":
        del values["identity"]["contract_identity_rule"]
    if missing in {"version", "all"}:
        del values["odcs_3_2"]["contract_version"]
    result = odcs.project_odcs(
        None if missing == "invalid" else catalog(),
        ExportConfiguration.model_validate(values),
    )
    assert result.readiness.state == "blocked"
    assert result.documents == []
    expected = (
        ["INVALID_METADATA"]
        if missing == "invalid"
        else ["target_contract_identity_missing", "target_contract_version_missing"]
        if missing == "all"
        else ["target_contract_version_missing"]
        if missing == "version"
        else ["target_contract_identity_missing"]
    )
    assert result.readiness.reasons == expected


def test_per_record_identity_override_and_version_agreement() -> None:
    """Explicit identity overrides derivation; two supplied versions must agree."""
    data = record().model_dump(exclude_none=True) | {
        "contract_id": "explicit-contract",
        "contract_version": "9",
        "dataset_version": "dataset-42",
    }
    source = Catalog(
        schema_version="1.0", datasets=[DatasetRecord.model_validate(data)]
    )
    assert odcs.project_odcs(source, configuration()).readiness.reasons == [
        "target_fact_conflict"
    ]
    values = configuration().model_dump(exclude_none=True)
    values["odcs_3_2"]["contract_version"] = "9"
    result = odcs.project_odcs(source, ExportConfiguration.model_validate(values))
    assert result.documents[0].id == "explicit-contract"
    assert result.documents[0].version == "9"
    explicit = ExportConfiguration(schema_version="1.0")
    assert odcs.project_odcs(source, explicit).documents[0].id == "explicit-contract"
    assert odcs.project_odcs(source, explicit).documents[0].version == "9"


@pytest.mark.parametrize("collision", ["duplicate_contract", "dataset"])
def test_contract_identities_remain_distinct(collision: str) -> None:
    """Duplicate contracts and reuse of a known dataset IRI block all output."""
    base = record().model_dump(exclude_none=True)
    first = base | {
        "contract_id": "shared"
        if collision == "duplicate_contract"
        else "https://example.org/datasets/asset-001"
    }
    records = [DatasetRecord.model_validate(first)]
    if collision == "duplicate_contract":
        records.append(
            DatasetRecord.model_validate(
                base | {"id": "second", "contract_id": "shared"}
            )
        )
    result = odcs.project_odcs(
        Catalog(schema_version="1.0", datasets=records), configuration()
    )
    assert result.documents == []
    assert result.readiness.reasons == ["target_fact_conflict"]


@pytest.mark.parametrize(
    "type_name",
    [
        "string",
        "date",
        "timestamp",
        "time",
        "number",
        "integer",
        "object",
        "array",
        "boolean",
        "map",
        "vector",
        "CustomType",
    ],
)
def test_logical_types_and_unknown_spelling(type_name: str) -> None:
    """Known declared types map exactly; unsupported types stay named properties."""
    data = record().model_dump(exclude_none=True) | {
        "fields": [{"object_name": "table", "field_name": "field", "type": type_name}]
    }
    result = odcs.project_odcs(
        Catalog(schema_version="1.0", datasets=[DatasetRecord.model_validate(data)]),
        configuration(),
    )
    assert result.readiness.state == "ready"
    payload = json.loads(odcs.serialize_odcs(result.documents[0]))["schema"][0]
    field = payload["properties"][0]
    assert payload["logicalType"] == "object"
    if type_name in {"map", "vector", "CustomType"}:
        assert "logicalType" not in field
        assert field["customProperties"] == [
            {"property": "catalogFieldType", "value": type_name}
        ]
    else:
        assert field["logicalType"] == type_name
        assert "customProperties" not in field
    assert "physicalType" not in field
    assert "properties" not in field
    assert "items" not in field


@pytest.mark.parametrize("nullable", [None, False, True])
def test_nullable_semantic_references_and_field_order(*, nullable: bool | None) -> None:
    """Keep exact nullable semantics, field order and inert normalized references."""
    fields = []
    for object_name, name in [("z", "second"), ("a", "first"), ("z", "first")]:
        item = {
            "object_name": object_name,
            "field_name": name,
            "type": "number",
            "description": "Synthetic amount",
            "semantic_references": ["urn:example:amount"],
        }
        if nullable is not None:
            item["nullable"] = nullable
        fields.append(item)
    data = record().model_dump(exclude_none=True) | {"fields": fields}
    result = odcs.project_odcs(
        Catalog(schema_version="1.0", datasets=[DatasetRecord.model_validate(data)]),
        configuration(),
    )
    objects = json.loads(odcs.serialize_odcs(result.documents[0]))["schema"]
    assert [item["name"] for item in objects] == ["a", "z"]
    assert [item["name"] for item in objects[1]["properties"]] == ["second", "first"]
    field = objects[0]["properties"][0]
    assert field["authoritativeDefinitions"] == [
        {"type": "semanticReference", "url": "urn:example:amount"}
    ]
    if nullable is None:
        assert "customProperties" not in field
    else:
        assert field["customProperties"] == [
            {"property": "canonicalNullable", "value": nullable}
        ]


@pytest.mark.parametrize("count", [0, 1, 2])
def test_usage_and_limitations_never_join_or_choose(count: int) -> None:
    """Multiple consumer assertions stay canonical with explicit scalar losses."""
    data = record().model_dump(exclude_none=True) | {
        "consumer": {"semantic_references": ["urn:example:definition"]}
    }
    if count:
        data["consumer"]["intended_uses"] = [f"Use {i}" for i in range(count)]
        data["consumer"]["limitations"] = [f"Limit {i}" for i in range(count)]
    source = Catalog(
        schema_version="1.0", datasets=[DatasetRecord.model_validate(data)]
    )
    result = odcs.project_odcs(source, configuration())
    assert result.readiness.state == "ready"
    description = json.loads(odcs.serialize_odcs(result.documents[0]))["description"]
    assert description["authoritativeDefinitions"] == [
        {"type": "semanticReference", "url": "urn:example:definition"}
    ]
    if count == 1:
        assert description["usage"] == "Use 0"
        assert description["limitations"] == "Limit 0"
    else:
        assert "usage" not in description
        assert "limitations" not in description
    losses = {
        item.field for item in result.losses if item.reason == "unsupported_cardinality"
    }
    assert losses == (
        {"consumer.intended_uses", "consumer.limitations"} if count > 1 else set()
    )


def test_optional_unresolved_members_do_not_block_otherwise_ready_contracts() -> None:
    """A valid minimal intake can export without inventing optional party identities."""
    values = configuration().model_dump(exclude_none=True)
    values["identity"]["parties"] = {}
    result = odcs.project_odcs(catalog(), ExportConfiguration.model_validate(values))
    assert result.readiness.state == "ready"
    assert result.documents[0].team is None
    assert any(
        item.field == "core_party.label" and item.reason == "unresolved_contact"
        for item in result.losses
    )


def test_selected_version_and_no_arbitrary_target_extensions() -> None:
    """Upstream legacy versions or arbitrary guarantees are outside this adapter."""
    result = odcs.project_odcs(catalog(), configuration())
    raw = result.documents[0].model_dump(mode="json", by_alias=True, exclude_none=True)
    for change in (
        {"apiVersion": "v3.1.0"},
        {"kind": "Dataset"},
        {"quality": []},
        {"purpose": "Invented"},
        {"version": ""},
        {"extra": "untyped"},
    ):
        with pytest.raises(ValidationError):
            OdcsDocument.model_validate(raw | change)
    raw["schema"] = [
        {
            "name": "table",
            "logicalType": "object",
            "properties": [
                {
                    "name": "field",
                    "customProperties": [{"property": "canonicalNullable", "value": 0}],
                }
            ],
        }
    ]
    with pytest.raises(ValidationError):
        OdcsDocument.model_validate(raw)


def test_empty_catalog_and_empty_consumer_assertions_stay_empty() -> None:
    """No contract or consumer assertion is fabricated from empty collections."""
    empty = odcs.project_odcs(
        Catalog(schema_version="1.0", datasets=[]), configuration()
    )
    assert empty.readiness.state == "ready"
    assert empty.documents == []
    data = record().model_dump(exclude_none=True) | {
        "consumer": {"intended_uses": [], "limitations": []}
    }
    result = odcs.project_odcs(
        Catalog(schema_version="1.0", datasets=[DatasetRecord.model_validate(data)]),
        configuration(),
    )
    assert result.documents[0].description.usage is None
    assert result.documents[0].description.limitations is None


def test_incomplete_schema_closure_never_claims_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken resolver remains an operational resource failure without retrieval."""
    bundle = load_registry()
    altered = ResourceBundle(
        registry=bundle.registry,
        schemas=bundle.schemas
        | {
            odcs.ODCS_SCHEMA: DOCUMENT.validate_python(
                {
                    "$schema": "https://json-schema.org/draft/2019-09/schema",
                    "$ref": "https://example.org/unbundled",
                }
            )
        },
    )
    monkeypatch.setattr(odcs, "load_registry", lambda: altered)
    with pytest.raises(ResourceError):
        odcs.project_odcs(catalog(), configuration())


def test_failed_target_transform_never_returns_partial_contracts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid target shape cannot be promoted to an accepted document."""

    def malformed(*_args: object) -> None:
        OdcsDocument.model_validate({})

    monkeypatch.setattr(odcs, "document_for", malformed)
    result = odcs.project_odcs(catalog(), configuration())
    assert result.documents == []
    assert result.readiness.reasons == ["target_unrepresentable"]


def test_schema_failure_cannot_be_serialized(monkeypatch: pytest.MonkeyPatch) -> None:
    """Final schema refusal blocks output even for an existing typed document."""
    result = odcs.project_odcs(catalog(), configuration())
    monkeypatch.setattr(odcs, "valid_document", lambda _document: False)
    assert odcs.project_odcs(catalog(), configuration()).documents == []
    with pytest.raises(ResourceError):
        odcs.serialize_odcs(result.documents[0])
