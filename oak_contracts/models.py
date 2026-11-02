"""Strict contracts for the tested subset of the proposed OaK design."""

import hashlib
import json
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION = "oak-contract-harness/1"
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


def canonical(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class ContractError(Exception):
    """Stable machine code, not a success-shaped fallback."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, serialize_by_alias=True)


class Scope(StrictModel):
    project_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)


class ArtifactRef(StrictModel):
    kind: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    contract_version: Literal["oak-contract-harness/1"] = CONTRACT_VERSION
    producer_version: str = "local-harness-1"


class Package(StrictModel):
    schema_ref: ArtifactRef = Field(alias="schema")
    functions: ArtifactRef
    extractor: ArtifactRef
    operators: ArtifactRef
    functions_schema_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_mode: Literal["optional_functions", "guarded_requirements"]

    @model_validator(mode="after")
    def linked_schema(self):
        if self.functions_schema_hash != self.schema_ref.sha256:
            raise ValueError("function_schema_mismatch")
        if [
            self.schema_ref.kind,
            self.functions.kind,
            self.extractor.kind,
            self.operators.kind,
        ] != [
            "schema",
            "functions",
            "extractor",
            "operators",
        ]:
            raise ValueError("artifact_kind_mismatch")
        return self


GateName = Literal["structure", "coverage", "logic", "projection", "functions", "regression"]
REQUIRED_GATES = frozenset(
    {"structure", "coverage", "logic", "projection", "functions", "regression"}
)


class GateReport(StrictModel):
    candidate_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_hashes: tuple[Hash, ...] = Field(min_length=1)
    gates: dict[GateName, Literal["passed", "failed", "not_run", "error"]]
    receipt_kind: Literal["recorded_test_substitute"] = "recorded_test_substitute"
    issuer: str


class SelectionRequest(StrictModel):
    case_id: str
    city: str
    check_in: date
    check_out: date
    party_size: int = Field(gt=0)
    budget_minor: int = Field(ge=0)
    currency: Literal["USD"]

    @model_validator(mode="after")
    def positive_stay(self):
        if self.check_out <= self.check_in:
            raise ValueError("invalid_stay")
        return self


class ToolObservation(StrictModel):
    observation_id: str
    case_id: str
    tool_id: Literal["fixture.search_offers", "fixture.get_offer_details"]
    tool_version: Literal["0.1.0"]
    call_id: str
    arguments: dict[str, Any]
    invocation_status: Literal["completed"]
    effect_status: Literal["not_applicable"]
    effect_evidence_refs: list[str]
    observed_at: datetime
    media_type: Literal["application/json"]
    payload: dict[str, Any]
    synthetic: Literal[True]

    @model_validator(mode="after")
    def aware_source_time(self):
        if self.observed_at.utcoffset() is None:
            raise ValueError("source_time_requires_timezone")
        return self


class IngestReceipt(StrictModel):
    context_id: str
    observation_id: str
    observation_hash: str
    package_hash: str
    parent_revision: int
    revision: int


class OfferResult(StrictModel):
    offer_id: str
    status: Literal["eligible", "violated", "unknown"]
    violations: tuple[str, ...]
    unknowns: tuple[str, ...]
    sources: tuple[str, ...]


class SelectionResult(StrictModel):
    package_hash: str
    context_id: str
    revision: int
    offers: tuple[OfferResult, ...]
    exhaustive: bool


class Trial(StrictModel):
    assignment_id: str
    selected_offer_id: str | None
    claim: Literal[
        "observed_eligible_offer",
        "no_supported_offer",
        "reservation_completed",
        "globally_cheapest",
    ]
    evidence_ids: tuple[str, ...]


class RepairProposal(StrictModel):
    target_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    changed_semantic_ids: tuple[str, ...]
    kind: Literal["schema", "functions"]
    evidence_ids: tuple[str, ...]


def repair_invalidation(proposal: RepairProposal, current_hash: str, mode: str) -> tuple[str, ...]:
    if mode != "development":
        raise ContractError("held_out_repair_forbidden")
    if proposal.target_hash != current_hash:
        raise ContractError("stale_repair")
    if not proposal.changed_semantic_ids or not proposal.evidence_ids:
        raise ContractError("unsupported_repair")
    if proposal.kind == "schema":
        return ("coverage", "logic", "projection", "functions", "regression")
    return ("functions", "regression")
