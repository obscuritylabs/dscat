# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Required facts, exact mappings, isolated readiness and loss-safe projections."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from dscat.cli import app
from dscat.export import dcat_us_3 as dcat
from dscat.export.models import DcatDocument
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
from tests.test_intake import CORE, workbook_bytes

FIXTURES = Path(__file__).parent / "fixtures/contracts"
RESEARCH = Path(__file__).parents[1] / "docs/evidence/architecture"


def configuration() -> ExportConfiguration:
    """Supply every required target identity/contact fact explicitly."""
    return ExportConfiguration.model_validate_json(
        (RESEARCH / "minimum-configuration.json").read_bytes()
    )


def record(*, detailed: bool = False) -> DatasetRecord:
    """Use canonical synthetic fixtures already checked by the intake contract."""
    return DatasetRecord.model_validate_json(
        (FIXTURES / ("detailed.json" if detailed else "minimum.json")).read_bytes()
    )


def catalog(*, detailed: bool = False) -> Catalog:
    """Create one wholly valid canonical catalog."""
    return Catalog(schema_version="1.0", datasets=[record(detailed=detailed)])


@pytest.mark.parametrize("detailed", [False, True])
def test_minimum_and_detailed_schema_roundtrip_repeatability(
    tmp_path: Path, *, detailed: bool
) -> None:
    """Target output survives canonical reload with fixed aliases, dates and bytes."""
    source = catalog(detailed=detailed)
    result = dcat.project_dcat(source, configuration())
    assert result.readiness.state == "ready"
    assert result.document is not None
    encoded = dcat.serialize_dcat(result.document)
    payload = json.loads(encoded)
    assert payload["dataset"][0]["identifier"] == source.datasets[0].id
    assert payload["dataset"][0]["contactPoint"] == {
        "@type": "Kind",
        "fn": "Metadata support",
        "hasEmail": "mailto:metadata@example.org",
    }
    assert encoded.endswith(b"\n")
    assert not encoded.endswith(b"\n\n")
    assert b'"@id"' in encoded
    assert b'"datasets"' not in encoded
    publish(tmp_path / "bundle", source)
    loaded = load_snapshot(tmp_path / "bundle")
    repeated = dcat.project_dcat(loaded.catalog, configuration())
    assert repeated.document is not None
    assert dcat.serialize_dcat(repeated.document) == encoded
    assert repeated.losses == result.losses
    if detailed:
        dataset = payload["dataset"][0]
        assert dataset["modified"] == "2026-01-03"
        assert dataset["version"] == "2026-Q1"
        assert dataset["distribution"] == [
            {
                "@id": "https://example.org/datasets/asset-001/distributions/download",
                "@type": "Distribution",
                "title": "Synthetic download",
                "accessURL": "https://example.org/access/",
                "downloadURL": "https://example.org/download/",
            }
        ]
        assert "quality" not in dataset
        assert "slaProperties" not in dataset
        paths = {loss.field for loss in result.losses}
        assert {
            "distributions.media_type",
            "distributions.format",
            "commitments.description",
            "consumer.intended_uses",
            "roles.role",
            "capacity.state",
            "records.hold_state",
        } <= paths
    else:
        assert set(payload["dataset"][0]) == {
            "@id",
            "@type",
            "identifier",
            "title",
            "description",
            "contactPoint",
        }


@pytest.mark.parametrize(
    "missing", ["namespace", "catalog", "association", "email", "invalid_intake"]
)
def test_readiness_blocks_missing_facts_without_fabrication(missing: str) -> None:
    """Minimal intake remains valid while unsupported target facts stay blocked."""
    values = configuration().model_dump(exclude_none=True)
    if missing == "namespace":
        del values["identity"]["dataset_namespace"]
    elif missing == "catalog":
        del values["dcat_us_3"]["catalog_id"]
    elif missing == "association":
        values["identity"]["parties"]["Metadata support"]["contact_association"] = False
    elif missing == "email":
        values["identity"]["parties"] = {}
    configured = ExportConfiguration.model_validate(values)
    result = dcat.project_dcat(
        None if missing == "invalid_intake" else catalog(), configured
    )
    assert result.readiness.state == "blocked"
    assert result.document is None
    expected = (
        "INVALID_METADATA"
        if missing == "invalid_intake"
        else "target_unrepresentable"
        if missing in {"namespace", "catalog"}
        else "target_contact_missing"
    )
    assert result.readiness.reasons == [expected]


