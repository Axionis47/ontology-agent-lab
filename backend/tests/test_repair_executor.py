from copy import deepcopy

import pytest

from oak.repair_executor import (
    MAX_INTEGER,
    RecordedObservation,
    execute_function,
    validate_candidate,
)
from oak.repair_schemas import Candidate


def candidate(filtered=False):
    definition = {
        "original_input_digest": "a" * 64,
        "requirements": {
            "requirements": [
                {
                    "id": "minimum",
                    "statement": "Return records that meet the requested minimum.",
                    "evidence": [{"source": "input", "id": "surface", "path": "/rules"}],
                    "tool_ids": ["catalog.list"],
                }
            ],
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
                    "requirement_ids": ["minimum"],
                }
            ],
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
        "constraints": [],
        "functions": [
            {
                "id": "select_records",
                "entity_id": "record",
                "parameters": [{"name": "minimum", "type": "integer"}],
                "required_constraint_ids": [],
                "steps": [
                    {"op": "lookup", "id": "records", "entity_id": "record"},
                    {
                        "op": "project",
                        "id": "result",
                        "input": "records",
                        "fields": [
                            {"name": "id", "expression": {"kind": "field", "name": "id"}},
                            {"name": "amount", "expression": {"kind": "field", "name": "amount"}},
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
    if filtered:
        definition["constraints"].append(
            {
                "id": "minimum",
                "entity_id": "record",
                "requirement_ids": ["minimum"],
                "predicate": {
                    "operator": "ge",
                    "left": {"kind": "field", "name": "amount"},
                    "right": {"kind": "argument", "name": "minimum"},
                },
            }
        )
        function = definition["functions"][0]
        function["required_constraint_ids"] = ["minimum"]
        function["steps"].insert(
            1,
            {
                "op": "filter",
                "id": "eligible",
                "input": "records",
                "constraint_ids": ["minimum"],
            },
        )
        function["steps"][-1]["input"] = "eligible"
    return Candidate.model_validate(definition)


def observed(rows=None, coverage="complete"):
    return [
        {
            "id": "observation-1",
            "tool_id": "catalog.list",
            "status": "succeeded",
            "coverage": coverage,
            "data": {
                "items": rows
                if rows is not None
                else [{"id": "low", "amount": 2}, {"id": "valid", "amount": 9}]
            },
        }
    ]


def run(value, observations=None, **arguments):
    return execute_function(
        value,
        "select_records",
        {"minimum": 5, **arguments},
        observations if observations is not None else observed(),
    )


def test_missing_constraint_changes_execution_and_keeps_valid_records():
    initial, repaired = candidate(), candidate(filtered=True)
    assert validate_candidate(repaired, {"catalog.list"}, {"minimum"}) == []
    assert [r["id"] for r in run(initial)["value"]] == ["low", "valid"]
    outcome = run(repaired)
    assert outcome["status"] == "complete"
    assert outcome["value"] == [{"id": "valid", "amount": 9}]
    assert outcome["trace"][1]["excluded_ids"] == [["low"]]
    assert run(repaired, observed([{"id": "valid", "amount": 9}]))["value"] == [
        {"id": "valid", "amount": 9}
    ]


def test_required_constraint_cannot_be_disconnected_from_return_value():
    value = candidate(True).model_dump(mode="json")
    value["functions"][0]["steps"][-1]["input"] = "records"
    assert "contribute" in validate_candidate(value, {"catalog.list"}, {"minimum"})[0]


@pytest.mark.parametrize("argument", [True, "5", 5.0, MAX_INTEGER + 1])
def test_argument_types_and_range_are_exact(argument):
    with pytest.raises(ValueError, match="Invalid function argument"):
        run(candidate(True), minimum=argument)


@pytest.mark.parametrize(
    "record,issue",
    [
        ({"id": "a"}, "missing"),
        ({"id": "a", "amount": None}, "null"),
        ({"id": "a", "amount": True}, "invalid type"),
        ({"id": "a", "amount": MAX_INTEGER + 1}, "invalid type"),
    ],
)
def test_missing_null_and_wrong_types_do_not_become_filtered_success(record, issue):
    result = run(candidate(True), observed([record]))
    assert result["status"] == "incomplete"
    assert result["value"] is None
    assert issue in result["issues"][0]


def test_sample_coverage_cannot_prove_empty_or_complete_result():
    result = run(candidate(True), observed([], "sample"))
    assert result["status"] == "incomplete"
    assert run(candidate(True), observed([]))["value"] == []


def test_failed_missing_and_ambiguous_observations_remain_incomplete():
    failed = observed()
    failed[0]["status"] = "failed"
    assert run(candidate(), failed)["status"] == "incomplete"
    assert run(candidate(), [])["status"] == "incomplete"
    second = deepcopy(observed()[0])
    second["id"] = "observation-2"
    assert run(candidate(), [*observed(), second])["status"] == "incomplete"


def test_duplicate_identity_is_not_silently_merged():
    result = run(candidate(), observed([{"id": "a", "amount": 2}, {"id": "a", "amount": 8}]))
    assert result["status"] == "incomplete"
    assert "identities" in result["issues"][0]


@pytest.mark.parametrize(
    "operation,empty,expected",
    [("count", 0, 2), ("sum", 0, 11), ("min", None, 2), ("max", None, 9)],
)
def test_aggregates_require_complete_coverage(operation, empty, expected):
    value = candidate().model_dump(mode="json")
    function = value["functions"][0]
    function["steps"][-1] = {
        "id": "result",
        "op": "aggregate",
        "input": "records",
        "operation": operation,
        "expression": None if operation == "count" else {"kind": "field", "name": "amount"},
    }
    function["output"] = {
        "kind": "scalar",
        "type": "integer",
        "nullable": operation in {"min", "max"},
    }
    assert run(value)["value"] == expected
    assert run(value, observed([]))["value"] == empty
    assert run(value, observed(coverage="sample"))["status"] == "incomplete"


def test_unsupported_quantifier_and_executable_fields_are_rejected():
    value = candidate().model_dump(mode="json")
    value["functions"][0]["steps"][-1] = {
        "id": "result",
        "op": "aggregate",
        "input": "records",
        "operation": "all",
        "expression": None,
    }
    assert validate_candidate(value, {"catalog.list"}, {"minimum"})
    value = candidate().model_dump(mode="json")
    value["functions"][0]["code"] = "raise RuntimeError('must not execute')"
    assert validate_candidate(value, {"catalog.list"}, {"minimum"})


def test_unknown_grants_references_and_types_fail_before_execution():
    assert "ungranted" in validate_candidate(candidate(), set(), {"minimum"})[0]
    assert (
        "unknown original requirement"
        in validate_candidate(candidate(), {"catalog.list"}, set())[0]
    )
    value = candidate(True).model_dump(mode="json")
    value["constraints"][0]["predicate"]["left"]["name"] = "absent"
    assert "Unknown field" in validate_candidate(value, {"catalog.list"}, {"minimum"})[0]
    value = candidate(True).model_dump(mode="json")
    value["constraints"][0]["predicate"]["right"] = {"kind": "literal", "value": True}
    assert "same type" in validate_candidate(value, {"catalog.list"}, {"minimum"})[0]


def test_selection_requires_declared_identity_tie_break():
    value = candidate().model_dump(mode="json")
    function = value["functions"][0]
    function["steps"].insert(
        1,
        {
            "id": "best",
            "op": "select_min",
            "input": "records",
            "order_by": [{"kind": "field", "name": "amount"}, {"kind": "field", "name": "id"}],
        },
    )
    function["steps"][-1]["input"] = "best"
    rows = [{"id": "z", "amount": 2}, {"id": "a", "amount": 2}]
    assert run(value, observed(rows))["value"] == [{"id": "a", "amount": 2}]
    function["steps"][1]["order_by"].pop()
    assert "identity" in validate_candidate(value, {"catalog.list"}, {"minimum"})[0]


def test_arithmetic_checks_intermediate_integer_overflow():
    value = candidate().model_dump(mode="json")
    value["functions"][0]["steps"][-1]["fields"][1]["expression"] = {
        "kind": "add",
        "left": {"kind": "field", "name": "amount"},
        "right": {"kind": "literal", "value": 1},
    }
    result = run(value, observed([{"id": "a", "amount": MAX_INTEGER}]))
    assert result["status"] == "incomplete"
    assert "range" in result["issues"][0]


def test_input_snapshots_are_unchanged_by_execution():
    value, observations = candidate(True), observed()
    before = value.model_dump(mode="json"), deepcopy(observations)
    result = run(value, observations)
    assert result["evidence_refs"][0] == {"observation_id": "observation-1", "path": "/items"}
    assert (value.model_dump(mode="json"), observations) == before


def test_escaped_json_pointers_map_actual_observed_fields():
    value = candidate().model_dump(mode="json")
    value["mappings"][0]["fields"][1]["path"] = "/amount~1value"
    result = run(value, observed([{"id": "a", "amount/value": 8}]))
    assert result["value"] == [{"id": "a", "amount": 8}]
    value["mappings"][0]["fields"][1]["path"] = "/amount~2value"
    assert "JSON Pointer" in validate_candidate(value, {"catalog.list"}, {"minimum"})[0]


def test_nullable_argument_is_preserved_only_by_a_nullable_output():
    value = candidate().model_dump(mode="json")
    function = value["functions"][0]
    function["parameters"][0]["nullable"] = True
    function["steps"][-1]["fields"][1]["expression"] = {"kind": "argument", "name": "minimum"}
    function["output"]["fields"][1]["nullable"] = True
    assert run(value, observed([{"id": "a", "amount": 8}]), minimum=None)["value"] == [
        {"id": "a", "amount": None}
    ]
    function["output"]["fields"][1]["nullable"] = False
    assert "output type" in validate_candidate(value, {"catalog.list"}, {"minimum"})[0]


def test_projection_cannot_replace_observed_fields_before_a_required_filter():
    value = candidate(True).model_dump(mode="json")
    function = value["functions"][0]
    fake = deepcopy(function["steps"][-1])
    fake.update(id="fake", input="records")
    fake["fields"][1]["expression"] = {"kind": "literal", "value": 100}
    function["steps"].insert(1, fake)
    function["steps"][2]["input"] = "fake"
    errors = validate_candidate(value, {"catalog.list"}, {"minimum"})
    assert "before projection" in errors[0]
    with pytest.raises(ValueError, match="before projection"):
        run(value)


def related_candidate():
    value = candidate(True).model_dump(mode="json")
    value["schema"]["entities"][0]["properties"].append({"name": "next_id", "type": "string"})
    value["mappings"][0]["fields"].append({"property": "next_id", "path": "/next_id"})
    value["schema"]["bindings"] = [
        {
            "id": name,
            "tool_id": "catalog.list",
            "entity_id": "record",
            "property": name,
            "source": {"source": "artifact", "id": "catalog", "path": f"/{name}"},
            "support": "observed",
            "coverage": "sample",
        }
        for name in ("next_id", "id")
    ]
    value["schema"]["relations"] = [
        {
            "id": "next",
            "name": "Next record",
            "from_entity": "record",
            "to_entity": "record",
            "from_property": "next_id",
            "to_property": "id",
            "requirement_ids": ["minimum"],
            "binding_ids": ["next_id", "id"],
        }
    ]
    function = value["functions"][0]
    function["steps"].insert(
        1, {"id": "linked", "op": "traverse", "input": "records", "relation_id": "next"}
    )
    function["steps"][2]["input"] = "linked"
    return value


def test_traversal_uses_declared_relation_and_actual_targets():
    value = related_candidate()
    assert validate_candidate(value, {"catalog.list"}, {"minimum"}) == []
    rows = [{"id": "a", "amount": 2, "next_id": "b"}, {"id": "b", "amount": 9, "next_id": "a"}]
    result = run(value, observed(rows))
    assert result["status"] == "complete"
    assert result["value"] == [{"id": "b", "amount": 9}]
    rows[0]["next_id"] = "absent"
    result = run(value, observed(rows))
    assert result["status"] == "incomplete"
    assert "no observed target" in result["issues"][0]


def test_self_traversal_cannot_reuse_a_guard_for_different_records():
    value = related_candidate()
    function = value["functions"][0]
    lookup, traversal, filtering, projection = function["steps"]
    filtering["input"] = "records"
    traversal["input"] = "eligible"
    projection["input"] = "linked"
    function["steps"] = [lookup, filtering, traversal, projection]
    assert "Required constraints" in validate_candidate(value, {"catalog.list"}, {"minimum"})[0]


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", 1),
        ("tool_id", False),
        ("status", "SUCCESS"),
        ("coverage", "yes"),
    ],
)
def test_recorded_observation_envelope_is_strict(field, value):
    observation = observed()[0]
    observation[field] = value
    with pytest.raises(ValueError):
        run(candidate(), [observation])


def test_recorded_observation_rejects_extra_fields_and_non_json_data():
    observation = observed()[0]
    observation["claimed_constraint_pass"] = True
    with pytest.raises(ValueError):
        run(candidate(), [observation])
    observation = observed()[0]
    observation["data"] = {"items": {1, 2}}
    with pytest.raises(ValueError):
        RecordedObservation.model_validate(observation)


def test_recorded_observation_model_is_accepted_without_mutation():
    observation = RecordedObservation.model_validate(observed()[0])
    assert run(candidate(True), [observation])["status"] == "complete"
