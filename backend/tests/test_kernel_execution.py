"""Check fixed request conditions against exact scoped evidence."""

from copy import deepcopy

import pytest

from oak.evidence_graph import EvidenceGraph
from oak.kernel_execution import compile_function, execute_v2, validate_v2
from oak.repair_schemas import CandidateV2
from tests.kernel_fixtures import (
    DEFAULT_VALUES,
    READ_ID,
    REQUIREMENTS,
    SOURCE,
    WRITE_ID,
    arguments,
    candidate,
    candidate_data,
    observe,
)


def execute(graph, *, offer_id="offer-a", request=None, **changes):
    return execute_v2(
        graph.candidate,
        "check_offer",
        arguments(offer_id, **changes),
        DEFAULT_VALUES if request is None else request,
        graph,
    )


def conditions(result):
    return {item["condition_id"]: item["value"] for item in result["conditions"]}


def altered_graph(change):
    data = candidate_data()
    change(data)
    accepted = CandidateV2.model_validate(data)
    validate_v2(accepted, {READ_ID, WRITE_ID}, REQUIREMENTS)
    return EvidenceGraph(accepted)


def test_observed_subject_does_not_require_complete_collection():
    graph = EvidenceGraph(candidate())
    observe(graph, complete=False)
    result = execute(graph)
    assert result["status"] == "allowed"
    assert conditions(result) == {"capacity_ok": "true", "budget_ok": "true"}
    assert result["graph_revision"] == 1
    assert not graph.collection("offer", arguments()).complete


@pytest.mark.parametrize("complete, expected", [(False, "missing_evidence"), (True, "rejected")])
def test_empty_exact_lookup_never_allows(complete, expected):
    graph = EvidenceGraph(candidate())
    observe(graph, [], complete=complete)
    result = execute(graph)
    assert result["status"] == expected
    assert set(conditions(result).values()) == ({"false"} if complete else {"unknown"})


def test_unobserved_offer_cannot_reuse_another_offer():
    graph = EvidenceGraph(candidate())
    observe(graph)
    result = execute(graph, offer_id="offer-b")
    assert result["status"] == "missing_evidence"
    assert result["evidence_refs"] == []
    assert all(
        gap["identity"] == {"id": "offer-b"} and gap["context"] == arguments()
        for gap in result["missing_dependencies"]
    )


def test_missing_property_identifies_exact_subject_context():
    graph = EvidenceGraph(candidate())
    observe(graph, [{"id": "offer-a", "capacity": 4}])
    result = execute(graph)
    assert result["missing_dependencies"] == [
        {
            "source": "field",
            "property": "total_cost",
            "reason": "unavailable",
            "entity_id": "offer",
            "identity": {"id": "offer-a"},
            "context": arguments(),
        }
    ]


@pytest.mark.parametrize(
    "changes", [{"guests": 1}, {"start_date": "2027-02-10"}, {"end_date": "2027-02-12"}]
)
def test_evidence_must_match_every_scope_component(changes):
    graph = EvidenceGraph(candidate())
    observe(graph)
    result = execute(graph, **changes)
    assert result["status"] == "missing_evidence"


@pytest.mark.parametrize(
    "row, expected_conditions, status",
    [
        (
            {"id": "offer-a", "capacity": 2},
            {"capacity_ok": "false", "budget_ok": "unknown"},
            "rejected",
        ),
        (
            {"id": "offer-a", "total_cost": 40000},
            {"capacity_ok": "unknown", "budget_ok": "false"},
            "rejected",
        ),
        (
            {"id": "offer-a", "capacity": 4},
            {"capacity_ok": "true", "budget_ok": "unknown"},
            "missing_evidence",
        ),
    ],
)
def test_known_false_wins_over_missing_scalar(row, expected_conditions, status):
    graph = EvidenceGraph(candidate())
    observe(graph, [row])
    result = execute(graph)
    assert conditions(result) == expected_conditions
    assert result["status"] == status


