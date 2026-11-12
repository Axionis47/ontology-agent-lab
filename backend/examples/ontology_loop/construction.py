"""Generate, review, repair, and freeze a small operational ontology."""

import asyncio
import hashlib
import json
import random
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .kernel import (
    FIELDS,
    TASK,
    Candidate,
    Inventory,
    Policies,
    Query,
    reason,
    validate_candidate,
)

VARIANTS = {
    "explicit_stratified": {
        "description": "explicit",
        "sampling": "stratified",
        "review_prompt": "standard",
    },
    "concise_stratified": {
        "description": "concise",
        "sampling": "stratified",
        "review_prompt": "standard",
    },
    "explicit_random": {
        "description": "explicit",
        "sampling": "random",
        "review_prompt": "standard",
    },
    "counterexample_stratified": {
        "description": "explicit",
        "sampling": "stratified",
        "review_prompt": "counterexample",
    },
}

CONCISE_TASK = (
    "List every room offer suitable for the requested adults and one child in the requested "
    "city. Follow each offer's hotel and that hotel's child policy. Capacity must cover all "
    "adults and the child. The child's age must meet the policy minimum. Stay cost must not "
    "exceed the budget. The stay costs nights times nightly_cents plus fee_cents once. "
    "Include exact-boundary matches. Missing links or conflicting source records make the "
    "whole result incomplete. Do not invent facts."
)
COMPLETENESS = (
    " Treat each source read as a complete snapshot. Merge identical records by typed id. "
    "A conflicting duplicate anywhere in the snapshot, or an unresolved hotel or policy "
    "for any offer, makes the whole result incomplete. The adapter enforces these data "
    "checks. The function returns all eligible offer IDs and integer total costs. "
    "Action selection is a later step. Do not restrict this function to the cheapest offer."
)
OPERATORS = (
    " Draft pairwise disjoint source types and named relations. Each relation identifies "
    "its source foreign-key field and target record type. Source records use id as primary "
    "key. Compose a function from lookup, typed relation traversal, comparisons, and "
    "arithmetic projection. Use op field with name alias.field, op input with a request "
    "field name, op constant with value 0 or 1, or op add/multiply with two args. "
    "Predicate compare is eq, le, or ge. Constants describe structural counts only. "
    "Read thresholds from the request or records. Do not use example IDs or numeric "
    "answers as rules. Each traversal introduces a fresh alias. Return a RoomOffer result."
)


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: Literal["schema", "function", "workflow"]
    action: Literal["add", "modify", "remove"]
    artifact: str
    reason: str
    proposal: str


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    blocking: bool
    summary: str
    findings: list[Finding] = Field(max_length=12)


def sample_cases(cases, sampling, round_number, size=6, seed=731):
    """Resample training worlds on each round. Do not sample evaluation worlds."""
    rng = random.Random(seed + round_number)
    if sampling == "random":
        return rng.sample(cases, min(size, len(cases)))
    groups = {}
    for case in cases:
        groups.setdefault(case.get("family", case["name"]), []).append(case)
    families = sorted(groups)
    rng.shuffle(families)
    selected = [rng.choice(groups[family]) for family in families[:size]]
    if len(selected) < min(size, len(cases)):
        names = {case["name"] for case in selected}
        remaining = [case for case in cases if case["name"] not in names]
        selected.extend(rng.sample(remaining, min(size - len(selected), len(remaining))))
    return selected


def training_observations(candidate, cases):
    """Keep operator traces and compare results with supplied training references."""
    observations = []
    for case in cases:
        record = {"case": case["name"], "family": case.get("family")}
        try:
            result = reason(
                candidate,
                Query.model_validate_json(json.dumps(case["query"])),
                Inventory.model_validate_json(json.dumps(case["inventory"])),
                Policies.model_validate_json(json.dumps(case["policies"])),
            )
            actual = {row["offer_id"]: row["total_cents"] for row in result["eligible"]}
            expected_status = case.get("expected_status", "complete")
            record.update(
                {
                    "passed": result["status"] == expected_status and actual == case["expected"],
                    "expected_status": expected_status,
                    "expected": case["expected"],
                    "result": result,
                }
            )
        except (ValueError, KeyError, TypeError) as exc:
            record.update({"passed": False, "error": str(exc)})
        observations.append(record)
    return observations


