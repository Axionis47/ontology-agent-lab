from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from oak.main import create_app


def scope_input():
    return {
        "name": "Team meetings",
        "objective": "Keep meeting schedules consistent.",
        "scope": {
            "responsibilities": "Create meetings.\nChange individual occurrences or series.",
            "context_and_rules": "An occurrence belongs to a series.",
            "boundaries": "Preserve unrelated meetings.",
            "success_criteria": "The calendar matches the requested change.",
            "examples": [
                {
                    "situation": "Cancel Friday's occurrence.",
                    "expected_behavior": "Cancel only that occurrence.",
                    "prohibited_behavior": "Do not cancel the series.",
                },
                {
                    "situation": "Cancel the entire series.",
                    "expected_behavior": "Cancel the series.",
                    "prohibited_behavior": "",
                },
            ],
        },
    }


def test_scope_persistence_and_access(client, settings):
    payload = scope_input()
    payload["scope"]["responsibilities"] += "\n  Preserve this indentation.\n"
    created = client.post("/api/tasks", json=payload)
    assert created.status_code == 201
    path = "/api/tasks/" + created.json()["id"]
    assert created.json()["scope"] == payload["scope"]
    assert client.get(path).json()["scope"] == payload["scope"]
    assert client.get("/api/tasks").json()[0]["scope"] == payload["scope"]
    assert client.get(path, headers={"X-Oak-User": "demo-sam"}).status_code == 404
    assert client.patch(path, json=payload, headers={"X-Oak-User": "demo-sam"}).status_code == 404
    with TestClient(create_app(settings), headers={"X-Oak-Key": settings.api_key}) as restarted:
        assert restarted.get(path).json()["scope"] == payload["scope"]


def test_scope_is_immutable_and_name_can_change(client):
    payload = scope_input()
    path = "/api/tasks/" + client.post("/api/tasks", json=payload).json()["id"]
    for field in ["responsibilities", "context_and_rules", "boundaries", "success_criteria"]:
        changed = deepcopy(payload)
        changed["scope"][field] = "Changed requirement"
        response = client.patch(path, json=changed)
        assert response.status_code == 409
        assert "read-only" in response.json()["detail"]
    changed = deepcopy(payload)
    changed["scope"]["examples"].reverse()
    assert client.patch(path, json=changed).status_code == 409
    assert client.patch(path, json={**payload, "objective": "New purpose"}).status_code == 409
    assert client.patch(path, json={**payload, "scope": None}).status_code == 409
    renamed = client.patch(path, json={"name": "Renamed", "objective": payload["objective"]})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Renamed"
    assert renamed.json()["scope"] == payload["scope"]
    assert client.patch(path, json=payload).status_code == 200


def test_original_requests_and_optional_sections(client):
    original = {"name": "Original", "objective": "Find reliable sources."}
    created = client.post("/api/tasks", json=original)
    assert created.status_code == 201
    assert created.json()["scope"] is None
    path = "/api/tasks/" + created.json()["id"]
    assert client.patch(path, json={**original, "name": "New name"}).status_code == 200
    assert client.patch(path, json={**original, "objective": "Changed"}).status_code == 409
    assert client.patch(path, json={**original, "scope": scope_input()["scope"]}).status_code == 409
    minimal = {"responsibilities": "Find evidence", "success_criteria": "Sources are identified"}
    response = client.post("/api/tasks", json={**original, "scope": minimal})
    assert response.status_code == 201
    assert response.json()["scope"] == {
        **minimal,
        "context_and_rules": "",
        "boundaries": "",
        "examples": [],
    }


@pytest.mark.parametrize("field", ["responsibilities", "success_criteria"])
@pytest.mark.parametrize("value", ["", " \n ", "x" * 10001])
def test_required_scope_validation(client, field, value):
    payload = scope_input()
    payload["scope"][field] = value
    assert client.post("/api/tasks", json=payload).status_code == 422


@pytest.mark.parametrize("field", ["context_and_rules", "boundaries"])
def test_optional_scope_limits(client, field):
    payload = scope_input()
    payload["scope"][field] = "x" * 10001
    assert client.post("/api/tasks", json=payload).status_code == 422


@pytest.mark.parametrize(
    "example",
    [
        {},
        {"situation": "Request", "expected_behavior": "   "},
        {"situation": "", "expected_behavior": "Clarify"},
        {"situation": "x" * 10001, "expected_behavior": "Clarify"},
        {"situation": "Request", "expected_behavior": "x" * 10001},
        {
            "situation": "Request",
            "expected_behavior": "Clarify",
            "prohibited_behavior": "x" * 10001,
        },
    ],
)
def test_example_validation(client, example):
    payload = scope_input()
    payload["scope"]["examples"] = [example]
    assert client.post("/api/tasks", json=payload).status_code == 422
