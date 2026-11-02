# C4: Execution protocol

Design version 0.4.1. November 2, 2026. Proposed service contract.

The [shared contracts](CONTRACTS.md) define envelopes, references, failures, and package identity.
The [baseline](README.md) selects one read-only offer-selection loop. C8 owns its decisions. C4 owns dispatch and evidence ordering.
Production acceptance cases below are not run. Local harness evidence has a separate scope.

## Logic and ownership

C4 binds each action to one admitted request, fixed package, evidence context, and resource reservation.
It validates the action, records dispatch intent, invokes the registered callable, and records the observed outcome.
For native results, it waits for C2 ingestion before exposing dependent function execution.
For function results, it preserves the exact graph snapshot and underlying operations.
For final results, it applies the package's declared execution mode.

C4 cannot change schemas, functions, source mappings, private evaluator inputs, or model settings.
The first native registry contains only `fixture.search_offers@0.1.0` and `fixture.get_offer_details@0.1.0`.
No booking, payment, delegated agent, arbitrary endpoint, or general host adapter is admitted.

1. **C4-R01:** C4 must reject actions that do not match the run's pinned contracts.
2. **C4-R02:** C4 must save dispatch intent before it invokes a callable.
3. **C4-R03:** C4 must retain every attempt and its resource use.
4. **C4-R04:** C4 must wait for required C2 receipts before dependent function execution.
5. **C4-R05:** C4 must bind every function invocation to one immutable graph snapshot.
6. **C4-R06:** C4 must enforce guarded finalization at the actual result-release boundary.
7. **C4-R07:** C4 must preserve the run's package after a later package activation.
8. **C4-R08:** C4 must keep process completion separate from independent task success.

## Exact contracts

Use the scalar types and `ArtifactRef` from [CONTRACTS.md](CONTRACTS.md). Reject unknown fields with Pydantic.
All objects inherit the shared envelope unless the table defines a nested value.

| Model | Required payload |
| --- | --- |
| `ExecuteRequest` | `admission_ref: ArtifactRef`; `task_request_ref: ArtifactRef`; `package_ref: ArtifactRef`; `host_binding_ref: ArtifactRef`; `projection_id: Id`; `budget_reservation_id: Id`; `mode: engineering_replay\|model_development\|held_out_evaluation` |
| `ActionRequest` | `step: integer[1,12]`; `expected_state_version: integer>=0`; `action: NativeCall\|FunctionCall\|Finalize` |
| `NativeCall` | `kind: "native"`; `tool_version: "0.1.0"`; `call: SearchOffers\|GetOfferDetails` |
| `SearchOffers` | `tool_id: "fixture.search_offers"`; `city: string[1,128]`; `check_in: date`; `check_out: date`; `party_size: integer[1,100]`; `page_token: string[1,1024]\|null` |
| `GetOfferDetails` | `tool_id: "fixture.get_offer_details"`; `offer_id: string[1,128]`; `check_in: date`; `check_out: date`; `party_size: integer[1,100]` |
| `FunctionCall` | `kind: "function"`; `function_id: "select_eligible_offers"`; `function_bundle_ref: ArtifactRef`; `task_request_ref: ArtifactRef`; `required_observation_ids: unique Id[]`; `minimum_revision: integer>=0` |
| `Finalize` | `kind: "finalize"`; `result: FinalSelection` |
| `FinalSelection` | `claim: observed_eligible_offer\|no_supported_offer`; `selected_offer_id: string[1,128]\|null`; `evidence_ids: unique Id[]`; `explanation: literal("")` |
| `ActionResult` | Shared result envelope; `step: integer[1,12]`; `state_version: integer>=0`; `action_status: completed\|needs_evidence\|rejected\|failed\|cancelled`; `call_receipt_ref: ArtifactRef\|null`; `ingest_receipt_ref: ArtifactRef\|null`; `function_result_ref: ArtifactRef\|null`; `guard_receipt_ref: ArtifactRef\|null`; `diagnostic_refs: ArtifactRef[]` |
| `CallReceipt` | `call_id: Id`; `operation_id: Id`; `attempt_id: Id`; `callable_ref: ArtifactRef`; `arguments_ref: ArtifactRef`; `arguments_sha256: Hash`; `started_at: Timestamp`; `finished_at: Timestamp`; `invocation_status: completed\|failed\|timed_out`; `effect_status: "not_applicable"`; `response_ref: ArtifactRef\|null`; `failure_ref: ArtifactRef\|null`; `usage_ref: ArtifactRef` |
| `GuardReceipt` | `package_ref: ArtifactRef`; `policy_ref: ArtifactRef`; `checker_ref: ArtifactRef`; `result_sha256: Hash`; `snapshot_ref: GraphSnapshotRef`; `required_observation_ids: unique Id[]`; `run_state_version: integer>=0`; `outcome: passed\|violated\|needs_evidence\|error`; `constraint_result_ref: ArtifactRef`; `checked_at: Timestamp` |
| `TrialRecord` | `assignment_id: Id`; `task_request_ref: ArtifactRef`; `package_ref: ArtifactRef`; `host_binding_ref: ArtifactRef`; `ordered_operation_ids: Id[]`; `event_range: EventRange`; `snapshot_refs: GraphSnapshotRef[]`; `final_result_ref: ArtifactRef\|null`; `guard_receipt_ref: ArtifactRef\|null`; `usage_ref: ArtifactRef`; `terminal_reason: finalized\|budget_exhausted\|cancelled\|dependency_failed\|host_failed`; `started_at: Timestamp`; `finished_at: Timestamp` |

