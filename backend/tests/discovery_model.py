"""Deterministic model responses for discovery acceptance tests."""

import asyncio

from oak.discovery_modeling import DiscoveryRound
from oak.discovery_schemas import (
    ClarificationReview,
    ProbeDecision,
    RequirementsProposal,
    SchemaProposal,
)
from oak.model_client import ModelResult
from oak.schemas import ModelUsage


class DiscoveryModel:
    def __init__(self, mode="success", delay=0.02):
        self.mode, self.delay, self.calls = mode, delay, 0

    async def generate(self, instructions, data, response_schema, **kwargs):
        self.calls += 1
        await asyncio.sleep(self.delay)
        value = self._value(data, response_schema)
        return ModelResult(
            response_schema.model_validate(value),
            "mock-gemini",
            ModelUsage(input_tokens=100, output_tokens=50, reasoning_tokens=0, total_tokens=150),
            20,
        )

    def _value(self, data, response_schema):
        artifacts = data["artifacts"]
        catalog = next(a for a in reversed(artifacts) if a["kind"] == "catalog")
        tools = {t["name"]: t["id"] for t in catalog["payload"]["tools"]}
        observations = [a for a in artifacts if a["kind"] == "observation"]
        evidence = [{"source": "input", "id": "surface", "path": "/agent/responsibilities"}]
        question = {
            "key": "recipient",
            "text": "Which contact receives the note?",
            "why_needed": "The task does not select a contact.",
            "options": ["Billing contact", "Primary contact"],
            "evidence": evidence,
            "affected": ["R1"],
        }
        answers = [q for q in data["clarifications"] if q["answer"]]
        if response_schema is DiscoveryRound:
            requirements = self._value(data, RequirementsProposal)
            schema = self._value(data, SchemaProposal)
            decision = self._value(data, ProbeDecision)
            choices = [
                {
                    "target": {"kind": "entity", "id": "note"},
                    "requirement_ids": ["R1"],
                    "purpose": "Track the requested note.",
                    "reason": "Each note has its own identifier and title.",
                    "identity_scope": "The selected note source and test workspace.",
                    "evidence": evidence,
                    "unresolved": [] if observations else ["Observe the note identity fields."],
                }
            ]
            for prop in ("id", "title"):
                refs = [b["source"] for b in schema["bindings"] if b["property"] == prop]
                choices.append(
                    {
                        "target": {"kind": "property", "id": "note", "property": prop},
                        "requirement_ids": ["R1"],
                        "purpose": "Identify and report the note.",
                        "reason": "This value describes one note without separate identity.",
                        "evidence": refs or evidence,
                        "unresolved": [] if refs else ["Inspect the source field."],
                    }
                )
            choices.append(
                {
                    "target": {"kind": "function", "id": "note_fields"},
                    "requirement_ids": ["R1"],
                    "purpose": "Report the observed note fields.",
                    "reason": "Project the fields from observed records.",
                    "evidence": evidence,
                }
            )
            value = {
                "summary": "Revise note declarations from the available observations.",
                "requirements": requirements,
                "schema_proposal": schema,
                "choices": choices,
                "tool_access": [
                    {
                        "tool_id": tool["id"],
                        "capabilities": [
                            {
                                "capability": capability,
                                "status": "unknown",
                                "description": "The fixture does not establish this source guarantee.",
                                "evidence": [
                                    {
                                        "source": "artifact",
                                        "id": catalog["id"],
                                        "path": f"/tools/{index}/description",
                                    }
                                ],
                            }
                            for capability in (
                                "identity",
                                "filters",
                                "projection",
                                "pagination",
                                "ordering",
                                "completeness",
                            )
                        ],
                    }
                    for index, tool in enumerate(catalog["payload"]["tools"])
                ],
                "function_needs": [
                    {
                        "id": "note_fields",
                        "parameters": [],
                        "output_kind": "rows",
                        "outputs": schema["entities"][0]["properties"],
                        "dependencies": [
                            {"kind": "property", "id": "note", "property": p}
                            for p in ("id", "title")
                        ],
                        "missing_evidence": "Request the missing note fields from the source.",
                    }
                ],
                "action": decision["action"],
                "questions": decision.get("questions", []),
            }
            if decision["action"] == "call":
                value["probe"] = decision
                value["probe_question"] = {
                    "question": "Which fields and state does the note source provide?",
                    "requirement_ids": ["R1"],
                    "targets": [{"kind": "function", "id": "note_fields"}],
                    "expected_information": "The note identifier, title, and observed creation result.",
                }
            return value
        if response_schema is ClarificationReview:
            value = {
                "compatible": self.mode != "conflict",
                "conflict": "The answer contradicts the saved boundary."
                if self.mode == "conflict"
                else None,
                "questions": [],
            }
            if self.mode == "repeat":
                question["unresolved_detail"] = (
                    "The selected contact still has two addresses. Specify the address."
                )
                value["questions"] = [question]
        elif response_schema is ProbeDecision:
            if self.mode == "questions_first" and not answers:
                value = {
                    "action": "questions",
                    "purpose": "Resolve recipient intent",
                    "questions": [question],
                }
            elif not observations:
                value = {
                    "action": "call",
                    "purpose": "Inspect note fields",
                    "tool_id": tools["list_notes"],
                    "arguments_json": "{}",
                    "effect": "read",
                    "evidence": evidence,
                }
            elif len(observations) == 1 and data["resume_requires_fresh_reads"]:
                value = {
                    "action": "call",
                    "purpose": "Recheck source data after pause",
                    "tool_id": tools["list_notes"],
                    "arguments_json": "{}",
                    "effect": "read",
                    "evidence": evidence,
                }
            elif len(observations) == 1:
                value = {
                    "action": "call",
                    "purpose": "Test note creation",
                    "tool_id": tools["create_note"],
                    "arguments_json": '{"title":"Discovery test"}',
                    "effect": "write",
                    "evidence": evidence,
                }
            elif self.mode == "repeat_write" and len(observations) == 2:
                value = {
                    "action": "call",
                    "purpose": "Repeat the write",
                    "tool_id": tools["create_note"],
                    "arguments_json": '{"title":"Discovery test"}',
                    "effect": "write",
                }
            elif len(observations) == 2:
                value = {
                    "action": "call",
                    "purpose": "Observe the created note",
                    "tool_id": tools["list_notes"],
                    "arguments_json": "{}",
                    "effect": "read",
                    "evidence": evidence,
                }
                if observations[1]["payload"]["effect"] != "read_observed":
                    value["confirmation_for"] = observations[1]["payload"]["invocation_id"]
                    value["confirmation_matches"] = [
                        {"written_path": "/data/id", "read_path": "/data/items/1/id"},
                        {
                            "written_source": "request",
                            "written_path": "/title",
                            "read_path": "/data/items/1/title",
                        },
                    ]
            elif not answers:
                value = {
                    "action": "questions",
                    "purpose": "Resolve recipient intent",
                    "questions": [question],
                }
            else:
                value = {"action": "finish", "purpose": "Enough evidence exists for proposals"}
        elif response_schema is RequirementsProposal:
            value = {
                "requirements": [
                    {
                        "id": "R1",
                        "statement": "Inspect notes and create only a test note within the saved boundaries.",
                        "evidence": [
                            {"source": "input", "id": "surface", "path": p}
                            for p in data["inputs"]["source_sections"]
                        ],
                        "tool_ids": list(tools.values()),
                    }
                ],
                "questions": [],
                "gaps": [],
            }
        elif response_schema is SchemaProposal:
            observation = observations[0] if observations else None
            value = {
                "entities": [
                    {
                        "id": "note",
                        "name": "Note",
                        "properties": [
                            {"name": "id", "type": "string"},
                            {"name": "title", "type": "string"},
                        ],
                        "identity_keys": ["id"] if observation else [],
                        "requirement_ids": ["R1"],
                    }
                ],
                "bindings": [
                    {
                        "id": "note-" + prop,
                        "tool_id": tools["list_notes"],
                        "entity_id": "note",
                        "property": prop,
                        "source": {
                            "source": "artifact",
                            "id": observation["id"],
                            "path": "/data/items/0/" + prop,
                        },
                        "support": "observed",
                        "coverage": "sample",
                    }
                    for prop in ("id", "title")
                ]
                if observation
                else [],
                "relations": [],
                "operations": [
                    {
                        "id": "create-note",
                        "tool_id": tools["create_note"],
                        "effect": "write",
                        "requirement_ids": ["R1"],
                        "prerequisites": ["Use the supplied test workspace"],
                        "outputs": "Created note identifier",
                        "confirmation_tool_id": tools["list_notes"],
                        "limitations": ["No provider idempotency guarantee"],
                    }
                ],
                "gaps": [],
            }
            if self.mode == "invented_field" and observation:
                value["bindings"][0]["source"]["path"] = "/data/items/0/invented"
        else:
            raise AssertionError(response_schema)
        if self.mode == "bad_confirmation" and value.get("confirmation_matches"):
            value["confirmation_matches"][0]["read_path"] = "/data/missing"
        if (
            self.mode == "bad_reference_once"
            and self.calls == 1
            and response_schema is ProbeDecision
        ):
            value["evidence"][0]["path"] = "/missing"
        return value
