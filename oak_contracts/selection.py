"""Deterministic offer fixture projection and computation, without provider access."""

import copy
from typing import Any

from .models import ContractError, OfferResult, SelectionRequest, SelectionResult, ToolObservation

FIELDS = ("max_occupancy", "min_nights", "available", "total_minor", "currency", "price_basis")
PRICE_BASIS = "total_for_requested_stay_including_fees"


def validate_scope(observation: ToolObservation, request: SelectionRequest) -> None:
    arguments = observation.arguments
    if observation.case_id != request.case_id:
        raise ContractError("observation_scope_mismatch")
    for field in ("check_in", "check_out", "party_size"):
        expected = request.model_dump(mode="json")[field]
        if arguments.get(field) != expected or type(arguments.get(field)) is not type(expected):
            raise ContractError("observation_scope_mismatch")
    if observation.tool_id == "fixture.search_offers":
        if arguments.get("city") != request.city:
            raise ContractError("observation_scope_mismatch")
    else:
        if arguments.get("offer_id") != observation.payload.get("offer_id"):
            raise ContractError("observation_identity_mismatch")
        for field in ("check_in", "check_out", "party_size"):
            if observation.payload.get(field) != arguments[field]:
                raise ContractError("observation_scope_mismatch")


def project(previous: dict[str, Any], observation: ToolObservation) -> dict[str, Any]:
    """Known disagreements remain conflicts; null does not erase known evidence."""
    result = copy.deepcopy(previous)
    payload = observation.payload
    if observation.tool_id == "fixture.search_offers":
        records = payload.get("offers")
        if not isinstance(records, list):
            raise ContractError("invalid_source_records")
        result["exhaustive"] = False  # This harness has no validated pagination closure.
    else:
        records = [payload]
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("offer_id"), str):
            raise ContractError("missing_source_identity")
        identity = record["offer_id"]
        offer = result["offers"].setdefault(
            identity, {"fields": {}, "conflicts": [], "sources": {}}
        )
        for field in FIELDS:
            source_field = "total_price" if field == "total_minor" else field
            value = record.get(
                source_field,
                payload.get(source_field) if field in {"currency", "price_basis"} else None,
            )
            if value is None:
                continue
            if field in {"max_occupancy", "min_nights", "total_minor"}:
                if type(value) is not int or value < 0 or (field != "total_minor" and value == 0):
                    raise ContractError("invalid_source_value")
                if field == "total_minor":
                    value *= 100  # This fixture accepts integer source dollars only.
            elif field == "available":
                if type(value) is not bool:
                    raise ContractError("invalid_source_value")
            elif type(value) is not str:
                raise ContractError("invalid_source_value")
            prior = offer["fields"].get(field)
            if field in offer["conflicts"] or (prior is not None and prior != value):
                offer["fields"][field] = None
                if field not in offer["conflicts"]:
                    offer["conflicts"].append(field)
            else:
                offer["fields"][field] = value
            offer["sources"].setdefault(field, []).append(observation.observation_id)
    result["observations"].append(observation.observation_id)
    return result


def check_candidates(
    snapshot: dict[str, Any],
    request: SelectionRequest,
    package_hash: str,
    context_id: str,
    revision: int,
) -> SelectionResult:
    nights = (request.check_out - request.check_in).days
    outputs = []
    for identity, offer in sorted(snapshot["offers"].items()):
        values = offer["fields"]
        unknowns = tuple(field for field in FIELDS if values.get(field) is None)
        violations = []
        checks = {
            "max_occupancy": lambda x: x >= request.party_size,
            "min_nights": lambda x: x <= nights,
            "available": lambda x: x is True,
            "total_minor": lambda x: x <= request.budget_minor,
            "currency": lambda x: x == request.currency,
            "price_basis": lambda x: x == PRICE_BASIS,
        }
        for field, check in checks.items():
            if values.get(field) is not None and not check(values[field]):
                violations.append(field)
        status = "violated" if violations else "unknown" if unknowns else "eligible"
        outputs.append(
            OfferResult(
                offer_id=identity,
                status=status,
                violations=tuple(violations),
                unknowns=unknowns,
                sources=tuple(sorted({sid for ids in offer["sources"].values() for sid in ids})),
            )
        )
    return SelectionResult(
        package_hash=package_hash,
        context_id=context_id,
        revision=revision,
        offers=tuple(outputs),
        exhaustive=snapshot["exhaustive"],
    )
