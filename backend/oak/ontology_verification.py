"""Encode a bounded schema and check it with an isolated HermiT process."""

import asyncio
import hashlib
import json
import math
import os
import signal
import sys
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote
from xml.etree import ElementTree as ET

ENCODER_VERSION = "oak.owl-encoder.v2"
MAX_ENTITIES = 100
MAX_PROPERTIES = 300
MAX_RELATIONS = 200
MAX_AXIOMS = 200
MAX_CARDINALITY = 1000
_PROCESS_LOCK = asyncio.Lock()
_RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
_RDFS = "http://www.w3.org/2000/01/rdf-schema#"
_OWL = "http://www.w3.org/2002/07/owl#"
_XSD = "http://www.w3.org/2001/XMLSchema#"
for _prefix, _uri in (("rdf", _RDF), ("rdfs", _RDFS), ("owl", _OWL)):
    ET.register_namespace(_prefix, _uri)


class SchemaEncodingError(ValueError):
    def __init__(self, message, declaration_id=None):
        super().__init__(message)
        self.declaration_id = declaration_id


def _data(candidate):
    if hasattr(candidate, "model_dump"):
        return candidate.model_dump(mode="json", by_alias=True)
    return deepcopy(candidate)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _projection(candidate):
    data = _data(candidate)
    if not isinstance(data, dict) or not isinstance(data.get("schema"), dict):
        raise SchemaEncodingError("The candidate requires a schema object.")
    schema = data["schema"]
    projection = {
        "entities": deepcopy(schema.get("entities", [])),
        "relations": deepcopy(schema.get("relations", [])),
        "formal_axioms": deepcopy(data.get("formal_axioms", [])),
    }
    for records in projection.values():
        if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
            raise SchemaEncodingError("Schema declarations must be lists of objects.")
        records.sort(key=lambda record: str(record.get("id", "")))
    for entity in projection["entities"]:
        properties = entity.get("properties", [])
        if not isinstance(properties, list) or any(not isinstance(p, dict) for p in properties):
            raise SchemaEncodingError(
                "Entity properties must be a list of objects.", entity.get("id")
            )
        properties.sort(key=lambda prop: str(prop.get("name", "")))
    return projection


def formal_schema_digest(candidate):
    """Hash the source declarations that the encoder reads."""
    return hashlib.sha256(_canonical(_projection(candidate)).encode()).hexdigest()


def _identifier(value):
    return isinstance(value, str) and 0 < len(value) <= 200 and bool(value.strip())


def _indexed(records, label, limit):
    if len(records) > limit:
        raise SchemaEncodingError(f"The supported profile permits at most {limit} {label}.")
    result = {}
    for record in records:
        identifier = record.get("id")
        if not _identifier(identifier) or identifier in result:
            raise SchemaEncodingError(f"Invalid or duplicate {label} identifier.", identifier)
        result[identifier] = record
    return result


def _iri(kind, *identifiers):
    return "urn:oak:" + kind + ":" + "/".join(quote(value, safe="") for value in identifiers)


def _resource(parent, namespace, tag, iri):
    return ET.SubElement(parent, "{" + namespace + "}" + tag, {"{" + _RDF + "}resource": iri})


