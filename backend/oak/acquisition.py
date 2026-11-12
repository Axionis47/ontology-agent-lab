"""Derive evidence needs and check source arguments before external transport."""

from copy import deepcopy

from oak.discovery_validation import digest
from oak.repair_executor import MISSING, IncompleteEvidence, _pointer


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def dependencies(candidate, function_ids):
    entities = {e.id: e for e in candidate.schema.entities}
    relations = {r.id: r for r in candidate.schema.relations}
    constraints = {c.id: c for c in candidate.constraints}
    needs = []
    for function in candidate.functions:
        if function.id not in function_ids:
            continue
        raw = function.model_dump(mode="json")
        nodes = list(walk(raw))
        cids = {cid for n in nodes for cid in n.get("constraint_ids", [])}
        nodes += [n for cid in cids for n in walk(constraints[cid].model_dump(mode="json"))]
        selected = set()
        for step in function.steps:
            if step.op == "lookup":
                selected.update(
                    step.entity_types or ([step.entity_id] if step.entity_id else entities)
                )
            if step.op == "traverse":
                for rid in step.relation_ids or (
                    [step.relation_id] if step.relation_id else relations
                ):
                    selected.update((relations[rid].from_entity, relations[rid].to_entity))
        selected.update(n["entity_id"] for n in nodes if n.get("entity_id") in entities)
        for entity_id in sorted(selected):
            entity = entities[entity_id]
            props = {p.name for p in entity.properties}
            fields = set(entity.identity_keys)
            fields.update(
                n["name"] for n in nodes if n.get("kind") == "field" and n.get("name") in props
            )
            for n in nodes:
                fields.update(k for k in n.get("property_filters", {}) if k in props)
                fields.update(k for k in n.get("name_fields", []) if k in props)
                fields.update(k for k in n.get("text_fields", []) if k in props)
                if n.get("group_by") in props:
                    fields.add(n["group_by"])
            for relation in relations.values():
                if relation.from_entity in selected and relation.to_entity in selected:
                    if relation.from_entity == entity_id:
                        fields.add(relation.from_property)
                    if relation.to_entity == entity_id:
                        fields.add(relation.to_property)
            if function.output.kind == "entities":
                fields.update(props)
            needs.append(
                {
                    "function_id": function.id,
                    "entity_id": entity_id,
                    "properties": sorted(fields),
                    "complete_required": any(
                        n.get("op") in {"aggregate", "select_min"} for n in nodes
                    ),
                }
            )
    return needs


def value(expression, request, arguments):
    if expression.kind == "request":
        return request.get(expression.name, MISSING)
    if expression.kind == "argument":
        return arguments.get(expression.name, MISSING)
    if expression.kind in {"literal", "typed_literal"}:
        return expression.value
    raise ValueError(
        "Source selectors support request values, bound arguments, and typed constants."
    )


def validate_access(candidate, tools=None, *, required=False):
    mappings = {m.id: m for m in candidate.mappings}
    request_names = {r.name for r in candidate.request_fields}
    for binding in candidate.operation_bindings:
        access = binding.source_access
        if access is None:
            if required:
                raise ValueError("Each operation requires a supported source-access declaration.")
            continue
        if not set(access.mapping_ids) <= mappings.keys() or any(
            mappings[m].tool_id != binding.tool_id for m in access.mapping_ids
        ):
            raise ValueError("Source access refers to an unrelated mapping.")
        if access.kind == "data" and not access.mapping_ids:
            raise ValueError("Data acquisition requires a record mapping.")
        if access.kind == "action" and access.pagination:
            raise ValueError("An external action cannot be repeated to obtain evidence pages.")
        paths = [f.path for f in access.filters]
        if len(paths) != len(set(paths)):
            raise ValueError("A source selector path cannot repeat.")
        for selector in access.filters:
            if selector.value.kind not in {"request", "argument", "literal", "typed_literal"}:
                raise ValueError(
                    "Source selectors cannot execute expressions or read unbound facts."
                )
            if selector.value.kind == "request" and selector.value.name not in request_names:
                raise ValueError("Source selector refers to an unknown request field.")
            if access.kind == "data" and not any(
                any(
                    s.source == "arguments" and s.path == selector.path for s in mappings[mid].scope
                )
                for mid in access.mapping_ids
            ):
                raise ValueError("A source filter must remain part of its mapped evidence scope.")
        if access.projection_path and not access.projection_fields:
            raise ValueError("Field selection requires declared source field names.")
        for key in access.projection_fields:
            if not any(
                key == m.entity_id + "." + f.property
                for mid in access.mapping_ids
                for m in [mappings[mid]]
                for f in m.fields
            ):
                raise ValueError("Projection refers to an unmapped property.")
        if access.pagination:
            page_paths = {access.pagination.cursor_path, access.pagination.size_path}
            paths.append(access.pagination.cursor_path)
            if access.pagination.size_path:
                paths.append(access.pagination.size_path)
            for mid in access.mapping_ids:
                if any(
                    s.source == "arguments" and s.path in page_paths for s in mappings[mid].scope
                ):
                    raise ValueError("Pagination arguments cannot define entity scope.")
        if access.projection_path:
            paths.append(access.projection_path)
        paths.extend(access.fixed_arguments)
        if any(not p.startswith("/") for p in paths):
            raise ValueError("Source argument paths must be non-root JSON Pointers.")
        if any(
            p == c or p.startswith(c + "/") or c.startswith(p + "/")
            for p in paths
            for c in binding.credential_paths
        ):
            raise ValueError("Credentials cannot supply acquisition selectors.")
        if tools is not None and binding.tool_id in tools:
            tool = tools[binding.tool_id]
            if (
                access.kind == "action"
                and (tool.get("annotations") or {}).get("readOnlyHint") is True
            ):
                raise ValueError(
                    "A declared read tool cannot bypass acquisition checks as an action."
                )
            for path in paths:
                node = tool["input_schema"]
                for part in path[1:].split("/"):
                    key = part.replace("~1", "/").replace("~0", "~")
                    node = node.get("properties", {}).get(key)
                    if not isinstance(node, dict):
                        raise ValueError(
                            "A source selector is absent from its native input schema."
                        )


