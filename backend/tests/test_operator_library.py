"""Check Appendix B behavior against independently specified task results."""

from copy import deepcopy
from fractions import Fraction

import pytest

from oak.evidence_graph import EvidenceGraph, GraphIngestionError
from oak.kernel_execution import compile_function, validate_v2
from oak.kernel_values import decimal_text, valid_value, value_schema
from oak.ontology_verification import encode_ontology
from oak.repair_patch import candidate_digest
from oak.repair_schemas import Candidate, CandidateV3, Parameter
from oak.request_preparation import RequestExtraction, validate_extraction
from tests.kernel_fixtures import (
    DEFAULT_VALUES,
    READ_ID,
    REQUIREMENTS,
    WRITE_ID,
    arguments,
    candidate_data,
    observe,
)
from tests.test_kernel_dispatcher import Harness


def expr(kind, name):
    return {"kind": kind, "name": name}


def literal(value, **spec):
    return (
        {"kind": "typed_literal", "value": value, **spec}
        if spec
        else {"kind": "literal", "value": value}
    )


def data():
    value = candidate_data()
    value["version"] = "oak.candidate.v3"
    properties = [
        {"name": "features", "type": "array", "item_type": "string"},
        {"name": "category", "type": "string"},
        {"name": "customer", "type": "string"},
        {"name": "amount", "type": "decimal", "unit": "USD"},
        {"name": "name", "type": "string"},
        {"name": "supplier_id", "type": "string"},
    ]
    value["schema"]["entities"][0]["properties"].extend(properties)
    value["mappings"][0]["fields"].extend(
        {"property": p["name"], "path": "/" + p["name"]} for p in properties
    )
    return value


def function(value, steps, output, *, required=(), lookup=None, parameters=()):
    root = {
        "op": "lookup",
        "id": "source",
        "entity_id": "offer",
        "context": {name: expr("argument", name) for name in arguments()},
    }
    root.update(lookup or {})
    value["functions"].append(
        {
            "id": "compute",
            "parameters": [*deepcopy(value["functions"][0]["parameters"]), *parameters],
            "steps": [root, *steps],
            "required_constraint_ids": list(required),
            "return_step": steps[-1]["id"] if steps else "source",
            "output": output,
        }
    )
    return value


def graph(value):
    candidate = CandidateV3.model_validate(value)
    validate_v2(candidate, {READ_ID, WRITE_ID}, REQUIREMENTS)
    return EvidenceGraph(candidate)


def rows():
    return [
        {
            "id": "a",
            "capacity": 4,
            "total_cost": 100,
            "features": ["wifi", "parking", "wifi"],
            "category": "hotel",
            "customer": "alice",
            "amount": "10.10",
            "name": "Harbor Hotel",
            "supplier_id": "s1",
        },
        {
            "id": "b",
            "capacity": 4,
            "total_cost": 200,
            "features": ["wifi"],
            "category": "apartment",
            "customer": "alice",
            "amount": "20.20",
            "name": "Harbour Hotel",
            "supplier_id": "s1",
        },
        {
            "id": "c",
            "capacity": 4,
            "total_cost": 300,
            "features": [],
            "category": "hostel",
            "customer": "bob",
            "amount": "30",
            "name": "Airport Lodge",
            "supplier_id": "s2",
        },
    ]


def execute(value, records=None, *, complete=True, args=None):
    observed = graph(value)
    observe(observed, rows() if records is None else records, complete=complete)
    return observed.execute("compute", arguments(**(args or {})), request=DEFAULT_VALUES)


def constraint(value, identifier, predicate, entity_id="offer"):
    value["constraints"].append(
        {
            "id": identifier,
            "entity_id": entity_id,
            "requirement_ids": ["budget"],
            "predicate": predicate,
        }
    )


def projected_ids(source):
    return {
        "op": "project",
        "id": "result",
        "input": source,
        "fields": [{"name": "id", "expression": expr("field", "id")}],
    }


IDS_OUTPUT = {"kind": "rows", "fields": [{"name": "id", "type": "string"}]}


