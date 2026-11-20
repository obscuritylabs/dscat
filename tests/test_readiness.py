# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Independent target-required facts and optional explicit party-role mappings."""

import json
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from dscat.cli import app
from dscat.export.odcs_3_2 import project_odcs, serialize_odcs
from dscat.export.readiness import assess_targets
from dscat.models.catalog import Catalog, DatasetRecord
from dscat.models.configuration import ExportConfiguration
from tests.test_dcat_us_3 import catalog, configuration, record
from tests.test_intake import CORE, workbook_bytes

if TYPE_CHECKING:
    from pathlib import Path


def with_roles(roles: list[dict[str, str]]) -> Catalog:
    """Attach only explicit synthetically supplied party-role facts."""
    values = record().model_dump(exclude_none=True) | {"roles": roles}
    return Catalog(
        schema_version="1.0", datasets=[DatasetRecord.model_validate(values)]
    )


def role(
    *,
    kind: str = "steward",
    label: str = "Synthetic stewardship",
    email: str | None = "steward@example.org",
    party: str = "steward",
) -> dict[str, str]:
    """Keep missing email different from an invented username."""
    values = {
        "party_id": party,
        "reference_kind": "local",
        "role": kind,
        "label": label,
    }
    if email is not None:
        values["email"] = email
    return values


def test_targets_have_independent_required_facts() -> None:
    """Valid intake can be ready for one profile while the other is blocked."""
    values = configuration().model_dump(exclude_none=True)
    values["identity"]["parties"] = {}
    values["dcat_us_3"] = {}
    targets = assess_targets(catalog(), ExportConfiguration.model_validate(values))
    assert [item.state for item in targets] == ["blocked", "ready"]
    values = configuration().model_dump(exclude_none=True)
    values["odcs_3_2"] = {}
    del values["identity"]["contract_identity_rule"]
    targets = assess_targets(catalog(), ExportConfiguration.model_validate(values))
    assert [item.state for item in targets] == ["ready", "blocked"]
    targets = assess_targets(None, configuration())
    assert [item.state for item in targets] == ["blocked", "blocked"]
    assert all(item.reasons == ["INVALID_METADATA"] for item in targets)


def test_explicit_roles_map_without_core_owner_inference() -> None:
    """Owner/steward/maintainer/contact are supplied role strings, never defaults."""
    roles = [
        role(kind=kind, email=f"{kind}@example.org", party=kind)
        for kind in ["accountable_owner", "steward", "maintainer", "contact"]
    ]
    result = project_odcs(with_roles(roles), configuration())
    assert result.readiness.state == "ready"
    team = result.documents[0].team
    assert team is not None
    assert {member.role for member in team.members if member.role is not None} == {
        "accountable_owner",
        "steward",
        "maintainer",
        "contact",
    }
    core = [
        member for member in team.members if member.username == "metadata@example.org"
    ]
    assert len(core) == 1
    assert core[0].role is None


def test_core_and_resolved_explicit_contact_do_not_duplicate_members() -> None:
    """One resolved target username carries only its explicit canonical role."""
    source = with_roles(
        [
            role(
                kind="contact",
                label="Metadata support",
                email="metadata@example.org",
                party="support",
            )
        ]
    )
    result = project_odcs(source, configuration())
    team = result.documents[0].team
    assert team is not None
    assert len(team.members) == 1
    assert team.members[0].role == "contact"


def test_multiple_explicit_roles_preserve_scalar_cardinality() -> None:
    """Do not join roles or select one for the single target role field."""
    source = with_roles([role(kind=kind) for kind in ["steward", "maintainer"]])
    before = source.model_dump_json(exclude_none=True)
    result = project_odcs(source, configuration())
    team = result.documents[0].team
    assert team is not None
    selected = [
        member for member in team.members if member.username == "steward@example.org"
    ]
    assert len(selected) == 1
    assert selected[0].role is None
    assert any(
        item.field == "roles.role" and item.reason == "unsupported_cardinality"
        for item in result.losses
    )
    assert source.model_dump_json(exclude_none=True) == before


def test_unresolved_role_reports_each_supplied_field_without_username() -> None:
    """Optional unresolved parties produce losses, not a new fabricated account."""
    source = with_roles([role(email=None)])
    result = project_odcs(source, configuration())
    team = result.documents[0].team
    assert team is not None
    assert [member.username for member in team.members] == ["metadata@example.org"]
    assert {
        item.field for item in result.losses if item.reason == "unresolved_contact"
    } == {"roles.label", "roles.party_id", "roles.reference_kind", "roles.role"}


