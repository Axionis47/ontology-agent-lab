"""Check source coverage and offline decisions without external tool calls."""

from copy import deepcopy

import pytest

from oak.discovery_validation import digest
from oak.kernel_dispatcher import KernelDispatcher
from oak.kernel_validation import (
    CASE_POLICY,
    CASE_REVIEW,
    COVERAGE_POLICY,
    ValidationSuite,
    build_validation_suite,
    replay_validation_suite,
    review_coverage,
    validate_suite_coverage,
)
from oak.repair_schemas import CandidateV2
from tests.kernel_fixtures import (
    DEFAULT_QUERY,
    READ_ID,
    SOURCE,
    WRITE_ID,
    arguments,
    candidate,
    candidate_data,
    tools,
)
from tests.test_request_preparation import (
    ScriptedGeneration,
    extraction,
    ignore_event,
    preservation,
)


def context(data=None):
    return {"candidate": candidate_data() if data is None else data, "evidence_refs": [SOURCE]}


def review(status="passed", refs=None):
    return {
        "status": status,
        "reason": "The cases preserve the cited source requirements.",
        "evidence_refs": [SOURCE] if refs is None else refs,
    }


def observation(*, capacity=4, total_cost=24000, tool_id=READ_ID):
    return {
        "id": "offer-observation",
        "tool_id": tool_id,
        "status": "succeeded",
        "coverage": "unknown",
        "data": {"items": [{"id": "offer-a", "capacity": capacity, "total_cost": total_cost}]},
        "arguments": arguments(),
    }


def case(identifier, tool_id, category, requirement_ids, *, observations=(), changes=None):
    expected = {
        "allowed": "allowed",
        "missing_fact": "missing_evidence",
        "request_mismatch": "rejected",
        "condition_violation": "rejected",
        "unsupported_request": "unsupported_request",
    }[category]
    return {
        "id": identifier,
        "query": DEFAULT_QUERY,
        "tool_id": tool_id,
        "arguments": arguments("offer-a" if tool_id == WRITE_ID else None, **(changes or {})),
        "observations": list(observations),
        "expected": expected,
        "category": category,
        "requirement_ids": requirement_ids,
        "evidence_refs": [SOURCE],
    }


def suite_data():
    cases = [
        case("allow-read", READ_ID, "allowed", ["party", "dates"]),
        case(
            "allow-write",
            WRITE_ID,
            "allowed",
            ["party", "dates", "budget", "capacity"],
            observations=[observation()],
        ),
        case(
            "mismatch-read",
            READ_ID,
            "request_mismatch",
            ["party", "dates"],
            changes={"guests": 1, "start_date": "2027-02-10"},
        ),
        case(
            "mismatch-write",
            WRITE_ID,
            "request_mismatch",
            ["party", "dates"],
            observations=[observation()],
            changes={"guests": 1, "start_date": "2027-02-10"},
        ),
        case("missing-offer", WRITE_ID, "missing_fact", ["budget", "capacity"]),
        case(
            "excess-cost",
            WRITE_ID,
            "condition_violation",
            ["budget"],
            observations=[observation(total_cost=40000)],
        ),
        case(
            "insufficient-capacity",
            WRITE_ID,
            "condition_violation",
            ["capacity"],
            observations=[observation(capacity=2)],
        ),
    ]
    exemptions = []
    for tool_id in (READ_ID, WRITE_ID):
        for rid in ("party", "dates"):
            for category in ("missing_fact", "condition_violation"):
                exemptions.append(
                    {
                        "tool_id": tool_id,
                        "requirement_id": rid,
                        "category": category,
                        "reason": "The original request supplies these values. Exact equality has a mismatch case.",
                        "evidence_refs": [SOURCE],
                    }
                )
    for rid in ("budget", "capacity"):
        exemptions.append(
            {
                "tool_id": WRITE_ID,
                "requirement_id": rid,
                "category": "request_mismatch",
                "reason": "The operation has no proposed budget or capacity parameter.",
                "evidence_refs": [SOURCE],
            }
        )
    return {"cases": cases, "exemptions": exemptions}


def replay_inputs():
    return {"task": {"rules": "Use the supplied catalog."}, "agent": {"id": "a"}, "tools": tools()}


def request_script(suite):
    responses = []
    seen = set()
    for item in suite.cases:
        if item.query in seen:
            continue
        seen.add(item.query)
        responses.append(extraction(query=item.query))
        responses.append(
            preservation(
                "unsupported" if item.category == "unsupported_request" else "passed",
                query=item.query,
                constraint_status="unsupported"
                if item.category == "unsupported_request"
                else "covered",
            )
        )
    return ScriptedGeneration(*responses)


