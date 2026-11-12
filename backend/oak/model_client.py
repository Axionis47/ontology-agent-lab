"""Obtain validated model output without executing tools."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass

import google.auth
import httpx2
from google.auth.exceptions import DefaultCredentialsError, RefreshError
from google.auth.exceptions import TransportError as GoogleAuthTransportError
from google.genai import Client, errors, types
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ValidationError

from oak.evidence_access import ContextCapacity
from oak.schemas import ModelUsage
from oak.settings import Settings

# The connection prompt and schema fit within this conservative token allowance.
INPUT_TOKEN_LIMIT = 4096
INPUT_BYTE_LIMIT = 1024
logger = logging.getLogger(__name__)

PROBLEMS = {
    "authentication": (
        "Google credentials are missing or expired.",
        "Run gcloud auth application-default login on the backend host, then check again.",
    ),
    "permissions": (
        "Google denied access to the configured project.",
        "Check the project's model permissions, API access, and billing configuration.",
    ),
    "model_unavailable": (
        "The configured model is unavailable.",
        "Check the model ID and location in the backend settings.",
    ),
    "rate_limit": (
        "Google rejected the request because of a quota or rate limit.",
        "Check the project quota. Wait before starting another check.",
    ),
    "timeout": (
        "The model did not respond within the time limit.",
        "Check the network, then try again. The cost reservation remains in use.",
    ),
    "invalid_output": (
        "The model response did not pass validation.",
        "Start another check. If it fails again, inspect the model configuration.",
    ),
    "output_truncated": (
        "The model response reached its output token limit.",
        "Increase the configured output limit or reduce the proposal size before a new run.",
    ),
    "provider_error": (
        "The model service could not complete the check.",
        "Check service availability and the backend network, then try again.",
    ),
    "request_configuration": (
        "Google rejected the model request configuration.",
        "Check the model's supported request parameters on the backend.",
    ),
    "interrupted": (
        "The backend stopped before the check completed.",
        "Start another check. The earlier cost reservation remains in use.",
    ),
}


class ModelFailure(Exception):
    def __init__(
        self,
        code: str,
        usage: ModelUsage | None = None,
        *,
        validation_errors: list[dict] | None = None,
        failed_output=None,
    ):
        self.code, self.usage = code, usage
        self.validation_errors = validation_errors or []
        self.failed_output = failed_output
        super().__init__(PROBLEMS[code][0])


@dataclass
class ModelResult:
    data: BaseModel
    model: str
    usage: ModelUsage | None
    duration_ms: int
    request: dict | None = None


@dataclass(frozen=True)
class GenerationLimits:
    input_tokens: int
    output_tokens: int
    timeout: float


def provider_schema(schema):
    """Reduce provider grammar complexity. Pydantic enforces all local bounds."""
    return _provider_schema(schema)


def _recursive_schema(schema):
    if not isinstance(schema, dict):
        return False
    definitions = schema.get("$defs", {})

    def references(value):
        if isinstance(value, list):
            return set().union(*(references(item) for item in value))
        if not isinstance(value, dict):
            return set()
        found = set()
        reference = value.get("$ref", "")
        if reference.startswith("#/$defs/"):
            found.add(reference.removeprefix("#/$defs/"))
        for child in value.values():
            found.update(references(child))
        return found

    edges = {name: references(value) for name, value in definitions.items()}

    def reaches(start, target, visited):
        if start == target:
            return True
        if start in visited:
            return False
        return any(reaches(child, target, visited | {start}) for child in edges.get(start, ()))

    return any(
        reaches(child, name, set()) for name, children in edges.items() for child in children
    )


def _provider_schema(schema):
    if isinstance(schema, list):
        return [_provider_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    result = {
        key: {name: _provider_schema(child) for name, child in value.items()}
        if key in {"properties", "$defs", "definitions", "patternProperties"}
        else _provider_schema(value)
        for key, value in schema.items()
        if key
        not in {
            "title",
            "default",
            "minLength",
            "maxLength",
            "minItems",
            "maxItems",
            "discriminator",
            "pattern",
        }
    }
    if "const" in result:
        result["enum"] = [result.pop("const")]
    if "oneOf" in result:
        result["anyOf"] = result.pop("oneOf")
    if "properties" in result:
        result["required"] = list(result["properties"])
    return result


def response_usage(response) -> ModelUsage | None:
    usage = response.usage_metadata
    if usage is None or usage.prompt_token_count is None or usage.total_token_count is None:
        return None
    prompt = usage.prompt_token_count
    output = (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)
    if prompt < 0 or output < 0 or usage.total_token_count < prompt + output:
        return None
    return ModelUsage(
        input_tokens=prompt,
        output_tokens=max(output, usage.total_token_count - prompt),
        reasoning_tokens=usage.thoughts_token_count or 0,
        total_tokens=usage.total_token_count,
    )


def _failed_output(text):
    """Retain bounded proposal evidence for a subsequent validated generation."""
    if len(text) > 100_000:
        return text[:100_000]

    def invalid_constant(value):
        raise ValueError("The proposal contains a non-JSON constant.")

    try:
        return json.loads(text, parse_constant=invalid_constant)
    except (ValueError, RecursionError):
        return text


class GeminiClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _client(self):
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return Client(
            vertexai=True,
            credentials=credentials,
            project=self.settings.gemini_project,
            location=self.settings.gemini_location,
            http_options=types.HttpOptions(
                api_version="v1",
                timeout=int(self.settings.gemini_timeout * 1000),
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )

    async def turn(self, messages, tools, *, limits: GenerationLimits, instructions="") -> dict:
        """Return one native model turn. The host alone dispatches function calls."""
        contents = [types.Content.model_validate(message) for message in messages]
        declarations = [
            types.FunctionDeclaration(
                name=tool["name"],
                description=tool.get("description", ""),
                parameters_json_schema=tool["input_schema"],
            )
            for tool in tools
        ]
        native_tools = [types.Tool(function_declarations=declarations)] if declarations else []
        if len(json.dumps(messages, ensure_ascii=True).encode()) > 1_000_000:
            raise ContextCapacity("The model conversation exceeds the supported context capacity.")
        client = None
        started = time.monotonic()
        try:
            async with asyncio.timeout(limits.timeout):
                client = await asyncio.to_thread(self._client)
                counted = await client.aio.models.count_tokens(
                    model=self.settings.gemini_model,
                    contents=contents,
                    config=types.CountTokensConfig(
                        system_instruction=instructions, tools=native_tools
                    ),
                )
                if counted.total_tokens is None or counted.total_tokens > limits.input_tokens:
                    raise ContextCapacity(
                        "The complete model input exceeds the training token limit."
                    )
                config = types.GenerateContentConfig(
                    system_instruction=instructions,
                    tools=native_tools,
                    max_output_tokens=limits.output_tokens,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    http_options=types.HttpOptions(timeout=int(limits.timeout * 1000)),
                )
                native_request = {
                    "counted_input_tokens": counted.total_tokens,
                    "model": self.settings.gemini_model,
                    "contents": [
                        item.model_dump(mode="json", exclude_none=True) for item in contents
                    ],
                    "config": config.model_dump(mode="json", exclude_none=True),
                }
                response = await client.aio.models.generate_content(
                    model=self.settings.gemini_model,
                    contents=contents,
                    config=config,
                )
            usage = response_usage(response)
            candidates = response.candidates or []
            if candidates and candidates[0].finish_reason == types.FinishReason.MAX_TOKENS:
                raise ModelFailure("output_truncated", usage)
            if (
                len(candidates) != 1
                or candidates[0].finish_reason != types.FinishReason.STOP
                or candidates[0].content is None
            ):
                raise ModelFailure("invalid_output", usage)
            content = candidates[0].content
            calls = []
            for index, part in enumerate(content.parts or []):
                if part.function_call is not None:
                    call = part.function_call
                    if not call.name or not isinstance(call.args, dict):
                        raise ModelFailure("invalid_output", usage)
                    calls.append(
                        {"id": call.id, "name": call.name, "arguments": call.args, "index": index}
                    )
            return {
                # Preserve provider parts, including signatures, for the next native request.
                "content": content.model_dump(mode="json", exclude_none=True),
                "text": "".join(
                    part.text or "" for part in content.parts or [] if not part.thought
                ),
                "tool_calls": calls,
                "usage": usage.model_dump(mode="json") if usage else None,
                "model": response.model_version or self.settings.gemini_model,
                "duration_ms": round((time.monotonic() - started) * 1000),
                "request": native_request,
            }
        except (DefaultCredentialsError, RefreshError):
            raise ModelFailure("authentication") from None
        except GoogleAuthTransportError:
            raise ModelFailure("provider_error") from None
        except (TimeoutError, httpx2.TimeoutException):
            raise ModelFailure("timeout") from None
        except errors.APIError as exc:
            code = {
                400: "request_configuration",
                401: "authentication",
                403: "permissions",
                404: "model_unavailable",
                429: "rate_limit",
            }.get(exc.code, "provider_error")
            raise ModelFailure(code) from None
        except httpx2.TransportError:
            raise ModelFailure("provider_error") from None
        finally:
            if client is not None:
                await client.aio.aclose()

    async def generate(
        self,
        instructions: str,
        data: dict,
        response_schema: type[BaseModel],
        *,
        limits: GenerationLimits | None = None,
    ) -> ModelResult:
        payload = json.dumps(data, ensure_ascii=True)
        contents = [types.Content(role="user", parts=[types.Part(text=payload)])]
        local_schema = response_schema.model_json_schema()
        recursive = _recursive_schema(local_schema)
        schema = None if recursive else provider_schema(local_schema)
        if recursive:
            instructions += (
                "\nReturn a JSON value that satisfies the complete schema below. "
                "Return nested JSON objects and arrays, not flattened key/value lists. "
                "All nested fields, operator tags, "
                "types, required operands, and bounds in this complete schema are mandatory.\n"
                + json.dumps(local_schema, ensure_ascii=True, separators=(",", ":"))
            )
        if schema is not None:
            Draft202012Validator.check_schema(schema)
        input_bytes = len((instructions + payload + json.dumps(schema)).encode())
        if input_bytes > (1_000_000 if limits else INPUT_BYTE_LIMIT):
            raise ContextCapacity("The model input exceeds the supported context capacity.")
        started = time.monotonic()
        client = None
        try:
            async with asyncio.timeout(limits.timeout if limits else self.settings.gemini_timeout):
                client = await asyncio.to_thread(self._client)
                if limits:
                    counted = await client.aio.models.count_tokens(
                        model=self.settings.gemini_model,
                        contents=contents,
                        config=types.CountTokensConfig(
                            system_instruction=instructions,
                            generation_config=types.GenerationConfig(response_json_schema=schema),
                        ),
                    )
                    schema_margin = len(json.dumps(schema, ensure_ascii=True).encode()) + 256
                    if (
                        counted.total_tokens is None
                        or counted.total_tokens + schema_margin > limits.input_tokens
                    ):
                        raise ContextCapacity(
                            "The complete model input exceeds the discovery token limit."
                        )
                config = types.GenerateContentConfig(
                    system_instruction=instructions,
                    response_mime_type="application/json",
                    response_json_schema=schema,
                    max_output_tokens=limits.output_tokens
                    if limits
                    else self.settings.gemini_max_output_tokens,
                    http_options=types.HttpOptions(timeout=int(limits.timeout * 1000))
                    if limits
                    else None,
                    thinking_config=types.ThinkingConfig(thinking_level="LOW"),
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                )
                response = await client.aio.models.generate_content(
                    model=self.settings.gemini_model,
                    contents=contents,
                    config=config,
                )
            usage = response_usage(response)
            candidates = response.candidates or []
            if candidates and candidates[0].finish_reason == types.FinishReason.MAX_TOKENS:
                raise ModelFailure("output_truncated", usage)
            if len(candidates) != 1 or candidates[0].finish_reason != types.FinishReason.STOP:
                raise ModelFailure("invalid_output", usage)
            parts = candidates[0].content.parts if candidates[0].content else []
            if not parts or any(part.function_call is not None for part in parts):
                raise ModelFailure("invalid_output", usage)
            text = "".join(part.text or "" for part in parts if not part.thought)
            try:
                validated = response_schema.model_validate_json(text, strict=True)
            except ValidationError as error:
                failures = [
                    {"loc": list(item["loc"]), "type": item["type"], "msg": item["msg"]}
                    for item in error.errors(
                        include_url=False, include_context=False, include_input=False
                    )[:20]
                ]
                raise ModelFailure(
                    "invalid_output",
                    usage,
                    validation_errors=failures,
                    failed_output=_failed_output(text),
                ) from None
            return ModelResult(
                data=validated,
                model=response.model_version or self.settings.gemini_model,
                usage=usage,
                duration_ms=round((time.monotonic() - started) * 1000),
                request={
                    "counted_input_tokens": counted.total_tokens if limits else None,
                    "model": self.settings.gemini_model,
                    "contents": [
                        item.model_dump(mode="json", exclude_none=True) for item in contents
                    ],
                    "config": config.model_dump(mode="json", exclude_none=True),
                },
            )
        except (DefaultCredentialsError, RefreshError):
            raise ModelFailure("authentication") from None
        except GoogleAuthTransportError:
            raise ModelFailure("provider_error") from None
        except (TimeoutError, httpx2.TimeoutException):
            raise ModelFailure("timeout") from None
        except errors.APIError as exc:
            logger.warning("Gemini request failed with HTTP status %s.", exc.code)
            code = {
                400: "request_configuration",
                401: "authentication",
                403: "permissions",
                404: "model_unavailable",
                429: "rate_limit",
            }.get(exc.code, "provider_error")
            raise ModelFailure(code) from None
        except httpx2.TransportError:
            raise ModelFailure("provider_error") from None
        finally:
            if client is not None:
                await client.aio.aclose()
