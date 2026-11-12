"""Check that every external invocation has its own kernel decision."""

import asyncio
from copy import deepcopy

import pytest

from oak.discovery_validation import digest
from oak.evidence_graph import EvidenceGraph
from oak.kernel_dispatcher import DispatchPermit, KernelDispatcher, verify_transport_arguments
from oak.repair_patch import candidate_digest
from tests.kernel_fixtures import (
    DEFAULT_VALUES,
    READ_ID,
    WRITE_ID,
    arguments,
    candidate,
    candidate_data,
    observe,
    snapshot,
    tools,
)


class Harness:
    def __init__(self, *, selected=None, request=None, accepted=None):
        self.candidate = candidate() if accepted is None else accepted
        self.graph = EvidenceGraph(self.candidate)
        self.tools = tools() if selected is None else selected
        self.events = []
        self.calls = []
        self.dispatcher = KernelDispatcher(
            candidate=self.candidate,
            graph=self.graph,
            request_snapshot=snapshot() if request is None else request,
            tools=self.tools,
            run_mode="inference",
            stage="inference",
            transport=self.transport,
            record=self.record,
        )

    async def record(self, kind, **data):
        self.events.append((kind, deepcopy(data)))

    async def transport(self, tool, values, invocation_id, *, permit):
        assert self.events[-1][0] == "dispatch_decision"
        assert self.events[-1][1]["status"] == "allowed"
        permit.consume(tool["id"], values, invocation_id)
        self.calls.append((tool["id"], deepcopy(values), invocation_id, permit))
        return {"status": "succeeded", "data": {"id": "booking-1"}, "dispatched": True}

    async def dispatch(self, tool_id, values, invocation_id="invocation-1"):
        tool = next(tool for tool in self.tools if tool["id"] == tool_id)
        return await self.dispatcher(tool, values, invocation_id)


@pytest.mark.asyncio
async def test_read_guard_allows_evidence_acquisition_on_empty_graph():
    harness = Harness()
    result = await harness.dispatch(READ_ID, arguments())
    assert result["status"] == "succeeded"
    assert len(harness.calls) == 1
    assert [call["function_id"] for call in result["decision"]["function_calls"]] == [
        "check_parameters"
    ]


@pytest.mark.asyncio
async def test_create_automatically_executes_all_bound_checks():
    harness = Harness()
    observe(harness.graph)
    result = await harness.dispatch(WRITE_ID, arguments("offer-a"))
    assert result["status"] == "succeeded"
    decision = result["decision"]
    assert decision["binding_id"] == "create"
    assert [call["function_id"] for call in decision["function_calls"]] == [
        "check_parameters",
        "check_offer",
    ]
    assert all(call["automatic"] for call in decision["function_calls"])
    assert len(harness.calls) == 1
    assert decision["arguments_digest"] == digest(arguments("offer-a"))
    assert decision["request_digest"] == snapshot()["digest"]
    assert decision["graph_revision"] == 1


@pytest.mark.asyncio
async def test_missing_subject_returns_available_source_without_transport():
    harness = Harness()
    result = await harness.dispatch(WRITE_ID, arguments("offer-a"))
    assert result["status"] == "missing_evidence"
    assert result["dispatched"] is False
    assert harness.calls == []
    assert result["missing_dependencies"]
    assert {
        source["tool_id"]
        for missing in result["missing_dependencies"]
        for source in missing["sources"]
    } == {READ_ID}


@pytest.mark.asyncio
async def test_source_suggestions_respect_selected_tools():
    harness = Harness(selected=[tools()[1]])
    result = await harness.dispatch(WRITE_ID, arguments("offer-a"))
    assert result["status"] == "missing_evidence"
    assert all(not gap["sources"] for gap in result["missing_dependencies"])


@pytest.mark.asyncio
async def test_false_request_condition_wins_over_unknown_graph_conditions():
    harness = Harness()
    result = await harness.dispatch(WRITE_ID, arguments("offer-a", guests=1))
    assert result["status"] == "rejected"
    assert {condition["value"] for condition in result["conditions"]} == {
        "true",
        "false",
        "unknown",
    }
    assert harness.calls == []


@pytest.mark.asyncio
async def test_changing_guests_cannot_evade_original_request():
    harness = Harness()
    observe(harness.graph, [{"id": "offer-a", "capacity": 1, "total_cost": 8000}], guests=1)
    result = await harness.dispatch(WRITE_ID, arguments("offer-a", guests=1))
    assert result["status"] == "rejected"
    assert harness.calls == []
    assert (
        next(c for c in result["conditions"] if c["condition_id"] == "party_match")["value"]
        == "false"
    )


@pytest.mark.asyncio
async def test_prior_allowing_check_does_not_authorize_another_offer():
    harness = Harness()
    observe(harness.graph)
    first = await harness.dispatch(WRITE_ID, arguments("offer-a"), "first")
    second = await harness.dispatch(WRITE_ID, arguments("offer-b"), "second")
    assert first["status"] == "succeeded"
    assert second["status"] == "missing_evidence"
    assert len(harness.calls) == 1


