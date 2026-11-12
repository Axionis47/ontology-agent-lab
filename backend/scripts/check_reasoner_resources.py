"""Test the backend and verifier in the current free-service resource limits."""

import argparse
import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

BACKEND = Path(__file__).resolve().parents[1]
MEMORY_LIMIT = "512m"
CPU_LIMIT = "0.1"
PLATFORM = "linux/amd64"


class SmokeFailure(RuntimeError):
    pass


def docker(*arguments, timeout=30):
    try:
        result = subprocess.run(
            ["docker", *arguments],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SmokeFailure(f"Docker {arguments[0]} is unavailable or timed out.") from error
    if result.returncode:
        # Docker errors can repeat environment values supplied to a container.
        raise SmokeFailure(f"Docker {arguments[0]} failed with exit code {result.returncode}.")
    return result.stdout.strip()


def app_arguments(name, network, image, database, api_key, secret_key):
    return [
        "run",
        "--detach",
        "--platform",
        PLATFORM,
        "--name",
        name,
        "--network",
        network,
        "--memory",
        MEMORY_LIMIT,
        "--memory-swap",
        MEMORY_LIMIT,
        "--cpus",
        CPU_LIMIT,
        "--pids-limit",
        "128",
        "--publish",
        "127.0.0.1::8000",
        "--env",
        "OAK_ENVIRONMENT=local",
        "--env",
        "OAK_SECRET_BACKEND=local",
        "--env",
        f"OAK_DATABASE_URL=postgresql://oak:resource-smoke@{database}:5432/oak_resource_test",
        "--env",
        f"OAK_API_KEY={api_key}",
        "--env",
        f"OAK_LOCAL_SECRET_KEY={secret_key}",
        image,
    ]


def wait_for_database(name):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            docker("exec", name, "pg_isready", "-U", "oak", "-d", "oak_resource_test")
            return
        except SmokeFailure:
            time.sleep(0.5)
    raise SmokeFailure("The temporary test database did not start.")


def wait_for_app(name):
    deadline = time.monotonic() + 120
    address = docker("port", name, "8000/tcp").splitlines()[0]
    if not address.startswith("127.0.0.1:"):
        raise SmokeFailure("The test backend must expose only a local port.")
    while time.monotonic() < deadline:
        if docker("inspect", "--format", "{{.State.Running}}", name) != "true":
            raise SmokeFailure("The backend stopped during startup.")
        try:
            with urlopen(f"http://{address}/health", timeout=5) as response:
                json.load(response)
            return
        except (OSError, URLError, ValueError):
            time.sleep(0.5)
    raise SmokeFailure("The backend did not become ready within its resource limits.")


def run(image, *, build=True):
    docker("info", "--format", "{{.ServerVersion}}")
    if build:
        docker("build", "--platform", PLATFORM, "--tag", image, str(BACKEND), timeout=900)
    platform = docker("image", "inspect", "--format", "{{.Os}}/{{.Architecture}}", image)
    if platform != PLATFORM:
        raise SmokeFailure(f"The image must target {PLATFORM}.")
    suffix = uuid4().hex[:12]
    network, database, app = [f"oak-resource-{kind}-{suffix}" for kind in ("net", "db", "api")]
    api_key = "resource-smoke-" + uuid4().hex
    secret_key = base64.urlsafe_b64encode(os.urandom(32)).decode()
    try:
        docker("network", "create", network)
        docker(
            "run",
            "--detach",
            "--name",
            database,
            "--network",
            network,
            "--env",
            "POSTGRES_USER=oak",
            "--env",
            "POSTGRES_PASSWORD=resource-smoke",
            "--env",
            "POSTGRES_DB=oak_resource_test",
            "postgres:16.11",
            timeout=180,
        )
        wait_for_database(database)
        docker(*app_arguments(app, network, image, database, api_key, secret_key))
        wait_for_app(app)
        output = docker("exec", app, "python", "-m", "scripts.reasoner_resource_probe", timeout=90)
        result = json.loads(output)
        state = json.loads(docker("inspect", "--format", "{{json .State}}", app))
        if state.get("OOMKilled") or not state.get("Running"):
            raise SmokeFailure("The backend stopped or exceeded its memory limit.")
        result["image_id"] = docker("inspect", "--format", "{{.Image}}", app)
        result["platform"] = platform
        result["docker_host_architecture"] = docker("info", "--format", "{{.Architecture}}")
        return result
    finally:
        for name in (app, database):
            try:
                docker("rm", "--force", name)
            except SmokeFailure:
                pass
        try:
            docker("network", "rm", network)
        except SmokeFailure:
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="oak-api:reasoner-resource-smoke")
    parser.add_argument("--skip-build", action="store_true")
    options = parser.parse_args()
    try:
        report = run(options.image, build=not options.skip_build)
    except (SmokeFailure, ValueError) as error:
        report = {"status": "unsupported_resource_envelope", "error": str(error)}
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