def encode_ontology(candidate):
    """Return deterministic RDF/XML. Never include imports or source individuals."""
    data = _data(candidate)
    source = _projection(data)
    entities = _indexed(source["entities"], "entities", MAX_ENTITIES)
    relations = _indexed(source["relations"], "relations", MAX_RELATIONS)
    axioms = _indexed(source["formal_axioms"], "formal axioms", MAX_AXIOMS)
    if not entities:
        raise SchemaEncodingError("The schema requires at least one entity.")
    total = sum(len(entity.get("properties", [])) for entity in entities.values())
    if total > MAX_PROPERTIES:
        raise SchemaEncodingError(
            f"The supported profile permits at most {MAX_PROPERTIES} scalar properties."
        )
    requirements = {
        r["id"] for r in data.get("requirements", {}).get("requirements", []) if "id" in r
    }
    schema_digest = formal_schema_digest(data)
    root = ET.Element("{" + _RDF + "}RDF")
    ET.SubElement(
        root, "{" + _OWL + "}Ontology", {"{" + _RDF + "}about": _iri("schema", schema_digest)}
    )
    class_nodes, relation_nodes, fields = {}, {}, {}
    for identifier, entity in entities.items():
        class_nodes[identifier] = ET.SubElement(
            root, "{" + _OWL + "}Class", {"{" + _RDF + "}about": _iri("entity", identifier)}
        )
        fields[identifier] = {}
        for prop in entity.get("properties", []):
            name, kind = prop.get("name"), prop.get("type")
            if not _identifier(name) or name in fields[identifier]:
                raise SchemaEncodingError("Invalid or duplicate property name.", identifier)
            expanded = data.get("version") == "oak.candidate.v3"
            element = prop.get("item_type")
            if kind not in {"string", "integer", "boolean"} and not (
                expanded
                and (
                    kind == "decimal"
                    or kind == "array"
                    and element in {"string", "integer", "boolean", "decimal"}
                )
            ):
                raise SchemaEncodingError(
                    "The formal profile supports only scalar properties.", identifier
                )
            fields[identifier][name] = kind
            node = ET.SubElement(
                root,
                "{" + _OWL + "}DatatypeProperty",
                {"{" + _RDF + "}about": _iri("property", identifier, name)},
            )
            _resource(node, _RDFS, "domain", _iri("entity", identifier))
            _resource(node, _RDFS, "range", _XSD + (element if kind == "array" else kind))
            # A scalar record property has at most one value. Absence is still unknown.
            if kind != "array":
                _resource(node, _RDF, "type", _OWL + "FunctionalProperty")
        keys = entity.get("identity_keys", [])
        if (
            not keys
            or not set(keys) <= fields[identifier].keys()
            or any(fields[identifier][key] not in {"string", "integer", "boolean"} for key in keys)
        ):
            raise SchemaEncodingError(
                "Entity identity fields must name scalar properties.", identifier
            )
    for identifier, relation in relations.items():
        start, end = relation.get("from_entity"), relation.get("to_entity")
        if start not in entities or end not in entities:
            raise SchemaEncodingError("A relation refers to an unknown entity.", identifier)
        left = fields[start].get(relation.get("from_property"))
        right = fields[end].get(relation.get("to_property"))
        if left is None or left != right or left == "array":
            raise SchemaEncodingError(
                "Relation endpoints require matching scalar properties.", identifier
            )
        node = ET.SubElement(
            root,
            "{" + _OWL + "}ObjectProperty",
            {"{" + _RDF + "}about": _iri("relation", identifier)},
        )
        _resource(node, _RDFS, "domain", _iri("entity", start))
        _resource(node, _RDFS, "range", _iri("entity", end))
        relation_nodes[identifier] = node

    optional_fields = {
        "entity_id",
        "target_entity_id",
        "relation_id",
        "inverse_relation_id",
        "restriction",
        "cardinality",
    }
    for identifier, axiom in axioms.items():
        kind = axiom.get("kind")
        required = {
            "subclass": {"entity_id", "target_entity_id"},
            "disjoint": {"entity_id", "target_entity_id"},
            "restriction": {"entity_id", "target_entity_id", "relation_id", "restriction"},
            "functional": {"relation_id"},
            "inverse_functional": {"relation_id"},
            "inverse": {"relation_id", "inverse_relation_id"},
        }.get(kind)
        if required is None:
            raise SchemaEncodingError(
                "The axiom kind is outside the supported profile.", identifier
            )
        if kind == "restriction" and axiom.get("restriction") in {"min", "max", "exactly"}:
            required = required | {"cardinality"}
        supplied = {key for key in optional_fields if axiom.get(key) is not None}
        if supplied != required or set(axiom) - optional_fields - {"id", "kind", "requirement_ids"}:
            raise SchemaEncodingError("The axiom fields do not match its kind.", identifier)
        refs = axiom.get("requirement_ids", [])
        if not refs or not set(refs) <= requirements:
            raise SchemaEncodingError("The axiom requires known source requirements.", identifier)
        for key in ("entity_id", "target_entity_id"):
            if key in supplied and axiom[key] not in entities:
                raise SchemaEncodingError("The axiom refers to an unknown entity.", identifier)
        for key in ("relation_id", "inverse_relation_id"):
            if key in supplied and axiom[key] not in relations:
                raise SchemaEncodingError("The axiom refers to an unknown relation.", identifier)
        if kind in {"subclass", "disjoint"}:
            if kind == "disjoint" and axiom["entity_id"] == axiom["target_entity_id"]:
                raise SchemaEncodingError(
                    "Disjointness requires two distinct entity classes.", identifier
                )
            _resource(
                class_nodes[axiom["entity_id"]],
                _RDFS if kind == "subclass" else _OWL,
                "subClassOf" if kind == "subclass" else "disjointWith",
                _iri("entity", axiom["target_entity_id"]),
            )
        elif kind == "restriction":
            restriction = axiom["restriction"]
            if restriction not in {"some", "only", "min", "max", "exactly"}:
                raise SchemaEncodingError("Unsupported relation restriction.", identifier)
            cardinality = axiom.get("cardinality")
            if restriction in {"min", "max", "exactly"} and (
                type(cardinality) is not int or not 0 <= cardinality <= MAX_CARDINALITY
            ):
                raise SchemaEncodingError(
                    "Cardinality must be an integer from 0 through 1000.", identifier
                )
            parent = ET.SubElement(class_nodes[axiom["entity_id"]], "{" + _RDFS + "}subClassOf")
            node = ET.SubElement(parent, "{" + _OWL + "}Restriction")
            _resource(node, _OWL, "onProperty", _iri("relation", axiom["relation_id"]))
            if restriction in {"some", "only"}:
                _resource(
                    node,
                    _OWL,
                    "someValuesFrom" if restriction == "some" else "allValuesFrom",
                    _iri("entity", axiom["target_entity_id"]),
                )
            else:
                tag = {
                    "min": "minQualifiedCardinality",
                    "max": "maxQualifiedCardinality",
                    "exactly": "qualifiedCardinality",
                }[restriction]
                ET.SubElement(
                    node,
                    "{" + _OWL + "}" + tag,
                    {"{" + _RDF + "}datatype": _XSD + "nonNegativeInteger"},
                ).text = str(cardinality)
                _resource(node, _OWL, "onClass", _iri("entity", axiom["target_entity_id"]))
        elif kind == "inverse":
            _resource(
                relation_nodes[axiom["relation_id"]],
                _OWL,
                "inverseOf",
                _iri("relation", axiom["inverse_relation_id"]),
            )
        else:
            _resource(
                relation_nodes[axiom["relation_id"]],
                _RDF,
                "type",
                _OWL
                + ("FunctionalProperty" if kind == "functional" else "InverseFunctionalProperty"),
            )
    ET.indent(root)
    return ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n"


