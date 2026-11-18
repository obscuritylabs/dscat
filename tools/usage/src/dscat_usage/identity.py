"""Versioned shared-secret receipts, never content-derived identity."""

from __future__ import annotations

import hmac
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from .private import read_bytes
from .schema import canonical, require, text

SECRET_BYTES = 32
DOMAIN = "dscat-usage/receipt-domain/v1"


def load_secret(path: Path) -> bytes:
    """Read and validate an externally provisioned shared secret."""
    secret = read_bytes(path, SECRET_BYTES, private=True)
    require(len(secret) == SECRET_BYTES, "shared secret must contain 32 bytes", 2)
    return secret


def domain(secret: bytes) -> str:
    """Return the versioned shared-secret domain marker."""
    require(isinstance(secret, bytes) and len(secret) == SECRET_BYTES, "invalid shared secret")
    return hmac.digest(secret, DOMAIN.encode(), "sha256").hex()


def receipt(secret: bytes, kind: str, thread_id: str, native_id: str | None = None) -> str:
    """Return a domain-separated stable native-identity receipt."""
    domain(secret)
    require(kind in {"thread", "turn", "response", "root", "parent"}, "unsupported receipt type")
    text(thread_id, r"[^\x00-\x1f]{1,512}")
    if kind in {"response", "turn"}:
        text(native_id, r"[^\x00-\x1f]{1,512}")
        values = ["dscat-usage/receipt/v1", kind, thread_id, native_id]
    else:
        require(native_id is None, "unexpected native identity")
        # Relationships use thread receipts so they join to the thread corpus;
        # tuple kind remains explicit for callers requesting separate markers.
        values = ["dscat-usage/receipt/v1", kind, thread_id]
    return hmac.digest(secret, canonical(values), "sha256").hex()
