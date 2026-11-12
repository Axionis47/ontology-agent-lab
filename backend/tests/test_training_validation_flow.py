"""Check training gate order with local reports and an isolated store."""

from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from oak import kernel_validation, ontology_verification
from oak.kernel_execution import VERSIONS
from oak.kernel_validation import ValidationSuite
from oak.model_client import ModelFailure
from oak.ontology_verification import formal_schema_digest
from oak.repair_schemas import CandidateV3
from oak.training import Training, TrainingHalt
from oak.training_construction import PatchProposal
from tests.kernel_fixtures import (
    DEFAULT_QUERY,
    READ_ID,
    WRITE_ID,
    candidate_data,
    tools,
    with_source_access,
)
from tests.test_kernel_validation import suite_data


class MemoryStore:
    def __init__(self):
        self.rows = {}
        self.accepted_id = None

    async def one(self, statement, parameters):
        if statement.startswith("INSERT INTO training_candidates"):
            identifier, run_id, digest, payload, patch = parameters
            old = next((r for r in self.rows.values() if r["digest"] == digest), None)
            row = old or {
                "id": identifier,
                "run_id": run_id,
                "digest": digest,
                "payload": deepcopy(payload.obj),
                "patch": deepcopy(patch.obj) if patch else None,
                "status": "provisional",
                "decision": {},
            }
            self.rows[str(row["id"])] = row
            return deepcopy(row)
        if statement.startswith("SELECT decision FROM training_candidates"):
            return {"decision": deepcopy(self.rows[str(parameters[0])]["decision"])}
        raise AssertionError(statement)

    async def all(self, statement, parameters):
        if statement.startswith("UPDATE training_candidates SET status="):
            status, decision, identifier = parameters
            self.rows[str(identifier)].update(status=status, decision=deepcopy(decision.obj))
            return [{"id": identifier}]
        if statement.startswith("UPDATE training_runs SET accepted_candidate_id="):
            self.accepted_id = parameters[0]
            return [{"id": parameters[1]}]
        raise AssertionError(statement)


def flow_candidate(*, bad_axiom=False):
    data = candidate_data()
    data["version"] = "oak.candidate.v3"
    data["mappings"][0].pop("coverage")
    if bad_axiom:
        data["formal_axioms"] = [
            {
                "id": "impossible",
                "kind": "disjoint",
                "entity_id": "offer",
                "target_entity_id": "offer",
                "requirement_ids": ["capacity"],
            }
        ]
    return with_source_access(data)


def training_run(*, rounds=3):
    return {
        "id": "run-1",
        "mode": "training",
        "created_at": datetime.now(UTC),
        "input_digest": "a" * 64,
        "inputs": {
            "task": {"rules": "Use the supplied catalog."},
            "agent": {"id": "a"},
            "tools": tools(),
        },
        "cases": [
            {
                "id": "sample-1",
                "query": DEFAULT_QUERY,
                "tool_ids": [READ_ID, WRITE_ID],
                "task_success": "The requested booking exists.",
            }
        ],
        "limits": {"max_rounds": rounds, "active_seconds": 120},
    }


