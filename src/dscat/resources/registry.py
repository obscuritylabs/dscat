# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Verify pinned local resources and deny every unbundled reference retrieval."""

import hashlib
from dataclasses import dataclass
from importlib.resources import files
from typing import TYPE_CHECKING, Annotated

from pydantic import Field, JsonValue, TypeAdapter, ValidationError
from referencing import Registry, Resource
from referencing.exceptions import (
    CannotDetermineSpecification,
    NoSuchResource,
)
from referencing.jsonschema import UnknownDialect

from dscat.intake.limits import IntakeError
from dscat.json_guard import check_json
from dscat.models.base import Sha256, StrictModel

if TYPE_CHECKING:
    from referencing.jsonschema import SchemaRegistry, SchemaResource

MANIFEST_SHA256 = "f352010ab552d96bce636dff81d7a3cd25fba9fc60175d474cfffc466ecded26"
RESOURCE_BYTES = 1024**2
SCHEMA_COUNT = 42
DOCUMENT = TypeAdapter(dict[str, JsonValue])


class ResourceError(Exception):
    """A fixed resource failure that never exposes a path or input value."""

    def __init__(self) -> None:
        """Retain one public-safe resource-integrity message."""
        super().__init__("Packaged validation resources are unavailable or invalid.")


class ResourceEntry(StrictModel):
    """The unchanged approved manifest binds public retrieval and resolver URIs."""

    url: str
    path: Annotated[str, Field(pattern=r"^resources/[A-Za-z0-9_.-]+$")]
    sha256: Sha256
    resolver_uri: str | None = None


class ResourceManifest(StrictModel):
    """Exactly the selected schemas, meta-schemas and complete license notices."""

    retrieved: str
    resources: Annotated[list[ResourceEntry], Field(min_length=45, max_length=45)]


@dataclass(frozen=True)
class ResourceBundle:
    """Validated package bytes and an immutable, explicitly denying registry."""

    registry: SchemaRegistry
    schemas: dict[str, dict[str, JsonValue]]


def deny_retrieval(uri: str) -> SchemaResource:
    """Never use an implicit downloader, even for an apparently familiar URI."""
    raise NoSuchResource(ref=uri)


def load_registry() -> ResourceBundle:
    """Check the manifest and every installed resource before creating a resolver."""
    root = files("dscat.resources").joinpath("vendor")
    try:
        with root.joinpath("resource-manifest.json").open("rb") as stream:
            raw = stream.read(RESOURCE_BYTES + 1)
        if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
            raise ResourceError
        manifest = ResourceManifest.model_validate_json(raw)
        schemas: dict[str, dict[str, JsonValue]] = {}
        names: set[str] = set()
        registry: SchemaRegistry = Registry(retrieve=deny_retrieval)
        for entry in manifest.resources:
            if entry.path in names:
                raise ResourceError
            names.add(entry.path)
            with root.joinpath(entry.path).open("rb") as stream:
                content = stream.read(RESOURCE_BYTES + 1)
            if hashlib.sha256(content).hexdigest() != entry.sha256:
                raise ResourceError
            if entry.resolver_uri is not None:
                check_json(content, RESOURCE_BYTES)
                schema = DOCUMENT.validate_json(content)
                if (
                    entry.resolver_uri in schemas
                    or schema.get("$id", entry.resolver_uri) != entry.resolver_uri
                ):
                    raise ResourceError
                schemas[entry.resolver_uri] = schema
                registry = registry.with_resources(
                    [(entry.resolver_uri, Resource.from_contents(schema))]
                )
        if len(schemas) != SCHEMA_COUNT:
            raise ResourceError
    except (
        OSError,
        ValueError,
        ValidationError,
        IntakeError,
        CannotDetermineSpecification,
        UnknownDialect,
    ):
        raise ResourceError from None
    return ResourceBundle(registry=registry, schemas=schemas)