def test_missing_request_value_reports_only_its_dependency():
    graph = EvidenceGraph(candidate())
    observe(graph)
    request = {name: value for name, value in DEFAULT_VALUES.items() if name != "budget"}
    result = execute(graph, request=request)
    assert result["status"] == "missing_evidence"
    assert conditions(result) == {"capacity_ok": "true", "budget_ok": "unknown"}
    assert result["missing_dependencies"] == [
        {"source": "request", "property": "budget", "reason": "unavailable"}
    ]


def test_request_and_call_arguments_are_separate_inputs():
    graph = EvidenceGraph(candidate())
    result = execute_v2(
        graph.candidate, "check_parameters", arguments(guests=1), DEFAULT_VALUES, graph
    )
    assert result["status"] == "rejected"
    assert conditions(result)["party_match"] == "false"


def test_nullable_request_absence_is_distinct_from_an_unobserved_value():
    def change(data):
        data["request_fields"][1]["nullable"] = True

    graph = altered_graph(change)
    observe(graph)
    result = execute(graph, request={**DEFAULT_VALUES, "budget": None})
    assert result["status"] == "missing_evidence"
    assert result["missing_dependencies"] == [
        {"source": "request", "property": "budget", "reason": "known_absent"}
    ]


def test_missing_lookup_parameter_is_unknown_and_names_parameter():
    from oak.repair_executor import MISSING

    graph = EvidenceGraph(candidate())
    result = execute(graph, offer_id=MISSING)
    assert result["status"] == "missing_evidence"
    assert {"source": "argument", "property": "offer_id", "reason": "unavailable"} in result[
        "missing_dependencies"
    ]


@pytest.mark.parametrize("invalid", [True, "3", None])
def test_scalar_type_errors_do_not_become_missing_evidence(invalid):
    graph = EvidenceGraph(candidate())
    with pytest.raises(ValueError, match="parameter type"):
        execute(graph, guests=invalid)


def test_replacement_removes_a_previous_allowing_fact():
    graph = EvidenceGraph(candidate())
    observe(graph)
    assert execute(graph)["status"] == "allowed"
    observe(graph, [{"id": "offer-a", "capacity": 4}], identifier="replacement")
    result = execute(graph)
    assert result["status"] == "missing_evidence"
    assert conditions(result)["budget_ok"] == "unknown"


def test_explicit_currency_scale_conversion_is_exact():
    def change(data):
        data["request_fields"][1]["unit"] = "USD"
        data["constraints"][4]["predicate"]["right"] = {
            "kind": "convert",
            "value": {"kind": "request", "name": "budget"},
            "unit": "USD.cent",
        }

    graph = altered_graph(change)
    observe(graph)
    result = execute(graph, request={**DEFAULT_VALUES, "budget": 300})
    assert result["status"] == "allowed"
    assert execute(graph, request={**DEFAULT_VALUES, "budget": 200})["status"] == "rejected"


def test_fractional_conversion_is_an_execution_error():
    def change(data):
        data["request_fields"][1]["unit"] = "USD"
        data["constraints"][4]["predicate"]["left"] = {
            "kind": "convert",
            "value": {"kind": "field", "name": "total_cost"},
            "unit": "USD",
        }

    graph = altered_graph(change)
    observe(graph, [{"id": "offer-a", "capacity": 4, "total_cost": 24001}])
    with pytest.raises(ValueError, match="exact integer"):
        execute(graph, request={**DEFAULT_VALUES, "budget": 300})


def test_multiplication_composes_units_before_budget_comparison():
    def change(data):
        data["schema"]["entities"][0]["properties"][2]["unit"] = "USD.cent/count"
        data["constraints"][4]["predicate"]["left"] = {
            "kind": "multiply",
            "left": {"kind": "field", "name": "total_cost"},
            "right": {"kind": "request", "name": "guests"},
        }

    graph = altered_graph(change)
    observe(graph, [{"id": "offer-a", "capacity": 4, "total_cost": 9000}])
    assert execute(graph)["status"] == "allowed"
    observe(
        graph, [{"id": "offer-a", "capacity": 4, "total_cost": 11000}], identifier="price-update"
    )
    assert execute(graph)["status"] == "rejected"