def test_direct_contact_and_explicit_config_conflict() -> None:
    """A contact email is supplied; owner-only email does not establish association."""
    data = record().model_dump(exclude_none=True)
    data["core_party"] = {
        "label": "Metadata support",
        "role": "contact",
        "email": "direct@example.org",
    }
    direct = Catalog(
        schema_version="1.0", datasets=[DatasetRecord.model_validate(data)]
    )
    values = configuration().model_dump(exclude_none=True)
    values["identity"]["parties"] = {}
    configured = ExportConfiguration.model_validate(values)
    result = dcat.project_dcat(direct, configured)
    assert result.document is not None
    assert result.document.datasets[0].contact.email == "mailto:direct@example.org"
    assert dcat.assess_dcat(direct, configuration()).reasons == ["target_fact_conflict"]
    data["core_party"]["role"] = "owner"
    owner = Catalog(schema_version="1.0", datasets=[DatasetRecord.model_validate(data)])
    assert dcat.assess_dcat(owner, configured).reasons == ["target_contact_missing"]


def test_ids_are_separately_escaped_and_sorted() -> None:
    """Reserved identifier characters cannot create a new namespace path segment."""
    base = record().model_dump(exclude_none=True)
    records = [
        DatasetRecord.model_validate(base | {"id": identifier})
        for identifier in ["z:part", "a"]
    ]
    result = dcat.project_dcat(
        Catalog(schema_version="1.0", datasets=records), configuration()
    )
    assert result.document is not None
    assert [item.identifier for item in result.document.datasets] == ["a", "z:part"]
    assert result.document.datasets[1].id == "https://example.org/datasets/z%3Apart"


@pytest.mark.parametrize(
    "mutation",
    [
        "remote",
        "import",
        "scoped",
        "unknown_term",
        "nested",
        "unknown_field",
        "bad_email",
        "empty_title",
    ],
)
def test_target_boundary_refuses_remote_context_and_invalid_required_facts(
    mutation: str,
) -> None:
    """Rejected context data is never handed to an RDF interpreter."""
    projection = dcat.project_dcat(catalog(), configuration())
    assert projection.document is not None
    raw = projection.document.model_dump(mode="json", by_alias=True, exclude_none=True)
    if mutation == "remote":
        raw["@context"] = "https://example.org/context"
    elif mutation == "import":
        raw["@context"]["@import"] = "https://example.org/context"
    elif mutation == "scoped":
        raw["@context"]["title"] = {
            "@id": "dcterms:title",
            "@context": "https://example.org/context",
        }
    elif mutation == "unknown_term":
        raw["@context"]["unmapped"] = "https://example.org/term"
    elif mutation == "nested":
        raw["dataset"][0]["@context"] = "https://example.org/context"
    elif mutation == "unknown_field":
        raw["dataset"][0]["publisher"] = "Invented"
    elif mutation == "bad_email":
        raw["dataset"][0]["contactPoint"]["hasEmail"] = "invalid@example.org"
    else:
        raw["dataset"][0]["title"] = ""
    with pytest.raises(ValidationError):
        DcatDocument.model_validate(raw)


def test_empty_catalog_and_distribution_optional_absence() -> None:
    """Empty inventory remains explicit and optional fields never gain defaults."""
    empty = dcat.project_dcat(
        Catalog(schema_version="1.0", datasets=[]), configuration()
    )
    assert empty.document is not None
    assert empty.document.datasets == []
    data = record().model_dump(exclude_none=True) | {
        "distributions": [{"id": "access"}]
    }
    result = dcat.project_dcat(
        Catalog(schema_version="1.0", datasets=[DatasetRecord.model_validate(data)]),
        configuration(),
    )
    assert result.document is not None
    assert result.document.datasets[0].distributions is not None
    assert result.document.datasets[0].distributions[0].title is None


def test_failed_transform_never_returns_partial_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A shape/semantic target failure blocks the whole projection."""

    def malformed(*_args: object) -> None:
        DcatDocument.model_validate({})

    monkeypatch.setattr(dcat, "dataset_for", malformed)
    result = dcat.project_dcat(catalog(), configuration())
    assert result.document is None
    assert result.readiness.reasons == ["target_unrepresentable"]


def test_schema_failure_and_mutation_are_not_serialized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid accepted-model mutations cannot bypass the final schema fence."""
    result = dcat.project_dcat(catalog(), configuration())
    assert result.document is not None
    monkeypatch.setattr(dcat, "valid_document", lambda _document: False)
    assert dcat.project_dcat(catalog(), configuration()).document is None
    with pytest.raises(ResourceError):
        dcat.serialize_dcat(result.document)


