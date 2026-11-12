"""Run saved cases and a new query through the expanded construction path."""

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from oak.ontology_verification import verify_candidate
from oak.repair_patch import candidate_digest
from oak.repair_schemas import CandidateV3
from oak.training_construction import ConstructionRevision, construct_candidate
from oak.training_evaluation import evaluate_task
from oak.training_runner import run_episode
from tests.kernel_fixtures import (
    DEFAULT_QUERY,
    READ_ID,
    WRITE_ID,
    arguments,
    snapshot,
    tools,
    with_source_access,
)
from tests.test_operator_library import constraint, expr, function, relation_data, rows
from tests.test_training_runner import call


def composed_candidate():
    value = with_source_access(relation_data())
    for mapping in value["mappings"]:
        mapping["coverage"]["support"] = {
            "source": "input",
            "id": "surface",
            "path": "/tools/0/description",
        }
    constraint(
        value,
        "category",
        {
            "operator": "in",
            "left": expr("field", "category"),
            "right": expr("argument", "categories"),
        },
    )
    constraint(
        value,
        "features",
        {
            "operator": "overlap_all",
            "left": expr("field", "features"),
            "right": expr("argument", "features"),
        },
    )
    constraint(
        value,
        "supplier",
        {
            "operator": "connected",
            "relation_ids": ["supplied_by"],
            "anchors": [
                {"entity_id": "supplier", "identity": {"id": expr("argument", "supplier")}}
            ],
        },
    )
    return function(
        value,
        [
            {
                "op": "filter",
                "id": "eligible",
                "input": "source",
                "constraint_ids": ["category", "features", "supplier"],
            },
            {
                "op": "aggregate",
                "id": "result",
                "input": "eligible",
                "operation": "average",
                "expression": expr("field", "amount"),
                "group_by": "customer",
            },
        ],
        {
            "kind": "rows",
            "fields": [
                {"name": "group", "type": "string"},
                {"name": "value", "type": "decimal", "unit": "USD", "nullable": True},
            ],
        },
        required=["category", "features", "supplier"],
        lookup={
            "name_query": expr("argument", "name"),
            "name_fields": ["name"],
            "min_score": "0.8",
        },
        parameters=[
            {"name": "name", "type": "string"},
            {"name": "supplier", "type": "string"},
            {"name": "features", "type": "array", "item_type": "string"},
            {"name": "categories", "type": "array", "item_type": "string"},
        ],
    )


class CaseModel:
    def __init__(self, parameters, expected, harness):
        self.parameters, self.expected, self.harness = parameters, expected, harness
        self.turns = 0

    async def turn(self, messages, tools, **kwargs):
        self.turns += 1
        if self.turns == 1:
            parts = [call("tool_0", arguments())]
        elif self.turns == 2:
            parts = [call("tool_1", arguments("a"))]
        elif self.harness and self.turns == 3:
            parts = [
                call(
                    "run_function",
                    {
                        "function_id": "compute",
                        "arguments_json": json.dumps(arguments(**self.parameters)),
                    },
                )
            ]
        else:
            result = self.expected
            if self.harness:
                responses = [
                    p["function_response"]
                    for m in messages
                    for p in m.get("parts", [])
                    if "function_response" in p
                ]
                response = next(r["response"] for r in responses if r["name"] == "run_function")
                assert response["status"] == "complete", response
                result = response["value"]
            parts = [{"text": json.dumps(result)}]
        return {
            "content": {"role": "model", "parts": parts},
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }


