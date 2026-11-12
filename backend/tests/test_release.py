import json

import httpx
import pytest

from scripts import release


@pytest.fixture
def deployment(monkeypatch, tmp_path):
    for name, value in {
        "RENDER_SERVICE_ID": "srv-test",
        "RENDER_API_KEY": "test-render-key",
        "OAK_RELEASE_SHA": "a" * 40,
        "OAK_API_URL": "https://oak-api.example",
        "VERCEL_TOKEN": "test-vercel-key",
        "VERCEL_PROJECT_ID": "prj-test",
        "VERCEL_ORG_ID": "team-test",
    }.items():
        monkeypatch.setenv(name, value)
    target = tmp_path / "release.json"
    monkeypatch.setattr(release, "RELEASE_FILE", target)
    return target


def simulate(monkeypatch, state, health_sha):
    requests = []

    def handler(request):
        requests.append(request)
        path = request.url.path
        if path == "/v1/services/srv-test/deploys":
            if request.method == "GET":
                return httpx.Response(
                    200, json=[{"deploy": {"id": "old-render", "status": "live"}}]
                )
            assert json.loads(request.content) == {"commitId": "a" * 40}
            return httpx.Response(201, json={"id": "new-render"})
        if path.endswith("/new-render"):
            return httpx.Response(200, json={"status": state})
        if path == "/v6/deployments":
            return httpx.Response(200, json={"deployments": [{"uid": "old-vercel"}]})
        if path == "/health":
            return httpx.Response(200, json={"status": "ok", "release": health_sha})
        raise AssertionError(path)

    original = httpx.Client
    monkeypatch.setattr(
        release.httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)
    )
    monkeypatch.setattr(
        release.httpx,
        "get",
        lambda url, **kw: original(transport=httpx.MockTransport(handler)).get(url, **kw),
    )
    return requests


def test_release_uses_tested_commit_and_preserves_rollback_targets(monkeypatch, deployment):
    simulate(monkeypatch, "live", "a" * 40)
    release.backend()
    record = json.loads(deployment.read_text())
    assert record["status"] == "backend_ready"
    assert record["previous_render_deploy"] == "old-render"
    assert record["previous_vercel_deploy"] == "old-vercel"


@pytest.mark.parametrize("state,sha", [("build_failed", "a" * 40), ("live", "wrong-commit")])
def test_failed_or_wrong_backend_stops_release(monkeypatch, deployment, state, sha):
    simulate(monkeypatch, state, sha)
    with pytest.raises(RuntimeError):
        release.backend()
    assert json.loads(deployment.read_text())["status"] != "backend_ready"