@pytest.mark.parametrize(
    "operator,requested,minimum,expected",
    [
        ("overlap_all", ["wifi", "parking"], None, ["a"]),
        ("overlap_any", ["wifi", "parking"], None, ["a", "b"]),
        ("overlap_min", ["wifi", "wifi", "parking"], 2, ["a"]),
        ("overlap_min", ["wifi", "wifi"], 2, []),
        ("overlap_all", [], None, ["a", "b", "c"]),
        ("overlap_any", [], None, []),
        ("overlap_min", [], 0, ["a", "b", "c"]),
    ],
)
def test_set_overlap(operator, requested, minimum, expected):
    value = data()
    predicate = {
        "operator": operator,
        "left": expr("field", "features"),
        "right": literal(requested, type="array", item_type="string"),
    }
    if minimum is not None:
        predicate["minimum"] = literal(minimum)
    constraint(value, "features_ok", predicate)
    function(
        value,
        [
            {
                "op": "filter",
                "id": "eligible",
                "input": "source",
                "constraint_ids": ["features_ok"],
            },
            projected_ids("eligible"),
        ],
        IDS_OUTPUT,
        required=["features_ok"],
    )
    result = execute(value)
    assert result["value"] == [{"id": identifier} for identifier in expected]
    assert result["evidence_refs"]
    assert len(result["trace"][1]["excluded_ids"]) == 3 - len(expected)
    assert len(result["trace"][1]["input"]) == 3
    assert len(result["trace"][1]["excluded_records"]) == 3 - len(expected)
    assert result["trace"][1]["evaluated_operands"][0]["expression"] == expr("field", "features")


def test_categorical_inclusion_exclusion_and_missing_values():
    value = data()
    for identifier, operator, allowed in [
        ("included", "in", ["hotel", "apartment"]),
        ("excluded", "not_in", ["apartment"]),
    ]:
        constraint(
            value,
            identifier,
            {
                "operator": operator,
                "left": expr("field", "category"),
                "right": literal(allowed, type="array", item_type="string"),
            },
        )
    function(
        value,
        [
            {
                "op": "filter",
                "id": "eligible",
                "input": "source",
                "constraint_ids": ["included", "excluded"],
            },
            projected_ids("eligible"),
        ],
        IDS_OUTPUT,
        required=["included", "excluded"],
    )
    assert execute(value)["value"] == [{"id": "a"}]
    missing = rows()
    del missing[0]["category"]
    assert execute(value, missing)["status"] == "incomplete"


@pytest.mark.parametrize(
    "operation,expected",
    [
        ("count", [2, 1]),
        ("sum", ["30.3", "30"]),
        ("min", ["10.1", "30"]),
        ("max", ["20.2", "30"]),
        ("average", ["15.15", "30"]),
    ],
)
def test_grouped_aggregation(operation, expected):
    value = data()
    step = {
        "op": "aggregate",
        "id": "result",
        "input": "source",
        "operation": operation,
        "group_by": "customer",
    }
    if operation != "count":
        step["expression"] = expr("field", "amount")
    output = {
        "kind": "rows",
        "fields": [
            {"name": "group", "type": "string"},
            {
                "name": "value",
                "type": "integer" if operation == "count" else "decimal",
                "unit": None if operation == "count" else "USD",
                "nullable": operation in {"min", "max", "average"},
            },
        ],
    }
    function(value, [step], output)
    result = execute(value)
    assert result["value"] == [
        {"group": "alice", "value": expected[0]},
        {"group": "bob", "value": expected[1]},
    ]
    assert [len(row["sources"]) for row in result["row_metadata"]] == [2, 1]
    assert execute(value, complete=False)["status"] == "incomplete"
    assert execute(value, [])["value"] == []
    missing = rows()
    del missing[0]["customer"]
    assert execute(value, missing)["status"] == "incomplete"


@pytest.mark.parametrize(
    "operation,expected",
    [("count", 0), ("sum", "0"), ("min", None), ("max", None), ("average", None)],
)
def test_empty_scalar_aggregates(operation, expected):
    value = data()
    step = {"op": "aggregate", "id": "result", "input": "source", "operation": operation}
    if operation != "count":
        step["expression"] = expr("field", "amount")
    function(
        value,
        [step],
        {
            "kind": "scalar",
            "type": "integer" if operation == "count" else "decimal",
            "unit": None if operation == "count" else "USD",
            "nullable": operation in {"min", "max", "average"},
        },
    )
    assert execute(value, [])["value"] == expected


