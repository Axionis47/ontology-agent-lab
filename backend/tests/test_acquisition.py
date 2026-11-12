"""Check query-bound acquisition, page coverage, and evidence reuse."""

from copy import deepcopy

import pytest

from oak.acquisition import Acquisition, dependencies, validate_access
from oak.discovery_validation import digest
from oak.evidence_graph import EvidenceGraph, GraphIngestionError
from oak.kernel_dispatcher import KernelDispatcher
from oak.repair_schemas import CandidateV3
from tests.kernel_fixtures import (
    READ_ID,
    arguments,
    candidate_data,
    snapshot,
    tools,
    with_source_access,
)


def fixture(paged=False):
    raw = with_source_access(candidate_data())
    raw["version"] = "oak.candidate.v3"
    raw["request_fields"].append(
        {
            "id": "customer",
            "name": "customer",
            "type": "string",
            "description": "The requested customer.",
            "requirement_ids": ["party"],
        }
    )
    raw["mappings"][0]["scope"].append(
        {"name": "customer", "path": "/customer", "source": "arguments"}
    )
    source = raw["operation_bindings"][0]["source_access"]
    for function in raw["functions"]:
        for step in function["steps"]:
            if step["op"] == "lookup":
                step["context"]["customer"] = {"kind": "request", "name": "customer"}
    source["filters"].append(
        {
            "path": "/customer",
            "value": {"kind": "request", "name": "customer"},
            "support": source["support"],
        }
    )
    source.update(
        projection_path="/fields",
        projection_fields={"offer." + p: p for p in ("id", "capacity", "total_cost")},
    )
    if paged:
        source["pagination"] = {
            "cursor_path": "/cursor",
            "next_cursor_path": "/next",
            "size_path": "/page_size",
            "max_size": 10,
            "support": source["support"],
        }
    raw["functions"].append(
        {
            "id": "total",
            "parameters": [],
            "required_constraint_ids": ["capacity_ok"],
            "steps": [
                {
                    "op": "lookup",
                    "id": "rows",
                    "entity_id": "offer",
                    "context": {
                        k: {"kind": "request", "name": k}
                        for k in ("customer", "guests", "start_date", "end_date")
                    },
                },
                {
                    "op": "filter",
                    "id": "filtered",
                    "input": "rows",
                    "constraint_ids": ["capacity_ok"],
                },
                {
                    "op": "aggregate",
                    "id": "total",
                    "input": "filtered",
                    "operation": "sum",
                    "expression": {"kind": "field", "name": "total_cost"},
                },
            ],
            "return_step": "total",
            "output": {"kind": "scalar", "type": "integer", "unit": "USD.cent"},
        }
    )
    candidate = CandidateV3.model_validate(raw)
    request = snapshot()
    request["values"]["customer"] = "C17"
    request["functions"] = [
        {"function_id": "total", "arguments": {}, "requirement_ids": ["budget"]}
    ]
    request["digest"] = digest({k: v for k, v in request.items() if k != "digest"})
    native = tools()
    native[0]["input_schema"]["properties"].update(
        customer={"type": "string"}, fields={"type": "array", "items": {"type": "string"}}
    )
    if paged:
        native[0]["input_schema"]["properties"].update(
            cursor={"type": ["string", "null"]}, page_size={"type": "integer"}
        )
    args = {**arguments(), "customer": "C17", "fields": ["id", "capacity", "total_cost"]}
    if paged:
        args.update(cursor=None, page_size=10)
    return candidate, request, native, args


def observation(identifier, row_id, next_cursor=None):
    return {
        "id": identifier,
        "tool_id": READ_ID,
        "status": "succeeded",
        "coverage": "unknown",
        "data": {
            "items": [{"id": row_id, "capacity": 4, "total_cost": 12000}],
            "next": next_cursor,
            "complete": True,
        },
    }


