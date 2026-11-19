# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Explicit bounded TOML, closed settings and declarative-rule acceptance."""

import json
import socket
from datetime import date, datetime
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from dscat.configuration import MAX_CONFIG_BYTES, check_toml_depth, parse_configuration
from dscat.models.catalog import EntityReference
from dscat.models.configuration import (
    AssessmentConfiguration,
    ExportConfiguration,
    IdentityConfiguration,
    LocalRule,
    PublicationConfiguration,
    canonical_paths,
)
from dscat.normalization import parse_date, parse_timestamp

if TYPE_CHECKING:
    from dscat.models.base import StrictModel

MINIMAL = b'schema_version = "1.0"\n'
SUBJECT = {"subject_kind": "canonical", "subject_id": "title", "target": "dcat-us-3"}


def test_minimal_config_without_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Absent optional settings remain absent regardless of external environment."""

    def deny(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Unexpected configuration network access")

    monkeypatch.setattr(socket, "getaddrinfo", deny)
    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setenv("DSCAT_CONFIG", "untrusted.toml")
    config = parse_configuration(MINIMAL)
    assert config.identity.dataset_namespace is None
    assert config.identity.parties == {}
    assert config.publication is None
    assert config.assessment.rules == []
    assert config.dcat_us_3.catalog_id is None
    assert config.odcs_3_2.contract_version is None


def test_full_explicit_config() -> None:
    """Valid explicit settings preserve independent versions and role association."""
    raw = b"""schema_version = "1.0"
[identity]
dataset_namespace = "https://example.org/datasets/"
contract_namespace = "https://example.org/contracts/"
contract_identity_rule = "namespace-plus-dataset-id"
[identity.parties."Metadata support"]
role_email = "metadata@example.org"
contact_association = true
[dcat_us_3]
catalog_id = "https://example.org/catalog"
[odcs_3_2]
contract_version = "2.7.0"
[assessment]
completeness = ["core_party.email", "capacity.normalized_bytes"]
[[assessment.rules]]
id = "has-title"
path = "title"
operator = "present"
[[assessment.rules]]
id = "expected-title"
path = "title"
operator = "equals"
operand = "Synthetic title"
severity = "info"
[[assessment.rules]]
id = "permitted-title"
path = "title"
operator = "one_of"
operands = ["Synthetic title", "Alternative title"]
[publication]
policy_version = "1.0"
authority_reference = "Synthetic policy"
[[publication.allowed_subjects]]
subject_kind = "canonical"
subject_id = "title"
target = "dcat-us-3"
"""
    config = parse_configuration(raw)
    assert config.schema_version != config.odcs_3_2.contract_version
    assert config.identity.parties["Metadata support"].contact_association is True
    assert config.publication is not None
    assert config.publication.allowed_subjects[0].subject_id == "title"
    assert (
        ExportConfiguration.model_validate_json(
            config.model_dump_json(exclude_none=True)
        )
        == config
    )


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"\xff",
        b'schema_version = "1.0"\n[invalid',
        b"schema_version = 1.0",
        b'schema_version = "2.0"',
        b'schema_version = "1.0"\nextra = true',
        MINIMAL + b"[identity]\nunknown = true",
        MINIMAL + b'[identity.parties."Support"]\nrole_email = "not-an-email"\n'
        b"contact_association = true",
        MINIMAL + b'[identity.parties."Support"]\nrole_email = "support@example.org"\n'
        b'contact_association = "Yes"',
        MINIMAL + b'[identity.parties."Support"]\nrole_email = "support@example.org"\n'
        b'contact_association = true\n[identity.parties." Support "]\n'
        b'role_email = "support@example.org"\ncontact_association = true',
        MINIMAL + b'[assessment]\ncompleteness = ["not.a.field"]',
        MINIMAL + b'[assessment]\ncompleteness = ["title", "title"]',
        MINIMAL + b'[assessment]\nrules = [{id="r", path="title", operator="exec", '
        b'operand="import os"}]',
    ],
)
def test_invalid_config(raw: bytes) -> None:
    """Malformed/unsupported/unknown/coerced configuration fails before intake."""
    with pytest.raises(ValueError, match=r"."):
        parse_configuration(raw)


@pytest.mark.parametrize(
    ("model", "data"),
    [
        (
            IdentityConfiguration,
            {
                "dataset_namespace": "https://example.org/same/",
                "contract_namespace": "https://example.org/same/",
            },
        ),
        (IdentityConfiguration, {"dataset_namespace": "https://u:p@example.org/"}),
        (IdentityConfiguration, {"dataset_namespace": "https://example.org/?query#"}),
        (IdentityConfiguration, {"dataset_namespace": "https://example.org/no-suffix"}),
        (IdentityConfiguration, {"contract_identity_rule": "implicit"}),
        (
            IdentityConfiguration,
            {
                "parties": {
                    "": {
                        "role_email": "support@example.org",
                        "contact_association": True,
                    }
                }
            },
        ),
        (LocalRule, {"id": "r", "path": "not.a.field", "operator": "present"}),
        (
            LocalRule,
            {"id": "r", "path": "title", "operator": "present", "operand": "value"},
        ),
        (
            LocalRule,
            {"id": "r", "path": "title", "operator": "present", "operands": ["value"]},
        ),
        (LocalRule, {"id": "r", "path": "title", "operator": "equals"}),
        (
            LocalRule,
            {
                "id": "r",
                "path": "title",
                "operator": "equals",
                "operand": "v",
                "operands": ["v"],
            },
        ),
        (LocalRule, {"id": "r", "path": "title", "operator": "one_of"}),
        (
            LocalRule,
            {
                "id": "r",
                "path": "title",
                "operator": "one_of",
                "operand": "v",
                "operands": ["v"],
            },
        ),
        (LocalRule, {"id": "r", "path": "title", "operator": "one_of", "operands": []}),
        (
            LocalRule,
            {"id": "r", "path": "title", "operator": "equals", "operand": None},
        ),
        (
            LocalRule,
            {
                "id": "r",
                "path": "title",
                "operator": "equals",
                "operand": {"expression": "synthetic"},
            },
        ),
        (
            AssessmentConfiguration,
            {
                "rules": [
                    {"id": "r", "path": "title", "operator": "present"},
                    {"id": "r", "path": "description", "operator": "present"},
                ]
            },
        ),
        (
            PublicationConfiguration,
            {
                "policy_version": "1.0",
                "authority_reference": "Synthetic",
                "allowed_subjects": [SUBJECT, SUBJECT],
            },
        ),
        (ExportConfiguration, {"schema_version": "1.0", "identity": None}),
    ],
)
def test_config_business_rules(
    model: type[StrictModel], data: dict[str, object]
) -> None:
    """Namespace, typed-operand, rule uniqueness and policy scope constraints hold."""
    with pytest.raises(ValidationError):
        model.model_validate(data)


def test_normalized_party_labels() -> None:
    """Normalized labels must preserve distinct explicit associations."""
    config = IdentityConfiguration.model_validate(
        {
            "parties": {
                " Support ": {
                    "role_email": "support@example.org",
                    "contact_association": False,
                }
            }
        }
    )
    assert list(config.parties) == ["Support"]
    assert config.parties["Support"].contact_association is False


def test_config_size_boundary_and_nested_tables() -> None:
    """Accept the byte limit; refuse excess bytes and overly deep tables."""
    raw = MINIMAL + b"#" + b"x" * (MAX_CONFIG_BYTES - len(MINIMAL) - 1)
    assert parse_configuration(raw).schema_version == "1.0"
    with pytest.raises(ValueError, match="byte limit"):
        parse_configuration(raw + b"x")
    deep = MINIMAL + b"[" + b".".join([b"nested"] * 65) + b"]\nkey=1"
    with pytest.raises(ValueError, match="depth"):
        parse_configuration(deep)


def test_lexical_depth_and_quoted_content() -> None:
    """Depth counts exclude comments, quoted content and escaped quotes."""
    check_toml_depth("[" * 64 + "]" * 64)
    with pytest.raises(ValueError, match="depth"):
        check_toml_depth("[" * 65 + "]" * 65)
    samples = [
        "# " + "[" * 100,
        '# comment\nschema_version="1.0"',
        'text="' + "[" * 100 + '"',
        "text='" + "[" * 100 + "'",
        'text="""' + "[" * 100 + '"""',
        "text='''" + "[" * 100 + "'''",
        'text="escaped \\" quote ["',
        'items=[{key="[value]"}]',
    ]
    for sample in samples:
        check_toml_depth(sample)
    assert parse_configuration(MINIMAL + b"# trailing comment").schema_version == "1.0"


def test_config_parser_recursion_is_a_fixed_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parser failures cannot escape as stack traces or arbitrary exception text."""

    def fail(_text: str) -> dict[str, object]:
        msg = "synthetic parser recursion"
        raise RecursionError(msg)

    monkeypatch.setattr("dscat.configuration.tomllib.loads", fail)
    with pytest.raises(ValueError, match="valid UTF-8 TOML"):
        parse_configuration(MINIMAL)


