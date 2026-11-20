# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Hash-pinned CycloneDX 1.6 schema validation with no remote retrieval."""

import hashlib
from pathlib import Path
from typing import Annotated

from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError
from pydantic import Field, JsonValue, ValidationError
from referencing import Registry, Resource
from referencing.exceptions import CannotDetermineSpecification, Unresolvable
from referencing.jsonschema import UnknownDialect

from dscat.intake.limits import IntakeError
from dscat.json_guard import check_json
from dscat.models.base import HttpsReference, Sha256, StrictModel
from dscat.resources.registry import DOCUMENT, ResourceBundle, deny_retrieval

MANIFEST_SHA256 = "9ed0416f030527f1bdad9c21538e0b68a82a8188eb247406c213362fae29699a"
BOM_URI = "http://cyclonedx.org/schema/bom-1.6.schema.json"
RESOURCE_BYTES = 1024**2
DOCUMENT_BYTES = 32 * 1024**2
RESOURCE_NAMES = frozenset(
    {"bom-1.6.schema.json", "jsf-0.82.schema.json", "spdx.schema.json", "LICENSE"}
)


class SchemaEntry(StrictModel):
    """Only fixed schema and license names are eligible for local reads."""

    path: Annotated[
        str,
        Field(pattern=r"^(bom-1\.6|jsf-0\.82|spdx)\.schema\.json$|^LICENSE$"),
    ]
    sha256: Sha256
    url: HttpsReference


class SchemaManifest(StrictModel):
    """A separately pinned manifest identifies the complete upstream closure."""

    specification: str
    upstream_revision: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    resources: Annotated[list[SchemaEntry], Field(min_length=4, max_length=4)]


def load_schema_bundle() -> ResourceBundle:
    """Verify every schema and full notice before creating the denying registry."""
    root = Path(__file__).parent / "resources" / "cyclonedx"
    try:
        with root.joinpath("resource-manifest.json").open("rb") as stream:
            raw = stream.read(RESOURCE_BYTES + 1)
        if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
            msg = "CycloneDX manifest identity mismatch."
            raise ValueError(msg)
        manifest = SchemaManifest.model_validate_json(raw)
        if {entry.path for entry in manifest.resources} != RESOURCE_NAMES:
            msg = "CycloneDX resource set mismatch."
            raise ValueError(msg)
        bundle = ResourceBundle(registry=Registry(retrieve=deny_retrieval), schemas={})
        registry = bundle.registry
        schemas: dict[str, dict[str, JsonValue]] = {}
        for entry in manifest.resources:
            with root.joinpath(entry.path).open("rb") as stream:
                content = stream.read(RESOURCE_BYTES + 1)
            if hashlib.sha256(content).hexdigest() != entry.sha256:
                msg = "CycloneDX resource identity mismatch."
                raise ValueError(msg)
            if entry.path.endswith(".json"):
                check_json(content, RESOURCE_BYTES)
                schema = DOCUMENT.validate_json(content)
                identifier = schema.get("$id")
                expected = f"http://cyclonedx.org/schema/{entry.path}"
                if identifier != expected:
                    msg = "CycloneDX schema identity mismatch."
                    raise ValueError(msg)
                schemas[expected] = schema
                registry = registry.with_resources(
                    [(expected, Resource.from_contents(schema))]
                )
    except (
        OSError,
        ValidationError,
        IntakeError,
        CannotDetermineSpecification,
        UnknownDialect,
    ):
        msg = "CycloneDX validation resources are unavailable."
        raise ValueError(msg) from None
    return ResourceBundle(registry=registry, schemas=schemas)


def validate_sbom(raw: bytes) -> dict[str, JsonValue]:
    """Validate actual schema 1.6 bytes rather than trust a generator's default."""
    check_json(raw, DOCUMENT_BYTES)
    bundle = load_schema_bundle()
    try:
        document = DOCUMENT.validate_json(raw)
        schema = bundle.schemas[BOM_URI]
        Draft7Validator.check_schema(schema)
        if not Draft7Validator(schema, registry=bundle.registry).is_valid(document):
            msg = "SBOM does not conform to CycloneDX 1.6."
            raise ValueError(msg)
    except ValidationError, SchemaError, Unresolvable:
        msg = "SBOM validation failed."
        raise ValueError(msg) from None
    if document.get("specVersion") != "1.6":
        msg = "SBOM version is unsupported."
        raise ValueError(msg)
    return document