@pytest.mark.parametrize("unit", [None, "EUR.cent", "USD"])
def test_comparison_requires_identical_units_without_conversion(unit):
    data = candidate_data()
    data["request_fields"][1]["unit"] = unit
    with pytest.raises(ValueError, match="compatible types and units"):
        validate_v2(CandidateV2.model_validate(data), {READ_ID, WRITE_ID}, REQUIREMENTS)


def test_projected_fields_preserve_units_for_later_expressions():
    data = candidate_data()
    function = deepcopy(data["functions"][1])
    function.update(id="project_price", required_constraint_ids=[], return_step="with_fee")
    function["steps"] = [
        function["steps"][0],
        {
            "op": "project",
            "id": "price",
            "input": "offer",
            "fields": [{"name": "amount", "expression": {"kind": "field", "name": "total_cost"}}],
        },
        {
            "op": "project",
            "id": "with_fee",
            "input": "price",
            "fields": [
                {
                    "name": "amount",
                    "expression": {
                        "kind": "add",
                        "left": {"kind": "field", "name": "amount"},
                        "right": {"kind": "literal", "value": 100, "unit": "USD.cent"},
                    },
                }
            ],
        },
    ]
    function["output"] = {
        "kind": "rows",
        "fields": [{"name": "amount", "type": "integer", "unit": "USD.cent"}],
    }
    data["functions"].append(function)
    accepted = CandidateV2.model_validate(data)
    compile_function(accepted, accepted.functions[-1])
    graph = EvidenceGraph(accepted)
    observe(graph)
    result = graph.execute("project_price", arguments("offer-a"), request=DEFAULT_VALUES)
    assert result["value"] == [{"amount": 24100}]


def computation_candidate(
    *, aggregate=None, output_type="integer", nullable=False, unit="USD.cent"
):
    data = candidate_data()
    function = deepcopy(data["functions"][1])
    function.update(id="observed_offers", required_constraint_ids=[], return_step="result")
    lookup = function["steps"][0]
    lookup["identity"] = {}
    function["parameters"] = [
        parameter for parameter in function["parameters"] if parameter["name"] != "offer_id"
    ]
    if aggregate:
        step = {"op": "aggregate", "id": "result", "input": "offer", "operation": aggregate}
        if aggregate != "count":
            step["expression"] = {"kind": "field", "name": "total_cost"}
        function["steps"] = [lookup, step]
        function["output"] = {
            "kind": "scalar",
            "type": output_type,
            "nullable": nullable,
            "unit": unit,
        }
    else:
        function["required_constraint_ids"] = ["budget_ok", "capacity_ok"]
        function["steps"] = [
            lookup,
            {
                "op": "filter",
                "id": "eligible",
                "input": "offer",
                "constraint_ids": ["budget_ok", "capacity_ok"],
            },
            {
                "op": "project",
                "id": "result",
                "input": "eligible",
                "fields": [{"name": "id", "expression": {"kind": "field", "name": "id"}}],
            },
        ]
        function["output"] = {"kind": "rows", "fields": [{"name": "id", "type": "string"}]}
    data["functions"].append(function)
    return CandidateV2.model_validate(data)


def test_computation_filters_observed_rows_without_complete_collection():
    graph = EvidenceGraph(computation_candidate())
    observe(
        graph,
        [
            {"id": "offer-a", "capacity": 4, "total_cost": 24000},
            {"id": "offer-b", "capacity": 2, "total_cost": 10000},
        ],
    )
    result = graph.execute("observed_offers", arguments(), request=DEFAULT_VALUES)
    assert result["status"] == "complete"
    assert result["value"] == [{"id": "offer-a"}]
    assert result["coverage"] == "observed"
    assert all(not step["complete"] for step in result["trace"])


