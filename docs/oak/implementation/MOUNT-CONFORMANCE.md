# Nonrecursive mount conformance

Design version 0.4.1. Owners: C8 binding, C4 dispatch, C10 storage and authorization.
This is a proposed production contract. The declaration checks do not execute these probes.
Use pytest, the registered production handlers, the existing LangGraph checkpointer, and C10's ledger.
Do not create an adapter framework, alternate executor, scheduler, or unrecorded task runner.

## Prepare before testing

C8 resolves a normal or candidate-verification run's exact package and its passed registry receipt.
It checks dependency availability and callable contracts, then publishes a `PreparedHostBinding` artifact.
This artifact contains resolved bindings, not permission to dispatch. Its artifact availability may be `ready`; its binding state is only `prepared`.
The existing worker runs the registered pytest suite against this prepared binding. It does not call full mount from a probe.
Only after all seven required probe receipts pass may C8 publish `HostMountReceipt.status: ready` for the requesting run.
The package need not be active for candidate verification. The existing internal verification authorization still applies.

## Exact internal contracts

Use the shared strict scalar types and `ArtifactRef`. Unknown fields are forbidden. These are not browser request models.
`MountProbeId` is the seven `mount` probe IDs in [AGENT-SHAPE](AGENT-SHAPE.md), excluding both registry probe IDs.

| Model | Required fields |
| --- | --- |
| `PreparedHostBinding` | `profile: "prepared-host-binding/1"`; `state: "prepared"`; `project_id`, `agent_id`, `parent_run_id`, `mount_operation_id`: `Id`; `agent_version: positive_integer`; `host_config_ref`, `package_ref`, `registry_receipt_ref`: `ArtifactRef`; `resolved_function: C8.ResolvedFunctionBinding`; `tested_dependency_refs: unique ArtifactRef[]`; `implementation_fingerprint: Hash` |
| `MountProbeSuite` | `profile: "mount-probe-suite/1"`; `runner_ref: ArtifactRef`; `fixture_manifest_ref: ArtifactRef`; `max_seconds: integer[1,900]`; `max_action_attempts: integer[1,2304]`; `cases: MountProbeCase[1..64]` |
| `MountProbeCase` | `case_id: Id`; `probe_id: MountProbeId`; `pytest_node_id: registered nonempty string`; `task_request_ref`, `source_manifest_ref`: `ArtifactRef`; `max_decisions: integer[1,12]` |
| `ConformanceGrant` | `profile: "host-conformance-grant/1"`; `project_id`, `agent_id`, `parent_run_id`, `run_id`, `assignment_id`, `evidence_context_id`, `checkpoint_thread_id`: `Id`; `agent_version: positive_integer`; `probe_id: MountProbeId`; `case_id: Id`; `prepared_binding_ref`, `suite_ref`, `admission_ref`, `task_request_ref`, `source_manifest_ref`: `ArtifactRef`; `implementation_fingerprint: Hash`; `verifier_principal_id: Id`; `expires_at: Timestamp` |

The suite is a server-registered immutable artifact. Its node IDs select installed tests, never uploaded Python or arbitrary pytest arguments.
Every required probe ID has at least one case. Case IDs are unique. The complete declared case set must finish before the suite can pass.
The dependency list includes the exact shape, workflow, callable registry, contract schemas, hook code, runtime, and package artifacts.
Its fingerprint uses AGENT-SHAPE's canonical dependency hashing rule. The suite and runner hashes remain additional cache inputs.
A grant is a worker-only record. Possessing its ID or bytes is not an authorization capability.
Do not put grants, prepared bindings, private evaluator references, or test-control parameters into host decisions or browser requests.

## Authoritative isolated rows

For each uncached case, C10 creates one assignment and one run with `purpose: host_conformance` in its existing tables.
The assignment keeps the parent's `admission_id` as its project, configuration, and clock anchor.
Its case membership comes exclusively from the registered public suite, not the admission's scored case population.
Use `condition_id = "hc_" + sha256(canonical_json([mount_operation_id, suite_sha256, case_id]))` and `repetition: 1`.
Same-command delivery retries resolve these existing assignments and runs. They cannot allocate a new repetition or deadline.

| Existing table | Required narrow additions or constraints |
| --- | --- |
| `assignments` | Extend `purpose` with `host_conformance`; add nullable `conformance_suite_ref` and `conformance_case_id`; both are nonnull exactly for this purpose; `verification_id` is null |
| `runs` | Extend `purpose` with `host_conformance`; add nullable `parent_run_id`, `prepared_binding_ref`, and `conformance_grant_ref`; all are nonnull exactly for this purpose; parent is ordinary or candidate verification in the same project, agent, version, and package; `verification_id` is null |
| `operations`, `attempts`, `reservations`, `events` | Reuse existing run foreign keys and uniqueness rules; conformance actions belong to their child run, never to the parent run's decision ledger |

