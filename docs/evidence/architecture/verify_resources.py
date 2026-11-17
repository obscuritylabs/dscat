"""Research-only offline resource audit and minimum-export experiment.

Run from any directory: python3 docs/evidence/architecture/verify_resources.py.
No downloads or dependency installation occur. JSON Schema experiments require
pre-existing jsonschema and referencing tooling; absence fails explicitly.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from urllib.parse import quote, urldefrag, urljoin
import socket


def network_forbidden(*args, **kwargs):
    raise RuntimeError("Network forbidden during research verification")


socket.create_connection = network_forbidden
socket.socket.connect = network_forbidden

ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / "resource-manifest.json").read_text())
RESOURCES = {}
for record in MANIFEST["resources"]:
    payload = (ROOT / record["path"]).read_bytes()
    assert hashlib.sha256(payload).hexdigest() == record["sha256"], record["path"]
    if record["path"].endswith(".json"):
        RESOURCES[record["resolver_uri"]] = json.loads(payload)


def references(node, base):
    if isinstance(node, dict):
        base = urljoin(base, node["$id"]) if isinstance(node.get("$id"), str) else base
        for key, value in node.items():
            if key in {"$ref", "$dynamicRef", "$recursiveRef", "$schema"} and isinstance(value, str):
                yield urljoin(base, value)
            else:
                yield from references(value, base)
    elif isinstance(node, list):
        for value in node:
            yield from references(value, base)


resolved_documents = set()
for uri, schema in RESOURCES.items():
    for reference in references(schema, uri):
        document, fragment = urldefrag(reference)
        assert document in RESOURCES, reference
        resolved_documents.add(document)
        if fragment.startswith("/"):
            target = RESOURCES[document]
            for segment in fragment[1:].split("/"):
                target = target[segment.replace("~1", "/").replace("~0", "~")]
print(f"PASS hashes: {len(MANIFEST['resources'])}; schema documents: {len(RESOURCES)}; referenced document URIs: {len(resolved_documents)}")

try:
    from jsonschema import Draft201909Validator, Draft202012Validator
    from referencing import Registry, Resource
except ImportError as error:
    raise SystemExit("PENDING schema validation: pre-existing jsonschema/referencing research tooling unavailable") from error


def deny_network(uri):
    raise RuntimeError(f"Unbundled resource requested: {uri}")


registry = Registry(retrieve=deny_network)
for uri, schema in RESOURCES.items():
    registry = registry.with_resource(uri, Resource.from_contents(schema))

for target, validator_type, uri in [
    ("dcat", Draft202012Validator, "https://resources.data.gov/dcat-us/3.0.0/definitions/catalog"),
    ("odcs", Draft201909Validator, next(uri for uri in RESOURCES if uri.endswith("odcs-json-schema-v3.2.0.json"))),
]:
    schema = RESOURCES[uri]
    validator_type.check_schema(schema)
    validator = validator_type(schema, registry=registry, format_checker=validator_type.FORMAT_CHECKER)
    positive = json.loads((ROOT / f"minimum-{target}.json").read_text())
    validator.validate(positive)
    if target == "odcs":
        no_contact = copy.deepcopy(positive)
        del no_contact["team"]
        validator.validate(no_contact)
    negative = copy.deepcopy(positive)
    if target == "dcat":
        del negative["dataset"][0]["contactPoint"]["hasEmail"]
    else:
        negative["kind"] = "Dataset"
    assert list(validator.iter_errors(negative)), target
    mutants = []
    if target == "dcat":
        for field in ["description", "title", "identifier", "contactPoint"]:
            candidate = copy.deepcopy(positive)
            del candidate["dataset"][0][field]
            mutants.append(candidate)
        candidate = copy.deepcopy(positive)
        candidate["dataset"][0]["contactPoint"]["hasEmail"] = "invalid-email"
        mutants.append(candidate)
        candidate = copy.deepcopy(positive)
        candidate["dataset"][0]["title"] = 17
        mutants.append(candidate)
    else:
        for field in ["version", "apiVersion", "kind", "id"]:
            candidate = copy.deepcopy(positive)
            del candidate[field]
            mutants.append(candidate)
        candidate = copy.deepcopy(positive)
        candidate["description"] = "wrong shape"
        mutants.append(candidate)
        candidate = copy.deepcopy(positive)
        candidate["team"]["members"][0]["unexpected"] = True
        mutants.append(candidate)
    for candidate in mutants:
        assert list(validator.iter_errors(candidate)), target
    print(f"PASS {target}: positive minimum and {len(mutants) + 1} negative schema fixtures")

# Demonstrate that the positive fixtures are precisely derived from four-field
# core + explicit shared configuration, without optional sheets or commitments.
core = json.loads((ROOT / "minimum-core.json").read_text())
config = json.loads((ROOT / "minimum-configuration.json").read_text())
party = config["identity"]["parties"][core["core_party"]["label"]]
assert party["contact_association"] is True
segment = quote(core["id"], safe="")
dcat = json.loads((ROOT / "minimum-dcat.json").read_text())
assert dcat["@id"] == config["dcat_us_3"]["catalog_id"]
assert dcat["dataset"] == [{
    "@id": config["identity"]["dataset_namespace"] + segment,
    "@type": "Dataset", "identifier": core["id"], "title": core["title"],
    "description": core["description"], "contactPoint": {
        "@type": "Kind", "fn": core["core_party"]["label"],
        "hasEmail": "mailto:" + party["role_email"],
    },
}]
odcs = json.loads((ROOT / "minimum-odcs.json").read_text())
assert odcs == {
    "apiVersion": "v3.2.0", "kind": "DataContract",
    "id": config["identity"]["contract_namespace"] + segment,
    "version": config["odcs_3_2"]["contract_version"], "name": core["title"],
    "description": {"customProperties": [{"property": "catalogDescription", "value": core["description"]}]},
    "team": {"members": [{"username": party["role_email"], "name": core["core_party"]["label"]}]},
}
assert odcs["id"] != dcat["dataset"][0]["@id"]
assert "purpose" not in odcs["description"] and "slaProperties" not in odcs
print("PASS core/configuration derivation; distinct identities; no invented purpose/service guarantees")

from pyld import jsonld


def deny_document(url, options=None):
    raise RuntimeError("Remote JSON-LD document forbidden")


options = {"documentLoader": deny_document, "processingMode": "json-ld-1.1"}
expanded = jsonld.expand(dcat, options=options)
nquads = jsonld.to_rdf(dcat, options={**options, "format": "application/n-quads"})
subject = "<https://example.org/datasets/asset-001>"
assert '<https://example.org/catalog> <http://www.w3.org/ns/dcat#dataset> ' + subject in nquads
assert subject + ' <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/ns/dcat#Dataset>' in nquads
assert subject + ' <http://purl.org/dc/terms/identifier> "asset-001"' in nquads
assert subject + ' <http://purl.org/dc/terms/description> "Synthetic measurement metadata."' in nquads
assert '<http://www.w3.org/2006/vcard/ns#hasEmail> <mailto:metadata@example.org>' in nquads
assert '<http://www.w3.org/2006/vcard/ns#fn> "Metadata support"' in nquads
assert '<http://www.w3.org/2006/vcard/ns#Kind>' in nquads
assert "contactPoint" in str(expanded)
for bad in [{"@context": "https://example.org/unbundled-context", "@id": "https://example.org/x"},
            {"@context": {"@version": 2}, "@id": "https://example.org/x"}]:
    try:
        jsonld.expand(bad, options=options)
    except Exception:
        pass
    else:
        raise AssertionError("Invalid/remote JSON-LD unexpectedly accepted")
try:
    registry.get_or_retrieve("https://example.org/unbundled-schema")
except Exception:
    pass
else:
    raise AssertionError("Unbundled schema unexpectedly resolved")
print("PASS offline JSON-LD expansion/RDF core graph; rejected remote context, malformed context and unknown schema")

for target, validator_type, uri in [
    ("dcat", Draft202012Validator, "https://resources.data.gov/dcat-us/3.0.0/definitions/catalog"),
    ("odcs", Draft201909Validator, next(uri for uri in RESOURCES if uri.endswith("odcs-json-schema-v3.2.0.json"))),
]:
    validator = validator_type(RESOURCES[uri], registry=registry, format_checker=validator_type.FORMAT_CHECKER)
    detailed = json.loads((ROOT / f"detailed-{target}.json").read_text())
    validator.validate(detailed)
    malformed = copy.deepcopy(detailed)
    if target == "dcat":
        malformed["dataset"][0]["distribution"][0]["accessURL"] = 45
    else:
        malformed["schema"][0]["properties"][0]["logicalType"] = "madeUpType"
    assert list(validator.iter_errors(malformed)), target
    if target == "dcat":
        graph = jsonld.to_rdf(detailed, options={**options, "format": "application/n-quads"})
        assert subject + ' <http://www.w3.org/ns/dcat#distribution> <https://example.org/datasets/asset-001/distributions/csv>' in graph
        assert '<https://example.org/datasets/asset-001/distributions/csv> <http://www.w3.org/ns/dcat#downloadURL> <https://example.org/measurements.csv>' in graph
        assert subject + ' <http://purl.org/dc/terms/modified> "2026-10-01"^^<http://www.w3.org/2001/XMLSchema#date>' in graph
        assert subject + ' <http://www.w3.org/ns/dcat#version> "dataset-4"' in graph
    print(f"PASS {target}: detailed optional mapping and malformed output rejection")
