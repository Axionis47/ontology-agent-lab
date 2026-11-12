import asyncio
import json
from contextlib import asynccontextmanager
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from google.genai import types
from mcp import types as mcp_types

from oak.discovery_schemas import SchemaProposal
from oak.discovery_validation import digest
from oak.kernel_dispatcher import DispatchPermit
from oak.model_client import (
    GeminiClient,
    GenerationLimits,
    ModelFailure,
    _failed_output,
    provider_schema,
)
from oak.repair_schemas import Candidate
from oak.settings import Settings
from oak.training import Training, TrainingHalt
from oak.training_construction import PatchProposal
from oak.training_runner import run_episode
from tests.kernel_fixtures import arguments as rental_arguments
from tests.kernel_fixtures import tools as rental_tools
from tests.test_evidence_graph import graph_candidate

TOOLS = [
    {
        "id": "catalog.list",
        "name": "list_records",
        "description": "Get records.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "id": "catalog.create",
        "name": "create_record",
        "description": "Create a record.",
        "input_schema": {
            "type": "object",
            "properties": {"amount": {"type": "integer"}},
            "required": ["amount"],
            "additionalProperties": False,
        },
    },
]


def runner_candidate():
    value = graph_candidate()
    value["version"] = "oak.candidate.v2"
    value["constraints"].append(
        {
            "id": "request_minimum",
            "entity_id": None,
            "requirement_ids": ["minimum"],
            "predicate": {
                "operator": "ge",
                "left": {"kind": "request", "name": "minimum"},
                "right": {"kind": "literal", "value": 0},
            },
        }
    )
    value["request_fields"] = [
        {
            "id": "minimum",
            "name": "minimum",
            "type": "integer",
            "description": "Minimum value.",
            "requirement_ids": ["minimum"],
        }
    ]
    value["functions"].append(
        {
            "id": "check_request",
            "parameters": [],
            "required_constraint_ids": ["request_minimum"],
            "steps": [
                {"op": "input", "id": "request"},
                {
                    "op": "assert",
                    "id": "check",
                    "input": "request",
                    "constraint_ids": ["request_minimum"],
                },
                {"op": "decision", "id": "decision", "inputs": ["check"]},
            ],
            "return_step": "decision",
            "output": {"kind": "decision"},
        }
    )
    value["operation_bindings"] = [
        {
            "id": tool["id"],
            "tool_id": tool["id"],
            "requirement_ids": ["minimum"],
            "checks": [{"function_id": "check_request", "arguments": {}}],
        }
        for tool in TOOLS
    ]
    value["requirement_coverage"] = [
        {
            "id": "minimum",
            "requirement_id": "minimum",
            "request_field_ids": ["minimum"],
            "constraint_ids": ["request_minimum"],
            "binding_ids": [t["id"] for t in TOOLS],
        }
    ]
    return value


def call(name, arguments=None, identifier="provider-call"):
    return {"function_call": {"name": name, "args": arguments or {}, "id": identifier}}


class ScriptedModel:
    def __init__(self, *turns):
        self.turns = list(turns)
        self.requests = []

    async def turn(self, messages, tools, **kwargs):
        self.requests.append(deepcopy({"messages": messages, "tools": tools, **kwargs}))
        parts = self.turns.pop(0)
        return {
            "content": {"role": "model", "parts": parts},
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }


async def episode(model, candidate=None, dispatch=None, should_stop=None, **kwargs):
    dispatched, events = [], []

    async def default_dispatch(tool, arguments, invocation_id, *, permit):
        permit.consume(tool["id"], arguments, invocation_id)
        dispatched.append((tool["id"], arguments, invocation_id))
        data = (
            {"items": [{"id": "existing", "amount": 2}]}
            if tool["id"] == "catalog.list"
            else {"id": "created", "amount": arguments["amount"]}
        )
        return {
            "status": "succeeded",
            "data": data,
            "raw": {"structuredContent": data, "content": []},
            "coverage": "sample",
        }

    async def emit(kind, data):
        events.append((kind, data))

    async def running():
        return False

    request = {"status": "ready", "values": {"minimum": 5}}
    request["digest"] = digest(request)
    result = await run_episode(
        case={
            "query": "Create a record and report its identifier.",
            "tool_ids": [tool["id"] for tool in TOOLS],
        },
        tools=TOOLS,
        candidate=candidate,
        model=model,
        dispatch=dispatch or default_dispatch,
        emit=emit,
        limits={"max_steps": 8},
        should_stop=should_stop or running,
        run_mode="training" if candidate is None else "inference",
        stage="baseline" if candidate is None else "inference",
        request_snapshot=request if candidate else None,
        **kwargs,
    )
    return result, dispatched, events


