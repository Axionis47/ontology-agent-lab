import time
from uuid import uuid4

import httpx
import psycopg
import pytest
from psycopg.types.json import Jsonb

from oak.discovery_validation import digest, redact, validate_json
from tests.discovery_model import DiscoveryModel


@pytest.fixture
def discovery(client, mcp_server):
    httpx.post(f"{mcp_server}/probe-reset")
    manager = client.app.state.discoveries
    manager.settings = manager.settings.model_copy(update={"gemini_project": "test-project"})
    manager.model = DiscoveryModel()
    task = client.post(
        "/api/tasks",
        json={
            "name": "Discovery",
            "objective": "Inspect notes and create one test note. Do not delete notes.",
        },
    ).json()
    base = f"/api/tasks/{task['id']}"
    connection = client.post(
        base + "/connections",
        json={"name": "Supplied test world", "url": f"{mcp_server}/discovery/mcp"},
    ).json()
    assert (
        client.post(base + f"/connections/{connection['id']}/refresh").json()["status"]
        == "connected"
    )
    tools = client.get(base + "/tools").json()
    agent = client.post(
        base + "/agents",
        json={
            "name": "Discoverer",
            "responsibilities": "Inspect notes and create only a test note. Do not delete notes.",
            "tool_ids": [t["id"] for t in tools if t["name"] != "search"],
        },
    ).json()
    path = base + f"/agents/{agent['id']}/discovery"
    return client, path, manager, tools


def start(discovery, **limits):
    client, path, *_ = discovery
    response = client.post(
        path + "/runs",
        json={
            "request_id": str(uuid4()),
            "environment": "Supplied test world",
            "limits": {"cost_usd": "1", **limits},
        },
    )
    assert response.status_code == 202, response.text
    return response.json()


def wait(discovery, run_id, statuses=("paused", "completed", "stopped")):
    client, path, *_ = discovery
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        response = client.get(path + f"/runs/{run_id}")
        assert response.status_code == 200, response.text
        detail = response.json()
        if detail["run"]["status"] in statuses:
            return detail
        time.sleep(0.03)
    pytest.fail(f"Discovery did not settle: {detail['run']}")


def resume(discovery, detail, **kwargs):
    client, path, *_ = discovery
    body = {
        "request_id": str(uuid4()),
        "expected_revision": detail["run"]["revision"],
        "answers": {q["id"]: "Billing contact" for q in detail["questions"] if q["answer"] is None},
        **kwargs,
    }
    response = client.post(path + f"/runs/{detail['run']['id']}/resume", json=body)
    assert response.status_code == 202, response.text
    return body, response.json()


def test_complete_discovery_clarification_resume_and_no_write_replay(discovery, mcp_server):
    client, path, manager, _ = discovery
    detail = wait(discovery, start(discovery)["run"]["id"])
    assert detail["run"]["reason"] == "questions"
    assert detail["run"]["mcp_calls"] == 3
    before = httpx.get(f"{mcp_server}/probe-state").json()
    assert before["calls"].count("create_note") == 1
    model_calls = manager.model.calls
    time.sleep(0.1)
    client.get(path)
    client.get(path + f"/runs/{detail['run']['id']}")
    assert manager.model.calls == model_calls
    body, _ = resume(discovery, detail)
    duplicate = client.post(path + f"/runs/{detail['run']['id']}/resume", json=body)
    assert duplicate.status_code == 202
    result = wait(discovery, detail["run"]["id"])
    assert result["run"]["status"] == "completed", result["run"]
    assert result["run"]["reason"] == "ready", result["artifacts"][-1]
    assert result["run"]["mcp_calls"] == 3
    assert result["questions"][0]["answered_by"] == "demo-alex"
    assert httpx.get(f"{mcp_server}/probe-state").json()["calls"].count("create_note") == 1
    assert result["schema_proposal"]["bindings"][0]["support"] == "observed"
    configuration = next(a for a in result["artifacts"] if a["kind"] == "model_configuration")
    assert configuration["payload"] == manager.model_configuration
    assert configuration["digest"] == digest(manager.model_configuration)
    assert any(a["kind"] == "confirmation" and a["payload"]["matched"] for a in result["artifacts"])
    events = client.get(path + f"/runs/{detail['run']['id']}/events?after=0").json()
    assert len({e["sequence"] for e in events}) == len(events)


