"""Two domains share one loop definition through ordinary registered Pydantic models."""

import json
from dataclasses import FrozenInstanceError
from typing import Literal

import pytest
from pydantic import BaseModel, ValidationError

from oak_contracts.task_boundary import (
    AgentLoopDefinition,
    Bounds,
    Declaration,
    FunctionContract,
    NativeToolContract,
    TaskBinding,
    TaskDefinition,
    ToolRef,
)


class OfferRequest(Declaration):
    city: str
    party_size: int
    budget_minor: int


class SearchInput(Declaration):
    city: str


class SearchOutput(Declaration):
    offer_ids: list[str]


class DetailInput(Declaration):
    offer_id: str


class DetailOutput(Declaration):
    offer_id: str
    capacity: int
    total_minor: int


class OfferResult(Declaration):
    selected_offer_id: str
    evidence_ids: list[str]


class EligibilityInput(Declaration):
    offer_ids: list[str]
    party_size: int


class TicketRequest(Declaration):
    ticket_id: str
    title: str
    body: str


class TicketInput(Declaration):
    ticket_id: str


class TicketOutput(Declaration):
    customer_tier: Literal["standard", "priority"]


class TicketResult(Declaration):
    category: Literal["access", "billing", "other"]
    priority: Literal["normal", "urgent"]


def changed(model, **updates):
    raw = model.model_dump(mode="json") | updates
    return type(model).model_validate_json(json.dumps(raw))


@pytest.fixture
def catalog():
    native = tuple(
        NativeToolContract(
            tool_id=name,
            tool_version="1.0.0",
            binding_key=binding,
            input_profile=input_profile,
            output_profile=output_profile,
            effect="read",
        )
        for name, binding, input_profile, output_profile in (
            ("offers.search", "search_offers", "SearchInput/1", "SearchOutput/1"),
            ("offers.details", "offer_details", "DetailInput/1", "DetailOutput/1"),
            ("tickets.lookup", "ticket_lookup", "TicketInput/1", "TicketOutput/1"),
        )
    )
    functions = tuple(
        FunctionContract(
            function_id=name,
            function_version="1.0.0",
            binding_key="c4_function_dispatch",
            input_profile=input_profile,
            result_profile=result_profile,
            effect="read",
        )
        for name, input_profile, result_profile in (
            ("check_capacity", "EligibilityInput/1", "SearchOutput/1"),
            ("classify_ticket", "TicketRequest/1", "TicketResult/1"),
        )
    )
    loop = AgentLoopDefinition(
        definition_id="reference-loop",
        version="1.0.0",
        loop_profile="sequential_readonly/1",
        attachment="managed",
        driver="scripted_fixture",
        native_tools=native,
        bounds=Bounds(max_decisions=12, max_seconds=900),
        observation_hook="c4_after_call",
        finalization_hook="c4_finalize",
        parallel_actions=False,
        cross_run_memory="disabled",
        scope_requirement="project_agent_run",
        action_kinds=("native", "function", "finalize"),
    )
    tasks = {
        name: TaskDefinition(
            task_id=name,
            version="1.0.0",
            input_profile=input_profile,
            result_profile=result_profile,
            required_native_tools=tuple(
                ToolRef(tool_id=t.tool_id, tool_version=t.tool_version) for t in tools
            ),
            functions=(function,),
            mapping_id=f"{name}-mapping",
            evaluator_id=f"{name}-evaluator",
            suite_id=f"{name}-suite",
        )
        for name, input_profile, result_profile, tools, function in (
            ("offer-selection", "OfferRequest/1", "OfferResult/1", native[:2], functions[0]),
            ("ticket-triage", "TicketRequest/1", "TicketResult/1", native[2:], functions[1]),
        )
    }
    models = {
        f"{model.__name__}/1": model
        for model in (
            OfferRequest,
            SearchInput,
            SearchOutput,
            DetailInput,
            DetailOutput,
            OfferResult,
            EligibilityInput,
            TicketRequest,
            TicketInput,
            TicketOutput,
            TicketResult,
        )
    }
    registrations = {
        "models": models,
        "native_registry": {(t.tool_id, t.tool_version): t for t in native},
        "function_registry": {(f.function_id, f.function_version): f for f in functions},
        "resources": {
            kind: {getattr(task, f"{kind}_id") for task in tasks.values()}
            for kind in ("mapping", "evaluator", "suite")
        },
    }
    return loop, tasks, registrations