def _worker_command(path, heap_mb):
    return [
        sys.executable,
        str(Path(__file__).with_name("ontology_worker.py")),
        str(path),
        str(heap_mb),
    ]


async def _terminate(process):
    """Stop the worker and its Java child before removing temporary files."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        await asyncio.wait_for(process.wait(), timeout=1)
    except TimeoutError:
        pass
    # The worker can exit before a child does. Always terminate the remaining group.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    await process.wait()


async def verify_candidate(candidate, *, timeout=30, heap_mb=128):
    """Return a schema report. A failed dependency never passes verification."""
    report = {
        "status": "invalid",
        "schema_digest": None,
        "versions": {"encoder": ENCODER_VERSION},
        "owl": "",
        "errors": [],
        "unsatisfiable_classes": [],
    }
    try:
        candidate = _data(candidate)
        report["schema_digest"] = formal_schema_digest(candidate)
        report["owl"] = encode_ontology(candidate)
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        report["errors"] = [
            {
                "code": "unsupported_schema",
                "message": str(error),
                "declaration_id": getattr(error, "declaration_id", None),
            }
        ]
        return report
    report["owl_digest"] = hashlib.sha256(report["owl"].encode()).hexdigest()
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
        or type(heap_mb) is not int
        or not 32 <= heap_mb <= 2048
    ):
        report.update(
            status="infrastructure_error",
            errors=[{"code": "invalid_limits", "message": "Verification limits are invalid."}],
        )
        return report
    process = None
    try:
        async with asyncio.timeout(timeout):
            async with _PROCESS_LOCK:
                with TemporaryDirectory(prefix="oak-ontology-") as directory:
                    path = Path(directory) / "schema.owl"
                    path.write_text(report["owl"], encoding="utf-8")
                    env = {**os.environ, "TMPDIR": directory}
                    starting = asyncio.create_task(
                        asyncio.create_subprocess_exec(
                            *_worker_command(path, heap_mb),
                            cwd=directory,
                            env=env,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                            start_new_session=True,
                        )
                    )
                    try:
                        process = await asyncio.shield(starting)
                    except BaseException:
                        process = await starting
                        await asyncio.shield(_terminate(process))
                        raise
                    try:
                        stdout, stderr = await process.communicate()
                    except BaseException:
                        await asyncio.shield(_terminate(process))
                        raise
                    if process.returncode or len(stdout) > 1_000_000:
                        raise RuntimeError("The ontology worker did not return a valid report.")
                    result = json.loads(stdout)
                    if (
                        not isinstance(result, dict)
                        or result.get("status") not in {"passed", "invalid", "infrastructure_error"}
                        or not isinstance(result.get("versions"), dict)
                        or any(not isinstance(value, str) for value in result["versions"].values())
                        or (
                            result["status"] in {"passed", "invalid"}
                            and not {"owlready2", "hermit", "hermit_jar_sha256", "java"}
                            <= result["versions"].keys()
                        )
                        or not isinstance(result.get("errors"), list)
                        or any(
                            not isinstance(item, dict)
                            or not isinstance(item.get("code"), str)
                            or not isinstance(item.get("message"), str)
                            for item in result["errors"]
                        )
                        or not isinstance(result.get("unsatisfiable_classes"), list)
                        or any(
                            not isinstance(item, str) for item in result["unsatisfiable_classes"]
                        )
                        or (
                            result["status"] == "passed"
                            and (result["errors"] or result["unsatisfiable_classes"])
                        )
                    ):
                        raise RuntimeError("The ontology worker returned an invalid report.")
                    report.update(
                        {key: result[key] for key in ("status", "errors", "unsatisfiable_classes")}
                    )
                    report["versions"].update(
                        {
                            key: value
                            for key, value in result["versions"].items()
                            if key != "encoder"
                        }
                    )
                    names = {
                        _iri("entity", entity["id"]): entity["id"]
                        for entity in _projection(candidate)["entities"]
                    }
                    report["unsatisfiable_classes"] = sorted(
                        names.get(iri, iri) for iri in report["unsatisfiable_classes"]
                    )
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        report.update(
            status="infrastructure_error",
            errors=[
                {
                    "code": "verification_timeout",
                    "message": "Formal verification exceeded its time limit.",
                }
            ],
        )
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        report.update(
            status="infrastructure_error",
            errors=[{"code": "worker_failure", "message": str(error)}],
        )
    return report