def test_false_filter_condition_excludes_row_with_another_unknown_condition():
    graph = EvidenceGraph(computation_candidate())
    observe(graph, [{"id": "offer-a", "capacity": 2}])
    result = graph.execute("observed_offers", arguments(), request=DEFAULT_VALUES)
    assert result["status"] == "complete"
    assert result["value"] == []


def test_empty_partial_collection_can_return_observed_empty_rows():
    graph = EvidenceGraph(computation_candidate())
    observe(graph, [])
    result = graph.execute("observed_offers", arguments(), request=DEFAULT_VALUES)
    assert result["status"] == "complete"
    assert result["value"] == []


def test_aggregation_requires_authoritative_collection_completeness():
    graph = EvidenceGraph(computation_candidate(aggregate="sum"))
    observe(graph)
    assert (
        graph.execute("observed_offers", arguments(), request=DEFAULT_VALUES)["status"]
        == "incomplete"
    )
    observe(graph, identifier="complete-list", complete=True)
    result = graph.execute("observed_offers", arguments(), request=DEFAULT_VALUES)
    assert result["status"] == "complete"
    assert result["value"] == 24000
    assert result["evidence_refs"]


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"output_type": "string"}, "type or nullability"),
        ({"unit": "EUR.cent"}, "unit differs"),
        ({"aggregate": "min", "nullable": False}, "type or nullability"),
    ],
)
def test_scalar_outputs_must_match_aggregate_type_and_unit(changes, message):
    params = {"aggregate": "sum", **changes}
    accepted = computation_candidate(**params)
    with pytest.raises(ValueError, match=message):
        compile_function(accepted, accepted.functions[-1])


def test_empty_minimum_returns_declared_null():
    graph = EvidenceGraph(computation_candidate(aggregate="min", nullable=True))
    observe(graph, [], complete=True)
    result = graph.execute("observed_offers", arguments(), request=DEFAULT_VALUES)
    assert result["status"] == "complete"
    assert result["value"] is None


def test_aggregate_overflow_is_an_execution_error():
    from oak.repair_executor import MAX_INTEGER

    graph = EvidenceGraph(computation_candidate(aggregate="sum"))
    observe(
        graph,
        [
            {"id": "offer-a", "capacity": 4, "total_cost": MAX_INTEGER},
            {"id": "offer-b", "capacity": 4, "total_cost": 1},
        ],
        complete=True,
    )
    with pytest.raises(ValueError, match="supported integer range"):
        graph.execute("observed_offers", arguments(), request=DEFAULT_VALUES)


def traversal_candidate():
    data = candidate_data()
    data["schema"]["entities"][0]["properties"].extend(
        [{"name": "accommodation_id", "type": "string"}, {"name": "region", "type": "string"}]
    )
    data["mappings"][0]["fields"].extend(
        [
            {"property": "accommodation_id", "path": "/accommodation_id"},
            {"property": "region", "path": "/region"},
        ]
    )
    data["schema"]["entities"].append(
        {
            "id": "accommodation",
            "name": "Accommodation",
            "identity_keys": ["id"],
            "properties": [
                {"name": "id", "type": "string"},
                {"name": "capacity", "type": "integer", "unit": "count"},
            ],
            "requirement_ids": ["capacity"],
        }
    )
    data["schema"].setdefault("relations", []).append(
        {
            "id": "stays_at",
            "name": "Stays at",
            "from_entity": "offer",
            "to_entity": "accommodation",
            "from_property": "accommodation_id",
            "to_property": "id",
            "requirement_ids": ["capacity"],
            "binding_ids": ["source-offer", "source-accommodation"],
        }
    )
    data["schema"].setdefault("bindings", []).extend(
        [
            {
                "id": "source-offer",
                "tool_id": READ_ID,
                "entity_id": "offer",
                "property": "accommodation_id",
                "source": SOURCE,
                "support": "declared",
                "coverage": "unknown",
            },
            {
                "id": "source-accommodation",
                "tool_id": READ_ID,
                "entity_id": "accommodation",
                "property": "id",
                "source": SOURCE,
                "support": "declared",
                "coverage": "unknown",
            },
        ]
    )
    data["mappings"].append(
        {
            "id": "accommodations",
            "entity_id": "accommodation",
            "tool_id": READ_ID,
            "collection_path": "/units",
            "fields": [
                {"property": "id", "path": "/id"},
                {"property": "capacity", "path": "/capacity"},
            ],
            "scope": [{"name": "region", "path": "/unit_context", "source": "data"}],
            "coverage": {"kind": "flag", "path": "/units_complete", "support": SOURCE},
        }
    )
    data["constraints"].append(
        {
            "id": "accommodation_ready",
            "entity_id": "accommodation",
            "requirement_ids": ["capacity"],
            "predicate": {
                "operator": "ge",
                "left": {"kind": "field", "name": "capacity"},
                "right": {"kind": "request", "name": "guests"},
            },
        }
    )
    function = deepcopy(data["functions"][1])
    function.update(id="check_accommodation", required_constraint_ids=["accommodation_ready"])
    function["steps"] = [
        function["steps"][0],
        {
            "op": "traverse",
            "id": "accommodation",
            "input": "offer",
            "relation_id": "stays_at",
            "context": {"region": {"kind": "field", "name": "region"}},
        },
        {
            "op": "assert",
            "id": "checks",
            "input": "accommodation",
            "constraint_ids": ["accommodation_ready"],
        },
        {"op": "decision", "id": "result", "inputs": ["checks"]},
    ]
    data["functions"].append(function)
    return CandidateV2.model_validate(data)


