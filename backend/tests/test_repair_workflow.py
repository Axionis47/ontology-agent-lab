"""Check repair acceptance against independent evaluator results."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from oak.discovery_validation import digest
from oak.repair_executor import execute_function
from oak.repair_patch import candidate_digest
from oak.repair_schemas import Candidate, TargetedPatch
from oak.repair_workflow import (
    CaseEvaluation,
    CriterionEvaluation,
    EvaluationSuite,
    RepairCase,
    RepairContract,
    RepairSession,
)


@pytest.fixture
def contract():
    return RepairContract(
        task_text="Return records whose amount is at least the requested minimum. Preserve each source amount.",
        granted_tool_ids=("catalog.list",),
        cases=tuple(
            RepairCase(
                id=case_id,
                query=query,
                tool_ids=("catalog.list",),
                criterion_ids=("minimum",),
            )
            for case_id, query in (
                ("boundary", "Return records with an amount of at least 10."),
                ("above", "Return records with an amount of at least 5."),
                ("other", "Return records with an amount of at least 20."),
            )
        ),
        evaluator_id="record-evaluator",
        evaluator_version="v1",
        discovery_digest="d" * 64,
    )


@pytest.fixture
def candidate(contract):
    return Candidate.model_validate(
        {
            "original_input_digest": contract.digest,
            "requirements": {
                "requirements": [
                    {
                        "id": "r-minimum",
                        "statement": contract.task_text,
                        "evidence": [{"source": "input", "id": "surface", "path": "/task_text"}],
                        "tool_ids": ["catalog.list"],
                    }
                ]
            },
            "schema": {
                "entities": [
                    {
                        "id": "record",
                        "name": "Record",
                        "properties": [
                            {"name": "id", "type": "string"},
                            {"name": "amount", "type": "integer"},
                        ],
                        "identity_keys": ["id"],
                        "requirement_ids": ["r-minimum"],
                    }
                ]
            },
            "mappings": [
                {
                    "id": "records",
                    "entity_id": "record",
                    "tool_id": "catalog.list",
                    "collection_path": "/items",
                    "fields": [
                        {"property": "id", "path": "/id"},
                        {"property": "amount", "path": "/amount"},
                    ],
                }
            ],
            "constraints": [
                {
                    "id": "minimum",
                    "entity_id": "record",
                    "requirement_ids": ["r-minimum"],
                    "predicate": {
                        "operator": "ge",
                        "left": {"kind": "field", "name": "amount"},
                        "right": {"kind": "argument", "name": "minimum"},
                    },
                }
            ],
            "functions": [
                {
                    "id": "select_records",
                    "entity_id": "record",
                    "parameters": [{"name": "minimum", "type": "integer"}],
                    "required_constraint_ids": ["minimum"],
                    "steps": [
                        {"op": "lookup", "id": "all", "entity_id": "record"},
                        {
                            "op": "filter",
                            "id": "eligible",
                            "input": "all",
                            "constraint_ids": ["minimum"],
                        },
                        {
                            "op": "project",
                            "id": "result",
                            "input": "eligible",
                            "fields": [
                                {"name": "id", "expression": {"kind": "field", "name": "id"}},
                                {
                                    "name": "amount",
                                    "expression": {
                                        "kind": "add",
                                        "left": {"kind": "field", "name": "amount"},
                                        "right": {"kind": "literal", "value": 1},
                                    },
                                },
                            ],
                        },
                    ],
                    "return_step": "result",
                    "output": {
                        "kind": "rows",
                        "fields": [
                            {"name": "id", "type": "string"},
                            {"name": "amount", "type": "integer"},
                        ],
                    },
                }
            ],
        }
    )


def boundary_patch(candidate, patch_id="include-boundary"):
    function = candidate.functions[0].model_dump(mode="json")
    updated = deepcopy(function)
    updated["steps"][-1]["fields"][1]["expression"] = {"kind": "field", "name": "amount"}
    return TargetedPatch.model_validate(
        {
            "id": patch_id,
            "base_digest": candidate_digest(candidate),
            "original_input_digest": candidate.original_input_digest,
            "fault": {
                "id": "source-amount-changed",
                "sample_id": "boundary",
                "requirement_ids": ["r-minimum"],
                "reason": "The function changes the source amount instead of preserving it.",
            },
            "evidence_refs": [
                {"source": "artifact", "id": "boundary-observation", "path": "/items"}
            ],
            "changes": [
                {
                    "collection": "functions",
                    "op": "replace",
                    "id": "select_records",
                    "expected_digest": digest(function),
                    "value": updated,
                }
            ],
        }
    )


def replace(value, **changes):
    return value.model_copy(update=changes)


def suite(contract, candidate_version, statuses=None, mode="native"):
    statuses = statuses or {}
    return EvaluationSuite(
        contract_digest=contract.digest,
        candidate_digest=candidate_version,
        evaluator_id=contract.evaluator_id,
        evaluator_version=contract.evaluator_version,
        mode=mode,
        cases=tuple(
            CaseEvaluation(
                case_id=case.id,
                criteria=tuple(
                    CriterionEvaluation(
                        criterion_id=criterion_id,
                        status=statuses.get(case.id, "passed"),
                        evidence_refs=(f"observation:{case.id}",),
                    )
                    for criterion_id in case.criterion_ids
                ),
                execution_status="complete",
                trace_complete=True,
                environment_digest=digest({"case": case.id, "fixture": "original"}),
                function_ids=("select_records",),
            )
            for case in contract.cases
        ),
    )


def started_session(contract, candidate, statuses=None, mode="native"):
    session = RepairSession(contract, candidate)
    session.record_baseline(
        suite(
            contract,
            candidate_digest(candidate),
            {"boundary": "failed", **(statuses or {})},
            mode=mode,
        )
    )
    return session


def propose_boundary(session, candidate, patch_id="include-boundary"):
    return session.propose(
        boundary_patch(candidate, patch_id),
        target_case_id="boundary",
        target_criterion_ids=("minimum",),
    )


def test_targeted_repair_preserves_original_and_unrelated_artifacts(contract, candidate):
    before = candidate.model_dump(mode="json")
    version = candidate_digest(candidate)
    session = started_session(contract, candidate)
    record = propose_boundary(session, candidate)
    proposed = session.candidate(record.candidate_digest).model_dump(mode="json")

    expected = deepcopy(before)
    expected["functions"][0]["steps"][-1]["fields"][1]["expression"] = {
        "kind": "field",
        "name": "amount",
    }
    assert proposed == expected
    assert session.candidate(version).model_dump(mode="json") == before
    assert candidate.model_dump(mode="json") == before
    assert candidate_digest(session.candidate()) == version


def test_target_fix_cannot_hide_regression_in_a_previously_passing_case(contract, candidate):
    session = started_session(contract, candidate)
    record = propose_boundary(session, candidate)
    result = session.assess(
        "include-boundary",
        suite(contract, record.candidate_digest, {"above": "failed"}),
    )

    assert result.state == "rejected"
    assert result.reasons
    assert candidate_digest(session.candidate()) == candidate_digest(candidate)
    with pytest.raises(ValueError):
        session.pin_for_inference()


@pytest.mark.parametrize("status", ["inconclusive", "error"])
def test_inconclusive_or_error_replaces_no_prior_pass(contract, candidate, status):
    session = started_session(contract, candidate)
    record = propose_boundary(session, candidate)
    result = session.assess(
        "include-boundary", suite(contract, record.candidate_digest, {"above": status})
    )
    assert result.state == "rejected"


def test_unrelated_existing_failure_leaves_a_useful_repair_provisional(contract, candidate):
    session = started_session(contract, candidate, {"other": "failed"})
    record = propose_boundary(session, candidate)
    result = session.assess(
        "include-boundary",
        suite(contract, record.candidate_digest, {"other": "failed"}),
    )

    assert result.state == "provisional"
    assert candidate_digest(session.candidate()) == record.candidate_digest
    with pytest.raises(ValueError):
        session.pin_for_inference()


def test_offline_pass_does_not_claim_native_inference_readiness(contract, candidate):
    session = started_session(contract, candidate, mode="offline")
    record = propose_boundary(session, candidate)
    result = session.assess(
        "include-boundary", suite(contract, record.candidate_digest, mode="offline")
    )

    assert result.state == "provisional"
    with pytest.raises(ValueError):
        session.pin_for_inference()


@pytest.mark.parametrize("missing", ["case", "criterion"])
def test_incomplete_evaluator_suite_cannot_approve_a_patch(contract, candidate, missing):
    session = started_session(contract, candidate)
    record = propose_boundary(session, candidate)
    evaluation = suite(contract, record.candidate_digest)
    if missing == "case":
        evaluation = replace(evaluation, cases=evaluation.cases[:-1])
    else:
        evaluation = replace(
            evaluation,
            cases=(replace(evaluation.cases[0], criteria=()), *evaluation.cases[1:]),
        )

    with pytest.raises(ValueError):
        session.assess("include-boundary", evaluation)
    assert candidate_digest(session.candidate()) == candidate_digest(candidate)


@pytest.mark.parametrize("field", ["candidate_digest", "contract_digest", "evaluator_version"])
def test_results_are_bound_to_candidate_inputs_and_evaluator(contract, candidate, field):
    session = started_session(contract, candidate)
    record = propose_boundary(session, candidate)
    evaluation = suite(contract, record.candidate_digest)
    evaluation = replace(evaluation, **{field: "wrong-version"})

    with pytest.raises(ValueError):
        session.assess("include-boundary", evaluation)


@pytest.mark.parametrize(
    "execution_status,trace_complete", [("unknown", True), ("failed", True), ("complete", False)]
)
def test_passing_evaluator_labels_do_not_erase_failed_or_unknown_execution(
    contract, candidate, execution_status, trace_complete
):
    session = started_session(contract, candidate)
    record = propose_boundary(session, candidate)
    evaluation = suite(contract, record.candidate_digest)
    evaluation = replace(
        evaluation,
        cases=(
            replace(
                evaluation.cases[0],
                execution_status=execution_status,
                trace_complete=trace_complete,
            ),
            *evaluation.cases[1:],
        ),
    )

    result = session.assess("include-boundary", evaluation)
    assert result.state == "rejected"
    with pytest.raises(ValueError):
        session.pin_for_inference()


def test_duplicate_patch_submission_has_one_candidate_and_conflicting_reuse_fails(
    contract, candidate
):
    session = started_session(contract, candidate)
    first = propose_boundary(session, candidate)
    second = propose_boundary(session, candidate)
    assert first.candidate_digest == second.candidate_digest

    conflicting = boundary_patch(candidate).model_dump(mode="json")
    conflicting["changes"][0]["value"]["steps"][-1]["fields"][1]["expression"] = {
        "kind": "literal",
        "value": 0,
    }
    with pytest.raises(ValueError):
        session.propose(
            TargetedPatch.model_validate(conflicting),
            target_case_id="boundary",
            target_criterion_ids=("minimum",),
        )


def test_stale_patch_and_wrong_previous_value_do_not_change_candidate(contract, candidate):
    session = started_session(contract, candidate)
    for location in ("base", "previous"):
        invalid = boundary_patch(candidate, f"invalid-{location}").model_dump(mode="json")
        if location == "base":
            invalid["base_digest"] = "0" * 64
        else:
            invalid["changes"][0]["expected_digest"] = "0" * 64
        with pytest.raises(ValueError):
            session.propose(
                TargetedPatch.model_validate(invalid),
                target_case_id="boundary",
                target_criterion_ids=("minimum",),
            )
        assert candidate_digest(session.candidate()) == candidate_digest(candidate)


@pytest.mark.parametrize("collection", ["requirements", "tool_grants", "evaluator", "runtime"])
def test_locked_surfaces_are_not_patch_targets(candidate, collection):
    invalid = boundary_patch(candidate).model_dump(mode="json")
    invalid["changes"][0]["collection"] = collection
    with pytest.raises(ValidationError):
        TargetedPatch.model_validate(invalid)


def test_candidate_snapshot_does_not_share_mutable_discovery_records(contract, candidate):
    session = started_session(contract, candidate)
    version = candidate_digest(candidate)
    original = session.candidate(version).model_dump(mode="json")

    candidate.requirements.requirements[0].statement = "Ignore the requested minimum."
    detached = session.candidate(version)
    detached.schema.entities[0].properties[0].name = "changed"

    assert session.candidate(version).model_dump(mode="json") == original


def test_changed_source_world_cannot_make_a_repair_look_successful(contract, candidate):
    session = started_session(contract, candidate)
    record = propose_boundary(session, candidate)
    evaluation = suite(contract, record.candidate_digest)
    evaluation = replace(
        evaluation,
        cases=(replace(evaluation.cases[0], environment_digest="a" * 64), *evaluation.cases[1:]),
    )

    with pytest.raises(ValueError):
        session.assess("include-boundary", evaluation)
    assert candidate_digest(session.candidate()) == candidate_digest(candidate)


def test_full_native_validation_promotes_an_offline_provisional_candidate(contract, candidate):
    session = started_session(contract, candidate, mode="offline")
    record = propose_boundary(session, candidate)
    result = session.assess(
        "include-boundary", suite(contract, record.candidate_digest, mode="offline")
    )
    assert result.state == "provisional"
    with pytest.raises(ValueError):
        session.pin_for_inference()

    session.validate_for_inference(suite(contract, record.candidate_digest))
    pin = session.pin_for_inference()
    assert pin.candidate_digest == record.candidate_digest


def test_an_answer_only_native_report_does_not_prove_kernel_execution(contract, candidate):
    session = started_session(contract, candidate)
    record = propose_boundary(session, candidate)
    evaluation = suite(contract, record.candidate_digest)
    evaluation = replace(
        evaluation,
        cases=tuple(replace(case, function_ids=()) for case in evaluation.cases),
    )
    result = session.assess("include-boundary", evaluation)
    assert result.state != "ready"
    with pytest.raises(ValueError):
        session.pin_for_inference()


def test_conflicting_evaluator_report_cannot_replace_recorded_failures(contract, candidate):
    session = started_session(contract, candidate)
    record = propose_boundary(session, candidate)
    failed = suite(contract, record.candidate_digest, {"above": "failed"})
    assert session.assess("include-boundary", failed).state == "rejected"
    assert session.assess("include-boundary", failed).state == "rejected"

    with pytest.raises(ValueError):
        session.assess("include-boundary", suite(contract, record.candidate_digest))


@pytest.mark.parametrize("drop_declaration", [False, True])
def test_repair_cannot_bypass_required_constraint_enforcement(
    contract, candidate, drop_declaration
):
    session = started_session(contract, candidate)
    invalid = boundary_patch(candidate).model_dump(mode="json")
    function = invalid["changes"][0]["value"]
    function["steps"] = [function["steps"][0], function["steps"][-1]]
    function["steps"][-1]["input"] = "all"
    if drop_declaration:
        function["required_constraint_ids"] = []

    with pytest.raises(ValueError):
        session.propose(
            TargetedPatch.model_validate(invalid),
            target_case_id="boundary",
            target_criterion_ids=("minimum",),
        )
    assert candidate_digest(session.candidate()) == candidate_digest(candidate)


@pytest.mark.parametrize(
    "field", ["task_text", "evaluator_id", "evaluator_version", "discovery_digest"]
)
def test_candidate_cannot_be_reused_under_changed_original_inputs(contract, candidate, field):
    value = "e" * 64 if field == "discovery_digest" else "changed"
    changed_contract = replace(contract, **{field: value})
    with pytest.raises(ValueError):
        RepairSession(changed_contract, candidate)


def test_case_query_and_tool_selection_are_in_the_frozen_input_digest(contract, candidate):
    for changed_case in (
        replace(contract.cases[0], query="Ignore the minimum and return all records."),
        replace(contract.cases[0], tool_ids=("catalog.delete",)),
    ):
        changed_contract = replace(contract, cases=(changed_case, *contract.cases[1:]))
        with pytest.raises(ValueError):
            RepairSession(changed_contract, candidate)


def test_passing_criterion_requires_evidence():
    with pytest.raises(ValidationError):
        CriterionEvaluation(criterion_id="minimum", status="passed", evidence_refs=())


def test_empty_training_set_and_empty_checks_cannot_become_a_vacuous_pass(contract):
    with pytest.raises(ValidationError):
        RepairContract.model_validate({**contract.model_dump(), "cases": ()})
    with pytest.raises(ValidationError):
        RepairCase(id="empty", query="List records.", tool_ids=("catalog.list",), criterion_ids=())


def test_accepted_pin_executes_fixed_function_without_mcp_dispatch(
    contract, candidate, monkeypatch
):
    from mcp import ClientSession

    calls = []

    async def forbidden_call(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Recorded-observation checks must not dispatch MCP calls.")

    monkeypatch.setattr(ClientSession, "call_tool", forbidden_call)
    session = started_session(contract, candidate)
    record = propose_boundary(session, candidate)
    assert (
        session.assess("include-boundary", suite(contract, record.candidate_digest)).state
        == "ready"
    )
    pin = session.pin_for_inference()
    snapshot = session.candidate(pin.candidate_digest).model_dump(mode="json")
    result = session.execute_pinned(
        pin,
        "select_records",
        {"minimum": 10},
        [
            {
                "id": "actual-records",
                "tool_id": "catalog.list",
                "status": "succeeded",
                "coverage": "complete",
                "data": {
                    "items": [
                        {"id": "below", "amount": 9},
                        {"id": "boundary", "amount": 10},
                        {"id": "above", "amount": 11},
                    ]
                },
            }
        ],
    )

    assert result["status"] == "complete"
    assert result["value"] == [
        {"id": "boundary", "amount": 10},
        {"id": "above", "amount": 11},
    ]
    assert result["trace"]
    assert result["evidence_refs"]
    assert calls == []
    assert session.candidate(pin.candidate_digest).model_dump(mode="json") == snapshot
    with pytest.raises(ValueError):
        session.execute_pinned(
            replace(pin, candidate_digest=candidate_digest(candidate)),
            "select_records",
            {"minimum": 10},
            [],
        )


def test_observed_function_failure_drives_repair_and_new_query_execution(contract, candidate):
    samples = {
        "boundary": (10, [{"id": "low", "amount": 9}, {"id": "equal", "amount": 10}]),
        "above": (5, [{"id": "excluded", "amount": 4}]),
        "other": (20, [{"id": "also-excluded", "amount": 19}]),
    }

    def evaluate_observed_outputs(version):
        results = []
        for case in contract.cases:
            minimum, records = samples[case.id]
            observation = {
                "id": f"source:{case.id}",
                "tool_id": "catalog.list",
                "status": "succeeded",
                "coverage": "complete",
                "data": {"items": records},
            }
            actual = execute_function(
                version, "select_records", {"minimum": minimum}, [observation]
            )
            expected = [dict(record) for record in records if record["amount"] >= minimum]
            passed = actual["status"] == "complete" and actual["value"] == expected
            results.append(
                CaseEvaluation(
                    case_id=case.id,
                    environment_digest=digest({"records": records, "minimum": minimum}),
                    criteria=(
                        CriterionEvaluation(
                            criterion_id="minimum",
                            status="passed" if passed else "failed",
                            evidence_refs=(observation["id"], f"function:{case.id}"),
                        ),
                    ),
                    execution_status="complete",
                    trace_complete=True,
                    function_ids=("select_records",),
                    observed_tool_ids=("catalog.list",),
                )
            )
        return EvaluationSuite(
            contract_digest=contract.digest,
            candidate_digest=candidate_digest(version),
            evaluator_id=contract.evaluator_id,
            evaluator_version=contract.evaluator_version,
            mode="offline",
            cases=tuple(results),
        )

    session = RepairSession(contract, candidate)
    baseline = evaluate_observed_outputs(candidate)
    assert [case.criteria[0].status for case in baseline.cases] == ["failed", "passed", "passed"]
    session.record_baseline(baseline)
    record = propose_boundary(session, candidate)
    repaired = evaluate_observed_outputs(session.candidate(record.candidate_digest))
    assert all(case.criteria[0].status == "passed" for case in repaired.cases)
    assert session.assess("include-boundary", repaired).state == "provisional"
    with pytest.raises(ValueError):
        session.pin_for_inference()

    # Supply a trusted runner fixture. This test does not run a native model episode.
    session.validate_for_inference(replace(repaired, mode="native"))
    pin = session.pin_for_inference()
    result = session.execute_pinned(
        pin,
        "select_records",
        {"minimum": 30},
        [
            {
                "id": "new-query-source",
                "tool_id": "catalog.list",
                "status": "succeeded",
                "coverage": "complete",
                "data": {"items": [{"id": "new-low", "amount": 29}, {"id": "new", "amount": 30}]},
            }
        ],
    )
    assert result["status"] == "complete"
    assert result["value"] == [{"id": "new", "amount": 30}]
    assert candidate_digest(session.candidate(pin.candidate_digest)) == record.candidate_digest


def test_reported_tool_must_belong_to_the_sample_selection(contract, candidate):
    contract = replace(contract, granted_tool_ids=("catalog.list", "archive.list"))
    candidate = replace(candidate, original_input_digest=contract.digest)
    session = RepairSession(contract, candidate)
    evaluation = suite(contract, candidate_digest(candidate), {"boundary": "failed"})
    evaluation = replace(
        evaluation,
        cases=(
            replace(evaluation.cases[0], observed_tool_ids=("archive.list",)),
            *evaluation.cases[1:],
        ),
    )
    with pytest.raises(ValueError):
        session.record_baseline(evaluation)


def test_function_dependencies_must_belong_to_the_sample_selection(contract, candidate):
    contract = replace(contract, granted_tool_ids=("catalog.list", "archive.list"))
    payload = candidate.model_dump(mode="json")
    payload["original_input_digest"] = contract.digest
    payload["mappings"][0]["tool_id"] = "archive.list"
    candidate = Candidate.model_validate(payload)
    session = RepairSession(contract, candidate)

    with pytest.raises(ValueError):
        session.record_baseline(
            suite(contract, candidate_digest(candidate), {"boundary": "failed"})
        )


def test_added_function_requires_execution_evidence_before_inference(contract, candidate):
    session = started_session(contract, candidate)
    payload = boundary_patch(candidate).model_dump(mode="json")
    added = deepcopy(payload["changes"][0]["value"])
    added["id"] = "additional_records"
    payload["changes"].append(
        {"collection": "functions", "op": "add", "id": added["id"], "value": added}
    )
    record = session.propose(
        TargetedPatch.model_validate(payload),
        target_case_id="boundary",
        target_criterion_ids=("minimum",),
    )

    result = session.assess("include-boundary", suite(contract, record.candidate_digest))
    assert result.state == "provisional"
    with pytest.raises(ValueError):
        session.pin_for_inference()
