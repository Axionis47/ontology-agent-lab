from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class User(BaseModel):
    id: str
    name: str


class TaskInput(Input):
    name: str = Field(min_length=1, max_length=100)
    objective: str = Field(min_length=1, max_length=5000)


class Task(TaskInput):
    id: UUID
    created_at: datetime


class AgentInput(Input):
    name: str = Field(min_length=1, max_length=100)
    responsibilities: str = Field(min_length=1, max_length=10000)


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
    available: bool


class ToolSelection(Input):
    tool_ids: list[UUID] = Field(max_length=2000)


class TokenInput(Input):
    token: str = Field(min_length=1, max_length=16000)


class Problem(BaseModel):
    detail: str
