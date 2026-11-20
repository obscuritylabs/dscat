# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Exact normalized value identities for supplied publication approval scopes."""

import hashlib
import json
import unicodedata
from typing import Literal, Self

from pydantic import Field, JsonValue, model_validator

from dscat.export.models import CONTEXT
from dscat.models.base import Sha256, StrictModel, Target, Text
from dscat.models.catalog import ApprovalSubject
from dscat.resources.registry import MANIFEST_SHA256

MAPPING_REVISIONS: dict[Target, str] = {
    "dcat-us-3": "dcat-us-3.0:1",
    "odcs-3.2": "odcs-3.2.0:1",
}
CANONICAL_INPUTS = frozenset(
    {
        "id",
        "title",
        "description",
        "core_party.label",
        "core_party.email",
        "core_party.role",
        "contract_id",
        "contract_version",
    }
)
CONFIGURATION_INPUTS = frozenset(
    {
        "dcat_us_3.catalog_id",
        "identity.dataset_namespace",
        "identity.contract_namespace",
        "identity.contract_identity_rule",
        "identity.parties.role_email",
        "identity.parties.contact_association",
        "odcs_3_2.contract_version",
    }
)


def normalized_value(value: JsonValue) -> JsonValue:
    """Normalize text recursively without merging keys or changing scalar types."""
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [normalized_value(child) for child in value]
    if isinstance(value, dict):
        result: dict[str, JsonValue] = {}
        for key, child in value.items():
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in result:
                msg = "Duplicate normalized approval binding key."
                raise ValueError(msg)
            result[normalized_key] = normalized_value(child)
        return result
    return value


def value_hash(value: JsonValue) -> str:
    """Hash compact sorted UTF-8 normalized JSON without a trailing newline."""
    raw = json.dumps(
        normalized_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def mapping_version(target: Target) -> str:
    """Bind selected resources and inline context independently of source paths."""
    constants: JsonValue = (
        CONTEXT
        if target == "dcat-us-3"
        else {"apiVersion": "v3.2.0", "kind": "DataContract"}
    )
    return f"{MAPPING_REVISIONS[target]}:{MANIFEST_SHA256}:{value_hash(constants)}"


class BindingInput(StrictModel):
    """A closed dependency identifier and exact value identity, never a grant."""

    subject_kind: Literal["canonical", "configuration"]
    subject_id: str
    value_sha256: Sha256

    @model_validator(mode="after")
    def known_identifier(self) -> Self:
        """Bind each finite dependency name to its canonical/configuration kind."""
        allowed = (
            CANONICAL_INPUTS
            if self.subject_kind == "canonical"
            else CONFIGURATION_INPUTS
        )
        if self.subject_id not in allowed:
            msg = "Unknown publication derivation dependency."
            raise ValueError(msg)
        return self


class DerivedBinding(StrictModel):
    """An emitted value, mapping version and ordered actual source identities."""

    value: Text
    mapping_version: Text
    sources: list[BindingInput] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_sources(self) -> Self:
        """Never conceal duplicate or contradictory source identities."""
        keys = [(item.subject_kind, item.subject_id) for item in self.sources]
        if len(keys) != len(set(keys)):
            msg = "Duplicate publication derivation dependency."
            raise ValueError(msg)
        return self


class ResolvedSubject(ApprovalSubject):
    """Actual selected normalized value; resolution precedes approval comparison."""

    value: JsonValue

    def value_sha256(self) -> str:
        """Use the exact same normalized encoding for all subject kinds."""
        return value_hash(self.value)


def binding_input(
    kind: Literal["canonical", "configuration"], identifier: str, value: JsonValue
) -> BindingInput:
    """Hash an actual source value, including the normalized party label as needed."""
    return BindingInput(
        subject_kind=kind, subject_id=identifier, value_sha256=value_hash(value)
    )


def derived_subject(
    target: Target, identifier: str, value: str, sources: list[BindingInput]
) -> ResolvedSubject:
    """Require ordered source selection and bind dependencies, not only final text."""
    binding = DerivedBinding(
        value=value, mapping_version=mapping_version(target), sources=sources
    )
    return ResolvedSubject(
        subject_kind="derived_target",
        subject_id=identifier,
        target=target,
        value=binding.model_dump(mode="json"),
    )