class TrainingFlow(Training):
    def __init__(self, data=None, *, initial_errors=(), omit_binding=False, outcome="passed"):
        self.store = MemoryStore()
        self.model = object()
        self.data = flow_candidate() if data is None else data
        self.initial_errors = list(initial_errors)
        self.omit_binding = omit_binding
        self.outcome = outcome
        self.events = []
        self.timeline = []
        self.generations = []
        self.states = []
        self.episodes = []

    async def _context(self, run):
        return {
            "inputs": run["inputs"],
            "original_input_digest": run["input_digest"],
            "discovery": {"requirements": self.data["requirements"], "schema": self.data["schema"]},
            "cases": run["cases"],
            "allowed_tool_ids": [READ_ID, WRITE_ID],
            "requirement_ids": [r["id"] for r in self.data["requirements"]["requirements"]],
        }

    def _generate(self, run_id):
        async def generate(**kwargs):
            self.generations.append(deepcopy(kwargs))
            if kwargs["response_schema"] is CandidateV3:
                self.timeline.append("construct")
                if self.initial_errors:
                    raise self.initial_errors.pop(0)
                return SimpleNamespace(data=deepcopy(self.data))
            assert kwargs["response_schema"] is PatchProposal
            self.timeline.append("repair")
            context = kwargs["data"]
            report_ref = context["problem_ref"]
            index = context["declaration_index"]
            if any(item["collection"] == "formal_axioms" for item in index):
                collection, identifier = "formal_axioms", "impossible"
                change = {"collection": collection, "op": "remove", "id": identifier}
                requirements = ["capacity"]
            else:
                collection, identifier = "request_fields", "request.guests"
            declaration = next(
                item
                for item in index
                if (item["collection"], item["id"]) == (collection, identifier)
            )
            if identifier not in context["declarations"].get(collection, {}):
                return SimpleNamespace(
                    data={
                        "reason": "Inspect the affected declaration.",
                        "patch": None,
                        "evidence_requests": [declaration["ref"]],
                    }
                )
            if collection == "request_fields":
                value = deepcopy(context["declarations"][collection][identifier])
                value["description"] += " Corrected."
                change = {
                    "collection": collection,
                    "op": "replace",
                    "id": identifier,
                    "value": value,
                }
                requirements = ["party"]
            change["expected_digest"] = declaration["digest"]
            return SimpleNamespace(
                data={
                    "reason": "Correct the declaration cited by the saved report.",
                    "patch": {
                        "id": "patch-" + str(len(self.generations)),
                        "base_digest": context["candidate_digest"],
                        "original_input_digest": context["original_input_digest"],
                        "fault": {
                            "id": "fault-1",
                            "validation_event_id": report_ref["id"],
                            "requirement_ids": requirements,
                            "reason": "The saved validation report identifies this declaration.",
                        },
                        "evidence_refs": [
                            report_ref,
                            {"source": "input", "id": "surface", "path": ""},
                        ],
                        "changes": [change],
                    },
                }
            )

        return generate

    async def emit(self, run_id, kind, data, *args):
        identifier = "event-" + str(len(self.events) + 1)
        self.events.append({"id": identifier, "kind": kind, "data": deepcopy(data)})
        if kind == "kernel_validation":
            self.timeline.append(data["validation_kind"] + ":" + data["report"]["status"])
        elif kind.startswith("validation_suite_"):
            self.timeline.append(kind)
        return identifier

    async def _set(self, run_id, **kwargs):
        self.states.append(deepcopy(kwargs))

    async def _episode(self, run, case, stage, round_index, candidate_row=None):
        self.timeline.append(stage)
        observations = []
        decisions = []
        if stage == "harness":
            for binding in candidate_row["payload"]["operation_bindings"]:
                if self.omit_binding and binding["id"] == "create":
                    continue
                invocation = binding["id"] + "-invocation"
                observations.append(
                    {
                        "id": invocation,
                        "tool_id": binding["tool_id"],
                        "invocation_id": invocation,
                        "status": "succeeded",
                        "data": {"items": []},
                    }
                )
                decisions.append(
                    {"binding_id": binding["id"], "invocation_id": invocation, "status": "allowed"}
                )
        episode = {
            "id": "episode-" + str(len(self.episodes) + 1),
            "case_id": case["id"],
            "case_snapshot": deepcopy(case),
            "stage": stage,
            "evaluation": {"status": self.outcome if stage == "harness" else "passed"},
            "result": {
                "status": "complete",
                "observations": observations,
                "dispatch_decisions": decisions,
                "function_ids": ["check_parameters", "check_offer"] if stage == "harness" else [],
            },
        }
        self.episodes.append(deepcopy(episode))
        return episode


def install_gates(
    monkeypatch, flow, *, formal=("passed",), coverage=("passed",), probes=("passed",)
):
    formal_statuses, coverage_statuses, probe_statuses = list(formal), list(coverage), list(probes)
    calls = {"formal": [], "coverage": [], "build": [], "probes": []}

    async def verify(candidate, **kwargs):
        calls["formal"].append((candidate.model_dump(mode="json"), deepcopy(kwargs)))
        return {
            "status": formal_statuses.pop(0),
            "schema_digest": formal_schema_digest(candidate),
            "versions": {"encoder": VERSIONS["encoder"]},
            "owl": "<rdf:RDF/>",
            "errors": [],
            "unsatisfiable_classes": [],
        }

    async def review(context, generate):
        calls["coverage"].append(deepcopy(context))
        return {
            "status": coverage_statuses.pop(0),
            "reason": "Fixed coverage report.",
            "evidence_refs": [context["evidence_refs"][0]],
        }

    async def build(context, generate, existing=None):
        calls["build"].append(deepcopy(context))
        return ValidationSuite.model_validate(suite_data()), {
            "status": "passed",
            "reason": "Source expectations fixed.",
        }

    async def replay(candidate, suite, inputs, generate, emit):
        calls["probes"].append(suite.model_dump(mode="json"))
        assert not any(item["stage"] == "harness" for item in flow.episodes)
        return {"status": probe_statuses.pop(0), "results": [], "suite_digest": "suite-digest"}

    monkeypatch.setattr(ontology_verification, "verify_candidate", verify)
    monkeypatch.setattr(kernel_validation, "review_coverage", review)
    monkeypatch.setattr(kernel_validation, "build_validation_suite", build)
    monkeypatch.setattr(kernel_validation, "replay_validation_suite", replay)
    return calls