C10 allocates separate checkpoint, evidence-context, and projection identities for every child run.
Its transaction publishes the assignment, run, grant index, and initial reservation before a handler can dispatch.
Write grant bytes first through the existing artifact store. A failed transaction publishes no usable grant or runnable child.
The suite manifest and authoritative child rows, not pytest's console output, identify the required cases and completed operations.
No separate conformance-session table is needed. The prepared binding and suite identify the batch; child rows retain its evidence.

## The only staged dispatch path

Ordinary and candidate-verification execution still require `ExecuteRequest.host_binding_ref` to resolve to a ready `HostMountReceipt`.
For `host_conformance` only, that same field must equal the child row's `prepared_binding_ref`.
C4 loads the grant from the authoritative row and verifies its exact principal, run, assignment, package, input, and evidence scope.
C10 rechecks the initiating command's authorization. Only the registered verifier service may use this path.
A browser, ordinary worker, copied grant, foreign child, changed dependency, expired grant, or terminal child must be rejected.
The grant never authorizes activation, private evaluator access, model calls, provider calls, or writes to another run's evidence.

C8 initializes the same host state and registered handlers with this checked prepared binding.
For this purpose only, `HostState.mount_receipt_ref` is null and `prepared_binding_ref` is nonnull; other purposes require the reverse.
The conformance load branch must not call full mount, request its own probe receipts, or enqueue another conformance batch.
Pytest drives declared cases through the same decision reservation, C4 dispatch, C2 ingestion, finalization, and recovery code.
Restart tests reopen the same authoritative rows and checkpoint with the same grant. They do not rebuild a fresh run.
Fault injection belongs to the installed test fixtures. It cannot be selected through a public endpoint or a model action.

## Source isolation, limits, and closure

The suite's fixture manifest is an explicit public conformance subset of the registered callable fixture manifest.
Tests use the original callable implementations and exact tool contracts. They cannot replace a callable with a passing stub.
Each source response must match the grant's suite case, tool, version, and canonical arguments before C2 can ingest it.
The suite case supplies its typed request and allowed public source IDs. The package still supplies all interpretation code and policies.
Use the parent admission's fixed scenario clock. No probe may refresh source time, borrow evaluator-private cases, or preload task evidence.
Grant-scoped source selection is permitted only for conformance; ordinary dispatch continues to use its admitted case and sources.

All children share `deadline_at = min(parent.deadline_at, batch_started_at + suite.max_seconds)`.
Each case has its declared decision ceiling, capped at 12. A thirteenth-action test records rejection without creating a thirteenth semantic action.
Child reservations and usage are separate setup costs. They do not consume the parent's decision count or disappear from resource accounting.
C10 reserves the complete registered suite's operation limits from the initiating command's admitted resource allocation before creating children.
An insufficient allocation blocks the probe batch. Child runs cannot mint additional construction rounds or resource authority.
The first suite sets `max_action_attempts` to three times the sum of its case decision ceilings.
One charged unit is a native, function, or finalization invocation attempt through C4 after durable intent, including failed attempts and retries.
Validation rejections before invocation retain diagnostics but consume no invocation unit. Underlying database operations remain separately recorded costs.
C10 atomically debits the shared suite reservation before each invocation. Redelivery of a completed attempt cannot debit it again.
Exhaustion blocks new invocations, closes unresolved children with `conformance_budget_exhausted`, and makes the affected probe `error`.
The error is a diagnostic code; the C4 trial terminal reason is `budget_exhausted`. No passing suite can omit those children.
Probe elapsed time counts against the parent's existing wall-clock deadline. Retries and restarts cannot extend either deadline.
Cancellation or authorization loss stops new child dispatch. Existing C4 reconciliation records completed work before closure.

The production close handler may retain a normal `TrialRecord` for each child, to exercise the actual terminal path.
C5 must reject `host_conformance` assignments before resolving an evaluator. No child trial enters verification regression or task denominators.
UI run summaries must retain the conformance purpose. They cannot display a probe's final selection as the user's task result.
On success, failure, cancellation, or timeout, close all children before publishing the suite result; terminal children invalidate their grants.
An interrupted worker resumes or closes the same children through existing retry and deadline handling. It cannot abandon live grants.
Preserve referenced receipts, source artifacts, checkpoints, and graph evidence under existing retention rules. Cleanup never deletes user task data.

## Probe receipts and readiness

Aggregate each probe's complete case set into one C8 `CapabilityProbeReceipt` with its exact fingerprint, suite, inputs, observations, and diagnostics.
A passing probe requires every assigned case and expected rejection to pass. Missing cases are `not_run`; harness faults are `error`.
Required negative cases include ordinary dispatch with a prepared binding, a copied grant, recursive conformance dispatch, and scoring a child trial.
Reuse only server-issued passed receipts for identical dependency, suite, and runner hashes. Never reuse a grant or child run for another mount.
Even with cached probes, C8 checks current authorization, artifact availability, exact parent scope, and checkpoint identity before ready publication.
Failed or missing probes yield a rejected mount. No partial catalog or prepared binding becomes available to ordinary dispatch.
