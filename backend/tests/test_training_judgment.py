"""Check the fixed construction contract and semantic evaluation evidence gate."""

from types import SimpleNamespace

import pytest

from oak.model_client import ModelFailure
from oak.repair_schemas import CandidateV3
from oak.training_construction import construct_candidate, execution_evidence
from oak.training_evaluation import TaskEvaluation, evaluate_task
from tests.kernel_fixtures import READ_ID, WRITE_ID, tools, with_source_access
from tests.kernel_fixtures import candidate_data as kernel_candidate_data


def candidate_data():
    value = kernel_candidate_data()
    value["version"] = "oak.candidate.v3"
    value["mappings"][0]["coverage"]["support"] = {
        "source": "input",
        "id": "surface",
        "path": "/tools/0/description",
    }
    return with_source_access(value)


def construction_context():
    candidate = candidate_data()
    return {
        "original_input_digest": candidate["original_input_digest"],
        "discovery": {"requirements": candidate["requirements"], "schema": candidate["schema"]},
        "inputs": {"tools": tools()},
        "allowed_tool_ids": [READ_ID, WRITE_ID],
        "requirement_ids": [r["id"] for r in candidate["requirements"]["requirements"]],
    }


@pytest.mark.asyncio
async def test_construction_keeps_original_contract():
    candidate = CandidateV3.model_validate(candidate_data())

    async def generate(**kwargs):
        assert kwargs["response_schema"] is CandidateV3
        return SimpleNamespace(data=candidate)

    result = await construct_candidate(None, construction_context(), generate)
    assert result == candidate


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["digest", "requirements", "functions", "tools"])
async def test_construction_rejects_contract_change(change):
    value = candidate_data()
    if change == "digest":
        value["original_input_digest"] = "b" * 64
    elif change == "requirements":
        value["requirements"]["requirements"][0]["statement"] = "Ignore the original requirement."
    elif change == "functions":
        value["functions"] = []
    else:
        value["mappings"][0]["tool_id"] = "ungranted"

    async def generate(**kwargs):
        return SimpleNamespace(data=CandidateV3.model_validate(value))

    with pytest.raises(ValueError):
        await construct_candidate(None, construction_context(), generate)


@pytest.mark.asyncio
@pytest.mark.parametrize("execution", ["unknown", "failed", "stopped", "limit"])
async def test_incomplete_episode_cannot_pass(execution):
    async def generate(**kwargs):
        pytest.fail("The evaluator must not judge incomplete execution as successful.")

    result = await evaluate_task(None, {"result": {"status": execution}}, generate)
    assert result.status == "inconclusive"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "citation,expected", [("saved", "passed"), ("invented", "error"), (None, "inconclusive")]
)
async def test_evaluator_requires_saved_evidence(citation, expected):
    ref = {"source": "artifact", "id": "saved", "path": "/result/final_output"}

    async def generate(**kwargs):
        return SimpleNamespace(
            data=TaskEvaluation(
                status="passed",
                reason="The result establishes the requested outcome.",
                evidence_refs=[{**ref, "id": citation}] if citation else [],
            )
        )

    result = await evaluate_task(
        None,
        {
            "case": {},
            "result": {"status": "complete", "final_output": "Done"},
            "evidence_refs": [ref],
        },
        generate,
    )
    assert result.status == expected


def test_model_context_keeps_execution_evidence_without_repeated_provider_history():
    observation = {"id": "write-1", "status": "succeeded", "data": {"id": "note-2"}}
    result = {
        "status": "complete",
        "final_output": "Created note-2.",
        "observations": [observation],
        "function_calls": [{"function_id": "notes"}],
        "trace": [
            {"kind": "model_request", "request": {"messages": "repeated history"}},
            {"kind": "tool_rejected", "error": "Invalid argument"},
        ],
    }
    evidence = execution_evidence(result)
    assert evidence["observations"] == [observation]
    assert evidence["function_calls"] == result["function_calls"]
    assert evidence["trace"] == [None, {"kind": "tool_rejected", "error": "Invalid argument"}]
    assert len(result["trace"]) == 2
    assert execution_evidence(evidence) == evidence


@pytest.mark.parametrize(
    "path,expected",
    [
        ("/result/observations/0/data/a~1b~0c", "passed"),
        ("/result/observations/0/data/nullable", "passed"),
        ("/result/observations/9", "error"),
        ("/result/observations_extra", "error"),
        ("/result/observations/0/data/a~2b", "error"),
        ("/result/trace/0/response", "error"),
    ],
)
async def test_evaluator_accepts_only_existing_visible_child_references(path, expected):
    calls = []

    async def generate(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            data=TaskEvaluation(
                status="passed",
                reason="The cited value establishes the result.",
                evidence_refs=[{"source": "artifact", "id": "saved", "path": path}],
            )
        )

    result = await evaluate_task(
        None,
        {
            "case": {},
            "result": {
                "status": "complete",
                "observations": [{"data": {"a/b~c": 17, "nullable": None}}],
                "trace": [{"kind": "model_response", "response": "Not supplied to the evaluator."}],
            },
            "evidence_refs": [
                {"source": "artifact", "id": "saved", "path": "/result/" + key}
                for key in ("observations", "trace")
            ],
        },
        generate,
    )
    assert result.status == expected
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_initial_construction_corrects_a_bounded_validation_error():
    calls = []

    async def generate(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            error = ModelFailure("invalid_output")
            error.validation_errors = [
                {"loc": ["functions", 0, "steps"], "msg": "Invalid operator"}
            ]
            error.failed_output = {"functions": [{"steps": ["invalid"]}]}
            raise error
        return SimpleNamespace(data=CandidateV3.model_validate(candidate_data()))

    result = await construct_candidate(None, construction_context(), generate)
    assert result.original_input_digest == "a" * 64
    assert len(calls) == 2
    assert calls[1]["data"]["construction_correction"]["issues"][0]["msg"] == "Invalid operator"


@pytest.mark.asyncio
async def test_initial_mapping_is_checked_against_actual_baseline_data():
    context = construction_context()
    context["episodes"] = [
        {
            "id": "baseline-1",
            "case_id": "sample-1",
            "result": {
                "observations": [
                    {
                        "status": "succeeded",
                        "tool_id": READ_ID,
                        "data": {"items": []},
                    }
                ]
            },
        }
    ]
    calls = []

    async def generate(**kwargs):
        calls.append(kwargs)
        value = candidate_data()
        if len(calls) == 1:
            value["mappings"][0]["collection_path"] = "/data/items"
        return SimpleNamespace(data=CandidateV3.model_validate(value))

    candidate = await construct_candidate(None, context, generate)
    assert candidate.mappings[0].collection_path == "/items"
    assert len(calls) == 2
    assert "observation.data" in calls[1]["data"]["construction_correction"]["issues"][0]