def report_events(flow, kind):
    return [
        event
        for event in flow.events
        if event["kind"] == "kernel_validation" and event["data"]["validation_kind"] == kind
    ]


async def test_invalid_formal_schema_receives_targeted_correction_before_harness(monkeypatch):
    flow = TrainingFlow(flow_candidate(bad_axiom=True))
    calls = install_gates(monkeypatch, flow, formal=("invalid", "passed"))
    await flow._train(training_run())

    assert (
        flow.timeline.index("formal:invalid")
        < flow.timeline.index("repair")
        < flow.timeline.index("harness")
    )
    repair = next(
        call["data"] for call in flow.generations if call["response_schema"] is PatchProposal
    )
    invalid = report_events(flow, "formal")[0]
    assert repair["target_case"] is None
    assert repair["problem_ref"] == {
        "source": "artifact",
        "id": invalid["id"],
        "path": "/report",
    }
    assert {"source": "input", "id": "surface", "path": ""} in repair["evidence_refs"]
    assert "episodes" not in repair and "candidate" not in repair
    assert "Observed problem" in repair["repair_brief"]
    assert calls["formal"][0][0]["formal_axioms"]
    assert calls["formal"][1][0]["formal_axioms"] == []
    assert len(calls["coverage"]) == len(calls["probes"]) == 1
    rows = list(flow.store.rows.values())
    assert [row["status"] for row in rows] == ["rejected", "accepted"]
    assert rows[0]["decision"]["validation"]["formal_event_id"] == invalid["id"]
    assert (
        rows[1]["decision"]["validation"]["formal_event_id"]
        == report_events(flow, "formal")[1]["id"]
    )
    assert invalid["data"]["report"]["status"] == "invalid"
    assert flow.store.accepted_id == rows[1]["id"]


async def test_formal_infrastructure_failure_never_requests_declaration_repair(monkeypatch):
    flow = TrainingFlow()
    calls = install_gates(monkeypatch, flow, formal=("infrastructure_error",))
    with pytest.raises(TrainingHalt, match="verification is unavailable"):
        await flow._train(training_run())
    assert "repair" not in flow.timeline
    assert "harness" not in flow.timeline
    assert not calls["coverage"] and not calls["build"] and not calls["probes"]
    row = next(iter(flow.store.rows.values()))
    report = report_events(flow, "formal")[0]
    assert row["decision"]["validation"]["formal_event_id"] == report["id"]
    assert report["data"]["report"]["status"] == "infrastructure_error"
    assert flow.store.accepted_id is None


async def test_repeated_formal_failures_stop_at_the_round_limit(monkeypatch):
    flow = TrainingFlow(flow_candidate(bad_axiom=True))
    calls = install_gates(monkeypatch, flow, formal=("invalid", "invalid"))
    await flow._train(training_run(rounds=2))
    assert len(calls["formal"]) == 2
    assert flow.timeline.count("repair") == 2
    assert "harness" not in flow.timeline
    assert all(row["status"] == "rejected" for row in flow.store.rows.values())
    assert flow.store.accepted_id is None
    assert "round limit" in flow.states[-1]["message"]