@pytest.mark.asyncio
async def test_each_invocation_checks_the_current_graph_revision():
    harness = Harness()
    observe(harness.graph)
    await harness.dispatch(WRITE_ID, arguments("offer-a"), "first")
    observe(
        harness.graph,
        [{"id": "offer-a", "capacity": 4, "total_cost": 40000}],
        identifier="changed-price",
    )
    result = await harness.dispatch(WRITE_ID, arguments("offer-a"), "second")
    assert result["status"] == "rejected"
    assert result["graph_revision"] == 2
    assert len(harness.calls) == 1


@pytest.mark.asyncio
async def test_request_dependency_is_checked_only_when_operation_uses_it():
    values = {name: value for name, value in DEFAULT_VALUES.items() if name != "budget"}
    harness = Harness(request=snapshot(values))
    read = await harness.dispatch(READ_ID, arguments(), "read")
    observe(harness.graph)
    write = await harness.dispatch(WRITE_ID, arguments("offer-a"), "write")
    assert read["status"] == "succeeded"
    assert write["status"] == "missing_evidence"
    assert len(harness.calls) == 1
    assert any(
        gap["source"] == "request" and gap["property"] == "budget"
        for gap in write["missing_dependencies"]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [True, "3", None])
async def test_declared_tool_schema_is_checked_before_transport(value):
    harness = Harness()
    result = await harness.dispatch(READ_ID, arguments(guests=value))
    assert result["status"] == "rejected"
    assert result["error"] == "check_error"
    assert harness.calls == []


@pytest.mark.asyncio
async def test_tool_definition_cannot_change_after_selection():
    harness = Harness()
    changed = deepcopy(harness.tools[0])
    changed["input_schema"] = {}
    result = await harness.dispatcher(changed, arguments(), "changed-tool")
    assert result["status"] == "rejected"
    assert harness.calls == []


@pytest.mark.asyncio
async def test_saved_snapshot_is_copied_before_external_mutation():
    request = snapshot()
    harness = Harness(request=request)
    request["values"]["guests"] = 1
    result = await harness.dispatch(READ_ID, arguments(guests=1))
    assert result["status"] == "rejected"
    assert harness.calls == []


def test_request_digest_mismatch_prevents_episode_start():
    request = snapshot()
    request["values"]["guests"] = 1
    with pytest.raises(ValueError, match="digest"):
        Harness(request=request)


def test_graph_must_use_the_same_accepted_kernel():
    accepted = candidate()
    changed = candidate_data()
    changed["requirements"]["requirements"][0]["statement"] += " Changed definition."
    with pytest.raises(ValueError, match="graph does not belong"):
        KernelDispatcher(
            candidate=accepted,
            graph=EvidenceGraph(changed),
            request_snapshot=snapshot(),
            tools=tools(),
            run_mode="inference",
            stage="inference",
            transport=None,
            record=None,
        )


def test_unicode_candidate_digest_matches_persisted_kernel_digest():
    data = candidate_data()
    data["requirements"]["requirements"][0]["statement"] += " Café."
    harness = Harness(accepted=data)
    assert harness.dispatcher.candidate_digest == candidate_digest(harness.graph.candidate)


@pytest.mark.parametrize(
    "mode, stage",
    [
        ("inference", "inference"),
        ("inference", "baseline"),
        ("training", "evaluation"),
        ("training", "candidate"),
    ],
)
def test_absent_kernel_is_refused_outside_training_baseline(mode, stage):
    with pytest.raises(ValueError, match="supported scoped kernel"):
        KernelDispatcher(
            candidate=None,
            graph=None,
            request_snapshot=None,
            tools=tools(),
            run_mode=mode,
            stage=stage,
            transport=None,
            record=None,
        )


@pytest.mark.asyncio
async def test_baseline_bypass_requires_both_training_mode_and_baseline_stage():
    calls = []

    async def record(kind, **data):
        calls.append((kind, data["baseline"]))

    async def transport(tool, values, invocation_id, *, permit):
        permit.consume(tool["id"], values, invocation_id)
        assert permit.baseline
        return {"status": "succeeded"}

    dispatcher = KernelDispatcher(
        candidate=None,
        graph=None,
        request_snapshot=None,
        tools=tools(),
        run_mode="training",
        stage="baseline",
        transport=transport,
        record=record,
    )
    result = await dispatcher(tools()[0], arguments(), "baseline")
    assert result["status"] == "succeeded"
    assert calls == [("dispatch_decision", True)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "declaration", [{"format": "password"}, {"writeOnly": True}, {"x-oak-credential": True}]
)
async def test_baseline_allows_only_contract_declared_credentials(declaration):
    selected = tools()
    selected[1]["input_schema"]["properties"]["auth"].update(declaration)
    calls = []

    async def record(kind, **data):
        pass

    async def transport(tool, values, invocation_id, *, permit):
        permit.consume(tool["id"], values, invocation_id)
        assert permit.credential_paths == ("/auth",)
        calls.append(invocation_id)
        return {"status": "succeeded"}

    dispatcher = KernelDispatcher(
        candidate=None,
        graph=None,
        request_snapshot=None,
        tools=selected,
        run_mode="training",
        stage="baseline",
        transport=transport,
        record=record,
    )
    allowed = await dispatcher(
        selected[1], arguments("offer-a", auth="oak-secret:account"), "credential"
    )
    rejected = await dispatcher(selected[1], arguments("oak-secret:offer"), "task-field")
    assert allowed["status"] == "succeeded"
    assert rejected["status"] == "rejected"
    assert calls == ["credential"]