def test_fuzzy_lookup_threshold_ties_and_identifiers():
    value = data()
    function(
        value,
        [],
        {"kind": "entities", "entity_types": ["offer"]},
        lookup={
            "name_query": literal("  HARBOR  HOTEL "),
            "name_fields": ["name"],
            "min_score": "0.8",
            "top_k": 1,
        },
    )
    result = execute(value)
    assert [row["identity"] for row in result["value"]] == [{"id": "a"}]
    assert result["value"][0]["score"] == "1"
    assert result["truncated"] and result["coverage"] == "observed"
    root = value["functions"][-1]["steps"][0]
    root.pop("top_k")
    result = execute(value, list(reversed(rows())))
    assert [row["identity"]["id"] for row in result["value"]] == ["a", "b"]
    selected = result["value"][1]["id"]
    root.update(identifiers=literal([selected], type="array", item_type="string"))
    assert execute(value)["value"][0]["identity"] == {"id": "b"}
    root.update(fuzzy=False)
    assert execute(value)["value"] == []


def test_fuzzy_ties_use_canonical_identity_and_unicode_normalization():
    value = data()
    function(
        value,
        [],
        {"kind": "entities", "entity_types": ["offer"]},
        lookup={"text_query": literal("hotel"), "text_fields": ["name"]},
    )
    records = rows()[:2]
    records[0]["name"], records[1]["name"] = " ＨＯＴＥＬ ", "HOTEL"
    result = execute(value, list(reversed(records)))
    assert [row["identity"]["id"] for row in result["value"]] == ["a", "b"]
    assert [row["score"] for row in result["value"]] == ["1", "1"]


def relation_data():
    value = data()
    value["schema"]["entities"].append(
        {
            "id": "supplier",
            "name": "Supplier",
            "identity_keys": ["id"],
            "requirement_ids": ["budget"],
            "properties": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}],
        }
    )
    value["schema"]["relations"] = [
        {
            "id": "supplied_by",
            "name": "Supplier",
            "from_entity": "offer",
            "to_entity": "supplier",
            "from_property": "supplier_id",
            "to_property": "id",
            "requirement_ids": ["budget"],
            "binding_ids": ["source", "target"],
        }
    ]
    value["mappings"].append(
        {
            "id": "suppliers",
            "entity_id": "supplier",
            "tool_id": READ_ID,
            "collection_path": "/suppliers",
            "fields": [{"property": key, "path": "/" + key} for key in ("id", "name")],
            "coverage": deepcopy(value["mappings"][0]["coverage"]),
        }
    )
    return value


def relation_graph(value, *, complete=True, suppliers=None):
    observed = graph(value)
    observed.add(
        {
            "id": "joined-source",
            "tool_id": READ_ID,
            "status": "succeeded",
            "coverage": "unknown",
            "data": {
                "items": rows(),
                "suppliers": suppliers
                if suppliers is not None
                else [{"id": "s1", "name": "Acme"}, {"id": "s2", "name": "Other"}],
                "complete": complete,
            },
        },
        arguments=arguments(),
    )
    return observed


def test_connectivity_keeps_sources_and_positive_partial_evidence():
    value = relation_data()
    constraint(
        value,
        "supplier_ok",
        {
            "operator": "connected",
            "relation_ids": ["supplied_by"],
            "anchors": [{"entity_id": "supplier", "identity": {"id": literal("s1")}}],
        },
    )
    function(
        value,
        [
            {
                "op": "filter",
                "id": "eligible",
                "input": "source",
                "constraint_ids": ["supplier_ok"],
            },
            projected_ids("eligible"),
        ],
        IDS_OUTPUT,
        required=["supplier_ok"],
    )
    result = relation_graph(value).execute("compute", arguments())
    assert result["value"] == [{"id": "a"}, {"id": "b"}]
    assert {edge["relation_id"] for edge in result["relations"]} == {"supplied_by"}
    observed = relation_graph(value, complete=False, suppliers=[{"id": "s1", "name": "Acme"}])
    assert observed.execute("compute", arguments())["status"] == "incomplete"


