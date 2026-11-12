"""Review a proposed cause before changing a persistent harness definition."""

from copy import deepcopy
from typing import Literal

from pydantic import Field, JsonValue

from oak.definition_checks import constants, source_occurrence
from oak.discovery_schemas import EvidenceRef
from oak.evidence_graph import EvidenceGraph
from oak.graph_query import GraphQuery, definition_catalog, execute_query
from oak.repair_executor import MISSING
from oak.repair_patch import candidate_digest, canonical_digest
from oak.repair_schemas import Frozen
from oak.training_feedback import RepairInput, resolve_evidence

Decision = Literal[
    "existing_route",
    "missing_evidence",
    "agent_use",
    "definition_defect",
    "missing_definition",
    "unresolved",
]


class DefinitionTarget(Frozen):
    collection: str
    id: str


class ReplayProbe(Frozen):
    episode_id: str
    observation_count: int = Field(ge=0)
    function_id: str | None = None
    arguments: dict[str, JsonValue] = Field(default_factory=dict)
    query: GraphQuery | None = None
    expected_ref: EvidenceRef


class ReviewProposal(Frozen):
    decision: Decision
    reason: str = Field(min_length=1, max_length=4000)
    evidence_refs: tuple[EvidenceRef, ...] = Field(default=(), max_length=100)
    examined: tuple[DefinitionTarget, ...] = Field(default=(), max_length=100)
    targets: tuple[DefinitionTarget, ...] = Field(default=(), max_length=100)
    missing_element: str = Field(default="", max_length=4000)
    alternatives: tuple[str, ...] = Field(default=(), max_length=20)
    probes: tuple[ReplayProbe, ...] = Field(default=(), max_length=3)
    evidence_requests: tuple[EvidenceRef, ...] = Field(default=(), max_length=3)


class RepairReview(ReviewProposal):
    version: Literal["oak.repair-review.v1"] = "oak.repair-review.v1"
    candidate_digest: str
    evidence_digest: str
    verified: bool = False
    verification: str = "unresolved"
    replays: tuple[dict, ...] = ()


REVIEW_INSTRUCTIONS = """Review one failure before proposing a harness change.
The reason is a proposed cause, not a proven cause. Do not propose a patch here.
First inspect existing definitions and routes. A missing shortcut is not a missing capability.
Use existing_route when existing operations can meet the requirement. Use agent_use when
the required capability was present but used incorrectly. Tool errors and missing observations
are missing_evidence. Limits, incomplete traces, and uncertain causes are unresolved.
Use definition_defect only for a concrete incorrect definition. Supply a replay probe over
the saved observation prefix and an expected_ref to the correct recorded value. Do not invent
expected results. Use missing_definition only for a specific absent definition supported by
the original requirements, tool contracts, or observations. List the alternatives examined.
An unsuccessful search does not prove absence. An unavailable operation outside the fixed
runtime is unresolved. Functions need not be added when query_graph can perform the work.
Identify exact collection and ID targets. Cite source evidence and examined definitions.
Request saved evidence when needed. Probes cannot dispatch tools. Never repeat an action.
Preserve all original requirements and working definitions. Return the requested object."""


def _context_key(context):
    # Execution IDs and times do not change the evidence content.
    episodes = []
    for episode in context.get("episodes", []):
        result = episode.get("result", {})
        episodes.append(
            {
                "case": episode.get("case_snapshot"),
                "status": result.get("status"),
                "observations": [
                    {k: o.get(k) for k in ("tool_id", "status", "coverage", "arguments", "data")}
                    for o in result.get("observations", [])
                ],
                "final_output": result.get("final_output"),
                "evaluation": episode.get("evaluation", {}).get("status"),
            }
        )
    report = context.get("construction_correction", {}).get("report", {})

    def stable(value):
        if isinstance(value, dict):
            return {
                k: stable(v)
                for k, v in value.items()
                if k
                not in {
                    "id",
                    "invocation_id",
                    "evidence_refs",
                    "created_at",
                    "duration_ms",
                    "observation_id",
                    "request_snapshot",
                }
            }
        if isinstance(value, list):
            return [stable(v) for v in value]
        return value

    return canonical_digest(
        {
            "episodes": sorted({canonical_digest(e) for e in episodes}),
            "validation": stable(
                {
                    k: report[k]
                    for k in (
                        "status",
                        "errors",
                        "unsatisfiable_classes",
                        "results",
                        "unexecuted_functions",
                        "unexecuted_bindings",
                    )
                    if k in report
                }
            ),
            "validation_kind": context.get("construction_correction", {}).get("validation_kind"),
            "input_digest": context.get("original_input_digest"),
        }
    )