def append_event(directory, event):
    with (directory / "events.jsonl").open("a") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")


async def call(model, directory, name, prompt, payload, schema):
    request = {"tool": name, "prompt": prompt, "payload": payload, "schema": schema}
    append_event(directory, {"kind": "request", **request})
    try:
        output = await model.turn(
            prompt,
            [{"role": "user", "content": json.dumps(payload)}],
            [{"type": "function", "name": name, "description": name, "parameters": schema}],
        )
    except Exception as exc:
        append_event(directory, {"kind": "model_error", "tool": name, "error": str(exc)})
        raise
    append_event(directory, {"kind": "response", "tool": name, "response": output})
    calls = [item for item in output if item.get("name") == name]
    if len(calls) != 1:
        raise ValueError(f"Return one {name} call.")
    return calls[0]["arguments"]


async def construct(
    model,
    cases,
    output_dir,
    variant="explicit_stratified",
    max_rounds=3,
    trajectory_runner=None,
    initial_feedback=None,
    initial_candidate=None,
):
    """Return a frozen candidate only after all training checks and judge review pass.

    The optional trajectory_runner receives candidate, case, and output directory.
    It must return a JSON object with a passed boolean and the actual native MCP trace.
    """
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / "construction.json").exists() or (directory / "events.jsonl").exists():
        raise ValueError("Use a new directory to preserve the earlier experiment record.")
    config = VARIANTS[variant]
    description = TASK if config["description"] == "explicit" else CONCISE_TASK
    prompt = (
        "Construct a small operational ontology from requirements and source contracts. "
        + description
        + COMPLETENESS
        + " Source contracts: "
        + json.dumps(FIELDS)
        + " Request contract: "
        + json.dumps(Query.model_json_schema())
        + OPERATORS
        + " Derive relations and calculations from the requirements and examples. "
        "Apply schema and function feedback separately. Call propose_kernel."
    )
    if config["review_prompt"] == "counterexample":
        prompt += (
            " Before submitting, check whether each predicate can reject a different "
            "invalid offer. Check exact boundaries, a changed relation target, and a "
            "shared child policy. Do not include private reasoning in the response."
        )
    feedback = initial_feedback or []
    previous = initial_candidate.model_dump(mode="json") if initial_candidate else None
    report = {
        "variant": variant,
        "config": config,
        "mode": getattr(model, "mode", "unspecified"),
        "training_cases": [case["name"] for case in cases],
        "training_digest": hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest(),
        "native_training_checked": trajectory_runner is not None,
        "repair_challenge": initial_candidate is not None,
        "rounds": [],
        "status": "not_frozen",
    }
    frozen = None
    for number in range(1, max_rounds + 1):
        samples = sample_cases(cases, config["sampling"], number)
        record = {"round": number, "sample": [case["name"] for case in samples]}
        try:
            raw = await call(
                model,
                directory,
                "propose_kernel",
                prompt,
                {"examples": samples, "previous_candidate": previous, "feedback": feedback},
                Candidate.model_json_schema(),
            )
            candidate = Candidate.model_validate_json(raw)
            record["candidate"] = candidate.model_dump(mode="json")
            previous = record["candidate"]
            # HermiT uses process-global state. Keep this check on the main event loop.
            validate_candidate(candidate, directory / f"round-{number}.owl")
            record["owl"] = "HermiT_passed"
            observations = training_observations(candidate, cases)
            record["observations"] = observations
            failures = [item for item in observations if not item["passed"]]
            native_runs = []
            if trajectory_runner and not failures:
                for case in samples[:2]:
                    episode_path = directory / f"round-{number}-{case['name']}"
                    native_runs.append(await trajectory_runner(candidate, case, episode_path))
            record["native_runs"] = native_runs
            workflow_failures = [run for run in native_runs if not run.get("passed", False)]
            review_prompt = (
                "Review the whole operational ontology, training task scores, operator "
                "traces, and native MCP trajectories. Diagnose blocking faults only from "
                "the supplied evidence and task requirements. Separate schema, function, "
                "and workflow findings. A passing case alone does not prove a correct "
                "general rule. Do not change the scorer or source contracts. Call review_kernel. "
                + description
                + COMPLETENESS
            )
            raw_review = await call(
                model,
                directory,
                "review_kernel",
                review_prompt,
                {
                    "kernel": previous,
                    "task_scores": {"passed": len(cases) - len(failures), "total": len(cases)},
                    "failed_cases": failures,
                    "operator_traces": observations,
                    "native_trajectories": native_runs,
                },
                Review.model_json_schema(),
            )
            review = Review.model_validate_json(raw_review)
            record["review"] = review.model_dump(mode="json")
            feedback = {
                "schema": [f.model_dump() for f in review.findings if f.target == "schema"],
                "function": [f.model_dump() for f in review.findings if f.target == "function"],
                "workflow": [f.model_dump() for f in review.findings if f.target == "workflow"],
                "failed_cases": failures,
                "failed_native_runs": workflow_failures,
            }
            if not failures and not workflow_failures and not review.blocking:
                frozen = candidate
                report["status"] = "frozen"
                report["fingerprint"] = candidate.fingerprint
                (directory / "kernel.json").write_text(candidate.model_dump_json(indent=2))
                owl_bytes = (directory / f"round-{number}.owl").read_bytes()
                (directory / "schema.owl").write_bytes(owl_bytes)
                report["artifact_sha256"] = {
                    name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                    for name in ("kernel.json", "schema.owl")
                }
                validation = {
                    "fingerprint": candidate.fingerprint,
                    "mode": report["mode"],
                    "training_cases_passed": len(cases),
                    "owl_reasoner": "HermiT",
                    "native_training_checked": trajectory_runner is not None,
                    "artifact_sha256": report["artifact_sha256"],
                }
                (directory / "validation.json").write_text(json.dumps(validation, indent=2))
        except (ValueError, KeyError, TypeError) as exc:
            feedback = {"schema_or_function_error": str(exc), "previous_candidate": previous}
            record["error"] = str(exc)
        except Exception as exc:
            record["infrastructure_error"] = str(exc)
            report["rounds"].append(record)
            (directory / "construction.json").write_text(json.dumps(report, indent=2))
            raise
        record["feedback"] = feedback
        report["rounds"].append(record)
        (directory / "construction.json").write_text(json.dumps(report, indent=2))
        if frozen:
            break
        await asyncio.sleep(0)
    return {"candidate": frozen, "report": report}


