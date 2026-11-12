"""Scripted native model for controlled training integration tests."""

import asyncio
import copy
import json
import re

import httpx

from oak.kernel_validation import CoverageReview, ValidationSuite
from oak.model_client import ModelResult
from oak.repair_patch import canonical_digest
from oak.repair_schemas import Candidate, CandidateV3
from oak.request_preparation import PreservationResult, RequestExtraction
from oak.schemas import ModelUsage
from oak.training_construction import ConstructionRevision, PatchProposal
from oak.training_evaluation import TaskEvaluation


def requested_title(query):
    match = re.search(r'(?:named|titled)\s+["\']?([^"\'\n.]+)', query, re.I)
    return match.group(1).split(" and ")[0].strip() if match else "Training note"


def find_rows(value):
    if isinstance(value, dict):
        if "id" in value and "title" in value:
            yield {"id": value["id"], "title": value["title"]}
        else:
            for child in value.values():
                yield from find_rows(child)
    elif isinstance(value, list):
        for child in value:
            yield from find_rows(child)


async def prepare_training_environment(run, case, episode_index):
    """Reset only the controlled MCP fixture before each training episode."""
    async with httpx.AsyncClient() as client:
        response = await client.post("http://127.0.0.1:9147/probe-reset")
        response.raise_for_status()
    return "fixture:notes:v1"