async def test_fixed_negative_suite_runs_before_harness_and_survives_repair(monkeypatch):
    flow = TrainingFlow()
    calls = install_gates(
        monkeypatch,
        flow,
        formal=("passed", "passed"),
        coverage=("passed", "passed"),
        probes=("failed", "passed"),
    )
    await flow._train(training_run())
    assert flow.timeline.index("validation_suite_fixed") < flow.timeline.index(
        "counterexamples:failed"
    )
    assert flow.timeline.index("counterexamples:failed") < flow.timeline.index("repair")
    assert flow.timeline.index("counterexamples:passed") < flow.timeline.index("harness")
    assert len(calls["build"]) == 1
    assert calls["probes"][0] == calls["probes"][1]
    repair = next(
        call["data"] for call in flow.generations if call["response_schema"] is PatchProposal
    )
    assert {
        "source": "artifact",
        "id": repair["problem_ref"]["id"],
        "path": "/fixed_validation_suite",
    } in repair["evidence_refs"]
    assert "fixed_validation_suite" not in repair
    first, second = list(flow.store.rows.values())
    assert first["status"] == "rejected" and second["status"] == "accepted"
    for row in (first, second):
        assert {"formal_event_id", "coverage_event_id", "counterexamples_event_id"} <= row[
            "decision"
        ]["validation"].keys()
    assert second["decision"]["evaluation"]["task_outcomes"][0]["report"]["status"] == "passed"


def invalid_output():
    return ModelFailure(
        "invalid_output",
        validation_errors=[{"loc": ["functions"], "msg": "Invalid typed function."}],
        failed_output={"version": "oak.candidate.v2", "functions": "invalid"},
    )


async def test_invalid_typed_proposal_is_reported_before_the_bounded_retry(monkeypatch):
    flow = TrainingFlow(initial_errors=[invalid_output()])
    install_gates(monkeypatch, flow)
    await flow._train(training_run())
    reports = report_events(flow, "structural")
    assert len(reports) == 1
    assert reports[0]["data"]["candidate_id"] is None
    assert reports[0]["data"]["report"]["proposal"]["functions"] == "invalid"
    correction = flow.generations[1]["data"]["construction_correction"]
    assert correction["validation_report"]["id"] == reports[0]["id"]
    assert flow.timeline.index("structural:invalid") < flow.timeline.index("formal:passed")
    assert flow.store.accepted_id is not None


async def test_second_invalid_typed_proposal_is_saved_without_an_unbounded_retry(monkeypatch):
    flow = TrainingFlow(initial_errors=[invalid_output(), invalid_output()])
    calls = install_gates(monkeypatch, flow)
    with pytest.raises(ValueError, match="valid typed declarations"):
        await flow._train(training_run())
    assert len(flow.generations) == 2
    assert len(report_events(flow, "structural")) == 2
    assert not calls["formal"]
    assert "harness" not in flow.timeline
    assert not flow.store.rows


@pytest.mark.parametrize("coverage", ["failed", "inconclusive"])
async def test_coverage_failure_prevents_suite_and_external_harness(monkeypatch, coverage):
    flow = TrainingFlow()
    calls = install_gates(monkeypatch, flow, coverage=(coverage,))
    await flow._train(training_run(rounds=1))
    assert not calls["build"] and not calls["probes"]
    assert "harness" not in flow.timeline
    row = next(iter(flow.store.rows.values()))
    assert row["status"] == "rejected"
    assert (
        row["decision"]["validation"]["coverage_event_id"]
        == report_events(flow, "coverage")[0]["id"]
    )


@pytest.mark.parametrize("outcome", ["failed", "inconclusive", "error"])
async def test_task_outcome_failure_cannot_accept_a_checked_kernel(monkeypatch, outcome):
    flow = TrainingFlow(outcome=outcome)
    install_gates(monkeypatch, flow)
    await flow._train(training_run(rounds=1))
    row = next(iter(flow.store.rows.values()))
    assert row["status"] == "rejected"
    assert flow.store.accepted_id is None
    assert report_events(flow, "execution")[0]["data"]["report"]["status"] == "failed"
    assert {
        "formal_event_id",
        "coverage_event_id",
        "counterexamples_event_id",
        "execution_event_id",
    } <= row["decision"]["validation"].keys()


async def test_passing_task_without_successful_binding_coverage_is_not_accepted(monkeypatch):
    flow = TrainingFlow(omit_binding=True)
    install_gates(monkeypatch, flow)
    await flow._train(training_run(rounds=1))
    row = next(iter(flow.store.rows.values()))
    assert row["status"] == "rejected"
    assert row["decision"]["unexecuted_bindings"] == ["create"]
    assert flow.store.accepted_id is None
