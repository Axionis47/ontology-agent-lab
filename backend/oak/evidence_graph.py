"""Maintain observed entity facts and execute fixed plans on one graph revision."""

import json
from copy import deepcopy

from oak.discovery_validation import digest
from oak.kernel_values import source_value
from oak.repair_executor import (
    MAX_RECORDS,
    MISSING,
    IncompleteEvidence,
    RecordedObservation,
    RecordSet,
    _pointer,
    _scalar,
    execute_function,
    validate_candidate,
)
from oak.repair_schemas import Candidate


class GraphIngestionError(ValueError):
    """A response cannot be published as one graph update."""

    def __init__(self, issues):
        self.issues = deepcopy(issues)
        super().__init__("The tool response did not pass graph mapping validation.")


class EvidenceGraph:
    """Keep source observations separate from the latest observed property values."""

    def __init__(self, candidate):
        self.candidate = Candidate.model_validate(candidate).model_copy(deep=True)
        self.definition = self.candidate.model_dump(mode="json")
        self.scoped = self.definition["version"] in {"oak.candidate.v2", "oak.candidate.v3"}
        tools = {mapping.tool_id for mapping in self.candidate.mappings}
        tools.update(binding.tool_id for binding in self.candidate.schema.bindings)
        tools.update(operation.tool_id for operation in self.candidate.schema.operations)
        tools.update(t for r in self.candidate.requirements.requirements for t in r.tool_ids)
        errors = validate_candidate(
            self.candidate, tools, {r.id for r in self.candidate.requirements.requirements}
        )
        if errors:
            raise ValueError(errors[0])
        self.entities = {entity["id"]: entity for entity in self.definition["schema"]["entities"]}
        self.revision = 0
        self.observations = {}
        self.observation_scopes = {}
        self.observation_arguments = {}
        self.records = {entity: {} for entity in self.entities}
        self.complete = {entity: False for entity in self.entities}
        self.scopes = {entity: set() for entity in self.entities}
        self.members = {}
        self.collection_evidence = {}
        self.history = []
        self.scoped_coverage = {entity: {} for entity in self.entities}
        self.scope_names = {entity: set() for entity in self.entities}
        self.page_sequences = {}
        declared_scopes = {}
        if self.scoped:
            for mapping in self.definition["mappings"]:
                names = frozenset(item["name"] for item in mapping.get("scope", []))
                entity = mapping["entity_id"]
                if len(names) != len(mapping.get("scope", [])):
                    raise ValueError("A mapping cannot repeat a scope name.")
                if entity in declared_scopes and declared_scopes[entity] != names:
                    raise ValueError("Mappings of one entity must use the same scope names.")
                declared_scopes[entity] = names
                self.scope_names[entity] = names

    def add(self, observation, *, arguments=None, scope="") -> dict:
        """Publish all mapped changes together. Failed ingestion changes no graph state."""
        raw = (
            observation.model_dump(mode="json")
            if hasattr(observation, "model_dump")
            else deepcopy(observation)
        )
        embedded_arguments = raw.pop("arguments", None)
        if arguments is not None and embedded_arguments is not None:
            if arguments != embedded_arguments:
                raise ValueError("The observation arguments do not match the actual call.")
        arguments = deepcopy(arguments if arguments is not None else embedded_arguments or {})
        if not isinstance(arguments, dict):
            raise ValueError("Observation arguments must be an object.")
        json.dumps(arguments, allow_nan=False)
        observed = RecordedObservation.model_validate(raw).model_dump(mode="json")
        previous = self.observations.get(observed["id"])
        if previous is not None:
            if (
                previous != observed
                or self.observation_scopes[observed["id"]] != scope
                or self.observation_arguments[observed["id"]] != arguments
            ):
                raise ValueError("An observation ID cannot identify different evidence.")
            return {"revision": self.revision, "changes": [], "issues": [], "duplicate": True}

        # The dispatcher uses one graph per serial episode. Stage only mutable state.
        state_names = (
            "revision",
            "observations",
            "observation_scopes",
            "observation_arguments",
            "records",
            "complete",
            "scopes",
            "members",
            "collection_evidence",
            "history",
            "scoped_coverage",
            "page_sequences",
        )
        staged = object.__new__(type(self))
        staged.__dict__ = self.__dict__.copy()
        for name in state_names:
            setattr(staged, name, deepcopy(getattr(self, name)))
        result = (
            staged._add_scoped(observed, arguments, scope)
            if self.scoped
            else staged._add_legacy(observed, scope=scope)
        )
        staged.observation_arguments[observed["id"]] = arguments
        for name in state_names:
            setattr(self, name, getattr(staged, name))
        return deepcopy(result)

    def _add_legacy(self, observation, *, scope="") -> dict:
        """Apply one actual response. Reapplying its ID does not change the graph."""
        observed = RecordedObservation.model_validate(observation).model_dump(mode="json")
        previous = self.observations.get(observed["id"])
        if previous is not None:
            if previous != observed or self.observation_scopes[observed["id"]] != scope:
                raise ValueError("An observation ID cannot identify different evidence.")
            return {"revision": self.revision, "changes": [], "issues": [], "duplicate": True}
        if len(self.observations) >= 1000:
            raise ValueError("The graph observation limit was reached.")
        self.observations[observed["id"]] = deepcopy(observed)
        self.observation_scopes[observed["id"]] = scope
        self.revision += 1
        changes, issues = [], []
        if observed["status"] != "succeeded":
            return {"revision": self.revision, "changes": changes, "issues": issues}
        for mapping in self.definition["mappings"]:
            if mapping["tool_id"] != observed["tool_id"]:
                continue
            entity_id = mapping["entity_id"]
            entity = self.entities[entity_id]
            source = _pointer(observed["data"], mapping["collection_path"])
            if source is MISSING:
                issues.append({"mapping_id": mapping["id"], "reason": "source_missing"})
                continue
            rows = [source] if isinstance(source, dict) else source
            if not isinstance(rows, list) or len(rows) > MAX_RECORDS:
                issues.append({"mapping_id": mapping["id"], "reason": "invalid_collection"})
                continue
            types = {prop["name"]: prop["type"] for prop in entity["properties"]}
            seen = set()
            valid_collection = True
            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    valid_collection = False
                    issues.append({"mapping_id": mapping["id"], "reason": "invalid_record"})
                    continue
                fields = {
                    field["property"]: _pointer(row, field["path"]) for field in mapping["fields"]
                }
                if any(
                    not _scalar(fields.get(key, MISSING), types[key])
                    for key in entity["identity_keys"]
                ):
                    valid_collection = False
                    issues.append({"mapping_id": mapping["id"], "reason": "invalid_identity"})
                    continue
                key = tuple(fields[name] for name in entity["identity_keys"])
                if key in seen:
                    valid_collection = False
                    issues.append({"mapping_id": mapping["id"], "reason": "duplicate_identity"})
                    # Neither duplicate is authoritative for non-identity properties.
                    record = self.records[entity_id].get(key)
                    if record is not None:
                        record["values"] = {
                            name: value
                            for name, value in record["values"].items()
                            if name in entity["identity_keys"]
                        }
                    continue
                seen.add(key)
                if (
                    key not in self.records[entity_id]
                    and len(self.records[entity_id]) >= MAX_RECORDS
                ):
                    raise ValueError("The graph record limit was reached.")
                record = self.records[entity_id].setdefault(key, {"values": {}, "evidence": {}})
                for field in mapping["fields"]:
                    name, value = field["property"], fields[field["property"]]
                    if value is MISSING:
                        continue
                    path = mapping["collection_path"]
                    if isinstance(source, list):
                        path += f"/{index}"
                    evidence = {
                        "observation_id": observed["id"],
                        "tool_id": observed["tool_id"],
                        "mapping_id": mapping["id"],
                        "path": path + field["path"],
                        "graph_revision": self.revision,
                    }
                    valid = _scalar(value, types[name])
                    if not valid:
                        issues.append(
                            {
                                "mapping_id": mapping["id"],
                                "property": name,
                                "reason": "null" if value is None else "invalid_type",
                            }
                        )
                    prior = record["evidence"].get(name)
                    if valid:
                        record["values"][name] = deepcopy(value)
                    else:
                        # An invalid later value cannot leave an older value usable as current.
                        record["values"].pop(name, None)
                    record["evidence"][name] = evidence
                    change = {
                        "entity_id": entity_id,
                        "identity": list(key),
                        "property": name,
                        "value": deepcopy(value),
                        "valid": valid,
                        "evidence": evidence,
                        "supersedes": prior,
                    }
                    changes.append(change)
                    self.history.append(deepcopy(change))
            self.scopes[entity_id].add((mapping["id"], scope))
            complete = (
                valid_collection
                and observed["coverage"] == "complete"
                and isinstance(source, list)
                and len(self.scopes[entity_id]) == 1
            )
            self.complete[entity_id] = complete
            if complete:
                self.members[entity_id] = seen
                self.collection_evidence[entity_id] = {
                    "observation_id": observed["id"],
                    "tool_id": observed["tool_id"],
                    "mapping_id": mapping["id"],
                    "path": mapping["collection_path"],
                    "graph_revision": self.revision,
                }
            else:
                self.members.pop(entity_id, None)
                self.collection_evidence.pop(entity_id, None)
        return {"revision": self.revision, "changes": changes, "issues": issues}

    @staticmethod
    def _context_key(context):
        return json.dumps(context, sort_keys=True, separators=(",", ":"), allow_nan=False)

    def _query_context(self, entity_id, context):
        if entity_id not in self.entities:
            raise ValueError("Unknown graph entity.")
        if not isinstance(context, dict):
            raise ValueError("Graph context must be an object.")
        selected = {}
        for name in sorted(self.scope_names[entity_id]):
            value = context.get(name, MISSING)
            if not any(_scalar(value, kind) for kind in ("string", "integer", "boolean")):
                raise IncompleteEvidence(f"The required graph context is unavailable: {name}.")
            selected[name] = value
        return selected

    @staticmethod
    def _mapping_error(mapping, reason, **details):
        raise GraphIngestionError([{"mapping_id": mapping["id"], "reason": reason, **details}])

    def _mapping_context(self, mapping, observed, arguments):
        context = {}
        for item in mapping.get("scope", []):
            source = arguments if item["source"] == "arguments" else observed["data"]
            value = _pointer(source, item["path"])
            if not any(_scalar(value, kind) for kind in ("string", "integer", "boolean")):
                self._mapping_error(mapping, "invalid_context", name=item["name"])
            context[item["name"]] = value
        return context

    def _mapping_complete(self, mapping, observed, source):
        contract = mapping.get("coverage")
        if not contract or not isinstance(source, list):
            return False
        if not contract.get("support"):
            self._mapping_error(mapping, "unsupported_coverage")
        if contract["kind"] == "complete_response":
            return True
        value = _pointer(observed["data"], contract["path"])
        if value is MISSING:
            return False
        if type(value) is not bool:
            self._mapping_error(mapping, "invalid_coverage_flag")
        return value

    def _page_key(self, binding, arguments):
        selected = deepcopy(arguments)
        page = binding.source_access.pagination
        for path in (page.cursor_path, page.size_path):
            if not path:
                continue
            parts = [p.replace("~1", "/").replace("~0", "~") for p in path[1:].split("/")]
            node = selected
            for part in parts[:-1]:
                node = node.get(part, {})
            node.pop(parts[-1], None)
        return binding.id + ":" + digest(selected)

    def check_page(self, binding, arguments):
        page = binding.source_access.pagination
        key = self._page_key(binding, arguments)
        sequence = self.page_sequences.get(key)
        expected = (
            sequence["next_cursor"]
            if sequence and not sequence["finished"]
            else page.initial_cursor
        )
        actual = _pointer(arguments, page.cursor_path)
        actual = None if actual is MISSING else actual
        if type(actual) is not type(expected) or actual != expected:
            raise ValueError("The page cursor does not match the saved continuation.")
        if page.size_path:
            count = _pointer(arguments, page.size_path)
            if type(count) is not int or not 1 <= count <= page.max_size:
                raise ValueError("The requested page size exceeds its supported bound.")
        return key

    def _add_scoped(self, observed, arguments, scope):
        if len(self.observations) >= 1000:
            raise ValueError("The graph observation limit was reached.")
        self.observations[observed["id"]] = deepcopy(observed)
        self.observation_scopes[observed["id"]] = scope
        self.revision += 1
        changes = []
        if observed["status"] != "succeeded":
            return {"revision": self.revision, "changes": changes, "issues": []}

        paged = next(
            (
                b
                for b in self.candidate.operation_bindings
                if b.tool_id == observed["tool_id"]
                and b.source_access
                and b.source_access.pagination
            ),
            None,
        )
        sequence = None
        refresh = False
        if paged:
            page_key = self.check_page(paged, arguments)
            page = paged.source_access.pagination
            cursor = _pointer(arguments, page.cursor_path)
            cursor = None if cursor is MISSING else cursor
            next_cursor = _pointer(observed["data"], page.next_cursor_path)
            if next_cursor is MISSING or (
                next_cursor is not None and type(next_cursor) not in {str, int}
            ):
                raise ValueError("The response has no valid page continuation.")
            refresh = bool(self.page_sequences.get(page_key, {}).get("finished"))
            if refresh:
                # Start a new page population. Preserve old observations as history.
                del self.page_sequences[page_key]
            sequence = self.page_sequences.setdefault(
                page_key,
                {
                    "next_cursor": page.initial_cursor,
                    "finished": False,
                    "cursors": [],
                    "members": {},
                    "rows": {},
                    "observations": [],
                },
            )
            if (
                cursor in sequence["cursors"]
                or next_cursor is not None
                and next_cursor in [cursor, *sequence["cursors"]]
            ):
                raise ValueError("The source repeated a pagination cursor.")
            sequence["cursors"].append(cursor)
            sequence["next_cursor"] = next_cursor
            sequence["finished"] = next_cursor is None
            sequence["observations"].append(observed["id"])

        updates, supplied, touched_subjects = {}, {}, set()
        for mapping in self.definition["mappings"]:
            if mapping["tool_id"] != observed["tool_id"]:
                continue
            entity_id = mapping["entity_id"]
            entity = self.entities[entity_id]
            context = self._mapping_context(mapping, observed, arguments)
            context_key = self._context_key(context)
            source = _pointer(observed["data"], mapping["collection_path"])
            rows = [source] if isinstance(source, dict) else source
            if not isinstance(rows, list) or len(rows) > MAX_RECORDS:
                self._mapping_error(mapping, "invalid_collection")
            if mapping.get("update_mode", "replacement") == "partial":
                if not mapping.get("update_support"):
                    self._mapping_error(mapping, "unsupported_partial_update")
            types = {prop["name"]: prop["type"] for prop in entity["properties"]}
            seen = set()
            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    self._mapping_error(mapping, "invalid_record", index=index)
                fields = {
                    field["property"]: _pointer(row, field["path"]) for field in mapping["fields"]
                }
                if any(
                    not _scalar(fields.get(name, MISSING), types[name])
                    for name in entity["identity_keys"]
                ):
                    self._mapping_error(mapping, "invalid_identity", index=index)
                identity = tuple(fields[name] for name in entity["identity_keys"])
                if identity in seen:
                    self._mapping_error(mapping, "duplicate_identity", index=index)
                seen.add(identity)
                page_mapping = (
                    sequence is not None and mapping["id"] in paged.source_access.mapping_ids
                )
                if page_mapping:
                    row_key = (mapping["id"], context_key, identity)
                    old = sequence["rows"].get(row_key)
                    if old is not None:
                        if old != row:
                            self._mapping_error(mapping, "conflicting_page_record", index=index)
                        continue
                    sequence["rows"][row_key] = deepcopy(row)
                key = (context_key, identity)
                if (
                    key not in self.records[entity_id]
                    and len(self.records[entity_id]) >= MAX_RECORDS
                ):
                    self._mapping_error(mapping, "record_limit")
                subject = (entity_id, context_key, identity)
                previous_members = (
                    self.scoped_coverage[entity_id].get(context_key, {}).get("members", set())
                )
                if subject not in touched_subjects and identity not in previous_members:
                    # A subject that returns after observed absence starts a new fact set.
                    self.records[entity_id].pop(key, None)
                touched_subjects.add(subject)
                record = self.records[entity_id].setdefault(
                    key, {"identity": identity, "context": context, "values": {}, "evidence": {}}
                )
                for field in mapping["fields"]:
                    name = field["property"]
                    value = fields[name]
                    missing = value is MISSING
                    if missing and mapping.get("update_mode", "replacement") == "partial":
                        continue
                    spec = next(
                        p
                        for e in self.candidate.schema.entities
                        if e.id == entity_id
                        for p in e.properties
                        if p.name == name
                    )
                    if not missing and not _scalar(value, types[name], item_type=spec.item_type):
                        self._mapping_error(mapping, "invalid_property", property=name, index=index)
                    if not missing and self.candidate.version == "oak.candidate.v3":
                        value = source_value(value, spec)
                    fact_key = (entity_id, context_key, identity, name)
                    supplied_value = (missing, None if missing else value)
                    if fact_key in supplied and supplied[fact_key] != supplied_value:
                        self._mapping_error(mapping, "conflicting_property", property=name)
                    supplied[fact_key] = supplied_value
                    path = mapping["collection_path"]
                    if isinstance(source, list):
                        path += f"/{index}"
                    evidence = {
                        "observation_id": observed["id"],
                        "tool_id": observed["tool_id"],
                        "mapping_id": mapping["id"],
                        "path": path + field["path"],
                        "graph_revision": self.revision,
                        "context": deepcopy(context),
                    }
                    if missing:
                        evidence["missing"] = True
                    prior = record["evidence"].get(name)
                    if missing:
                        record["values"].pop(name, None)
                    else:
                        record["values"][name] = deepcopy(value)
                    record["evidence"][name] = evidence
                    change = {
                        "entity_id": entity_id,
                        "identity": list(identity),
                        "context": deepcopy(context),
                        "property": name,
                        "value": None if missing else deepcopy(value),
                        "valid": not missing,
                        "evidence": evidence,
                        "supersedes": prior,
                    }
                    if missing:
                        change["reason"] = "property_missing"
                    changes.append(change)
                    self.history.append(deepcopy(change))
            update = updates.setdefault(
                (entity_id, context_key),
                {
                    "context": context,
                    "observed": set(),
                    "complete_sets": [],
                    "evidence": [],
                    "refresh": False,
                },
            )
            update["observed"].update(seen)
            page_mapping = sequence is not None and mapping["id"] in paged.source_access.mapping_ids
            if page_mapping:
                update["refresh"] = refresh
                page_members = sequence["members"].setdefault((mapping["id"], context_key), set())
                page_members.update(seen)
                update["observed"].update(page_members)
            if self._mapping_complete(mapping, observed, source) and (
                not page_mapping or sequence["finished"]
            ):
                update["complete_sets"].append(set(page_members) if page_mapping else seen)
                update["evidence"].append(
                    {
                        "observation_id": observed["id"],
                        "tool_id": observed["tool_id"],
                        "mapping_id": mapping["id"],
                        "path": mapping["collection_path"],
                        "graph_revision": self.revision,
                        "context": deepcopy(context),
                        "coverage": "complete",
                    }
                )

        for (entity_id, context_key), update in updates.items():
            previous = (
                {} if update["refresh"] else self.scoped_coverage[entity_id].get(context_key, {})
            )
            complete_sets = update["complete_sets"]
            if complete_sets:
                members = complete_sets[0]
                if any(members != other for other in complete_sets[1:]):
                    raise GraphIngestionError(
                        [{"entity_id": entity_id, "reason": "conflicting_coverage"}]
                    )
                if not update["observed"] <= members:
                    raise GraphIngestionError(
                        [{"entity_id": entity_id, "reason": "conflicting_coverage"}]
                    )
                complete = True
            else:
                members = previous.get("members", set()) | update["observed"]
                complete = False
            self.scoped_coverage[entity_id][context_key] = {
                "context": deepcopy(update["context"]),
                "members": deepcopy(members),
                "complete": complete,
                "evidence": deepcopy(update["evidence"]),
            }
        return {
            "revision": self.revision,
            "changes": changes,
            "issues": [],
            "page_coverage": {
                "next_cursor": sequence["next_cursor"],
                "finished": sequence["finished"],
                "observations": sequence["observations"],
            }
            if sequence
            else None,
        }

    def collection(self, entity_id, context=None):
        """Read one declared scope. Extra request fields do not change its meaning."""
        if not self.scoped:
            return self._collection(entity_id)
        context = self._query_context(entity_id, context or {})
        context_key = self._context_key(context)
        state = self.scoped_coverage[entity_id].get(context_key, {})
        selected = [
            self.records[entity_id][(context_key, identity)]
            for identity in sorted(state.get("members", set()), key=repr)
        ]
        evidence = [ref for record in selected for ref in record["evidence"].values()]
        evidence.extend(state.get("evidence", []))
        return RecordSet(
            entity_id,
            [deepcopy(record["values"]) for record in selected],
            state.get("complete", False),
            deepcopy(evidence),
            tuple(self.entities[entity_id]["identity_keys"]),
        )

    def lookup(self, entity_id, identity, context=None):
        """Read an exact subject. Empty incomplete results do not establish absence."""
        if entity_id not in self.entities:
            raise ValueError("Unknown graph entity.")
        entity = self.entities[entity_id]
        types = {prop["name"]: prop["type"] for prop in entity["properties"]}
        if not isinstance(identity, dict) or set(identity) != set(entity["identity_keys"]):
            raise ValueError("A lookup requires the exact declared identity fields.")
        if any(not _scalar(value, types[name]) for name, value in identity.items()):
            raise ValueError("A lookup identity has an invalid type.")
        if self.scoped:
            selected_context = self._query_context(entity_id, context or {})
            context_key = self._context_key(selected_context)
            identity_key = tuple(identity[name] for name in entity["identity_keys"])
            state = self.scoped_coverage[entity_id].get(context_key, {})
            record = (
                self.records[entity_id].get((context_key, identity_key))
                if identity_key in state.get("members", set())
                else None
            )
            evidence = (
                list(record["evidence"].values())
                if record is not None
                else state.get("evidence", [])
            )
            return RecordSet(
                entity_id,
                [deepcopy(record["values"])] if record is not None else [],
                record is not None or state.get("complete", False),
                deepcopy(evidence),
                tuple(entity["identity_keys"]),
            )
        source = self.collection(entity_id, context)
        matching = [
            row
            for row in source.records
            if all(
                type(row.get(name)) is type(value) and row[name] == value
                for name, value in identity.items()
            )
        ]
        if len(matching) > 1:
            raise IncompleteEvidence("The subject has conflicting observed identities.")
        return RecordSet(
            entity_id,
            deepcopy(matching),
            bool(matching) or source.complete,
            deepcopy(source.evidence),
            source.identity,
        )

    def _collection(self, entity_id):
        if self.scoped:
            return self.collection(entity_id)
        records = self.records[entity_id]
        if not records and not self.complete[entity_id]:
            raise IncompleteEvidence(f"No observed records for entity {entity_id}.")
        members = self.members.get(entity_id, records.keys())
        selected = [records[key] for key in members]
        evidence = [ref for record in selected for ref in record["evidence"].values()]
        if entity_id in self.collection_evidence:
            evidence.append(self.collection_evidence[entity_id])
        return RecordSet(
            entity_id,
            [deepcopy(record["values"]) for record in selected],
            self.complete[entity_id],
            deepcopy(evidence),
            tuple(self.entities[entity_id]["identity_keys"]),
        )

    def execute(self, function_id, arguments, *, request=None) -> dict:
        """Run a function on current facts. Do not dispatch a tool to fill a gap."""
        if self.scoped:
            from oak.kernel_execution import execute_v2

            return execute_v2(self.candidate, function_id, arguments, request, self)
        result = execute_function(
            self.candidate,
            function_id,
            arguments,
            [],
            _collection_loader=self._collection,
            _allow_partial_rows=True,
        )
        result["graph_revision"] = self.revision
        result["coverage"] = "observed"
        result["missing_dependencies"] = (
            [{"reason": issue, "sources": self.sources(function_id)} for issue in result["issues"]]
            if result["status"] == "incomplete"
            else []
        )
        return result

    def sources(
        self, function_id=None, *, tool_ids=None, entity_id=None, property=None
    ) -> list[dict]:
        """Describe fixed source mappings used by a function's entity operations."""
        if function_id is None:
            entity_ids = {entity_id} if entity_id is not None else set(self.entities)
            steps = []
        else:
            function = next(item for item in self.candidate.functions if item.id == function_id)
            steps = function.steps
            entity_ids = set()
            for step in steps:
                if step.op == "lookup":
                    entity_ids.update(
                        step.entity_types or ([step.entity_id] if step.entity_id else self.entities)
                    )
        relations = {item.id: item for item in self.candidate.schema.relations}
        for step in steps:
            if step.op == "traverse":
                for rid in step.relation_ids or (
                    [step.relation_id] if step.relation_id else relations
                ):
                    relation = relations[rid]
                    entity_ids.update((relation.from_entity, relation.to_entity))
            if step.op in {"filter", "assert"}:
                for condition in self.candidate.constraints:
                    if (
                        condition.id in step.constraint_ids
                        and condition.predicate.operator == "connected"
                    ):
                        entity_ids.update(
                            anchor.entity_id for anchor in condition.predicate.anchors
                        )
                        for rid in condition.predicate.relation_ids:
                            relation = relations[rid]
                            entity_ids.update((relation.from_entity, relation.to_entity))
        allowed = set(tool_ids) if tool_ids is not None else None
        return [
            {
                "tool_id": mapping.tool_id,
                "entity_id": mapping.entity_id,
                "mapping_id": mapping.id,
                "properties": [field.property for field in mapping.fields],
            }
            for mapping in self.candidate.mappings
            if mapping.entity_id in entity_ids
            and (allowed is None or mapping.tool_id in allowed)
            and (property is None or property in {field.property for field in mapping.fields})
        ]

    def missing_facts(self, entity_id, identity, context, properties, *, tool_ids=None):
        """Describe unavailable subject properties and the selected tools that can supply them."""
        source = self.lookup(entity_id, identity, context)
        if not source.records and source.complete:
            return []
        row = source.records[0] if source.records else {}
        return [
            {
                "entity_id": entity_id,
                "identity": deepcopy(identity),
                "context": self._query_context(entity_id, context) if self.scoped else {},
                "property": name,
                "reason": "property_missing" if source.records else "subject_unobserved",
                "sources": self.sources(entity_id=entity_id, property=name, tool_ids=tool_ids),
            }
            for name in properties
            if name not in row
        ]

    def snapshot(self) -> dict:
        if self.scoped:
            return {
                "revision": self.revision,
                "observations": [
                    {
                        **{key: item[key] for key in ("id", "tool_id", "status", "coverage")},
                        "arguments": deepcopy(self.observation_arguments[item["id"]]),
                    }
                    for item in self.observations.values()
                ],
                "entities": {
                    entity_id: [
                        {
                            "identity": list(record["identity"]),
                            "context": deepcopy(record["context"]),
                            "values": deepcopy(record["values"]),
                            "evidence": deepcopy(record["evidence"]),
                        }
                        for record in records.values()
                    ]
                    for entity_id, records in self.records.items()
                },
                "coverage": {
                    entity_id: [
                        {
                            "context": deepcopy(state["context"]),
                            "complete": state["complete"],
                            "members": [list(key) for key in sorted(state["members"], key=repr)],
                            "evidence": deepcopy(state["evidence"]),
                        }
                        for state in scopes.values()
                    ]
                    for entity_id, scopes in self.scoped_coverage.items()
                },
                "history": deepcopy(self.history),
            }
        return {
            "revision": self.revision,
            "observations": [
                {key: item[key] for key in ("id", "tool_id", "status", "coverage")}
                for item in self.observations.values()
            ],
            "entities": {
                entity_id: [
                    {
                        "identity": list(key),
                        "values": deepcopy(record["values"]),
                        "evidence": deepcopy(record["evidence"]),
                    }
                    for key, record in records.items()
                ]
                for entity_id, records in self.records.items()
            },
            "complete": deepcopy(self.complete),
            "history": deepcopy(self.history),
        }