async def test_native_read_write_graph_function_and_final_answer_share_one_loop():
    model = ScriptedModel(
        [call("tool_0")],
        [call("tool_1", {"amount": 9}, "write")],
        [call("oak_function_0", {"minimum": 5}, "function")],
        [{"text": "Created created."}],
    )
    result, dispatched, events = await episode(model, runner_candidate())
    assert result["status"] == "complete"
    assert [item[0] for item in dispatched] == ["catalog.list", "catalog.create"]
    assert result["function_calls"][-1]["result"]["value"] == [{"id": "created", "amount": 9}]
    assert result["function_calls"][-1]["result"]["graph_revision"] == 2
    assert result["function_ids"] == ["check_request", "select_records"]
    assert len(result["dispatch_decisions"]) == 2
    assert result["usage"]["total_tokens"] == 60
    assert result["observations"][1]["raw"]["structuredContent"]["id"] == "created"
    delivered = model.requests[-1]["messages"][-1]["parts"][0]["function_response"]
    assert delivered["id"] == "function"
    assert delivered["response"]["value"][0]["id"] == "created"
    kinds = [kind for kind, _ in events]
    assert (
        kinds.index("tool_result") < kinds.index("graph_updated") < kinds.index("function_result")
    )


async def test_baseline_needs_no_candidate_or_graph_functions():
    model = ScriptedModel([call("tool_0")], [{"text": "Observed existing."}])
    result, dispatched, _ = await episode(model)
    assert result["status"] == "complete"
    assert result["graph"] is None
    assert len(dispatched) == 1
    assert all(not tool["name"].startswith("oak_") for tool in model.requests[0]["tools"])


