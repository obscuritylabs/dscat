# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""One deterministic encoding for validated canonical and manifest models."""

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dscat.models.base import StrictModel


def canonical_bytes(model: StrictModel) -> bytes:
    """Encode normalized facts with sorted keys and exactly one trailing LF."""
    return (
        json.dumps(
            model.model_dump(mode="json", exclude_none=True),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )
