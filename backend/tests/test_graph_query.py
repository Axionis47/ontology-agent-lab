"""Check temporary routes against the fixed execution and access boundaries."""

from copy import deepcopy

import pytest

from oak.acquisition import Acquisition
from oak.evidence_graph import EvidenceGraph
from oak.graph_query import GraphQuery, execute_query
from oak.kernel_dispatcher import KernelDispatcher
from oak.repair_patch import candidate_digest
from oak.repair_schemas import CandidateV3
from oak.request_preparation import RequestExtraction, validate_extraction
from tests.kernel_fixtures import READ_ID, arguments
from tests.test_acquisition import fixture, observation
from tests.test_operator_library import relation_data, relation_graph


def supplier_query():
    return {
        "steps": [
            {"op": "lookup", "id": "rows", "entity_id": "supplier"},
            {
                "op": "project",
                "id": "result",
                "input": "rows",
                "fields": [
                    {"name": n, "expression": {"kind": "field", "name": n}} for n in ("id", "name")
                ],
            },
        ],
        "return_step": "result",
        "output": {
            "kind": "rows",
            "fields": [{"name": n, "type": "string"} for n in ("id", "name")],
        },
    }


def test_lookup_without_helper_preserves_candidate_and_sources():
    graph = relation_graph(relation_data())
    before = candidate_digest(graph.candidate)
    result = execute_query(graph.candidate, graph, supplier_query())
    assert result["status"] == "complete"
    assert result["value"] == [{"id": "s1", "name": "Acme"}, {"id": "s2", "name": "Other"}]
    assert result["evidence_refs"] and result["coverage"] == "complete"
    assert candidate_digest(graph.candidate) == before
    assert all(f.id != "query" for f in graph.candidate.functions)


@pytest.mark.parametrize("hops", [3, 4])
def test_route_across_several_relations_keeps_library_fixed(hops):
    raw = relation_data()
    for i in range(1, hops):
        previous = raw["schema"]["entities"][-1]
        previous["properties"].append({"name": "next_id", "type": "string"})
        raw["mappings"][-1]["fields"].append({"property": "next_id", "path": "/next_id"})
        entity = deepcopy(raw["schema"]["entities"][1])
        entity.update(id=f"node{i}", name=f"Node{i}")
        entity["properties"] = [
            {"name": "id", "type": "string"},
            {"name": "name", "type": "string"},
        ]
        raw["schema"]["entities"].append(entity)
        relation = deepcopy(raw["schema"]["relations"][0])
        relation.update(
            id=f"edge{i}",
            from_entity=previous["id"],
            to_entity=entity["id"],
            from_property="next_id",
        )
        raw["schema"]["relations"].append(relation)
        mapping = deepcopy(raw["mappings"][1])
        mapping.update(id=f"map{i}", entity_id=entity["id"], collection_path=f"/node{i}")
        mapping["fields"] = [{"property": n, "path": "/" + n} for n in ("id", "name")]
        raw["mappings"].append(mapping)
    candidate = CandidateV3.model_validate(raw)
    graph = EvidenceGraph(candidate)
    payload = {
        "items": [{"id": "a", "supplier_id": "s1"}],
        "suppliers": [{"id": "s1", "name": "Start", "next_id": "n1"}],
        "complete": True,
    }
    for i in range(1, hops):
        payload[f"node{i}"] = [{"id": f"n{i}", "name": f"Node {i}", "next_id": f"n{i + 1}"}]
    graph.add(
        {
            "id": "chain",
            "tool_id": READ_ID,
            "status": "succeeded",
            "coverage": "unknown",
            "data": payload,
        },
        arguments=arguments(),
    )
    query = {
        "parameters": raw["functions"][0]["parameters"],
        "arguments": arguments(),
        "steps": [
            {
                "op": "lookup",
                "id": "start",
                "entity_id": "offer",
                "context": {n: {"kind": "argument", "name": n} for n in arguments()},
            },
            {
                "op": "traverse",
                "id": "path",
                "input": "start",
                "relation_ids": [r["id"] for r in raw["schema"]["relations"]],
                "max_hops": hops,
            },
            {
                "op": "select_types",
                "id": "end",
                "input": "path",
                "entity_types": [f"node{hops - 1}"],
            },
        ],
        "return_step": "end",
        "output": {"kind": "entities", "entity_types": [f"node{hops - 1}"]},
    }
    before = candidate_digest(candidate)
    result = execute_query(candidate, graph, query)
    assert result["status"] == "complete", result
    assert result["value"][0]["identity"] == {"id": f"n{hops - 1}"}
    assert len(result["relations"]) == hops
    assert candidate_digest(candidate) == before


def test_saved_function_value_can_parameterize_next_query():
    raw = relation_data()
    function = {
        "id": "supplier_ids",
        "parameters": [],
        "required_constraint_ids": [],
        **supplier_query(),
    }
    raw["functions"].append(function)
    graph = relation_graph(raw)
    intermediate = graph.execute("supplier_ids", {})
    query = supplier_query()
    query["parameters"] = [{"name": "supplier", "type": "string"}]
    query["arguments"] = {"supplier": intermediate["value"][0]["id"]}
    query["steps"][0]["identity"] = {"id": {"kind": "argument", "name": "supplier"}}
    result = execute_query(graph.candidate, graph, query)
    assert result["value"] == [{"id": "s1", "name": "Acme"}]
    assert result["evidence_refs"]