@pytest.mark.parametrize("operation", ["tool_0", "tool_1"])
async def test_large_native_response_is_saved_and_read_without_repeating_transport(operation):
    from oak.evidence_access import size

    payload = {"items": [{"id": str(i), "body": "x" * 400} for i in range(1500)]}
    payload["items"][-1]["body"] = "decisive"
    requests, calls, events = [], [], []

    class Reader:
        async def turn(self, messages, tools, **kwargs):
            requests.append(
                deepcopy(
                    {"messages": messages, "tools": tools, "instructions": kwargs["instructions"]}
                )
            )
            if len(requests) == 1:
                parts = [call(operation, {"amount": 9} if operation == "tool_1" else {})]
            elif len(requests) == 2:
                delivered = messages[-1]["parts"][0]["function_response"]["response"]
                assert delivered["data"]["omitted"] and delivered["status"] == "succeeded"
                parts = [
                    call(
                        "read_evidence",
                        {"id": delivered["observation_id"], "path": "/data/items/1499"},
                    )
                ]
            else:
                delivered = messages[-1]["parts"][0]["function_response"]["response"]
                assert delivered["value"]["body"] == "decisive"
                parts = [{"text": "decisive"}]
            return {"content": {"role": "model", "parts": parts}}

    async def dispatch(tool, arguments, invocation_id, *, permit):
        permit.consume(tool["id"], arguments, invocation_id)
        calls.append(invocation_id)
        return {
            "status": "succeeded",
            "data": payload,
            "raw": {"structuredContent": payload},
            "coverage": "unknown",
        }

    async def emit(kind, data):
        events.append((kind, data))

    async def running():
        return False

    result = await run_episode(
        case={
            "query": "Read the final item. Preserve the original scope.",
            "tool_ids": [t["id"] for t in TOOLS],
        },
        tools=TOOLS,
        candidate=None,
        model=Reader(),
        dispatch=dispatch,
        emit=emit,
        limits={"max_steps": 4, "input_tokens": 8192},
        should_stop=running,
        run_mode="training",
        stage="baseline",
    )
    assert result["status"] == "complete" and result["final_output"] == "decisive"
    assert len(calls) == 1 and result["observations"][0]["data"] == payload
    assert any(kind == "evidence_read" for kind, _ in events)
    assert all(size(request) // 3 < int(8192 * 0.8) for request in requests)
    assert all(
        "Preserve the original scope." in request["messages"][0]["parts"][0]["text"]
        for request in requests
    )


async def test_json_text_is_never_treated_as_a_tool_call():
    model = ScriptedModel([{"text": '{"name":"tool_1","arguments":{"amount":9}}'}])
    result, dispatched, _ = await episode(model)
    assert result["status"] == "complete"
    assert dispatched == []


async def test_unknown_dispatch_stops_without_replay_or_followup():
    model = ScriptedModel([call("tool_1", {"amount": 9})], [call("tool_1", {"amount": 9})])
    dispatch = AsyncMock(
        return_value={"status": "unknown", "raw": None, "data": None, "error": "timeout"}
    )
    result, _, _ = await episode(model, runner_candidate(), dispatch=dispatch)
    assert result["status"] == "unknown"
    assert len(result["unresolved_outcomes"]) == 1
    assert dispatch.await_count == len(model.requests) == 1
    assert result["graph"]["entities"]["record"] == []
    assert not any(event["kind"] == "observation_delivered" for event in result["trace"])
    assert any(event["kind"] == "observation_prepared" for event in result["trace"])


@pytest.mark.parametrize("failure", ["mapping", "output_schema"])
async def test_successful_write_is_saved_before_graph_failure_stops_later_calls(failure):
    model = ScriptedModel(
        [call("tool_1", {"amount": 9}, "first"), call("tool_1", {"amount": 10}, "second")]
    )
    outcome = {
        "status": "succeeded",
        "dispatched": True,
        "data": {"id": "created", "amount": "invalid"},
        "raw": {"structuredContent": {"id": "created", "amount": "invalid"}},
        "coverage": "unknown",
    }
    if failure == "output_schema":
        outcome["validation_error"] = "The response does not match its output schema."
    dispatch = AsyncMock(return_value=outcome)
    result, _, events = await episode(model, runner_candidate(), dispatch=dispatch)
    assert result["status"] == "graph_processing_failed"
    assert dispatch.await_count == 1
    assert len(result["observations"]) == 1
    assert result["observations"][0]["status"] == "succeeded"
    assert result["observations"][0]["data"] == outcome["data"]
    assert result["graph"]["revision"] == 0
    assert result["graph"]["entities"]["record"] == []
    kinds = [kind for kind, _ in events]
    assert kinds.index("tool_result") < kinds.index("graph_processing_failed")
    assert result["unresolved_outcomes"] == []


async def test_baseline_response_processing_failure_stops_without_replaying_success():
    model = ScriptedModel(
        [call("tool_1", {"amount": 9}, "first"), call("tool_1", {"amount": 10}, "second")]
    )
    dispatch = AsyncMock(
        return_value={
            "status": "succeeded",
            "dispatched": True,
            "data": None,
            "raw": None,
            "validation_error": "Response processing failed.",
        }
    )
    result, _, _ = await episode(model, dispatch=dispatch)
    assert result["status"] in {"graph_processing_failed", "response_processing_failed"}
    assert dispatch.await_count == len(model.requests) == 1
    assert result["observations"][0]["status"] == "succeeded"
    assert result["observations"][0]["validation_error"] == "Response processing failed."
    assert result["unresolved_outcomes"] == []
    assert result["graph"] is None


async def test_native_loop_accepts_declared_credential_reference_with_strict_native_format():
    selected = rental_tools()
    selected[1]["input_schema"]["properties"]["auth"].update(
        format="password", pattern="^resolved-"
    )
    proposed = rental_arguments("offer-a", auth="oak-secret:account")
    model = ScriptedModel([call("tool_0", proposed)], [{"text": "Created booking-1."}])
    dispatch = AsyncMock(return_value={"status": "succeeded", "data": {"id": "booking-1"}})
    result = await run_episode(
        case={"query": "Create a booking.", "tool_ids": [selected[1]["id"]]},
        tools=selected,
        candidate=None,
        model=model,
        dispatch=dispatch,
        emit=AsyncMock(),
        limits={"max_steps": 3},
        should_stop=AsyncMock(return_value=False),
        run_mode="training",
        stage="baseline",
    )
    assert result["status"] == "complete"
    assert dispatch.await_count == 1
    assert dispatch.await_args.args[1] == proposed


def transport_boundary(*, payload=None, output_schema=None):
    """Exercise the production transport with a local MCP response and no database."""
    manager = object.__new__(Training)
    manager.settings = SimpleNamespace(surface_tool_timeout=2)
    tool = rental_tools()[1]
    tool["input_schema"]["properties"]["auth"]["format"] = "password"
    tool["output_schema"] = output_schema
    cleartext = "resolved-example-value"
    logical = rental_arguments("offer-a", auth="oak-secret:account")

    @asynccontextmanager
    async def connection():
        yield object()

    manager.store = SimpleNamespace(
        one=AsyncMock(return_value={"mode": "training", "stage": "baseline", "digest": None}),
        connection=AsyncMock(return_value={"id": tool["connection_id"]}),
        pool=SimpleNamespace(connection=connection),
    )
    response = mcp_types.CallToolResult(
        content=[],
        structuredContent=payload if payload is not None else {"id": "booking-1"},
        isError=False,
    )
    sender = AsyncMock(return_value=response)
    client = SimpleNamespace(session=SimpleNamespace(send_request=sender))

    @asynccontextmanager
    async def session(connection):
        yield client

    manager.connections = SimpleNamespace(
        session=session,
        catalog=AsyncMock(
            return_value=[
                SimpleNamespace(
                    name=tool["name"],
                    input_schema=tool["input_schema"],
                    output_schema=output_schema,
                    description=tool["description"],
                    annotations=None,
                )
            ]
        ),
    )

    async def capture(db, run_id, connection_id, value):
        return value

    async def scrub(db, run_id, value):
        return json.loads(json.dumps(value).replace(cleartext, "[redacted]"))

    manager.credentials = SimpleNamespace(
        resolve=AsyncMock(return_value={**logical, "auth": cleartext}),
        capture=AsyncMock(side_effect=capture),
        scrub=AsyncMock(side_effect=scrub),
    )
    manager._reserve = AsyncMock(return_value="durable-call")
    manager._finish = AsyncMock()
    permit = DispatchPermit(
        "invocation", tool["id"], digest(logical), None, None, None, ("/auth",), True
    )
    run = {"id": "run", "task_id": "task"}
    return manager, run, tool, logical, permit, sender


async def test_transport_refuses_a_direct_call_without_a_kernel_permit():
    manager, run, tool, logical, _, sender = transport_boundary()
    with pytest.raises(TrainingHalt, match="dispatch permit"):
        await manager._dispatch(run, "episode", tool, logical, "invocation", permit=None)
    sender.assert_not_awaited()
    manager._reserve.assert_not_awaited()


async def test_transport_rechecks_persisted_baseline_mode():
    manager, run, tool, logical, permit, sender = transport_boundary()
    manager.store.one.return_value = {"mode": "inference", "stage": "baseline", "digest": None}
    with pytest.raises(TrainingHalt, match="persisted baseline"):
        await manager._dispatch(run, "episode", tool, logical, "invocation", permit=permit)
    sender.assert_not_awaited()


async def test_transport_refuses_changed_task_arguments_after_credential_resolution():
    manager, run, tool, logical, permit, sender = transport_boundary()
    manager.credentials.resolve.return_value["guests"] = 1
    with pytest.raises(ValueError, match="changed checked task arguments"):
        await manager._dispatch(run, "episode", tool, logical, "invocation", permit=permit)
    sender.assert_not_awaited()
    manager._reserve.assert_not_awaited()


@pytest.mark.parametrize(
    "resolved, expected", [("resolved-example-value", "succeeded"), ("invalid-format", "rejected")]
)
async def test_transport_validates_native_credential_format_after_resolution(resolved, expected):
    manager, run, tool, logical, permit, sender = transport_boundary()
    tool["input_schema"]["properties"]["auth"]["pattern"] = "^resolved-"
    manager.credentials.resolve.return_value["auth"] = resolved
    if expected == "rejected":
        with pytest.raises(ValueError, match="declared JSON Schema"):
            await manager._dispatch(run, "episode", tool, logical, "invocation", permit=permit)
        sender.assert_not_awaited()
        manager._reserve.assert_not_awaited()
    else:
        result = await manager._dispatch(run, "episode", tool, logical, "invocation", permit=permit)
        assert result["status"] == "succeeded"
        assert sender.await_args.args[0].params.arguments["auth"] == resolved


async def test_transport_contract_change_stops_before_durable_dispatch():
    manager, run, tool, logical, permit, sender = transport_boundary()
    manager.connections.catalog.return_value[0].description = "Changed operation."
    with pytest.raises(TrainingHalt, match="contract changed"):
        await manager._dispatch(run, "episode", tool, logical, "invocation", permit=permit)
    sender.assert_not_awaited()
    manager._reserve.assert_not_awaited()


async def test_transport_refuses_reused_permit_before_a_second_send():
    manager, run, tool, logical, permit, sender = transport_boundary()
    await manager._dispatch(run, "episode", tool, logical, "invocation", permit=permit)
    with pytest.raises(ValueError, match="does not match"):
        await manager._dispatch(run, "episode", tool, logical, "invocation", permit=permit)
    assert sender.await_count == 1


async def test_transport_preserves_success_when_output_schema_validation_fails():
    manager, run, tool, logical, permit, sender = transport_boundary(
        payload={"id": 99},
        output_schema={
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    )
    result = await manager._dispatch(run, "episode", tool, logical, "invocation", permit=permit)
    assert sender.await_count == 1
    assert result["status"] == "succeeded"
    assert result["validation_error"]
    assert result["data"] == {"id": 99}
    assert manager._finish.await_args.args[1] == "succeeded"


async def test_transport_scrubs_known_credentials_from_structured_data_and_raw():
    manager, run, tool, logical, permit, sender = transport_boundary(
        payload={"id": "booking-1", "debug": "resolved-example-value"}
    )
    result = await manager._dispatch(run, "episode", tool, logical, "invocation", permit=permit)
    assert sender.await_count == 1
    assert "resolved-example-value" not in json.dumps(result)
    assert "resolved-example-value" not in json.dumps(manager._finish.await_args.args)


async def test_native_output_contract_is_validated_before_credential_references_replace_values():
    manager, run, tool, logical, permit, sender = transport_boundary(
        payload={"api_token": "resolved-example-value"},
        output_schema={
            "type": "object",
            "properties": {"api_token": {"type": "string", "pattern": "^resolved-"}},
            "required": ["api_token"],
        },
    )
    manager.credentials.capture.side_effect = None
    manager.credentials.capture.return_value = {"api_token": "oak-secret:new-credential"}
    result = await manager._dispatch(run, "episode", tool, logical, "invocation", permit=permit)
    assert sender.await_count == 1
    assert result["status"] == "succeeded"
    assert result["validation_error"] is None
    assert result["data"] == {"api_token": "oak-secret:new-credential"}
    assert "resolved-example-value" not in json.dumps(result)


@pytest.mark.parametrize("failed_step", ["capture", "scrub"])
async def test_sanitization_failure_preserves_external_success_without_secret_payload(failed_step):
    manager, run, tool, logical, permit, sender = transport_boundary(
        payload={"id": "booking-1", "debug": "resolved-example-value"}
    )
    getattr(manager.credentials, failed_step).side_effect = RuntimeError(
        "Credential store unavailable."
    )
    result = await manager._dispatch(run, "episode", tool, logical, "invocation", permit=permit)
    assert sender.await_count == 1
    assert result["status"] == "succeeded"
    assert result.get("validation_error")
    assert "resolved-example-value" not in json.dumps(result)
    assert "resolved-example-value" not in json.dumps(manager._finish.await_args.args)
    assert manager._finish.await_args.args[1] == "succeeded"


async def test_cancellation_after_external_success_preserves_success_and_hides_payload():
    manager, run, tool, logical, permit, sender = transport_boundary(
        payload={"id": "booking-1", "debug": "resolved-example-value"}
    )
    manager.credentials.capture.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await manager._dispatch(run, "episode", tool, logical, "invocation", permit=permit)
    assert sender.await_count == 1
    assert manager._finish.await_args.args[1] == "succeeded"
    assert "resolved-example-value" not in json.dumps(manager._finish.await_args.args)


@pytest.mark.parametrize(
    "part", [call("not_granted"), call("tool_1", {"amount": True}), call("tool_1", {"amount": "9"})]
)
async def test_unknown_tools_and_invalid_arguments_never_dispatch(part):
    model = ScriptedModel([part], [{"text": "Cannot complete."}])
    result, dispatched, _ = await episode(model)
    assert dispatched == []
    assert any(event["kind"] == "tool_rejected" for event in result["trace"])


async def test_stop_between_native_calls_prevents_later_dispatch():
    model = ScriptedModel([call("tool_0"), call("tool_1", {"amount": 9})])
    stop = AsyncMock(side_effect=[False, False, True])
    result, dispatched, _ = await episode(model, should_stop=stop)
    assert result["status"] == "stopped"
    assert len(dispatched) == 1


async def test_model_reservation_precedes_call_and_usage_is_finished():
    order = []
    model = ScriptedModel([{"text": "Done."}])

    async def reserve(kind, request):
        assert not model.requests
        order.append(kind)
        return "model-call"

    async def finish(identifier, status, response, usage=None):
        assert len(model.requests) == 1
        order.append((identifier, status, usage["total_tokens"]))

    await episode(model, reserve=reserve, finish=finish)
    assert order == ["model", ("model-call", "succeeded", 15)]


async def test_native_gemini_method_preserves_function_parts_and_disables_sdk_dispatch(monkeypatch):
    content = types.Content(
        role="model",
        parts=[
            types.Part(
                function_call=types.FunctionCall(id="native-id", name="tool_0", args={}),
                thought_signature=b"opaque-signature",
            )
        ],
    )
    response = types.GenerateContentResponse(
        candidates=[types.Candidate(content=content, finish_reason=types.FinishReason.STOP)],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=10, candidates_token_count=5, total_token_count=15
        ),
    )
    sdk = SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(
                count_tokens=AsyncMock(return_value=SimpleNamespace(total_tokens=10)),
                generate_content=AsyncMock(return_value=response),
            ),
            aclose=AsyncMock(),
        )
    )
    model = GeminiClient(Settings(gemini_project="test"))
    monkeypatch.setattr(model, "_client", lambda: sdk)
    result = await model.turn(
        [{"role": "user", "parts": [{"text": "Observe."}]}],
        [{"name": "tool_0", "description": "Observe.", "input_schema": {"type": "object"}}],
        limits=GenerationLimits(1000, 1000, 10),
    )
    assert result["tool_calls"] == [
        {"id": "native-id", "name": "tool_0", "arguments": {}, "index": 0}
    ]
    restored = types.Content.model_validate(result["content"])
    assert restored.parts[0].thought_signature == b"opaque-signature"
    config = sdk.aio.models.generate_content.call_args.kwargs["config"]
    assert config.automatic_function_calling.disable
    assert config.response_json_schema is None
    assert config.tools[0].function_declarations[0].name == "tool_0"
    sdk.aio.aclose.assert_awaited_once()


