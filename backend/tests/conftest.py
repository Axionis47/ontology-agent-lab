import asyncio
import os
import subprocess
import sys
import time

import httpx
import psycopg
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict

from oak.db import migrate
from oak.main import create_app
from oak.settings import Settings


@pytest.fixture(scope="session")
def settings():
    database_url = os.environ.get("OAK_TEST_DATABASE_URL")
    if not database_url or not conninfo_to_dict(database_url)["dbname"].endswith("_test"):
        pytest.fail("Set OAK_TEST_DATABASE_URL to a dedicated database ending in _test.")
    config = Settings(
        _env_file=None,
        environment="local",
        database_url=database_url,
        api_key="test-private-key-" + "x" * 32,
        secret_backend="local",
        local_secret_key=Fernet.generate_key().decode(),
        allow_local_mcp=True,
        public_api_url="http://localhost:8047",
        discovery_timeout=5,
        oauth_timeout=15,
    )
    asyncio.run(migrate(config))
    return config


@pytest.fixture(scope="session")
def mcp_server():
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "tests.mcp_server:app",
            "--host",
            "127.0.0.1",
            "--port",
            "9147",
            "--no-access-log",
            "--log-level",
            "critical",
        ],
        stdout=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError("The controlled MCP server could not start.")
            try:
                if httpx.get("http://127.0.0.1:9147/health").status_code == 200:
                    yield "http://127.0.0.1:9147"
                    return
            except httpx.ConnectError:
                pass
            time.sleep(0.1)
        raise RuntimeError("MCP fixture did not become ready.")
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.fixture
def client(settings, mcp_server):
    with psycopg.connect(settings.database_url) as db:
        db.execute("TRUNCATE tasks,oak_local_secrets CASCADE")
    httpx.post(f"{mcp_server}/catalog/original")
    with TestClient(create_app(settings), headers={"X-Oak-Key": settings.api_key}) as client:
        yield client