@pytest.mark.parametrize(
    "change", ["customer", "missing_filter", "projection", "extra_argument", "page_size"]
)
async def test_wrong_acquisition_never_reaches_transport(change):
    candidate, request, native, args = fixture(True)
    if change == "customer":
        args["customer"] = "C99"
    elif change == "missing_filter":
        args.pop("customer")
    elif change == "projection":
        args["fields"].remove("capacity")
    elif change == "extra_argument":
        native[0]["input_schema"]["properties"]["unrestricted"] = {"type": "boolean"}
        args["unrestricted"] = True
    else:
        args["page_size"] = 1000
    calls = []

    async def transport(*args, **kwargs):
        calls.append(args)
        return {}

    async def record(*args, **kwargs):
        pass

    dispatcher = KernelDispatcher(
        candidate=candidate,
        graph=EvidenceGraph(candidate),
        request_snapshot=request,
        tools=native,
        run_mode="inference",
        stage="inference",
        transport=transport,
        record=record,
    )
    result = await dispatcher(native[0], args, "call")
    assert not result["dispatched"] and result["status"] == "rejected"
    assert calls == []


def test_dependencies_include_filter_fields_and_identity():
    candidate, *_ = fixture()
    assert dependencies(candidate, {"total"})[0]["properties"] == ["capacity", "id", "total_cost"]


async def test_real_mcp_pages_use_checked_arguments_and_fixed_function(mcp_server):
    import json

    import httpx
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client

    from oak.training_runner import run_episode
    from tests.test_training_runner import ScriptedModel, call

    candidate, request, native, args = fixture(True)
    args["page_size"] = 1
    events = []

    async def emit(kind, payload):
        events.append((kind, payload))

    async def running():
        return False

    async with Client(streamable_http_client(mcp_server + "/acquisition/mcp")) as client:
        declared = next(
            t for t in (await client.list_tools()).tools if t.name == "customer_records"
        )
        native[0].update(
            name=declared.name, description=declared.description, input_schema=declared.input_schema
        )

        async def transport(tool, arguments, invocation_id, *, permit):
            permit.consume(tool["id"], arguments, invocation_id)
            response = await client.call_tool(tool["name"], arguments)
            assert not response.is_error
            data = response.structured_content
            if data is None:
                data = json.loads(response.content[0].text)
            return {
                "status": "succeeded",
                "data": data,
                "raw": response.model_dump(mode="json"),
                "coverage": "unknown",
            }

        model = ScriptedModel(
            [call("tool_0", {**args, "customer": "C99"})],
            [call("tool_0", args)],
            [call("tool_0", {**args, "cursor": "1"})],
            [call("run_function", {"function_id": "total", "arguments_json": "{}"})],
            [{"text": "The complete C17 total is 30000 cents."}],
        )
        result = await run_episode(
            case={"query": "Compute the total for C17.", "tool_ids": [READ_ID]},
            tools=native,
            candidate=candidate,
            request_snapshot=request,
            model=model,
            dispatch=transport,
            emit=emit,
            limits={"max_steps": 6},
            should_stop=running,
            run_mode="inference",
            stage="inference",
        )
    assert result["status"] == "complete", (
        result["graph_processing"],
        result["observations"],
        result["trace"][-3:],
    )
    assert result["dispatch_decisions"][0]["status"] == "rejected"
    assert result["function_calls"][-1]["result"]["value"] == 30000
    assert len(result["observations"]) == 2
    async with httpx.AsyncClient() as web:
        actual = (await web.get(mcp_server + "/acquisition-state")).json()["calls"]
    assert actual == [args, {**args, "cursor": "1"}]
    assert all(len(o["data"]["items"]) == 1 for o in result["observations"])


def test_complete_evidence_allows_checked_refresh_but_does_not_change_scope():
    candidate, request, _, args = fixture()
    graph = EvidenceGraph(candidate)
    acquisition = Acquisition(candidate, request, graph)
    graph.add(observation("other", "a"), arguments={**args, "customer": "C99"})
    assert acquisition.check(candidate.operation_bindings[0], args)["mode"] == "acquire"
    graph.add(observation("matching", "b"), arguments=args)
    refreshed = acquisition.check(candidate.operation_bindings[0], args)
    assert refreshed["mode"] == "refresh" and refreshed["missing_needs"] == []
    with pytest.raises(ValueError, match="filters"):
        acquisition.check(candidate.operation_bindings[0], {**args, "customer": "C99"})


