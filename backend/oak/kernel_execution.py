"""Compile and execute versioned, bounded plans over observed facts."""

import json
import re
import unicodedata
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field
from fractions import Fraction

from oak.kernel_values import MAX_INTEGER, json_value, normalize, numeric, valid_value
from oak.repair_schemas import Candidate

MAX_VISITED = 10_000


@dataclass(frozen=True)
class ValueType:
    type: str
    unit: str | None = None
    item_type: str | None = None
    nullable: bool = False


def _declared_type(spec):
    kind, item = spec.type, getattr(spec, "item_type", None)
    if kind not in {"string", "integer", "boolean", "decimal", "array"}:
        raise ValueError("Unsupported value type.")
    if (kind == "array") != (item in {"string", "integer", "boolean", "decimal"}):
        raise ValueError("Only a collection requires a scalar element type.")
    if spec.unit and (item if kind == "array" else kind) not in {"integer", "decimal"}:
        raise ValueError("Only numeric values can have units.")
    unit_signature(spec.unit)
    return ValueType(kind, spec.unit, item, getattr(spec, "nullable", False))


def _compatible(left, right):
    return (
        (left.type == right.type or {left.type, right.type} <= {"integer", "decimal"})
        and left.item_type == right.item_type
        and unit_signature(left.unit) == unit_signature(right.unit)
    )


def _common_fields(entities, types):
    fields = None
    for identifier in sorted(types):
        current = {p.name: _declared_type(p) for p in entities[identifier].properties}
        fields = (
            current
            if fields is None
            else {
                name: value
                for name, value in fields.items()
                if name in current and value == current[name]
            }
        )
    return fields or {}


def _expanded_expression(expression, state, parameters, requests, states, depth=0):
    if depth > 6:
        raise ValueError("Expression depth exceeds six.")
    kind = expression.kind
    if kind in {"field", "argument", "request"}:
        source = {"field": state["fields"], "argument": parameters, "request": requests}[kind]
        if expression.name not in source:
            raise ValueError(f"Unknown or incompatible {kind}: {expression.name}.")
        return source[expression.name]
    if kind == "result":
        previous = states.get(expression.step_id)
        if previous is None or previous["kind"] not in {"scalar", "group"}:
            raise ValueError("A result reference requires an earlier scalar or selected group.")
        if expression.field not in previous["fields"]:
            raise ValueError("Unknown result field.")
        state["ancestors"].update(previous["ancestors"])
        return previous["fields"][expression.field]
    if kind == "literal":
        spec = ValueType(
            {str: "string", int: "integer", bool: "boolean"}[type(expression.value)],
            expression.unit,
        )
        _declared_type(spec)
        normalize(expression.value, spec)
        return spec
    if kind == "typed_literal":
        spec = _declared_type(expression)
        normalize(expression.value, spec)
        return spec
    if kind == "convert":
        source = _expanded_expression(
            expression.value, state, parameters, requests, states, depth + 1
        )
        if source.type not in {"integer", "decimal"}:
            raise ValueError("Conversion requires a numeric value.")
        conversion(unit_signature(source.unit), unit_signature(expression.unit))
        return ValueType(source.type, expression.unit, nullable=source.nullable)
    left = _expanded_expression(expression.left, state, parameters, requests, states, depth + 1)
    right = _expanded_expression(expression.right, state, parameters, requests, states, depth + 1)
    if left.type not in {"integer", "decimal"} or right.type not in {"integer", "decimal"}:
        raise ValueError("Arithmetic requires numeric operands.")
    if kind == "add" and unit_signature(left.unit) != unit_signature(right.unit):
        raise ValueError("Addition requires identical units.")
    unit = (
        left.unit
        if kind == "add"
        else _signature_unit(_product(unit_signature(left.unit), unit_signature(right.unit)))
    )
    return ValueType(
        "decimal" if "decimal" in {left.type, right.type} else "integer",
        unit,
        nullable=left.nullable or right.nullable,
    )


def _signature_unit(signature):
    top = [name for name, count in signature.items() for _ in range(max(count, 0))]
    bottom = [name for name, count in signature.items() for _ in range(max(-count, 0))]
    if bottom and not top:
        raise ValueError("A unit requires a numerator.")
    return "*".join(top) + ("/" + "*".join(bottom) if bottom else "") or None


def _context_expressions(candidate, entity_id, expressions, evaluate):
    scopes = {
        s.name
        for mapping in candidate.mappings
        if mapping.entity_id == entity_id
        for s in mapping.scope
    }
    if set(expressions) != scopes:
        raise ValueError("An entity operation must bind its declared evidence context.")
    for expression in expressions.values():
        if evaluate(expression).type not in {"string", "integer", "boolean"}:
            raise ValueError("Evidence context values must be scalar.")


def _reachable_types(types, relations, identifiers, direction, hops, include_start):
    visited, frontier = set(types) if include_start else set(), set(types)
    for _ in range(hops):
        targets = set()
        for identifier in identifiers:
            relation = relations.get(identifier)
            if relation is None:
                raise ValueError("Unknown relation.")
            if direction in {"forward", "outgoing", "both"} and relation.from_entity in frontier:
                targets.add(relation.to_entity)
            if direction in {"reverse", "incoming", "both"} and relation.to_entity in frontier:
                targets.add(relation.from_entity)
        visited.update(targets)
        frontier = targets
    return visited


def _compile_predicate(predicate, state, evaluate, candidate, entities, relations):
    if predicate.operator == "connected":
        if state["kind"] != "entities":
            raise ValueError("Connectivity needs observed entities.")
        targets = _reachable_types(
            state["types"],
            relations,
            predicate.relation_ids,
            predicate.direction,
            predicate.max_hops,
            False,
        )
        if not targets:
            raise ValueError("The relation cannot start at this entity type.")
        original_fields = state["fields"]
        state["fields"] = _common_fields(
            entities,
            _reachable_types(
                state["types"],
                relations,
                predicate.relation_ids,
                predicate.direction,
                predicate.max_hops - 1,
                True,
            ),
        )
        for target in targets:
            _context_expressions(candidate, target, predicate.contexts.get(target, {}), evaluate)
        state["fields"] = original_fields
        if predicate.contexts.keys() - targets:
            raise ValueError("Connectivity context names an unreachable entity type.")
        for anchor in predicate.anchors:
            if anchor.entity_id not in targets:
                raise ValueError("The relation cannot reach this anchor type.")
            properties = {p.name: _declared_type(p) for p in entities[anchor.entity_id].properties}
            if set(anchor.identity) != set(entities[anchor.entity_id].identity_keys):
                raise ValueError("An anchor requires its complete identity.")
            for name, expression in anchor.identity.items():
                actual = evaluate(expression)
                if properties[name].type != actual.type or not _compatible(
                    properties[name], actual
                ):
                    raise ValueError("Anchor identity type differs.")
            _context_expressions(candidate, anchor.entity_id, anchor.context, evaluate)
        return
    left, right = evaluate(predicate.left), evaluate(predicate.right)
    if predicate.operator in {"in", "not_in", "overlap_any", "overlap_all", "overlap_min"}:
        element = left.item_type if predicate.operator.startswith("overlap_") else left.type
        if (
            right.type != "array"
            or right.item_type != element
            or (predicate.operator.startswith("overlap_") and left.type != "array")
            or unit_signature(left.unit) != unit_signature(right.unit)
        ):
            raise ValueError("Set predicates require matching element types and units.")
        if (predicate.operator == "overlap_min") != (predicate.minimum is not None):
            raise ValueError("Only minimum-overlap requires a minimum expression.")
        if predicate.minimum is not None and evaluate(predicate.minimum) != ValueType("integer"):
            raise ValueError("An overlap minimum must be a dimensionless integer.")
    elif not _compatible(left, right) or (
        predicate.operator not in {"eq", "ne"} and left.type not in {"integer", "decimal"}
    ):
        raise ValueError("Comparison requires compatible types and units.")