def test_schema_normalization_retains_nested_types_without_changing_local_schema():
    original = Candidate.model_json_schema()
    schema = provider_schema(original)
    assert schema["properties"]["functions"]["items"] == {"$ref": "#/$defs/Function"}
    assert "AddExpression" in schema["$defs"]
    assert original["$defs"]["AddExpression"]["required"] == ["left", "right"]
    assert set(schema["required"]) == set(schema["properties"])


def test_acyclic_discovery_schema_retains_its_structured_definitions():
    schema = provider_schema(SchemaProposal.model_json_schema())
    assert "EntityProposal" in schema["$defs"]
    entity = schema["$defs"]["EntityProposal"]
    assert "identity_keys" in entity["properties"]
    assert set(entity["required"]) == set(entity["properties"])
    assert schema["properties"]["entities"]["items"] == {"$ref": "#/$defs/EntityProposal"}


def test_provider_operand_object_does_not_relax_local_candidate_validation():
    value = graph_candidate()
    predicate = value["constraints"][0]["predicate"]
    predicate["left"] = {"kind": "add", "right": {"kind": "literal", "value": 1}}
    with pytest.raises(ValueError, match="left"):
        Candidate.model_validate(value)


@pytest.mark.parametrize("invalid", [False, True])
async def test_recursive_json_generation_sends_full_schema_and_validates_output(
    monkeypatch, invalid
):
    value = graph_candidate()
    if invalid:
        value["constraints"][0]["predicate"]["left"] = {
            "kind": "add",
            "right": {"kind": "literal", "value": 1},
        }
    response = types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=[types.Part(text=json.dumps(value))]),
                finish_reason=types.FinishReason.STOP,
            )
        ],
    )
    sdk = SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(
                count_tokens=AsyncMock(return_value=SimpleNamespace(total_tokens=500)),
                generate_content=AsyncMock(return_value=response),
            ),
            aclose=AsyncMock(),
        )
    )
    model = GeminiClient(Settings(gemini_project="test"))
    monkeypatch.setattr(model, "_client", lambda: sdk)
    if invalid:
        with pytest.raises(ModelFailure) as error:
            await model.generate(
                "Build a candidate.", {}, Candidate, limits=GenerationLimits(32768, 4096, 10)
            )
        assert error.value.code == "invalid_output"
        assert error.value.failed_output == value
        assert error.value.validation_errors
        assert all(set(item) == {"loc", "type", "msg"} for item in error.value.validation_errors)
        assert any(
            item["type"] == "missing" and item["loc"][-1] == "left"
            for item in error.value.validation_errors
        )
    else:
        result = await model.generate(
            "Build a candidate.", {}, Candidate, limits=GenerationLimits(32768, 4096, 10)
        )
        assert result.data.functions[0].id == "select_records"
        assert result.request["contents"][0]["parts"][0]["text"] == "{}"
        assert result.request["config"]["response_mime_type"] == "application/json"
        assert "response_json_schema" not in result.request["config"]
    config = sdk.aio.models.generate_content.call_args.kwargs["config"]
    assert "AddExpression" in config.system_instruction
    assert '"required":["left","right"]' in config.system_instruction
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema is None
    sdk.aio.aclose.assert_awaited_once()


