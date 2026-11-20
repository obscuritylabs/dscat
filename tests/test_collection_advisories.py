# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Scanner completeness and exploitation retrieval are separate hard boundaries."""

import hashlib
import io
import json
import urllib.request
from email.message import Message
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import pytest
from scripts import candidate_collection as collection
from scripts.processes import Execution

from tests.test_collection_boundaries import context
from tests.test_provenance import Reply
from tests.test_release_evidence import candidate

if TYPE_CHECKING:
    from urllib.request import Request


KEV = json.dumps({"count": 1, "vulnerabilities": [{"cveID": "CVE-2099-0001"}]}).encode()


class CatalogTransport(urllib.request.BaseHandler):
    """Return owned response bytes without DNS, sockets or real service access."""

    def __init__(self, mutation: str, raw: bytes) -> None:
        """Control one explicit response property at a time."""
        self.mutation = mutation
        self.raw = raw

    def https_open(self, request: Request) -> Reply:
        """Keep the selected request identity visible to the transport test."""
        assert request.full_url == collection.KEV_URL
        url = (
            "https://example.org/changed"
            if self.mutation == "origin"
            else request.full_url
        )
        code = 503 if self.mutation == "status" else 200
        return Reply(io.BytesIO(self.raw), Message(), url, code)


@pytest.mark.parametrize("mutation", ["none", "exit", "origin", "status", "size"])
def test_scanner_and_exploitation_catalog_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    """A nonclean scanner exit, changed origin or oversized feed cannot become clean."""
    workspace = context(tmp_path)
    evidence, _ = candidate()
    inventory = evidence.runtime
    raw = json.dumps(
        {
            "dependencies": [
                {"name": "synthetic-package", "version": "1.0", "vulns": []}
            ],
            "fixes": [],
        }
    ).encode()

    def run(argv: list[str], **options: object) -> Execution:
        label = str(options["label"])
        assert {"--strict", "--no-deps", "--require-hashes"} <= set(argv)
        Path(argv[argv.index("--output") + 1]).write_bytes(raw)
        return Execution(label, int(mutation == "exit"), "a" * 64, "b" * 64, 0.1)

    monkeypatch.setattr(collection, "run_tool", run)
    opener = urllib.request.OpenerDirector()
    response = KEV + b" " * len(raw) if mutation == "size" else KEV
    opener.add_handler(CatalogTransport(mutation, response))
    monkeypatch.setattr(
        collection.urllib.request, "build_opener", lambda *_handlers: opener
    )
    if mutation == "size":
        # Audit documents still fit; the catalog is larger than this test bound.
        monkeypatch.setattr(collection, "DOCUMENT_BYTES", len(raw))
    inventories: dict[Literal["runtime", "development"], collection.Inventory] = {
        "runtime": inventory,
        "development": inventory,
    }
    arguments = (
        workspace,
        inventories,
        {"runtime": tmp_path / "runtime", "development": tmp_path / "development"},
    )
    if mutation != "none":
        with pytest.raises(
            ValueError, match=r"disagree|selected source|supported bounds"
        ):
            collection.collect_advisories(*arguments)
        assert not (workspace.assets / "cisa-kev.json").exists()
    else:
        feeds, findings, exploited = collection.collect_advisories(*arguments)
        assert findings == []
        assert exploited == {"CVE-2099-0001"}
        assert {(feed.source, feed.scope) for feed in feeds} == {
            ("pypi", "runtime"),
            ("pypi", "development"),
            ("osv", "runtime"),
            ("osv", "development"),
            ("cisa-kev", "catalog"),
        }
        assert all(feed.state == "complete" for feed in feeds)
        assert feeds[-1].sha256 == hashlib.sha256(KEV).hexdigest()
        assert (workspace.assets / "cisa-kev.json").read_bytes() == KEV
