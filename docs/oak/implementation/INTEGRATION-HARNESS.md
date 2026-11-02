# Offline integration harness

Harness contract: `oak-contract-harness/1`. Design baseline: `0.4.1`. November 2, 2026.

The local harness runs. It tests a subset of the proposed integration rules with Pydantic, SQLite, and published synthetic inputs.
It does not implement the product API, UI, authentication provider, queue, schema builder, or repair algorithm.
Its messages are not wire-compatible with the production [contracts](CONTRACTS.md).

## Run and inspect

Run from the repository root:

```sh
.venv/bin/python scripts/check_oak_contracts.py
```

The command creates a new directory under `.runtime/oak-contracts/`. It preserves previous runs.
It writes `receipt.json`, `tests.xml`, `pytest-output.txt`, `demo.json`, and the demonstration SQLite database.
The receipt records each assigned test, outcome, duration, Python version, and source-file digest.

The publication run passed **70 of 70 assigned checks**: 30 starting-declaration checks, 24 SQLite substitute checks, and 16 task-boundary checks.
Its local receipt is `.runtime/oak-contracts/20261102T213043Z-3e8a7225/receipt.json`, relative to the repository root.
It records each suite separately and hashes the tested code and input fixtures.
The [task-boundary validator](../../../oak_contracts/task_boundary.py) and its [tests](../../../tests/oak_contracts/test_task_boundary.py) check two task definitions under one registered loop catalog.
They do not implement the production multi-task lifecycle or establish runtime isolation.
The earlier 54-check run remains at `.runtime/oak-contracts/20261102T204349Z-5627fb0c/receipt.json`.
The [shape validator](../../../oak_contracts/agent_shape.py) rejects unsupported tools, channels, effects, profiles, fields, and bounds.
Its [tests](../../../tests/oak_contracts/test_agent_shape.py) also check the complete preset and generated JSON Schema.
These checks do not execute the managed host, source adapter, or production conformance probes.

The earlier checked run used Python 3.12.8 and the root environment. **24 of 24 assigned checks passed.**
Ruff also passed for the harness, tests, and runner. The harness required no additional dependency.
StrictDoc was installed separately for documentation. The harness was rerun after that environment change and still passed 24 of 24 checks.
This is an exhaustive local fixture count. It is not a population accuracy estimate.

The earlier local receipt is `.runtime/oak-contracts/20261102T195451Z-2fd10a1c/receipt.json`.
The demonstration result is `.runtime/oak-contracts/20261102T195451Z-2fd10a1c/demo.json`.
The subsequent root verification receipt is `.runtime/oak-contracts/20261102T201512Z-a8875ae3/receipt.json`.
These ignored files are local evidence. A different checkout must run the command to create its own receipts.

## Implemented path

The [runner](../../../scripts/check_oak_contracts.py) creates a synthetic project and an agent configuration.
It stores immutable package references and a recorded verification receipt.
It activates that package and starts one scripted development run.

The script ingests the saved search response. The first function result contains no eligible offer.
It then ingests the saved detail response. The second result identifies `o3` as eligible.
The independent literal fixture evaluator accepts that selection.

S and F remain unchanged between the two calls. New source evidence causes the changed result.
This demonstrates observation enrichment, not schema repair or model improvement.
Search coverage remains incomplete. The result cannot support an exhaustive-search or globally-cheapest claim.

The script records four agent-visible operations: two native response replays and two function calls.
It also records two graph commits. These operation categories overlap and must not be added into one cost count.
There are zero model calls and zero external provider calls.
The native responses come directly from saved files. No live provider or general host adapter runs.

The fixture source uses integer dollar amounts. The harness converts those amounts to integer cents before comparisons.
The harness rejects other numeric representations. The production adapter must implement C0's wider exact decimal contract.

## Code and tested responsibilities