def test_paths_are_schema_defined() -> None:
    """Nested typed collections expose declared scalar paths, never expressions."""
    paths = canonical_paths()
    assert "core_party.email" in paths
    assert "capacity.normalized_bytes" in paths
    assert "fields.nullable" in paths
    assert "publication.approvals.approved_on" in paths
    assert "__class__" not in paths
    assert "records.disposal_date" not in paths


def test_date_and_reference_encodings() -> None:
    """Dates do not coerce datetimes; reference normalization cannot hide controls."""
    assert parse_date(date(2026, 1, 1)) == date(2026, 1, 1)
    naive = datetime(2026, 1, 1, tzinfo=None)  # noqa: DTZ001 -- rejection fixture.
    for value in (True, 0, naive, "2026-1-1", "2026-02-30"):
        with pytest.raises(ValueError, match=r"date|day"):
            parse_date(value)
    for value in (True, 0, "2026-01-01", "2026-01-01T00:00:00", naive):
        with pytest.raises(ValueError, match="timezone"):
            parse_timestamp(value)
    assert (
        EntityReference(reference_kind="external", id=" https://example.org/a ").id
        == "https://example.org/a"
    )


def test_finite_scalar_operands() -> None:
    """Only typed scalar facts are accepted for pure comparisons."""
    for value in (True, False, 0, 12, "Synthetic"):
        rule = LocalRule.model_validate(
            {"id": "r", "path": "title", "operator": "equals", "operand": value}
        )
        assert type(rule.operand) is type(value)
    for value in (float("nan"), float("inf"), ["value"]):
        with pytest.raises(ValidationError):
            LocalRule.model_validate_json(
                json.dumps(
                    {"id": "r", "path": "title", "operator": "equals", "operand": value}
                )
            )