def _compile_expanded(candidate, function):
    entities = {e.id: e for e in candidate.schema.entities}
    relations = {r.id: r for r in candidate.schema.relations}
    constraints = {c.id: c for c in candidate.constraints}
    parameters = {
        p.name: _declared_type(p)
        for p in _unique(function.parameters, "name", "parameter").values()
    }
    requests = {p.name: _declared_type(p) for p in candidate.request_fields}
    _unique(function.steps, "id", "step")
    if function.steps[0].op not in {"lookup", "input"}:
        raise ValueError("A function starts with input or lookup.")
    states, required = {}, set()
    check = function.output.kind == "decision"
    for step in function.steps:
        state = {
            "kind": "rows",
            "types": set(),
            "fields": {},
            "ancestors": {step.id},
            "role": "input",
            "reduced": False,
        }
        if step.op not in {"lookup", "input", "decision"}:
            if step.input not in states or states[step.input]["kind"] in {"assert", "decision"}:
                raise ValueError("An operator needs an earlier data input.")
            state = deepcopy(states[step.input])
            state["ancestors"].add(step.id)

        def evaluate(expression):
            return _expanded_expression(expression, state, parameters, requests, states)

        if step.op == "input":
            pass
        elif step.op == "lookup":
            types = set(step.entity_types or ([step.entity_id] if step.entity_id else entities))
            if not types or not types <= entities.keys() or step.entity_id and step.entity_types:
                raise ValueError("Invalid lookup entity types.")
            state.update(
                kind="entities",
                types=types,
                fields=_common_fields(entities, types),
                role="population",
            )

            def evaluate(expression):
                root_state = {**state, "fields": {}}
                return _expanded_expression(expression, root_state, parameters, requests, states)

            for identifier in types:
                entity = entities[identifier]
                _context_expressions(
                    candidate, identifier, step.contexts.get(identifier, step.context), evaluate
                )
                if not set(step.identity) <= set(entity.identity_keys):
                    raise ValueError("Lookup uses undeclared identity fields.")
            if set(step.contexts) - types:
                raise ValueError("Lookup context names an unselected entity type.")
            for name, expression in {**step.identity, **step.property_filters}.items():
                if name not in state["fields"] or not _compatible(
                    state["fields"][name], evaluate(expression)
                ):
                    raise ValueError(
                        "Lookup property type differs or needs an entity-type selection."
                    )
            for name, expression in step.identity.items():
                if state["fields"][name].type != evaluate(expression).type:
                    raise ValueError("Lookup identity types must match exactly.")
            if step.identifiers is not None and evaluate(step.identifiers) != ValueType(
                "array", item_type="string"
            ):
                raise ValueError("Lookup identifiers require a string collection.")
            for query, fields in (
                (step.name_query, step.name_fields),
                (step.text_query, step.text_fields),
            ):
                if query is not None:
                    if (
                        evaluate(query) != ValueType("string")
                        or not fields
                        or any(state["fields"].get(name) != ValueType("string") for name in fields)
                    ):
                        raise ValueError(
                            "Text lookup requires declared string fields and a string query."
                        )
            if not 0 <= numeric(step.min_score) <= 1:
                raise ValueError("The minimum score must be between zero and one.")
            if check and not step.population:
                if len(types) != 1 or set(step.identity) != set(
                    entities[next(iter(types))].identity_keys
                ):
                    raise ValueError("A subject check requires an exact identity.")
                if any(e.kind not in {"argument", "request"} for e in step.identity.values()):
                    raise ValueError("A subject identity must bind the action or original request.")
                if (
                    step.property_filters
                    or step.identifiers
                    or step.name_query
                    or step.text_query
                    or step.top_k
                ):
                    raise ValueError("A subject check cannot filter or rank its subject.")
                state["role"] = "subject"
        elif step.op == "traverse":
            if state["kind"] != "entities":
                raise ValueError("Traversal requires observed entities.")
            identifiers = step.relation_ids or (
                [step.relation_id] if step.relation_id else list(relations)
            )
            if step.relation_id and step.relation_ids:
                raise ValueError("Use one relation selector.")
            targets = _reachable_types(
                state["types"], relations, identifiers, step.direction, step.max_hops, False
            )
            state["fields"] = _common_fields(
                entities,
                _reachable_types(
                    state["types"], relations, identifiers, step.direction, step.max_hops - 1, True
                ),
            )
            for target in targets:
                _context_expressions(
                    candidate, target, step.contexts.get(target, step.context), evaluate
                )
            if step.contexts.keys() - targets:
                raise ValueError("Traversal context names an unreachable entity type.")
            types = targets | (
                state["types"] if step.include_starting_entities is not False else set()
            )
            if not types:
                raise ValueError("Traversal cannot reach a declared entity type.")
            state.update(types=types, fields=_common_fields(entities, types))
        elif step.op == "select_types":
            if state["kind"] != "entities" or not set(step.entity_types) <= state["types"]:
                raise ValueError("Type selection requires types in the input entity set.")
            if check and state["role"] == "subject":
                raise ValueError("A subject assertion cannot discard an entity type.")
            state.update(
                types=set(step.entity_types), fields=_common_fields(entities, step.entity_types)
            )
        elif step.op in {"filter", "assert"}:
            if step.op == "filter" and (
                state["kind"] == "scalar" or check and state["role"] != "population"
            ):
                raise ValueError("Filters cannot remove a checked subject.")
            if (
                step.op == "assert"
                and check
                and state["role"] == "population"
                and state["kind"] not in {"scalar", "group"}
            ):
                raise ValueError("Population checks require an aggregate assertion.")
            for cid in step.constraint_ids:
                condition = constraints.get(cid)
                if (
                    condition is None
                    or condition.entity_id is not None
                    and state["types"] != {condition.entity_id}
                ):
                    raise ValueError("Condition uses the wrong entity type.")
                _compile_predicate(
                    condition.predicate, state, evaluate, candidate, entities, relations
                )
                if step.op == "assert" or not check:
                    required.add(cid)
            if step.op == "assert":
                state["kind"] = "assert"
        elif step.op == "project":
            if state["kind"] not in {"entities", "rows", "group"}:
                raise ValueError("Projection requires rows or entities.")
            projected = {}
            for projection in step.fields:
                spec = evaluate(projection.expression)
                if projection.name in projected:
                    raise ValueError("Duplicate projected field.")
                if projection.missing_value is not None and not _compatible(
                    spec, evaluate(projection.missing_value)
                ):
                    raise ValueError("Projection fallback type or unit differs.")
                projected[projection.name] = ValueType(
                    spec.type, spec.unit, spec.item_type, spec.nullable or projection.nullable
                )
            state.update(
                kind="rows",
                fields=projected,
                grouped=state.get("grouped", False)
                and any(
                    p.name == "group"
                    and p.expression.kind == "field"
                    and p.expression.name == "group"
                    for p in step.fields
                ),
            )
        elif step.op == "aggregate":
            if state["kind"] not in {"entities", "rows"} or check and state["role"] != "population":
                raise ValueError("Aggregation requires a population input.")
            operand = evaluate(step.expression) if step.expression else ValueType("integer")
            if operand.type not in {"integer", "decimal"}:
                raise ValueError("Aggregation requires numeric operands.")
            result = ValueType(
                "integer"
                if step.operation == "count"
                else "decimal"
                if step.operation == "average"
                else operand.type,
                None if step.operation == "count" else operand.unit,
                nullable=step.operation in {"min", "max", "average"},
            )
            group = state["fields"].get(step.group_by) if step.group_by else None
            if step.group_by and (group is None or group.type == "array"):
                raise ValueError("Grouping requires a declared scalar field.")
            state.update(
                kind="rows" if group else "scalar",
                types=set(),
                fields={"value": result},
                reduced=True,
            )
            if group:
                state["fields"]["group"] = group
                state["grouped"] = True
        elif step.op == "select_group":
            if (
                not state.get("grouped")
                or "group" not in state["fields"]
                or not _compatible(state["fields"]["group"], evaluate(step.key))
            ):
                raise ValueError("Group selection requires a matching scalar key.")
            if check and step.key.kind not in {"argument", "request"}:
                raise ValueError("A checked group must bind the action or original request.")
            state["kind"] = "group"
        elif step.op == "select_min":
            if check or state["kind"] not in {"entities", "rows"}:
                raise ValueError("Selection cannot remove checked subjects.")
            for expression in step.order_by:
                if evaluate(expression).type == "array":
                    raise ValueError("Ordering requires scalar values.")
        elif step.op == "decision":
            if not check or any(
                identifier not in states or states[identifier]["kind"] != "assert"
                for identifier in step.inputs
            ):
                raise ValueError("A decision requires earlier assertions.")
            state["kind"] = "decision"
            for identifier in step.inputs:
                state["ancestors"].update(states[identifier]["ancestors"])
        else:
            raise ValueError("Unsupported operator.")
        states[step.id] = state
    returned = states.get(function.return_step)
    if returned is None or returned["ancestors"] != set(states):
        raise ValueError("Every step must contribute to the returned result.")
    if set(function.required_constraint_ids) != required or check and not required:
        raise ValueError(
            "Required conditions must match executed assertions or computation predicates."
        )
    output_kind = "rows" if returned["kind"] == "group" else returned["kind"]
    # Legacy row functions can still return a homogeneous entity collection.
    if output_kind == "entities" and function.output.kind == "rows":
        output_kind = "rows"
    if output_kind != function.output.kind:
        raise ValueError("Function output does not match its plan.")
    if function.output.kind == "entities":
        if set(function.output.entity_types) != returned["types"]:
            raise ValueError("Entity output types differ from the plan.")
    if function.output.kind in {"rows", "scalar"}:
        outputs = (
            {p.name: _declared_type(p) for p in function.output.fields}
            if function.output.kind == "rows"
            else {"value": _declared_type(function.output)}
        )
        if outputs.keys() != returned["fields"].keys():
            raise ValueError("Output fields do not match the plan.")
        for name, spec in outputs.items():
            actual = returned["fields"][name]
            if (
                spec.type != actual.type
                or not _compatible(spec, actual)
                or actual.nullable
                and not spec.nullable
            ):
                raise ValueError("Output type, unit, or nullability differs.")
    return states


@dataclass
class OperatorResult:
    rows: list = field(default_factory=list)
    complete: bool = True
    evidence: list = field(default_factory=list)
    missing: list = field(default_factory=list)
    relations: list = field(default_factory=list)
    truncated: bool = False


