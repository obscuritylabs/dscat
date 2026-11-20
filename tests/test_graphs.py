# Copyright (c) 2026 Obscurity Labs. All rights reserved.
"""Named dataset/distribution nodes and intended literal/contact RDF semantics."""

import socket
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError
from rdflib import Graph, Literal, Namespace, URIRef

from dscat.export.dcat_us_3 import project_dcat, serialize_dcat
from dscat.export.models import DcatDocument
from tests.test_dcat_us_3 import catalog, configuration

if TYPE_CHECKING:
    from rdflib.term import Node

DCAT = Namespace("http://www.w3.org/ns/dcat#")
DCTERMS = Namespace("http://purl.org/dc/terms/")
RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")
VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")


@pytest.mark.parametrize("detailed", [False, True])
def test_every_mapped_fact_has_its_intended_graph_meaning(
    monkeypatch: pytest.MonkeyPatch, *, detailed: bool
) -> None:
    """Parsing only local data cannot retrieve contexts or descriptive references."""

    def denied(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Graph acceptance attempted network access.")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    result = project_dcat(catalog(detailed=detailed), configuration())
    assert result.document is not None
    graph = Graph().parse(
        data=serialize_dcat(result.document), format="json-ld", version=1.1
    )
    root = URIRef("https://example.org/catalog")
    dataset = URIRef("https://example.org/datasets/asset-001")
    assert (root, RDF.type, DCAT.Catalog) in graph
    assert (root, DCAT.dataset, dataset) in graph
    assert (dataset, RDF.type, DCAT.Dataset) in graph
    assert (dataset, DCTERMS.identifier, Literal("asset-001")) in graph
    assert (dataset, DCTERMS.title, Literal("Synthetic measurements")) in graph
    assert (
        dataset,
        DCTERMS.description,
        Literal(catalog(detailed=detailed).datasets[0].description),
    ) in graph
    contacts = list(graph.objects(dataset, DCAT.contactPoint))
    assert len(contacts) == 1
    contact: Node = contacts[0]
    assert (contact, RDF.type, VCARD.Kind) in graph
    assert (contact, VCARD.fn, Literal("Metadata support")) in graph
    assert (contact, VCARD.hasEmail, URIRef("mailto:metadata@example.org")) in graph
    assert not list(graph.objects(dataset, DCTERMS.publisher))
    assert not list(graph.objects(dataset, DCTERMS.creator))
    if detailed:
        distribution = URIRef(str(dataset) + "/distributions/download")
        assert (dataset, DCAT.distribution, distribution) in graph
        assert (distribution, RDF.type, DCAT.Distribution) in graph
        assert (distribution, DCTERMS.title, Literal("Synthetic download")) in graph
        assert (
            distribution,
            DCAT.accessURL,
            URIRef("https://example.org/access/"),
        ) in graph
        assert (
            distribution,
            DCAT.downloadURL,
            URIRef("https://example.org/download/"),
        ) in graph
        assert (
            dataset,
            DCTERMS.modified,
            Literal("2026-01-03", datatype=XSD.date),
        ) in graph
        assert (dataset, DCAT.version, Literal("2026-Q1")) in graph
    else:
        assert not list(graph.objects(dataset, DCAT.distribution))


@pytest.mark.parametrize(
    "context",
    [
        "https://example.org/context",
        {"@import": "https://example.org/context"},
        {
            "field": {
                "@id": "https://example.org/term",
                "@context": "https://example.org/scoped",
            }
        },
    ],
)
def test_remote_context_refuses_before_graph_parser(
    context: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The model boundary rejects remote, imported and nested context shapes."""

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("An invalid context reached graph parsing.")

    monkeypatch.setattr(Graph, "parse", forbidden)
    result = project_dcat(catalog(), configuration())
    assert result.document is not None
    raw = result.document.model_dump(mode="json", by_alias=True, exclude_none=True)
    raw["@context"] = context
    with pytest.raises(ValidationError):
        DcatDocument.model_validate(raw)
