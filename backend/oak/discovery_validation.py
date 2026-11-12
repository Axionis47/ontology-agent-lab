"""Validate evidence references without treating proposals as observations."""

import hashlib
import json
import re

from jsonschema import validators
from referencing import Registry

from oak.discovery_schemas import EvidenceRef, RequirementsProposal, SchemaProposal

SECRET_KEYS = re.compile(r"password|secret|token|authorization|cookie|api.?key", re.I)


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
        allow_nan=False,
    )


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def write_arguments(value):
    """Compare write parameters without treating credential refresh as a new operation."""
    if isinstance(value, dict):
        return {
            key: "[credential]" if SECRET_KEYS.search(key) else write_arguments(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [write_arguments(item) for item in value]
    return value


def redact(value, preserve_schemas=False):
    if isinstance(value, dict):
        return {
            key: item
            if preserve_schemas and key in ("input_schema", "output_schema")
            else item
            if isinstance(item, str) and item.startswith("oak-secret:")
            else "[redacted]"
            if SECRET_KEYS.search(key)
            else redact(item, preserve_schemas)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item, preserve_schemas) for item in value]
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
            if isinstance(decoded, (dict, list)):
                return canonical(redact(decoded))
        except (ValueError, TypeError):
            pass
        value = re.sub(r"(?i)Bearer\s+[^\s\"']+", "Bearer [redacted]", value)
        return re.sub(
            r"(?i)((?:password|secret|token|api_key)\s*[=:]\s*)[^\s,;]+", r"\1[redacted]", value
        )
    return value


def pointer(value, path, allow_credentials=False):
    if path == "":
        return value
    if not path.startswith("/"):
        raise ValueError("Evidence paths must use JSON Pointer syntax.")
    for part in path[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        try:
            value = value[int(part)] if isinstance(value, list) else value[part]
        except (ValueError, TypeError, KeyError, IndexError):
            raise ValueError(f"Evidence path does not exist: {path}") from None
    if value == "[redacted]" or (
        not allow_credentials and isinstance(value, str) and value.startswith("oak-secret:")
    ):
        raise ValueError("A redacted field cannot support a proposal.")
    return value


def validate_json(value, schema):
    cls = validators.validator_for(schema)
    cls.check_schema(schema)
    # An unresolved reference must not trigger a network request.
    validator = cls(schema, registry=Registry())
    errors = list(validator.iter_errors(value))
    if errors:
        raise ValueError("The value does not match its declared JSON Schema.")


def references(value):
    if isinstance(value, dict):
        if set(value) == {"source", "id", "path"}:
            yield EvidenceRef.model_validate(value)
        else:
            for item in value.values():
                yield from references(item)
    elif isinstance(value, list):
        for item in value:
            yield from references(item)


def check_references(value, inputs, artifacts, questions, allow_credentials=False):
    for ref in references(value):
        if ref.source == "input" and ref.id == "surface":
            source = inputs
        elif ref.source == "artifact" and ref.id in artifacts:
            source = artifacts[ref.id]["payload"]
        elif ref.source == "question" and ref.id in questions and questions[ref.id]["answer"]:
            source = questions[ref.id]
        else:
            raise ValueError("An evidence reference is absent or has no submitted answer.")
        pointer(source, ref.path, allow_credentials=allow_credentials)


def package_errors(requirements, schema, inputs, artifacts, questions, tools):
    errors = []
    try:
        r = RequirementsProposal.model_validate(requirements)
        s = SchemaProposal.model_validate(schema)
        check_references(requirements, inputs, artifacts, questions)
        check_references(schema, inputs, artifacts, questions)
        reqs = {item.id for item in r.requirements}
        if len(reqs) != len(r.requirements):
            errors.append("Requirement IDs must be unique.")
        entities = {item.id: item for item in s.entities}
        bindings = {item.id: item for item in s.bindings}
        for items in (s.entities, s.bindings, s.relations, s.operations):
            if len({item.id for item in items}) != len(items):
                errors.append("Artifact item IDs must be unique.")
        covered = {
            ref.path for item in r.requirements for ref in item.evidence if ref.source == "input"
        }
        covered |= {ref.path for gap in r.gaps for ref in gap.evidence if ref.source == "input"}
        for path in inputs["source_sections"]:
            if path not in covered:
                errors.append(f"Original scope section has no requirement or gap reference: {path}")
        for item in r.requirements:
            if any(tool not in tools for tool in item.tool_ids):
                errors.append(f"Requirement {item.id} refers to an ungranted tool.")
        for entity in s.entities:
            names = {p.name for p in entity.properties}
            if len(names) != len(entity.properties) or not set(entity.identity_keys) <= names:
                errors.append(f"Entity {entity.id} has invalid property or identity declarations.")
            if not set(entity.requirement_ids) <= reqs:
                errors.append(f"Entity {entity.id} has an unknown requirement.")
        for binding in s.bindings:
            entity = entities.get(binding.entity_id)
            if (
                binding.tool_id not in tools
                or not entity
                or binding.property not in {p.name for p in entity.properties}
            ):
                errors.append(f"Binding {binding.id} has an unknown tool, entity, or property.")
                continue
            source = artifacts.get(binding.source.id)
            if binding.source.source != "artifact" or not source:
                errors.append(f"Binding {binding.id} requires a tool contract or observation.")
                continue
            payload = source["payload"]
            if binding.support == "observed":
                if (
                    source["kind"] != "observation"
                    or payload.get("tool_id") != binding.tool_id
                    or payload.get("validation") != "valid"
                    or not binding.source.path.startswith("/data/")
                ):
                    errors.append(
                        f"Binding {binding.id} does not reference a validated tool response field."
                    )
            elif source["kind"] != "catalog":
                errors.append(f"Binding {binding.id} requires a declared output schema.")
            else:
                matching = [
                    f"/tools/{i}/output_schema/"
                    for i, tool in enumerate(payload["tools"])
                    if tool["id"] == binding.tool_id
                ]
                if not any(binding.source.path.startswith(path) for path in matching):
                    errors.append(
                        f"Binding {binding.id} does not reference its tool output schema."
                    )
        for relation in s.relations:
            left, right = entities.get(relation.from_entity), entities.get(relation.to_entity)
            if (
                not left
                or not right
                or relation.from_property not in {p.name for p in left.properties}
                or relation.to_property not in {p.name for p in right.properties}
            ):
                errors.append(f"Relation {relation.id} refers to an unknown entity property.")
            if (
                not set(relation.requirement_ids) <= reqs
                or not set(relation.binding_ids) <= bindings.keys()
            ):
                errors.append(
                    f"Relation {relation.id} has missing requirement or binding references."
                )
            else:
                fields = {
                    (bindings[b].entity_id, bindings[b].property) for b in relation.binding_ids
                }
                if (
                    not {
                        (relation.from_entity, relation.from_property),
                        (relation.to_entity, relation.to_property),
                    }
                    <= fields
                ):
                    errors.append(
                        f"Relation {relation.id} lacks bindings for both relation fields."
                    )
        for operation in s.operations:
            if (
                operation.tool_id not in tools
                or (operation.confirmation_tool_id and operation.confirmation_tool_id not in tools)
                or not set(operation.requirement_ids) <= reqs
            ):
                errors.append(f"Operation {operation.id} has an unknown tool or requirement.")
    except (ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc)[:500])
    return errors