def replay_probe(candidate, probe, context):
    """Rebuild only the recorded prefix. Do not contact an external service."""
    episode = next(
        (e for e in context.get("episodes", []) if str(e["id"]) == probe.episode_id), None
    )
    if episode is None:
        raise ValueError("The replay episode is unavailable.")
    observations = episode["result"].get("observations", [])
    if probe.observation_count > len(observations):
        raise ValueError("The replay prefix exceeds the saved observations.")
    if (probe.query is None) == (probe.function_id is None):
        raise ValueError("Select one saved function or graph query for replay.")
    supplied = probe.query.arguments if probe.query is not None else probe.arguments
    values = list(supplied.values())
    if probe.query is not None:
        values.extend(v for _, v in constants(probe.query.model_dump(mode="json")))

    def nodes(value):
        yield value
        if isinstance(value, dict):
            for child in value.values():
                yield from nodes(child)
        elif isinstance(value, list):
            for child in value:
                yield from nodes(child)

    inputs = [(episode["result"].get("request_snapshot") or {}).get("values", {})]
    inputs += [
        {k: o.get(k) for k in ("arguments", "data")}
        for o in observations[: probe.observation_count]
    ]
    recorded = list(nodes(inputs))
    query_source = {"task": {"query": episode.get("case_snapshot", {}).get("query", "")}}
    if any(
        not any(type(v) is type(item) and v == item for item in recorded)
        and source_occurrence(v, query_source) is None
        for v in values
    ):
        raise ValueError("Replay arguments require recorded request or observation values.")
    graph = EvidenceGraph(candidate)
    phase = "ingestion"
    try:
        for observation in observations[: probe.observation_count]:
            graph.add(
                {k: observation.get(k) for k in ("id", "tool_id", "status", "coverage", "data")},
                arguments=observation.get("arguments", {}),
            )
        request = episode["result"].get("request_snapshot") or {}
        phase = "execution"
        if probe.query is not None:
            result = execute_query(candidate, graph, probe.query, request.get("values", {}))
        else:
            result = graph.execute(
                probe.function_id, probe.arguments, request=request.get("values", {})
            )
        return result
    except ValueError as error:
        return {"status": "invalid", "phase": phase, "error": str(error)}


def _matches(result, expected):
    return result.get("status") in {"complete", "allowed", "rejected"} and (
        result.get("value", result.get("status")) == expected
    )


def _source_reference(ref):
    return (ref.source == "input" and ref.id == "surface") or (
        ref.source == "artifact"
        and "/result/observations/" in ref.path
        and ("/data" in ref.path or "/raw" in ref.path)
    )


def _probe_targets(candidate, probe, context):
    """Find declarations referenced by a replay, including its source mappings."""
    function = next((f for f in candidate.functions if f.id == probe.function_id), None)
    plan = probe.query or function
    targets = {("functions", probe.function_id)} if function else set()
    if plan is None:
        return targets
    fields = {
        "entity_id": "entities",
        "entity_types": "entities",
        "relation_id": "relations",
        "relation_ids": "relations",
        "constraint_ids": "constraints",
        "required_constraint_ids": "constraints",
    }

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in fields:
                    for identifier in value if isinstance(value, list) else [value]:
                        if isinstance(identifier, str):
                            targets.add((fields[key], identifier))
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(plan.model_dump(mode="json"))
    for relation in candidate.schema.relations:
        if ("relations", relation.id) in targets:
            targets.update(("entities", e) for e in (relation.from_entity, relation.to_entity))
    for mapping in candidate.mappings:
        if ("entities", mapping.entity_id) in targets:
            targets.add(("mappings", mapping.id))
    return targets


