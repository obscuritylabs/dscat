# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Exact public scopes, independent controls, fresh DTOs and all-target withholding."""

import json
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from dscat import public_projection as public
from dscat import publication_bindings as bindings
from dscat.intake.limits import IntakeError, fail
from dscat.models.catalog import Catalog, DatasetRecord
from dscat.models.configuration import ExportConfiguration
from tests.test_dcat_us_3 import catalog, configuration
from tests.test_publication_bindings import approved_fixture

if TYPE_CHECKING:
    from dscat.models.base import Target


def public_bytes(result: public.PublicProjection) -> bytes:
    """Inspect only actual target document bytes, never serialize private reports."""
    return (
        public.public_dcat_bytes(result.dcat) if result.dcat is not None else b""
    ) + b"".join(public.public_odcs_bytes(document) for document in result.odcs)


@pytest.mark.parametrize("detailed", [False, True])
def test_explicit_approved_minimum_and_detail_use_fresh_minimal_dtos(
    *, detailed: bool
) -> None:
    """Expose only initially allowed approved facts through new target models."""
    record, configured = approved_fixture(detailed=detailed)
    source = Catalog(schema_version="1.0", datasets=[record])
    before = source.model_dump_json(exclude_none=True)
    result = public.project_public(source, configured, ["dcat-us-3", "odcs-3.2"])
    assert [item.state for item in result.readiness] == ["ready", "ready"]
    assert result.dcat is not None
    assert len(result.odcs) == 1
    dcat = json.loads(public.public_dcat_bytes(result.dcat))
    odcs = json.loads(public.public_odcs_bytes(result.odcs[0]))
    assert set(dcat["dataset"][0]) == {
        "@id",
        "@type",
        "identifier",
        "title",
        "description",
        "contactPoint",
    }
    assert set(odcs) == {
        "apiVersion",
        "kind",
        "id",
        "version",
        "name",
        "description",
        "customProperties",
        "team",
    }
    assert odcs["team"] == {
        "members": [{"name": "Metadata support", "username": "metadata@example.org"}]
    }
    assert "role" not in odcs["team"]["members"][0]
    assert source.model_dump_json(exclude_none=True) == before
    assert result.losses