def parameter_fixture():
    candidate, request, _, args = fixture()
    raw = candidate.model_dump(mode="json")
    function = next(f for f in raw["functions"] if f["id"] == "total")
    function["parameters"] = [
        {"name": "customer", "type": "string"},
        {"name": "guests", "type": "integer", "unit": "count"},
    ]
    function["steps"][0]["context"]["customer"] = {"kind": "argument", "name": "customer"}
    for selector in raw["operation_bindings"][0]["source_access"]["filters"]:
        if selector["path"] == "/customer":
            selector["value"] = {"kind": "argument", "name": "customer"}
    request["functions"][0]["arguments"] = {"guests": 3}
    candidate = CandidateV3.model_validate(raw)
    return candidate, request, args


def test_function_reuse_keeps_each_argument_binding_and_only_pins_request_values():
    candidate, request, args = parameter_fixture()
    graph = EvidenceGraph(candidate)
    acquisition = Acquisition(candidate, request, graph)
    for index, customer in enumerate(("C17", "C99", "different-record"), start=1):
        bound = {"customer": customer, "guests": 3}
        acquisition.bind_function("total", bound)
        bound["customer"] = "mutated-after-call"
        graph.add(observation(str(index), str(index)), arguments={**args, "customer": customer})
        assert (
            graph.execute("total", {"customer": customer, "guests": 3}, request=request["values"])[
                "value"
            ]
            == 12000
        )
    for customer in ("C17", "C99", "different-record"):
        result = acquisition.check(candidate.operation_bindings[0], {**args, "customer": customer})
        assert result["status"] == "allowed" and result["mode"] == "refresh"
        assert all(n["arguments"]["customer"] == customer for n in result["needs"])
    before = deepcopy(acquisition.selections)
    acquisition.bind_function("total", {"customer": "C17", "guests": 3})
    assert acquisition.selections == before
    with pytest.raises(ValueError, match="checked request"):
        acquisition.bind_function("total", {"customer": "C17", "guests": 4})
    with pytest.raises(ValueError, match="filters"):
        acquisition.check(candidate.operation_bindings[0], {**args, "customer": "unbound"})
    assert request["functions"][0]["arguments"] == {"guests": 3}


def test_paged_refresh_starts_a_new_population_and_preserves_old_observations():
    candidate, request, _, args = fixture(True)
    graph = EvidenceGraph(candidate)
    graph.add(observation("old-1", "a", "next"), arguments=args)
    graph.add(observation("old-2", "b"), arguments={**args, "cursor": "next"})
    acquisition = Acquisition(candidate, request, graph)
    assert acquisition.check(candidate.operation_bindings[0], args)["mode"] == "refresh"
    with pytest.raises(ValueError, match="cursor"):
        acquisition.check(candidate.operation_bindings[0], {**args, "cursor": "next"})
    graph.add(observation("new-1", "c", "fresh-next"), arguments=args)
    assert graph.execute("total", {}, request=request["values"])["status"] != "complete"
    current = graph.collection("offer", request["values"])
    assert {r["id"] for r in current.records} == {"c"}
    with pytest.raises(ValueError, match="cursor"):
        acquisition.check(candidate.operation_bindings[0], args)
    last = observation("new-2", "d")
    last["data"]["items"][0]["total_cost"] = 15000
    graph.add(last, arguments={**args, "cursor": "fresh-next"})
    result = graph.execute("total", {}, request=request["values"])
    assert result["status"] == "complete" and result["value"] == 27000
    assert set(graph.observations) == {"old-1", "old-2", "new-1", "new-2"}
    assert {
        ref["observation_id"] for ref in graph.collection("offer", request["values"]).evidence
    } == {"new-1", "new-2"}


def test_invalid_refresh_preserves_the_previous_complete_graph():
    candidate, request, _, args = fixture(True)
    graph = EvidenceGraph(candidate)
    graph.add(observation("old", "a"), arguments=args)
    before = deepcopy(graph.snapshot())
    invalid = observation("new", "b")
    invalid["data"]["items"][0]["total_cost"] = "not-an-integer"
    with pytest.raises(GraphIngestionError):
        graph.add(invalid, arguments=args)
    assert graph.snapshot() == before
    assert graph.execute("total", {}, request=request["values"])["value"] == 12000