| File | Responsibility |
| --- | --- |
| [models.py](../../../oak_contracts/models.py) | Strict subset contracts, package dependencies, repair-routing requirements |
| [store.py](../../../oak_contracts/store.py) | Scoped local persistence, immutable snapshots, receipts, atomic activation, durable reservations |
| [selection.py](../../../oak_contracts/selection.py) | Fixed source mapping, unknown/conflict handling, deterministic offer checks |
| [evaluator.py](../../../oak_contracts/evaluator.py) | Literal expected result for published `dev-001`, independent of selection code |
| [fixture.py](../../../oak_contracts/fixture.py) | Existing fixture loading and exact runtime implementation identity |
| [test_contracts.py](../../../tests/oak_contracts/test_contracts.py) | Fault injection and independent state assertions |

The SQLite test module blocks Python socket connections. All checks run without a model or service connection.
This prevents accidental network use through the tested Python path. It is not an operating-system network sandbox.

## Executed coverage

Names below identify real tests. The three logic-status cases are separate parameterized assignments.

| Contract or failure | Executed test name | Established limit |
| --- | --- | --- |
| Same IDs in different projects | `test_cross_project_same_ids_do_not_grant_access` | Local membership and agent/context scope |
| Known hash without authorization | `test_hash_knowledge_does_not_grant_artifact_access` | Artifact access still requires project membership |
| Changed bytes or artifact kind | `test_artifact_bytes_and_kind_are_verified` | Corrupt content cannot resolve as the declared artifact |
| Unknown field, version, or schema mismatch | `test_contracts_reject_unknown_fields_and_schema_mismatch` | Rejection before dependent package use |
| User submits verifier results | `test_user_cannot_issue_verifier_receipts` | Local owner role cannot issue a verification receipt |
| Failed, unrun, or errored logic check | `test_failed_or_unrun_layer_blocks_activation` | Each status blocks local activation |
| Missing gate or changed test inputs | `test_report_missing_gate_or_changed_test_inputs_blocks_activation` | Complete report and exact input digest set required |
| Modified verification report | `test_tampered_report_cannot_activate` | Report content digest is checked |
| Changed base or wrong candidate | `test_stale_activation_and_candidate_report_mismatch` | Compare-and-swap activation and candidate binding |
| Active run during promotion | `test_active_run_keeps_package_after_activation` | Existing run retains its package; next run gets the new package |
| Commit succeeds, acknowledgement is lost | `test_lost_ack_replay_after_reopen_has_one_revision` | Reopened SQLite returns the original receipt without another revision |
| Observation identity reused with different bytes | `test_changed_observation_identity_is_rejected_without_write` | Collision leaves the projection unchanged |
| Concurrent commits at one parent | `test_concurrent_commits_have_one_winner_at_parent` | One SQLite commit wins; the other reports a stale parent |
| Missing dependency and later revision | `test_required_evidence_and_stable_revision` | Required observations must exist; old snapshots remain stable |
| Unknown, false, and conflicting evidence | `test_unknown_conflict_and_false_remain_distinct` | No missing or conflicting availability becomes eligible |
| Wrong scope or boolean in a numeric field | `test_wrong_request_scope_and_bad_type_leave_no_projection` | Rejection leaves zero committed observations |
| Stale source or mixed package view | `test_stale_source_and_mixed_package_view_are_rejected` | Frozen fixture clock and package binding apply |
| Restart and duplicate completion | `test_budget_reservations_survive_reopen_and_completion_redelivery` | Reservation persists; completion debits once; deadline does not reset |
| Expired deadline or operation collision | `test_deadline_and_operation_collision_do_not_create_calls` | No new reservation is created |
| Proposed schema change | `test_schema_repair_invalidates_dependents_and_rejects_stale_or_held_out` | Computes required invalidation set; rejects stale or held-out proposals |
| Wrong final choice after successful local work | `test_evaluator_rejects_wrong_result_despite_local_success` | Independent literal oracle can reject the result |
| Missing or duplicate trial | `test_evaluator_preserves_denominator_and_rejects_duplicate` | Missing trial stays in denominator; duplicate trial is rejected |

