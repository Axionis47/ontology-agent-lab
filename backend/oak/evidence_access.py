"""Provide bounded views of saved evidence without repeating external calls."""

import json
from copy import deepcopy

from pydantic import BaseModel, ConfigDict, Field, create_model

from oak.discovery_validation import digest, pointer

VIEW_TOKENS = 4096
CONTEXT_POLICY = """Evidence views can omit content to fit the context budget.
Omitted content is unknown, not absent. Use read_evidence or evidence_requests to
inspect exact saved content. References do not authorize external calls. Cite
original evidence identifiers in final declarations and judgments. Never infer
complete coverage from a preview, page size, or search result. Preserve the original
task and unresolved external outcomes. Request decisive evidence before judging.
Use working_notes to retain provisional findings and exact references between
evidence requests. Notes are proposals, not source evidence."""


class ContextCapacity(ValueError):
    """Required context cannot fit the configured model input limit."""


def encoded(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), default=str)


def size(value):
    # UTF-8 bytes are a conservative token bound. The provider also counts the full input.
    return len(encoded(value).encode())


def child_path(path, key):
    return path + "/" + str(key).replace("~", "~0").replace("/", "~1")


class EvidenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    path: str = Field(default="", pattern=r"^(|/.*)$")
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=1000)
    search: str | None = Field(default=None, min_length=1, max_length=500)


class EvidenceStore:
    """Own only the records explicitly supplied by the current run or model call."""

    def __init__(self):
        self.records = {}
        self.seen = set()
        self.text_ranges = {}

    def save(self, identifier, value):
        if identifier in self.records and self.records[identifier] != value:
            raise ValueError("An evidence identifier cannot change its content.")
        self.records[identifier] = deepcopy(value)
        return {"id": identifier, "path": ""}

    def reference(self, identifier, value, path=""):
        result = {
            "evidence_ref": {"id": identifier, "path": path},
            "omitted": True,
            "type": type(value).__name__,
        }
        if isinstance(value, (list, dict, str)):
            result["length"] = len(value)
        if isinstance(value, dict):
            for key in ("id", "status", "coverage", "invocation_id", "tool_id", "graph_revision"):
                if key in value and size(value[key]) < 200:
                    result[key] = deepcopy(value[key])
        return result

    def read(self, request, budget=VIEW_TOKENS):
        request = EvidenceRead.model_validate(request)
        if request.id not in self.records:
            raise ValueError("Evidence is unavailable in this run.")
        value = pointer(self.records[request.id], request.path)
        budget = max(0, min(VIEW_TOKENS, budget))
        if budget < 256:
            raise ContextCapacity("The evidence view has no remaining context budget.")
        result = {
            "evidence_ref": {"id": request.id, "path": request.path},
            "offset": request.offset,
        }
        root = self.records[request.id]
        if isinstance(root, dict):
            result.update(
                {
                    "execution_status": root.get("status", "saved"),
                    "source_coverage": root.get("coverage", "unknown"),
                }
            )
        if (
            request.search is None
            and request.offset == 0
            and not request.model_fields_set.intersection({"offset", "limit"})
            and size(value) + size(result) + 100 <= budget
        ):
            self.seen.add((request.id, request.path))
            return {**result, "value": deepcopy(value), "omitted": False, "next_offset": None}
        if isinstance(value, str):
            offset = request.offset
            if request.search is not None:
                stop = min(len(value), offset + 65536)
                offset = value.find(request.search, offset, stop)
                if offset < 0:
                    return {
                        **result,
                        "value": "",
                        "omitted": True,
                        "next_offset": max(request.offset + 1, stop - len(request.search) + 1)
                        if stop < len(value)
                        else None,
                        "matched": False,
                    }
            length = max(0, min(request.limit, len(value) - offset))
            while (
                length and size({**result, "value": value[offset : offset + length]}) + 200 > budget
            ):
                length //= 2
            end = offset + length
            ranges = self.text_ranges.setdefault((request.id, request.path), [])
            ranges.append((offset, end))
            through = 0
            for start, stop in sorted(ranges):
                if start > through:
                    break
                through = max(through, stop)
            if through >= len(value):
                self.seen.add((request.id, request.path))
            return {
                **result,
                "offset": offset,
                "value": value[offset:end],
                "length": len(value),
                "omitted": True,
                "next_offset": end if end < len(value) else None,
            }
        if not isinstance(value, (dict, list)):
            raise ContextCapacity("The scalar evidence cannot fit this view.")
        keys = list(value) if isinstance(value, dict) else range(len(value))
        items, index = [], request.offset
        scan_end = min(len(keys), request.offset + 1000)
        while index < scan_end and len(items) < request.limit:
            key = keys[index]
            item = value[key]
            if request.search is not None and request.search not in encoded(item):
                index += 1
                continue
            path = child_path(request.path, key)
            entry = {"path": path, "value": deepcopy(item)}
            if size(entry) + 250 > budget:
                entry = {"path": path, **self.reference(request.id, item, path)}
            if size({**result, "items": items + [entry]}) + 250 > budget:
                break
            items.append(entry)
            if "value" in entry:
                self.seen.add((request.id, path))
            index += 1
        if index == request.offset and index < len(keys):
            raise ContextCapacity("The evidence index cannot fit this view.")
        return {
            **result,
            "items": items,
            "length": len(value),
            "omitted": True,
            "next_offset": index if index < len(keys) else None,
            "coverage": "view_only",
        }

    def view(self, identifier, value, budget=VIEW_TOKENS):
        self.save(identifier, value)
        return self.read({"id": identifier}, budget)

    def present(self, identifier, value, budget=VIEW_TOKENS):
        """Retain result status and small values while referencing bulky fields."""
        self.save(identifier, value)
        if size(value) <= budget:
            return deepcopy(value)
        if not isinstance(value, dict):
            return self.reference(identifier, value)
        result = deepcopy(value)
        result["evidence_ref"] = {"id": identifier, "path": ""}
        result["omitted"] = True
        for key in sorted(value, key=lambda k: size(value[k]), reverse=True):
            if size(result) <= budget:
                return result
            if key in {"status", "coverage", "graph_revision", "error"}:
                continue
            result[key] = self.reference(identifier, value[key], child_path("", key))
        if size(result) > budget:
            return self.reference(identifier, value)
        return result

    def inspected(self, identifier, path):
        if any(i == identifier and (path == p or path.startswith(p + "/")) for i, p in self.seen):
            return True
        value = pointer(self.records[identifier], path)
        if isinstance(value, dict):
            return all(self.inspected(identifier, child_path(path, key)) for key in value)
        if isinstance(value, list):
            return all(
                self.inspected(identifier, child_path(path, key)) for key in range(len(value))
            )
        return False