def test_transform_identity_collision_is_not_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A future faulty transform cannot silently assign two records one node."""
    template = dcat.dataset_for(
        record(), "https://example.org/datasets/", "metadata@example.org"
    )
    monkeypatch.setattr(dcat, "dataset_for", lambda *_args: template)
    second = DatasetRecord.model_validate(
        record().model_dump(exclude_none=True) | {"id": "second"}
    )
    result = dcat.project_dcat(
        Catalog(schema_version="1.0", datasets=[record(), second]), configuration()
    )
    assert result.document is None
    assert result.readiness.reasons == ["target_fact_conflict"]


def test_unknown_schema_reference_is_a_safe_resource_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unexpectedly incomplete resolver cannot produce a ready projection."""
    bundle = load_registry()
    schema = DOCUMENT.validate_python({"$ref": "https://example.org/not-bundled"})
    altered = ResourceBundle(
        registry=bundle.registry, schemas=bundle.schemas | {dcat.CATALOG_SCHEMA: schema}
    )
    monkeypatch.setattr(dcat, "load_registry", lambda: altered)
    with pytest.raises(ResourceError):
        dcat.project_dcat(catalog(), configuration())


def test_actual_cli_readiness_uses_explicit_configuration(tmp_path: Path) -> None:
    """The public validation result passes target facts through guarded processing."""
    source = tmp_path / "input.xlsx"
    source.write_bytes(workbook_bytes([CORE]))
    config = tmp_path / "settings.toml"
    config.write_text(
        'schema_version="1.0"\n[identity]\n'
        'dataset_namespace="https://example.org/datasets/"\n'
        '[identity.parties."Metadata support"]\n'
        'role_email="metadata@example.org"\ncontact_association=true\n'
        '[dcat_us_3]\ncatalog_id="https://example.org/catalog"\n'
    )
    runner = CliRunner()
    for args, expected in [([], "blocked"), (["--config", str(config)], "ready")]:
        result = runner.invoke(
            app, ["validate", str(source), "--format", "json", *args]
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["assessment"]["validity"] == "valid"
        assert payload["assessment"]["targets"][0]["state"] == expected
        assert payload["assessment"]["targets"][1]["state"] == "blocked"
        assert "metadata@example.org" not in result.output
        assert CORE["title"] not in result.output


def test_explicit_association_disagreement_is_a_conflict() -> None:
    """A supplied contact role cannot override an explicit contrary mapping."""
    values = record().model_dump(exclude_none=True)
    values["core_party"] = {
        "label": "Metadata support",
        "role": "contact",
        "email": "metadata@example.org",
    }
    configured = configuration().model_dump(exclude_none=True)
    configured["identity"]["parties"]["Metadata support"]["contact_association"] = False
    source = Catalog(
        schema_version="1.0", datasets=[DatasetRecord.model_validate(values)]
    )
    result = dcat.project_dcat(source, ExportConfiguration.model_validate(configured))
    assert result.document is None
    assert result.readiness.reasons == ["target_fact_conflict"]


def test_contact_role_is_mapped_without_ownership_inference() -> None:
    """Explicit contact roles map without interpreting unrelated roles."""
    values = record().model_dump(exclude_none=True)
    values["core_party"] = {"label": "Metadata support", "role": "contact"}
    result = dcat.project_dcat(
        Catalog(schema_version="1.0", datasets=[DatasetRecord.model_validate(values)]),
        configuration(),
    )
    assert result.document is not None
    assert not any(item.field == "core_party.role" for item in result.losses)


def test_pinned_contact_pattern_can_block_otherwise_valid_email() -> None:
    """Canonical email validity does not imply target-pattern representability."""
    values = record().model_dump(exclude_none=True)
    values["core_party"] = {
        "label": "Metadata support",
        "role": "contact",
        "email": "a/b@example.org",
    }
    configured = configuration().model_dump(exclude_none=True)
    configured["identity"]["parties"] = {}
    source = Catalog(
        schema_version="1.0", datasets=[DatasetRecord.model_validate(values)]
    )
    result = dcat.project_dcat(source, ExportConfiguration.model_validate(configured))
    assert result.document is None
    assert result.readiness.reasons == ["target_unrepresentable"]


@pytest.mark.parametrize("collision", ["dataset", "distribution"])
def test_catalog_cannot_conflate_generated_named_nodes(collision: str) -> None:
    """A configured catalog must not become its own dataset or distribution."""
    values = configuration().model_dump(exclude_none=True)
    identity = "https://example.org/datasets/asset-001"
    values["dcat_us_3"]["catalog_id"] = (
        identity if collision == "dataset" else identity + "/distributions/download"
    )
    result = dcat.project_dcat(
        catalog(detailed=True), ExportConfiguration.model_validate(values)
    )
    assert result.document is None
    assert result.readiness.reasons == ["target_fact_conflict"]
