import time
from urllib.parse import parse_qs, urlsplit

import httpx
import psycopg
from fastapi.testclient import TestClient

from oak.main import create_app


def task(client, name="Research"):
    response = client.post("/api/tasks", json={"name": name, "objective": "Find reliable sources"})
    assert response.status_code == 201, response.text
    return "/api/tasks/" + response.json()["id"]


def agent(client, path, name="Analyst"):
    response = client.post(
        path + "/agents", json={"name": name, "responsibilities": "Find source evidence"}
    )
    assert response.status_code == 201
    assert response.json()["tool_ids"] == []
    return response.json()


def connect(client, path, server, auth="none", token=None):
    response = client.post(
        path + "/connections",
        json={
            "name": server,
            "url": f"http://127.0.0.1:9147/{server}/mcp",
            "auth_mode": auth,
            "token": token,
        },
    )
    assert response.status_code == 201, response.text
    connection = response.json()
    assert "token" not in connection and "secret_id" not in connection
    return connection, client.post(path + f"/connections/{connection['id']}/refresh").json()


def test_discovery_isolation_refresh_and_persistence(client, settings, mcp_server):
    path = task(client)
    first, second = agent(client, path), agent(client, path, "Reviewer")
    alpha, refreshed = connect(client, path, "alpha")
    assert refreshed["status"] == "connected", refreshed
    _, refreshed = connect(client, path, "beta")
    assert refreshed["status"] == "connected"
    tools = client.get(path + "/tools").json()
    searches = [t for t in tools if t["name"] == "search"]
    assert len(searches) == 2 and searches[0]["id"] != searches[1]["id"]
    inspection = next(t for t in tools if t["name"] == "inspect_document")
    ids = [searches[0]["id"], inspection["id"]]
    assert (
        client.put(path + f"/agents/{first['id']}/tools", json={"tool_ids": ids}).status_code == 200
    )
    assert (
        client.put(
            path + f"/agents/{second['id']}/tools", json={"tool_ids": [searches[1]["id"]]}
        ).status_code
        == 200
    )
    other = task(client, "Other task")
    outsider = agent(client, other)
    assert (
        client.put(other + f"/agents/{outsider['id']}/tools", json={"tool_ids": ids}).status_code
        == 422
    )
    assert (
        client.put(other + f"/agents/{first['id']}/tools", json={"tool_ids": []}).status_code == 404
    )
    assert client.get(path + "/agents", headers={"X-Oak-User": "demo-sam"}).status_code == 404
    assert client.get("/api/tasks", headers={"X-Oak-User": "demo-sam"}).json() == []
    assert client.get(path + "/tools", headers={"X-Oak-Key": "wrong"}).status_code == 401
    assert client.get("/api/tasks", headers={"X-Oak-User": "fake"}).status_code == 401
    # A task member can access both agents, without separate agent permissions.
    with psycopg.connect(settings.database_url) as db:
        db.execute("INSERT INTO task_members VALUES (%s,'demo-sam')", (path.split("/")[-1],))
    assert len(client.get(path + "/agents", headers={"X-Oak-User": "demo-sam"}).json()) == 2
    httpx.post(mcp_server + "/catalog/changed")
    assert client.post(path + f"/connections/{alpha['id']}/refresh").json()["status"] == "connected"
    changed = client.get(path + "/tools").json()
    missing = next(t for t in changed if t["id"] == inspection["id"])
    assert not missing["available"]
    fresh = next(t for t in changed if t["name"] == "summarize")
    saved = client.get(path + "/agents").json()
    assert set(saved[0]["tool_ids"]) == set(ids)
    assert fresh["id"] not in saved[0]["tool_ids"]
    assert (
        client.put(
            path + f"/agents/{second['id']}/tools", json={"tool_ids": [inspection["id"]]}
        ).status_code
        == 422
    )
    assert (
        client.put(path + f"/agents/{first['id']}/tools", json={"tool_ids": ids}).status_code == 200
    )
    assert httpx.get(mcp_server + "/health").json()["calls"] == 0
    # Reloading a new application process reads the same saved configuration.
    with TestClient(create_app(settings), headers={"X-Oak-Key": settings.api_key}) as restarted:
        assert set(restarted.get(path + "/agents").json()[0]["tool_ids"]) == set(ids)


def test_connection_and_token_failure_recovery(client, mcp_server):
    path = task(client)
    connection, result = connect(client, path, "secure", "token", "wrong-token")
    assert result["status"] == "error"
    target = path + f"/connections/{connection['id']}"
    assert client.put(target + "/token", json={"token": "fixture-token"}).status_code == 200
    assert client.post(target + "/refresh").json()["status"] == "connected"
    before = client.get(path + "/tools").json()
    client.put(target + "/token", json={"token": "wrong-token"})
    assert client.post(target + "/refresh").json()["status"] == "error"
    assert client.get(path + "/tools").json() == before
    response = client.post(
        path + "/connections",
        json={"name": "Down", "url": "http://127.0.0.1:9147/missing", "auth_mode": "none"},
    )
    down = response.json()["id"]
    assert client.post(path + f"/connections/{down}/refresh").json()["status"] == "error"
    assert (
        client.post(
            path + "/connections",
            json={"name": "Private", "url": "http://169.254.169.254/metadata"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            path + "/connections",
            json={"name": "Secret URL", "url": "http://127.0.0.1:9147/mcp?token=secret"},
        ).status_code
        == 422
    )
    oversized = "never-echo-this" * 2000
    response = client.put(target + "/token", json={"token": oversized})
    assert response.status_code == 422 and "never-echo-this" not in response.text
    assert client.delete(target).status_code == 204
    assert client.get(path + "/tools").json() == []


def test_oauth_sdk_pkce_callback_and_saved_credentials(client, mcp_server):
    path = task(client)
    connection, result = connect(client, path, "oauth", "oauth")
    assert result["status"] == "auth_required", result
    auth_url = result["auth_url"]
    query = parse_qs(urlsplit(auth_url).query)
    assert query["code_challenge_method"] == ["S256"]
    assert client.get("/oauth/callback?state=wrong&code=no").status_code == 400
    authorized = httpx.get(auth_url, follow_redirects=False)
    callback = urlsplit(authorized.headers["location"])
    assert client.get(callback.path + "?" + callback.query).status_code == 200
    assert client.get(callback.path + "?" + callback.query).status_code == 400
    for _ in range(100):
        result = client.get(path + "/connections").json()[0]
        if result["status"] in {"connected", "error"}:
            break
        time.sleep(0.05)
    assert result["status"] == "connected", result
    assert result["auth_url"] is None
    count = httpx.get(mcp_server + "/health").json()["authorizations"]
    assert (
        client.post(path + f"/connections/{connection['id']}/refresh").json()["status"]
        == "connected"
    )
    assert httpx.get(mcp_server + "/health").json()["authorizations"] == count
