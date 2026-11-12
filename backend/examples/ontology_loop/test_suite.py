"""Check the generator, independent scorer, and the typed executor."""

import copy
import json
import random
from pathlib import Path

import pytest

from .kernel import Candidate, Inventory, Policies, Query, reason, validate_candidate
from .suite import FAMILIES, make_suite, public_case, reference, score_episode


@pytest.fixture(scope="module")
def candidate():
    value = Candidate.model_validate_json(Path(__file__).with_name("seed.json").read_text())
    validate_candidate(value)
    return value


def execute(candidate, case):
    return reason(
        candidate,
        Query.model_validate_json(json.dumps(case["query"])),
        Inventory.model_validate_json(json.dumps(case["inventory"])),
        Policies.model_validate_json(json.dumps(case["policies"])),
    )


def compact(result):
    return {
        "status": result["status"],
        "eligible": {item["offer_id"]: item["total_cents"] for item in result["eligible"]},
    }


def test_ten_thousand_worlds_match_independent_reference(candidate):
    families = set()
    outcomes = set()
    for case in make_suite("executor-stress", 70391, 10000):
        expected = reference(case)
        assert compact(execute(candidate, case)) == {
            key: expected[key] for key in ("status", "eligible")
        }, case["name"]
        families.add(case["family"])
        outcomes.add((expected["status"], bool(expected["eligible"])))
    assert families == set(FAMILIES)
    assert outcomes == {("complete", True), ("complete", False), ("incomplete", False)}


def test_splits_are_repeatable_disjoint_and_public_inputs_have_no_gold():
    training = make_suite("training", 11, 24)
    unseen = make_suite("unseen", 11, 24)
    assert training == make_suite("training", 11, 24)
    first_ids = {item["id"] for case in training for item in case["inventory"]["offers"]}
    second_ids = {item["id"] for case in unseen for item in case["inventory"]["offers"]}
    assert not first_ids & second_ids
    public = public_case(training[0])
    assert set(public) == {"name", "query", "inventory", "policies"}
    public["query"]["city"] = "Changed"
    assert training[0]["query"]["city"] != "Changed"


def test_reference_matches_static_examples_and_lexical_action_tie():
    examples = json.loads(Path(__file__).with_name("cases.json").read_text())
    for case in [*examples["training"], examples["held_out"]]:
        result = reference(case)
        assert result["status"] == "complete"
        assert result["eligible"] == case["expected"]
    case = copy.deepcopy(examples["training"][1])
    offer = copy.deepcopy(case["inventory"]["offers"][1])
    offer["id"] = "aaa_tie"
    case["inventory"]["offers"].append(offer)
    assert reference(case)["action"] == "aaa_tie"


def test_record_order_and_identity_renaming_preserve_results(candidate):
    for case in make_suite("metamorphic", 503, 100):
        transformed = copy.deepcopy(case)
        groups = (
            transformed["inventory"]["hotels"],
            transformed["inventory"]["offers"],
            transformed["policies"]["policies"],
        )
        mapping = {record["id"]: f"renamed_{record['id']}" for group in groups for record in group}
        for group in groups:
            random.Random(51).shuffle(group)
            for record in group:
                record["id"] = mapping[record["id"]]
                for field in ("hotel_id", "policy_id"):
                    if field in record and record[field] in mapping:
                        record[field] = mapping[record[field]]
        old = compact(execute(candidate, case))
        new = compact(execute(candidate, transformed))
        assert new["status"] == old["status"]
        assert new["eligible"] == {mapping[key]: value for key, value in old["eligible"].items()}


def test_budget_increase_cannot_remove_an_eligible_offer(candidate):
    for case in make_suite("budget-metamorphic", 411, 100):
        changed = copy.deepcopy(case)
        changed["query"]["budget_cents"] += 100000
        before, after = compact(execute(candidate, case)), compact(execute(candidate, changed))
        assert before["status"] == after["status"]
        assert set(before["eligible"]) <= set(after["eligible"])
        assert all(after["eligible"][key] == value for key, value in before["eligible"].items())


def test_relation_change_changes_the_linked_policy_result(candidate):
    case = make_suite("relation-metamorphic", 145, 1)[0]
    case["inventory"]["offers"] = [case["inventory"]["offers"][0]]
    offer = case["inventory"]["offers"][0]
    hotel = next(item for item in case["inventory"]["hotels"] if item["id"] == offer["hotel_id"])
    hotel["city"] = case["query"]["city"]
    offer.update(capacity=case["query"]["adults"] + 1, nightly_cents=1, fee_cents=0)
    case["policies"]["policies"] = [
        {"id": "allows_children", "minimum_child_age": 0},
        {"id": "adults_only", "minimum_child_age": 18},
    ]
    hotel["policy_id"] = "allows_children"
    assert compact(execute(candidate, case))["eligible"]
    hotel["policy_id"] = "adults_only"
    assert compact(execute(candidate, case))["eligible"] == {}


def test_scoring_uses_first_proposal_and_checks_action():
    case = make_suite("score", 10, 1)[0]
    expected = reference(case)
    answer = {
        "status": "complete",
        "eligible": [
            {"offer_id": key, "total_cents": value} for key, value in expected["eligible"].items()
        ],
    }
    action = {
        "offer_id": expected["action"],
        "total_cents": expected["eligible"][expected["action"]],
    }
    good = {
        "first_proposal": answer,
        "proposals": [answer],
        "answer": answer,
        "action_proposals": [action],
        "actions": [action],
        "completed": True,
    }
    assert score_episode(case, good)["exact_task_success"]
    corrected = copy.deepcopy(good)
    corrected["first_proposal"] = {"status": "complete", "eligible": []}
    corrected["proposals"].insert(0, corrected["first_proposal"])
    score = score_episode(case, corrected)
    assert not score["exact_task_success"]
    assert score["invalid_answer_proposals"] == 1
    assert score["accepted_invalid_answers"] == 0
    duplicate = copy.deepcopy(good)
    duplicate["first_proposal"]["eligible"].append(duplicate["first_proposal"]["eligible"][0])
    assert not score_episode(case, duplicate)["first_answer_correct"]
    wrong_action = copy.deepcopy(good)
    wrong_action["actions"][0]["offer_id"] = "not_a_real_offer"
    assert score_episode(case, wrong_action)["accepted_invalid_actions"] == 1
    assert not score_episode(case, wrong_action)["exact_task_success"]
    missing_action = copy.deepcopy(good)
    missing_action["actions"] = []
    assert not score_episode(case, missing_action)["exact_task_success"]
    corrected_cost = copy.deepcopy(good)
    rejected_action = {**action, "total_cents": action["total_cents"] + 1}
    corrected_cost["action_proposals"].insert(0, rejected_action)
    score = score_episode(case, corrected_cost)
    assert not score["first_action_correct"]
    assert not score["exact_task_success"]
    assert score["invalid_action_proposals"] == 1
    assert score["committed_action_correct"]
    malformed_cost = copy.deepcopy(good)
    malformed_cost["action_proposals"][0]["total_cents"] = str(action["total_cents"])
    assert not score_episode(case, malformed_cost)["first_action_correct"]
