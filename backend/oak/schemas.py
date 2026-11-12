from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class User(BaseModel):
    id: str
    name: str


class ScopeExample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    situation: str = Field(min_length=1, max_length=10000)
    expected_behavior: str = Field(min_length=1, max_length=10000)
    prohibited_behavior: str = Field(default="", max_length=10000)

    @field_validator("situation", "expected_behavior")
    @classmethod
    def require_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter text for this field.")
        return value


class TaskScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    responsibilities: str = Field(min_length=1, max_length=10000)
    context_and_rules: str = Field(default="", max_length=10000)
    boundaries: str = Field(default="", max_length=10000)
    success_criteria: str = Field(min_length=1, max_length=10000)
    examples: list[ScopeExample] = Field(default_factory=list)

    @field_validator("responsibilities", "success_criteria")
    @classmethod
    def require_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter text for this field.")
        return value


class TaskInput(Input):
    name: str = Field(min_length=1, max_length=100)
    objective: str = Field(min_length=1, max_length=5000)
    scope: TaskScope | None = None


class Task(TaskInput):
    id: UUID
    created_at: datetime


class AgentInput(Input):
    name: str = Field(min_length=1, max_length=100)
    responsibilities: str = Field(min_length=1, max_length=10000)
    scope: TaskScope | None = None
    tool_ids: list[UUID] | None = Field(default=None, max_length=2000)


class Agent(AgentInput):
    id: UUID
    task_id: UUID
    created_at: datetime
    tool_ids: list[UUID] = Field(default_factory=list)


class ConnectionInput(Input):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=1, max_length=2048)
    auth_mode: Literal["none", "token", "oauth"] = "none"
    token: str | None = Field(default=None, max_length=16000)


class Connection(BaseModel):
    id: UUID
    task_id: UUID
    name: str
    url: str
    auth_mode: Literal["none", "token", "oauth"]
    status: Literal["disconnected", "connecting", "auth_required", "connected", "error"]
    error: str | None
    auth_url: str | None
    refreshed_at: datetime | None


class Tool(BaseModel):
    id: UUID
    task_id: UUID
    connection_id: UUID
    connection_name: str
    name: str
    title: str | None
    description: str
    input_schema: dict
    output_schema: dict | None = None
    annotations: dict | None = None
    available: bool


class ToolSelection(Input):
    tool_ids: list[UUID] = Field(max_length=2000)


class TokenInput(Input):
    token: str = Field(min_length=1, max_length=16000)


class Problem(BaseModel):
    detail: str


class ModelCheckInput(Input):
    request_id: UUID


class ModelUsage(BaseModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    reasoning_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class ModelCheck(BaseModel):
    id: UUID
    model: str
    status: Literal["checking", "connected", "check_failed"]
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    error_code: str | None
    message: str | None
    recovery: str | None
    usage: ModelUsage | None
    accounted_usd: float
    usage_known: bool


class ModelRuntime(BaseModel):
    provider: Literal["Vertex AI"] = "Vertex AI"
    model: str
    location: str
    configured: bool
    status: Literal["not_configured", "not_checked", "checking", "connected", "check_failed"]
    outdated: bool
    last_check: ModelCheck | None
    can_check: bool
    blocked_reason: str | None
    budget_usd: float
    accounted_usd: float
    remaining_usd: float
