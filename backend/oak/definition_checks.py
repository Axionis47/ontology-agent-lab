"""Reject duplicates and identify every persistent constant that needs review."""

import re
from copy import deepcopy

from oak.graph_query import definition_catalog
from oak.repair_patch import candidate_digest, canonical_digest


def normalized_definition(value):
    value = deepcopy(value)
    value.pop("id", None)
    steps = {s["id"]: f"step_{n}" for n, s in enumerate(value.get("steps", []))}

    def normalize(node, key=""):
        if isinstance(node, dict):
            return {k: normalize(v, k) for k, v in node.items()}
        if isinstance(node, list):
            return [normalize(v, key) for v in node]
        if key in {"id", "input", "inputs", "step_id", "return_step"} and isinstance(node, str):
            return steps.get(node, node)
        return node

    return normalize(value)


def constants(value, path=""):
    if isinstance(value, dict):
        if value.get("kind") in {"literal", "typed_literal"} and "value" in value:
            yield path + "/value", value["value"]
        for key, child in value.items():
            if key == "fixed_arguments":
                for name, item in child.items():
                    yield (
                        path + "/fixed_arguments/" + name.replace("~", "~0").replace("/", "~1"),
                        item,
                    )
            else:
                yield from constants(child, path + "/" + key.replace("~", "~0").replace("/", "~1"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from constants(child, path + "/" + str(index))


def source_occurrence(value, inputs):
    """Locate a recorded value. Text occurrence does not justify persistent use."""

    def walk(node, path):
        if isinstance(node, dict):
            for key, child in node.items():
                yield from walk(child, path + "/" + key.replace("~", "~0").replace("/", "~1"))
        elif isinstance(node, list):
            for index, child in enumerate(node):
                yield from walk(child, path + "/" + str(index))
        else:
            yield path, node

    roots = [("/" + k, inputs.get(k, {})) for k in ("task", "agent")]
    roots += [
        (f"/tools/{i}/{k}", tool.get(k, {}))
        for i, tool in enumerate(inputs.get("tools", []))
        for k in ("description", "input_schema", "output_schema", "annotations")
    ]
    for root, data in roots:
        for path, observed in walk(data, root):
            exact = type(observed) is type(value) and observed == value
            quoted = (
                isinstance(observed, str)
                and not isinstance(value, (dict, list, bool))
                and (
                    re.search(r"(?<![\w.])" + re.escape(str(value)) + r"(?![\w.])", observed)
                    is not None
                )
            )
            if exact or quoted:
                return {"source": "input", "id": "surface", "path": path}
    return None


def constant_uses(candidate):
    return [
        {"collection": collection, "id": identifier, "path": path, "value": value}
        for collection, definitions in definition_catalog(candidate)["definitions"].items()
        for identifier, definition in definitions.items()
        for path, value in constants(definition)
    ]


def check_definitions(candidate, *, before=None):
    catalog = definition_catalog(candidate)["definitions"]
    previous = definition_catalog(before)["definitions"] if before is not None else {}
    receipts = []
    for collection, definitions in catalog.items():
        seen = {}
        for identifier, definition in definitions.items():
            normalized = canonical_digest(normalized_definition(definition))
            if normalized in seen:
                raise ValueError(
                    f"Duplicate definition: {collection}/{identifier} matches {seen[normalized]}."
                )
            seen[normalized] = identifier
            old = previous.get(collection, {}).get(identifier, {})
            old_constants = {path: val for path, val in constants(old)}
            for path, value in constants(definition):
                if (
                    path in old_constants
                    and type(value) is type(old_constants[path])
                    and value == old_constants[path]
                ):
                    continue
                receipts.append(
                    {
                        "collection": collection,
                        "id": identifier,
                        "path": path,
                        "value": value,
                        "status": "requires_review",
                    }
                )
    return receipts


def proposal_key(candidate, patch, evidence_digest):
    return canonical_digest(
        {
            "candidate": candidate_digest(candidate),
            "changes": sorted(
                [c.model_dump(mode="json") for c in patch.changes], key=canonical_digest
            ),
            "evidence": evidence_digest,
        }
    )