@pytest.mark.parametrize("status", ["passed", "failed", "inconclusive"])
async def test_coverage_review_preserves_fixed_evaluator_status(status):
    generate = ScriptedGeneration(review(status))
    result = await review_coverage(context(), generate)
    assert result["status"] == status
    assert generate.calls[0]["instructions"] == COVERAGE_POLICY


@pytest.mark.parametrize("changed", ["source", "id", "path"])
async def test_coverage_review_rejects_unknown_evidence(changed):
    ref = deepcopy(SOURCE)
    ref[changed] = "input" if changed == "source" else "unknown"
    with pytest.raises(ValueError, match="unknown evidence"):
        await review_coverage(context(), ScriptedGeneration(review(refs=[ref])))


async def test_suite_uses_independent_fixed_review_and_source_coverage():
    data = suite_data()
    generate = ScriptedGeneration(data, review())
    suite, report = await build_validation_suite(context(), generate)
    assert suite.model_dump(mode="json") == data
    assert report["status"] == "passed"
    assert [call["instructions"] for call in generate.calls] == [CASE_POLICY, CASE_REVIEW]
    assert generate.calls[1]["data"]["validation_suite"] == data


@pytest.mark.parametrize("status", ["failed", "inconclusive"])
async def test_nonpassing_case_review_prevents_acceptance(status):
    with pytest.raises(ValueError, match="not supported"):
        await build_validation_suite(context(), ScriptedGeneration(suite_data(), review(status)))


@pytest.mark.parametrize(
    "defect",
    [
        "duplicate_id",
        "unknown_tool",
        "unknown_requirement",
        "wrong_operation",
        "unknown_case_evidence",
        "unknown_exemption_evidence",
        "missing_allowed",
        "missing_category",
        "bad_expected",
    ],
)
async def test_suite_rejects_invalid_or_incomplete_cases_before_review(defect):
    data = suite_data()
    if defect == "duplicate_id":
        data["cases"][1]["id"] = data["cases"][0]["id"]
    elif defect == "unknown_tool":
        data["cases"][0]["tool_id"] = "unknown"
    elif defect == "unknown_requirement":
        data["cases"][0]["requirement_ids"] = ["unknown"]
    elif defect == "wrong_operation":
        data["cases"][0]["requirement_ids"] = ["budget"]
    elif defect == "unknown_case_evidence":
        data["cases"][0]["evidence_refs"] = [{**SOURCE, "path": "/invented"}]
    elif defect == "unknown_exemption_evidence":
        data["exemptions"][0]["evidence_refs"] = [{**SOURCE, "path": "/invented"}]
    elif defect == "missing_allowed":
        data["cases"].pop(0)
    elif defect == "missing_category":
        data["cases"] = [c for c in data["cases"] if c["category"] != "missing_fact"]
    else:
        data["cases"][-1]["expected"] = "missing_evidence"
    generate = ScriptedGeneration(data)
    with pytest.raises(ValueError):
        await build_validation_suite(context(), generate)
    assert len(generate.calls) == 1


async def test_negative_case_for_one_binding_does_not_cover_another():
    data = suite_data()
    data["cases"] = [c for c in data["cases"] if c["id"] != "mismatch-read"]
    with pytest.raises(ValueError, match="enabled operation"):
        await build_validation_suite(context(), ScriptedGeneration(data))


def test_exemption_for_one_binding_does_not_cover_another():
    data = suite_data()
    data["exemptions"] = [
        e
        for e in data["exemptions"]
        if not (
            e["tool_id"] == READ_ID
            and e["requirement_id"] == "party"
            and e["category"] == "missing_fact"
        )
    ]
    with pytest.raises(ValueError, match="enabled operation"):
        validate_suite_coverage(ValidationSuite.model_validate(data), candidate())


