"""Check joint exploration, modeling decisions, and the final handoff."""

import asyncio
from copy import deepcopy
from threading import Event

import httpx
import pytest

from oak.discovery_modeling import (
    DiscoveryRound,
    ModelingChoice,
    check_modeling_references,
    modeling_errors,
)
from oak.discovery_schemas import RelationProposal, SchemaProposal
from tests.discovery_model import DiscoveryModel
from tests.test_discovery import discovery as discovery_fixture
from tests.test_discovery import resume, start, wait

discovery = discovery_fixture


def sample_round():
    data = {
        "inputs": {"source_sections": ["/agent/responsibilities"]},
        "artifacts": [
            {
                "id": "catalog",
                "kind": "catalog",
                "payload": {
                    "tools": [
                        {"id": "read", "name": "list_notes"},
                        {"id": "write", "name": "create_note"},
                    ]
                },
            },
            {
                "id": "observation",
                "kind": "observation",
                "payload": {
                    "tool_id": "read",
                    "data": {"items": [{"id": "n1", "title": "Note"}]},
                },
            },
        ],
        "clarifications": [],
        "resume_requires_fresh_reads": False,
    }
    return DiscoveryRound.model_validate(DiscoveryModel()._value(data, DiscoveryRound))


@pytest.mark.parametrize(
    "change, expected",
    [
        (lambda p: p.schema_proposal.entities[0].identity_keys.clear(), "identity fields"),
        (lambda p: setattr(p.choices[0], "identity_scope", None), "source scope"),
        (lambda p: p.schema_proposal.bindings.clear(), "source binding"),
        (lambda p: p.choices.pop(), "modeling explanation"),
        (lambda p: p.choices[0].unresolved.append("Unknown scope"), "unresolved assumptions"),
        (
            lambda p: setattr(p.schema_proposal.entities[0].properties[0], "type", "object"),
            "unsupported type",
        ),
        (lambda p: p.function_needs[0].outputs.clear(), "typed output"),
    ],
)
def test_incomplete_choices_cannot_be_ready(change, expected):
    proposal = sample_round()
    assert not modeling_errors(proposal)
    change(proposal)
    assert any(expected in error for error in modeling_errors(proposal))


def test_probe_requires_a_known_question_and_function_dependencies():
    proposal = sample_round()
    check_modeling_references(proposal)
    proposal.probe_question.targets[0].id = "missing"
    with pytest.raises(ValueError, match="unknown requirement or modeling target"):
        check_modeling_references(proposal)
    proposal = sample_round()
    proposal.function_needs[0].dependencies[0].property = "invented"
    with pytest.raises(ValueError, match="unknown evidence dependency"):
        check_modeling_references(proposal)
    raw = sample_round().model_dump(mode="json")
    raw["probe_question"] = None
    with pytest.raises(ValueError, match="modeling question"):
        DiscoveryRound.model_validate(raw)


def test_function_needs_never_become_executable_schema_fields():
    proposal = sample_round()
    before = proposal.schema_proposal.model_dump(mode="json")
    proposal.choices[0].reason = "An updated explanation."
    proposal.function_needs[0].missing_evidence = "Obtain the missing field."
    assert proposal.schema_proposal.model_dump(mode="json") == before
    assert SchemaProposal.model_validate(before).model_dump(mode="json") == before
    assert not {"choices", "function_needs", "steps"} & before.keys()


def test_relations_require_connection_reasons_and_matching_endpoint_types():
    proposal = sample_round()
    proposal.schema_proposal.relations.append(
        RelationProposal(
            id="same_note",
            name="Same source note",
            from_entity="note",
            to_entity="note",
            from_property="id",
            to_property="id",
            requirement_ids=["R1"],
            binding_ids=["note-id", "note-id"],
        )
    )
    assert any("connection rule" in e for e in modeling_errors(proposal))
    proposal.choices.append(
        ModelingChoice(
            target={"kind": "relation", "id": "same_note"},
            requirement_ids=["R1"],
            purpose="Match repeated observations of a note.",
            reason="The source returns the same scoped identifier.",
            evidence=proposal.choices[1].evidence,
            connection_rule="Match the identifier within the same source and workspace.",
        )
    )
    assert not modeling_errors(proposal)
    proposal.schema_proposal.relations[0].to_property = "title"
    proposal.schema_proposal.entities[0].properties[1].type = "integer"
    assert any("matching scalar endpoint types" in e for e in modeling_errors(proposal))