class Acquisition:
    def __init__(self, candidate, request, graph):
        self.candidate, self.request, self.graph = candidate, request, graph
        self.selections = deepcopy(request.get("functions", []))
        self.needs = dependencies(candidate, {s["function_id"] for s in self.selections})

    def bind_function(self, function_id, arguments):
        for selection in self.selections:
            if selection["function_id"] == function_id:
                if any(
                    k in arguments and arguments[k] != v
                    for k, v in selection.get("arguments", {}).items()
                ):
                    raise ValueError("Function arguments changed the checked request values.")
                selection["arguments"] = {**selection.get("arguments", {}), **deepcopy(arguments)}
                return

    def check(self, binding, arguments):
        access = binding.source_access
        if access is None or access.kind == "action":
            return {"status": "allowed", "kind": "action" if access else "legacy"}
        mappings = [m for m in self.candidate.mappings if m.id in access.mapping_ids]
        needs = [n for n in self.needs if any(m.entity_id == n["entity_id"] for m in mappings)]
        # An operation's own decision can request facts before it can execute.
        if not needs and not self.selections:
            needs = [
                n
                for n in dependencies(
                    self.candidate,
                    {c.function_id for b in self.candidate.operation_bindings for c in b.checks},
                )
                if any(m.entity_id == n["entity_id"] for m in mappings)
            ]
        if not needs:
            raise ValueError(
                "The data call does not serve a selected function or action dependency."
            )
        parameters_by_function = {s["function_id"]: s.get("arguments", {}) for s in self.selections}
        matching = []
        for need in needs:
            parameters = parameters_by_function.get(need["function_id"], {})
            matches = True
            for selector in access.filters:
                expected = value(selector.value, self.request["values"], parameters)
                actual = _pointer(arguments, selector.path)
                if expected is MISSING or type(actual) is not type(expected) or actual != expected:
                    matches = False
                    break
            if matches:
                matching.append(need)
        if not matching:
            raise ValueError(
                "Source filters do not match the checked query or bound function inputs."
            )
        needs = matching
        for path, expected in access.fixed_arguments.items():
            if _pointer(arguments, path) != expected:
                raise ValueError("A required source argument changed: " + path)
        allowed_paths = (
            [f.path for f in access.filters]
            + list(access.fixed_arguments)
            + list(binding.credential_paths)
        )
        if access.projection_path:
            allowed_paths.append(access.projection_path)
        if access.pagination:
            allowed_paths.extend(
                p for p in (access.pagination.cursor_path, access.pagination.size_path) if p
            )

        def checked_fields(node, path=""):
            if path in allowed_paths:
                return
            if not isinstance(node, dict):
                raise ValueError("An acquisition argument has no source-access binding: " + path)
            for key, child in node.items():
                checked_fields(child, path + "/" + key.replace("~", "~0").replace("/", "~1"))

        checked_fields(arguments)
        fields = {n["entity_id"] + "." + p for n in needs for p in n["properties"]}
        if access.projection_path:
            if not fields <= access.projection_fields.keys():
                raise ValueError("The source projection cannot supply required evidence fields.")
            required = {access.projection_fields[f] for f in fields}
            actual = _pointer(arguments, access.projection_path)
            if not isinstance(actual, list) or set(actual) != required:
                raise ValueError(
                    "Source projection must contain exactly the required evidence fields."
                )
        remaining = []
        for need in needs:
            parameters = parameters_by_function.get(need["function_id"], {})
            satisfied = False
            for mapping in mappings:
                if mapping.entity_id != need["entity_id"]:
                    continue
                context = {}
                for scope in mapping.scope:
                    if scope.source != "arguments":
                        break
                    context[scope.name] = _pointer(arguments, scope.path)
                else:
                    try:
                        collection = self.graph.collection(mapping.entity_id, context)
                        function = next(
                            f for f in self.candidate.functions if f.id == need["function_id"]
                        )
                        for step in function.steps:
                            if (
                                step.op == "lookup"
                                and step.entity_id == mapping.entity_id
                                and step.identity
                            ):
                                identity = {
                                    k: value(v, self.request["values"], parameters)
                                    for k, v in step.identity.items()
                                }
                                if all(v is not MISSING for v in identity.values()):
                                    collection = self.graph.lookup(
                                        mapping.entity_id, identity, context
                                    )
                        satisfied = (
                            (bool(collection.records) or collection.complete)
                            and (not need["complete_required"] or collection.complete)
                            and all(
                                all(p in row for p in need["properties"])
                                for row in collection.records
                            )
                        )
                    except (ValueError, KeyError, TypeError, IncompleteEvidence):
                        pass
                if satisfied:
                    break
            if not satisfied:
                remaining.append(need)
        if not remaining:
            raise ValueError("The required evidence is already available in this query scope.")
        page = access.pagination
        if page:
            self.graph.check_page(binding, arguments)
        return {
            "status": "allowed",
            "needs": deepcopy(remaining),
            "need_id": digest(remaining),
            "unsupported": list(access.unsupported),
            "source_access": binding.id,
        }
