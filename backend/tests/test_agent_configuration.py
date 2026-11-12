from copy import deepcopy
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from oak.main import create_app
from tests.test_onboarding import agent, connect, task
from tests.test_task_scope import scope_input


def configuration(tool_ids=()):
    scope = scope_input()["scope"]
    return {
        "name": "Meeting coordinator",
        "responsibilities": scope["responsibilities"],
        "scope": scope,
        "tool_ids": list(tool_ids),
    }


def test_configuration_saves_scope_and_multiple_servers(client, settings):
    path = task(client)
    connect(client, path, "alpha")
    connect(client, path, "beta")
    tools = client.get(path + "/tools").json()
    ids = [tool["id"] for tool in tools if tool["name"] == "search"]
    payload = configuration(ids + ids)
    payload["scope"]["responsibilities"] += "\n  Preserve this indentation.\n"
    response = client.post(path + "/agents", json=payload)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["scope"] == payload["scope"]
    assert saved["responsibilities"] == payload["scope"]["responsibilities"].strip()
    assert set(saved["tool_ids"]) == set(ids)
    assert len(saved["tool_ids"]) == 2
    with TestClient(create_app(settings), headers={"X-Oak-Key": settings.api_key}) as restarted:
        assert restarted.get(path + "/agents").json() == [saved]


def test_configuration_edits_preserve_other_agents_and_legacy_requests(client):
    path = task(client)
    connect(client, path, "alpha")
    ids = [tool["id"] for tool in client.get(path + "/tools").json()]
    first = client.post(path + "/agents", json=configuration(ids)).json()
    second = client.post(path + "/agents", json=configuration(ids[:1])).json()
    target = path + "/agents/" + first["id"]
    changed = configuration(ids[1:])
    changed["scope"]["boundaries"] = "Ask before a change to a series."
    response = client.patch(target, json=changed)
    assert response.status_code == 200
    assert response.json()["scope"] == changed["scope"]
    assert response.json()["tool_ids"] == ids[1:]
    assert client.get(path + "/agents").json()[1] == second
    legacy = client.patch(target, json={"name": "Renamed", "responsibilities": "Inspect meetings."})
    assert legacy.status_code == 200
    assert legacy.json()["scope"]["boundaries"] == changed["scope"]["boundaries"]
    assert legacy.json()["scope"]["responsibilities"] == "Inspect meetings."
    assert legacy.json()["tool_ids"] == ids[1:]
    cleared = client.patch(target, json=configuration())
    assert cleared.status_code == 200
    assert cleared.json()["tool_ids"] == []
    assert agent(client, path)["scope"] is None


def test_invalid_tools_roll_back_the_entire_configuration(client):
    path = task(client)
    other = task(client, "Other task")
    connect(client, other, "alpha")
    foreign = client.get(other + "/tools").json()[0]["id"]
    saved = client.post(path + "/agents", json=configuration()).json()
    target = path + "/agents/" + saved["id"]
    for invalid in (foreign, str(uuid4())):
        payload = configuration([invalid])
        payload["name"] = "Must not save"
        payload["scope"]["boundaries"] = "Must not save"
        assert client.post(path + "/agents", json=payload).status_code == 422
        assert client.patch(target, json=payload).status_code == 422
        assert client.get(path + "/agents").json() == [saved]
    assert (
        client.patch(target, json=configuration(), headers={"X-Oak-User": "demo-sam"}).status_code
        == 404
    )
    assert (
        client.post(
            path + "/agents", json=configuration(), headers={"X-Oak-User": "demo-sam"}
        ).status_code
        == 404
    )
    assert client.patch(other + "/agents/" + saved["id"], json=configuration()).status_code == 404
    assert client.get(path + "/agents").json() == [saved]


def test_configuration_preserves_unavailable_grants_without_new_access(client, mcp_server):
    path = task(client)
    connection, _ = connect(client, path, "alpha")
    tools = client.get(path + "/tools").json()
    unavailable_id = next(tool["id"] for tool in tools if tool["name"] == "inspect_document")
    saved = client.post(path + "/agents", json=configuration([unavailable_id])).json()
    target = path + "/agents/" + saved["id"]
    httpx.post(mcp_server + "/catalog/changed")
    client.post(path + "/connections/" + connection["id"] + "/refresh")
    assert client.patch(target, json=configuration([unavailable_id])).status_code == 200
    assert client.post(path + "/agents", json=configuration([unavailable_id])).status_code == 422
    second = client.post(path + "/agents", json=configuration()).json()
    assert (
        client.patch(
            path + "/agents/" + second["id"], json=configuration([unavailable_id])
        ).status_code
        == 422
    )
    assert client.patch(target, json=configuration()).json()["tool_ids"] == []
    assert client.patch(target, json=configuration([unavailable_id])).status_code == 422
    assert httpx.get(mcp_server + "/health").json()["calls"] == 0


@pytest.mark.parametrize("field", ["responsibilities", "success_criteria"])
def test_invalid_surface_does_not_change_the_agent(client, field):
    path = task(client)
    saved = client.post(path + "/agents", json=configuration()).json()
    payload = deepcopy(configuration())
    payload["scope"][field] = " \n "
    assert client.post(path + "/agents", json=payload).status_code == 422
    assert client.patch(path + "/agents/" + saved["id"], json=payload).status_code == 422
    assert client.get(path + "/agents").json() == [saved]
