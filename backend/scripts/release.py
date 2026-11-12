"""Deploy a tested backend, preserve rollback targets, and check the private release."""

import json
import os
import sys
import time
from pathlib import Path

import httpx

RELEASE_FILE = Path(__file__).resolve().parents[2] / "release.json"


def required(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Configure {name} before enabling deployment.")
    return value


def backend():
    service = required("RENDER_SERVICE_ID")
    sha = required("OAK_RELEASE_SHA")
    api_url = required("OAK_API_URL").rstrip("/")
    with httpx.Client(
        base_url="https://api.render.com/v1",
        timeout=30,
        headers={"Authorization": f"Bearer {required('RENDER_API_KEY')}"},
    ) as render:
        previous = render.get(f"/services/{service}/deploys", params={"limit": 20})
        previous.raise_for_status()
        render_previous = next(
            (d["deploy"]["id"] for d in previous.json() if d["deploy"]["status"] == "live"), None
        )
        vercel = httpx.get(
            "https://api.vercel.com/v6/deployments",
            timeout=30,
            headers={"Authorization": f"Bearer {required('VERCEL_TOKEN')}"},
            params={
                "projectId": required("VERCEL_PROJECT_ID"),
                "teamId": required("VERCEL_ORG_ID"),
                "target": "production",
                "state": "READY",
                "limit": 1,
            },
        )
        vercel.raise_for_status()
        releases = vercel.json()["deployments"]
        record = {
            "commit": sha,
            "previous_render_deploy": render_previous,
            "previous_vercel_deploy": releases[0]["uid"] if releases else None,
            "status": "deploying_backend",
        }
        RELEASE_FILE.write_text(json.dumps(record, indent=2) + "\n")
        result = render.post(f"/services/{service}/deploys", json={"commitId": sha})
        result.raise_for_status()
        deployment = result.json()["id"]
        record["render_deploy"] = deployment
        RELEASE_FILE.write_text(json.dumps(record, indent=2) + "\n")
        for _ in range(120):
            status = render.get(f"/services/{service}/deploys/{deployment}")
            status.raise_for_status()
            state = status.json()["status"]
            if state == "live":
                break
            if state.endswith("failed") or state in {"canceled", "deactivated"}:
                raise RuntimeError(f"Render deployment stopped: {state}.")
            time.sleep(10)
        else:
            raise RuntimeError("Render deployment timed out.")
    health = httpx.get(f"{api_url}/health", timeout=60)
    health.raise_for_status()
    if health.json() != {"status": "ok", "release": sha}:
        raise RuntimeError("Backend health does not match the tested commit.")
    record["status"] = "backend_ready"
    RELEASE_FILE.write_text(json.dumps(record, indent=2) + "\n")
    print("Tested backend is healthy. Frontend deployment can start.")


def smoke():
    origin = required("OAK_FRONTEND_URL").rstrip("/")
    bypass = os.environ.get("OAK_VERCEL_PROTECTION_BYPASS")
    headers = {"x-vercel-protection-bypass": bypass} if bypass else {}
    with httpx.Client(base_url=origin, timeout=60, headers=headers) as client:
        if client.get("/").status_code != 401 or client.get("/api/tasks").status_code != 401:
            raise RuntimeError("The frontend private access gate did not reject public requests.")
        auth = (required("OAK_PREVIEW_USER"), required("OAK_PREVIEW_PASSWORD"))
        page = client.get("/", auth=auth)
        page.raise_for_status()
        if "Oak" not in page.text:
            raise RuntimeError("The frontend did not return the Oak application.")
        users = client.get("/api/users", auth=auth)
        users.raise_for_status()
        if {u["id"] for u in users.json()} != {"demo-alex", "demo-sam"}:
            raise RuntimeError("The frontend could not reach the expected backend.")
        for user in ["demo-alex", "demo-sam"]:
            tasks = client.get("/api/tasks", auth=auth, headers={"X-Oak-User": user})
            tasks.raise_for_status()
            if not isinstance(tasks.json(), list):
                raise RuntimeError("Task storage is unavailable.")
    if httpx.get(required("OAK_API_URL") + "/api/tasks", timeout=60).status_code != 401:
        raise RuntimeError("The backend private access gate did not reject public requests.")
    record = json.loads(RELEASE_FILE.read_text())
    record["status"] = "smoke_passed"
    RELEASE_FILE.write_text(json.dumps(record, indent=2) + "\n")
    print("Deployed smoke checks passed.")


if __name__ == "__main__":
    try:
        {"backend": backend, "smoke": smoke}[sys.argv[1]]()
    except Exception as error:
        # Provider responses and environment values must not enter CI logs.
        print(f"Release stopped ({type(error).__name__}). Check configuration and provider status.")
        raise SystemExit(1) from None