`GraphSnapshotRef` and `ReadBarrier` are defined by [C2](C02-evidence.md).
`EventRange` contains `run_id: Id`, `first_sequence: integer>=1`, and `last_sequence: integer>=first_sequence`.
`observed_eligible_offer` requires an offer ID and at least one evidence ID. `no_supported_offer` requires a null offer ID.
A `no_supported_offer` result does not claim exhaustive absence. C5 decides task success from the assigned completion contract.
The first profile releases structured claims only. C11 renders a server-owned summary from those fields and their evidence.
Host prose may remain in trace commentary labeled unverified. It is not an authoritative result or an independently scored claim.

Native stay and party arguments must equal the admitted request. The first loop cannot change the task through tool arguments.
The runtime removes null `page_token` before matching the existing native tool contract.
Function arguments resolve the original typed task request. The host cannot replace its budget or currency.
All referenced artifacts must match the server-bound project and agent.

Ordinary and candidate-verification requests require `host_binding_ref` to resolve to a ready C8 mount receipt.
Only authoritative `purpose=host_conformance` permits the [prepared-binding path](MOUNT-CONFORMANCE.md).
C4 must load the server-only grant from the child run row and verify the verifier principal, scope, inputs, package, and expiry.
Possessing a grant or prepared artifact does not authorize dispatch. Ordinary callers cannot select this purpose.
Conformance uses the same action, observation, finalization, and recovery handlers. It cannot recursively request a full mount.
Its retained trials are test evidence, excluded from C5 task scoring.

## Dispatch and observation procedure

1. Resolve admission, package, host binding, and request within the run scope.
2. Verify fixed dependencies and the remaining reservation.
3. Reconcile any incomplete saved operation before accepting another action.
4. Validate the next action and compare the expected run state version.
5. Save the action digest, operation ID, step, reservation, and dispatch intent atomically through C10.
6. Invoke the exact registered callable with the saved arguments.
7. Save its actual response or failure artifact and the terminal call receipt.
8. For a native call, create the C2 observation from those saved artifacts.
9. Wait for its authoritative C2 receipt within the remaining deadline.
10. Advance the incorporated snapshot only after the required ingestion succeeds.
11. Save the action result and advance the run state version.
12. Return the saved action result to C8.

