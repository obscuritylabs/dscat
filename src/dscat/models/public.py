# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Initial closed public shapes admit no optional private canonical children."""

from copy import deepcopy
from typing import Annotated, Literal

from pydantic import EmailStr, Field, JsonValue, field_validator

from dscat.export.models import CONTEXT, DcatContact, DcatDocument
from dscat.models.base import HttpsReference, Identifier, StrictModel, Text


class PublicDcatContact(StrictModel):
    """Accept only the selected approved contact label and email IRI."""

    kind: Literal["Kind"] = Field(default="Kind", alias="@type")
    fn: Text
    email: str = Field(alias="hasEmail")

    @field_validator("email")
    @classmethod
    def mailto(cls, value: str) -> str:
        """Retain the canonical email boundary without inheriting optional fields."""
        return DcatContact.mailto(value)


class PublicDcatDataset(StrictModel):
    """Only approved core metadata and its explicitly selected contact."""

    id: HttpsReference = Field(alias="@id")
    kind: Literal["Dataset"] = Field(default="Dataset", alias="@type")
    identifier: Identifier
    title: Text
    description: Text
    contact: PublicDcatContact = Field(alias="contactPoint")


class PublicDcatDocument(StrictModel):
    """Keep the pinned inline context while excluding optional private target fields."""

    context: dict[str, JsonValue] = Field(
        default_factory=lambda: deepcopy(CONTEXT), alias="@context"
    )
    id: HttpsReference = Field(alias="@id")
    kind: Literal["Catalog"] = Field(default="Catalog", alias="@type")
    datasets: Annotated[list[PublicDcatDataset], Field(max_length=100000)] = Field(
        alias="dataset"
    )

    @field_validator("context", mode="before")
    @classmethod
    def local_context(cls, value: object) -> object:
        """Require the same complete finite context before any graph interpretation."""
        return DcatDocument.local_context(value)


class PublicDescriptionProperty(StrictModel):
    """The generic description is the sole allowed description property."""

    property: Literal["catalogDescription"] = "catalogDescription"
    value: Text


class PublicIdentifierProperty(StrictModel):
    """Dataset identity remains separate from contract identity."""

    property: Literal["datasetIdentifier"] = "datasetIdentifier"
    value: Identifier


class PublicOdcsDescription(StrictModel):
    """Do not accept purpose, intended use, limitations or semantic references."""

    custom_properties: Annotated[
        list[PublicDescriptionProperty], Field(min_length=1, max_length=1)
    ] = Field(alias="customProperties")


class PublicTeamMember(StrictModel):
    """Publish only selected approved contact label and username, without a role."""

    username: EmailStr
    name: Text


class PublicOdcsTeam(StrictModel):
    """The initial public allowlist selects only the core role contact."""

    members: Annotated[list[PublicTeamMember], Field(min_length=1, max_length=1)]


class PublicOdcsDocument(StrictModel):
    """Exclude optional schema, roles, guarantees and other private target metadata."""

    api_version: Literal["v3.2.0"] = Field(default="v3.2.0", alias="apiVersion")
    kind: Literal["DataContract"] = "DataContract"
    id: Text
    version: Text
    name: Text
    description: PublicOdcsDescription
    custom_properties: Annotated[
        list[PublicIdentifierProperty], Field(min_length=1, max_length=1)
    ] = Field(alias="customProperties")
    team: PublicOdcsTeam | None = None