@pytest.mark.asyncio
async def test_credential_reference_in_checked_task_field_is_rejected():
    harness = Harness()
    result = await harness.dispatch(WRITE_ID, arguments("oak-secret:offer"))
    assert result["status"] == "rejected"
    assert "task argument" in result["message"]
    assert harness.calls == []


@pytest.mark.asyncio
async def test_declared_credential_substitution_does_not_change_checked_values():
    harness = Harness()
    observe(harness.graph)
    logical = arguments("offer-a", auth="oak-secret:account")
    result = await harness.dispatch(WRITE_ID, logical)
    assert result["status"] == "succeeded"
    permit = harness.calls[0][3]
    assert permit.credential_paths == ("/auth",)
    resolved = {**logical, "auth": "resolved-token"}
    verify_transport_arguments(logical, resolved, permit.credential_paths)
    with pytest.raises(ValueError, match="changed checked task arguments"):
        verify_transport_arguments(logical, {**resolved, "guests": 1}, permit.credential_paths)


@pytest.mark.asyncio
async def test_declared_credential_reference_defers_native_format_check_to_transport():
    selected = tools()
    selected[1]["input_schema"]["properties"]["auth"].update(
        format="password", pattern="^resolved-"
    )
    harness = Harness(selected=selected)
    observe(harness.graph)
    allowed = await harness.dispatch(
        WRITE_ID, arguments("offer-a", auth="oak-secret:account"), "credential"
    )
    rejected = await harness.dispatch(
        WRITE_ID, arguments("oak-secret:offer", auth="oak-secret:account"), "task-field"
    )
    assert allowed["status"] == "succeeded"
    assert rejected["status"] == "rejected"
    assert len(harness.calls) == 1


@pytest.mark.parametrize("changed", [{"guests": True}, {"new_key": "value"}, {"auth": 42}])
def test_transport_refuses_undeclared_or_invalid_mutations(changed):
    logical = arguments("offer-a", auth="oak-secret:account")
    with pytest.raises(ValueError):
        verify_transport_arguments(logical, {**logical, **changed}, ("/auth",))


def test_invocation_permit_is_bound_to_tool_arguments_and_call_id():
    values = arguments("offer-a")
    permit = DispatchPermit("call", WRITE_ID, digest(values), "kernel", "request", 1, (), False)
    for tool_id, proposed, invocation in [
        (READ_ID, values, "call"),
        (WRITE_ID, arguments("offer-b"), "call"),
        (WRITE_ID, values, "another-call"),
    ]:
        with pytest.raises(ValueError, match="does not match"):
            permit.consume(tool_id, proposed, invocation)
    permit.consume(WRITE_ID, values, "call")
    with pytest.raises(ValueError, match="does not match"):
        permit.consume(WRITE_ID, values, "call")


@pytest.mark.asyncio
async def test_dispatch_lock_serializes_decision_and_transport():
    harness = Harness()
    entered, release = asyncio.Event(), asyncio.Event()
    original = harness.dispatcher.transport

    async def transport(tool, values, invocation_id, *, permit):
        if invocation_id == "first":
            entered.set()
            await release.wait()
        return await original(tool, values, invocation_id, permit=permit)

    harness.dispatcher.transport = transport
    first = asyncio.create_task(harness.dispatch(READ_ID, arguments(), "first"))
    await entered.wait()
    second = asyncio.create_task(harness.dispatch(READ_ID, arguments(), "second"))
    await asyncio.sleep(0)
    assert len(harness.events) == 1
    release.set()
    await asyncio.gather(first, second)
    assert [call[2] for call in harness.calls] == ["first", "second"]


@pytest.mark.asyncio
async def test_decision_persistence_failure_prevents_transport():
    harness = Harness()

    async def reject_record(*args, **kwargs):
        raise RuntimeError("Decision storage unavailable.")

    harness.dispatcher.record = reject_record
    with pytest.raises(RuntimeError, match="Decision storage"):
        await harness.dispatch(READ_ID, arguments())
    assert harness.calls == []