@pytest.mark.parametrize("operation", ["input", "assert", "decision", "dispatch"])
def test_query_schema_excludes_actions_and_permission_operations(operation):
    query = supplier_query()
    query["steps"] = [{"op": operation, "id": "result"}]
    with pytest.raises(ValueError):
        GraphQuery.model_validate(query)
    assert "DecisionStep" not in GraphQuery.model_json_schema()["$defs"]


def test_query_cannot_declare_schema_or_exceed_hop_limit():
    query = supplier_query()
    with pytest.raises(ValueError):
        GraphQuery.model_validate({**query, "schema": {"entities": []}})
    query["steps"].insert(1, {"op": "traverse", "id": "path", "input": "rows", "max_hops": 5})
    with pytest.raises(ValueError):
        GraphQuery.model_validate(query)


async def test_query_missing_observations_use_checked_acquisition():
    candidate, request, tools, args = fixture()
    request["functions"] = []
    graph = EvidenceGraph(candidate)
    fn = next(f for f in candidate.functions if f.id == "total")
    raw = fn.model_dump(mode="json")
    query = GraphQuery.model_validate(
        {k: raw[k] for k in ("parameters", "steps", "return_step", "output")}
    )
    before = candidate_digest(candidate)
    missing = execute_query(candidate, graph, query, request["values"])
    assert missing["status"] == "incomplete"
    acquisition = Acquisition(candidate, request, graph)
    assert acquisition.selections == []
    acquisition.register_query(query.function(), {})
    assert acquisition.check(candidate.operation_bindings[0], args)["status"] == "allowed"
    with pytest.raises(ValueError, match="filters"):
        acquisition.check(candidate.operation_bindings[0], {**args, "customer": "other"})
    graph.add(observation("one", "a"), arguments=args)
    result = execute_query(candidate, graph, query, request["values"])
    assert result["status"] == "complete" and result["value"] == 12000
    other = {**request["values"], "customer": "other"}
    assert execute_query(candidate, graph, query, other)["status"] == "incomplete"
    assert candidate_digest(candidate) == before

    async def forbidden(*args, **kwargs):
        raise AssertionError("No external dispatch is permitted.")

    async def record(*args, **kwargs):
        pass

    from oak.discovery_validation import digest

    request["digest"] = digest({k: v for k, v in request.items() if k != "digest"})
    dispatcher = KernelDispatcher(
        candidate=candidate,
        graph=graph,
        request_snapshot=request,
        tools=tools,
        run_mode="training",
        stage="harness",
        transport=forbidden,
        record=record,
    )
    dispatcher.acquisition.register_query(query.function(), {})
    denied = dispatcher.check({**tools[0], "id": "ungranted"}, args, "blocked")
    assert denied["status"] == "rejected"


def test_request_does_not_require_a_function_selection():
    candidate, request, _, _ = fixture()
    evidence = [{"source": "query", "quote": request["query"]}]
    extraction = RequestExtraction.model_validate(
        {
            "functions": [],
            "fields": [
                {"name": name, "status": "resolved", "value": value, "evidence": evidence}
                for name, value in request["values"].items()
            ],
        }
    )
    validate_extraction(extraction, candidate, request["query"], {})
    assert extraction.functions == ()


async def test_native_query_access_uses_catalog_and_records_routes_without_saved_functions():
    import json

    from oak.discovery_validation import digest
    from oak.training_runner import run_episode
    from tests.test_training_runner import ScriptedModel, call

    candidate, request, native, args = fixture()
    plan = next(f for f in candidate.functions if f.id == "total").model_dump(mode="json")
    candidate = candidate.model_copy(
        update={"functions": tuple(f for f in candidate.functions if f.output.kind == "decision")}
    )
    request["functions"] = []
    request["digest"] = digest({k: v for k, v in request.items() if k != "digest"})
    query = {k: plan[k] for k in ("steps", "return_step", "output")}
    model = ScriptedModel(
        [call("read_evidence", {"id": "harness_catalog", "path": "/index"})],
        [call("query_graph", {"query_json": json.dumps(query)})],
        [call("tool_0", args)],
        [call("query_graph", {"query_json": json.dumps(query)})],
        [{"text": "The observed total is 12000."}],
    )
    events, dispatches = [], []

    async def dispatch(tool, values, invocation, *, permit):
        permit.consume(tool["id"], values, invocation)
        dispatches.append(values)
        return observation(invocation, "a")

    async def emit(kind, data):
        events.append((kind, data))

    async def stop():
        return False

    before = candidate_digest(candidate)
    result = await run_episode(
        case={"query": request["query"], "tool_ids": [native[0]["id"]]},
        tools=native,
        candidate=candidate,
        model=model,
        dispatch=dispatch,
        emit=emit,
        limits={"max_steps": 6},
        should_stop=stop,
        request_snapshot=request,
    )
    assert result["status"] == "complete"
    routes = [e for kind, e in events if kind == "graph_route"]
    assert [e["result"]["status"] for e in routes] == ["incomplete", "complete"]
    assert routes[-1]["result"]["value"] == 12000
    assert routes[-1]["version"] == "oak.graph-route.v1"
    assert dispatches == [args]
    assert candidate_digest(candidate) == before
    assert all(f.output.kind == "decision" for f in candidate.functions)
    assert "harness_catalog" in model.requests[0]["instructions"]
    assert {s["name"] for s in model.requests[0]["tools"]} >= {
        "query_graph",
        "run_function",
        "read_evidence",
    }