@pytest.mark.parametrize(
    "field,value",
    [("cost_usd", ".001"), ("model_calls", 1), ("mcp_calls", 1), ("clarification_rounds", 0)],
)
def test_limit_pause_and_explicit_increase_preserve_counters(discovery, field, value):
    detail = wait(discovery, start(discovery, **{field: value})["run"]["id"])
    assert detail["run"]["status"] == "paused", detail["run"]
    assert detail["run"]["reason"] == ("cost" if field == "cost_usd" else field)
    before = detail["run"]
    limits = {
        **before["limits"],
        "cost_usd": "1",
        "model_calls": 30,
        "mcp_calls": 20,
        "clarification_rounds": 3,
    }
    resume(discovery, detail, limits=limits)
    continued = wait(discovery, before["id"])
    assert continued["run"]["model_calls"] >= before["model_calls"]
    assert continued["run"]["mcp_calls"] >= before["mcp_calls"]
    assert continued["run"]["accounted_usd"] >= before["accounted_usd"]
    assert continued["run"]["reason"] == "questions", continued["run"]


def test_question_limit_and_repeated_question_detail(discovery):
    discovery[2].model.mode = "repeat"
    detail = wait(discovery, start(discovery, clarification_rounds=1)["run"]["id"])
    resume(discovery, detail)
    result = wait(discovery, detail["run"]["id"])
    assert result["run"]["reason"] == "clarification_rounds"
    assert result["run"]["clarification_rounds"] == 1
    resume(discovery, result, limits={**result["run"]["limits"], "clarification_rounds": 2})
    result = wait(discovery, detail["run"]["id"])
    assert result["questions"][-1]["question"]["unresolved_detail"]


def test_answer_conflict_stops_before_another_probe(discovery, mcp_server):
    discovery[2].model.mode = "conflict"
    detail = wait(discovery, start(discovery)["run"]["id"])
    calls = httpx.get(f"{mcp_server}/probe-state").json()["calls"]
    resume(discovery, detail)
    result = wait(discovery, detail["run"]["id"])
    assert result["run"]["status"] == "stopped"
    assert "boundary" in result["run"]["message"]
    assert httpx.get(f"{mcp_server}/probe-state").json()["calls"] == calls


def test_unknown_write_has_no_retry(discovery, mcp_server):
    httpx.post(f"{mcp_server}/probe-reset?mode=timeout")
    discovery[2].settings = discovery[2].settings.model_copy(update={"surface_tool_timeout": 0.3})
    result = wait(discovery, start(discovery)["run"]["id"])
    assert result["run"]["reason"] == "unknown_write", result["run"]
    write = next(call for call in result["calls"] if call["effect"] == "write")
    assert write["status"] == "unknown"
    assert httpx.get(f"{mcp_server}/probe-state").json()["calls"].count("create_note") == 1


def test_start_deduplication_access_and_revision_checks(discovery):
    client, path, manager, _ = discovery
    body = {"request_id": str(uuid4()), "environment": "Test", "limits": {"cost_usd": "1"}}
    first = client.post(path + "/runs", json=body)
    second = client.post(path + "/runs", json=body)
    assert first.json()["run"]["id"] == second.json()["run"]["id"]
    assert client.get(path, headers={"X-Oak-User": "demo-sam"}).status_code == 404
    result = wait(discovery, first.json()["run"]["id"])
    endpoint = path + f"/runs/{result['run']['id']}/resume"
    assert (
        client.post(endpoint, json={"request_id": str(uuid4()), "expected_revision": 1}).status_code
        == 409
    )
    assert (
        client.post(
            endpoint,
            json={"request_id": str(uuid4()), "expected_revision": result["run"]["revision"]},
        ).status_code
        == 422
    )
    artifact = result["artifacts"][0]["id"]
    assert (
        client.get(
            path + f"/runs/{result['run']['id']}/artifacts/{artifact}",
            headers={"X-Oak-User": "demo-sam"},
        ).status_code
        == 404
    )


def test_grant_change_invalidates_resume(discovery):
    client, path, *_ = discovery
    detail = wait(discovery, start(discovery)["run"]["id"])
    agent_path = path.removesuffix("/discovery")
    assert client.put(agent_path + "/tools", json={"tool_ids": []}).status_code == 200
    assert client.get(path + f"/runs/{detail['run']['id']}").json()["run"]["outdated"]
    response = client.post(
        path + f"/runs/{detail['run']['id']}/resume",
        json={
            "request_id": str(uuid4()),
            "expected_revision": detail["run"]["revision"],
            "answers": {q["id"]: "Billing" for q in detail["questions"]},
        },
    )
    assert response.status_code == 409


def test_manual_pause_stop_and_wait_time_excluded(discovery):
    client, path, manager, _ = discovery
    manager.model.delay = 0.3
    detail = start(discovery)
    run_id = detail["run"]["id"]
    client.post(path + f"/runs/{run_id}/pause")
    paused = wait(discovery, run_id)
    assert paused["run"]["status"] == "paused"
    elapsed = paused["run"]["active_ms"]
    time.sleep(0.1)
    assert client.get(path + f"/runs/{run_id}").json()["run"]["active_ms"] == elapsed
    stopped = client.post(path + f"/runs/{run_id}/stop").json()
    assert stopped["run"]["status"] == "stopped"


