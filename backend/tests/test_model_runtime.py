import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from google.auth.exceptions import DefaultCredentialsError, RefreshError
from google.genai import errors, types

from oak.main import create_app
from oak.model_client import GeminiClient, ModelFailure, ModelResult
from oak.model_runtime import CHECK_INPUT, CHECK_INSTRUCTIONS, ConnectionReply
from oak.schemas import ModelUsage
from oak.settings import Settings


class FakeModel:
    def __init__(self):
        self.calls = []
        self.failure = None
        self.hold = False

    async def generate(self, instructions, data, response_schema):
        self.calls.append((instructions, data, response_schema))
        while self.hold:
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.03)
        if self.failure:
            raise self.failure
        return ModelResult(
            data=ConnectionReply(status="ok"),
            model="gemini-3.8-flash",
            usage=ModelUsage(
                input_tokens=50, output_tokens=20, reasoning_tokens=5, total_tokens=70
            ),
            duration_ms=30,
        )


@pytest.fixture
def runtime(settings):
    config = settings.model_copy(
        update={
            "gemini_project": "test-project",
            "gemini_check_budget_usd": Decimal("0.10"),
        }
    )
    with psycopg.connect(config.database_url) as db:
        db.execute("TRUNCATE model_runtime_checks")
    fake = FakeModel()
    with TestClient(create_app(config, fake), headers={"X-Oak-Key": config.api_key}) as client:
        yield client, fake, config


def completed(client):
    for _ in range(200):
        state = client.get("/api/model-runtime").json()
        if state["status"] != "checking":
            return state
        time.sleep(0.01)
    pytest.fail("The check did not finish.")


def test_connection_check_persists_and_get_never_calls_model(runtime):
    client, fake, config = runtime
    for _ in range(3):
        assert client.get("/api/model-runtime").json()["status"] == "not_checked"
    assert not fake.calls
    request = {"request_id": str(uuid4())}
    assert client.post("/api/model-runtime/check", json=request).status_code == 202
    state = completed(client)
    assert state["status"] == "connected"
    assert state["last_check"]["usage"]["reasoning_tokens"] == 5
    assert state["last_check"]["duration_ms"] >= 0
    assert 0 < state["accounted_usd"] < 0.001
    assert fake.calls == [(CHECK_INSTRUCTIONS, CHECK_INPUT, ConnectionReply)]
    assert client.post("/api/model-runtime/check", json=request).status_code == 202
    for _ in range(3):
        assert client.get("/api/model-runtime").json() == state
    assert len(fake.calls) == 1
    second_fake = FakeModel()
    with TestClient(
        create_app(config, second_fake), headers={"X-Oak-Key": config.api_key}
    ) as second:
        assert second.get("/api/model-runtime").json() == state
    assert not second_fake.calls


def test_concurrent_checks_share_one_reservation(runtime):
    client, fake, _ = runtime
    fake.hold = True
    request = {"request_id": str(uuid4())}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(lambda _: client.post("/api/model-runtime/check", json=request), range(2))
        )
    assert all(response.status_code == 202 for response in responses)
    assert (
        client.post("/api/model-runtime/check", json={"request_id": str(uuid4())}).status_code
        == 409
    )
    snapshot = client.get("/api/model-runtime").json()
    assert snapshot["status"] == "checking"
    assert snapshot["accounted_usd"] == pytest.approx(0.036864)
    fake.hold = False
    assert completed(client)["status"] == "connected"
    assert len(fake.calls) == 1


@pytest.mark.parametrize(
    "code",
    [
        "authentication",
        "permissions",
        "model_unavailable",
        "rate_limit",
        "timeout",
        "invalid_output",
    ],
)
def test_failures_are_visible_and_recoverable(runtime, code):
    client, fake, _ = runtime
    fake.failure = ModelFailure(code)
    client.post("/api/model-runtime/check", json={"request_id": str(uuid4())})
    state = completed(client)
    assert state["status"] == "check_failed"
    assert state["last_check"]["error_code"] == code
    assert state["last_check"]["recovery"]
    assert not state["last_check"]["usage_known"]
    assert state["accounted_usd"] == pytest.approx(0.036864)
    fake.failure = None
    client.post("/api/model-runtime/check", json={"request_id": str(uuid4())})
    assert completed(client)["status"] == "connected"


def test_invalid_output_keeps_observed_usage(runtime):
    client, fake, _ = runtime
    fake.failure = ModelFailure(
        "invalid_output",
        ModelUsage(
            input_tokens=20,
            output_tokens=10,
            reasoning_tokens=0,
            total_tokens=30,
        ),
    )
    client.post("/api/model-runtime/check", json={"request_id": str(uuid4())})
    state = completed(client)
    assert state["status"] == "check_failed"
    assert state["last_check"]["usage_known"]
    assert 0 < state["accounted_usd"] < 0.001


