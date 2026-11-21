# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Closed manifest and snapshot boundaries for canonical generations."""

import hashlib
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from dscat.models.base import Identifier, Sha256, StrictModel, Target, Text
from dscat.models.catalog import Catalog


def dataset_path(identifier: str) -> str:
    """Hide raw normalized business identifiers behind full portable hashes."""
    return f"datasets/{hashlib.sha256(identifier.encode('utf-8')).hexdigest()}.json"


class DatasetEntry(StrictModel):
    """An exact business identity, prescribed path and content identity."""

    id: Identifier
    path: str
    sha256: Sha256
    schema_version: Literal["1.0", "1.1"]

    @model_validator(mode="after")
    def prescribed_path(self) -> Self:
        """Reject aliases, traversal and arbitrary relative or absolute names."""
        if self.path != dataset_path(self.id):
            msg = "Dataset filename must match its normalized identity."
            raise ValueError(msg)
        return self


def export_path(target: Target, dataset_id: str | None = None) -> str:
    """Use static catalog names and full hashed IDs rather than raw path components."""
    if target == "dcat-us-3":
        return "exports/dcat-us-3/catalog.json"
    if dataset_id is None:
        msg = "An ODCS artifact requires its dataset identity."
        raise ValueError(msg)
    digest = hashlib.sha256(dataset_id.encode("utf-8")).hexdigest()
    return f"exports/odcs-3.2/{digest}.json"


class ExportEntry(StrictModel):
    """Bind one internal target artifact to its exact prescribed relative path."""

    target: Target
    dataset_id: Identifier | None = None
    path: str
    sha256: Sha256

    @model_validator(mode="after")
    def prescribed_path(self) -> Self:
        """Reject target aliases and any unexpected dataset association."""
        if self.target == "dcat-us-3" and self.dataset_id is not None:
            msg = "A DCAT catalog artifact does not have a per-dataset path."
            raise ValueError(msg)
        if self.path != export_path(self.target, self.dataset_id):
            msg = "Target artifact path does not match its selected identity."
            raise ValueError(msg)
        return self


class CanonicalManifest(StrictModel):
    """Canonical facts and optional target artifacts retain only input fingerprints."""

    schema_version: Literal["1.0", "1.1"]
    kind: Literal["canonical"]
    datasets: list[DatasetEntry] = Field(max_length=100000)
    resource_fingerprints: dict[str, Sha256] = Field(default_factory=dict)
    configuration_fingerprints: dict[str, Sha256] = Field(default_factory=dict)

    requested_targets: list[Target] | None = None
    successful_targets: list[Target] | None = None
    exports: Annotated[list[ExportEntry], Field(max_length=100001)] | None = None
    mapping_versions: dict[Target, Text] | None = None

    @model_validator(mode="after")
    def canonical_only(self) -> Self:
        """Require ordered identities and complete target dependency metadata."""
        if any(entry.schema_version != self.schema_version for entry in self.datasets):
            msg = "Dataset versions must match the canonical manifest."
            raise ValueError(msg)
        ids = [entry.id for entry in self.datasets]
        if ids != sorted(set(ids)):
            msg = "Manifest dataset identities must be unique and ordered."
            raise ValueError(msg)
        if self.requested_targets is None:
            if (
                self.resource_fingerprints
                or self.configuration_fingerprints
                or self.successful_targets is not None
                or self.exports is not None
                or self.mapping_versions is not None
            ):
                msg = "Canonical-only snapshots have no projection dependencies."
                raise ValueError(msg)
            return self
        requested = self.requested_targets
        successful = self.successful_targets
        if (
            not requested
            or requested != sorted(set(requested))
            or successful is None
            or successful != sorted(set(successful))
            or not set(successful) <= set(requested)
            or self.exports is None
            or self.mapping_versions is None
            or set(self.resource_fingerprints) != set(requested)
            or set(self.configuration_fingerprints) != set(requested)
            or set(self.mapping_versions) != set(requested)
        ):
            msg = "Incomplete or inconsistent target projection dependencies."
            raise ValueError(msg)
        paths = [entry.path for entry in self.exports]
        if paths != sorted(set(paths)) or any(
            entry.target not in successful for entry in self.exports
        ):
            msg = "Target artifacts must be unique, ordered and successful."
            raise ValueError(msg)
        dcat = [entry for entry in self.exports if entry.target == "dcat-us-3"]
        odcs = [entry for entry in self.exports if entry.target == "odcs-3.2"]
        if len(dcat) != int("dcat-us-3" in successful) or (
            "odcs-3.2" in successful
            and {entry.dataset_id for entry in odcs} != set(ids)
        ):
            msg = "Successful targets require every prescribed catalog artifact."
            raise ValueError(msg)
        return self


class Snapshot(StrictModel):
    """Loaded facts and their verified immutable generation identity."""

    generation: Sha256
    catalog: Catalog
    manifest: CanonicalManifest
    orphan_count: Annotated[int, Field(ge=0)] = 0
    retained_generation_count: Annotated[int, Field(ge=0)] = 0


class ProjectionEntry(StrictModel):
    """A minimal public artifact name and byte identity with no canonical metadata."""

    path: Annotated[
        str,
        Field(pattern=r"^exports/(dcat-us-3/catalog|odcs-3\.2/[0-9a-f]{64})\.json$"),
    ]
    sha256: Sha256


class ProjectionManifest(StrictModel):
    """Only approved target names, relative paths and public artifact identities."""

    schema_version: Literal["1.0"]
    kind: Literal["projection"]
    targets: Annotated[list[Target], Field(min_length=1, max_length=2)]
    artifacts: Annotated[list[ProjectionEntry], Field(max_length=100001)]

    @model_validator(mode="after")
    def exact_artifacts(self) -> Self:
        """Forbid duplicates and artifacts belonging to an unselected target."""
        paths = [entry.path for entry in self.artifacts]
        if self.targets != sorted(set(self.targets)) or paths != sorted(set(paths)):
            msg = "Public targets and artifacts must be unique and ordered."
            raise ValueError(msg)
        if any(path.split("/")[1] not in self.targets for path in paths) or (
            ("exports/dcat-us-3/catalog.json" in paths) != ("dcat-us-3" in self.targets)
        ):
            msg = "Public artifacts must match the exact selected targets."
            raise ValueError(msg)
        return self


class ProjectionSnapshot(StrictModel):
    """A public generation has no canonical catalog or private input fingerprints."""

    generation: Sha256
    manifest: ProjectionManifest
    orphan_count: Annotated[int, Field(ge=0)] = 0
    retained_generation_count: Annotated[int, Field(ge=0)] = 0