class RevisedFinishModel(DiscoveryModel):
    def _value(self, data, response_schema):
        value = super()._value(data, response_schema)
        if response_schema is DiscoveryRound and value["action"] == "finish":
            previous = data.get("current_draft")
            if previous["proposal"]["action"] != "finish":
                value["schema_proposal"]["entities"][0]["identity_keys"] = []
                value["summary"] = "Request a check of an incomplete identity declaration."
            else:
                assert any("identity fields" in e for e in previous["findings"]["errors"])
                value["summary"] = "Restore the identity from saved evidence."
        return value


def test_failed_finish_returns_to_revision_and_publishes_one_pair(discovery, settings, mcp_server):
    import psycopg

    discovery[2].model = RevisedFinishModel()
    paused = wait(discovery, start(discovery)["run"]["id"])
    assert paused["requirements"] and paused["schema_proposal"]
    assert not any(a["kind"] in {"requirements", "schema"} for a in paused["artifacts"])
    resume(discovery, paused)
    final = wait(discovery, paused["run"]["id"])
    assert final["run"]["reason"] == "ready"
    drafts = [a for a in final["artifacts"] if a["kind"] == "draft"]
    assert drafts[-2]["payload"]["findings"]["errors"]
    assert not drafts[-1]["payload"]["findings"]["errors"]
    published = [a for a in final["artifacts"] if a["kind"] in {"requirements", "schema"}]
    assert len(published) == 2
    assert published[0]["created_at"] == published[1]["created_at"]
    assert final["schema_proposal"] == drafts[-1]["payload"]["proposal"]["schema_proposal"]
    with psycopg.connect(settings.database_url) as db:
        checkpoint = db.execute(
            "SELECT checkpoint FROM discovery_runs WHERE id=%s", (final["run"]["id"],)
        ).fetchone()[0]
    assert checkpoint["published"]["draft_id"] == drafts[-1]["id"]
    assert set(checkpoint["published"].values()) == {
        drafts[-1]["id"],
        *(a["id"] for a in published),
    }
    calls = httpx.get(mcp_server + "/probe-state").json()["calls"]
    assert calls.count("create_note") == 1


class GapsModel(DiscoveryModel):
    def _value(self, data, response_schema):
        value = super()._value(data, response_schema)
        if response_schema is DiscoveryRound:
            value.update(action="finish_gaps", probe=None, probe_question=None, questions=[])
            value["summary"] = "The required identity source is unavailable."
        return value


def test_finish_with_gaps_preserves_draft_and_blocks_training(discovery):
    client, path, manager, tools = discovery
    manager.model = GapsModel()
    result = wait(discovery, start(discovery)["run"]["id"])
    assert result["run"]["status"] == "completed"
    assert result["run"]["reason"] == "gaps"
    assert result["run"]["mcp_calls"] == 0
    assert result["schema_proposal"]["entities"][0]["identity_keys"] == []
    training = path.removesuffix("discovery") + "training"
    client.post(
        training + "/cases",
        json={
            "query": "Inspect notes.",
            "tool_ids": [tools[0]["id"]],
            "task_success": "The response lists the observed notes.",
        },
    )
    assert not client.get(training).json()["ready"]


class BlockedFinishModel(GapsModel):
    def _value(self, data, response_schema):
        value = super()._value(data, response_schema)
        if response_schema is DiscoveryRound:
            value["action"] = "finish"
        return value


def test_repeated_incomplete_finish_obeys_existing_model_limit(discovery):
    discovery[2].model = BlockedFinishModel()
    result = wait(discovery, start(discovery, model_calls=2)["run"]["id"])
    assert result["run"]["reason"] == "model_calls"
    assert result["run"]["status"] == "paused"
    assert result["run"]["mcp_calls"] == 0
    assert len([a for a in result["artifacts"] if a["kind"] == "draft"]) == 2
    assert not any(a["kind"] in {"requirements", "schema"} for a in result["artifacts"])


def test_function_dependency_guides_probe_and_draft_survives_pause(discovery):
    client, path, _, _ = discovery
    paused = wait(discovery, start(discovery, mcp_calls=1)["run"]["id"])
    assert paused["run"]["reason"] == "mcp_calls"
    drafts = [a["payload"] for a in paused["artifacts"] if a["kind"] == "draft"]
    first, second = drafts[:2]
    assert first["proposal"]["schema_proposal"]["entities"][0]["identity_keys"] == []
    assert second["proposal"]["schema_proposal"]["entities"][0]["identity_keys"] == ["id"]
    assert first["proposal"]["probe_question"]["targets"][0]["id"] == "note_fields"
    before = deepcopy(paused)
    assert client.get(path + f"/runs/{paused['run']['id']}").json() == before
    resume(discovery, paused, limits={**paused["run"]["limits"], "mcp_calls": 12})
    resumed = wait(discovery, paused["run"]["id"])
    assert resumed["run"]["mcp_calls"] >= paused["run"]["mcp_calls"]
    assert next(a for a in resumed["artifacts"] if a["kind"] == "draft")["payload"] == first


