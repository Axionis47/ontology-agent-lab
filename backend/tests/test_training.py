import time
from uuid import uuid4

import httpx
import psycopg
import pytest

from tests.test_discovery import discovery, resume, start, wait  # noqa: F401
from tests.training_model import TrainingModel, find_rows, prepare_training_environment


@pytest.fixture
def training(discovery):  # noqa: F811
    client, path, _, tools = discovery
    detail = wait(discovery, start(discovery)["run"]["id"])
    resume(discovery, detail)
    completed = wait(discovery, detail["run"]["id"])
    assert completed["run"]["reason"] == "ready"
    manager = client.app.state.training
    manager.model = TrainingModel()
    manager.prepare_environment = prepare_training_environment
    path = path.removesuffix("discovery") + "training"
    tool_ids = [t["id"] for t in tools if t["name"] in {"list_notes", "create_note"}]
    for title in ("First sample", "Second sample"):
        response = client.post(
            path + "/cases",
            json={
                "query": f"Create a note named {title} and return its identifier and title.",
                "tool_ids": tool_ids,
                "task_success": f"The note {title} exists and the answer gives its identifier and title.",
            },
        )
        assert response.status_code == 201, response.text
    return client, path, manager, tool_ids


def launch(training, **limits):
    client, path, *_ = training
    body = {"request_id": str(uuid4()), "limits": {"cost_usd": "2", "model_calls": 100, **limits}}
    response = client.post(path + "/runs", json=body)
    assert response.status_code == 202, response.text
    return response.json(), body


def settled(training, run_id):
    client, path, *_ = training
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        response = client.get(path + f"/runs/{run_id}")
        assert response.status_code == 200, response.text
        detail = response.json()
        if detail["run"]["status"] not in {"running", "stopping"}:
            return detail
        time.sleep(0.03)
    pytest.fail(f"Training did not settle: {detail['run']}")


def test_all_cases_native_harness_persistence_and_fixed_inference(training):
    client, path, manager, tool_ids = training
    detail = settled(training, launch(training)[0]["run"]["id"])
    assert detail["run"]["status"] == "completed", detail["run"]
    assert detail["run"]["accepted_candidate_id"], detail
    assert len(detail["episodes"]) == 4
    assert {e["stage"] for e in detail["episodes"]} == {"baseline", "harness"}
    assert all(e["evaluation"]["status"] == "passed" for e in detail["episodes"])
    assert all(e["environment_ref"] == "fixture:notes:v1" for e in detail["episodes"])
    harness = [e for e in detail["episodes"] if e["stage"] == "harness"]
    assert all(
        set(e["result"]["function_ids"]) == {"observed_notes", "check_read", "check_write"}
        for e in harness
    )
    overview = client.get(path).json()
    assert overview["inference_ready"] is True
    assert set(overview["inference_tool_ids"]) == set(tool_ids)
    assert all(e["result"]["dispatch_decisions"] for e in harness)
    assert any(e["kind"] == "call_dispatched" for e in detail["events"])
    before = manager.model.calls
    assert client.get(path + f"/runs/{detail['run']['id']}").json() == detail
    assert manager.model.calls == before
    first_sequence = detail["events"][0]["sequence"]
    events = client.get(path + f"/runs/{detail['run']['id']}/events?after={first_sequence}").json()
    assert all(e["sequence"] > first_sequence for e in events)
    accepted = client.get(path).json()["accepted_candidate"]
    inference = client.post(
        path + "/inference",
        json={
            "request_id": str(uuid4()),
            "query": "Create a note named New query and return its identifier and title.",
            "tool_ids": tool_ids,
            "limits": {"cost_usd": "1"},
        },
    )
    assert inference.status_code == 202, inference.text
    result = settled(training, inference.json()["run"]["id"])
    assert result["episodes"][0]["evaluation"] is None
    assert result["episodes"][0]["environment_ref"] == "current-state"
    assert "New query" in result["episodes"][0]["result"]["final_output"]
    assert client.get(path).json()["accepted_candidate"]["digest"] == accepted["digest"]
    assert [c["id"] for c in result["candidates"]] == [accepted["id"]]
    assert result["candidates"][0]["payload"] == accepted["payload"]
    newer = settled(training, launch(training)[0]["run"]["id"])
    assert newer["run"]["accepted_candidate_id"] != accepted["id"]
    saved = client.get(path + f"/runs/{result['run']['id']}").json()
    assert [c["id"] for c in saved["candidates"]] == [accepted["id"]]
    assert saved["candidates"][0]["payload"] == accepted["payload"]