def test_backend_ceiling_and_scope_snapshot(discovery):
    client, path, *_ = discovery
    response = client.post(
        path + "/runs",
        json={"request_id": str(uuid4()), "environment": "Test", "limits": {"cost_usd": "99"}},
    )
    assert response.status_code == 422
    detail = wait(discovery, start(discovery)["run"]["id"])
    assert detail["inputs"]["task"]["scope"] is None
    assert detail["inputs"]["agent"]["scope"] is None
    assert detail["run"]["reason"] == "questions"


def test_invented_source_field_is_rejected(discovery):
    discovery[2].model.mode = "invented_field"
    result = wait(discovery, start(discovery)["run"]["id"])
    assert result["run"]["status"] == "stopped"
    assert result["run"]["reason"] == "invalid_or_oversized_output"
    assert result["run"]["mcp_calls"] == 1


def test_restart_marks_dispatched_work_unknown(discovery, settings):
    client, path, manager, _ = discovery
    detail = wait(discovery, start(discovery)["run"]["id"])
    run_id = detail["run"]["id"]
    with psycopg.connect(settings.database_url) as db:
        db.execute(
            "UPDATE discovery_runs SET status='running',active_since=now() WHERE id=%s", (run_id,)
        )
        db.execute(
            "INSERT INTO discovery_calls(id,run_id,kind,purpose,request,status,effect) VALUES (%s,%s,'mcp','uncertain',%s,'dispatched','write')",
            (uuid4(), run_id, Jsonb({})),
        )
    client.portal.call(manager.recover_interrupted)
    result = client.get(path + f"/runs/{run_id}").json()
    assert result["run"]["reason"] == "interrupted"
    assert result["calls"][-1]["status"] == "unknown"


def test_redaction_and_schema_validation():
    assert redact(
        {"access_token": "private", "nested": '{"password":"secret"}', "header": "Bearer abc123"}
    ) == {
        "access_token": "[redacted]",
        "nested": '{"password":"[redacted]"}',
        "header": "Bearer [redacted]",
    }
    with pytest.raises(ValueError):
        validate_json({"title": 3}, {"type": "object", "properties": {"title": {"type": "string"}}})
    with pytest.raises(Exception):
        validate_json({}, {"$ref": "https://example.invalid/schema.json"})


def test_active_time_limit_pauses_and_keeps_unknown_cost(discovery):
    discovery[2].model.delay = 1.2
    detail = wait(discovery, start(discovery, active_seconds=1)["run"]["id"])
    assert detail["run"]["status"] == "paused", detail["run"]
    assert detail["run"]["reason"] == "active_seconds"
    assert detail["run"]["reserved_usd"] > 0
    discovery[2].model.delay = 0.01
    resume(discovery, detail, limits={**detail["run"]["limits"], "active_seconds": 60})
    result = wait(discovery, detail["run"]["id"])
    assert result["run"]["reserved_usd"] >= detail["run"]["reserved_usd"]


def test_catalog_drift_on_resume_stops(discovery):
    detail = wait(discovery, start(discovery)["run"]["id"])
    manager = discovery[2]
    original = manager.connections.catalog

    async def changed(client):
        tools = await original(client)
        return [t.model_copy(update={"description": "Changed contract"}) for t in tools]

    manager.connections.catalog = changed
    resume(discovery, detail)
    result = wait(discovery, detail["run"]["id"])
    assert result["run"]["status"] == "stopped"
    assert result["run"]["mcp_calls"] == detail["run"]["mcp_calls"]


def test_resume_does_not_accept_foreign_answers_or_reduce_limits(discovery):
    client, path, *_ = discovery
    detail = wait(discovery, start(discovery)["run"]["id"])
    body = {
        "request_id": str(uuid4()),
        "expected_revision": detail["run"]["revision"],
        "answers": {str(uuid4()): "Billing"},
    }
    endpoint = path + f"/runs/{detail['run']['id']}/resume"
    assert client.post(endpoint, json=body).status_code == 422
    body["answers"] = {q["id"]: "Billing" for q in detail["questions"]}
    body["limits"] = {**detail["run"]["limits"], "mcp_calls": 2}
    assert client.post(endpoint, json=body).status_code == 422


