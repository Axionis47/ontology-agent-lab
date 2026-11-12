"""Typed discovery proposals and saved application views."""

import json
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from oak.schemas import ModelUsage


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DiscoveryLimits(Strict):
    cost_usd: Decimal = Field(gt=0, le=100, decimal_places=6)
    mcp_calls: int = Field(default=12, ge=1, le=200)
    model_calls: int = Field(default=14, ge=1, le=200)
    active_seconds: int = Field(default=600, ge=1, le=7200)
    clarification_rounds: int = Field(default=2, ge=0, le=20)


class DiscoveryStart(Strict):
    request_id: UUID
    environment: str = Field(min_length=1, max_length=200)
    limits: DiscoveryLimits


class DiscoveryResume(Strict):
    request_id: UUID
    expected_revision: int = Field(ge=1)
    answers: dict[UUID, str] = Field(default_factory=dict, max_length=3)
    limits: DiscoveryLimits | None = None


class EvidenceRef(Strict):
    source: Literal["input", "artifact", "question"]
    id: str
    path: str = ""


class QuestionProposal(Strict):
    key: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=2000)
    why_needed: str = Field(min_length=1, max_length=2000)
    options: list[str] = Field(default_factory=list, max_length=6)
    evidence: list[EvidenceRef] = Field(min_length=1, max_length=20)
    affected: list[str] = Field(default_factory=list, max_length=30)
    unresolved_detail: str = ""


class Gap(Strict):
    id: str
    message: str
    blocking: bool
    evidence: list[EvidenceRef] = Field(default_factory=list)


class ConfirmationMatch(Strict):
    written_source: Literal["request", "response"] = "response"
    written_path: str = Field(
        description=(
            "JSON Pointer into saved arguments for request, "
            "or the observation payload for response."
        )
    )
    read_path: str = Field(
        description="JSON Pointer into the new read observation payload, starting with /data/."
    )


class ProbeDecision(Strict):
    action: Literal["call", "questions", "finish", "conflict"]
    purpose: str
    tool_id: str | None = None
    arguments_json: str = Field(default="{}", max_length=64000)
    effect: Literal["read", "write", "unknown"] = "unknown"
    evidence: list[EvidenceRef] = Field(default_factory=list)
    questions: list[QuestionProposal] = Field(default_factory=list, max_length=3)
    gaps: list[Gap] = Field(default_factory=list)
    conflict: str | None = None
    confirmation_for: str | None = None
    confirmation_matches: list[ConfirmationMatch] = Field(default_factory=list, max_length=20)

    @field_validator("arguments_json")
    @classmethod
    def validate_arguments(cls, value):
        if not isinstance(json.loads(value), dict):
            raise ValueError("Probe arguments must be a JSON object.")
        return value

    @property
    def arguments(self):
        return json.loads(self.arguments_json)


class Requirement(Strict):
    id: str
    statement: str
    evidence: list[EvidenceRef] = Field(min_length=1)
    tool_ids: list[str] = Field(default_factory=list)
    ambiguity: str | None = None


class RequirementsProposal(Strict):
    requirements: list[Requirement] = Field(min_length=1, max_length=200)
    questions: list[QuestionProposal] = Field(default_factory=list, max_length=3)
    gaps: list[Gap] = Field(default_factory=list, max_length=100)
    conflict: str | None = None


class PropertyProposal(Strict):
    name: str
    type: Literal["string", "integer", "number", "boolean", "object", "array", "decimal"]
    unit: str | None = None
    item_type: Literal["string", "integer", "boolean", "decimal"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class EntityProposal(Strict):
    id: str
    name: str
    properties: list[PropertyProposal] = Field(min_length=1, max_length=100)
    identity_keys: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(min_length=1)


class SourceBinding(Strict):
    id: str
    tool_id: str
    entity_id: str
    property: str
    source: EvidenceRef
    support: Literal["declared", "observed"]
    coverage: Literal["sample", "unknown"]


class RelationProposal(Strict):
    id: str
    name: str
    from_entity: str
    to_entity: str
    from_property: str
    to_property: str
    requirement_ids: list[str] = Field(min_length=1)
    binding_ids: list[str] = Field(min_length=2)


class OperationProposal(Strict):
    id: str
    tool_id: str
    effect: Literal["read", "write", "unknown"]
    requirement_ids: list[str] = Field(min_length=1)
    prerequisites: list[str]
    outputs: str
    confirmation_tool_id: str | None = None
    limitations: list[str]


class SchemaProposal(Strict):
    entities: list[EntityProposal] = Field(default_factory=list, max_length=100)
    bindings: list[SourceBinding] = Field(default_factory=list, max_length=300)
    relations: list[RelationProposal] = Field(default_factory=list, max_length=200)
    operations: list[OperationProposal] = Field(default_factory=list, max_length=200)
    gaps: list[Gap] = Field(default_factory=list, max_length=100)


class ClarificationReview(Strict):
    compatible: bool
    conflict: str | None
    questions: list[QuestionProposal] = Field(default_factory=list, max_length=3)


class DiscoveryArtifact(BaseModel):
    id: UUID
    kind: str
    title: str
    digest: str
    payload: dict
    created_at: datetime


class DiscoveryQuestion(BaseModel):
    id: UUID
    round: int
    question: QuestionProposal
    answer: str | None
    answered_by: str | None
    answered_at: datetime | None


class DiscoveryEvent(BaseModel):
    sequence: int
    kind: str
    message: str
    data: dict
    created_at: datetime


class DiscoveryCall(BaseModel):
    id: UUID
    kind: str
    purpose: str
    tool_id: UUID | None
    effect: str | None
    status: str
    request: dict
    response_artifact_id: UUID | None
    error_code: str | None
    duration_ms: int | None
    usage: ModelUsage | None
    reserved_nanos: int
    accounted_nanos: int
    created_at: datetime


class DiscoveryRun(BaseModel):
    id: UUID
    task_id: UUID
    agent_id: UUID
    environment: str
    status: Literal["running", "pausing", "paused", "completed", "stopped"]
    stage: str
    reason: str | None
    message: str | None
    revision: int
    limits: DiscoveryLimits
    active_ms: int
    clarification_rounds: int
    created_at: datetime
    updated_at: datetime
    model_calls: int = 0
    mcp_calls: int = 0
    accounted_usd: float = 0
    reserved_usd: float = 0
    remaining_usd: float = 0
    outdated: bool = False


class DiscoveryDetail(BaseModel):
    run: DiscoveryRun
    inputs: dict
    questions: list[DiscoveryQuestion]
    events: list[DiscoveryEvent]
    artifacts: list[DiscoveryArtifact]
    calls: list[DiscoveryCall]
    requirements: RequirementsProposal | None = None
    schema_proposal: SchemaProposal | None = None


class DiscoveryOverview(BaseModel):
    ready: bool
    blocked_reason: str | None
    ceilings: DiscoveryLimits
    runs: list[DiscoveryRun]
    has_more: bool