def observe_accommodation(graph, *, region="east", units=None, complete=False, omit=()):
    offer = {
        "id": "offer-a",
        "capacity": 4,
        "total_cost": 24000,
        "accommodation_id": "unit-a",
        "region": "east",
    }
    for name in omit:
        offer.pop(name)
    graph.add(
        {
            "id": "accommodation-result",
            "tool_id": READ_ID,
            "status": "succeeded",
            "coverage": "unknown",
            "data": {
                "items": [offer],
                "complete": False,
                "units": [{"id": "unit-a", "capacity": 4}] if units is None else units,
                "unit_context": region,
                "units_complete": complete,
            },
        },
        arguments=arguments(),
    )


def test_traversal_checks_target_scope_and_reports_exact_missing_subject():
    graph = EvidenceGraph(traversal_candidate())
    observe_accommodation(graph, region="west")
    result = graph.execute("check_accommodation", arguments("offer-a"), request=DEFAULT_VALUES)
    assert result["status"] == "missing_evidence"
    assert any(
        gap.get("entity_id") == "accommodation"
        and gap["identity"] == {"id": "unit-a"}
        and gap["context"] == {"region": "east"}
        for gap in result["missing_dependencies"]
    )


@pytest.mark.parametrize("complete, expected", [(False, "missing_evidence"), (True, "rejected")])
def test_traversal_empty_target_requires_authoritative_absence(complete, expected):
    graph = EvidenceGraph(traversal_candidate())
    observe_accommodation(graph, units=[], complete=complete)
    result = graph.execute("check_accommodation", arguments("offer-a"), request=DEFAULT_VALUES)
    assert result["status"] == expected


@pytest.mark.parametrize("property", ["accommodation_id", "region"])
def test_traversal_missing_source_field_reports_source_scope(property):
    graph = EvidenceGraph(traversal_candidate())
    observe_accommodation(graph, omit=[property])
    result = graph.execute("check_accommodation", arguments("offer-a"), request=DEFAULT_VALUES)
    assert result["status"] == "missing_evidence"
    assert any(
        gap.get("property") == property
        and gap["entity_id"] == "offer"
        and gap["identity"] == {"id": "offer-a"}
        and gap["context"] == arguments()
        for gap in result["missing_dependencies"]
    )


def test_traversal_uses_observed_target_without_complete_target_collection():
    graph = EvidenceGraph(traversal_candidate())
    observe_accommodation(graph)
    result = graph.execute("check_accommodation", arguments("offer-a"), request=DEFAULT_VALUES)
    assert result["status"] == "allowed"