def _canonical_value(value):
    return json.dumps(json_value(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _entity_reference(entity_id, identity, context):
    from oak.discovery_validation import digest

    return "oak:entity:" + digest(
        {"entity_id": entity_id, "identity": identity, "context": context}
    )


def _row_key(row):
    return _canonical_value(
        [
            row.get("entity_id"),
            row.get("identity", {}),
            row.get("context", {}),
            row.get("values", {}),
        ]
    )


def _distinct(items):
    return list({_canonical_value(value): value for value in items}.values())


def _row_sources(row):
    return deepcopy(
        row.get(
            "sources",
            [{key: row[key] for key in ("id", "entity_id", "identity", "context") if key in row}],
        )
    )


def _observed_rows(graph, entity_id, context, identity=None):
    entity = graph.entities[entity_id]
    source = (
        graph.lookup(entity_id, identity, context)
        if identity is not None
        else graph.collection(entity_id, context)
    )
    specifications = {
        p.name: p
        for e in graph.candidate.schema.entities
        if e.id == entity_id
        for p in e.properties
    }
    rows = []
    for record in source.records:
        keys = {key: record[key] for key in entity["identity_keys"]}
        stored = graph.records[entity_id][
            (graph._context_key(context), tuple(keys[key] for key in entity["identity_keys"]))
        ]
        rows.append(
            {
                "id": _entity_reference(entity_id, keys, context),
                "entity_id": entity_id,
                "identity": deepcopy(keys),
                "context": deepcopy(context),
                "values": {
                    name: normalize(value, specifications[name]) for name, value in record.items()
                },
                "evidence_refs": deepcopy(list(stored["evidence"].values())),
                "unobserved_fields": [],
            }
        )
    return OperatorResult(rows, source.complete, deepcopy(source.evidence))


def _walk_relations(
    candidate, graph, source, relation_ids, direction, max_hops, include_start, contexts, evaluate
):
    relations = {r.id: r for r in candidate.schema.relations}
    visited = {row["id"]: deepcopy(row) for row in source.rows} if include_start else {}
    expanded, edges, frontier = set(), {}, source.rows
    result = OperatorResult(
        complete=source.complete,
        evidence=deepcopy(source.evidence),
        missing=deepcopy(source.missing),
        truncated=source.truncated,
    )
    cache = {}
    for _ in range(max_hops):
        next_rows = {}
        for row in sorted(frontier, key=_row_key):
            if row["id"] in expanded:
                continue
            expanded.add(row["id"])
            for rid in relation_ids:
                relation = relations[rid]
                for start, end in (("from", "to"), ("to", "from")):
                    if (start == "from" and direction not in {"forward", "outgoing", "both"}) or (
                        start == "to" and direction not in {"reverse", "incoming", "both"}
                    ):
                        continue
                    if row["entity_id"] != getattr(relation, start + "_entity"):
                        continue
                    key_name = getattr(relation, start + "_property")
                    target_id, target_key = (
                        getattr(relation, end + "_entity"),
                        getattr(relation, end + "_property"),
                    )
                    try:
                        if key_name not in row["values"]:
                            raise MissingValue(
                                {
                                    "source": "field",
                                    "entity_id": row["entity_id"],
                                    "identity": row["identity"],
                                    "context": row["context"],
                                    "property": key_name,
                                    "reason": "unavailable",
                                }
                            )
                        key = row["values"][key_name]
                        context = {
                            name: evaluate(expression, row)
                            for name, expression in contexts.get(target_id, {}).items()
                        }
                        if graph.entities[target_id]["identity_keys"] == [target_key]:
                            target = _observed_rows(graph, target_id, context, {target_key: key})
                            matched = target.rows
                        else:
                            cache_key = (target_id, target_key, _canonical_value(context))
                            if cache_key not in cache:
                                target = _observed_rows(graph, target_id, context)
                                index = {}
                                for target_row in target.rows:
                                    if target_key not in target_row["values"]:
                                        target.complete = False
                                        target.missing.append(
                                            {
                                                "source": "field",
                                                "entity_id": target_id,
                                                "identity": target_row["identity"],
                                                "context": context,
                                                "property": target_key,
                                                "reason": "unavailable",
                                            }
                                        )
                                        continue
                                    index.setdefault(
                                        _canonical_value(target_row["values"][target_key]), []
                                    ).append(target_row)
                                cache[cache_key] = (target, index)
                            target, index = cache[cache_key]
                            matched = index.get(_canonical_value(key), [])
                        result.evidence.extend(target.evidence)
                        result.missing.extend(target.missing)
                        result.complete = result.complete and target.complete
                        if not target.complete:
                            result.missing.append(
                                {
                                    "source": "graph",
                                    "entity_id": target_id,
                                    "identity": {target_key: json_value(key)},
                                    "context": context,
                                    "reason": "incomplete_scope",
                                }
                            )
                        for neighbor in matched:
                            visited[neighbor["id"]] = deepcopy(neighbor)
                            next_rows[neighbor["id"]] = neighbor
                            a, b = (row, neighbor) if start == "from" else (neighbor, row)
                            edge_key = (rid, a["id"], b["id"])
                            edges[edge_key] = {
                                "relation_id": rid,
                                "from": a["id"],
                                "to": b["id"],
                                "evidence_refs": _distinct(a["evidence_refs"] + b["evidence_refs"]),
                            }
                            if len(visited) > MAX_VISITED or len(edges) > MAX_VISITED:
                                raise ValueError("Traversal exceeds the entity or relation limit.")
                    except MissingValue as error:
                        result.complete = False
                        result.missing.append(error.detail)
        frontier = list(next_rows.values())
    result.rows = sorted(visited.values(), key=_row_key)
    result.relations = _distinct(source.relations + list(edges.values()))
    _check_result_bounds(result)
    result.evidence = _distinct(result.evidence)
    result.missing = _distinct(result.missing)
    return result


def _normalized_text(value):
    if not isinstance(value, str) or len(value) > 4096:
        raise ValueError("Search text must contain at most 4096 characters.")
    normalized = " ".join(unicodedata.normalize("NFKC", value).casefold().split())
    if len(normalized) > 4096:
        raise ValueError("Normalized search text must contain at most 4096 characters.")
    return normalized


def _check_result_bounds(result):
    identities = {row["id"] for row in result.rows if "id" in row}
    identities.update(edge[end] for edge in result.relations for end in ("from", "to"))
    if len(identities) > MAX_VISITED or len(result.relations) > MAX_VISITED:
        raise ValueError("Execution exceeds the entity or relation limit.")


def _similarity(query, value, fuzzy):
    query, value = _normalized_text(query), _normalized_text(value)
    if not query:
        raise ValueError("A text query cannot be empty.")
    if not fuzzy:
        return Fraction(query == value)
    previous = list(range(len(value) + 1))
    for i, a in enumerate(query, 1):
        current = [i]
        for j, b in enumerate(value, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return Fraction(1) - Fraction(previous[-1], max(len(query), len(value)))


def _execute_expanded(candidate, function_id, arguments, request, graph):
    from oak.repair_executor import MISSING

    function = next((f for f in candidate.functions if f.id == function_id), None)
    if function is None:
        raise ValueError("Unknown function.")
    plans = _compile_expanded(candidate, function)
    parameters = {p.name: _declared_type(p) for p in function.parameters}
    requests = {p.name: _declared_type(p) for p in candidate.request_fields}
    if set(arguments) != set(parameters) or not set(request or {}) <= requests.keys():
        raise ValueError("Function or request arguments do not match their declarations.")
    arguments = {
        name: normalize(value, parameters[name]) if value is not MISSING else value
        for name, value in arguments.items()
    }
    request = {name: normalize(value, requests[name]) for name, value in (request or {}).items()}
    constraints = {c.id: c for c in candidate.constraints}
    entities = {e.id: e for e in candidate.schema.entities}
    relations = {r.id: r for r in candidate.schema.relations}
    values, trace = {}, []
    search_work = 0

    def evaluate(expression, row, state):
        kind = expression.kind
        if kind in {"field", "argument", "request"}:
            source = {"field": row.get("values", {}), "argument": arguments, "request": request}[
                kind
            ]
            value = source.get(expression.name, MISSING)
            if (
                value is MISSING
                or value is None
                or kind == "field"
                and expression.name in row.get("unobserved_fields", [])
            ):
                detail = {
                    "source": kind,
                    "property": expression.name,
                    "reason": "known_absent" if value is None else "unavailable",
                }
                if kind == "field":
                    detail.update(
                        {
                            k: deepcopy(row[k])
                            for k in ("entity_id", "identity", "context")
                            if k in row
                        }
                    )
                raise MissingValue(detail)
            return value
        if kind in {"literal", "typed_literal"}:
            spec = _expanded_expression(expression, deepcopy(state), parameters, requests, plans)
            return normalize(expression.value, spec)
        if kind == "result":
            result = values[expression.step_id]
            if (
                not result.complete
                or result.missing
                or result.truncated
                or len(result.rows) != 1
                or expression.field in result.rows[0].get("unobserved_fields", [])
            ):
                raise MissingValue(
                    {"source": "result", "step_id": expression.step_id, "reason": "unavailable"}
                )
            value = result.rows[0]["values"][expression.field]
            if value is None:
                raise MissingValue(
                    {"source": "result", "step_id": expression.step_id, "reason": "known_absent"}
                )
            return value
        if kind == "convert":
            value = evaluate(expression.value, row, state)
            spec = _expanded_expression(
                expression.value, deepcopy(state), parameters, requests, plans
            )
            result = numeric(value) * conversion(
                unit_signature(spec.unit), unit_signature(expression.unit)
            )
            if spec.type == "integer":
                if result.denominator != 1:
                    raise ValueError("Integer conversion must be exact.")
                result = result.numerator
        else:
            left, right = (
                evaluate(expression.left, row, state),
                evaluate(expression.right, row, state),
            )
            result = left + right if kind == "add" else left * right
        if abs(result) > MAX_INTEGER:
            raise ValueError("Arithmetic result exceeds the numeric limit.")
        return result

    def predicate_value(predicate, row, state):
        def ev(expression, item=row):
            value = evaluate(expression, item, state)
            operand = {
                "expression": expression.model_dump(mode="json"),
                "sources": _row_sources(item),
                "value": json_value(value),
            }
            if isinstance(value, Fraction):
                operand["exact_numeric"] = {
                    "numerator": str(value.numerator),
                    "denominator": str(value.denominator),
                }
            event.setdefault("evaluated_operands", []).append(operand)
            return value

        if predicate.operator == "connected":
            walked = _walk_relations(
                candidate,
                graph,
                OperatorResult([row], evidence=row["evidence_refs"]),
                predicate.relation_ids,
                predicate.direction,
                predicate.max_hops,
                False,
                predicate.contexts,
                ev,
            )
            missing, outcomes = [], []
            for anchor in predicate.anchors:
                identity = {key: ev(expression) for key, expression in anchor.identity.items()}
                context = {key: ev(expression) for key, expression in anchor.context.items()}
                found = any(
                    r["entity_id"] == anchor.entity_id
                    and r["identity"] == identity
                    and r["context"] == context
                    for r in walked.rows
                )
                outcomes.append(True if found else False if walked.complete else None)
                if not found and not walked.complete:
                    missing.append(
                        {
                            "source": "graph",
                            "entity_id": anchor.entity_id,
                            "identity": identity,
                            "context": context,
                            "reason": "connection_unobserved",
                        }
                    )
            return (
                False if False in outcomes else None if None in outcomes else True,
                walked.evidence,
                missing,
                walked.relations,
            )
        left, right = ev(predicate.left), ev(predicate.right)
        if predicate.operator in {"in", "not_in"}:
            match = left in right
            return (match if predicate.operator == "in" else not match), [], [], []
        if predicate.operator.startswith("overlap_"):
            a, b = set(left), set(right)
            minimum = ev(predicate.minimum) if predicate.minimum is not None else None
            if minimum is not None and minimum < 0:
                raise ValueError("An overlap minimum cannot be negative.")
            return (
                (
                    {
                        "overlap_any": bool(a & b),
                        "overlap_all": b <= a,
                        "overlap_min": len(a & b) >= (minimum or 0),
                    }[predicate.operator]
                ),
                [],
                [],
                [],
            )
        return _compare(predicate.operator, left, right), [], [], []

    for step in function.steps:
        state = plans[step.id]
        source = values.get(getattr(step, "input", ""))
        input_state = plans.get(getattr(step, "input", ""), state)
        event = {
            "step_id": step.id,
            "operator": step.op,
            "operands": step.model_dump(mode="json"),
            "input_ids": [row.get("id") for row in source.rows]
            if isinstance(source, OperatorResult)
            else [],
            "input": deepcopy(source.rows) if isinstance(source, OperatorResult) else [],
        }
        result = deepcopy(source) if isinstance(source, OperatorResult) else OperatorResult()
        try:
            if step.op == "input":
                result.rows = [{"values": {}, "evidence_refs": [], "unobserved_fields": []}]
            elif step.op == "lookup":
                for entity_id in sorted(state["types"]):
                    context = {
                        name: evaluate(expression, {}, state)
                        for name, expression in step.contexts.get(entity_id, step.context).items()
                    }
                    identity = {
                        name: evaluate(expression, {}, state)
                        for name, expression in step.identity.items()
                    }
                    exact = set(identity) == set(entities[entity_id].identity_keys)
                    observed = _observed_rows(
                        graph, entity_id, context, identity if exact else None
                    )
                    event["input"].extend(deepcopy(observed.rows))
                    event.setdefault("lookup_operands", []).append(
                        {
                            "entity_id": entity_id,
                            "context": context,
                            "identity": identity,
                        }
                    )
                    result.complete = result.complete and observed.complete
                    result.evidence.extend(observed.evidence)
                    filters = {
                        name: evaluate(expression, {}, state)
                        for name, expression in step.property_filters.items()
                    }
                    identifiers = (
                        evaluate(step.identifiers, {}, state) if step.identifiers else None
                    )
                    queries = [
                        (_normalized_text(evaluate(query, {}, state)), fields)
                        for query, fields in (
                            (step.name_query, step.name_fields),
                            (step.text_query, step.text_fields),
                        )
                        if query is not None
                    ]
                    if any(not query for query, _ in queries):
                        raise ValueError("A text query cannot be empty.")
                    event["lookup_operands"][-1].update(
                        property_filters=filters, identifiers=identifiers, queries=queries
                    )
                    for row in observed.rows:
                        if (
                            any(
                                row["identity"].get(name) != value
                                for name, value in identity.items()
                            )
                            or identifiers is not None
                            and row["id"] not in identifiers
                        ):
                            continue
                        matches, gaps = [], []
                        for name, value in filters.items():
                            if name not in row["values"]:
                                gaps.append(
                                    {
                                        "source": "field",
                                        "entity_id": entity_id,
                                        "identity": row["identity"],
                                        "context": context,
                                        "property": name,
                                        "reason": "unavailable",
                                    }
                                )
                            else:
                                matches.append(row["values"][name] == value)
                        if False in matches:
                            continue
                        if gaps:
                            result.missing.extend(gaps)
                            continue
                        scores = []
                        for query_value, fields in queries:
                            if any(name not in row["values"] for name in fields):
                                gaps.extend(
                                    {
                                        "source": "field",
                                        "entity_id": entity_id,
                                        "identity": row["identity"],
                                        "context": context,
                                        "property": name,
                                        "reason": "unavailable",
                                    }
                                    for name in fields
                                    if name not in row["values"]
                                )
                                continue
                            field_values = [
                                _normalized_text(row["values"][name]) for name in fields
                            ]
                            search_work += sum(
                                len(query_value) * len(value) for value in field_values
                            )
                            if search_work > 5_000_000:
                                raise ValueError("Text lookup exceeds the comparison work limit.")
                            scores.append(
                                max(
                                    _similarity(query_value, value, step.fuzzy)
                                    for value in field_values
                                )
                            )
                        if gaps:
                            result.missing.extend(gaps)
                            continue
                        score = min(scores) if scores else Fraction(1)
                        if scores and (
                            score < numeric(step.min_score) or not step.fuzzy and score != 1
                        ):
                            continue
                        if scores:
                            row["score"] = score
                        result.rows.append(row)
                    if exact and not observed.rows and not observed.complete:
                        result.missing.append(
                            {
                                "source": "graph",
                                "entity_id": entity_id,
                                "identity": identity,
                                "context": context,
                                "reason": "subject_unobserved",
                            }
                        )
                result.rows.sort(key=lambda row: (-row.get("score", Fraction(1)), _row_key(row)))
                if len(result.rows) > MAX_VISITED:
                    raise ValueError("Lookup exceeds the entity limit.")
                if step.top_k is not None:
                    result.truncated = len(result.rows) > step.top_k
                    result.rows = result.rows[: step.top_k]
            elif step.op == "traverse":
                contexts = {
                    entity_id: step.contexts.get(entity_id, step.context) for entity_id in entities
                }
                result = _walk_relations(
                    candidate,
                    graph,
                    source,
                    step.relation_ids
                    or ([step.relation_id] if step.relation_id else list(relations)),
                    step.direction,
                    step.max_hops,
                    step.include_starting_entities is not False,
                    contexts,
                    lambda expression, row: evaluate(expression, row, input_state),
                )
            elif step.op == "select_types":
                result.rows = [row for row in source.rows if row["entity_id"] in step.entity_types]
            elif step.op in {"filter", "assert"}:
                checked = []
                outcomes_by_id = {cid: [] for cid in step.constraint_ids}
                missing_by_id = {cid: deepcopy(source.missing) for cid in step.constraint_ids}
                input_evidence = deepcopy(source.evidence)
                for ancestor in state["ancestors"] - {step.id}:
                    dependency = values.get(ancestor)
                    if isinstance(dependency, OperatorResult):
                        input_evidence.extend(dependency.evidence)
                evidence_by_id = {cid: _distinct(input_evidence) for cid in step.constraint_ids}
                selected, row_events = [], []
                predicate_relations = {
                    (edge["relation_id"], edge["from"], edge["to"]): edge
                    for edge in result.relations
                }
                for row in source.rows:
                    outcomes, gaps = [], []
                    for cid in step.constraint_ids:
                        try:
                            outcome, evidence, absent, edges = predicate_value(
                                constraints[cid].predicate, row, input_state
                            )
                            evidence_by_id[cid].extend(evidence)
                            result.evidence.extend(evidence)
                            predicate_relations.update(
                                ((edge["relation_id"], edge["from"], edge["to"]), edge)
                                for edge in edges
                            )
                            result.relations = list(predicate_relations.values())
                            _check_result_bounds(result)
                            missing_by_id[cid].extend(absent)
                            gaps.extend(absent)
                        except MissingValue as error:
                            outcome = None
                            gaps.append(error.detail)
                            missing_by_id[cid].append(error.detail)
                        outcomes.append(outcome)
                        outcomes_by_id[cid].append(outcome)
                    row_events.append(
                        {
                            "sources": _row_sources(row),
                            "conditions": dict(zip(step.constraint_ids, outcomes, strict=True)),
                        }
                    )
                    if False in outcomes:
                        continue
                    if None in outcomes:
                        if step.op == "filter":
                            result.missing.extend(gaps)
                        continue
                    selected.append(row)
                if step.op == "filter":
                    result.rows = selected
                else:
                    for cid in step.constraint_ids:
                        outcomes = outcomes_by_id[cid]
                        if not source.rows:
                            outcomes.append(
                                False if source.complete and not source.missing else None
                            )
                        if not source.complete or source.missing or source.truncated:
                            outcomes.append(None)
                        checked.append(
                            {
                                "condition_id": cid,
                                "value": "false"
                                if False in outcomes
                                else "unknown"
                                if None in outcomes
                                else "true",
                                "missing": _distinct(missing_by_id[cid]),
                                "evidence_refs": _distinct(evidence_by_id[cid]),
                            }
                        )
                    event["relations"] = _distinct(result.relations)
                    result = checked
                event["conditions"] = row_events
            elif step.op == "project":
                result.rows = []
                for row in source.rows:
                    projected = deepcopy(row)
                    projected["values"], projected["unobserved_fields"] = {}, []
                    projected["sources"] = _row_sources(row)
                    for projection in step.fields:
                        try:
                            value = evaluate(projection.expression, row, input_state)
                        except MissingValue:
                            if projection.missing_value is not None:
                                value = evaluate(projection.missing_value, row, input_state)
                            elif projection.nullable:
                                value = None
                            else:
                                raise
                            projected["unobserved_fields"].append(projection.name)
                        projected["values"][projection.name] = value
                    result.rows.append(projected)
            elif step.op == "aggregate":
                if not source.complete or source.missing or source.truncated:
                    raise MissingValue(
                        {
                            "source": "graph",
                            "reason": "complete_scope_required",
                            "step_id": step.input,
                        }
                    )
                groups = {} if step.group_by else {None: []}
                for row in source.rows:
                    if step.group_by:
                        from oak.repair_schemas import FieldExpression

                        key = evaluate(FieldExpression(name=step.group_by), row, input_state)
                    else:
                        key = None
                    groups.setdefault(key, []).append(row)
                result.rows = []
                for key, rows in sorted(groups.items(), key=lambda item: _canonical_value(item[0])):
                    operands = (
                        [evaluate(step.expression, row, input_state) for row in rows]
                        if step.expression
                        else []
                    )
                    value = (
                        len(rows)
                        if step.operation == "count"
                        else sum(operands)
                        if step.operation == "sum"
                        else min(operands)
                        if operands and step.operation == "min"
                        else max(operands)
                        if operands and step.operation == "max"
                        else sum((numeric(v) for v in operands), Fraction()) / len(operands)
                        if operands
                        else None
                    )
                    if value is not None and abs(value) > MAX_INTEGER:
                        raise ValueError("Aggregate result exceeds the numeric limit.")
                    if value is not None and state["fields"]["value"].type == "decimal":
                        value = numeric(value)
                    fields = {"value": value}
                    if step.group_by:
                        fields["group"] = key
                    result.rows.append(
                        {
                            "values": fields,
                            "sources": _distinct([s for row in rows for s in _row_sources(row)]),
                            "evidence_refs": _distinct(
                                [ref for row in rows for ref in row["evidence_refs"]]
                            ),
                            "unobserved_fields": [],
                        }
                    )
            elif step.op == "select_group":
                key = evaluate(step.key, {}, input_state)
                result.rows = [row for row in source.rows if row["values"]["group"] == key]
            elif step.op == "select_min":
                if not source.complete or source.missing or source.truncated:
                    raise MissingValue(
                        {
                            "source": "graph",
                            "reason": "complete_scope_required",
                            "step_id": step.input,
                        }
                    )
                result.rows = sorted(
                    source.rows,
                    key=lambda row: (
                        tuple(
                            evaluate(expression, row, input_state) for expression in step.order_by
                        ),
                        _row_key(row),
                    ),
                )[:1]
            elif step.op == "decision":
                result = [
                    condition for identifier in step.inputs for condition in values[identifier]
                ]
            if isinstance(result, OperatorResult):
                # Result references contribute evidence even when the final input is another branch.
                for ancestor in state["ancestors"] - {step.id}:
                    dependency = values.get(ancestor)
                    if isinstance(dependency, OperatorResult):
                        result.evidence.extend(dependency.evidence)
                result.evidence = _distinct(result.evidence)
                result.missing = _distinct(result.missing)
                result.relations = _distinct(result.relations)
                _check_result_bounds(result)
        except MissingValue as error:
            result = OperatorResult(
                complete=False,
                evidence=deepcopy(source.evidence) if isinstance(source, OperatorResult) else [],
                missing=[error.detail],
            )
            event["missing_dependencies"] = [error.detail]
        values[step.id] = result
        if isinstance(result, OperatorResult):
            event.update(
                complete=result.complete,
                truncated=result.truncated,
                output_count=len(result.rows),
                output=json_value(result.rows),
                evidence_refs=result.evidence,
                missing_dependencies=result.missing,
            )
            if step.op in {"lookup", "filter", "select_types", "select_min", "select_group"}:
                retained = {_canonical_value(row) for row in result.rows}
                retained_ids = {row["id"] for row in result.rows if "id" in row}
                event["excluded_records"] = [
                    row
                    for row in event["input"]
                    if row.get("id") not in retained_ids and _canonical_value(row) not in retained
                ]
                event["excluded_ids"] = [row.get("id") for row in event["excluded_records"]]
        else:
            event["output"] = json_value(result)
        trace.append(json_value(event))
    returned = values[function.return_step]
    if function.output.kind == "decision":
        return json_value(
            {
                "status": combine_conditions(returned),
                "conditions": returned,
                "trace": trace,
                "evidence_refs": _distinct([ref for c in returned for ref in c["evidence_refs"]]),
                "missing_dependencies": _distinct(
                    [gap for c in returned if c["value"] == "unknown" for gap in c["missing"]]
                ),
                "graph_revision": graph.revision,
            }
        )
    if function.output.kind == "entities":
        value = returned.rows
    elif function.output.kind == "scalar":
        value = returned.rows[0]["values"]["value"] if returned.rows else None
        if not returned.missing and not valid_value(
            value, function.output.type, function.output.nullable, internal=True
        ):
            raise ValueError("Scalar result does not match its output declaration.")
    else:
        value = [row["values"] for row in returned.rows]
        for row in returned.rows:
            for output in function.output.fields:
                if output.name not in row["values"]:
                    returned.missing.append(
                        {
                            "source": "field",
                            "property": output.name,
                            "reason": "unavailable",
                            "sources": _row_sources(row),
                        }
                    )
                elif not valid_value(
                    row["values"][output.name],
                    output.type,
                    output.nullable,
                    output.item_type,
                    internal=True,
                ):
                    raise ValueError("Row result does not match its output declaration.")
    return json_value(
        {
            "status": "incomplete" if returned.missing else "complete",
            "output_type": function.output.model_dump(mode="json"),
            "value": None if returned.missing else value,
            "issues": ["Required evidence is unavailable."] if returned.missing else [],
            "trace": trace,
            "evidence_refs": returned.evidence,
            "missing_dependencies": returned.missing,
            "graph_revision": graph.revision,
            "coverage": "complete" if returned.complete and not returned.truncated else "observed",
            "truncated": returned.truncated,
            "relations": returned.relations,
            "row_metadata": [
                {key: deepcopy(row[key]) for key in row if key != "values"} for row in returned.rows
            ],
        }
    )


VERSIONS = {
    "operators": "oak.operators.v3",
    "dispatcher": "oak.dispatcher.v4",
    "request_preparation": "oak.request.v4",
    "evidence_access": "oak.evidence-access.v1",
    "encoder": "oak.owl-encoder.v2",
    "evaluator": "oak.kernel-evaluation.v2",
}
# These scale relationships are fixed runtime definitions. Candidates cannot add them.
SCALES = {
    "second": ("second", 1),
    "minute": ("second", 60),
    "hour": ("second", 3600),
    "day": ("second", 86400),
    "USD.cent": ("USD", 1),
    "USD": ("USD", 100),
    "EUR.cent": ("EUR", 1),
    "EUR": ("EUR", 100),
    "GBP.penny": ("GBP", 1),
    "GBP": ("GBP", 100),
}


def unit_signature(unit):
    if not unit or unit == "1":
        return {}
    signature = Counter()
    parts = unit.split("/")
    if len(parts) > 2:
        raise ValueError("Use one denominator in a unit declaration.")
    for index, part in enumerate(parts):
        for atom in part.split("*"):
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]{0,79}", atom):
                raise ValueError("Invalid unit identifier.")
            signature[atom] += 1 if index == 0 else -1
    return {key: value for key, value in sorted(signature.items()) if value}


def _product(left, right):
    value = Counter(left)
    value.update(right)
    return {k: v for k, v in sorted(value.items()) if v}


def conversion(source, target):
    if source == target:
        return Fraction(1)
    if len(source) != 1 or len(target) != 1:
        raise ValueError("Unsupported unit conversion.")
    a, b = next(iter(source)), next(iter(target))
    if source[a] != 1 or target[b] != 1 or a not in SCALES or b not in SCALES:
        raise ValueError("Unsupported unit conversion.")
    if SCALES[a][0] != SCALES[b][0]:
        raise ValueError("Currency and dimension conversions are not permitted.")
    return Fraction(SCALES[a][1], SCALES[b][1])


def _unique(items, key, label):
    result = {getattr(item, key): item for item in items}
    if len(result) != len(items):
        raise ValueError(f"Duplicate {label}.")
    return result


def _expr_type(expression, fields, parameters, requests, depth=0):
    if depth > 6:
        raise ValueError("Expression depth exceeds six.")
    kind = expression.kind
    if kind in {"field", "argument", "request"}:
        source = {"field": fields, "argument": parameters, "request": requests}[kind]
        if expression.name not in source:
            raise ValueError(f"Unknown {kind}: {expression.name}.")
        item = source[expression.name]
        return item.type, getattr(item, "_signature", unit_signature(getattr(item, "unit", None)))
    if kind == "literal":
        scalar = {str: "string", int: "integer", bool: "boolean"}[type(expression.value)]
        if scalar != "integer" and expression.unit:
            raise ValueError("Only integer values can have units.")
        return scalar, unit_signature(expression.unit)
    if kind == "convert":
        scalar, source = _expr_type(expression.value, fields, parameters, requests, depth + 1)
        target = unit_signature(expression.unit)
        if scalar != "integer":
            raise ValueError("Unit conversion requires an integer.")
        conversion(source, target)
        return scalar, target
    a, au = _expr_type(expression.left, fields, parameters, requests, depth + 1)
    b, bu = _expr_type(expression.right, fields, parameters, requests, depth + 1)
    if a != "integer" or b != "integer":
        raise ValueError("Arithmetic requires integer operands.")
    if kind == "add" and au != bu:
        raise ValueError("Addition requires identical units.")
    return "integer", au if kind == "add" else _product(au, bu)


def _check_legacy_function(function, constraints):
    fields = {
        "input": {"op", "id"},
        "lookup": {"op", "id", "entity_id", "identity", "context"},
        "traverse": {"op", "id", "input", "relation_id", "direction", "context"},
        "filter": {"op", "id", "input", "constraint_ids"},
        "assert": {"op", "id", "input", "constraint_ids"},
        "project": {"op", "id", "input", "fields"},
        "aggregate": {"op", "id", "input", "operation", "expression"},
        "select_min": {"op", "id", "input", "order_by"},
        "decision": {"op", "id", "inputs"},
    }
    for step in function.steps:
        if step.op not in fields or step.model_dump(mode="json").keys() - fields[step.op]:
            raise ValueError("This operator requires a version 3 candidate.")
        if step.op == "aggregate" and step.operation == "average":
            raise ValueError("Average requires a version 3 candidate.")
        if step.op == "traverse" and step.direction not in {"forward", "reverse"}:
            raise ValueError("This traversal direction requires a version 3 candidate.")
        if step.op == "project" and any(p.nullable for p in step.fields):
            raise ValueError("Nullable projection requires a version 3 candidate.")

    def visit(value):
        if isinstance(value, dict):
            if (
                value.get("kind") in {"typed_literal", "result", "entities"}
                or value.get("type") in {"decimal", "array"}
                or "missing_value" in value
                or "item_type" in value
            ):
                raise ValueError("This declaration requires a version 3 candidate.")
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(function.model_dump(mode="json"))
    for condition in constraints:
        visit(condition.predicate.model_dump(mode="json"))


def compile_function(candidate, function):
    if candidate.version == "oak.candidate.v3":
        return _compile_expanded(candidate, function)
    _check_legacy_function(function, candidate.constraints)
    if any(
        c.predicate.operator not in {"eq", "ne", "lt", "le", "gt", "ge"}
        for c in candidate.constraints
    ):
        raise ValueError("This predicate requires a version 3 candidate.")
    entities = {e.id: e for e in candidate.schema.entities}
    relations = {r.id: r for r in candidate.schema.relations}
    constraints = {c.id: c for c in candidate.constraints}
    params = _unique(function.parameters, "name", "parameter")
    requests = {f.name: f for f in candidate.request_fields}
    _unique(function.steps, "id", "step")
    states, seen_constraints = {}, set()
    is_check = function.output.kind == "decision"
    if not function.steps or function.steps[0].op not in {"input", "lookup"}:
        raise ValueError("A function starts with request input or lookup.")
    for step in function.steps:
        if step.op == "input":
            state = {"fields": {}, "entity": None, "ancestors": {step.id}, "kind": "rows"}
        elif step.op == "lookup":
            if step.entity_id not in entities:
                raise ValueError("Unknown lookup entity.")
            entity = entities[step.entity_id]
            fields = {p.name: p for p in entity.properties}
            if is_check and set(step.identity) != set(entity.identity_keys):
                raise ValueError("A check lookup must bind the exact entity identity.")
            for name, expression in step.identity.items():
                if name not in entity.identity_keys:
                    raise ValueError("Lookup uses an undeclared identity property.")
                actual = _expr_type(expression, {}, params, requests)
                if actual != (fields[name].type, unit_signature(fields[name].unit)):
                    raise ValueError("Lookup identity type or unit differs.")
            for expression in step.context.values():
                _expr_type(expression, {}, params, requests)
            scopes = {
                s.name for m in candidate.mappings if m.entity_id == entity.id for s in m.scope
            }
            if set(step.context) != scopes:
                raise ValueError("Lookup must bind the declared evidence context.")
            state = {"fields": fields, "entity": entity.id, "ancestors": {step.id}, "kind": "rows"}
        elif step.op == "decision":
            if not is_check or any(
                s not in states or states[s]["kind"] != "assert" for s in step.inputs
            ):
                raise ValueError("A decision requires earlier assertion results.")
            state = {"fields": {}, "entity": None, "kind": "decision", "ancestors": {step.id}}
            for source in step.inputs:
                state["ancestors"].update(states[source]["ancestors"])
        else:
            if step.input not in states or states[step.input]["kind"] != "rows":
                raise ValueError("An operator needs an earlier record input.")
            state = deepcopy(states[step.input])
            state["ancestors"].add(step.id)
            fields = state["fields"]
            if step.op in {"assert", "filter"}:
                if is_check and step.op == "filter":
                    raise ValueError(
                        "Use assertions in checks so excluded records cannot authorize."
                    )
                for cid in step.constraint_ids:
                    if cid not in constraints or constraints[cid].entity_id != state["entity"]:
                        raise ValueError("Condition uses the wrong entity.")
                    p = constraints[cid].predicate
                    left = _expr_type(p.left, fields, params, requests)
                    right = _expr_type(p.right, fields, params, requests)
                    if left != right or (p.operator not in {"eq", "ne"} and left[0] != "integer"):
                        raise ValueError("Comparison requires compatible types and units.")
                    seen_constraints.add(cid)
                if step.op == "assert":
                    state["kind"] = "assert"
            elif step.op == "traverse":
                relation = relations.get(step.relation_id)
                start, end = ("from", "to") if step.direction == "forward" else ("to", "from")
                if relation is None or getattr(relation, start + "_entity") != state["entity"]:
                    raise ValueError("Traversal starts from the wrong entity.")
                target = entities[getattr(relation, end + "_entity")]
                for expression in step.context.values():
                    _expr_type(expression, fields, params, requests)
                scopes = {
                    s.name for m in candidate.mappings if m.entity_id == target.id for s in m.scope
                }
                if set(step.context) != scopes:
                    raise ValueError("Traversal must bind its target evidence context.")
                state["entity"] = target.id
                state["fields"] = {p.name: p for p in target.properties}
            elif step.op == "project":
                from oak.repair_schemas import Parameter

                projected = {}
                for field in step.fields:
                    kind, signature = _expr_type(field.expression, fields, params, requests)
                    projected[field.name] = Parameter(name=field.name, type=kind)
                    object.__setattr__(projected[field.name], "_signature", signature)
                state["fields"] = projected
            elif step.op in {"aggregate", "select_min"}:
                if is_check:
                    raise ValueError("Check functions use exact subjects and assertions.")
                expressions = (
                    step.order_by
                    if step.op == "select_min"
                    else ([step.expression] if step.expression else [])
                )
                for expression in expressions:
                    operand = _expr_type(expression, fields, params, requests)
                    if step.op == "aggregate" and operand[0] != "integer":
                        raise ValueError("Aggregation requires integer operands.")
                if step.op == "aggregate":
                    state["kind"] = "scalar"
                    state["scalar"] = ("integer", step.operation in {"min", "max"})
                    state["signature"] = operand[1] if expressions else {}
            else:
                raise ValueError("Unsupported operator.")
        states[step.id] = state
    result = states.get(function.return_step)
    if result is None or result["ancestors"] != set(states):
        raise ValueError("Every step must contribute to the returned result.")
    if set(function.required_constraint_ids) != seen_constraints:
        raise ValueError("Required conditions must match executed conditions.")
    if is_check and (result["kind"] != "decision" or not seen_constraints):
        raise ValueError("A check must return a decision with required conditions.")
    if not is_check and function.output.kind != result["kind"]:
        raise ValueError("Function output does not match its plan.")
    if function.output.kind == "scalar":
        kind, nullable = result["scalar"]
        if function.output.type != kind or (nullable and not function.output.nullable):
            raise ValueError("Scalar output type or nullability differs.")
        if unit_signature(getattr(function.output, "unit", None)) != result["signature"]:
            raise ValueError("Scalar output unit differs.")
    if function.output.kind == "rows":
        outputs = {f.name: f for f in function.output.fields}
        if set(outputs) != set(result["fields"]):
            raise ValueError("Output fields do not match projection.")
        for name, field in outputs.items():
            actual = result["fields"][name]
            signature = getattr(actual, "_signature", unit_signature(actual.unit))
            if field.type != actual.type or unit_signature(field.unit) != signature:
                raise ValueError("Output field type or unit differs.")
    return states


def validate_v2(candidate, allowed_tool_ids, requirement_ids):
    from oak.acquisition import validate_access

    candidate = Candidate.model_validate(candidate)
    validate_access(candidate)
    requirements = _unique(candidate.requirements.requirements, "id", "requirement")
    if not set(requirements) <= set(requirement_ids):
        raise ValueError("Unknown original requirement.")
    allowed = set(map(str, allowed_tool_ids))
    entities = _unique(candidate.schema.entities, "id", "entity")
    relations = _unique(candidate.schema.relations, "id", "relation")
    _unique(candidate.schema.bindings, "id", "source binding")
    for entity in entities.values():
        props = _unique(entity.properties, "name", "property")
        if not entity.identity_keys or not set(entity.identity_keys) <= set(props):
            raise ValueError("An entity requires declared identity properties.")
        for prop in props.values():
            if candidate.version == "oak.candidate.v3":
                _declared_type(prop)
            elif prop.type not in {"string", "integer", "boolean"} or prop.item_type is not None:
                raise ValueError("Only scalar graph properties are supported.")
            unit_signature(prop.unit)
        if any(
            props[key].type not in {"string", "integer", "boolean"} for key in entity.identity_keys
        ):
            raise ValueError("Identity properties must be scalar strings, integers, or booleans.")
    for relation in relations.values():
        endpoints = []
        for prefix in ("from", "to"):
            entity = entities.get(getattr(relation, prefix + "_entity"))
            if entity is None or getattr(relation, prefix + "_property") not in {
                p.name for p in entity.properties
            }:
                raise ValueError("Invalid relation endpoint.")
            prop = next(
                prop
                for prop in entity.properties
                if prop.name == getattr(relation, prefix + "_property")
            )
            endpoints.append((prop.type, unit_signature(prop.unit)))
        if endpoints[0] != endpoints[1] or endpoints[0][0] == "array":
            raise ValueError("Relation endpoints require identical types and units.")
    scopes = {}
    _unique(candidate.mappings, "id", "mapping")
    for mapping in candidate.mappings:
        entity = entities.get(mapping.entity_id)
        if entity is None or mapping.tool_id not in allowed:
            raise ValueError("Mapping uses an unknown entity or ungranted tool.")
        names = {f.property for f in mapping.fields}
        if not set(entity.identity_keys) <= names or not names <= {
            p.name for p in entity.properties
        }:
            raise ValueError("Mapping needs identity and declared properties.")
        signature = frozenset(s.name for s in mapping.scope)
        if entity.id in scopes and scopes[entity.id] != signature:
            raise ValueError("Entity mappings must use the same context fields.")
        scopes[entity.id] = signature
        if mapping.update_mode == "partial" and mapping.update_support is None:
            raise ValueError("Partial updates require source contract evidence.")
    functions = _unique(candidate.functions, "id", "function")
    constraints = _unique(candidate.constraints, "id", "condition")
    requests = _unique(candidate.request_fields, "id", "request field")
    _unique(candidate.request_fields, "name", "request field name")
    bindings = _unique(candidate.operation_bindings, "id", "operation binding")
    _unique(candidate.operation_bindings, "tool_id", "bound tool")
    _unique(candidate.formal_axioms, "id", "formal axiom")
    for item in [
        *entities.values(),
        *relations.values(),
        *constraints.values(),
        *requests.values(),
        *bindings.values(),
        *candidate.formal_axioms,
    ]:
        if not set(item.requirement_ids) <= set(requirements):
            raise ValueError("A declaration refers to an unknown requirement.")
    for function in functions.values():
        compile_function(candidate, function)
    for binding in bindings.values():
        if binding.tool_id not in allowed:
            raise ValueError("Binding uses an ungranted tool.")
        for check in binding.checks:
            function = functions.get(check.function_id)
            if function is None or function.output.kind != "decision":
                raise ValueError("A tool binding must name a decision function.")
            if set(check.arguments) != {p.name for p in function.parameters}:
                raise ValueError("Bound arguments must cover the function parameters.")
            for path in [*check.arguments.values(), *binding.credential_paths]:
                if not path.startswith("/"):
                    raise ValueError("Argument paths require a non-root JSON Pointer.")
            if any(
                a == c or a.startswith(c + "/") or c.startswith(a + "/")
                for a in check.arguments.values()
                for c in binding.credential_paths
            ):
                raise ValueError("Credentials cannot supply condition parameters.")
    coverage = _unique(candidate.requirement_coverage, "id", "requirement coverage")
    if {r.requirement_id for r in coverage.values()} != set(requirements):
        raise ValueError("Every original requirement needs explicit operation coverage.")
    for row in coverage.values():
        rid = row.requirement_id
        if (
            not set(row.request_field_ids) <= set(requests)
            or not set(row.constraint_ids) <= set(constraints)
            or not set(row.binding_ids) <= set(bindings)
        ):
            raise ValueError("Requirement coverage has an unknown reference.")
        if not row.constraint_ids:
            raise ValueError("Requirement coverage must include executable conditions.")
        for bid in row.binding_ids:
            binding = bindings[bid]
            executed = {
                c for b in binding.checks for c in functions[b.function_id].required_constraint_ids
            }
            if rid not in binding.requirement_ids or not set(row.constraint_ids) <= executed:
                raise ValueError("Requirement conditions must run in every covered binding.")
    if not bindings:
        raise ValueError("A version 2 candidate requires enabled operation bindings.")
    return candidate


class MissingValue(Exception):
    def __init__(self, detail):
        self.detail = detail
        super().__init__(str(detail))


def _value(expression, record, arguments, request, fields, params, request_fields):
    from oak.repair_executor import MISSING, _integer

    kind = expression.kind
    if kind in {"field", "argument", "request"}:
        source = {"field": record, "argument": arguments, "request": request}[kind]
        value = source.get(expression.name, MISSING)
        if value is MISSING:
            raise MissingValue(
                {"source": kind, "property": expression.name, "reason": "unavailable"}
            )
        if value is None:
            raise MissingValue(
                {"source": kind, "property": expression.name, "reason": "known_absent"}
            )
        return value
    if kind == "literal":
        return expression.value
    if kind == "convert":
        value = _integer(
            _value(expression.value, record, arguments, request, fields, params, request_fields)
        )
        _, source = _expr_type(expression.value, fields, params, request_fields)
        factor = conversion(source, unit_signature(expression.unit))
        converted = value * factor
        if converted.denominator != 1:
            raise ValueError("Unit conversion did not produce an exact integer.")
        return _integer(converted.numerator)
    left = _integer(
        _value(expression.left, record, arguments, request, fields, params, request_fields)
    )
    right = _integer(
        _value(expression.right, record, arguments, request, fields, params, request_fields)
    )
    return _integer(left + right if kind == "add" else left * right)


def _compare(operator, left, right):
    return {
        "eq": lambda: left == right,
        "ne": lambda: left != right,
        "lt": lambda: left < right,
        "le": lambda: left <= right,
        "gt": lambda: left > right,
        "ge": lambda: left >= right,
    }[operator]()


def combine_conditions(conditions):
    if not conditions:
        raise ValueError("A decision requires at least one condition result.")
    values = {c["value"] for c in conditions}
    if not values <= {"true", "false", "unknown"}:
        raise ValueError("A decision contains an invalid condition value.")
    return (
        "rejected"
        if "false" in values
        else "missing_evidence"
        if "unknown" in values
        else "allowed"
    )


def execute_v2(candidate, function_id, arguments, request, graph):
    from oak.repair_executor import MISSING, IncompleteEvidence, RecordSet, _scalar

    candidate = Candidate.model_validate(candidate)
    if candidate.version == "oak.candidate.v3":
        return _execute_expanded(candidate, function_id, arguments, request, graph)
    function = next((f for f in candidate.functions if f.id == function_id), None)
    if function is None:
        raise ValueError("Unknown function.")
    plans = compile_function(candidate, function)
    params = {p.name: p for p in function.parameters}
    requests = {f.name: f for f in candidate.request_fields}
    if set(arguments) != set(params):
        raise ValueError("Function arguments do not match its parameters.")
    for name, value in arguments.items():
        p = params[name]
        if value is not MISSING and not _scalar(value, p.type, p.nullable):
            raise ValueError("Invalid function parameter type.")
    request = deepcopy(request or {})
    for name, value in request.items():
        if name not in requests or not _scalar(value, requests[name].type, requests[name].nullable):
            raise ValueError("Invalid fixed request value.")
    values, trace, conditions, missing = {}, [], [], []
    scalar_evidence = []
    row_contexts, subjects, pending = {}, {}, {}
    constraints = {c.id: c for c in candidate.constraints}
    relations = {r.id: r for r in candidate.schema.relations}
    entities = {e.id: e for e in candidate.schema.entities}
    for step in function.steps:
        fields = plans[step.id]["fields"]
        row_contexts[step.id], subjects[step.id], pending[step.id] = [], [], []

        def evaluate(expression, record=None, source_fields=None):
            return _value(
                expression,
                record or {},
                arguments,
                request,
                source_fields or fields,
                params,
                requests,
            )

        try:
            if step.op == "input":
                result = RecordSet("", [{}], True, [], ())
                row_contexts[step.id] = [{}]
            elif step.op == "lookup":
                identity = {k: evaluate(e) for k, e in step.identity.items()}
                context = {k: evaluate(e) for k, e in step.context.items()}
                subjects[step.id] = [
                    {"entity_id": step.entity_id, "identity": identity, "context": context}
                ]
                result = (
                    graph.lookup(step.entity_id, identity, context)
                    if identity
                    else graph.collection(step.entity_id, context)
                )
                row_contexts[step.id] = [deepcopy(context) for _ in result.records]
            elif step.op == "decision":
                result = [item for identifier in step.inputs for item in values[identifier]]
            else:
                source = values[step.input]
                result = deepcopy(source)
                source_fields = plans[step.input]["fields"]
                row_contexts[step.id] = deepcopy(row_contexts[step.input])
                subjects[step.id] = deepcopy(subjects[step.input])
                pending[step.id] = deepcopy(pending[step.input])

                def dependency(detail, row=None, index=None):
                    if detail.get("source") != "field":
                        return deepcopy(detail)
                    return {
                        **detail,
                        "entity_id": source.entity_id,
                        "identity": {key: row[key] for key in source.identity if key in row},
                        "context": deepcopy(row_contexts[step.input][index]),
                    }

                def evaluate_row(expression, row, index):
                    try:
                        return evaluate(expression, row, source_fields)
                    except MissingValue as error:
                        raise MissingValue(dependency(error.detail, row, index)) from error

                if step.op == "filter":
                    selected = []
                    for index, row in enumerate(source.records):
                        outcomes, gaps = [], []
                        for cid in step.constraint_ids:
                            predicate = constraints[cid].predicate
                            try:
                                ok = _compare(
                                    predicate.operator,
                                    evaluate_row(predicate.left, row, index),
                                    evaluate_row(predicate.right, row, index),
                                )
                                outcomes.append("true" if ok else "false")
                            except MissingValue as error:
                                outcomes.append("unknown")
                                gaps.append(error.detail)
                        if "false" in outcomes:
                            continue
                        if "unknown" in outcomes:
                            raise MissingValue(gaps[0])
                        selected.append(index)
                    result.records = [source.records[index] for index in selected]
                    row_contexts[step.id] = [row_contexts[step.input][index] for index in selected]
                elif step.op == "assert":
                    checks = []
                    for cid in step.constraint_ids:
                        predicate = constraints[cid].predicate
                        outcomes, gaps = [], deepcopy(pending[step.input])
                        outcomes.extend(
                            "false" if gap.get("reason") == "subject_absent" else "unknown"
                            for gap in gaps
                        )
                        for index, row in enumerate(source.records):
                            try:
                                ok = _compare(
                                    predicate.operator,
                                    evaluate(predicate.left, row, source_fields),
                                    evaluate(predicate.right, row, source_fields),
                                )
                                outcomes.append("true" if ok else "false")
                            except MissingValue as error:
                                outcomes.append("unknown")
                                gaps.append(dependency(error.detail, row, index))
                        if not source.records:
                            outcomes.append("false" if source.complete else "unknown")
                            for subject in subjects[step.input]:
                                gaps.append(
                                    {
                                        "source": "graph",
                                        **deepcopy(subject),
                                        "reason": "subject_absent"
                                        if source.complete
                                        else "subject_unobserved",
                                    }
                                )
                        if not source.complete:
                            outcomes.append("unknown")
                        value = (
                            "false"
                            if "false" in outcomes
                            else "unknown"
                            if "unknown" in outcomes
                            else "true"
                        )
                        checks.append(
                            {
                                "condition_id": cid,
                                "value": value,
                                "missing": gaps,
                                "evidence_refs": deepcopy(source.evidence),
                            }
                        )
                    result = checks
                    conditions.extend(checks)
                elif step.op == "traverse":
                    relation = relations[step.relation_id]
                    start, end = ("from", "to") if step.direction == "forward" else ("to", "from")
                    target_id = getattr(relation, end + "_entity")
                    target_key = getattr(relation, end + "_property")
                    rows, refs, complete = [], list(source.evidence), source.complete
                    row_contexts[step.id], subjects[step.id] = [], []
                    for index, row in enumerate(source.records):
                        key = row.get(getattr(relation, start + "_property"), MISSING)
                        if key is MISSING or key is None:
                            complete = False
                            pending[step.id].append(
                                dependency(
                                    {
                                        "source": "field",
                                        "property": getattr(relation, start + "_property"),
                                        "reason": "unavailable"
                                        if key is MISSING
                                        else "known_absent",
                                    },
                                    row,
                                    index,
                                )
                            )
                            continue
                        try:
                            context = {
                                k: evaluate_row(e, row, index) for k, e in step.context.items()
                            }
                        except MissingValue as error:
                            complete = False
                            pending[step.id].append(error.detail)
                            continue
                        target = (
                            graph.lookup(target_id, {target_key: key}, context)
                            if entities[target_id].identity_keys == [target_key]
                            else graph.collection(target_id, context)
                        )
                        subject = {
                            "entity_id": target_id,
                            "identity": {target_key: key},
                            "context": deepcopy(context),
                        }
                        subjects[step.id].append(subject)
                        matched = [r for r in target.records if r.get(target_key, MISSING) == key]
                        for matched_row in matched:
                            if not any(
                                existing == matched_row and existing_context == context
                                for existing, existing_context in zip(
                                    rows, row_contexts[step.id], strict=True
                                )
                            ):
                                rows.append(matched_row)
                                row_contexts[step.id].append(deepcopy(context))
                        if not target.complete:
                            pending[step.id].append(
                                {
                                    "source": "graph",
                                    **subject,
                                    "reason": "subject_unobserved"
                                    if not matched
                                    else "incomplete_scope",
                                }
                            )
                        elif not matched:
                            pending[step.id].append(
                                {"source": "graph", **subject, "reason": "subject_absent"}
                            )
                        refs.extend(target.evidence)
                        complete = complete and target.complete
                    if not source.records:
                        subjects[step.id] = deepcopy(subjects[step.input])
                    result = RecordSet(
                        target_id, rows, complete, refs, tuple(entities[target_id].identity_keys)
                    )
                elif step.op == "project":
                    result.records = [
                        {f.name: evaluate_row(f.expression, row, index) for f in step.fields}
                        for index, row in enumerate(source.records)
                    ]
                elif step.op == "aggregate":
                    if not source.complete:
                        raise MissingValue(
                            {"reason": "complete_scope_required", "entity_id": source.entity_id}
                        )
                    operands = (
                        [
                            evaluate_row(step.expression, row, index)
                            for index, row in enumerate(source.records)
                        ]
                        if step.expression
                        else []
                    )
                    result = (
                        len(source.records)
                        if step.operation == "count"
                        else sum(operands)
                        if step.operation == "sum"
                        else (min(operands) if step.operation == "min" else max(operands))
                        if operands
                        else None
                    )
                    if result is not None and not _scalar(result, "integer"):
                        raise ValueError("Aggregate result is outside the supported integer range.")
                    scalar_evidence = deepcopy(source.evidence)
                elif step.op == "select_min":
                    if not source.complete:
                        raise MissingValue(
                            {"reason": "complete_scope_required", "entity_id": source.entity_id}
                        )
                    ordered = sorted(
                        enumerate(source.records),
                        key=lambda item: tuple(
                            evaluate_row(e, item[1], item[0]) for e in step.order_by
                        ),
                    )[:1]
                    result.records = [row for _, row in ordered]
                    row_contexts[step.id] = [
                        row_contexts[step.input][index] for index, _ in ordered
                    ]
            values[step.id] = result
            event = {"step_id": step.id, "operator": step.op}
            if isinstance(result, RecordSet):
                event.update(complete=result.complete, output_count=len(result.records))
            trace.append(event)
        except MissingValue as error:
            detail = error.detail
            missing.append(detail)
            if function.output.kind != "decision":
                return {
                    "status": "incomplete",
                    "value": None,
                    "issues": [str(error)],
                    "trace": trace,
                    "evidence_refs": [],
                    "missing_dependencies": missing,
                    "graph_revision": graph.revision,
                }
            entity_id = plans[step.id]["entity"] or ""
            values[step.id] = RecordSet(
                entity_id,
                [],
                False,
                [],
                tuple(entities[entity_id].identity_keys) if entity_id else (),
            )
            pending[step.id].append(detail)
        except IncompleteEvidence as error:
            raise ValueError(str(error)) from error
    returned = values[function.return_step]
    if function.output.kind == "decision":
        return {
            "status": combine_conditions(returned),
            "conditions": returned,
            "trace": trace,
            "missing_dependencies": missing
            + [m for c in returned if c["value"] == "unknown" for m in c["missing"]],
            "evidence_refs": [e for c in returned for e in c["evidence_refs"]],
            "graph_revision": graph.revision,
        }
    value = returned.records if isinstance(returned, RecordSet) else returned
    if function.output.kind == "rows":
        gaps = []
        for index, row in enumerate(value):
            for field in function.output.fields:
                if field.name not in row:
                    gaps.append(
                        {
                            "source": "field",
                            "entity_id": returned.entity_id,
                            "identity": {key: row[key] for key in returned.identity if key in row},
                            "context": deepcopy(row_contexts[function.return_step][index]),
                            "property": field.name,
                            "reason": "unavailable",
                        }
                    )
                elif not _scalar(row[field.name], field.type, field.nullable):
                    raise ValueError("Function result does not match its row output type.")
        if gaps:
            return {
                "status": "incomplete",
                "value": None,
                "issues": ["A returned property is unavailable."],
                "trace": trace,
                "evidence_refs": deepcopy(returned.evidence),
                "missing_dependencies": gaps,
                "graph_revision": graph.revision,
            }
    if function.output.kind == "scalar" and not _scalar(
        value, function.output.type, function.output.nullable
    ):
        raise ValueError("Function result does not match its scalar output type.")
    return {
        "status": "complete",
        "value": value,
        "issues": [],
        "trace": trace,
        "evidence_refs": returned.evidence if isinstance(returned, RecordSet) else scalar_evidence,
        "graph_revision": graph.revision,
        "coverage": "observed"
        if isinstance(returned, RecordSet) and not returned.complete
        else "complete",
    }
