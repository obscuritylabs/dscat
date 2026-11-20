# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Closed ODCS 3.2.0 shapes preserve supplied meanings without guarantees."""

from typing import Annotated, Literal

from pydantic import EmailStr, Field

from dscat.models.base import Reference, StrictModel, Text

LogicalType = Literal[
    "string",
    "date",
    "timestamp",
    "time",
    "number",
    "integer",
    "object",
    "array",
    "boolean",
]


class TextProperty(StrictModel):
    """A named metadata custom property, never an untyped extension dictionary."""

    property: Literal[
        "catalogDescription", "datasetIdentifier", "datasetVersion", "catalogFieldType"
    ]
    value: Text


class NullableProperty(StrictModel):
    """Preserve the supplied nullable boolean without implying a required inversion."""

    property: Literal["canonicalNullable"] = "canonicalNullable"
    value: bool


CustomProperty = Annotated[
    TextProperty | NullableProperty, Field(discriminator="property")
]


class AuthoritativeDefinition(StrictModel):
    """A descriptive semantic URI is never retrieved."""

    url: Reference
    type: Literal["semanticReference"] = "semanticReference"


class OdcsDescription(StrictModel):
    """Generic summary, intended use and limitations remain separate meanings."""

    custom_properties: list[TextProperty] = Field(alias="customProperties")
    usage: Text | None = None
    limitations: Text | None = None
    definitions: list[AuthoritativeDefinition] | None = Field(
        default=None, alias="authoritativeDefinitions"
    )


class TeamMember(StrictModel):
    """Only an explicitly resolved username and supplied role can describe a member."""

    username: EmailStr
    name: Text
    role: Literal["accountable_owner", "steward", "contact", "maintainer"] | None = None


class OdcsTeam(StrictModel):
    """Use the selected team object rather than deprecated upstream array syntax."""

    members: Annotated[list[TeamMember], Field(min_length=1)]


class OdcsField(StrictModel):
    """Keep declared types, semantic references and nullable facts explicit."""

    name: Text
    logical_type: LogicalType | None = Field(default=None, alias="logicalType")
    description: Text | None = None
    custom_properties: list[CustomProperty] | None = Field(
        default=None, alias="customProperties"
    )
    definitions: list[AuthoritativeDefinition] | None = Field(
        default=None, alias="authoritativeDefinitions"
    )


class OdcsObject(StrictModel):
    """One supplied object name and its ordered properties."""

    name: Text
    logical_type: Literal["object"] = Field(default="object", alias="logicalType")
    properties: list[OdcsField]


class OdcsDocument(StrictModel):
    """Selected constants and required contract facts; no purpose, quality or SLA."""

    api_version: Literal["v3.2.0"] = Field(default="v3.2.0", alias="apiVersion")
    kind: Literal["DataContract"] = "DataContract"
    id: Text
    version: Text
    name: Text
    description: OdcsDescription
    custom_properties: list[TextProperty] = Field(alias="customProperties")
    team: OdcsTeam | None = None
    schema_objects: list[OdcsObject] | None = Field(default=None, alias="schema")