The host may inspect a failed source call and its diagnostics. That failure does not create usable domain facts.
A failure observation references a typed failure artifact when no response exists. C2 cannot extract domain values from that artifact.
Source `observed_at`, arrival time, and replay time remain separate. Replaying a response cannot refresh its source time.
For the first class, the scenario clock is fixed by C0.

The first host permits one in-flight action per run. No parallel native calls or detached ingestion jobs are exposed to C8.
C2 may execute asynchronously in a worker, but C4 waits for the required receipt before completing the action.
An ingestion failure ends the dependent action. It does not erase the source response or advance the graph pointer.

## Function barrier and result release

For each function action, C4 builds a `ReadBarrier` with the pinned projection configuration.
Its required observations include all successful native observations acknowledged to C8 before that action.
The host may add explicit dependencies. It cannot remove earlier observations from the barrier.
C2 resolves one compatible committed snapshot. C3 executes the fixed function over that snapshot.
Later commits cannot change that invocation's values, membership, or provenance.
C4 maps `function_bundle_ref` to C3's `bundle_ref` and supplies the resolved snapshot as `graph`.
It sends `task_request_ref`, `required_observation_ids`, and `function_id` unchanged.
For this first loop, `candidate_ids` is empty. C3 therefore considers all observed candidates within its fixed 100-candidate limit.
The host's `minimum_revision` constrains the C2 barrier. It is not a second graph selector inside C3.

In `optional_functions`, C8 may finalize without calling F. C4 still preserves the final claim and evidence references.
C4 records actual function use. C5 does not require an F call for a correct independent score.

In `guarded_requirements`, C4 performs this finalization protocol:

1. Compare the expected state version and mark the run as `finalizing`.
2. Block new native and function dispatch for that run.
3. Reconcile every previously dispatched operation and required ingestion.
4. Resolve the latest compatible snapshot containing those observations.
5. Run the pinned checker on the exact proposed selection and request.
6. Save its guard receipt with the result digest and run state version.
7. Release the result only if the applicable requirements pass.
8. Atomically save finalization and its receipt through C10.

Unknown evidence returns `needs_evidence`. A violated constraint rejects the selection.
Either result reopens the run at a new state version if its budget remains.
An abstention may finalize as `no_supported_offer`. It cannot acquire a success label from the guard.
Checker execution failure ends the action with an error. A missing checker cannot become an optional-mode fallback.

The first class has no independent source-event stream. Only C4 can submit run observations.
Finalization therefore seals all possible run evidence inputs. A future push source requires a new barrier contract.

## Storage, recovery, and budgets

C10 stores action intents, run state versions, reservations, and event indexes in PostgreSQL.
It stores immutable arguments, responses, receipts, and trials through the artifact store.
C2 owns graph commits and authoritative ingestion receipts. LangGraph checkpoints store references, not replacement authoritative receipts.

One host decision consumes one step, including an invalid action or rejected finalization. The ceiling is 12 steps.
C8 reserves that step through C10 before invoking its decision driver. C4 consumes the same reservation and never increments it again.
Malformed driver output still consumes a decision step, even when no C4 action is dispatched.
Trial usage must include those failed decisions and their model usage through the linked C8 decision ledger.
Delivery of the same action ID and digest returns its saved result without consuming another decision step.
Changed bytes under the same action ID produce `action_collision`.
An argument correction is a new decision. Actual dispatch retries remain separately charged operations.

The first fixture lookup permits one retry after a transient local read failure, within the original deadline.
Fixture calls match case, tool version, and canonical arguments exactly. Missing fixtures return `fixture_response_unavailable` without substitution.
If dispatch completion is uncertain, C4 first resolves its saved receipt by operation ID.
Only a confirmed absent receipt permits exact fixture replay. No retry protocol for provider writes is implied.

Cancellation stops new dispatch. C4 records any completed in-flight result and reconciles any graph commit before closing the trial.
A process restart retains step count, absolute deadline, reservation consumption, package, pending operation, and incorporated revision.
Resume reads authoritative receipts before advancing from a checkpoint. A stale checkpoint cannot repeat a completed semantic action.