async def repair_mutation(
    model, candidate, cases, output_dir, max_rounds=3, trajectory_runner=None
):
    """Test real model repair after an explicit function mutation. Do not call this learning."""
    if not candidate.program.filters:
        raise ValueError("A repair challenge requires a predicate to remove.")
    failures = []
    # Select a mutation that has a real training counterexample.
    for index in reversed(range(len(candidate.program.filters))):
        predicates = candidate.program.filters
        mutated = candidate.model_copy(
            update={
                "program": candidate.program.model_copy(
                    update={"filters": predicates[:index] + predicates[index + 1 :]}
                )
            }
        )
        observations = training_observations(mutated, cases)
        failures = [item for item in observations if not item["passed"]]
        if failures:
            break
    if not failures:
        raise ValueError("This mutation has no failing training case. Do not claim repair.")
    native_runs = []
    if trajectory_runner:
        case = next(case for case in cases if case["name"] == failures[0]["case"])
        native_runs.append(
            await trajectory_runner(mutated, case, Path(output_dir) / "mutation-native")
        )
    return await construct(
        model,
        cases,
        output_dir,
        max_rounds=max_rounds,
        trajectory_runner=trajectory_runner,
        initial_candidate=mutated,
        initial_feedback={
            "challenge": "An evaluator removed one predicate from the generated function.",
            "failed_cases": failures,
            "operator_traces": observations,
            "native_trajectories": native_runs,
        },
    )
