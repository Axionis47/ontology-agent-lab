"""Check and execute bounded plans against recorded observations."""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StrictStr

from oak.kernel_values import valid_value
from oak.repair_schemas import Candidate

MAX_INTEGER = 9_007_199_254_740_991
MAX_RECORDS = 10_000
MISSING = object()


class RecordedObservation(BaseModel):
    """Host-recorded evidence for one actual tool invocation."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, allow_inf_nan=False)

    id: Annotated[StrictStr, Field(min_length=1, max_length=200)]
    tool_id: Annotated[StrictStr, Field(min_length=1, max_length=200)]
    status: Literal["succeeded", "failed", "unknown"]
    coverage: Literal["complete", "sample", "unknown"]
    data: JsonValue


class IncompleteEvidence(Exception):
    """The observations cannot support the requested result."""


def _data(value):
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else deepcopy(value)


def _scalar(value: Any, kind: str, nullable: bool = False, item_type=None) -> bool:
    return valid_value(value, kind, nullable, item_type)


def _pointer(value: Any, path: str) -> Any:
    if path == "":
        return value
    if not path.startswith("/"):
        raise ValueError("A source path must use JSON Pointer syntax.")
    for encoded in path[1:].split("/"):
        part = encoded.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            value = value.get(part, MISSING)
        elif isinstance(value, list) and (
            part == "0" or (part.isdecimal() and not part.startswith("0"))
        ):
            index = int(part)
            value = value[index] if index < len(value) else MISSING
        else:
            value = MISSING
        if value is MISSING:
            return MISSING
    return value


def _integer(value: Any) -> int:
    if not _scalar(value, "integer"):
        raise IncompleteEvidence("The integer is absent, invalid, or outside the supported range.")
    return value


@dataclass
class RecordSet:
    entity_id: str
    records: list[dict]
    complete: bool
    evidence: list[dict]
    identity: tuple[str, ...]


@dataclass
class PlanType:
    entity_id: str | None
    fields: dict[str, tuple[str, bool]]
    identity: tuple[str, ...]
    constraints: set[str]
    ancestors: set[str]
    scalar: tuple[str, bool] | None = None
    projected: bool = False


def _unique(items, key, label):
    result = {item[key]: item for item in items}
    if len(result) != len(items):
        raise ValueError(f"Duplicate {label} identifiers.")
    return result


def _path(path):
    if (path and not path.startswith("/")) or re.search(r"~(?![01])", path):
        raise ValueError("Invalid JSON Pointer in a source mapping.")


def _expression_type(expression, fields, parameters, depth=1):
    if depth > 6:
        raise ValueError("UNSUPPORTED_PROGRAM: Expression depth exceeds six.")
    kind = expression["kind"]
    if kind in {"field", "argument"}:
        values = fields if kind == "field" else parameters
        if expression["name"] not in values:
            raise ValueError(f"Unknown {kind}: {expression['name']}.")
        return values[expression["name"]]
    if kind == "literal":
        value = expression["value"]
        scalar = {str: "string", int: "integer", bool: "boolean"}.get(type(value))
        if scalar is None or not _scalar(value, scalar):
            raise ValueError("Unsupported literal or integer range.")
        return scalar, False
    if kind in {"add", "multiply"}:
        for side in ("left", "right"):
            if _expression_type(expression[side], fields, parameters, depth + 1)[0] != "integer":
                raise ValueError("Arithmetic operands must be integers.")
        return "integer", False
    raise ValueError("UNSUPPORTED_PROGRAM: Unknown expression.")


def _comparison_type(predicate, fields, parameters):
    left = _expression_type(predicate["left"], fields, parameters)[0]
    right = _expression_type(predicate["right"], fields, parameters)[0]
    if left != right:
        raise ValueError("Comparison operands must have the same type.")
    if predicate["operator"] not in {"eq", "ne"} and left != "integer":
        raise ValueError("Ordered comparisons require integer operands.")


def _compile(function, entities, relations, mappings, constraints):
    parameters = _unique(function["parameters"], "name", "parameter")
    parameters = {name: (p["type"], p["nullable"]) for name, p in parameters.items()}
    _unique(function["steps"], "id", "step")
    if function["entity_id"] not in entities:
        raise ValueError("A function refers to an unknown entity.")
    first = function["steps"][0]
    if first["op"] != "lookup" or first["entity_id"] != function["entity_id"]:
        raise ValueError("A function must start with a lookup of its declared entity.")
    required = set(function["required_constraint_ids"])
    if not required <= constraints.keys():
        raise ValueError("A function requires an unknown constraint.")
    if len(required) != len(function["required_constraint_ids"]):
        raise ValueError("A function repeats a required constraint.")
    plans, predicates, traversals = {}, 0, 0
    for step in function["steps"]:
        op, identifier = step["op"], step["id"]
        if op == "lookup":
            entity = entities.get(step["entity_id"])
            if entity is None or step["entity_id"] not in mappings:
                raise ValueError("Lookup requires a known entity and record mapping.")
            fields = {p["name"]: (p["type"], False) for p in entity["properties"]}
            result = PlanType(entity["id"], fields, tuple(entity["identity_keys"]), set(), set())
        else:
            if step["input"] not in plans:
                raise ValueError("A step input must refer to an earlier step.")
            source = plans[step["input"]]
            if source.scalar is not None:
                raise ValueError("This operator requires a record set.")
            if source.projected and op in {"filter", "traverse"}:
                raise ValueError("Filter and traversal require source records before projection.")
            result = deepcopy(source)
            if op == "traverse":
                traversals += 1
                relation = relations.get(step["relation_id"])
                if relation is None:
                    raise ValueError("Traversal refers to an unknown relation.")
                start, end = ("from", "to") if step["direction"] == "forward" else ("to", "from")
                if relation[start + "_entity"] != source.entity_id:
                    raise ValueError("Traversal starts from the wrong entity.")
                if relation[start + "_property"] not in source.fields:
                    raise ValueError("Traversal needs its source relation property.")
                target = entities[relation[end + "_entity"]]
                if target["id"] not in mappings:
                    raise ValueError("Traversal requires a target record mapping.")
                result.entity_id = target["id"]
                result.fields = {p["name"]: (p["type"], False) for p in target["properties"]}
                result.identity = tuple(target["identity_keys"])
                result.constraints = {
                    identifier
                    for identifier in result.constraints
                    if constraints[identifier]["entity_id"] != target["id"]
                }
            elif op == "filter":
                predicates += len(step["constraint_ids"])
                for constraint_id in step["constraint_ids"]:
                    constraint = constraints.get(constraint_id)
                    if constraint is None or constraint["entity_id"] != source.entity_id:
                        raise ValueError("A filter constraint refers to the wrong entity.")
                    _comparison_type(constraint["predicate"], source.fields, parameters)
                    result.constraints.add(constraint_id)
            elif op == "project":
                result.projected = True
                _unique(step["fields"], "name", "projection")
                result.fields = {
                    p["name"]: _expression_type(p["expression"], source.fields, parameters)
                    for p in step["fields"]
                }
                aliases = {
                    p["expression"]["name"]: p["name"]
                    for p in step["fields"]
                    if p["expression"]["kind"] == "field"
                }
                result.identity = (
                    tuple(aliases[k] for k in source.identity)
                    if all(k in aliases for k in source.identity)
                    else ()
                )
            elif op == "aggregate":
                if step["operation"] != "count":
                    if (
                        _expression_type(step["expression"], source.fields, parameters)[0]
                        != "integer"
                    ):
                        raise ValueError("This aggregate requires an integer expression.")
                result.scalar = ("integer", step["operation"] in {"min", "max"})
                result.fields, result.identity = {}, ()
            elif op == "select_min":
                for expression in step["order_by"]:
                    if _expression_type(expression, source.fields, parameters)[0] not in {
                        "string",
                        "integer",
                    }:
                        raise ValueError("Selection ordering requires strings or integers.")
                tail = step["order_by"][-len(source.identity) :] if source.identity else []
                if not source.identity or [
                    item.get("name") if item["kind"] == "field" else None for item in tail
                ] != list(source.identity):
                    raise ValueError(
                        "Selection ordering must end with the declared identity fields."
                    )
            else:
                raise ValueError("UNSUPPORTED_PROGRAM: Unknown operator.")
        result.ancestors.add(identifier)
        plans[identifier] = result
    if traversals > 4 or predicates > 10:
        raise ValueError("UNSUPPORTED_PROGRAM: Traversal or predicate limit exceeded.")
    result = plans.get(function["return_step"])
    if result is None:
        raise ValueError("A function return step does not exist.")
    if result.ancestors != plans.keys():
        raise ValueError("Every step must contribute to the returned result.")
    if required != result.constraints:
        raise ValueError("Required constraints must match filters on the returned execution path.")
    output = function["output"]
    if output["kind"] == "scalar":
        if result.scalar is None or result.scalar[0] != output["type"]:
            raise ValueError("The scalar output type does not match the plan.")
        if result.scalar[1] and not output["nullable"]:
            raise ValueError("An empty min or max result requires a nullable output.")
    else:
        declared = _unique(output["fields"], "name", "output field")
        if result.scalar is not None or declared.keys() != result.fields.keys():
            raise ValueError("The row output fields do not match the plan.")
        for name, (kind, nullable) in result.fields.items():
            if kind != declared[name]["type"] or (nullable and not declared[name]["nullable"]):
                raise ValueError("The row output type does not match the plan.")


def _validate(candidate, allowed_tool_ids, requirement_ids):
    data = Candidate.model_validate(_data(candidate)).model_dump(mode="json")
    requirements = _unique(data["requirements"]["requirements"], "id", "requirement")
    if not requirements.keys() <= set(requirement_ids):
        raise ValueError("A candidate refers to an unknown original requirement.")
    entities = _unique(data["schema"]["entities"], "id", "entity")
    relations = _unique(data["schema"]["relations"], "id", "relation")
    bindings = _unique(data["schema"]["bindings"], "id", "binding")
    _unique(data["schema"]["operations"], "id", "operation")
    constraints = _unique(data["constraints"], "id", "constraint")
    functions = _unique(data["functions"], "id", "function")
    allowed = set(map(str, allowed_tool_ids))
    for requirement in requirements.values():
        if not set(requirement["tool_ids"]) <= allowed:
            raise ValueError("A requirement refers to an ungranted tool.")
    for entity in entities.values():
        properties = _unique(entity["properties"], "name", "property")
        keys = entity["identity_keys"]
        if (
            not 1 <= len(keys) <= 3
            or len(keys) != len(set(keys))
            or not set(keys) <= properties.keys()
        ):
            raise ValueError("An entity requires one through three distinct identity properties.")
        if any(properties[key]["type"] not in {"string", "integer", "boolean"} for key in keys):
            raise ValueError("Identity properties must have supported scalar types.")
    for item in [
        *entities.values(),
        *relations.values(),
        *constraints.values(),
        *data["schema"]["operations"],
    ]:
        if not set(item["requirement_ids"]) <= requirements.keys():
            raise ValueError("A declaration refers to an unknown requirement.")
    for binding in bindings.values():
        entity = entities.get(binding["entity_id"])
        if entity is None or binding["property"] not in {p["name"] for p in entity["properties"]}:
            raise ValueError("A binding refers to an unknown entity property.")
        if binding["tool_id"] not in allowed:
            raise ValueError("A binding refers to an ungranted tool.")
    for operation in data["schema"]["operations"]:
        if operation["tool_id"] not in allowed:
            raise ValueError("An operation refers to an ungranted tool.")
    for relation in relations.values():
        types = []
        for end in ("from", "to"):
            entity = entities.get(relation[end + "_entity"])
            properties = {p["name"]: p["type"] for p in entity["properties"]} if entity else {}
            if relation[end + "_property"] not in properties:
                raise ValueError("A relation refers to an unknown entity property.")
            types.append(properties[relation[end + "_property"]])
        if types[0] != types[1] or types[0] not in {"string", "integer", "boolean"}:
            raise ValueError("Relation endpoints require the same scalar type.")
        if not set(relation["binding_ids"]) <= bindings.keys():
            raise ValueError("A relation refers to an unknown source binding.")
        bound = {
            (bindings[identifier]["entity_id"], bindings[identifier]["property"])
            for identifier in relation["binding_ids"]
        }
        if any(
            (relation[end + "_entity"], relation[end + "_property"]) not in bound
            for end in ("from", "to")
        ):
            raise ValueError("A relation requires a binding for each endpoint property.")
    mappings = {}
    _unique(data["mappings"], "id", "mapping")
    for mapping in data["mappings"]:
        entity = entities.get(mapping["entity_id"])
        if entity is None or mapping["tool_id"] not in allowed:
            raise ValueError("A record mapping needs a known entity and granted tool.")
        fields = _unique(mapping["fields"], "property", "mapped property")
        if not fields.keys() <= {p["name"] for p in entity["properties"]}:
            raise ValueError("A record mapping refers to an unknown entity property.")
        if not set(entity["identity_keys"]) <= fields.keys():
            raise ValueError("A record mapping must supply each identity property.")
        if any(p["type"] not in {"string", "integer", "boolean"} for p in entity["properties"]):
            raise ValueError("UNSUPPORTED_PROGRAM: Mapped properties require scalar types.")
        _path(mapping["collection_path"])
        for field in mapping["fields"]:
            _path(field["path"])
        mappings.setdefault(entity["id"], []).append(mapping)
    for constraint in constraints.values():
        if constraint["entity_id"] not in entities:
            raise ValueError("A constraint refers to an unknown entity.")
    used = set()
    for function in functions.values():
        _compile(function, entities, relations, mappings, constraints)
        used.update(function["required_constraint_ids"])
    if constraints.keys() - used:
        raise ValueError("Every constraint must be required by an executable function.")
    return data, entities, relations, mappings, constraints, functions


def validate_candidate(candidate, allowed_tool_ids, requirement_ids) -> list[str]:
    """Return declaration errors without executing a function."""
    try:
        if _data(candidate).get("version") in {"oak.candidate.v2", "oak.candidate.v3"}:
            from oak.kernel_execution import validate_v2

            validate_v2(candidate, allowed_tool_ids, requirement_ids)
            return []
        _validate(candidate, allowed_tool_ids, requirement_ids)
    except (ValueError, TypeError, KeyError, RecursionError) as error:
        return [str(error)]
    return []


def _evaluate(expression, record, arguments):
    kind = expression["kind"]
    if kind == "field":
        value = record.get(expression["name"], MISSING)
    elif kind == "argument":
        value = arguments[expression["name"]]
    elif kind == "literal":
        value = expression["value"]
    else:
        left = _integer(_evaluate(expression["left"], record, arguments))
        right = _integer(_evaluate(expression["right"], record, arguments))
        value = left + right if kind == "add" else left * right
        return _integer(value)
    if value is MISSING:
        raise IncompleteEvidence(f"An expression refers to a missing field: {expression['name']}.")
    return value


def _predicate(predicate, record, arguments):
    left = _evaluate(predicate["left"], record, arguments)
    right = _evaluate(predicate["right"], record, arguments)
    if left is None or right is None:
        raise IncompleteEvidence("A comparison operand is null.")
    operator = predicate["operator"]
    if operator == "eq":
        return left == right
    if operator == "ne":
        return left != right
    if operator == "lt":
        return left < right
    if operator == "le":
        return left <= right
    if operator == "gt":
        return left > right
    return left >= right


def _collection(entity_id, entities, mappings, observations):
    choices, entity = mappings[entity_id], entities[entity_id]
    if len(choices) != 1:
        raise IncompleteEvidence("Multiple source mappings require an evidence graph.")
    mapping = choices[0]
    sources = [o for o in observations if o.get("tool_id") == mapping["tool_id"]]
    if len(sources) != 1:
        raise IncompleteEvidence("Select exactly one recorded observation for each mapped tool.")
    observation = sources[0]
    if observation.get("status") != "succeeded":
        raise IncompleteEvidence("The required observation did not succeed.")
    rows = _pointer(observation.get("data", MISSING), mapping["collection_path"])
    if rows is MISSING:
        raise IncompleteEvidence("The source collection is missing.")
    if not isinstance(rows, list) or len(rows) > MAX_RECORDS:
        raise IncompleteEvidence("The source collection is invalid or exceeds the record limit.")
    records, identities = [], set()
    types = {p["name"]: p["type"] for p in entity["properties"]}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise IncompleteEvidence("A source record must be an object.")
        record = {}
        for field in mapping["fields"]:
            value = _pointer(row, field["path"])
            name = field["property"]
            if value is MISSING:
                raise IncompleteEvidence(f"Record {index}: property {name} is missing.")
            if value is None:
                raise IncompleteEvidence(f"Record {index}: property {name} is null.")
            if not _scalar(value, types[name]):
                raise IncompleteEvidence(
                    f"Record {index}: property {name} has an invalid type or range."
                )
            record[name] = value
        key = tuple(record[k] for k in entity["identity_keys"])
        if key in identities:
            raise IncompleteEvidence("Source records have duplicate or conflicting identities.")
        identities.add(key)
        records.append(record)
    return RecordSet(
        entity_id,
        records,
        observation.get("coverage") == "complete",
        [{"observation_id": observation["id"], "path": mapping["collection_path"]}],
        tuple(entity["identity_keys"]),
    )


def _keys(source):
    return (
        [[row[key] for key in source.identity] for row in source.records] if source.identity else []
    )


def execute_function(
    candidate,
    function_id,
    arguments,
    observations,
    *,
    _collection_loader=None,
    _allow_partial_rows=False,
) -> dict:
    """Execute one checked plan. This function has no external call path."""
    raw = Candidate.model_validate(_data(candidate)).model_dump(mode="json")
    tools = {m["tool_id"] for m in raw["mappings"]}
    tools.update(b["tool_id"] for b in raw["schema"]["bindings"])
    tools.update(o["tool_id"] for o in raw["schema"]["operations"])
    tools.update(t for r in raw["requirements"]["requirements"] for t in r["tool_ids"])
    _, entities, relations, mappings, constraints, functions = _validate(
        raw,
        tools,
        {r["id"] for r in raw["requirements"]["requirements"]},
    )
    if function_id not in functions:
        raise ValueError("Unknown function.")
    function = functions[function_id]
    parameters = {p["name"]: p for p in function["parameters"]}
    if not isinstance(arguments, dict) or arguments.keys() != parameters.keys():
        raise ValueError("Function arguments must match the declared parameters.")
    for name, parameter in parameters.items():
        if not _scalar(arguments[name], parameter["type"], parameter["nullable"]):
            raise ValueError(f"Invalid function argument: {name}.")
    if not isinstance(observations, list):
        raise ValueError("Observations must be a list of recorded objects.")
    observations = [
        RecordedObservation.model_validate(_data(o)).model_dump(mode="json") for o in observations
    ]
    _unique(observations, "id", "observation")
    values, trace, evidence = {}, [], []

    def collect(entity_id):
        if _collection_loader is not None:
            return _collection_loader(entity_id)
        return _collection(entity_id, entities, mappings, observations)

    try:
        for step in function["steps"]:
            op = step["op"]
            if op == "lookup":
                result = collect(step["entity_id"])
                event = {"step_id": step["id"], "operator": op}
            else:
                source = values[step["input"]]
                result = deepcopy(source)
                event = {"step_id": step["id"], "operator": op, "input_ids": _keys(source)}
                if op == "filter":
                    result.records = [
                        r
                        for r in source.records
                        if all(
                            _predicate(constraints[c]["predicate"], r, arguments)
                            for c in step["constraint_ids"]
                        )
                    ]
                    event["constraint_ids"] = step["constraint_ids"]
                    event["excluded_ids"] = [
                        [r[k] for k in source.identity]
                        for r in source.records
                        if r not in result.records
                    ]
                elif op == "project":
                    result.records = [
                        {
                            p["name"]: _evaluate(p["expression"], r, arguments)
                            for p in step["fields"]
                        }
                        for r in source.records
                    ]
                    aliases = {
                        p["expression"]["name"]: p["name"]
                        for p in step["fields"]
                        if p["expression"]["kind"] == "field"
                    }
                    result.identity = (
                        tuple(aliases[k] for k in source.identity)
                        if all(k in aliases for k in source.identity)
                        else ()
                    )
                elif op == "traverse":
                    relation = relations[step["relation_id"]]
                    start, end = (
                        ("from", "to") if step["direction"] == "forward" else ("to", "from")
                    )
                    target = collect(relation[end + "_entity"])
                    selected = []
                    for record in source.records:
                        if relation[start + "_property"] not in record or any(
                            relation[end + "_property"] not in row for row in target.records
                        ):
                            raise IncompleteEvidence("A relation endpoint is missing.")
                        matches = [
                            r
                            for r in target.records
                            if r[relation[end + "_property"]]
                            == record[relation[start + "_property"]]
                        ]
                        if not matches:
                            raise IncompleteEvidence("A declared relation has no observed target.")
                        selected.extend(r for r in matches if r not in selected)
                    target.records = selected
                    target.complete = source.complete and target.complete
                    target.evidence = source.evidence + target.evidence
                    result = target
                elif op in {"aggregate", "select_min"}:
                    if not source.complete:
                        raise IncompleteEvidence(
                            "This operation requires complete collection coverage."
                        )
                    if op == "select_min":
                        ordering = []
                        for record in source.records:
                            key = tuple(_evaluate(e, record, arguments) for e in step["order_by"])
                            if any(value is None for value in key):
                                raise IncompleteEvidence("A selection ordering value is null.")
                            ordering.append((key, record))
                        if len({key for key, _ in ordering}) != len(ordering):
                            raise IncompleteEvidence("Selection ordering does not resolve a tie.")
                        result.records = (
                            [min(ordering, key=lambda item: item[0])[1]] if ordering else []
                        )
                    elif step["operation"] == "count":
                        result = len(source.records)
                    else:
                        operands = [
                            _integer(_evaluate(step["expression"], r, arguments))
                            for r in source.records
                        ]
                        operation = step["operation"]
                        if operation == "sum":
                            result = 0
                            for operand in operands:
                                result = _integer(result + operand)
                        else:
                            result = (
                                (min(operands) if operation == "min" else max(operands))
                                if operands
                                else None
                            )
                    evidence.extend(source.evidence)
            if isinstance(result, RecordSet):
                event.update(
                    output_ids=_keys(result),
                    output_count=len(result.records),
                    complete=result.complete,
                )
                evidence.extend(result.evidence)
            else:
                event["value"] = result
            trace.append(event)
            values[step["id"]] = result
        result = values[function["return_step"]]
        if isinstance(result, RecordSet):
            if not result.complete and not _allow_partial_rows:
                raise IncompleteEvidence(
                    "The returned records have incomplete collection coverage."
                )
            result = result.records
        output = function["output"]
        if output["kind"] == "rows":
            if any(
                not _scalar(row.get(field["name"], MISSING), field["type"], field["nullable"])
                for row in result
                for field in output["fields"]
            ):
                raise IncompleteEvidence("A returned property is absent, null, or invalid.")
        elif not _scalar(result, output["type"], output["nullable"]):
            raise IncompleteEvidence("The scalar result does not match its output type.")
        return {
            "status": "complete",
            "value": result,
            "issues": [],
            "trace": trace,
            "evidence_refs": evidence,
        }
    except IncompleteEvidence as error:
        return {
            "status": "incomplete",
            "value": None,
            "issues": [str(error)],
            "trace": trace,
            "evidence_refs": evidence,
        }
