import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from pydantic import ValidationError

from oak_contracts.evaluator import evaluate_fixture
from oak_contracts.fixture import package_fixture
from oak_contracts.models import (
    REQUIRED_GATES,
    ArtifactRef,
    ContractError,
    Package,
    RepairProposal,
    Scope,
    ToolObservation,
    Trial,
    digest,
    repair_invalidation,
)
from oak_contracts.store import SQLiteHarness


def rejection(code):
    return pytest.raises(ContractError, match=f"^{code}$")


def test_cross_project_same_ids_do_not_grant_access(harness):
    store, scope, package_hash, _, _ = harness
    other = Scope(project_id="project-b", agent_id=scope.agent_id)
    store.bootstrap(other.project_id, "other-owner", "other-verifier")
    store.create_agent("other-owner", other)
    with rejection("forbidden"):
        store.select("other-owner", scope, "context-1", 0, (), package_hash)
    with rejection("forbidden"):
        store.create_agent("other-owner", Scope(project_id="project-a", agent_id="attack"))
    with rejection("context_not_found"):
        store.ingest("other-owner", other, "context-1", harness[4][0], 0)


def test_hash_knowledge_does_not_grant_artifact_access(harness):
    store, scope, _, package, _ = harness
    with rejection("forbidden"):
        store.get_artifact("outsider", scope.project_id, package.schema_ref)


def test_artifact_bytes_and_kind_are_verified(harness):
    store, scope, _, package, _ = harness
    with rejection("artifact_integrity_failure"):
        store.get_artifact(
            "owner",
            scope.project_id,
            ArtifactRef(kind="operators", sha256=package.schema_ref.sha256),
        )
    store.db.execute("UPDATE artifacts SET payload='{}' WHERE hash=?", (package.schema_ref.sha256,))
    with rejection("artifact_integrity_failure"):
        store.get_artifact("owner", scope.project_id, package.schema_ref)


def test_contracts_reject_unknown_fields_and_schema_mismatch(harness):
    package = harness[3].model_dump(mode="json")
    package["ignored_option"] = True
    with pytest.raises(ValidationError):
        Package.model_validate_json(json.dumps(package))
    package.pop("ignored_option")
    package["functions_schema_hash"] = "0" * 64
    with pytest.raises(ValidationError, match="function_schema_mismatch"):
        Package.model_validate_json(json.dumps(package))
    package["functions_schema_hash"] = package["schema"]["sha256"]
    package["schema"]["contract_version"] = "future/99"
    with pytest.raises(ValidationError):
        Package.model_validate_json(json.dumps(package))


def test_user_cannot_issue_verifier_receipts(harness):
    store, scope, package_hash, _, _ = harness
    with rejection("forbidden"):
        store.issue_report(
            "owner",
            scope,
            package_hash,
            dict.fromkeys(REQUIRED_GATES, "passed"),
            (digest("test-v1"),),
        )


@pytest.mark.parametrize("status", ["failed", "not_run", "error"])
def test_failed_or_unrun_layer_blocks_activation(harness, status):
    store, scope, package_hash, _, _ = harness
    gates = dict.fromkeys(REQUIRED_GATES, "passed")
    gates["logic"] = status
    report = store.issue_report("verifier", scope, package_hash, gates, (digest("test-v1"),))
    with rejection("verification_incomplete"):
        store.activate("owner", scope, package_hash, report, 1, (digest("test-v1"),))
    assert store.db.execute("SELECT generation FROM active").fetchone()[0] == 1


def test_report_missing_gate_or_changed_test_inputs_blocks_activation(harness):
    store, scope, package_hash, _, _ = harness
    report = store.issue_report(
        "verifier", scope, package_hash, {"logic": "passed"}, (digest("test-v1"),)
    )
    with rejection("verification_incomplete"):
        store.activate("owner", scope, package_hash, report, 1, (digest("test-v1"),))
    report = store.issue_report(
        "verifier",
        scope,
        package_hash,
        dict.fromkeys(REQUIRED_GATES, "passed"),
        (digest("test-v1"),),
    )
    with rejection("verification_binding_mismatch"):
        store.activate("owner", scope, package_hash, report, 1, (digest("test-v2"),))


def test_tampered_report_cannot_activate(harness):
    store, scope, package_hash, _, _ = harness
    report = store.issue_report(
        "verifier",
        scope,
        package_hash,
        dict.fromkeys(REQUIRED_GATES, "passed"),
        (digest("test-v1"),),
    )
    row = store.db.execute("SELECT payload FROM reports WHERE hash=?", (report,)).fetchone()
    payload = json.loads(row[0])
    payload["issuer"] = "forged"
    store.db.execute("UPDATE reports SET payload=? WHERE hash=?", (json.dumps(payload), report))
    with rejection("report_integrity_failure"):
        store.activate("owner", scope, package_hash, report, 1, (digest("test-v1"),))