async def review_repair(candidate, context, generate, execution_evidence):
    key = _context_key(context)
    base = {"candidate_digest": candidate_digest(candidate), "evidence_digest": key}
    correction = context.get("construction_correction", {})
    failed = correction.get("failed_episodes", [])
    report = correction.get("report", {})
    kind = correction.get("validation_kind")
    deterministic = kind in {"structural", "formal"} or (
        kind == "counterexamples"
        and any(
            not r.get("passed") and (r.get("decision") or r.get("actual") == "validation_error")
            for r in report.get("results", [])
        )
    )
    if deterministic and report.get("status") in {
        "invalid",
        "failed",
        "inconsistent",
        "unsatisfiable",
    }:
        return RepairReview(
            **base,
            decision="definition_defect",
            reason="The fixed validation report records a defect.",
            evidence_refs=(EvidenceRef.model_validate(correction["evidence_ref"]),),
            verified=True,
            verification="validation_report",
        )
    if (failed or kind == "execution") and not any(
        e.get("evaluation", {}).get("status") == "failed"
        and e.get("result", {}).get("status") == "complete"
        for e in failed
    ):
        return RepairReview(
            **base,
            decision="unresolved",
            reason="No completed case has a supported task-failure judgment.",
        )
    repair = RepairInput(context, candidate, execution_evidence)
    catalog = definition_catalog(candidate)
    indexed = {(i["collection"], i["id"]) for i in catalog["index"]}
    repair.data["query_schema"] = GraphQuery.model_json_schema()
    repair.data["replay_episodes"] = [
        {
            "episode_id": str(e["id"]),
            "case_id": str(e["case_id"]),
            "observation_count": len(e.get("result", {}).get("observations", [])),
            "result_ref": {"source": "artifact", "id": str(e["id"]), "path": "/result"},
        }
        for e in context.get("episodes", [])
    ]
    for attempt in range(3):
        response = await generate(
            instructions=REVIEW_INSTRUCTIONS,
            data=deepcopy(repair.data),
            response_schema=ReviewProposal,
        )
        proposal = ReviewProposal.model_validate(response.data)
        if proposal.evidence_requests:
            if attempt == 2:
                break
            repair.data.setdefault("additional_evidence", []).append(
                repair.read(proposal.evidence_requests, requested=True)
            )
            continue
        if any(resolve_evidence(ref, repair.roots) is MISSING for ref in proposal.evidence_refs):
            raise ValueError("The review cites unavailable evidence.")
        if any((t.collection, t.id) not in indexed for t in proposal.examined):
            raise ValueError("The review names an unavailable examined definition.")
        replays = []
        for probe in proposal.probes:
            expected = resolve_evidence(probe.expected_ref, repair.roots)
            if expected is MISSING:
                raise ValueError("The expected replay value has no saved source.")
            if not _source_reference(probe.expected_ref):
                raise ValueError(
                    "Replay expectations require a task contract or source observation."
                )
            actual = replay_probe(candidate, probe, context)
            replays.append(
                {
                    "probe": probe.model_dump(mode="json"),
                    "expected": expected,
                    "actual": actual,
                    "matches": _matches(actual, expected),
                }
            )
        verified = False
        verification = "proposed_cause"
        if proposal.decision == "definition_defect":
            verified = (
                bool(proposal.targets and proposal.evidence_refs and replays)
                and any(
                    not r["matches"]
                    and (
                        r["actual"].get("status") in {"complete", "allowed", "rejected"}
                        or (
                            r["actual"].get("status") == "invalid"
                            and r["actual"].get("phase") == "ingestion"
                        )
                    )
                    for r in replays
                )
                and all((t.collection, t.id) in indexed for t in proposal.targets)
                and all(
                    any(
                        (t.collection, t.id) in _probe_targets(candidate, p, context)
                        for p in proposal.probes
                    )
                    for t in proposal.targets
                )
            )
            verification = "recorded_input_replay" if verified else "unresolved"
        elif proposal.decision == "missing_definition":
            verified = bool(
                proposal.targets
                and proposal.missing_element
                and proposal.evidence_refs
                and proposal.alternatives
                and proposal.examined
                and replays
                and any(_source_reference(ref) for ref in proposal.evidence_refs)
            ) and all((t.collection, t.id) not in indexed for t in proposal.targets)
            # An unknown function ID does not prove that its data route is absent.
            verified = verified and all(t.collection != "functions" for t in proposal.targets)
            referenced = set().union(
                *(_probe_targets(candidate, p, context) for p in proposal.probes)
            )
            verified = verified and all(
                (t.collection, t.id) in referenced or t.collection == "mappings"
                for t in proposal.targets
            )
            # A successful alternative disproves the need for an added shortcut.
            verified = verified and not any(r["matches"] for r in replays)
            verification = "supported_gap" if verified else "unresolved"
        return RepairReview(
            **proposal.model_dump(),
            **base,
            verified=verified,
            verification=verification,
            replays=tuple(replays),
        )
    return RepairReview(
        **base, decision="unresolved", reason="The review evidence limit was reached."
    )


def check_reviewed_patch(review, patch, before, after, context):
    if not review.verified or review.candidate_digest != candidate_digest(before):
        raise ValueError("A patch requires a verified review of this candidate.")
    if review.evidence_digest != _context_key(context):
        raise ValueError("The review evidence has changed.")
    if review.verification == "validation_report" and len(patch.changes) != 1:
        raise ValueError("A validation-report repair must correct one definition at a time.")
    if review.targets:
        allowed = {(t.collection, t.id) for t in review.targets}
        if any((c.collection, c.id) not in allowed for c in patch.changes):
            raise ValueError("The patch changes a definition outside its reviewed targets.")
    if review.decision == "missing_definition" and any(c.op != "add" for c in patch.changes):
        raise ValueError("A missing-definition review permits only the reviewed additions.")
    for replay in review.replays:
        probe = ReplayProbe.model_validate(replay["probe"])
        actual = replay_probe(after, probe, context)
        if not _matches(actual, replay["expected"]):
            raise ValueError("The patch did not correct the recorded-input replay.")