@pytest.mark.parametrize(
    "conflict", ["email", "contact_association", "label", "core_email"]
)
def test_conflicting_resolved_member_facts_block_target(conflict: str) -> None:
    """One username cannot silently select a conflicting name or supplied email."""
    configured = configuration().model_dump(exclude_none=True)
    source = with_roles([role()])
    if conflict in {"email", "contact_association"}:
        configured["identity"]["parties"]["Synthetic stewardship"] = {
            "role_email": "different@example.org"
            if conflict == "email"
            else "steward@example.org",
            "contact_association": False,
        }
        if conflict == "contact_association":
            source = with_roles([role(kind="contact")])
    elif conflict == "label":
        source = with_roles([role(email="metadata@example.org")])
    else:
        values = record().model_dump(exclude_none=True)
        values["core_party"]["email"] = "other@example.org"
        source = Catalog(
            schema_version="1.0", datasets=[DatasetRecord.model_validate(values)]
        )
    result = project_odcs(source, ExportConfiguration.model_validate(configured))
    assert result.documents == []
    assert result.readiness.reasons == ["target_fact_conflict"]


def test_noncontact_role_uses_explicit_email_mapping_without_contact_claim() -> None:
    """A steward's username does not establish a contact association or owner."""
    configured = configuration().model_dump(exclude_none=True)
    configured["identity"]["parties"]["Synthetic stewardship"] = {
        "role_email": "steward@example.org",
        "contact_association": False,
    }
    result = project_odcs(
        with_roles([role(email=None)]), ExportConfiguration.model_validate(configured)
    )
    team = result.documents[0].team
    assert team is not None
    assert any(member.role == "steward" for member in team.members)


def test_guarded_command_assesses_both_targets_without_publication(
    tmp_path: Path,
) -> None:
    """The guarded command reports readiness without printing private metadata."""
    source = tmp_path / "input.xlsx"
    source.write_bytes(workbook_bytes([CORE]))
    config = tmp_path / "settings.toml"
    config.write_text(
        'schema_version="1.0"\n[identity]\n'
        'dataset_namespace="https://example.org/datasets/"\n'
        'contract_namespace="https://example.org/contracts/"\n'
        'contract_identity_rule="namespace-plus-dataset-id"\n'
        '[identity.parties."Metadata support"]\nrole_email="metadata@example.org"\n'
        'contact_association=true\n[dcat_us_3]\ncatalog_id="https://example.org/catalog"\n'
        '[odcs_3_2]\ncontract_version="2.7.0"\n'
    )
    result = CliRunner().invoke(
        app, ["validate", str(source), "--config", str(config), "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    output = json.loads(result.output)
    assert [item["state"] for item in output["assessment"]["targets"]] == [
        "ready",
        "ready",
    ]
    assert CORE["title"] not in result.output
    assert "metadata@example.org" not in result.output
    assert "receipt" not in output


def test_dataset_version_does_not_supply_contract_version() -> None:
    """Keep dataset version metadata separate from required contract version."""
    values = record().model_dump(exclude_none=True) | {"dataset_version": "dataset-42"}
    configured = configuration().model_dump(exclude_none=True)
    configured["odcs_3_2"] = {}
    result = project_odcs(
        Catalog(schema_version="1.0", datasets=[DatasetRecord.model_validate(values)]),
        ExportConfiguration.model_validate(configured),
    )
    assert result.readiness.reasons == ["target_contract_version_missing"]
    assert result.documents == []


def test_supplied_commitments_are_omitted_without_value_leakage() -> None:
    """Preserve assertions without inventing purpose or service guarantees."""
    values = record().model_dump(exclude_none=True) | {
        "commitments": [
            {
                "id": "test",
                "kind": "service",
                "subject": "synthetic-sensitive-subject",
                "description": "synthetic-sensitive-assertion",
            }
        ]
    }
    source = Catalog(
        schema_version="1.0", datasets=[DatasetRecord.model_validate(values)]
    )
    result = project_odcs(source, configuration())
    assert any(item.field.startswith("commitments.") for item in result.losses)
    assert "synthetic-sensitive" not in serialize_odcs(result.documents[0]).decode()
    assert "synthetic-sensitive" not in "".join(
        item.model_dump_json() for item in result.losses
    )
    assert "synthetic-sensitive" in source.model_dump_json()