def test_stale_activation_and_candidate_report_mismatch(harness):
    store, scope, old_hash, _, _ = harness
    new_hash, _ = package_fixture(store, scope, "guarded_requirements")
    report = store.issue_report(
        "verifier", scope, new_hash, dict.fromkeys(REQUIRED_GATES, "passed"), (digest("test-v1"),)
    )
    with rejection("verification_binding_mismatch"):
        store.activate("owner", scope, old_hash, report, 1, (digest("test-v1"),))
    assert store.activate("owner", scope, new_hash, report, 1, (digest("test-v1"),)) == 2
    with rejection("stale_activation"):
        store.activate("owner", scope, new_hash, report, 1, (digest("test-v1"),))


def test_active_run_keeps_package_after_activation(harness):
    store, scope, old_hash, _, _ = harness
    assert store.start_run("owner", scope, "run-1", 1000.0, 3) == old_hash
    new_hash, _ = package_fixture(store, scope, "guarded_requirements")
    report = store.issue_report(
        "verifier", scope, new_hash, dict.fromkeys(REQUIRED_GATES, "passed"), (digest("test-v1"),)
    )
    store.activate("owner", scope, new_hash, report, 1, (digest("test-v1"),))
    assert store.read_run("owner", scope, "run-1")["package"] == old_hash
    assert store.start_run("owner", scope, "run-2", 1000.0, 3) == new_hash


def test_lost_ack_replay_after_reopen_has_one_revision(harness):
    store, scope, _, _, observations = harness
    receipt = store.ingest("owner", scope, "context-1", observations[0], 0)
    filename = store.db.execute("PRAGMA database_list").fetchone()[2]
    reopened = SQLiteHarness(filename)
    try:
        replay = reopened.ingest("owner", scope, "context-1", observations[0], 0)
        assert replay == receipt
        assert reopened.db.execute("SELECT count(*) FROM snapshots").fetchone()[0] == 2
        assert reopened.db.execute("SELECT count(*) FROM observations").fetchone()[0] == 1
    finally:
        reopened.close()


def test_changed_observation_identity_is_rejected_without_write(harness):
    store, scope, _, _, observations = harness
    store.ingest("owner", scope, "context-1", observations[0], 0)
    changed = observations[0].model_dump(mode="json")
    changed["payload"]["offers"][0]["total_price"] = 1
    with rejection("observation_identity_collision"):
        store.ingest(
            "owner", scope, "context-1", ToolObservation.model_validate_json(json.dumps(changed)), 1
        )
    assert store.db.execute("SELECT revision FROM contexts").fetchone()[0] == 1


def test_concurrent_commits_have_one_winner_at_parent(harness):
    store, scope, _, _, observations = harness
    filename = store.db.execute("PRAGMA database_list").fetchone()[2]
    barrier = Barrier(2)

    def worker(observation):
        connection = SQLiteHarness(filename)
        try:
            barrier.wait(timeout=5)
            try:
                return connection.ingest("owner", scope, "context-1", observation, 0).revision
            except ContractError as exc:
                return exc.code
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, observations))
    assert sorted(str(result) for result in results) == ["1", "stale_graph_parent"]
    assert store.db.execute("SELECT count(*) FROM observations").fetchone()[0] == 1


def test_required_evidence_and_stable_revision(harness):
    store, scope, package_hash, _, observations = harness
    store.ingest("owner", scope, "context-1", observations[0], 0)
    before = store.select("owner", scope, "context-1", 1, ("obs-search-001",), package_hash)
    assert not any(row.status == "eligible" for row in before.offers)
    with rejection("required_observation_not_committed"):
        store.select("owner", scope, "context-1", 1, ("obs-detail-001",), package_hash)
    store.ingest("owner", scope, "context-1", observations[1], 1)
    assert store.select("owner", scope, "context-1", 1, (), package_hash) == before
    after = store.select("owner", scope, "context-1", 2, ("obs-detail-001",), package_hash)
    assert [(row.offer_id, row.status) for row in after.offers] == [
        ("o1", "violated"),
        ("o2", "violated"),
        ("o3", "eligible"),
    ]
    assert after.exhaustive is False


def test_unknown_conflict_and_false_remain_distinct(harness):
    store, scope, package_hash, _, observations = harness
    store.ingest("owner", scope, "context-1", observations[0], 0)
    first = store.select("owner", scope, "context-1", 1, (), package_hash)
    assert first.offers[2].unknowns == ("min_nights", "available")
    detail = observations[1].model_dump(mode="json")
    detail["payload"]["available"] = False
    store.ingest(
        "owner", scope, "context-1", ToolObservation.model_validate_json(json.dumps(detail)), 1
    )
    second = store.select("owner", scope, "context-1", 2, (), package_hash)
    assert second.offers[2].violations == ("available",)
    detail["observation_id"] = "conflicting-detail"
    detail["payload"]["available"] = True
    store.ingest(
        "owner", scope, "context-1", ToolObservation.model_validate_json(json.dumps(detail)), 2
    )
    third = store.select("owner", scope, "context-1", 3, (), package_hash)
    assert third.offers[2].status == "unknown"
    assert third.offers[2].unknowns == ("available",)


