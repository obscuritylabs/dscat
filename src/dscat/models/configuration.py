# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Explicit versioned export settings and pure declarative assessment rules."""

from typing import Annotated, Literal, Self, get_args

from pydantic import BaseModel, EmailStr, Field, model_validator

from dscat.models.base import HttpsReference, Identifier, Namespace, StrictModel, Text
from dscat.models.catalog import ApprovalSubject, DatasetRecord
from dscat.normalization import normalize_text

Scalar = str | bool | int


def canonical_paths(model: type[BaseModel] = DatasetRecord) -> frozenset[str]:
    """Enumerate schema-defined field paths, including children of typed collections."""
    paths: set[str] = set()

    def children(annotation: object) -> set[type[BaseModel]]:
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return {annotation}
        return {child for arg in get_args(annotation) for child in children(arg)}

    for name, field in model.model_fields.items():
        paths.add(name)
        for nested in children(field.annotation):
            paths.update(f"{name}.{path}" for path in canonical_paths(nested))
    return frozenset(paths)


class PartyConfiguration(StrictModel):
    """An explicit role-contact association for one normalized party label."""

    role_email: EmailStr
    contact_association: bool


class IdentityConfiguration(StrictModel):
    """Distinct namespaces and an explicit optional contract identity rule."""

    dataset_namespace: Namespace | None = None
    contract_namespace: Namespace | None = None
    contract_identity_rule: Literal["namespace-plus-dataset-id"] | None = None
    parties: dict[Text, PartyConfiguration] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def unique_labels(cls, data: object) -> object:
        """Reject normalized-key collisions before a dictionary could overwrite one."""
        if isinstance(data, dict) and isinstance(data.get("parties"), dict):
            labels = data["parties"]
            if len({normalize_text(label) for label in labels}) != len(labels):
                msg = "Duplicate normalized party label."
                raise ValueError(msg)
        return data

    @model_validator(mode="after")
    def distinct_namespaces(self) -> Self:
        """Prevent dataset and contract identity spaces from being conflated."""
        if (
            self.dataset_namespace is not None
            and self.dataset_namespace == self.contract_namespace
        ):
            msg = "Dataset and contract namespaces must differ."
            raise ValueError(msg)
        return self


class DcatConfiguration(StrictModel):
    """Only explicit shared catalog identity is configured for DCAT-US 3.0."""

    catalog_id: HttpsReference | None = None


class OdcsConfiguration(StrictModel):
    """A supplied contract version independent of all other versions."""

    contract_version: Text | None = None


class LocalRule(StrictModel):
    """Pure local metadata comparisons; no expressions, imports or code."""

    id: Identifier
    path: Text
    operator: Literal["present", "equals", "one_of"]
    operand: Scalar | None = None
    operands: Annotated[list[Scalar], Field(min_length=1)] | None = None
    severity: Literal["info", "warning", "error"] = "warning"

    @model_validator(mode="after")
    def valid_operation(self) -> Self:
        """Require a known schema path and exactly the applicable operand shape."""
        if self.path not in canonical_paths():
            msg = "Unknown canonical field path."
            raise ValueError(msg)
        valid = {
            "present": self.operand is None and self.operands is None,
            "equals": self.operand is not None and self.operands is None,
            "one_of": self.operand is None and self.operands is not None,
        }
        if not valid[self.operator]:
            msg = "Supply only the operands required by the selected operator."
            raise ValueError(msg)
        return self


class AssessmentConfiguration(StrictModel):
    """Optional completeness and conformity cannot change intake validity."""

    completeness: list[Text] = Field(default_factory=list)
    rules: list[LocalRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def known_unique_rules(self) -> Self:
        """Reject unknown paths, duplicate completeness paths and duplicate rule IDs."""
        if (
            len(set(self.completeness)) != len(self.completeness)
            or not set(self.completeness) <= canonical_paths()
        ):
            msg = "Completeness requires unique schema-defined canonical paths."
            raise ValueError(msg)
        if len({rule.id for rule in self.rules}) != len(self.rules):
            msg = "Duplicate assessment rule identifier."
            raise ValueError(msg)
        return self


class PublicationConfiguration(StrictModel):
    """Policy restricts allowed subjects but never supplies record approval."""

    policy_version: Text
    allowed_subjects: list[ApprovalSubject]
    authority_reference: Text

    @model_validator(mode="after")
    def unique_subjects(self) -> Self:
        """Reject duplicate publication policy subjects."""
        keys = {
            (item.subject_kind, item.subject_id, item.target)
            for item in self.allowed_subjects
        }
        if len(keys) != len(self.allowed_subjects):
            msg = "Duplicate publication policy subject."
            raise ValueError(msg)
        return self


class ExportConfiguration(StrictModel):
    """The complete closed configuration boundary, passed explicitly by the operator."""

    schema_version: Literal["1.0"]
    identity: IdentityConfiguration = Field(default_factory=IdentityConfiguration)
    dcat_us_3: DcatConfiguration = Field(default_factory=DcatConfiguration)
    odcs_3_2: OdcsConfiguration = Field(default_factory=OdcsConfiguration)
    assessment: AssessmentConfiguration = Field(default_factory=AssessmentConfiguration)
    publication: PublicationConfiguration | None = None
