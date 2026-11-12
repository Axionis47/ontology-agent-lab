"""Saved training cases, execution limits, and application views."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrainingCaseInput(Strict):
    query: str = Field(min_length=1, max_length=16000)
    tool_ids: list[UUID] = Field(min_length=1, max_length=100)
    task_success: str = Field(min_length=1, max_length=8000)

    @field_validator("query", "task_success")
    @classmethod
    def nonempty(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Enter text.")
        return value

    @field_validator("tool_ids")
    @classmethod
    def unique_tools(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Select each tool once.")
        return value


class TrainingCase(TrainingCaseInput):
    id: UUID
    task_id: UUID
    agent_id: UUID
    created_at: datetime
    updated_at: datetime


class TrainingLimits(Strict):
    cost_usd: Decimal = Field(default=Decimal("1"), gt=0, le=10, decimal_places=6)
    model_calls: int = Field(default=40, ge=1, le=200)
    mcp_calls: int = Field(default=30, ge=1, le=200)
    max_steps: int = Field(default=12, ge=1, le=50)
    max_rounds: int = Field(default=3, ge=1, le=10)
    active_seconds: int = Field(default=600, ge=1, le=7200)


class TrainingStart(Strict):
    request_id: UUID
    discovery_run_id: UUID | None = None
    environment_ref: str | None = Field(default=None, max_length=200)
    limits: TrainingLimits = Field(default_factory=TrainingLimits)


class InferenceStart(Strict):
    request_id: UUID
    accepted_candidate_id: UUID | None = None
    query: str = Field(min_length=1, max_length=16000)
    tool_ids: list[UUID] = Field(min_length=1, max_length=100)
    limits: TrainingLimits = Field(default_factory=TrainingLimits)


class View(BaseModel):
    model_config = ConfigDict(extra="ignore")


class TrainingRun(View):
    id: UUID
    task_id: UUID
    agent_id: UUID
    mode: Literal["training", "inference"]
    status: Literal["running", "stopping", "completed", "stopped", "failed", "interrupted"]
    stage: str
    message: str
    discovery_run_id: UUID | None
    input_digest: str
    cases: list[dict[str, Any]]
    limits: TrainingLimits
    environment_ref: str | None
    evaluator_version: str
    accepted_candidate_id: UUID | None
    model_calls: int = 0
    mcp_calls: int = 0
    accounted_usd: float = 0
    created_at: datetime
    updated_at: datetime


class TrainingCandidate(View):
    id: UUID
    run_id: UUID
    digest: str
    payload: dict[str, Any]
    patch: dict[str, Any] | None
    status: Literal["provisional", "accepted", "rejected"]
    decision: dict[str, Any]
    created_at: datetime


class TrainingEpisode(View):
    id: UUID
    run_id: UUID
    case_id: UUID
    case_snapshot: dict[str, Any]
    candidate_id: UUID | None
    round_index: int
    stage: Literal["baseline", "harness", "inference"]
    status: str
    environment_ref: str | None
    result: dict[str, Any]
    evaluation: dict[str, Any] | None
    created_at: datetime
    finished_at: datetime | None


class TrainingEvent(View):
    sequence: int
    id: UUID
    run_id: UUID
    episode_id: UUID | None
    kind: str
    message: str
    data: dict[str, Any]
    created_at: datetime


class TrainingDetail(Strict):
    run: TrainingRun
    episodes: list[TrainingEpisode]
    candidates: list[TrainingCandidate]
    events: list[TrainingEvent]


class TrainingOverview(Strict):
    cases: list[TrainingCase]
    runs: list[TrainingRun]
    has_more: bool = False
    accepted_candidate: TrainingCandidate | None
    ready: bool
    message: str
    inference_ready: bool = False
    inference_message: str = "Train an accepted version 3 kernel before inference."
    inference_tool_ids: list[str] = Field(default_factory=list)
