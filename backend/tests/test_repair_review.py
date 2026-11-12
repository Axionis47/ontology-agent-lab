"""Verify recorded-input diagnosis before permitting a definition change."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from oak.definition_checks import check_definitions, proposal_key
from oak.graph_query import GraphQuery
from oak.repair_patch import candidate_digest
from oak.repair_review import _context_key, check_reviewed_patch, review_repair
from oak.repair_schemas import CandidateV3
from oak.training_construction import execution_evidence
from tests.kernel_fixtures import READ_ID, arguments
from tests.test_graph_query import supplier_query
from tests.test_operator_library import relation_data


def review_fixture():
    raw = relation_data()
    raw["mappings"][1]["fields"][1]["path"] = "/id"
    candidate = CandidateV3.model_validate(raw)
    observation = {
        "id": "observed",
        "tool_id": READ_ID,
        "status": "succeeded",
        "coverage": "unknown",
        "arguments": arguments(),
        "data": {"items": [], "suppliers": [{"id": "s1", "name": "Acme"}], "complete": True},
    }
    episode = {
        "id": "episode",
        "case_id": "case",
        "case_snapshot": {"id": "case", "query": "Name the supplier."},
        "evaluation": {"status": "failed"},
        "result": {"status": "complete", "observations": [observation]},
    }
    ref = {"source": "artifact", "id": "episode", "path": "/result/observations/0/data/suppliers"}
    context = {
        "episodes": [episode],
        "candidate_digest": candidate_digest(candidate),
        "original_input_digest": candidate.original_input_digest,
        "allowed_tool_ids": [READ_ID],
        "requirement_ids": ["budget"],
        "inputs": {"task": {"objective": "Name the supplier."}},
        "construction_correction": {"failed_episodes": [episode], "validation_kind": "execution"},
        "target_case": episode["case_snapshot"],
        "evidence_refs": [ref],
    }
    proposal = {
        "decision": "definition_defect",
        "reason": "The name mapping reads the identifier.",
        "evidence_refs": [ref],
        "examined": [{"collection": "mappings", "id": "suppliers"}],
        "targets": [{"collection": "mappings", "id": "suppliers"}],
        "probes": [
            {
                "episode_id": "episode",
                "observation_count": 1,
                "query": supplier_query(),
                "expected_ref": ref,
            }
        ],
    }
    return candidate, context, proposal


async def review(candidate, context, proposal):
    async def generate(**kwargs):
        return SimpleNamespace(data=proposal)

    return await review_repair(candidate, context, generate, execution_evidence)


async def test_mapping_defect_replays_the_same_observation_before_and_after():
    candidate, context, proposal = review_fixture()
    record = await review(candidate, context, proposal)
    assert record.verified and record.verification == "recorded_input_replay"
    assert record.replays[0]["actual"]["value"] == [{"id": "s1", "name": "s1"}]
    corrected = CandidateV3.model_validate(relation_data())
    patch = SimpleNamespace(
        changes=[SimpleNamespace(collection="mappings", id="suppliers", op="replace")]
    )
    check_reviewed_patch(record, patch, candidate, corrected, context)
    with pytest.raises(ValueError, match="did not correct"):
        check_reviewed_patch(record, patch, candidate, candidate, context)
    unrelated = SimpleNamespace(
        changes=[SimpleNamespace(collection="functions", id="new", op="add")]
    )
    with pytest.raises(ValueError, match="outside"):
        check_reviewed_patch(record, unrelated, candidate, corrected, context)
    changed = deepcopy(context)
    changed["episodes"][0]["result"]["observations"][0]["data"]["suppliers"][0]["name"] = "Other"
    with pytest.raises(ValueError, match="evidence has changed"):
        check_reviewed_patch(record, patch, candidate, corrected, changed)


@pytest.mark.parametrize(
    "execution,evaluation",
    [
        ("failed", "failed"),
        ("budget_exceeded", "inconclusive"),
        ("complete", "error"),
        ("complete", "inconclusive"),
    ],
)
async def test_tool_limits_and_evaluator_errors_do_not_authorize_repair(execution, evaluation):
    candidate, context, _ = review_fixture()
    episode = context["episodes"][0]
    episode["result"]["status"], episode["evaluation"]["status"] = execution, evaluation

    async def forbidden(**kwargs):
        raise AssertionError("No model diagnosis is warranted.")

    record = await review_repair(candidate, context, forbidden, execution_evidence)
    assert not record.verified and record.decision == "unresolved"


@pytest.mark.parametrize(
    "decision", ["existing_route", "agent_use", "missing_evidence", "unresolved"]
)
async def test_no_change_decisions_remain_unchanged(decision):
    candidate, context, proposal = review_fixture()
    proposal["decision"] = decision
    record = await review(candidate, context, proposal)
    assert not record.verified


async def test_missing_mapping_allows_one_source_supported_addition():
    correct = CandidateV3.model_validate(relation_data())
    candidate, context, proposal = review_fixture()
    raw = correct.model_dump(mode="json")
    raw["mappings"] = raw["mappings"][:1]
    candidate = CandidateV3.model_validate(raw)
    context["candidate_digest"] = candidate_digest(candidate)
    proposal.update(
        decision="missing_definition",
        missing_element="Supplier records have no source mapping.",
        alternatives=["The supplier lookup has no mapped source."],
        examined=[{"collection": "entities", "id": "supplier"}],
    )
    record = await review(candidate, context, proposal)
    assert record.verified and record.verification == "supported_gap"
    patch = SimpleNamespace(
        changes=[SimpleNamespace(collection="mappings", id="suppliers", op="add")]
    )
    check_reviewed_patch(record, patch, candidate, correct, context)
    proposal["targets"] = [{"collection": "functions", "id": "shortcut"}]
    assert not (await review(candidate, context, proposal)).verified


async def test_unrelated_defect_and_invented_expected_result_are_rejected():
    candidate, context, proposal = review_fixture()
    proposal["targets"] = [{"collection": "functions", "id": "check_parameters"}]
    assert not (await review(candidate, context, proposal)).verified
    proposal["probes"][0]["expected_ref"]["path"] = "/result/final_output"
    context["episodes"][0]["result"]["final_output"] = "invented"
    with pytest.raises(ValueError, match="task contract or source observation"):
        await review(candidate, context, proposal)


def test_duplicate_definition_is_rejected_and_constants_require_review():
    raw = relation_data()
    before = CandidateV3.model_validate(raw)
    duplicate = deepcopy(raw["functions"][0])
    duplicate["id"] = "another_name"
    raw["functions"].append(duplicate)
    with pytest.raises(ValueError, match="Duplicate definition"):
        check_definitions(CandidateV3.model_validate(raw), before=before)
    raw = before.model_dump(mode="json")
    raw["functions"][0]["steps"].insert(
        1,
        {
            "op": "lookup",
            "id": "sample",
            "entity_id": "supplier",
            "identity": {"id": {"kind": "literal", "value": "customer-17"}},
        },
    )
    changed = CandidateV3.model_validate(raw)
    receipts = check_definitions(changed, before=before)
    assert receipts[0]["status"] == "requires_review"
    assert receipts[0]["value"] == "customer-17"
    assert "support" not in receipts[0]


def test_rejected_proposal_key_ignores_run_ids_but_tracks_evidence():
    candidate, context, _ = review_fixture()
    patch = SimpleNamespace(changes=[GraphQuery.model_validate(supplier_query())])
    previous = proposal_key(candidate, patch, _context_key(context))
    changed = deepcopy(context)
    changed["episodes"][0]["id"] = "new-run"
    changed["episodes"][0]["result"]["observations"][0]["id"] = "new-observation"
    assert proposal_key(candidate, patch, _context_key(changed)) == previous
    changed["episodes"][0]["result"]["observations"][0]["data"]["suppliers"][0]["name"] = "Changed"
    assert proposal_key(candidate, patch, _context_key(changed)) != previous


async def test_wrong_relation_is_corrected_on_the_recorded_graph():
    candidate, context, proposal = review_fixture()
    raw = relation_data()
    raw["schema"]["relations"][0]["to_property"] = "name"
    candidate = CandidateV3.model_validate(raw)
    context["candidate_digest"] = candidate_digest(candidate)
    context["episodes"][0]["result"]["observations"][0]["data"]["items"] = [
        {"id": "a", "supplier_id": "s1"}
    ]
    query = supplier_query()
    query["parameters"] = raw["functions"][0]["parameters"]
    query["arguments"] = arguments()
    query["steps"][0] = {
        "op": "lookup",
        "id": "start",
        "entity_id": "offer",
        "context": {k: {"kind": "argument", "name": k} for k in arguments()},
    }
    query["steps"].insert(
        1,
        {
            "op": "traverse",
            "id": "rows",
            "input": "start",
            "relation_id": "supplied_by",
            "include_starting_entities": False,
        },
    )
    proposal.update(
        targets=[{"collection": "relations", "id": "supplied_by"}],
        examined=[{"collection": "relations", "id": "supplied_by"}],
    )
    proposal["probes"][0]["query"] = query
    record = await review(candidate, context, proposal)
    assert record.verified
    patch = SimpleNamespace(
        changes=[SimpleNamespace(collection="relations", id="supplied_by", op="replace")]
    )
    check_reviewed_patch(
        record, patch, candidate, CandidateV3.model_validate(relation_data()), context
    )