def bind(catalog, name="offer-selection"):
    loop, tasks, registrations = catalog
    return TaskBinding(loop, tasks[name], **registrations)


def final(task_id, result):
    return {"kind": "finalize", "task_id": task_id, "task_version": "1.0.0", "result": result}


def test_two_domains_share_the_same_loop_with_different_inputs_results_and_tool_counts(catalog):
    offers, tickets = bind(catalog), bind(catalog, "ticket-triage")
    assert offers.loop is tickets.loop
    assert len(offers.task.required_native_tools) == 2
    assert len(tickets.task.required_native_tools) == 1
    assert isinstance(
        offers.validate_task_input({"city": "Boston", "party_size": 4, "budget_minor": 42000}),
        OfferRequest,
    )
    assert isinstance(
        tickets.validate_task_input(
            {"ticket_id": "t1", "title": "Locked out", "body": "No access"}
        ),
        TicketRequest,
    )
    offers.validate_action(
        final("offer-selection", {"selected_offer_id": "o1", "evidence_ids": []})
    )
    tickets.validate_action(final("ticket-triage", {"category": "access", "priority": "urgent"}))


def test_native_arguments_and_outputs_use_the_matching_registered_contract(catalog):
    binding = bind(catalog)
    binding.validate_action(
        {
            "kind": "native",
            "tool_id": "offers.search",
            "tool_version": "1.0.0",
            "arguments": {"city": "Boston"},
        }
    )
    assert isinstance(
        binding.validate_native_result("offers.search", "1.0.0", {"offer_ids": ["o1"]}),
        SearchOutput,
    )
    with pytest.raises(ValidationError):
        binding.validate_native_result("offers.search", "1.0.0", {"customer_tier": "priority"})


def test_registered_but_task_unpermitted_tool_cannot_be_called(catalog):
    with pytest.raises(ValueError, match="native_tool_not_permitted"):
        bind(catalog, "ticket-triage").validate_action(
            {
                "kind": "native",
                "tool_id": "offers.search",
                "tool_version": "1.0.0",
                "arguments": {"city": "Boston"},
            }
        )


def test_missing_model_registration_blocks_binding(catalog):
    catalog[2]["models"].pop("TicketOutput/1")
    with pytest.raises(ValueError, match="model_profile_unregistered"):
        bind(catalog, "ticket-triage")


def test_changed_tool_contract_cannot_reuse_a_registered_binding(catalog):
    loop, tasks, registrations = catalog
    wrong = changed(loop.native_tools[0], output_profile="TicketOutput/1")
    loop = changed(
        loop,
        native_tools=[
            wrong.model_dump(mode="json"),
            *[t.model_dump(mode="json") for t in loop.native_tools[1:]],
        ],
    )
    with pytest.raises(ValueError, match="native_contract_unregistered_or_incompatible"):
        TaskBinding(loop, tasks["offer-selection"], **registrations)


def test_task_cannot_require_an_absent_tool_version(catalog):
    loop, tasks, registrations = catalog
    task = changed(
        tasks["ticket-triage"],
        required_native_tools=[{"tool_id": "tickets.lookup", "tool_version": "2.0.0"}],
    )
    with pytest.raises(ValueError, match="required_native_tool_unavailable"):
        TaskBinding(loop, task, **registrations)


def test_readonly_loop_rejects_a_write_effect(catalog):
    with pytest.raises(ValidationError):
        changed(catalog[0].native_tools[0], effect="write")