def test_budget_survives_configuration_changes(runtime):
    client, fake, config = runtime
    client.post("/api/model-runtime/check", json={"request_id": str(uuid4())})
    completed(client)
    with psycopg.connect(config.database_url) as db:
        db.execute("UPDATE model_runtime_checks SET accounted_nanos=100000000")
    changed = config.model_copy(update={"gemini_timeout": 26})
    with TestClient(create_app(changed, fake), headers={"X-Oak-Key": config.api_key}) as second:
        state = second.get("/api/model-runtime").json()
        assert state["outdated"]
        assert state["status"] == "not_checked"
        assert not state["can_check"]
        assert state["remaining_usd"] == 0
        assert (
            second.post("/api/model-runtime/check", json={"request_id": str(uuid4())}).status_code
            == 409
        )
    assert len(fake.calls) == 1


def test_configuration_change_requires_a_new_check(runtime):
    client, fake, config = runtime
    request = {"request_id": str(uuid4())}
    client.post("/api/model-runtime/check", json=request)
    completed(client)
    changed = config.model_copy(update={"gemini_project": "another-project"})
    with TestClient(create_app(changed, fake), headers={"X-Oak-Key": config.api_key}) as second:
        state = second.get("/api/model-runtime").json()
        assert state["outdated"] and state["status"] == "not_checked"
        assert state["last_check"]["status"] == "connected"
        assert second.post("/api/model-runtime/check", json=request).status_code == 409
        second.post("/api/model-runtime/check", json={"request_id": str(uuid4())})
        assert not completed(second)["outdated"]


def test_interrupted_checks_keep_their_reservation(runtime):
    client, fake, config = runtime
    client.post("/api/model-runtime/check", json={"request_id": str(uuid4())})
    completed(client)
    with psycopg.connect(config.database_url) as db:
        db.execute(
            "UPDATE model_runtime_checks SET status='checking',usage=NULL,accounted_nanos=reserved_nanos"
        )
    with TestClient(create_app(config, fake), headers={"X-Oak-Key": config.api_key}) as second:
        state = second.get("/api/model-runtime").json()
        assert state["status"] == "check_failed"
        assert state["last_check"]["error_code"] == "interrupted"
        assert state["accounted_usd"] == pytest.approx(0.036864)
    assert len(fake.calls) == 1


def test_api_boundaries_and_health(runtime):
    client, fake, config = runtime
    assert client.get("/api/model-runtime", headers={"X-Oak-Key": "wrong"}).status_code == 401
    assert client.get("/api/model-runtime", headers={"X-Oak-User": "unknown"}).status_code == 401
    assert (
        client.post(
            "/api/model-runtime/check", json={"request_id": str(uuid4()), "prompt": "private task"}
        ).status_code
        == 422
    )
    assert client.get("/health").status_code == 200
    missing = config.model_copy(update={"gemini_project": ""})
    with TestClient(create_app(missing, fake), headers={"X-Oak-Key": config.api_key}) as second:
        assert second.get("/api/model-runtime").json()["status"] == "not_configured"
        assert (
            second.post("/api/model-runtime/check", json={"request_id": str(uuid4())}).status_code
            == 409
        )
        assert second.get("/health").status_code == 200
    assert not fake.calls


def sdk_response(text='{"status":"ok"}'):
    return types.GenerateContentResponse(
        model_version="gemini-3.8-flash",
        candidates=[
            types.Candidate(
                content=types.Content(parts=[types.Part(text=text)]), finish_reason="STOP"
            )
        ],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=30,
            candidates_token_count=8,
            thoughts_token_count=4,
            total_token_count=42,
        ),
    )


@pytest.fixture
def sdk(monkeypatch):
    model = GeminiClient(Settings(_env_file=None, gemini_project="test-project"))
    generate = AsyncMock(return_value=sdk_response())
    close = AsyncMock()
    monkeypatch.setattr(
        model,
        "_client",
        lambda: SimpleNamespace(
            aio=SimpleNamespace(
                models=SimpleNamespace(generate_content=generate),
                aclose=close,
            )
        ),
    )
    return model, generate, close


async def test_sdk_structured_output_and_usage(sdk):
    model, generate, close = sdk
    result = await model.generate(CHECK_INSTRUCTIONS, CHECK_INPUT, ConnectionReply)
    assert result.data.status == "ok"
    assert result.usage.output_tokens == 12
    config = generate.call_args.kwargs["config"]
    assert config.tools is None
    assert config.automatic_function_calling.disable
    assert config.max_output_tokens == 4096
    assert config.thinking_config.thinking_level == "LOW"
    assert config.candidate_count is None
    assert config.response_json_schema["additionalProperties"] is False
    close.assert_awaited_once()