`UsageRecord` contains `attempt_id: Id`, `agent_visible_calls: integer>=0`, and `underlying_operations: integer>=0`.
It also contains `elapsed_ms: integer>=0`, `model_calls: integer>=0`, and `provider_usage_refs: ArtifactRef[]`.
Token fields separate input, cached input, output, and reasoning tokens with the provider's inclusion rules.
Each token value carries `measured`, `not_collected`, or `not_applicable`. Unknown usage is not recorded as zero.
Engineering replay records zero model calls and `not_applicable` token and provider-cost fields.
C4 records observable requests and decisions. It does not request hidden reasoning text.

## Reuse and adversarial decisions

Use LangGraph for execution state and supported checkpoint recovery. Use Procrastinate for durable job delivery.
Use Pydantic for action unions and official tool clients for any later admitted provider.
Use C10's SQLAlchemy transaction layer and existing tracing libraries. Do not implement another scheduler, queue, or event broker.
Custom C4 code is limited to domain scope, barriers, package binding, guard routing, and observable receipts.

| Challenge | Rejected approach | Decision |
| --- | --- | --- |
| A checkpoint replays a completed call | Assume checkpoint persistence guarantees exactly-once effects | Reconcile durable operation receipts before redispatch |
| A function sees incomplete ingestion | Run against whichever graph head exists | Require C2's explicit observation barrier |
| A guard passes before contradictory evidence arrives | Release from an earlier function result | Seal dispatch and drain prior observations before the guard |
| Optional mode is called enforcement | Count registered tools as applied constraints | Report actual use and reserve enforcement claims for guarded mode |
| More infrastructure promises generality | Build an arbitrary adapter and a custom workflow engine | Fix one loop and reuse the selected libraries |

## Required service acceptance cases

All cases are proposed and unrun unless the separate harness report names an executed subset.

| ID | Injected condition | Required observation |
| --- | --- | --- |
| C4-T01 | Search then detail response | Ordered call, observation, ingest, and snapshot receipts with unchanged S/F hashes |
| C4-T02 | Required ingestion pending or failed | Zero dependent function dispatches |
| C4-T03 | Old acknowledgement arrives after a new revision | Incorporated revision never moves backward |
| C4-T04 | Same action delivered twice | Same saved result and one semantic action |
| C4-T05 | Changed payload under the same action ID | Collision; original action and graph remain unchanged |
| C4-T06 | Crash after native response or graph commit | Resume reconciles the receipt without duplicate ingestion |
| C4-T07 | Foreign-project reference or modified task arguments | Rejection before callable dispatch |
| C4-T08 | Optional finalization without F | Trial preserved; independent scoring remains possible |
| C4-T09 | Guarded selection with unknown availability | No protected selection released; evidence request remains possible |
| C4-T10 | Contradictory observation pending at finalization | Finalization waits and rejects unsupported selection |
| C4-T11 | Candidate activation during an active run | Original package and dependency hashes remain pinned |
| C4-T12 | Restart or repeated rejected actions near the ceiling | Original deadline and 12-step limit remain effective |
| C4-T13 | Cancellation during ingestion | Commit reconciled; no further dispatch; complete cancellation trial |
| C4-T14 | Fixture response absent or provider-write claim | Explicit failure; no fabricated response or external effect |
| C4-T15 | Dispatch-intent commit fails, or the worker stops immediately before invocation | No invocation without a durable intent; resume reconciles the saved operation |
| C4-T16 | Several rejected attempts precede a completed action | Every attempt and its usage remain recorded; retry does not reset limits |
| C4-T17 | Prepared binding reaches ordinary dispatch, or a conformance grant is copied, expired, or used by another principal | Reject before dispatch; only the exact authoritative conformance child can exercise the staged path |

Record boundary timestamps, hashes, operation counts, and failed attempts for each case.
These checks test execution contracts. They do not establish agent improvement or correctness of the independent evaluator.