class TrainingModel:
    def __init__(self, mode="success", delay=0.01):
        self.mode, self.delay, self.calls = mode, delay, 0

    @staticmethod
    def usage():
        return ModelUsage(input_tokens=100, output_tokens=80, reasoning_tokens=0, total_tokens=180)

    async def turn(self, messages, tools, *, limits, instructions):
        self.calls += 1
        await asyncio.sleep(self.delay)
        query = next(
            (
                part["text"]
                for message in messages
                for part in message.get("parts", [])
                if "text" in part
            ),
            "Create a note named Training note",
        )
        title = requested_title(query)
        wants_write = bool(re.search(r"\b(create|save|write)\b", query, re.I))
        replies = [
            part.get("function_response", part.get("functionResponse"))
            for message in messages
            for part in message.get("parts", [])
            if "function_response" in part or "functionResponse" in part
        ]
        called = {reply["name"] for reply in replies}
        read = next((t for t in tools if "current test notes" in t.get("description", "")), None)
        write = next((t for t in tools if "Create a note" in t.get("description", "")), None)
        function = next((t for t in tools if t["name"].startswith("oak_function_")), None)
        selected, arguments = None, {}
        if read and read["name"] not in called:
            selected = read
        elif wants_write and write and write["name"] not in called:
            selected, arguments = write, {"title": title}
        elif function and function["name"] not in called:
            observed = list(find_rows(replies[-1].get("response", {}))) if replies else []
            selected, arguments = function, {"id": observed[-1]["id"] if observed else "note-1"}
        if selected:
            name = selected["name"]
            call_id = f"call-{len(replies) + 1}"
            content = {
                "role": "model",
                "parts": [
                    {
                        "function_call": {
                            "id": call_id,
                            "name": name,
                            "args": arguments,
                        }
                    }
                ],
            }
            calls = [{"id": call_id, "name": name, "arguments": arguments, "index": 0}]
            text = ""
        else:
            response = replies[-1].get("response", {}) if replies else {}
            if replies and replies[-1]["name"].startswith("oak_function_"):
                response = response.get("value")
            rows = list(find_rows(response))
            text = json.dumps(rows, ensure_ascii=False)
            if self.mode == "baseline_failure" and not function:
                text = "The requested note is unavailable."
            content, calls = {"role": "model", "parts": [{"text": text}]}, []
        return {
            "content": content,
            "text": text,
            "tool_calls": calls,
            "usage": self.usage().model_dump(),
            "model": "scripted-training-model",
            "duration_ms": int(self.delay * 1000),
        }

    async def generate(self, instructions, data, response_schema, **kwargs):
        self.calls += 1
        await asyncio.sleep(self.delay)
        if response_schema.__name__.startswith("EvidenceExchange_"):
            if not data.get("evidence_views"):
                branch = next(
                    (
                        v
                        for v in data.values()
                        if isinstance(v, dict) and v.get("omitted") and "evidence_ref" in v
                    ),
                    None,
                )
                if branch:
                    return ModelResult(
                        response_schema.model_validate(
                            {"evidence_requests": [{**branch["evidence_ref"], "limit": 1}]}
                        ),
                        "scripted-training-model",
                        self.usage(),
                        1,
                    )
            inner = next(
                t
                for t in response_schema.model_fields["result"].annotation.__args__
                if t is not type(None)
            )
            answer = await self.generate(instructions, data, inner, **kwargs)
            return ModelResult(
                response_schema.model_validate({"result": answer.data.model_dump(mode="json")}),
                "scripted-training-model",
                self.usage(),
                1,
            )
        if response_schema in {Candidate, CandidateV3}:
            value = self.candidate(data)
        elif response_schema is ConstructionRevision:
            value = {
                "base_digest": data["candidate_digest"],
                "changes": [],
                "evidence_refs": data["evidence_refs"],
            }
        elif response_schema is RequestExtraction:
            query = data["query"]
            intent = (
                "delete"
                if re.search(r"\bdelete\b", query, re.I)
                else "create"
                if re.search(r"\b(create|save|write)\b", query, re.I)
                else "read"
            )
            evidence = [{"source": "query", "quote": query}]
            title = requested_title(query) if intent == "create" else "Initial note"
            value = {
                "functions": [
                    {
                        "function_id": "observed_notes",
                        "arguments": {},
                        "requirement_ids": [r["id"] for r in data["requirements"]["requirements"]],
                        "evidence": evidence,
                    }
                ],
                "fields": [
                    {"name": "intent", "status": "resolved", "value": intent, "evidence": evidence},
                    {"name": "title", "status": "resolved", "value": title, "evidence": evidence},
                ],
            }
        elif response_schema is PreservationResult:
            unsupported = "second note" in data["query"]
            value = {
                "status": "unsupported" if unsupported else "passed",
                "reason": "The kernel represents one requested note and the operation intent.",
                "constraints": [
                    {
                        "statement": data["query"],
                        "status": "unsupported" if unsupported else "covered",
                        "field_names": ["intent", "title"],
                        "evidence": [{"source": "query", "quote": data["query"]}],
                    }
                ],
            }
        elif response_schema is CoverageReview:
            value = {
                "status": "passed",
                "reason": "The fixture checks operation intent and preserves the requested write title.",
                "evidence_refs": data["evidence_refs"][:1],
            }
        elif response_schema is ValidationSuite:
            value = self.validation_suite(data)
        elif response_schema is TaskEvaluation:
            case = data["case"]
            query = case["query"]
            title = (
                requested_title(query)
                if re.search(r"\b(create|save|write)\b", query, re.I)
                else "Initial note"
            )
            final = str(data["result"].get("final_output", ""))
            passed = title in final and "note-" in final
            value = {
                "status": "passed" if passed else "failed",
                "reason": "The recorded outcome matches the requested note."
                if passed
                else "The final outcome does not contain the requested note and its identifier.",
                "evidence_refs": data["evidence_refs"][:1],
            }
        elif response_schema is PatchProposal:
            before = data["declarations"]["functions"]["observed_notes"]
            after = copy.deepcopy(before)
            after["steps"][-1]["fields"][1]["expression"]["name"] = "title"
            target = data["target_case"]
            evidence = [data["problem_ref"]]
            value = {
                "reason": "Correct the title projection.",
                "patch": {
                    "id": "repair-note-title",
                    "base_digest": data["candidate_digest"],
                    "original_input_digest": data["original_input_digest"],
                    "fault": {
                        "id": "wrong-title",
                        "sample_id": str(target["id"]),
                        "requirement_ids": data["requirement_ids"],
                        "reason": "The function projects the identifier into the title field.",
                    },
                    "evidence_refs": evidence,
                    "changes": [
                        {
                            "collection": "functions",
                            "op": "replace",
                            "id": before["id"],
                            "expected_digest": canonical_digest(before),
                            "value": after,
                        }
                    ],
                },
            }
        else:
            raise AssertionError(response_schema)
        return ModelResult(
            response_schema.model_validate(value),
            "scripted-training-model",
            self.usage(),
            int(self.delay * 1000),
        )

    @staticmethod
    def validation_suite(context):
        candidate = context["candidate"]
        tools = {t["name"]: str(t["id"]) for t in context["inputs"]["tools"]}
        refs = context["evidence_refs"][:1]
        cases, exemptions = [], []
        for requirement in candidate["requirements"]["requirements"]:
            rid = requirement["id"]
            for name in ("list_notes", "create_note"):
                tid = tools[name]
                if tid not in requirement["tool_ids"]:
                    continue
                write = name == "create_note"
                variants = [
                    (
                        "allowed",
                        "Create a note named Safe note." if write else "Read the initial note.",
                        {"title": "Safe note"} if write else {},
                        "allowed",
                    ),
                    (
                        "condition_violation",
                        "Read the initial note." if write else "Delete a note.",
                        {"title": "Initial note"} if write else {},
                        "rejected",
                    ),
                ]
                if write:
                    variants.append(
                        (
                            "request_mismatch",
                            "Create a note named Safe note.",
                            {"title": "Different note"},
                            "rejected",
                        )
                    )
                for category, query, arguments, expected in variants:
                    cases.append(
                        {
                            "id": f"{rid}-{name}-{category}",
                            "tool_id": tid,
                            "query": query,
                            "arguments": arguments,
                            "expected": expected,
                            "category": category,
                            "requirement_ids": [rid],
                            "evidence_refs": refs,
                        }
                    )
                for category in ["missing_fact"] if write else ["missing_fact", "request_mismatch"]:
                    exemptions.append(
                        {
                            "requirement_id": rid,
                            "tool_id": tid,
                            "category": category,
                            "reason": "This operation requires no observed graph facts."
                            if category == "missing_fact"
                            else "The read operation accepts no task arguments.",
                            "evidence_refs": refs,
                        }
                    )
        return {"cases": cases, "exemptions": exemptions}

    def candidate(self, context):
        tools = context["inputs"]["tools"]
        selected = {str(t["id"]): t for t in tools if str(t["id"]) in context["allowed_tool_ids"]}
        mappings = []
        for tool_id, tool in selected.items():
            if tool["name"] not in {"list_notes", "create_note"}:
                continue
            mappings.append(
                {
                    "id": "mapping-" + tool["name"],
                    "entity_id": "note",
                    "tool_id": tool_id,
                    "collection_path": "/items" if tool["name"] == "list_notes" else "",
                    "fields": [{"property": name, "path": "/" + name} for name in ("id", "title")],
                }
            )
        reqs = context["requirement_ids"]
        return {
            "version": "oak.candidate.v3",
            "original_input_digest": context["original_input_digest"],
            "requirements": context["discovery"]["requirements"],
            "schema": {
                "entities": [
                    {
                        "id": "note",
                        "name": "Note",
                        "properties": [{"name": n, "type": "string"} for n in ("id", "title")],
                        "identity_keys": ["id"],
                        "requirement_ids": reqs,
                    }
                ]
            },
            "mappings": mappings,
            "request_fields": [
                {
                    "id": name,
                    "name": name,
                    "type": "string",
                    "description": description,
                    "requirement_ids": reqs,
                }
                for name, description in [
                    ("intent", "The operation requested in the original query."),
                    ("title", "The note title in the original query."),
                ]
            ],
            "constraints": [
                {
                    "id": "read-permitted",
                    "requirement_ids": reqs,
                    "predicate": {
                        "operator": "ne",
                        "left": {"kind": "request", "name": "intent"},
                        "right": {"kind": "literal", "value": "delete"},
                    },
                },
                {
                    "id": "write-requested",
                    "requirement_ids": reqs,
                    "predicate": {
                        "operator": "eq",
                        "left": {"kind": "request", "name": "intent"},
                        "right": {"kind": "literal", "value": "create"},
                    },
                },
                {
                    "id": "requested-title",
                    "requirement_ids": reqs,
                    "predicate": {
                        "operator": "eq",
                        "left": {"kind": "argument", "name": "title"},
                        "right": {"kind": "request", "name": "title"},
                    },
                },
            ],
            "operation_bindings": [
                {
                    "id": "binding-" + tool["name"],
                    "tool_id": tid,
                    "source_access": {
                        "kind": "action" if tool["name"] == "create_note" else "data",
                        "mapping_ids": ["mapping-" + tool["name"]],
                        "unsupported": [
                            "identity",
                            "filters",
                            "projection",
                            "pagination",
                            "ordering",
                            "completeness",
                        ],
                        "support": {
                            "source": "input",
                            "id": "surface",
                            "path": f"/tools/{next(i for i, t in enumerate(tools) if str(t['id']) == tid)}/description",
                        },
                    },
                    "requirement_ids": reqs,
                    "checks": [
                        {
                            "function_id": "check_write"
                            if tool["name"] == "create_note"
                            else "check_read",
                            "arguments": {"title": "/title"}
                            if tool["name"] == "create_note"
                            else {},
                        }
                    ],
                }
                for tid, tool in selected.items()
                if tool["name"] in {"list_notes", "create_note"}
            ],
            "requirement_coverage": [
                {
                    "id": rid + "-" + tool["name"],
                    "requirement_id": rid,
                    "request_field_ids": ["intent", "title"]
                    if tool["name"] == "create_note"
                    else ["intent"],
                    "constraint_ids": ["write-requested", "requested-title"]
                    if tool["name"] == "create_note"
                    else ["read-permitted"],
                    "binding_ids": ["binding-" + tool["name"]],
                }
                for rid in reqs
                for tool in selected.values()
                if tool["name"] in {"list_notes", "create_note"}
            ],
            "functions": [
                {
                    "id": "observed_notes",
                    "entity_id": "note",
                    "parameters": [{"name": "id", "type": "string"}],
                    "required_constraint_ids": [],
                    "steps": [
                        {
                            "op": "lookup",
                            "id": "source",
                            "entity_id": "note",
                            "identity": {"id": {"kind": "argument", "name": "id"}},
                        },
                        {
                            "op": "project",
                            "id": "result",
                            "input": "source",
                            "fields": [
                                {"name": "id", "expression": {"kind": "field", "name": "id"}},
                                {
                                    "name": "title",
                                    "expression": {
                                        "kind": "field",
                                        "name": "id" if self.mode == "repair" else "title",
                                    },
                                },
                            ],
                        },
                    ],
                    "return_step": "result",
                    "output": {
                        "kind": "rows",
                        "fields": [{"name": n, "type": "string"} for n in ("id", "title")],
                    },
                },
                *[
                    {
                        "id": "check_write" if write else "check_read",
                        "parameters": [{"name": "title", "type": "string"}] if write else [],
                        "required_constraint_ids": ["write-requested", "requested-title"]
                        if write
                        else ["read-permitted"],
                        "steps": [
                            {"op": "input", "id": "input"},
                            {
                                "op": "assert",
                                "id": "checked",
                                "input": "input",
                                "constraint_ids": ["write-requested", "requested-title"]
                                if write
                                else ["read-permitted"],
                            },
                            {"op": "decision", "id": "decision", "inputs": ["checked"]},
                        ],
                        "return_step": "decision",
                        "output": {"kind": "decision"},
                    }
                    for write in (False, True)
                ],
            ],
        }
