"""Start the API with an isolated test database for browser tests."""

import asyncio
import os

import psycopg
import uvicorn
from cryptography.fernet import Fernet
from psycopg.conninfo import conninfo_to_dict

from oak.db import migrate
from oak.main import create_app
from oak.settings import Settings

database_url = os.environ["OAK_TEST_DATABASE_URL"]
if not conninfo_to_dict(database_url)["dbname"].endswith("_test"):
    raise RuntimeError("Browser tests require a dedicated database ending in _test.")
settings = Settings(
    _env_file=None,
    environment="local",
    database_url=database_url,
    api_key="e2e-private-key-" + "x" * 32,
    secret_backend="local",
    local_secret_key=Fernet.generate_key().decode(),
    allow_local_mcp=True,
    public_api_url="http://localhost:8047",
    frontend_url="http://localhost:3047",
    discovery_timeout=5,
    oauth_timeout=30,
)
asyncio.run(migrate(settings))
with psycopg.connect(database_url) as db:
    db.execute("TRUNCATE tasks,oak_local_secrets CASCADE")
uvicorn.run(create_app(settings), host="127.0.0.1", port=8047, access_log=False)