def test_targeted_repair_preserves_case_passes(training):
    training[2].model.mode = "repair"
    detail = settled(training, launch(training)[0]["run"]["id"])
    assert detail["run"]["accepted_candidate_id"], detail["run"]
    assert len(detail["candidates"]) == 2
    assert detail["candidates"][0]["status"] == "rejected"
    assert detail["candidates"][1]["status"] == "accepted"
    patch = detail["candidates"][1]["patch"]
    assert len(patch["changes"]) == 1
    assert patch["base_digest"] == detail["candidates"][0]["digest"]
    assert len(detail["episodes"]) == 6


def test_cases_access_grants_and_immutable_run_snapshot(training):
    client, path, manager, tool_ids = training
    manager.model.delay = 0.1
    detail, body = launch(training)
    run_id = detail["run"]["id"]
    duplicate = client.post(path + "/runs", json=body)
    assert duplicate.json()["run"]["id"] == run_id
    conflict = client.post(path + "/runs", json={**body, "limits": {"cost_usd": "1"}})
    assert conflict.status_code == 409
    case = client.get(path).json()["cases"][0]
    original = detail["run"]["cases"][0]["query"]
    assert (
        client.put(
            path + f"/cases/{case['id']}",
            json={
                "query": "Edited after Start",
                "tool_ids": tool_ids,
                "task_success": "An edited result",
            },
        ).status_code
        == 200
    )
    assert client.get(path + f"/runs/{run_id}").json()["run"]["cases"][0]["query"] == original
    assert client.get(path, headers={"X-Oak-User": "demo-sam"}).status_code == 404
    assert (
        client.get(path + f"/runs/{run_id}", headers={"X-Oak-User": "demo-sam"}).status_code == 404
    )
    invalid = client.post(
        path + "/cases",
        json={
            "query": "Read",
            "tool_ids": [str(uuid4())],
            "task_success": "Read done",
        },
    )
    assert invalid.status_code == 422
    client.post(path + f"/runs/{run_id}/stop")
    settled(training, run_id)


def test_stop_and_get_do_not_repeat_dispatch(training, mcp_server):
    client, path, manager, _ = training
    manager.model.delay = 0.4
    run_id = launch(training)[0]["run"]["id"]
    client.post(path + f"/runs/{run_id}/stop")
    detail = settled(training, run_id)
    assert detail["run"]["status"] == "stopped"
    before = httpx.get(mcp_server + "/probe-state").json()
    for _ in range(3):
        client.get(path)
        client.get(path + f"/runs/{run_id}")
    assert httpx.get(mcp_server + "/probe-state").json() == before
    assert not any(e["status"] in {"running", "evaluating"} for e in detail["episodes"])


def test_unprepared_repeat_dispatches_no_calls(training):
    client, path, manager, _ = training
    manager.prepare_environment = None
    detail = settled(training, launch(training)[0]["run"]["id"])
    assert detail["run"]["status"] == "stopped", detail["run"]
    assert "prepared environment" in detail["run"]["message"]
    blocked = [e for e in detail["episodes"] if e["status"] == "blocked"]
    assert len(blocked) == 1
    assert blocked[0]["evaluation"] is None
    assert not any(
        e["episode_id"] == blocked[0]["id"] and e["kind"] == "call_dispatched"
        for e in detail["events"]
    )


def test_model_budget_stops_before_dispatch(training):
    detail = settled(training, launch(training, cost_usd="0.001")[0]["run"]["id"])
    assert detail["run"]["status"] == "stopped", detail["run"]
    assert detail["run"]["model_calls"] == 0
    assert detail["run"]["mcp_calls"] == 0