READ_TOOL = {
    "name": "read_evidence",
    "description": (
        "Inspect saved evidence in this run by reference, range, or text search. "
        "Does not call an external service."
    ),
    "input_schema": EvidenceRead.model_json_schema(),
}


def bounded_context(data, store, budget):
    """Keep small inputs intact. Replace large evidence branches with exact references."""
    identifier = "context:" + digest(data)
    store.save(identifier, data)
    if size(data) <= budget:
        return deepcopy(data), False
    mandatory = {
        "query",
        "boundaries",
        "task_surface",
        "original_input_digest",
        "requirements",
        "request_fields",
        "extraction",
        "candidate_digest",
        "instructions",
    }
    result = deepcopy(data)
    candidates = []

    def collect(value, path, parent, key):
        if size(value) < 512:
            return
        candidates.append((size(value), path, parent, key, value))

    for key, value in result.items():
        if key in mandatory:
            continue
        if isinstance(value, dict) and key in {"inputs", "case", "discovery"}:
            for k, v in value.items():
                if k not in {"task", "agent", "query", "task_success", "requirements"}:
                    collect(v, child_path("/" + key, k), value, k)
        else:
            collect(value, child_path("", key), result, key)
    for _, path, parent, key, value in sorted(candidates, key=lambda entry: entry[0], reverse=True):
        if size(result) <= budget:
            break
        parent[key] = store.reference(identifier, value, path)
    if size(result) > budget:
        raise ContextCapacity("Mandatory task context exceeds the configured input capacity.")
    return result, True