def test_wrong_request_scope_and_bad_type_leave_no_projection(harness):
    store, scope, _, _, observations = harness
    changed = observations[0].model_dump(mode="json")
    changed["arguments"]["party_size"] = 2
    with rejection("observation_scope_mismatch"):
        store.ingest(
            "owner", scope, "context-1", ToolObservation.model_validate_json(json.dumps(changed)), 0
        )
    changed["arguments"]["party_size"] = 4
    changed["payload"]["offers"][0]["max_occupancy"] = True
    with rejection("invalid_source_value"):
        store.ingest(
            "owner", scope, "context-1", ToolObservation.model_validate_json(json.dumps(changed)), 0
        )
    assert store.db.execute("SELECT count(*) FROM observations").fetchone()[0] == 0


def test_stale_source_and_mixed_package_view_are_rejected(harness):
    store, scope, package_hash, _, observations = harness
    changed = observations[0].model_dump(mode="json")
    changed["observed_at"] = "2026-03-01T10:00:00Z"
    with rejection("source_outside_fixture_freshness_window"):
        store.ingest(
            "owner", scope, "context-1", ToolObservation.model_validate_json(json.dumps(changed)), 0
        )
    with rejection("view_package_mismatch"):
        store.select("owner", scope, "context-1", 0, (), "0" * 64)
    assert store.select("owner", scope, "context-1", 0, (), package_hash).offers == ()


def test_budget_reservations_survive_reopen_and_completion_redelivery(harness):
    store, scope, _, _, _ = harness
    store.start_run("owner", scope, "run-1", 1000.0, 1)
    store.reserve_call("owner", scope, "run-1", "op-1", {"tool": "search"}, 900.0)
    filename = store.db.execute("PRAGMA database_list").fetchone()[2]
    reopened = SQLiteHarness(filename)
    try:
        assert (
            reopened.reserve_call("owner", scope, "run-1", "op-1", {"tool": "search"}, 1100.0)
            == "reconcile"
        )
        reopened.complete_call("owner", scope, "run-1", "op-1")
        reopened.complete_call("owner", scope, "run-1", "op-1")
        assert (
            reopened.db.execute(
                "SELECT count(*) FROM events WHERE event='call.completed'"
            ).fetchone()[0]
            == 1
        )
        with rejection("call_budget_exhausted"):
            reopened.reserve_call("owner", scope, "run-1", "op-2", {}, 901.0)
        assert reopened.read_run("owner", scope, "run-1")["deadline"] == 1000.0
    finally:
        reopened.close()


def test_deadline_and_operation_collision_do_not_create_calls(harness):
    store, scope, _, _, _ = harness
    store.start_run("owner", scope, "run-1", 1000.0, 3)
    store.reserve_call("owner", scope, "run-1", "op-1", {"a": 1}, 900.0)
    with rejection("operation_identity_collision"):
        store.reserve_call("owner", scope, "run-1", "op-1", {"a": 2}, 900.0)
    with rejection("run_not_dispatchable"):
        store.reserve_call("owner", scope, "run-1", "op-2", {}, 1000.0)
    assert store.db.execute("SELECT count(*) FROM reservations").fetchone()[0] == 1


def test_schema_repair_invalidates_dependents_and_rejects_stale_or_held_out(harness):
    schema_hash = harness[3].schema_ref.sha256
    proposal = RepairProposal(
        target_hash=schema_hash,
        changed_semantic_ids=("Offer.minimum_stay",),
        kind="schema",
        evidence_ids=("development-failure-1",),
    )
    assert repair_invalidation(proposal, schema_hash, "development") == (
        "coverage",
        "logic",
        "projection",
        "functions",
        "regression",
    )
    with rejection("stale_repair"):
        repair_invalidation(proposal, "0" * 64, "development")
    with rejection("held_out_repair_forbidden"):
        repair_invalidation(proposal, schema_hash, "held_out")


def test_evaluator_rejects_wrong_result_despite_local_success(harness):
    store, scope, package_hash, _, observations = harness
    for parent, observation in enumerate(observations):
        store.ingest("owner", scope, "context-1", observation, parent)
    assert (
        store.select("owner", scope, "context-1", 2, (), package_hash).offers[2].status
        == "eligible"
    )
    wrong = Trial(
        assignment_id="a1",
        selected_offer_id="o1",
        claim="observed_eligible_offer",
        evidence_ids=("obs-detail-001",),
    )
    assert evaluate_fixture(("a1",), (wrong,))["correct"] == 0


def test_evaluator_preserves_denominator_and_rejects_duplicate(harness):
    trial = Trial(
        assignment_id="a1",
        selected_offer_id="o3",
        claim="observed_eligible_offer",
        evidence_ids=("obs-detail-001",),
    )
    assessment = evaluate_fixture(("a1", "a2"), (trial,))
    assert assessment["assigned"] == 2
    assert assessment["correct"] == 1
    assert assessment["outcomes"][1]["outcome"] == "missing"
    with rejection("duplicate_trial"):
        evaluate_fixture(("a1", "a2"), (trial, trial))
    forbidden = trial.model_copy(update={"claim": "reservation_completed"})
    assert evaluate_fixture(("a1",), (forbidden,))["correct"] == 0