@pytest.mark.parametrize("text", ['{"status":"wrong"}', '{"status":"ok","extra":true}', "not JSON"])
async def test_sdk_rejects_invalid_output(sdk, text):
    model, generate, _ = sdk
    generate.return_value = sdk_response(text)
    with pytest.raises(ModelFailure) as error:
        await model.generate(CHECK_INSTRUCTIONS, CHECK_INPUT, ConnectionReply)
    assert error.value.code == "invalid_output"
    assert error.value.usage.total_tokens == 42


@pytest.mark.parametrize(
    "exception,code",
    [
        (DefaultCredentialsError("secret"), "authentication"),
        (RefreshError("secret"), "authentication"),
        (errors.ClientError(400, {"error": {"message": "secret"}}), "request_configuration"),
        (errors.ClientError(403, {"error": {"message": "secret"}}), "permissions"),
        (errors.ClientError(404, {"error": {"message": "secret"}}), "model_unavailable"),
        (errors.ClientError(429, {"error": {"message": "secret"}}), "rate_limit"),
        (TimeoutError("secret"), "timeout"),
    ],
)
async def test_sdk_error_mapping(sdk, exception, code):
    model, generate, _ = sdk
    generate.side_effect = exception
    with pytest.raises(ModelFailure) as error:
        await model.generate(CHECK_INSTRUCTIONS, CHECK_INPUT, ConnectionReply)
    assert error.value.code == code
    assert "secret" not in str(error.value)
    assert generate.await_count == 1


def test_sdk_uses_adc_and_disables_retries(monkeypatch):
    from oak import model_client

    captured = {}
    credentials = object()
    monkeypatch.setattr(model_client.google.auth, "default", lambda **_: (credentials, None))
    monkeypatch.setattr(model_client, "Client", lambda **kwargs: captured.update(kwargs))
    GeminiClient(Settings(_env_file=None, gemini_project="test-project"))._client()
    assert captured["credentials"] is credentials
    assert captured["vertexai"] is True
    assert captured["http_options"].retry_options.attempts == 1
    assert captured["http_options"].timeout == 25000


async def test_large_input_never_reaches_provider(sdk):
    model, generate, _ = sdk
    with pytest.raises(ValueError):
        await model.generate(CHECK_INSTRUCTIONS, {"text": "x" * 2000}, ConnectionReply)
    assert not generate.called


@pytest.mark.parametrize("tokens,allowed", [(100, True), (10001, False)])
async def test_discovery_counts_full_input_before_generation(monkeypatch, tokens, allowed):
    from oak.model_client import GenerationLimits

    model = GeminiClient(Settings(_env_file=None, gemini_project="test-project"))
    generate = AsyncMock(return_value=sdk_response())
    count = AsyncMock(return_value=types.CountTokensResponse(total_tokens=tokens))
    close = AsyncMock()
    monkeypatch.setattr(
        model,
        "_client",
        lambda: SimpleNamespace(
            aio=SimpleNamespace(
                models=SimpleNamespace(generate_content=generate, count_tokens=count),
                aclose=close,
            )
        ),
    )
    if allowed:
        await model.generate(
            "Instructions",
            {"text": "data"},
            ConnectionReply,
            limits=GenerationLimits(10000, 16384, 30),
        )
        assert generate.call_args.kwargs["config"].max_output_tokens == 16384
    else:
        with pytest.raises(ValueError, match="token limit"):
            await model.generate(
                "Instructions",
                {"text": "data"},
                ConnectionReply,
                limits=GenerationLimits(10000, 16384, 30),
            )
        generate.assert_not_called()
    assert count.call_args.kwargs["config"].system_instruction == "Instructions"
    assert count.call_args.kwargs["config"].generation_config.response_json_schema
    close.assert_awaited_once()


async def test_truncated_model_output_reports_usage(sdk):
    model, generate, _ = sdk
    generate.return_value.candidates[0].finish_reason = types.FinishReason.MAX_TOKENS
    with pytest.raises(ModelFailure) as exc:
        await model.generate(CHECK_INSTRUCTIONS, CHECK_INPUT, ConnectionReply)
    assert exc.value.code == "output_truncated"
    assert exc.value.usage.total_tokens == 42


def test_provider_schema_preserves_field_names_and_all_proposal_contracts():
    from jsonschema import Draft202012Validator
    from pydantic import BaseModel

    from oak.discovery_schemas import (
        ClarificationReview,
        ProbeDecision,
        RequirementsProposal,
        SchemaProposal,
    )
    from oak.model_client import provider_schema

    class Fields(BaseModel):
        title: str
        properties: list[str]
        default: str

    transformed = provider_schema(Fields.model_json_schema())
    assert set(transformed["properties"]) == {"title", "properties", "default"}
    for model in [Fields, ClarificationReview, ProbeDecision, RequirementsProposal, SchemaProposal]:
        Draft202012Validator.check_schema(provider_schema(model.model_json_schema()))