def test_multihop_both_directions_deduplicate_cycles_and_preserve_types():
    value = relation_data()
    function(
        value,
        [
            {
                "op": "traverse",
                "id": "result",
                "input": "source",
                "relation_ids": ["supplied_by"],
                "direction": "both",
                "max_hops": 4,
                "contexts": {"offer": {name: expr("argument", name) for name in arguments()}},
            }
        ],
        {"kind": "entities", "entity_types": ["offer", "supplier"]},
    )
    result = relation_graph(value).execute("compute", arguments())
    assert len(result["value"]) == 5
    assert len(result["relations"]) == 3
    assert len({row["id"] for row in result["value"]}) == 5
    fn = value["functions"][-1]
    fn["steps"].extend(
        [
            {"op": "select_types", "id": "offers", "input": "result", "entity_types": ["offer"]},
            {
                "op": "aggregate",
                "id": "average",
                "input": "offers",
                "operation": "average",
                "expression": expr("field", "amount"),
                "group_by": "customer",
            },
        ]
    )
    fn.update(
        return_step="average",
        output={
            "kind": "rows",
            "fields": [
                {"name": "group", "type": "string"},
                {"name": "value", "type": "decimal", "unit": "USD", "nullable": True},
            ],
        },
    )
    result = relation_graph(value).execute("compute", arguments())
    assert result["value"] == [
        {"group": "alice", "value": "15.15"},
        {"group": "bob", "value": "30"},
    ]
    assert len(result["row_metadata"][0]["sources"]) == 2


def test_projection_fallback_is_marked_and_cannot_supply_aggregate_evidence():
    value = data()
    function(
        value,
        [
            {
                "op": "project",
                "id": "result",
                "input": "source",
                "fields": [
                    {"name": "amount", "expression": expr("field", "amount"), "nullable": True}
                ],
            }
        ],
        {
            "kind": "rows",
            "fields": [{"name": "amount", "type": "decimal", "unit": "USD", "nullable": True}],
        },
    )
    records = rows()
    del records[0]["amount"]
    result = execute(value, records)
    assert result["value"][0]["amount"] is None
    assert result["row_metadata"][0]["identity"] == {"id": "a"}
    assert result["row_metadata"][0]["unobserved_fields"] == ["amount"]
    fn = value["functions"][-1]
    fn["steps"].append(
        {
            "op": "aggregate",
            "id": "sum",
            "input": "result",
            "operation": "sum",
            "expression": expr("field", "amount"),
        }
    )
    fn.update(return_step="sum", output={"kind": "scalar", "type": "decimal", "unit": "USD"})
    assert execute(value, records)["status"] == "incomplete"


def test_decimal_exact_arithmetic_and_schema():
    assert decimal_text(Fraction(1, 3)) == "0.3333333333333333333333333333"
    spec = Parameter(name="values", type="array", item_type="decimal")
    assert value_schema(spec)["items"]["type"] == "string"
    for invalid in (True, "NaN", "Infinity", "1e10000", float("inf")):
        assert not valid_value(invalid, "decimal")
    assert not valid_value(["wifi", 1], "array", item_type="string")
    assert not valid_value([1] * 1001, "array", item_type="integer")


def test_invalid_ingestion_is_atomic_and_decimal_source_digits_are_preserved():
    observed = graph(data())
    records = rows()
    records[0]["amount"] = "0.1234567890123456789012345678901234"
    observe(observed, records, complete=True)
    assert observed.collection("offer", arguments()).records[0]["amount"] == records[0]["amount"]
    before = observed.snapshot()
    records[0]["features"] = ["wifi", 1]
    with pytest.raises(GraphIngestionError):
        observe(observed, records, identifier="invalid")
    assert observed.snapshot() == before