def test_restart_preserves_unknown_calls_without_replay(training, settings):
    client, path, manager, _ = training
    manager.model.delay = 0.5
    run_id = launch(training)[0]["run"]["id"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if client.get(path + f"/runs/{run_id}").json()["run"]["model_calls"]:
            break
        time.sleep(0.02)
    client.post(path + f"/runs/{run_id}/stop")
    settled(training, run_id)
    with psycopg.connect(settings.database_url) as db:
        calls = db.execute(
            "SELECT status FROM training_calls WHERE run_id=%s", (run_id,)
        ).fetchall()
    assert calls and calls[0][0] == "unknown"
    before = manager.model.calls
    with psycopg.connect(settings.database_url) as db:
        db.execute("UPDATE training_runs SET status='running' WHERE id=%s", (run_id,))
        db.execute("UPDATE training_calls SET status='dispatched' WHERE run_id=%s", (run_id,))
    client.portal.call(manager.recover_interrupted)
    recovered = client.get(path + f"/runs/{run_id}").json()
    assert recovered["run"]["status"] == "interrupted"
    assert manager.model.calls == before
    with psycopg.connect(settings.database_url) as db:
        assert (
            db.execute(
                "SELECT count(*) FROM training_calls WHERE run_id=%s AND status='dispatched'",
                (run_id,),
            ).fetchone()[0]
            == 0
        )


def test_unknown_action_stops_before_any_repeat(training, mcp_server):
    _, _, manager, _ = training

    async def prepare(run, case, episode_index):
        async with httpx.AsyncClient() as transport:
            response = await transport.post(mcp_server + "/probe-reset?mode=timeout")
            response.raise_for_status()
        return "fixture:timeout:v1"

    manager.prepare_environment = prepare
    manager.settings = manager.settings.model_copy(update={"surface_tool_timeout": 0.25})
    detail = settled(training, launch(training)[0]["run"]["id"])
    assert detail["run"]["status"] == "stopped", detail["run"]
    assert len(detail["episodes"]) == 1
    assert detail["episodes"][0]["evaluation"]["status"] == "inconclusive"
    assert detail["episodes"][0]["result"]["unresolved_outcomes"]
    assert httpx.get(mcp_server + "/probe-state").json()["calls"].count("create_note") == 1


def test_grant_change_stops_before_tool_dispatch(training):
    client, path, manager, _ = training
    manager.model.delay = 0.3
    run_id = launch(training)[0]["run"]["id"]
    response = client.put(path.removesuffix("/training") + "/tools", json={"tool_ids": []})
    assert response.status_code == 200
    detail = settled(training, run_id)
    assert detail["run"]["status"] == "stopped", detail["run"]
    assert detail["run"]["mcp_calls"] == 0
    assert not detail["run"]["accepted_candidate_id"]


def test_discovery_and_training_cannot_dispatch_concurrently(training):
    client, path, manager, _ = training
    discovery_path = path.removesuffix("training") + "discovery"
    discoveries = client.app.state.discoveries
    discovery_context = (client, discovery_path, discoveries, [])
    manager.model.delay = 0.4
    run_id = launch(training)[0]["run"]["id"]
    blocked = client.post(
        discovery_path + "/runs",
        json={
            "request_id": str(uuid4()),
            "environment": "Controlled test world",
            "limits": {"cost_usd": "1"},
        },
    )
    assert blocked.status_code == 409
    assert "training" in blocked.json()["detail"]
    client.post(path + f"/runs/{run_id}/stop")
    settled(training, run_id)

    discoveries.model.delay = 0.2
    discovery_run = start(discovery_context)
    blocked = client.post(path + "/runs", json={"request_id": str(uuid4())})
    assert blocked.status_code == 409
    assert "discovery" in blocked.json()["detail"]
    paused = wait(discovery_context, discovery_run["run"]["id"])
    assert paused["run"]["status"] == "paused"
    run_id = launch(training)[0]["run"]["id"]
    blocked = client.post(
        discovery_path + f"/runs/{paused['run']['id']}/resume",
        json={
            "request_id": str(uuid4()),
            "expected_revision": paused["run"]["revision"],
            "answers": {
                q["id"]: "Billing contact" for q in paused["questions"] if q["answer"] is None
            },
        },
    )
    assert blocked.status_code == 409
    assert "training" in blocked.json()["detail"]
    client.post(path + f"/runs/{run_id}/stop")
    settled(training, run_id)


def test_write_response_updates_graph_but_cannot_authorize_changed_arguments(training, mcp_server):
    client, path, manager, tool_ids = training
    trained = settled(training, launch(training)[0]["run"]["id"])
    assert trained["run"]["accepted_candidate_id"], trained["run"]
    accepted = client.get(path).json()["accepted_candidate"]

    class FollowupModel(TrainingModel):
        async def turn(self, messages, tools, *, limits, instructions):
            replies = [
                part["function_response"]
                for message in messages
                for part in message.get("parts", [])
                if "function_response" in part
            ]
            write = next(t for t in tools if "Create a note" in t.get("description", ""))
            write_count = sum(r["name"] == write["name"] for r in replies)
            if replies and write_count < 2:
                self.calls += 1
                arguments = {"title": "Different title" if write_count == 0 else "Reference seed"}
                call_id = "invalid-title" if write_count == 0 else "corrected-title"
                return {
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "function_call": {
                                    "id": call_id,
                                    "name": write["name"],
                                    "args": arguments,
                                }
                            }
                        ],
                    },
                    "text": "",
                    "tool_calls": [
                        {"id": call_id, "name": write["name"], "arguments": arguments, "index": 0}
                    ],
                    "usage": self.usage().model_dump(),
                    "model": "scripted-training-model",
                    "duration_ms": 0,
                }
            return await super().turn(messages, tools, limits=limits, instructions=instructions)

    manager.model = FollowupModel()
    before = httpx.get(mcp_server + "/probe-state").json()["calls"]
    response = client.post(
        path + "/inference",
        json={
            "request_id": str(uuid4()),
            "accepted_candidate_id": accepted["id"],
            "query": "Create a note named Reference seed and return its identifier and title.",
            "tool_ids": tool_ids,
            "limits": {"cost_usd": "1"},
        },
    )
    assert response.status_code == 202, response.text
    detail = settled(training, response.json()["run"]["id"])
    result = detail["episodes"][0]["result"]
    assert result["status"] == "complete", result
    graph_result = next(
        call["result"]
        for call in result["function_calls"]
        if call["function_id"] == "observed_notes"
    )
    first_id = next(find_rows(graph_result))["id"]
    writes = [o for o in result["observations"] if "title" in o["arguments"]]
    assert len(writes) == 1
    assert writes[0]["data"]["id"] == first_id
    rejected = [d for d in result["dispatch_decisions"] if d["status"] == "rejected"]
    assert len(rejected) == 1
    assert [d["status"] for d in result["dispatch_decisions"]] == ["allowed", "rejected", "allowed"]
    assert any(
        c["condition_id"] == "requested-title" and c["value"] == "false"
        for c in rejected[0]["conditions"]
    )
    assert result["request_snapshot"]["values"]["title"] == "Reference seed"
    graph_ids = {record["values"]["id"] for record in result["graph"]["entities"]["note"]}
    assert graph_ids >= {w["data"]["id"] for w in writes}
    assert httpx.get(mcp_server + "/probe-state").json()["calls"][len(before) :] == [
        "list_notes",
        "create_note",
    ]
    assert client.get(path).json()["accepted_candidate"]["digest"] == accepted["digest"]
    manager.model = TrainingModel()
    next_query = client.post(
        path + "/inference",
        json={
            "request_id": str(uuid4()),
            "accepted_candidate_id": accepted["id"],
            "query": "Create a note named Another query and return its identifier and title.",
            "tool_ids": tool_ids,
            "limits": {"cost_usd": "1"},
        },
    )
    assert next_query.status_code == 202, next_query.text
    next_result = settled(training, next_query.json()["run"]["id"])["episodes"][0]["result"]
    assert "Another query" in next_result["final_output"]
    assert client.get(path).json()["accepted_candidate"]["digest"] == accepted["digest"]
