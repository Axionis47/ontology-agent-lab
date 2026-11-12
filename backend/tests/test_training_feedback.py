"""Check focused repair input against saved MCP and function records."""

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from oak.repair_patch import apply_targeted_patch, candidate_digest, canonical_digest
from oak.repair_schemas import CandidateV3
from oak.training_construction import execution_evidence, propose_repair
from oak.training_feedback import RepairInput
from tests.kernel_fixtures import READ_ID, WRITE_ID, candidate_data, tools


def ref(path, identifier="episode-1"):
    return {"source": "artifact", "id": identifier, "path": path}


def context(noise=0, tool_name=READ_ID):
    raw = json.loads(json.dumps(candidate_data()).replace(READ_ID, tool_name))
    raw["version"] = "oak.candidate.v3"
    candidate = CandidateV3.model_validate(raw)
    case = {
        "id": "case-1",
        "query": "Return the requested result.",
        "task_success": "The result uses the observed value.",
    }
    observation = {
        "id": "early-observation",
        "invocation_id": "early-call",
        "tool_id": tool_name,
        "status": "succeeded",
        "coverage": "unknown",
        "arguments": {"scope": "original"},
        "data": {"metric/unit": 17},
    }
    result = {
        "status": "complete",
        "final_output": "Incorrect result.",
        "observations": [observation]
        + [
            {
                "id": f"unrelated-{i}",
                "invocation_id": f"other-{i}",
                "data": {"text": "unrelated payload"},
            }
            for i in range(noise)
        ],
        "function_ids": ["check_offer"],
        "function_calls": [
            {
                "invocation_id": "checked-call",
                "function_id": "check_offer",
                "arguments": {"offer_id": "a"},
                "result": {
                    "status": "rejected",
                    "value": 3,
                    "graph_revision": 7,
                    "coverage": "observed",
                    "evidence_refs": [
                        {
                            "observation_id": "early-observation",
                            "mapping_id": raw["mappings"][0]["id"],
                            "path": "/metric~1unit",
                            "context": {"scope": "original"},
                            "graph_revision": 2,
                        }
                    ],
                },
            }
        ],
        "trace": [{"kind": "model_response", "response": "PRIVATE PROVIDER HISTORY"}],
        "graph": {"revision": 50, "data": "LATEST GRAPH IS NOT THE CHECKED STATE"},
    }
    episode = {
        "id": "episode-1",
        "case_id": case["id"],
        "case_snapshot": case,
        "result": result,
        "evaluation": {
            "status": "failed",
            "reason": "The result differs from the observed value.",
            "evidence_refs": [ref("/result/function_calls/0/result/value")],
        },
    }
    report_ref = ref("/report", "validation-1")
    return {
        "candidate": raw,
        "candidate_digest": candidate_digest(candidate),
        "allowed_tool_ids": [tool_name, WRITE_ID],
        "requirement_ids": [r.id for r in candidate.requirements.requirements],
        "inputs": {
            "task": {"objective": "Use observed evidence."},
            "agent": {},
            "tools": json.loads(json.dumps(tools()).replace(READ_ID, tool_name)),
        },
        "episodes": [episode],
        "target_case": case,
        "construction_correction": {
            "failed_episodes": [episode],
            "evidence_ref": report_ref,
            "report": {"status": "failed", "failed_episodes": [episode]},
        },
        "evidence_refs": [
            report_ref,
            ref("/result"),
            {"source": "input", "id": "surface", "path": ""},
        ],
    }


def build(data):
    return RepairInput(data, CandidateV3.model_validate(data["candidate"]), execution_evidence)


@pytest.mark.parametrize("tool_name", ["opaque-operation-17", "document.write", "sensor.read"])
def test_brief_follows_distant_evidence_without_domain_rules(tool_name):
    data = context(1000, tool_name)
    before = deepcopy(data)
    repair = build(data)
    brief = repair.data["repair_brief"]
    assert "early-observation" in brief and "metric/unit" in brief and "17" in brief
    assert '"graph_revision":2' in brief and '"graph_revision":7' in brief
    assert '"coverage":"unknown"' in brief
    assert "unrelated payload" not in brief
    assert "PRIVATE PROVIDER HISTORY" not in brief and "LATEST GRAPH" not in brief
    assert "check_offer" in repair.data["declarations"]["functions"]
    assert "capacity_ok" in repair.data["declarations"]["constraints"]
    assert "episodes" not in repair.data and "candidate" not in repair.data
    assert len(json.dumps(repair.data)) == len(json.dumps(build(context(0, tool_name)).data))
    assert data == before


def test_tool_payload_keys_are_not_execution_links():
    data = context()
    episode = data["episodes"][0]
    episode["result"]["function_ids"] = []
    episode["result"]["observations"][0]["data"] = {"invocation_id": "unrelated-call"}
    episode["result"]["observations"].append(
        {"id": "other", "invocation_id": "unrelated-call", "data": "UNRELATED RECORD"}
    )
    episode["evaluation"]["evidence_refs"] = [ref("/result/observations/0/data")]
    assert "UNRELATED RECORD" not in build(data).data["repair_brief"]