def test_owl_array_is_not_functional_and_decimal_has_numeric_range():
    text = encode_ontology(graph(data()).candidate)
    from xml.etree import ElementTree as ET

    root = ET.fromstring(text)
    array = next(
        node
        for node in root
        if node.attrib.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about", "").endswith(
            "offer/features"
        )
    )
    assert not any(
        child.attrib.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource", "").endswith(
            "FunctionalProperty"
        )
        for child in array
    )
    assert "XMLSchema#decimal" in text


def test_version_two_digest_is_unchanged():
    value = Candidate.model_validate(candidate_data())
    assert (
        candidate_digest(value)
        == "c87eac97744e53af427950393ca96c82da819c65fbc05ece5e6ea42a1856d590"
    )


@pytest.mark.asyncio
async def test_dispatcher_uses_set_assertions_and_write_response_facts():
    value = data()
    constraint(
        value,
        "features_ok",
        {
            "operator": "overlap_all",
            "left": expr("field", "features"),
            "right": literal(["wifi", "parking"], type="array", item_type="string"),
        },
    )
    check = value["functions"][1]
    check["required_constraint_ids"].append("features_ok")
    check["steps"][1]["constraint_ids"].append("features_ok")
    # The same mapping path accepts evidence from a successful write response.
    mapped = deepcopy(value["mappings"][0])
    mapped.update(id="written_offers", tool_id=WRITE_ID)
    value["mappings"].append(mapped)
    harness = Harness(accepted=CandidateV3.model_validate(value))
    harness.graph.add(
        {
            "id": "write-result",
            "tool_id": WRITE_ID,
            "status": "succeeded",
            "coverage": "unknown",
            "data": {"items": rows(), "complete": False},
        },
        arguments=arguments("a"),
    )
    assert (await harness.dispatch(WRITE_ID, arguments("a")))["status"] == "succeeded"
    assert (await harness.dispatch(WRITE_ID, arguments("b"), "second"))["status"] == "rejected"
    assert len(harness.calls) == 1
    assert any(
        ref["observation_id"] == "write-result"
        for ref in harness.events[0][1]["function_calls"][-1]["result"]["evidence_refs"]
    )


def test_subject_filter_cannot_remove_failed_condition():
    value = data()
    check = value["functions"][1]
    check["steps"].insert(
        1, {"op": "filter", "id": "hide", "input": "offer", "constraint_ids": ["capacity_ok"]}
    )
    check["steps"][2]["input"] = "hide"
    with pytest.raises(ValueError, match="remove a checked subject"):
        graph(value)


@pytest.mark.asyncio
async def test_aggregate_decision_uses_exact_value_and_argument_bound_group():
    value = data()
    budget = next(c for c in value["constraints"] if c["id"] == "budget_ok")
    budget.update(
        entity_id=None,
        predicate={
            "operator": "le",
            "left": {"kind": "result", "step_id": "group"},
            "right": literal("0.3333333333333333333333333333", type="decimal", unit="USD.cent"),
        },
    )
    check = value["functions"][1]
    population = deepcopy(check["steps"][0])
    population.update(id="population", identity={}, population=True)
    check["steps"][1:1] = [
        population,
        {
            "op": "aggregate",
            "id": "average",
            "input": "population",
            "operation": "average",
            "expression": expr("field", "total_cost"),
            "group_by": "customer",
        },
        {
            "op": "select_group",
            "id": "group",
            "input": "average",
            "key": expr("argument", "offer_id"),
        },
    ]
    harness = Harness(accepted=CandidateV3.model_validate(value))
    records = rows()
    for index, row in enumerate(records):
        row.update(total_cost=1 if index == 0 else 0, customer="a")
    observe(harness.graph, records, complete=True)
    result = await harness.dispatch(WRITE_ID, arguments("a"))
    assert result["status"] == "rejected"
    assert not harness.calls
    conditions = result["decision"]["function_calls"][-1]["result"]["conditions"]
    assert next(c for c in conditions if c["condition_id"] == "budget_ok")["value"] == "false"
    # The rounded result equals the threshold. The exact one-third is larger.
    trace = result["decision"]["function_calls"][-1]["result"]["trace"]
    assert (
        next(s for s in trace if s["step_id"] == "average")["output"][0]["values"]["value"]
        == "0.3333333333333333333333333333"
    )
    assert (await harness.dispatch(WRITE_ID, arguments("b"), "other-group"))[
        "status"
    ] == "missing_evidence"
    observe(harness.graph, records, complete=False, identifier="partial-update")
    assert (await harness.dispatch(WRITE_ID, arguments("a"), "partial"))[
        "status"
    ] == "missing_evidence"