The repair test checks routing requirements only. It does not rebuild a schema, reproject facts, recompile functions, or run HermiT.
The receipt's `logic` status comes from a test substitute. It is never evidence of formal consistency.

## Trust assumptions of this substitute

The test setup injects subjects and seeds membership. It does not authenticate a caller or verify a service credential.
The verifier fixture can submit recorded statuses. No component test result is automatically inspected before that receipt is stored.
The activation caller supplies `expected_input_hashes`. The harness checks equality with the stored report, not approval by a policy registry.
Production C6 must derive the required inputs and suites from the frozen, registry-approved policy. Caller agreement alone is insufficient.

The fixture's schema and function artifacts describe one fixed implementation. They are not a compiled domain schema or a generated function bundle.
Their manifest pins the selection module. The runner separately records all harness source hashes.
This tests local immutable references, not complete production dependency closure or OWL fidelity.
The harness context binds a package directly. Production C10 must also bind the context to its admitted run or construction sample.

The literal evaluator accepts a supplied fixture evidence identifier. It does not resolve that identifier through a protected source service.
The production C5 evidence-resolution and private-answer tests remain necessary, even when this literal oracle passes.

## Deliberate limits and required next tests

| Boundary | Current substitute or omission | Required production test |
| --- | --- | --- |
| Authentication | Test subjects are injected | Real OIDC login, issuer/audience checks, PKCE/state/nonce, session expiry, logout, CSRF |
| Authorization | Local membership table | HTTP object access, worker scope, artifact downloads, events, cache keys, membership revocation |
| Storage | One SQLite transaction domain | PostgreSQL/Neo4j/file-store failure matrix and authoritative-receipt reconciliation |
| Graph store | JSON snapshots in SQLite | Neo4j locking, uniqueness contention, stable revision reads, and graph/receipt atomicity |
| Queue | Reservation invariant only | Selected queue library redelivery, worker death, cancellation, deadline, and recovery |
| LangGraph | No workflow runs | Checkpoint resume against the job operation ledger, with one owner for retries |
| Schema repair | Typed proposal and invalidation list | Real compiler/HermiT local loop plus score-driven repair, affected rebuilds, and regressions |
| Functions | One fixed Python implementation | C3's registered-callable validation, dependency rejection, and independent semantic fixtures |
| Trial finalization | No dispatch seal | Seal the run, reconcile dispatched work, bind the latest graph, run guards, then commit the result |
| Evaluator | Published `dev-001` literal oracle | General scorer, independently resolved source evidence, evaluator isolation, and private-answer denial |
| Host loop | Scripted source loading | Exact replay-call matching, bounded C8 loop, cancellation, budget, and lifecycle hooks |
| Trace | Local events and test receipts | Full invocation/attempt/operation causal chain and token/cost accounting |
| Interface | No HTTP or browser | Generated OpenAPI client, browser journeys, stale views, scope isolation, and accessibility |

The original IV-01 through IV-22 inventory remains a production acceptance inventory.
Passing this subset does not mark all 22 IV cases as passed.
In particular, external write reconciliation, private-answer isolation, partial host mount, and actual guard routes remain untested here.

## Build versus reuse

The harness reuses Pydantic validation, SQLite transactions, pytest, and the existing project environment.
Its custom code makes domain-specific invariants observable. It is deliberately not a production service foundation.

Use the [selected libraries](CONTRACTS.md) for production auth, sessions, ORM, migrations, jobs, HTTP, frontend data access, and graph rendering.
Do not copy the harness membership table into a password system or its reservation table into a queue.
Do not extend its fixed function into a custom programming language.
Keep only the scope, identity, revision, package, and independent-scoring rules when implementing the real boundaries.

These checks establish local contract behavior only. They supply no task-performance denominator, model comparison, or ontology-benefit result.