async def test_offline_replay_executes_real_checks_without_external_dispatch(monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail("A validation case attempted external dispatch.")

    monkeypatch.setattr(KernelDispatcher, "__call__", forbidden)
    suite = ValidationSuite.model_validate(suite_data())
    before = suite.model_dump(mode="json")
    generate = request_script(suite)
    result = await replay_validation_suite(
        candidate(), suite, replay_inputs(), generate, ignore_event
    )
    assert result["status"] == "passed", result
    assert [r["actual"] for r in result["results"]] == [c.expected for c in suite.cases]
    assert result["suite_digest"] == digest(before)
    assert suite.model_dump(mode="json") == before
    assert len(generate.calls) == len({item.query for item in suite.cases}) * 2


async def test_fixed_counterexample_expectations_detect_a_tautological_repair():
    data = candidate_data()
    condition = next(c for c in data["constraints"] if c["id"] == "budget_ok")
    condition["predicate"]["right"] = deepcopy(condition["predicate"]["left"])
    repaired = CandidateV2.model_validate(data)
    suite = ValidationSuite.model_validate(suite_data())
    before = suite.model_dump(mode="json")
    result = await replay_validation_suite(
        repaired, suite, replay_inputs(), request_script(suite), ignore_event
    )
    assert result["status"] == "failed"
    failed = next(r for r in result["results"] if r["id"] == "excess-cost")
    assert failed["expected"] == "rejected"
    assert failed["actual"] == "allowed"
    assert not failed["passed"]
    assert suite.model_dump(mode="json") == before


async def test_unsupported_request_is_a_supported_negative_expectation():
    data = suite_data()
    unsupported = case("unsupported", WRITE_ID, "unsupported_request", ["capacity"])
    unsupported["query"] += " Require certified sound insulation."
    data["cases"].append(unsupported)
    suite, _ = await build_validation_suite(context(), ScriptedGeneration(data, review()))
    result = await replay_validation_suite(
        candidate(), suite, replay_inputs(), request_script(suite), ignore_event
    )
    assert result["status"] == "passed", result
    assert result["results"][-1]["actual"] == "unsupported_request"
    assert "decision" not in result["results"][-1]


async def test_replay_rejects_an_untested_new_binding_before_preparing_requests():
    data = candidate_data()
    new_binding = deepcopy(data["operation_bindings"][0])
    new_binding.update(id="new-search", tool_id="catalog.new-search")
    data["operation_bindings"].append(new_binding)
    suite = ValidationSuite.model_validate(suite_data())
    generate = ScriptedGeneration()
    result = await replay_validation_suite(
        CandidateV2.model_validate(data), suite, replay_inputs(), generate, ignore_event
    )
    assert result["status"] == "failed"
    assert "allowed validation case" in result["errors"][0]
    assert not generate.calls


async def test_ungranted_observations_cannot_supply_probe_evidence():
    data = suite_data()
    data["cases"][1]["observations"][0]["tool_id"] = "ungranted"
    suite = ValidationSuite.model_validate(data)
    result = await replay_validation_suite(
        candidate(), suite, replay_inputs(), request_script(suite), ignore_event
    )
    failed = next(r for r in result["results"] if r["id"] == "allow-write")
    assert failed["actual"] == "validation_error"
    assert not failed["passed"]


async def test_check_errors_cannot_count_as_successful_rejections():
    data = suite_data()
    item = next(c for c in data["cases"] if c["id"] == "mismatch-read")
    item["arguments"]["guests"] = "not an integer"
    suite = ValidationSuite.model_validate(data)
    result = await replay_validation_suite(
        candidate(), suite, replay_inputs(), request_script(suite), ignore_event
    )
    failed = next(r for r in result["results"] if r["id"] == "mismatch-read")
    assert failed["actual"] == "rejected"
    assert failed["decision"]["error"] == "check_error"
    assert not failed["passed"]


@pytest.mark.parametrize("change", ["expected", "query", "remove_case", "remove_exemption"])
async def test_repair_cannot_replace_fixed_cases_or_exemptions(change):
    fixed = ValidationSuite.model_validate(suite_data())
    changed = suite_data()
    if change == "expected":
        changed["cases"][-1]["expected"] = "allowed"
        changed["cases"][-1]["category"] = "allowed"
    elif change == "query":
        changed["cases"][0]["query"] = "A new request."
    elif change == "remove_case":
        changed["cases"].pop()
    else:
        changed["exemptions"].pop()
    generate = ScriptedGeneration(changed)
    with pytest.raises(ValueError, match="cannot"):
        await build_validation_suite(context(), generate, existing=fixed)
    assert len(generate.calls) == 1
    assert generate.calls[0]["data"]["fixed_validation_suite"] == fixed.model_dump(mode="json")


async def test_candidate_specific_cases_can_be_added_without_rewriting_existing_decisions():
    fixed = ValidationSuite.model_validate(suite_data())
    expanded = suite_data()
    expanded["cases"].append(
        case(
            "new-cost-boundary",
            WRITE_ID,
            "condition_violation",
            ["budget"],
            observations=[observation(total_cost=30001)],
        )
    )
    suite, report = await build_validation_suite(
        context(), ScriptedGeneration(expanded, review()), existing=fixed
    )
    assert suite.cases[:-1] == fixed.cases
    assert report["status"] == "passed"
