"""Start the API with an isolated test database for browser tests."""

import asyncio
import os
from decimal import Decimal
from typing import Literal

import psycopg
import uvicorn
from cryptography.fernet import Fernet
from psycopg.conninfo import conninfo_to_dict

from oak.db import migrate
from oak.main import create_app
from oak.model_client import ModelFailure, ModelResult
from oak.model_runtime import ConnectionReply
from oak.schemas import ModelUsage
from oak.settings import Settings
from tests.discovery_model import DiscoveryModel
from tests.training_model import TrainingModel, prepare_training_environment

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
    gemini_project="browser-test-project",
    gemini_check_budget_usd=Decimal("0.10"),
)
asyncio.run(migrate(settings))
with psycopg.connect(database_url) as db:
    db.execute("TRUNCATE tasks,oak_local_secrets,model_runtime_checks CASCADE")


class BrowserModel:
    mode = "success"
    calls = 0

    async def generate(self, instructions, data, response_schema):
        self.calls += 1
        await asyncio.sleep(0.8)
        if self.mode == "permissions":
            raise ModelFailure("permissions")
        return ModelResult(
            data=ConnectionReply(status="ok"),
            model=settings.gemini_model,
            usage=ModelUsage(
                input_tokens=50, output_tokens=20, reasoning_tokens=5, total_tokens=70
            ),
            duration_ms=800,
        )


model = BrowserModel()
discovery_model = DiscoveryModel(delay=0.3)
training_model = TrainingModel()
app = create_app(
    settings,
    model,
    discovery_model,
    training_model=training_model,
    prepare_environment=prepare_training_environment,
)


@app.get("/test-training")
async def training_calls():
    return {"calls": training_model.calls}


@app.post("/test-training")
async def training_mode(
    mode: Literal["success", "repair", "baseline_failure"] = "success",
    delay: float = 0.01,
):
    training_model.mode = mode
    training_model.delay = max(0.01, min(delay, 2))
    return {"mode": mode}


@app.get("/test-discovery")
async def discovery_calls():
    return {"calls": discovery_model.calls}


@app.post("/test-discovery")
async def discovery_mode(mode: Literal["success", "conflict", "questions_first"]):
    discovery_model.mode = mode
    return {"mode": mode}


@app.get("/test-model")
async def model_calls():
    return {"calls": model.calls}


@app.post("/test-model")
async def model_mode(mode: Literal["success", "permissions"]):
    model.mode = mode
    return {"mode": mode}


uvicorn.run(app, host="127.0.0.1", port=8047, access_log=False)
