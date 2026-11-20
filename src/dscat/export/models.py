# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Closed DCAT-US projection models and a finite inline JSON-LD context."""

from copy import deepcopy
from typing import Annotated, Literal

from pydantic import EmailStr, Field, JsonValue, TypeAdapter, field_validator

from dscat.models.base import (
    CalendarDate,
    HttpsReference,
    Identifier,
    StrictModel,
    Text,
)

EMAIL = TypeAdapter(EmailStr)
CONTEXT: dict[str, JsonValue] = {
    "dcat": "http://www.w3.org/ns/dcat#",
    "dcterms": "http://purl.org/dc/terms/",
    "vcard": "http://www.w3.org/2006/vcard/ns#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "Catalog": "dcat:Catalog",
    "Dataset": "dcat:Dataset",
    "Kind": "vcard:Kind",
    "Distribution": "dcat:Distribution",
    "dataset": {"@id": "dcat:dataset", "@type": "@id"},
    "identifier": "dcterms:identifier",
    "title": "dcterms:title",
    "description": "dcterms:description",
    "contactPoint": {"@id": "dcat:contactPoint", "@type": "@id"},
    "fn": "vcard:fn",
    "hasEmail": {"@id": "vcard:hasEmail", "@type": "@id"},
    "distribution": {"@id": "dcat:distribution", "@type": "@id"},
    "accessURL": {"@id": "dcat:accessURL", "@type": "@id"},
    "downloadURL": {"@id": "dcat:downloadURL", "@type": "@id"},
    "modified": {"@id": "dcterms:modified", "@type": "xsd:date"},
    "version": "dcat:version",
}


class DcatContact(StrictModel):
    """One explicitly associated contact; no ownership or publisher inference."""

    kind: Literal["Kind"] = Field(default="Kind", alias="@type")
    fn: Text
    email: str = Field(alias="hasEmail")

    @field_validator("email")
    @classmethod
    def mailto(cls, value: str) -> str:
        """Keep email as a mailto IRI while applying the canonical email boundary."""
        if not value.startswith("mailto:"):
            msg = "Contact email requires a mailto IRI."
            raise ValueError(msg)
        return "mailto:" + EMAIL.validate_python(value.removeprefix("mailto:"))


class DcatDistribution(StrictModel):
    """Only supplied distribution facts with separately minted node identities."""

    id: HttpsReference = Field(alias="@id")
    kind: Literal["Distribution"] = Field(default="Distribution", alias="@type")
    title: Text | None = None
    access_url: HttpsReference | None = Field(default=None, alias="accessURL")
    download_url: HttpsReference | None = Field(default=None, alias="downloadURL")


class DcatDataset(StrictModel):
    """The selected profile's required core and supported optional fields."""

    id: HttpsReference = Field(alias="@id")
    kind: Literal["Dataset"] = Field(default="Dataset", alias="@type")
    identifier: Identifier
    title: Text
    description: Text
    contact: DcatContact = Field(alias="contactPoint")
    modified: CalendarDate | None = None
    version: Text | None = None
    distributions: Annotated[list[DcatDistribution], Field(min_length=1)] | None = (
        Field(default=None, alias="distribution")
    )


class DcatDocument(StrictModel):
    """No arbitrary context, remote context, extension key or nested context."""

    context: dict[str, JsonValue] = Field(
        default_factory=lambda: deepcopy(CONTEXT), alias="@context"
    )
    id: HttpsReference = Field(alias="@id")
    kind: Literal["Catalog"] = Field(default="Catalog", alias="@type")
    datasets: list[DcatDataset] = Field(alias="dataset")

    @field_validator("context", mode="before")
    @classmethod
    def local_context(cls, value: object) -> object:
        """Require the complete finite mapping before any graph interpretation."""
        if value != CONTEXT:
            msg = "Only the packaged inline context is supported."
            raise ValueError(msg)
        return value