def test_failed_proposal_evidence_is_bounded_and_preserves_invalid_json_as_text():
    assert _failed_output('{"bad":') == '{"bad":'
    assert _failed_output('{"value":NaN}') == '{"value":NaN}'
    assert len(_failed_output("x" * 100_001)) == 100_000


async def test_patch_proposal_also_uses_json_mode_with_full_local_grammar(monkeypatch):
    response = types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            text=json.dumps(
                                {
                                    "reason": "No supported repair is available.",
                                    "patch": None,
                                }
                            )
                        )
                    ],
                ),
                finish_reason=types.FinishReason.STOP,
            )
        ]
    )
    sdk = SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(
                count_tokens=AsyncMock(return_value=SimpleNamespace(total_tokens=500)),
                generate_content=AsyncMock(return_value=response),
            ),
            aclose=AsyncMock(),
        )
    )
    model = GeminiClient(Settings(gemini_project="test"))
    monkeypatch.setattr(model, "_client", lambda: sdk)
    result = await model.generate(
        "Propose a repair.", {}, PatchProposal, limits=GenerationLimits(32768, 4096, 10)
    )
    assert result.data.patch is None
    config = sdk.aio.models.generate_content.call_args.kwargs["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema is None
    assert "TargetedPatch" in config.system_instruction