def test_request_arrays_and_decimal_values_require_typed_source_evidence():
    value = data()
    value["request_fields"] = [
        {
            "id": "features",
            "name": "features",
            "type": "array",
            "item_type": "string",
            "description": "Required features.",
            "requirement_ids": ["capacity"],
        },
        {
            "id": "amount",
            "name": "amount",
            "type": "decimal",
            "unit": "USD",
            "description": "Requested amount.",
            "requirement_ids": ["budget"],
        },
    ]
    candidate = CandidateV3.model_validate(value)
    query = "Require wifi and parking. Spend at most 10.25 USD."
    fields = [
        {
            "name": name,
            "status": "resolved",
            "value": content,
            "evidence": [{"source": "query", "quote": query}],
        }
        for name, content in [("features", ["wifi", "parking"]), ("amount", "10.25")]
    ]
    validate_extraction(RequestExtraction(fields=fields), candidate, query, {})
    fields[0]["value"] = ["wifi", 1]
    with pytest.raises(ValueError, match="typed source evidence"):
        validate_extraction(RequestExtraction(fields=fields), candidate, query, {})


def test_numeric_interval_and_unit_rejection():
    value = data()
    for identifier, operation, bound in [("lower", "ge", "10.1"), ("upper", "lt", "30")]:
        constraint(
            value,
            identifier,
            {
                "operator": operation,
                "left": expr("field", "amount"),
                "right": literal(bound, type="decimal", unit="USD"),
            },
        )
    function(
        value,
        [
            {
                "op": "filter",
                "id": "eligible",
                "input": "source",
                "constraint_ids": ["lower", "upper"],
            },
            projected_ids("eligible"),
        ],
        IDS_OUTPUT,
        required=["lower", "upper"],
    )
    assert execute(value)["value"] == [{"id": "a"}, {"id": "b"}]
    value["constraints"][-1]["predicate"]["right"]["unit"] = "EUR"
    with pytest.raises(ValueError, match="compatible types and units"):
        graph(value)


def test_type_selection_and_reverse_traversal():
    value = relation_data()
    function(
        value,
        [
            {"op": "traverse", "id": "neighbors", "input": "source", "relation_id": "supplied_by"},
            {
                "op": "select_types",
                "id": "suppliers",
                "input": "neighbors",
                "entity_types": ["supplier"],
            },
            projected_ids("suppliers"),
        ],
        IDS_OUTPUT,
    )
    result = relation_graph(value).execute("compute", arguments())
    assert result["value"] == [{"id": "s1"}, {"id": "s2"}]
    fn = value["functions"][-1]
    fn["steps"] = [
        {
            "op": "lookup",
            "id": "source",
            "entity_id": "supplier",
            "identity": {"id": literal("s1")},
        },
        {
            "op": "traverse",
            "id": "result",
            "input": "source",
            "relation_id": "supplied_by",
            "direction": "incoming",
            "include_starting_entities": False,
            "contexts": {"offer": {name: expr("argument", name) for name in arguments()}},
        },
    ]
    fn.update(return_step="result", output={"kind": "entities", "entity_types": ["offer"]})
    assert [
        r["identity"]["id"] for r in relation_graph(value).execute("compute", arguments())["value"]
    ] == ["a", "b"]


def test_legacy_grammar_does_not_accept_new_operator_options():
    value = candidate_data()
    value["functions"][1]["steps"][0]["population"] = True
    with pytest.raises(ValueError, match="version 3"):
        compile_function(
            Candidate.model_validate(value), Candidate.model_validate(value).functions[1]
        )


def test_legacy_grammar_rejects_new_predicates():
    value = candidate_data()
    value["constraints"][0]["predicate"] = {
        "operator": "connected",
        "relation_ids": ["supplied_by"],
        "anchors": [{"entity_id": "offer", "identity": {"id": literal("a")}}],
    }
    candidate = Candidate.model_validate(value)
    with pytest.raises(ValueError, match="version 3"):
        compile_function(candidate, candidate.functions[0])