def test_domain_functions_are_registered_data_and_can_be_zero_one_or_many(catalog):
    loop, tasks, registrations = catalog
    task = tasks["ticket-triage"]
    functions = list(registrations["function_registry"].values())
    for declarations in ([], [functions[1]], functions):
        variant = changed(task, functions=[f.model_dump(mode="json") for f in declarations])
        TaskBinding(loop, variant, **registrations)
    bound = bind(catalog, "ticket-triage")
    bound.validate_action(
        {
            "kind": "function",
            "function_id": "classify_ticket",
            "function_version": "1.0.0",
            "arguments": {"ticket_id": "t1", "title": "Locked out", "body": "No access"},
        }
    )
    assert isinstance(
        bound.validate_function_result(
            "classify_ticket", "1.0.0", {"category": "access", "priority": "urgent"}
        ),
        TicketResult,
    )
    with pytest.raises(ValueError, match="function_not_permitted"):
        bound.validate_function_result("check_capacity", "1.0.0", {"offer_ids": []})


def test_unregistered_function_or_required_resource_blocks_binding(catalog):
    registrations = catalog[2]
    registry = registrations["function_registry"]
    saved = registry.pop(("classify_ticket", "1.0.0"))
    with pytest.raises(ValueError, match="function_contract_unregistered_or_incompatible"):
        bind(catalog, "ticket-triage")
    registry[("classify_ticket", "1.0.0")] = saved
    registrations["resources"]["evaluator"].clear()
    with pytest.raises(ValueError, match="evaluator_unregistered"):
        bind(catalog, "ticket-triage")


def test_cross_task_final_identity_cannot_be_hidden_by_a_valid_result_shape(catalog):
    with pytest.raises(ValueError, match="final_result_task_mismatch"):
        bind(catalog, "ticket-triage").validate_action(
            final("offer-selection", {"category": "access", "priority": "urgent"})
        )


def test_matching_task_identity_still_requires_the_correct_result_schema(catalog):
    with pytest.raises(ValidationError):
        bind(catalog, "ticket-triage").validate_action(
            final("ticket-triage", {"selected_offer_id": "o1", "evidence_ids": []})
        )


def test_unknown_payload_fields_and_numeric_coercion_are_rejected(catalog):
    binding = bind(catalog)
    request = {"city": "Boston", "party_size": 4, "budget_minor": 42000}
    with pytest.raises(ValidationError):
        binding.validate_task_input(request | {"secret_override": True})
    with pytest.raises(ValidationError):
        binding.validate_task_input(request | {"party_size": "4"})


def test_permissive_models_cannot_disable_unknown_field_checks(catalog):
    class Permissive(BaseModel):
        city: str

    catalog[2]["models"]["OfferRequest/1"] = Permissive
    with pytest.raises(ValueError, match="model_must_forbid_unknown_fields"):
        bind(catalog)


def test_declaration_contains_no_import_endpoint_secret_or_readiness_escape_hatch(catalog):
    for extra in ("import_path", "endpoint", "credential", "status", "package_ref"):
        with pytest.raises(ValidationError):
            changed(catalog[0], **{extra: "untrusted-value"})
    with pytest.raises(ValidationError):
        changed(catalog[0], parallel_actions=0)


def test_generic_budget_is_positive_and_not_capped_by_offer_fixture_defaults():
    assert Bounds(max_decisions=100, max_seconds=3600).max_decisions == 100
    with pytest.raises(ValidationError):
        Bounds(max_decisions=True, max_seconds=900)
    with pytest.raises(ValidationError):
        Bounds(max_decisions=12, max_seconds=0)


def test_bound_definitions_and_model_registry_snapshot_cannot_silently_change(catalog):
    binding = bind(catalog)
    catalog[2]["models"].clear()
    assert isinstance(
        binding.validate_task_input({"city": "Boston", "party_size": 4, "budget_minor": 42000}),
        OfferRequest,
    )
    with pytest.raises(FrozenInstanceError):
        binding.task = catalog[1]["ticket-triage"]
