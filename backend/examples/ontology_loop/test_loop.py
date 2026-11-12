import json
from contextlib import asynccontextmanager
from copy import deepcopy
from pathlib import Path

import owlready2 as owl
import pytest
from mcp import Client

from .kernel import (
    Candidate,
    Inventory,
    Policies,
    Query,
    check_owl,
    create_world,
    evaluate,
    load_cases,
    reason,
    validate_candidate,
)
from .run import GeminiModel, ReplayModel, build, load_kernel, run_case, score_run
from .runtime import Runtime, agent_loop, source_servers, unpack


@pytest.fixture
def candidate():
    return Candidate.model_validate_json(Path(__file__).with_name("seed.json").read_text())


@pytest.fixture
def case():
    return deepcopy(load_cases()["held_out"])


def execute(candidate, case):
    return reason(
        candidate,
        Query.model_validate_json(json.dumps(case["query"])),
        Inventory.model_validate_json(json.dumps(case["inventory"])),
        Policies.model_validate_json(json.dumps(case["policies"])),
    )


@asynccontextmanager
async def connected(candidate, case):
    inventory, policies = source_servers(case)
    async with Client(inventory) as left, Client(policies) as right:
        await left.list_tools()
        await right.list_tools()
        runtime = Runtime(
            candidate, Query.model_validate_json(json.dumps(case["query"])), left, right
        )
        async with Client(runtime.server) as client:
            await client.list_tools()
            yield runtime, client


async def read_both(client, case):
    for name in ("inventory__read_inventory", "policies__read_policies"):
        unpack(await client.call_tool(name, {"city": case["query"]["city"]}))


def test_owl_disjointness_is_checked_by_hermit(candidate):
    world, ontology = create_world(candidate)
    try:
        item = ontology.RoomOffer("contradiction")
        item.is_a.append(ontology.Hotel)
        with pytest.raises(ValueError, match="global consistency"):
            check_owl(world)
    finally:
        world.close()


def test_owl_finds_unsatisfiable_restrictions_without_individuals(candidate):
    relation = candidate.relations[0].model_copy(update={"minimum": 2, "maximum": 1})
    broken = candidate.model_copy(update={"relations": (relation, candidate.relations[1])})
    with pytest.raises(ValueError, match="unsatisfiable classes"):
        validate_candidate(broken)


def test_owl_property_domain_conflict(candidate):
    world, ontology = create_world(candidate)
    try:
        offer = ontology.RoomOffer("offer")
        offer.hasPolicy = [ontology.ChildPolicy("policy")]
        with pytest.raises(ValueError, match="global consistency"):
            check_owl(world)
    finally:
        world.close()


def test_owl_cardinality_uses_distinct_targets(candidate):
    world, ontology = create_world(candidate)
    try:
        with ontology:
            left, right = ontology.Hotel("left"), ontology.Hotel("right")
            owl.AllDifferent([left, right])
            ontology.RoomOffer("offer").belongsTo = [left, right]
        with pytest.raises(ValueError, match="global consistency"):
            check_owl(world)
    finally:
        world.close()


def test_missing_policy_is_unknown_not_eligible(candidate, case):
    case["policies"]["policies"] = []
    result = execute(candidate, case)
    assert result["status"] == "incomplete"
    assert result["eligible"] == []
    assert "exact_boundary" in result["missing_links_for"]


def test_conflicting_primary_key_is_rejected(candidate, case):
    conflict = {**case["inventory"]["hotels"][0], "city": "Boston"}
    case["inventory"]["hotels"].append(conflict)
    assert execute(candidate, case)["status"] == "incomplete"


def test_function_follows_linked_policy(candidate, case):
    case["policies"]["policies"].append({"id": "adult", "minimum_child_age": 18})
    case["inventory"]["hotels"][0]["policy_id"] = "adult"
    assert execute(candidate, case)["eligible"] == []


def test_training_detects_missing_computation(candidate):
    broken = candidate.model_copy(
        update={
            "program": candidate.program.model_copy(
                update={
                    "filters": tuple(
                        p
                        for p in candidate.program.filters
                        if p.left.name != "policy.minimum_child_age"
                    )
                }
            )
        }
    )
    failures = evaluate(broken, load_cases()["training"])
    assert failures[0]["case"] == "child_policy_and_city"
    assert "cheap_adult_room" in failures[0]["actual"]


async def test_mcp_loop_passes_held_out_boundary(candidate, case):
    result = await run_case(ReplayModel(), candidate, case)
    assert score_run(result, case)
    assert result["mode"] == "scripted_replay"
    assert len(result["trace"]) == 4
    match = result["answer"]["eligible"][0]
    assert match["total_cents"] == 50000
    assert match["relations"][1] == ["eight_plus", "hasPolicy", "age_eight"]


async def test_changed_request_cannot_relax_the_budget(candidate, case):
    async with connected(candidate, case) as (_, client):
        await read_both(client, case)
        changed = {**case["query"], "budget_cents": 999999}
        result = await client.call_tool("eligible_stays", {"request": changed})
        assert result.is_error
        assert "original request" in result.content[0].text


