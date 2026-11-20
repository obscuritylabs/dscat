# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Closed manifest and snapshot boundaries for canonical generations."""

import hashlib
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from dscat.models.base import Identifier, Sha256, StrictModel
from dscat.models.catalog import Catalog


def dataset_path(identifier: str) -> str:
    """Hide raw normalized business identifiers behind full portable hashes."""
    return f"datasets/{hashlib.sha256(identifier.encode('utf-8')).hexdigest()}.json"


class DatasetEntry(StrictModel):
    """An exact business identity, prescribed path and content identity."""

    id: Identifier
    path: str
    sha256: Sha256
    schema_version: Literal["1.0"]

    @model_validator(mode="after")
    def prescribed_path(self) -> Self:
        """Reject aliases, traversal and arbitrary relative or absolute names."""
        if self.path != dataset_path(self.id):
            msg = "Dataset filename must match its normalized identity."
            raise ValueError(msg)
        return self


class CanonicalManifest(StrictModel):
    """Canonical-only manifests do not embed assessments or configuration."""

    schema_version: Literal["1.0"]
    kind: Literal["canonical"]
    datasets: list[DatasetEntry] = Field(max_length=100000)
    resource_fingerprints: dict[str, Sha256] = Field(default_factory=dict)
    configuration_fingerprints: dict[str, Sha256] = Field(default_factory=dict)

    @model_validator(mode="after")
    def canonical_only(self) -> Self:
        """Require ordered unique identities and no unsupported projection inputs."""
        ids = [entry.id for entry in self.datasets]
        if ids != sorted(set(ids)):
            msg = "Manifest dataset identities must be unique and ordered."
            raise ValueError(msg)
        if self.resource_fingerprints or self.configuration_fingerprints:
            msg = "Canonical-only snapshots have no projection dependencies."
            raise ValueError(msg)
        return self


class Snapshot(StrictModel):
    """Loaded facts and their verified immutable generation identity."""

    generation: Sha256
    catalog: Catalog
    manifest: CanonicalManifest
    orphan_count: Annotated[int, Field(ge=0)] = 0
    retained_generation_count: Annotated[int, Field(ge=0)] = 0