async def test_agent_reuses_one_function_and_refreshes_through_checked_transport():
    import json

    from oak.repair_patch import candidate_digest
    from oak.training_runner import run_episode
    from tests.test_training_runner import ScriptedModel, call

    candidate, request, args = parameter_fixture()
    _, _, native, _ = fixture()
    request["digest"] = digest({k: v for k, v in request.items() if k != "digest"})

    def compute(customer):
        return call(
            "run_function",
            {
                "function_id": "total",
                "arguments_json": json.dumps({"customer": customer, "guests": 3}),
            },
        )

    model = ScriptedModel(
        [compute("C17")],
        [call("tool_0", args)],
        [compute("C17")],
        [compute("C99")],
        [call("tool_0", {**args, "customer": "C99"})],
        [compute("C99")],
        [call("tool_0", args)],
        [compute("C17")],
        [{"text": "The refreshed total is 33000."}],
    )
    calls, events = [], []

    async def transport(tool, values, invocation, *, permit):
        permit.consume(tool["id"], values, invocation)
        calls.append(deepcopy(values))
        result = observation(invocation, "offer")
        result["data"]["items"][0]["total_cost"] = [12000, 23000, 33000][len(calls) - 1]
        return result

    async def emit(kind, data):
        events.append((kind, data))

    async def stop():
        return False

    before = candidate_digest(candidate)
    result = await run_episode(
        case={"query": request["query"], "tool_ids": [READ_ID]},
        tools=native,
        candidate=candidate,
        request_snapshot=request,
        model=model,
        dispatch=transport,
        emit=emit,
        limits={"max_steps": 10},
        should_stop=stop,
    )
    assert result["status"] == "complete"
    totals = [
        c["result"]["value"]
        for c in result["function_calls"]
        if c["function_id"] == "total" and c["result"]["status"] == "complete"
    ]
    assert totals == [12000, 23000, 33000]
    assert [c["customer"] for c in calls] == ["C17", "C99", "C17"]
    assert [d["acquisition"]["mode"] for d in result["dispatch_decisions"]] == [
        "acquire",
        "acquire",
        "refresh",
    ]
    assert candidate_digest(candidate) == before


def test_pages_preserve_facts_and_only_final_page_establishes_complete_total():
    candidate, request, _, args = fixture(True)
    graph = EvidenceGraph(candidate)
    graph.add(observation("page-1", "a", "next"), arguments=args)
    result = graph.execute("total", {}, request=request["values"])
    assert result["status"] != "complete"
    assert (
        Acquisition(candidate, request, graph).check(
            candidate.operation_bindings[0], {**args, "cursor": "next"}
        )["status"]
        == "allowed"
    )
    graph.add(observation("page-2", "b"), arguments={**args, "cursor": "next"})
    result = graph.execute("total", {}, request=request["values"])
    assert result["status"] == "complete" and result["value"] == 24000
    collection = graph.collection("offer", request["values"])
    assert {r["id"] for r in collection.records} == {"a", "b"}
    assert {e["observation_id"] for e in collection.evidence} == {"page-1", "page-2"}


@pytest.mark.parametrize("conflict", ["cursor", "record"])
def test_invalid_pages_do_not_change_the_graph(conflict):
    candidate, _, _, args = fixture(True)
    graph = EvidenceGraph(candidate)
    graph.add(observation("page-1", "a", "next"), arguments=args)
    before = deepcopy(graph.snapshot())
    item = observation("page-2", "a", "next" if conflict == "cursor" else None)
    if conflict == "record":
        item["data"]["items"][0]["capacity"] = 9
    with pytest.raises((ValueError, GraphIngestionError)):
        graph.add(item, arguments={**args, "cursor": "next"})
    assert graph.snapshot() == before


def test_pagination_cannot_be_an_entity_scope():
    candidate, _, native, _ = fixture(True)
    raw = candidate.model_dump(mode="json")
    raw["mappings"][0]["scope"].append({"name": "page", "source": "arguments", "path": "/cursor"})
    with pytest.raises(ValueError, match="Pagination"):
        validate_access(CandidateV3.model_validate(raw), {t["id"]: t for t in native})