@pytest.mark.asyncio
async def test_saved_cases_construct_composed_function_and_freeze_new_query():
    declarations = composed_candidate()
    cases = [
        (
            "Find the average for Wi-Fi hotels supplied by s1.",
            {
                "name": "Harbor Hotel",
                "features": ["wifi"],
                "categories": ["hotel", "apartment"],
                "supplier": "s1",
            },
            [{"group": "alice", "value": "15.15"}],
        ),
        (
            "Require Wi-Fi and parking for the s1 hotel average.",
            {
                "name": "Harbor Hotel",
                "features": ["wifi", "parking"],
                "categories": ["hotel", "apartment"],
                "supplier": "s1",
            },
            [{"group": "alice", "value": "10.1"}],
        ),
    ]
    observations, events = [], []

    async def emit(kind, payload):
        events.append((kind, deepcopy(payload)))

    async def should_stop():
        return False

    async def transport(tool, args, invocation_id, *, permit):
        permit.consume(tool["id"], args, invocation_id)
        observations.append((tool["id"], deepcopy(args)))
        payload = (
            {
                "items": rows(),
                "suppliers": [{"id": "s1", "name": "Acme"}, {"id": "s2", "name": "Other"}],
                "complete": True,
            }
            if tool["id"] == READ_ID
            else {"id": "booking-1", "offer_id": args["offer_id"]}
        )
        return {"status": "succeeded", "data": payload, "coverage": "unknown"}

    async def episode(case_data, candidate=None, stage="baseline"):
        query, parameters, expected = case_data
        case = {
            "query": DEFAULT_QUERY + " " + query,
            "tool_ids": [READ_ID, WRITE_ID],
            "task_success": "The booking exists. Return the requested customer averages.",
        }
        result = await run_episode(
            case=case,
            tools=tools(),
            candidate=candidate,
            model=CaseModel(parameters, expected, candidate is not None),
            dispatch=transport,
            emit=emit,
            limits={"max_steps": 5},
            should_stop=should_stop,
            run_mode="inference" if stage == "inference" else "training",
            stage=stage,
            request_snapshot=snapshot(query=case["query"]) if candidate else None,
        )
        assert result["status"] == "complete", result

        async def judge(**kwargs):
            actual = json.loads(kwargs["data"]["result"]["final_output"])
            passed = actual == expected and len(result["observations"]) == 2
            return SimpleNamespace(
                data={
                    "status": "passed" if passed else "failed",
                    "reason": "Compare the reported averages and observed booking with the case outcome.",
                    "evidence_refs": kwargs["data"]["evidence_refs"],
                }
            )

        evaluation = await evaluate_task(
            None,
            {
                "case": case,
                "result": result,
                "evidence_refs": [
                    {"source": "artifact", "id": stage + query, "path": "/result/final_output"}
                ],
            },
            judge,
        )
        assert evaluation.status == "passed"
        return {
            "id": stage + query,
            "case_id": query,
            "case_snapshot": case,
            "case": case,
            "result": result,
        }

    baselines = [await episode(case) for case in cases]
    assert all(not episode["result"]["function_calls"] for episode in baselines)
    context = {
        "original_input_digest": declarations["original_input_digest"],
        "discovery": {
            "requirements": declarations["requirements"],
            "schema": declarations["schema"],
        },
        "inputs": {"tools": tools()},
        "allowed_tool_ids": [READ_ID, WRITE_ID],
        "requirement_ids": [r["id"] for r in declarations["requirements"]["requirements"]],
        "episodes": baselines,
    }

    async def construct(**kwargs):
        assert len(kwargs["data"]["episodes"]) == 2
        assert all(e["result"]["observations"] for e in kwargs["data"]["episodes"])
        if kwargs["response_schema"] is ConstructionRevision:
            return SimpleNamespace(
                data={
                    "base_digest": kwargs["data"]["candidate_digest"],
                    "changes": [],
                    "evidence_refs": kwargs["data"]["evidence_refs"],
                }
            )
        assert kwargs["response_schema"] is CandidateV3
        return SimpleNamespace(data=deepcopy(declarations))

    candidate = await construct_candidate(None, context, construct)
    before = candidate_digest(candidate)
    harness = [await episode(case, candidate, "harness") for case in cases]
    assert all(
        set(e["result"]["function_ids"]) == {"check_parameters", "check_offer", "compute"}
        for e in harness
    )
    unseen = (
        "Report the average for the s2 Airport Lodge hostel.",
        {"name": "Airport Lodge", "features": [], "categories": ["hostel"], "supplier": "s2"},
        [{"group": "bob", "value": "30"}],
    )
    result = await episode(unseen, candidate, "inference")
    assert candidate_digest(candidate) == before
    computed = next(c for c in result["result"]["function_calls"] if c["function_id"] == "compute")
    assert computed["result"]["relations"]
    assert computed["result"]["row_metadata"][0]["sources"][0]["identity"] == {"id": "c"}
    assert len(observations) == 10


@pytest.mark.asyncio
async def test_expanded_types_pass_the_real_reasoner(monkeypatch):
    from pathlib import Path

    java = Path("/opt/homebrew/opt/openjdk@21/bin/java")
    if java.exists():
        monkeypatch.setenv("OAK_JAVA", str(java))
    report = await verify_candidate(CandidateV3.model_validate(composed_candidate()))
    assert report["status"] == "passed", report["errors"]


async def test_large_history_uses_every_case_and_retains_early_and_late_evidence():
    from oak.evidence_access import generate_with_evidence, size

    declarations = composed_candidate()
    episodes = [
        {
            "id": str(i),
            "case_id": str(i),
            "case_snapshot": {
                "id": str(i),
                "query": "Check case " + str(i),
                "tool_ids": [READ_ID, WRITE_ID],
            },
            "result": {
                "status": "complete",
                "final_output": "decisive-" + str(i),
                "observations": [{"payload": "unrelated" * 40000}],
            },
        }
        for i in range(8)
    ]
    context = {
        "original_input_digest": declarations["original_input_digest"],
        "discovery": {
            "requirements": declarations["requirements"],
            "schema": declarations["schema"],
        },
        "inputs": {"tools": tools()},
        "allowed_tool_ids": [READ_ID, WRITE_ID],
        "requirement_ids": [r["id"] for r in declarations["requirements"]["requirements"]],
        "episodes": episodes,
        "cases": [e["case_snapshot"] for e in episodes],
    }
    progress, requests, events = [], [], []

    async def emit(kind, value):
        events.append((kind, value))

    async def single(**kwargs):
        data = kwargs["data"]
        requests.append(deepcopy(data))
        if not data["evidence_views"]:
            result = {
                "evidence_requests": [
                    {"id": "case:0", "path": "/result/final_output"},
                    {"id": "case:7", "path": "/result/final_output"},
                ]
            }
        else:
            assert [v["value"] for v in data["evidence_views"][:2]] == ["decisive-0", "decisive-7"]
            result = {"result": declarations}
        return SimpleNamespace(data=kwargs["response_schema"].model_validate(result))

    async def generate(**kwargs):
        return await generate_with_evidence(single, **kwargs, input_tokens=32768, emit=emit)

    async def record_progress(value):
        progress.append(value)

    candidate = await construct_candidate(None, context, generate, on_progress=record_progress)
    assert candidate_digest(candidate) == candidate_digest(CandidateV3.model_validate(declarations))
    assert progress[-1]["considered_case_ids"] == [str(i) for i in range(8)]
    assert len(progress) == 1 and len(requests) == 2
    assert all(size(data) < 32768 * 3 * 0.8 for data in requests)
    assert sum(kind == "evidence_read" for kind, _ in events) >= 2
    with pytest.raises(ValueError, match="every saved case"):
        await construct_candidate(None, {**context, "episodes": episodes[:-1]}, generate)