async def test_receipts_require_current_function_evidence(candidate, case):
    async with connected(candidate, case) as (_, client):
        assert (await client.call_tool("submit_answer", {"receipt": "invented"})).is_error
        assert (await client.call_tool("eligible_stays", {"request": case["query"]})).is_error
        await read_both(client, case)
        computed = unpack(await client.call_tool("eligible_stays", {"request": case["query"]}))
        await client.call_tool("inventory__read_inventory", {"city": case["query"]["city"]})
        assert (await client.call_tool("submit_answer", {"receipt": computed["receipt"]})).is_error


async def test_ungrounded_text_cannot_complete(candidate, case):
    class TextOnly:
        async def turn(self, prompt, history, tools):
            return [{"role": "assistant", "content": "Book the adult-only room."}]

    async with connected(candidate, case) as (runtime, _):
        result = await agent_loop(TextOnly(), runtime, max_steps=2)
        assert result["answer"] is None
        assert len(result["trace"]) == 2


async def test_ungranted_tool_cannot_execute(candidate, case):
    class Ungranted:
        async def turn(self, prompt, history, tools):
            return [
                {
                    "type": "function_call",
                    "name": "book_any_room",
                    "call_id": "x",
                    "arguments": "{}",
                }
            ]

    async with connected(candidate, case) as (runtime, _):
        result = await agent_loop(Ungranted(), runtime, max_steps=1)
        assert result["answer"] is None
        assert "not granted" in result["trace"][0]["observation"]["error"]


async def test_construction_repairs_before_freezing(candidate, tmp_path):
    class Repairing(ReplayModel):
        def __init__(self):
            self.feedback = []

        async def propose(self, cases, feedback):
            self.feedback.append(deepcopy(feedback))
            if len(self.feedback) == 1:
                return candidate.model_copy(
                    update={
                        "program": candidate.program.model_copy(
                            update={
                                "filters": tuple(
                                    p
                                    for p in candidate.program.filters
                                    if p.left.name != "offer.capacity"
                                )
                            }
                        )
                    }
                )
            return candidate

    model = Repairing()
    await build(model, tmp_path, max_rounds=2)
    assert model.feedback[1]
    assert load_kernel(tmp_path) == candidate
    assert (tmp_path / "schema.owl").is_file()
    saved = json.loads((tmp_path / "kernel.json").read_text())
    saved["program"]["filters"].pop()
    (tmp_path / "kernel.json").write_text(json.dumps(saved))
    with pytest.raises(ValueError, match="changed after validation"):
        load_kernel(tmp_path)


async def test_cli_adapter_transports_catalog_and_action(tmp_path, monkeypatch):
    executable = tmp_path / "test-gemini"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "request = json.load(sys.stdin)\n"
        "assert request['tools'][0]['name'] == 'example_read'\n"
        "assert '--skip-trust' in sys.argv\n"
        "settings = json.loads(Path('.gemini/settings.json').read_text())\n"
        "assert settings['security']['auth']['selectedType'] == 'vertex-ai'\n"
        "assert os.environ['GOOGLE_CLOUD_PROJECT'] == 'test-project'\n"
        "assert os.environ['GOOGLE_CLOUD_LOCATION'] == 'global'\n"
        "assert os.environ['GEMINI_CLI_AUTH_OVERRIDE'] == 'vertex-ai'\n"
        "assert os.environ['GEMINI_CLI_TRUST_WORKSPACE'] == 'true'\n"
        "assert 'GEMINI_CLI_SYSTEM_SETTINGS_PATH' not in os.environ\n"
        "print(json.dumps({'response': json.dumps({'name': 'example_read', "
        "'arguments': {'city': 'Newark'}}), 'stats': {'test_double': True}}))\n"
    )
    executable.chmod(0o700)
    monkeypatch.setenv("OAK_GEMINI_CLI", str(executable))
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"auth_type": "vertex-ai", "project": "test-project"}))
    monkeypatch.setenv("OAK_GEMINI_PROFILE", str(profile))
    for key in ("GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "GEMINI_CLI_SYSTEM_SETTINGS_PATH"):
        monkeypatch.delenv(key, raising=False)
    model = GeminiModel(tmp_path)
    output = await model.turn("Read the fixture.", [], [{"name": "example_read"}])
    assert output[0]["name"] == "example_read"
    assert json.loads(output[0]["arguments"]) == {"city": "Newark"}
    settings = json.loads(model.settings.read_text())
    assert settings["admin"]["mcp"]["enabled"] is False
    assert settings["tools"]["core"] == ["__oak_no_native_tools__"]


async def test_invalid_model_json_can_recover(candidate, case):
    class InvalidFirst(ReplayModel):
        first = True

        async def turn(self, prompt, history, tools):
            if self.first:
                self.first = False
                raise ValueError("Invalid JSON.")
            return await super().turn(prompt, history, tools)

    result = await run_case(InvalidFirst(), candidate, case)
    assert score_run(result, case)
    assert result["trace"][0]["model_output_error"] == "Invalid JSON."