@pytest.mark.parametrize(
    "mutation",
    [
        "catalog",
        "dataset_namespace",
        "contract_namespace",
        "email",
        "association",
        "rule",
        "mapping",
        "policy",
        "source_selection",
    ],
)
def test_changed_effective_values_or_sources_withhold_entire_bundle(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    """Source approval never grants a changed source, derivation or mapping."""
    source, configured = approved_fixture()
    record_values = source.model_dump(exclude_none=True)
    values = configured.model_dump(exclude_none=True)
    if mutation == "catalog":
        values["dcat_us_3"]["catalog_id"] = "https://example.org/changed-catalog"
    elif mutation == "dataset_namespace":
        values["identity"]["dataset_namespace"] = (
            "https://example.org/changed-datasets/"
        )
    elif mutation == "contract_namespace":
        values["identity"]["contract_namespace"] = (
            "https://example.org/changed-contracts/"
        )
    elif mutation == "email":
        values["identity"]["parties"]["Metadata support"]["role_email"] = (
            "changed@example.org"
        )
    elif mutation == "association":
        values["identity"]["parties"]["Metadata support"]["contact_association"] = False
    elif mutation == "rule":
        del values["identity"]["contract_identity_rule"]
    elif mutation == "policy":
        values["publication"]["policy_version"] = "new-policy"
    elif mutation == "source_selection":
        record_values["core_party"]["email"] = "metadata@example.org"
    else:
        monkeypatch.setitem(bindings.MAPPING_REVISIONS, "dcat-us-3", "changed-mapping")
    result = public.project_public(
        Catalog(
            schema_version="1.0", datasets=[DatasetRecord.model_validate(record_values)]
        ),
        ExportConfiguration.model_validate(values),
        ["dcat-us-3", "odcs-3.2"],
    )
    assert any(item.state == "blocked" for item in result.readiness)
    assert result.dcat is None
    assert result.odcs == []
    assert public_bytes(result) == b""


@pytest.mark.parametrize(
    "subject_kind", ["canonical", "configuration", "derived_target"]
)
def test_missing_exact_subject_approval_cannot_be_replaced_by_policy(
    subject_kind: str,
) -> None:
    """A policy's allowed list is not an approval or an all-fields grant."""
    source, configured = approved_fixture()
    values = source.model_dump(exclude_none=True)
    approvals = values["publication"]["approvals"]
    removed = next(
        item
        for item in approvals
        if item["target"] == "dcat-us-3" and item["subject_kind"] == subject_kind
    )
    values["publication"]["approvals"] = [item for item in approvals if item != removed]
    result = public.project_public(
        Catalog(schema_version="1.0", datasets=[DatasetRecord.model_validate(values)]),
        configured,
        ["dcat-us-3", "odcs-3.2"],
    )
    assert result.dcat is None
    assert result.odcs == []
    assert result.readiness[0].reasons == ["PUBLIC_PROJECTION_DENIED"]


def test_optional_odcs_contact_can_stay_unselected() -> None:
    """An unapproved optional member is omitted without inventing an identity."""
    source, configured = approved_fixture()
    values = source.model_dump(exclude_none=True)
    contact_scopes = {
        "core_party.label",
        "core_party.email",
        "identity.parties.role_email",
        "contact_username",
    }
    values["publication"]["approvals"] = [
        item
        for item in values["publication"]["approvals"]
        if not (item["target"] == "odcs-3.2" and item["subject_id"] in contact_scopes)
    ]
    result = public.project_public(
        Catalog(schema_version="1.0", datasets=[DatasetRecord.model_validate(values)]),
        configured,
        ["odcs-3.2"],
    )
    assert result.readiness[0].state == "ready"
    assert result.odcs[0].team is None
    assert any(item.field == "core_party.label" for item in result.losses)


def test_unreviewed_or_unready_source_cannot_emit_public_documents() -> None:
    """Valid intake and normal standards readiness do not grant public disclosure."""
    result = public.project_public(
        catalog(), configuration(), ["dcat-us-3", "odcs-3.2"]
    )
    assert result.dcat is None
    assert result.odcs == []
    assert all(item.state == "blocked" for item in result.readiness)
    record, configured = approved_fixture()
    values = configured.model_dump(exclude_none=True)
    del values["dcat_us_3"]["catalog_id"]
    result = public.project_public(
        Catalog(schema_version="1.0", datasets=[record]),
        ExportConfiguration.model_validate(values),
        ["dcat-us-3", "odcs-3.2"],
    )
    assert result.dcat is None
    assert result.odcs == []


def test_one_unapproved_record_withholds_every_record_and_target() -> None:
    """Previously accepted records do not become a partial public bundle."""
    record, configured = approved_fixture()
    values = record.model_dump(exclude_none=True) | {"id": "unapproved"}
    source = Catalog(
        schema_version="1.0", datasets=[record, DatasetRecord.model_validate(values)]
    )
    result = public.project_public(source, configured, ["dcat-us-3", "odcs-3.2"])
    assert result.dcat is None
    assert result.odcs == []


def test_private_optional_text_and_urls_do_not_reach_public_bytes() -> None:
    """Preserve private canonical details while recursively excluding their values."""
    record, configured = approved_fixture(detailed=True)
    values = record.model_dump(exclude_none=True)
    values["services"][0]["title"] = "synthetic-sensitive-service"
    values["services"][0]["endpoint_url"] = (
        "https://example.org/synthetic-sensitive-endpoint"
    )
    values["fields"][0]["description"] = "synthetic-sensitive-field"
    values["consumer"]["provenance"] = ["synthetic-sensitive-provenance"]
    values["records"]["authority"] = "synthetic-sensitive-records-authority"
    values["disclosure_determination"]["rationale"] = (
        "synthetic-sensitive-disclosure-rationale"
    )
    values["metadata_review"]["authority"] = "synthetic-sensitive-review-authority"
    source = Catalog(
        schema_version="1.0", datasets=[DatasetRecord.model_validate(values)]
    )
    result = public.project_public(source, configured, ["dcat-us-3", "odcs-3.2"])
    assert all(item.state == "ready" for item in result.readiness)
    assert "synthetic-sensitive" not in public_bytes(result).decode()
    assert "synthetic-sensitive" not in "".join(
        item.model_dump_json() for item in result.losses
    )
    assert "synthetic-sensitive" in source.model_dump_json()


def test_unknown_new_children_refuse_without_exposure() -> None:
    """Unsupported nested children cannot enter canonical or public model boundaries."""
    source, _configured = approved_fixture()
    values = source.model_dump(exclude_none=True)
    values["core_party"]["future_private_child"] = "synthetic-sensitive-unknown"
    with pytest.raises(ValidationError):
        DatasetRecord.model_validate(values)


def test_operational_failure_is_not_reclassified_as_policy_denial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A resource or I/O failure retains its operation failure category."""
    record, configured = approved_fixture()

    def failed(*_args: object, **_kwargs: object) -> None:
        raise fail(code="INPUT_LIMIT", limit="memory")

    monkeypatch.setattr(public, "approved_subjects", failed)
    with pytest.raises(IntakeError) as caught:
        public.project_public(
            Catalog(schema_version="1.0", datasets=[record]), configured, ["dcat-us-3"]
        )
    assert caught.value.diagnostic.limit == "memory"


def test_public_result_cannot_hold_partial_data_for_blocked_targets() -> None:
    """The output DTO itself enforces the all-or-nothing boundary."""
    record, configured = approved_fixture()
    result = public.project_public(
        Catalog(schema_version="1.0", datasets=[record]), configured, ["dcat-us-3"]
    )
    values = result.model_dump(mode="json", by_alias=True, exclude_none=True)
    values["readiness"][0]["state"] = "blocked"
    with pytest.raises(ValidationError):
        public.PublicProjection.model_validate(values)


@pytest.mark.parametrize("targets", [[], ["dcat-us-3", "dcat-us-3"]])
def test_public_target_selection_is_explicit_and_unique(targets: list[Target]) -> None:
    """A missing or repeated requested target is not an implicit public grant."""
    record, configured = approved_fixture()
    with pytest.raises(IntakeError) as caught:
        public.project_public(
            Catalog(schema_version="1.0", datasets=[record]), configured, targets
        )
    assert caught.value.diagnostic.code == "INVALID_INVOCATION"


def test_non_scalar_source_is_not_implicitly_rendered_as_public_text() -> None:
    """Configured party bindings cannot be stringified into an emitted scalar."""
    record, configured = approved_fixture()
    subjects = public.resolve_subjects(record, configured, "dcat-us-3")
    with pytest.raises(IntakeError) as caught:
        public.selected_value(subjects, "configuration", "identity.parties.role_email")
    assert caught.value.diagnostic.code == "PUBLIC_PROJECTION_DENIED"


def test_empty_dcat_cannot_publish_catalog_identity_without_record_scopes() -> None:
    """Require a containing record to approve the factual catalog IRI."""
    _record, configured = approved_fixture()
    result = public.project_public(
        Catalog(schema_version="1.0", datasets=[]), configured, ["dcat-us-3"]
    )
    assert result.dcat is None
    assert result.readiness[0].reasons == ["PUBLIC_PROJECTION_DENIED"]


@pytest.mark.parametrize(
    "mutation",
    [
        "dataset_version",
        "contact_address",
        "odcs_field",
        "odcs_role",
        "odcs_purpose",
        "odcs_identifier_extension",
    ],
)
def test_closed_public_models_refuse_private_children_at_each_depth(
    mutation: str,
) -> None:
    """No optional private child becomes public through a broader target model."""
    record, configured = approved_fixture()
    result = public.project_public(
        Catalog(schema_version="1.0", datasets=[record]),
        configured,
        ["dcat-us-3", "odcs-3.2"],
    )
    raw = result.model_dump(mode="json", by_alias=True, exclude_none=True)
    if mutation == "dataset_version":
        raw["dcat"]["dataset"][0]["version"] = "synthetic-sensitive-version"
    elif mutation == "contact_address":
        raw["dcat"]["dataset"][0]["contactPoint"]["address"] = (
            "synthetic-sensitive-address"
        )
    elif mutation == "odcs_field":
        raw["odcs"][0]["schema"] = [{"name": "synthetic-sensitive-field"}]
    elif mutation == "odcs_role":
        raw["odcs"][0]["team"]["members"][0]["role"] = "synthetic-sensitive-role"
    elif mutation == "odcs_purpose":
        raw["odcs"][0]["description"]["purpose"] = "synthetic-sensitive-purpose"
    else:
        raw["odcs"][0]["customProperties"].append(
            {"property": "datasetVersion", "value": "synthetic-sensitive-version"}
        )
    with pytest.raises(ValidationError):
        public.PublicProjection.model_validate(raw)


@pytest.mark.parametrize("collision", ["catalog", "dataset_id", "identifier"])
def test_public_dcat_read_boundary_rejects_conflated_nodes(collision: str) -> None:
    """Stored public artifacts cannot introduce duplicate or self-member identities."""
    record, configured = approved_fixture()
    result = public.project_public(
        Catalog(schema_version="1.0", datasets=[record]), configured, ["dcat-us-3"]
    )
    assert result.dcat is not None
    raw = result.dcat.model_dump(mode="json", by_alias=True, exclude_none=True)
    if collision == "catalog":
        raw["@id"] = raw["dataset"][0]["@id"]
    else:
        second = dict(raw["dataset"][0])
        second["identifier" if collision == "dataset_id" else "@id"] = (
            "other"
            if collision == "dataset_id"
            else "https://example.org/datasets/other"
        )
        raw["dataset"].append(second)
    with pytest.raises(ValidationError):
        public.PublicDcatDocument.model_validate(raw)


def string_locations(value: object) -> list[tuple[str | int, ...]]:
    """Enumerate nested scalar locations without relying on an exclusion list."""
    if isinstance(value, dict):
        return [
            (key, *path)
            for key, child in value.items()
            for path in string_locations(child)
        ]
    if isinstance(value, list):
        return [
            (index, *path)
            for index, child in enumerate(value)
            for path in string_locations(child)
        ]
    return [()] if isinstance(value, str) else []


def test_recursive_private_string_mutations_never_escape_public_documents() -> None:
    """Probe every mutable text leaf, including nested authorities and facts."""
    record, configured = approved_fixture(detailed=True)
    baseline = record.model_dump(mode="json", exclude_none=True)
    locations = string_locations(baseline)
    tested = 0
    private_ready = 0
    for location in locations:
        for candidate in (
            "synthetic-sensitive-recursive",
            "https://example.org/synthetic-sensitive-recursive",
            "urn:synthetic-sensitive:recursive",
        ):
            changed = json.loads(json.dumps(baseline))
            parent = changed
            for component in location[:-1]:
                parent = parent[component]
            parent[location[-1]] = candidate
            try:
                updated = DatasetRecord.model_validate(changed)
                source = Catalog(schema_version="1.0", datasets=[updated])
            except ValidationError:
                continue
            tested += 1
            result = public.project_public(
                source,
                configured,
                ["dcat-us-3", "odcs-3.2"],
            )
            assert b"synthetic-sensitive-recursive" not in public_bytes(result)
            private_ready += all(item.state == "ready" for item in result.readiness)
            break
    minimum_mutations, minimum_private_ready = 50, 30
    assert tested > minimum_mutations
    assert private_ready > minimum_private_ready