def test_private_credentials_are_scoped_persistent_and_redacted(discovery):
    from oak.discovery_validation import pointer

    client, _, manager, tools = discovery
    detail = wait(discovery, start(discovery)["run"]["id"])
    run_id = detail["run"]["id"]
    connection_id = tools[0]["connection_id"]

    async def verify():
        async with manager.store.pool.connection() as db:
            safe = await manager.credentials.capture(
                db,
                run_id,
                connection_id,
                {"password": "test-password-value", "access_token": "test-access-value"},
            )
        assert safe["password"].startswith("oak-secret:")
        assert "test-password-value" not in str(redact(safe))
        with pytest.raises(ValueError):
            pointer(safe, "/password")
        async with manager.store.pool.connection() as db:
            resolved = await manager.credentials.resolve(db, run_id, connection_id, safe)
            assert resolved["password"] == "test-password-value"
            scrubbed = await manager.credentials.scrub(
                db, run_id, {"echo": "Received test-password-value and test-access-value"}
            )
            assert scrubbed["echo"] == "Received [redacted] and [redacted]"
            for foreign_run, foreign_connection in [(uuid4(), connection_id), (run_id, uuid4())]:
                with pytest.raises(ValueError):
                    await manager.credentials.resolve(db, foreign_run, foreign_connection, safe)
            await manager.credentials.clear(db, run_id)
            with pytest.raises(ValueError):
                await manager.credentials.resolve(db, run_id, connection_id, safe)

    client.portal.call(verify)


def test_catalog_credential_properties_remain_valid_schema():
    schema = {"type": "object", "properties": {"password": {"type": "string"}}}
    assert redact({"input_schema": schema}, preserve_schemas=True)["input_schema"] == schema
    assert redact({"password": "private"}) == {"password": "[redacted]"}


def test_concurrent_start_and_resume_dispatch_once(discovery, mcp_server):
    from concurrent.futures import ThreadPoolExecutor

    client, path, *_ = discovery
    body = {"request_id": str(uuid4()), "environment": "Test", "limits": {"cost_usd": "1"}}
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda _: client.post(path + "/runs", json=body), range(2)))
    assert [r.status_code for r in replies] == [202, 202]
    assert replies[0].json()["run"]["id"] == replies[1].json()["run"]["id"]
    detail = wait(discovery, replies[0].json()["run"]["id"])
    body = {
        "request_id": str(uuid4()),
        "expected_revision": detail["run"]["revision"],
        "answers": {q["id"]: "Billing contact" for q in detail["questions"]},
    }
    endpoint = path + f"/runs/{detail['run']['id']}/resume"
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda _: client.post(endpoint, json=body), range(2)))
    assert [r.status_code for r in replies] == [202, 202]
    result = wait(discovery, detail["run"]["id"])
    assert result["run"]["status"] == "completed"
    assert result["run"]["model_calls"] == 6
    assert httpx.get(f"{mcp_server}/probe-state").json()["calls"].count("create_note") == 1


def test_probe_can_cite_credential_reference_but_schema_cannot():
    from oak.discovery_validation import check_references

    ref = {"source": "artifact", "id": "observation", "path": "/data/access_token"}
    artifacts = {
        "observation": {"payload": {"data": {"access_token": "oak-secret:" + str(uuid4())}}}
    }
    check_references(ref, {}, artifacts, {}, allow_credentials=True)
    with pytest.raises(ValueError):
        check_references(ref, {}, artifacts, {})


def test_invalid_reference_is_recorded_and_corrected_before_dispatch(discovery):
    discovery[2].model.mode = "bad_reference_once"
    result = wait(discovery, start(discovery)["run"]["id"])
    assert result["run"]["reason"] == "questions"
    assert result["run"]["model_calls"] == 5
    assert result["run"]["mcp_calls"] == 3
    reports = [a for a in result["artifacts"] if a["kind"] == "proposal_validation"]
    assert len(reports) == 1 and reports[0]["payload"]["repair_requested"]


def test_invalid_comparison_preserves_actual_read_and_write_records(discovery):
    discovery[2].model.mode = "bad_confirmation"
    result = wait(discovery, start(discovery)["run"]["id"])
    assert result["run"]["reason"] == "questions"
    assert (
        len([c for c in result["calls"] if c["kind"] == "mcp" and c["status"] == "succeeded"]) == 3
    )
    comparison = next(a for a in result["artifacts"] if a["kind"] == "confirmation")
    assert not comparison["payload"]["matched"]
    assert "does not exist" in comparison["payload"]["error"]


def test_model_cannot_repeat_a_completed_write(discovery, mcp_server):
    discovery[2].model.mode = "repeat_write"
    result = wait(discovery, start(discovery)["run"]["id"])
    assert result["run"]["status"] == "stopped"
    assert result["run"]["mcp_calls"] == 2
    assert httpx.get(f"{mcp_server}/probe-state").json()["calls"].count("create_note") == 1