def test_group_selection_rejects_a_replaced_group_key():
    value = data()
    function(
        value,
        [
            {
                "op": "aggregate",
                "id": "groups",
                "input": "source",
                "operation": "count",
                "group_by": "customer",
            },
            {
                "op": "project",
                "id": "renamed",
                "input": "groups",
                "fields": [
                    {"name": "group", "expression": literal("alice")},
                    {"name": "value", "expression": expr("field", "value")},
                ],
            },
            {"op": "select_group", "id": "result", "input": "renamed", "key": literal("alice")},
        ],
        {
            "kind": "rows",
            "fields": [{"name": "group", "type": "string"}, {"name": "value", "type": "integer"}],
        },
    )
    with pytest.raises(ValueError, match="Group selection"):
        graph(value)


def test_lookup_and_traversal_enforce_combined_entity_limits(monkeypatch):
    monkeypatch.setattr("oak.kernel_execution.MAX_VISITED", 3)
    value = relation_data()
    function(
        value,
        [
            {
                "op": "traverse",
                "id": "result",
                "input": "source",
                "relation_id": "supplied_by",
                "include_starting_entities": False,
            }
        ],
        {"kind": "entities", "entity_types": ["supplier"]},
    )
    # Three source records and two suppliers exceed the bound, even without start rows in the output.
    with pytest.raises(ValueError, match="entity or relation limit"):
        relation_graph(value).execute("compute", arguments())


def test_normalized_text_and_comparison_work_are_bounded():
    value = data()
    function(
        value,
        [],
        {"kind": "entities", "entity_types": ["offer"]},
        lookup={"name_query": literal("a" * 2300), "name_fields": ["name"]},
    )
    records = rows()[:1]
    records[0]["name"] = "a" * 2300
    with pytest.raises(ValueError, match="comparison work limit"):
        execute(value, records)
    # NFKC expands this ligature to three characters.
    value["functions"][-1]["steps"][0]["name_query"] = literal("\ufb03" * 1400)
    with pytest.raises(ValueError, match="Normalized search text"):
        execute(value, records)
    with pytest.raises(ValueError, match="Normalized search text"):
        execute(value, [])


def test_count_rejects_an_operand_expression():
    value = data()
    function(
        value,
        [
            {
                "op": "aggregate",
                "id": "result",
                "input": "source",
                "operation": "count",
                "expression": expr("field", "amount"),
            }
        ],
        {"kind": "scalar", "type": "integer"},
    )
    with pytest.raises(ValueError, match="Only count omits its expression"):
        graph(value)


def test_result_reference_cannot_use_a_projection_placeholder():
    value = data()
    value["request_fields"].append(
        {
            "id": "estimate",
            "name": "estimate",
            "type": "decimal",
            "unit": "USD",
            "description": "A requested estimate.",
            "requirement_ids": ["budget"],
        }
    )
    function(
        value,
        [
            {
                "op": "aggregate",
                "id": "groups",
                "input": "source",
                "operation": "average",
                "expression": expr("field", "amount"),
                "group_by": "customer",
            },
            {
                "op": "project",
                "id": "placeholder",
                "input": "groups",
                "fields": [
                    {"name": "group", "expression": expr("field", "group")},
                    {
                        "name": "value",
                        "expression": expr("request", "estimate"),
                        "missing_value": literal("0", type="decimal", unit="USD"),
                    },
                ],
            },
            {
                "op": "select_group",
                "id": "selected",
                "input": "placeholder",
                "key": literal("alice"),
            },
            {
                "op": "project",
                "id": "result",
                "input": "selected",
                "fields": [
                    {"name": "value", "expression": {"kind": "result", "step_id": "selected"}},
                ],
            },
        ],
        {"kind": "rows", "fields": [{"name": "value", "type": "decimal", "unit": "USD"}]},
    )
    result = execute(value)
    assert result["status"] == "incomplete"
    assert result["missing_dependencies"] == [
        {"source": "result", "step_id": "selected", "reason": "unavailable"}
    ]
