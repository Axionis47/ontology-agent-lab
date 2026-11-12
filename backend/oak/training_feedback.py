"""Select repair evidence by saved references and execution identifiers."""

import json
import re
from copy import deepcopy

from oak.discovery_schemas import EvidenceRef
from oak.evidence_access import EvidenceStore, size
from oak.repair_executor import MISSING, _pointer
from oak.repair_patch import canonical_digest


def resolve_evidence(reference, roots):
    """Resolve a reference only below an available source root."""
    ref = EvidenceRef.model_validate(reference)
    if re.search(r"~(?![01])", ref.path):
        return MISSING
    for root, value in roots:
        root = EvidenceRef.model_validate(root)
        if (ref.source, ref.id) != (root.source, root.id):
            continue
        if ref.path == root.path:
            return value
        if ref.path.startswith(root.path + "/"):
            return _pointer(value, ref.path[len(root.path) :])
    return MISSING


def _ref(identifier, path, source="artifact"):
    return {"source": source, "id": str(identifier), "path": path}


def _walk(value):
    if isinstance(value, dict):
        yield value
        for key, child in value.items():
            if key not in {"data", "raw", "arguments", "value", "values", "identity", "context"}:
                yield from _walk(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _walk(child)


class RepairInput:
    """Keep the complete records in the host. Send only selected evidence."""

    def __init__(self, context, candidate, evidence_view):
        self.roots, self.records, self.declarations = [], [], {}
        self.seen = set()
        self.evidence = EvidenceStore()
        self.remaining = 16_000
        self.data = {
            "candidate_digest": context["candidate_digest"],
            "repair_review": deepcopy(context.get("repair_review")),
            "original_input_digest": candidate.original_input_digest,
            "allowed_tool_ids": context["allowed_tool_ids"],
            "requirement_ids": context["requirement_ids"],
            "requirements": candidate.requirements.model_dump(mode="json"),
            "task_surface": {
                key: context.get("inputs", {}).get(key, {}) for key in ("task", "agent")
            },
            "target_case": context.get("target_case"),
            "declarations": {},
            "declaration_index": [],
            "evidence_refs": deepcopy(context.get("evidence_refs", [])),
        }
        if self.data["repair_review"]:
            # Full replay traces remain in the review event and source episodes.
            self.data["repair_review"]["replays"] = [
                {k: r[k] for k in ("probe", "matches")}
                for r in self.data["repair_review"].get("replays", [])
            ]
        self.roots.append((_ref("surface", "", "input"), context.get("inputs", {})))
        raw = candidate.model_dump(mode="json")
        for owner, prefix in ((raw["schema"], "/schema"), (raw, "")):
            for collection, items in owner.items():
                if not isinstance(items, list):
                    continue
                for index, item in enumerate(items):
                    if not isinstance(item, dict) or "id" not in item:
                        continue
                    ref = _ref(context["candidate_digest"], f"{prefix}/{collection}/{index}")
                    self.roots.append((ref, item))
                    self.declarations[(collection, item["id"])] = (ref, item)
                    self.data["declaration_index"].append(
                        {
                            "collection": collection,
                            "id": item["id"],
                            "digest": canonical_digest(item),
                            "ref": ref,
                        }
                    )
        self.roots.append((_ref(context["candidate_digest"], "/requirements"), raw["requirements"]))
        episodes = context.get("episodes", [])
        for episode in episodes:
            result = evidence_view(episode.get("result", {}))
            self.roots.append((_ref(episode["id"], "/result"), result))
            for key in (
                "observations",
                "function_calls",
                "dispatch_decisions",
                "graph_processing",
                "trace",
            ):
                for index, record in enumerate(result.get(key, [])):
                    if isinstance(record, dict):
                        self.records.append((_ref(episode["id"], f"/result/{key}/{index}"), record))
        correction = context.get("construction_correction", {})
        self.problem_ref = correction.get("evidence_ref")
        if self.problem_ref:
            self.roots.append((self.problem_ref, correction.get("report", {})))
            if context.get("fixed_validation_suite") is not None:
                suite_ref = _ref(self.problem_ref["id"], "/fixed_validation_suite")
                self.roots.append((suite_ref, context["fixed_validation_suite"]))
                self.data["evidence_refs"].append(suite_ref)
        self.data["problem_ref"] = self.problem_ref
        target = context.get("target_case") or {}
        selected = next(
            (e for e in reversed(episodes) if str(e.get("case_id")) == str(target.get("id"))), None
        )
        report = selected.get("evaluation", {}) if selected else correction.get("report", {})
        requirement = {key: target[key] for key in ("query", "task_success") if key in target}
        seeds = report.get("evidence_refs", []) if selected else []
        if not seeds and selected and "final_output" in selected.get("result", {}):
            seeds = [_ref(selected["id"], "/result/final_output")]
        if not seeds and self.problem_ref:
            seeds = [self.problem_ref]
        evidence = self.read(seeds)
        # Executed definitions can explain a final answer even without a direct result citation.
        if selected:
            identifiers = selected.get("result", {}).get("function_ids", [])
            evidence += self.read(
                [
                    self.declarations[("functions", i)][0]
                    for i in identifiers
                    if ("functions", i) in self.declarations
                ]
            )
        self.data["repair_brief"] = (
            "Requirement\n"
            + json.dumps(requirement or raw["requirements"], ensure_ascii=False)
            + "\n\nObserved problem\n"
            + str(report.get("reason", report.get("errors", report.get("status", "Unknown"))))
            + "\n\nEvidence\n"
            + evidence
            + "\n\nRelevant declarations\nSee the loaded declarations and their versioned index."
            + "\n\nUncertainty\nA citation identifies evidence, not a proven cause. "
            "Omitted content remains unavailable until requested."
        )
        self.remaining += 8_000

    def read(self, references, *, requested=False):
        """Follow explicit links. Large records retain references to their children."""
        queue, rendered = list(references), []
        if requested:
            for reference in references:
                ref = EvidenceRef.model_validate(reference)
                self.seen.discard((ref.source, ref.id, ref.path))
        while queue and self.remaining > 0:
            ref = EvidenceRef.model_validate(queue.pop(0)).model_dump(mode="json")
            key = (ref["source"], ref["id"], ref["path"])
            if key in self.seen:
                continue
            self.seen.add(key)
            value = resolve_evidence(ref, self.roots)
            if value is MISSING:
                rendered.append(f"{ref}: unavailable in this saved run.")
                continue
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            definition_size = 0
            definition = None
            self.evidence.save(canonical_digest(ref), value)
            view = self.evidence.read({"id": canonical_digest(ref)}, min(4096, self.remaining))
            # A requested declaration joins the required definitions. The shared context
            # policy checks its visibility before the model can replace it.
            full_declaration = requested and any(
                ref == item[0] for item in self.declarations.values()
            )
            if view["omitted"] and not (full_declaration and size(value) <= self.remaining):
                preview = {
                    **view,
                    "source_ref": ref,
                    "metadata": {
                        key: value[key]
                        for key in (
                            "id",
                            "invocation_id",
                            "tool_id",
                            "function_id",
                            "status",
                            "coverage",
                            "complete",
                            "truncated",
                            "graph_revision",
                            "context",
                        )
                        if isinstance(value, dict) and key in value and size(value[key]) < 200
                    },
                    "reason": (
                        "Request a specific field or array index. This is not a complete result."
                    ),
                }
                encoded = json.dumps(preview, ensure_ascii=False)
            else:
                self._follow(ref, value, queue)
                for (collection, identifier), (decl_ref, declaration) in self.declarations.items():
                    if ref == decl_ref:
                        definition = (collection, identifier, declaration)
                        definition_size = len(encoded.encode())
                        encoded = f"Loaded declaration {collection}/{identifier}."
                        break
            entry = f"{json.dumps(ref)}\n{encoded}\n"
            if len(entry.encode()) + definition_size > self.remaining:
                rendered.append("Evidence budget reached. Remaining records are unavailable.")
                break
            if definition:
                collection, identifier, declaration = definition
                self.data["declarations"].setdefault(collection, {})[identifier] = deepcopy(
                    declaration
                )
            self.remaining -= len(entry.encode()) + definition_size
            rendered.append(entry)
        if queue:
            rendered.append(
                "Additional dependencies were omitted because the evidence budget was reached."
            )
        return "\n".join(rendered)

    def _follow(self, ref, value, queue):
        # Restore the invocation metadata when the citation names a result field.
        for record_ref, record in self.records:
            if ref["id"] == record_ref["id"] and ref["path"].startswith(record_ref["path"] + "/"):
                queue.append(record_ref)
        if {"data", "raw", "arguments", "value", "values"} & set(ref["path"].split("/")):
            return
        fields = {
            "function_id": "functions",
            "mapping_id": "mappings",
            "entity_id": "entities",
            "entity_types": "entities",
            "from_entity": "entities",
            "to_entity": "entities",
            "relation_id": "relations",
            "relation_ids": "relations",
            "condition_id": "constraints",
            "constraint_ids": "constraints",
            "required_constraint_ids": "constraints",
            "binding_ids": "bindings",
        }
        for node in _walk(value):
            invocation, observation = node.get("invocation_id"), node.get("observation_id")
            for record_ref, record in self.records:
                if record_ref["id"] != ref["id"]:
                    continue
                if (invocation and record.get("invocation_id") == invocation) or (
                    observation and record.get("id") == observation
                ):
                    queue.append(record_ref)
                    if observation and "path" in node:
                        queue.append(
                            {**record_ref, "path": record_ref["path"] + "/data" + node["path"]}
                        )
            for name, collection in fields.items():
                ids = node.get(name, [])
                for identifier in ids if isinstance(ids, (tuple, list)) else [ids]:
                    if (
                        isinstance(identifier, str)
                        and (collection, identifier) in self.declarations
                    ):
                        queue.append(self.declarations[(collection, identifier)][0])
            for collection in ("mappings", "operation_bindings"):
                for (kind, _), (decl_ref, declaration) in self.declarations.items():
                    if (
                        kind == collection
                        and node.get("tool_id")
                        and declaration.get("tool_id") == node["tool_id"]
                    ):
                        queue.append(decl_ref)
            if node.get("kind") == "request":
                for (kind, _), (decl_ref, declaration) in self.declarations.items():
                    if kind == "request_fields" and declaration.get("name") == node.get("name"):
                        queue.append(decl_ref)