def test_large_evidence_retains_coverage_and_explicit_omissions():
    data = context()
    result = data["episodes"][0]["result"]
    result["function_calls"][0]["result"].update(value=["large" * 1000] * 20, truncated=True)
    repair = build(data)
    assert '"omitted": true' in repair.data["repair_brief"]
    assert "not a complete result" in repair.data["repair_brief"]
    reply = repair.read([ref("/result/function_calls/0/result")])
    assert '"coverage": "observed"' in reply and '"truncated": true' in reply


def test_requested_declaration_can_expand_an_initial_preview():
    data = context()
    declaration = data["candidate"]["functions"][1]
    declaration["parameters"] += [
        {"name": f"parameter_{index}_" + "x" * 100, "type": "string"} for index in range(40)
    ]
    candidate = CandidateV3.model_validate(data["candidate"])
    data["candidate_digest"] = candidate_digest(candidate)
    repair = build(data)
    assert declaration["id"] not in repair.data["declarations"].get("functions", {})
    declaration_ref = next(
        item["ref"]
        for item in repair.data["declaration_index"]
        if item["collection"] == "functions" and item["id"] == declaration["id"]
    )
    repair.read([declaration_ref], requested=True)
    assert repair.data["declarations"]["functions"][declaration["id"]] == candidate.functions[
        1
    ].model_dump(mode="json")
    assert repair.remaining >= 0


async def test_two_evidence_requests_use_saved_records_then_return_patch():
    data = context()
    before = deepcopy(data)
    candidate = CandidateV3.model_validate(data["candidate"])
    declaration = candidate.request_fields[0].model_dump(mode="json")
    updated = {**declaration, "description": "The original requested quantity."}
    citation = ref("/result/observations/0/data/metric~1unit")
    calls, registered = [], []

    async def generate(**kwargs):
        calls.append(deepcopy(kwargs["data"]))
        if len(calls) == 1:
            requested = {"source": "input", "id": "surface", "path": "/task/objective"}
        elif len(calls) == 2:
            assert "Use observed evidence." in calls[-1]["additional_evidence"][0]
            requested = {"source": "input", "id": "surface", "path": "/tools/0/input_schema"}
        else:
            return SimpleNamespace(
                data={
                    "reason": "Clarify the affected request declaration.",
                    "patch": {
                        "id": "repair-1",
                        "base_digest": data["candidate_digest"],
                        "original_input_digest": candidate.original_input_digest,
                        "fault": {
                            "id": "fault-1",
                            "sample_id": "case-1",
                            "requirement_ids": ["party"],
                            "reason": "The saved execution identifies the affected quantity.",
                        },
                        "evidence_refs": [citation],
                        "changes": [
                            {
                                "op": "replace",
                                "collection": "request_fields",
                                "id": declaration["id"],
                                "expected_digest": canonical_digest(declaration),
                                "value": updated,
                            }
                        ],
                    },
                }
            )
        return SimpleNamespace(
            data={
                "reason": "Inspect the saved source.",
                "patch": None,
                "evidence_requests": [requested],
            }
        )

    patch = await propose_repair(None, data, generate, on_evidence=registered.append)
    applied = apply_targeted_patch(
        candidate,
        patch,
        allowed_tool_ids=set(data["allowed_tool_ids"]),
        requirement_ids=set(data["requirement_ids"]),
    )
    assert applied.candidate.request_fields[0].description == updated["description"]
    assert registered == [citation]
    assert [call["evidence_requests_remaining"] for call in calls] == [2, 1, 0]
    assert "additional_evidence" not in calls[0]
    assert data == before


async def test_missing_evidence_stops_after_two_reads_without_patch():
    calls = []

    async def generate(**kwargs):
        calls.append(deepcopy(kwargs["data"]))
        return SimpleNamespace(
            data={
                "reason": "The source is unavailable.",
                "patch": None,
                "evidence_requests": [ref("/result/observations/0", "another-run")],
            }
        )

    assert await propose_repair(None, context(), generate) is None
    assert len(calls) == 3
    assert "unavailable in this saved run" in calls[1]["additional_evidence"][0]


async def test_no_supported_repair_needs_only_one_call():
    calls = []

    async def generate(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            data={"reason": "The evidence does not establish a declaration defect.", "patch": None}
        )

    assert await propose_repair(None, context(), generate) is None
    assert len(calls) == 1


async def test_rejected_evidence_proposal_is_recorded_before_it_stops():
    data = context()
    candidate = CandidateV3.model_validate(data["candidate"])
    declaration = candidate.request_fields[0].model_dump(mode="json")
    proposal = {
        "reason": "Correct the declaration.",
        "patch": {
            "id": "unsupported",
            "base_digest": data["candidate_digest"],
            "original_input_digest": candidate.original_input_digest,
            "fault": {
                "id": "fault",
                "sample_id": "case-1",
                "requirement_ids": ["party"],
                "reason": "Proposed cause.",
            },
            "evidence_refs": [{"source": "input", "id": "surface", "path": "/unavailable"}],
            "changes": [
                {
                    "op": "replace",
                    "collection": "request_fields",
                    "id": declaration["id"],
                    "expected_digest": canonical_digest(declaration),
                    "value": declaration,
                }
            ],
        },
    }
    rejected = []

    async def generate(**kwargs):
        return SimpleNamespace(data=proposal)

    async def record(patch, reason):
        rejected.append((patch.id, reason))

    with pytest.raises(ValueError):
        await propose_repair(None, data, generate, on_rejected=record)
    assert rejected[0][0] == "unsupported"
    assert rejected[0][1]