class PromotingModel(DiscoveryModel):
    def _value(self, data, response_schema):
        value = super()._value(data, response_schema)
        if response_schema is DiscoveryRound and not any(
            a["kind"] == "observation" for a in data["artifacts"]
        ):
            value["summary"] = "Investigate whether a note needs its own identity."
            value["schema_proposal"]["entities"] = [
                {
                    "id": "workspace",
                    "name": "Workspace",
                    "identity_keys": [],
                    "properties": [{"name": "note", "type": "string"}],
                    "requirement_ids": ["R1"],
                }
            ]
            entity, prop = deepcopy(value["choices"][:2])
            entity["target"] = {"kind": "entity", "id": "workspace"}
            entity["reason"] = "Check whether notes are values in a workspace."
            prop["target"] = {"kind": "property", "id": "workspace", "property": "note"}
            prop["unresolved"] = ["Determine whether each note has a source identifier."]
            value["choices"] = [entity, prop, value["choices"][-1]]
            value["function_needs"][0]["dependencies"] = [deepcopy(prop["target"])]
            value["probe_question"]["question"] = prop["unresolved"][0]
        return value


def test_observation_promotes_property_to_entity_and_updates_dependencies(discovery):
    discovery[2].model = PromotingModel()
    result = wait(discovery, start(discovery)["run"]["id"])
    drafts = [a["payload"]["proposal"] for a in result["artifacts"] if a["kind"] == "draft"]
    first, second = drafts[:2]
    assert first["schema_proposal"]["entities"][0]["id"] == "workspace"
    assert first["schema_proposal"]["entities"][0]["properties"][0]["name"] == "note"
    assert second["schema_proposal"]["entities"][0]["id"] == "note"
    assert second["schema_proposal"]["entities"][0]["identity_keys"] == ["id"]
    assert all(d["id"] == "note" for d in second["function_needs"][0]["dependencies"])
    assert all(c["target"]["id"] != "workspace" for c in second["choices"])
    observation_ids = {a["id"] for a in result["artifacts"] if a["kind"] == "observation"}
    assert all(b["source"]["id"] in observation_ids for b in second["schema_proposal"]["bindings"])


class DraftEvidenceModel(DiscoveryModel):
    def _value(self, data, response_schema):
        value = super()._value(data, response_schema)
        if response_schema is DiscoveryRound and data.get("current_draft"):
            value["choices"][0]["evidence"] = [
                {
                    "source": "artifact",
                    "id": data["current_draft"]["proposal_id"],
                    "path": "",
                }
            ]
        return value


def test_a_draft_cannot_supply_source_evidence_for_the_next_probe(discovery, mcp_server):
    discovery[2].model = DraftEvidenceModel()
    result = wait(discovery, start(discovery)["run"]["id"])
    assert result["run"]["status"] == "stopped"
    assert result["run"]["mcp_calls"] == 1
    assert "source evidence" in result["run"]["message"]
    assert "create_note" not in httpx.get(mcp_server + "/probe-state").json()["calls"]


class HeldRoundModel(DiscoveryModel):
    def __init__(self):
        super().__init__()
        self.started, self.release = Event(), Event()

    async def generate(self, instructions, data, response_schema, **kwargs):
        result = await super().generate(instructions, data, response_schema, **kwargs)
        if response_schema is DiscoveryRound and not self.started.is_set():
            self.started.set()
            while not self.release.is_set():
                await asyncio.sleep(0.01)
        return result


@pytest.mark.parametrize("action, expected", [("pause", "paused"), ("stop", "stopped")])
def test_control_during_model_output_commits_before_draft_save(discovery, action, expected):
    client, path, manager, _ = discovery
    manager.model = HeldRoundModel()
    run_id = start(discovery)["run"]["id"]
    assert manager.model.started.wait(5)
    try:
        response = client.post(path + f"/runs/{run_id}/{action}")
        assert response.status_code == 202
    finally:
        manager.model.release.set()
    result = wait(discovery, run_id)
    assert result["run"]["status"] == expected
    assert result["run"]["mcp_calls"] == 0
    assert not any(a["kind"] == "draft" for a in result["artifacts"])