async def generate_with_evidence(
    generate, *, instructions, data, response_schema, input_tokens, emit, saved_evidence=None
):
    """Request saved evidence through bounded structured exchanges when input is large."""
    store = EvidenceStore()
    for identifier, value in (saved_evidence or {}).items():
        store.save(identifier, value)
    # Use a practical estimate for stable grammar. Provider counting remains authoritative.
    fixed = (len(instructions.encode()) + size(response_schema.model_json_schema())) // 3
    budget = (int(input_tokens * 0.8) - fixed - 1024) * 3
    if budget < 512:
        raise ContextCapacity("Mandatory instructions and declarations exceed context capacity.")
    context, omitted = bounded_context(
        data, store, budget if size(data) <= budget else max(512, budget * 3 // 5)
    )
    root_id = "context:" + digest(data)

    def mark_visible(original, visible, path=""):
        if original == visible:
            store.seen.add((root_id, path))
        elif isinstance(original, dict) and isinstance(visible, dict):
            for key in original.keys() & visible.keys():
                mark_visible(original[key], visible[key], child_path(path, key))

    mark_visible(data, context)
    await emit(
        "context_usage",
        {
            "input_bytes": size(context),
            "target_tokens": int(input_tokens * 0.8),
            "evidence_omitted": omitted,
        },
    )
    if not omitted and not saved_evidence:
        return await generate(
            instructions=instructions, data=context, response_schema=response_schema
        )
    await emit("evidence_context", {"id": root_id, "value": data})
    exchange = create_model(
        "EvidenceExchange_" + response_schema.__name__,
        result=(response_schema | None, None),
        evidence_requests=(list[EvidenceRead], Field(default_factory=list, max_length=4)),
        working_notes=(str, Field(default="", max_length=4000)),
    )
    current = {**context, "evidence_views": []}
    while True:
        result = await generate(
            instructions=instructions
            + "\n"
            + CONTEXT_POLICY
            + "\nReturn result when ready, or evidence_requests with result=null.",
            data=current,
            response_schema=exchange,
        )
        response = result.data
        if response.result is not None:
            if response.evidence_requests:
                raise ValueError("An evidence exchange cannot both finish and request evidence.")
            if response_schema.__name__ in {
                "TaskEvaluation",
                "CoverageReview",
            } and response.result.status in {"passed", "failed"}:
                required = []
                if response_schema.__name__ == "CoverageReview" and "candidate" in data:
                    required.append("/candidate")
                for ref in response.result.evidence_refs:
                    if "result" in data and (
                        ref.path == "/result" or ref.path.startswith("/result/")
                    ):
                        required.append(ref.path)
                if any(not store.inspected(root_id, path) for path in required):
                    response.result = response.result.model_copy(
                        update={
                            "status": "inconclusive",
                            "reason": (
                                "The review did not inspect its decisive evidence "
                                "or required declarations."
                            ),
                        }
                    )
            if (
                hasattr(response.result, "patch")
                and response.result.patch is not None
                and "declarations" in data
            ):
                for change in response.result.patch.changes:
                    if change.op != "add":
                        path = child_path(child_path("/declarations", change.collection), change.id)
                        if not store.inspected(root_id, path):
                            raise ValueError(
                                "Inspect the complete declaration before replacing it."
                            )
            if "current_candidate" in data and hasattr(response.result, "changes"):
                candidate = data["current_candidate"]
                for change in response.result.changes:
                    if change.op == "add":
                        continue
                    schema_collection = change.collection in {
                        "entities",
                        "relations",
                        "bindings",
                        "operations",
                    }
                    owner = candidate["schema"] if schema_collection else candidate
                    for index, declaration in enumerate(owner.get(change.collection, [])):
                        if declaration["id"] == change.id:
                            path = "/current_candidate" + ("/schema" if schema_collection else "")
                            path += "/" + change.collection + "/" + str(index)
                            if not store.inspected(root_id, path):
                                raise ValueError(
                                    "Inspect the complete declaration before replacing it."
                                )
            result.data = response.result
            return result
        if not response.evidence_requests:
            raise ValueError("An evidence exchange requires a result or evidence requests.")
        views = list(current["evidence_views"])
        remaining = budget - size(context) - size(response.working_notes) - 300
        for request in response.evidence_requests:
            try:
                view = store.read(request, min(VIEW_TOKENS, remaining))
            except ContextCapacity:
                raise
            except (ValueError, KeyError) as error:
                view = {
                    "evidence_ref": {"id": request.id, "path": request.path},
                    "status": "unavailable",
                    "omitted": True,
                    "error": str(error),
                }
            views.append(view)
            await emit("evidence_read", {"request": request.model_dump(), "view": view})
        while views and size(views) > remaining:
            views.pop(0)
        if not views:
            raise ContextCapacity("The requested evidence cannot fit alongside mandatory context.")
        current = {**context, "evidence_views": views, "working_notes": response.working_notes}
