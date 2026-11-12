# PRD 05: Protected action execution

Status: Retained component draft. AppWorld is now the evaluation environment.

## AppWorld scope revision

The [AppWorld implementation plan](07-implementation-plan.md) controls the current evaluation scope.
Retain this document's generic invariants and component responsibilities.
The hotel and stock profiles, fixed two-function catalog, and fixture-specific acceptance counts are superseded.
SQLite source templates and reservation transactions are not AppWorld requirements.
Do not assume global source versions, complete collection reads, or provider idempotency.
Revise these details against the actual AppWorld interface before implementation.
Use official AppWorld splits and evaluation instead of the former generated-world protocol.
This component draft is not yet an implementation-ready AppWorld specification.

## Purpose and scope

This component executes one authorized local reservation from a validated ontology function result. It uses the existing SQLite Model Context Protocol (MCP) server. It does not create an MCP server or contact a booking service.

The component must preserve the relation between the request, observed evidence, declared procedure, and committed effect. It must distinguish a rejected action from a write whose outcome is unknown.

Read this document with [the shared contracts](00-system-contracts.md), [graph construction](03-evidence-graph.md), and [the inference interface](04-inference-tool-interface.md).

## Basis and current implementation

The [paper](../../paper/source/oak-2608.22974v1.pdf), Sections 3.1 to 3.3, places computation and workflow requirements in function control flow. It does not define distributed transactions, idempotency, or uncertain write recovery. Those controls are project requirements.

The current [hook](../../../backend/examples/ontology_loop/hook.py) checks an answer before it permits a reservation. It checks source freshness before dispatch. A separate native call then executes an unconditional reservation insert.

The current [database schema](../../../backend/examples/ontology_loop/sql_kernel.py) gives reservations unique identifiers and idempotency keys. A pending reservation record prevents some conflicting authorizations. These checks do not make the source check and write atomic. They do not establish a durable action state machine or reliable unknown-outcome recovery.

## Terms and fixed choices

An **intent** is one requested business effect with fixed typed arguments. It includes the selected offer, total cost, request binding, and the supporting function receipt.

An **idempotency key** identifies repeated attempts to execute the same intent. The host creates it. A retry must keep it.

A **source version** identifies the authoritative source state. A **graph revision** identifies one accepted graph publication. These values are independent. Reading the same source version again can create a new graph revision.

The source SQLite database stores source records, source versions, and fictional reservations.
The Python runtime owns the accepted graph and function receipts.
It stores its durable snapshots and action journal in a separate private host store.

The model selects the native call. The host checks and binds the call. The existing server executes it. The model never supplies authority by inventing an identifier or receipt.

The ontology condition requires both `assess_stays` and `prepare_reservation`.
These are registered Python kernel functions.
The second function returns a typed action proposal and does not execute a write.
The existing native MCP tool performs the external action.

An explicit evaluation baseline is the only exception to function-receipt admission. It submits a typed model intent bound to observed source versions. It uses the same physical grants, conditional source-version check, idempotency, and run uniqueness rules. It has no generated function or independent semantic oracle. Eligibility and selection errors remain observable for independent scoring.

The evaluation controller fixes this condition before the run. The model cannot enable it. Requirements about semantic function receipts below apply to the ontology condition.

## Inputs and outputs

| Input | Required fields |
| --- | --- |
| Run binding | `run_id`, `surface_id`, `surface_version`, `agent_id`, and `grant_version` |
| Request binding | Canonical typed request and `query_hash` |
| Kernel binding | `kernel_version`, action operation contract, compiled statement, and binding version |
| Function evidence | Assessment and preparation `function_receipt_id` values, result digests, `graph_revision`, `source_version`, and evidence references |
| Proposed action | `operation_id`, selected `offer_id`, and integer `total_cents` |
| Provider capabilities | Atomic conditional write, idempotency, and authoritative action-status lookup |

The host must create `action_id`, `idempotency_key`, and an intent digest. Each dispatch also receives a unique `invocation_id` under PRD 04.

| Output | Required fields |
| --- | --- |
| Action observation | Action identifier, state, outcome, version bindings, and permitted recovery operation |
| Confirmation | Exact reservation identifier, offer identifier, cost, idempotency key, and authoritative receipt reference |
| Private action journal | Immutable intent, dispatch attempts, native results, lookup results, and state transitions |
| Final run report | Business outcome and transport termination as separate fields |

The journal must store named fields. A result digest alone does not replace the fields needed for recovery.

## Requirements

### ACT-001: Require an explicit action contract

The frozen action contract must identify the permitted effect, exact native tool binding, typed arguments, and units. It must also identify prerequisites, the conditional-write rule, postcondition, and recovery operation.

The initial effect is one fictional reservation. The task requires the cheapest eligible offer. Equal prices use ascending offer identifier order. This selection rule must belong to the declared procedure. The host must not invent a second correct-answer procedure at runtime.

The generated `prepare_reservation` procedure must use the approved `select_min` primitive over the complete eligible set. It must check the requested `offer_id` against the declared ordering. It must return `selected_offer` and integer `total_cents` with its assessment binding. An unsupported selection operation blocks construction. It does not permit a handwritten host substitute.

The action contract must not interpret guest capacity as room stock. Room-stock allocation and real bookings are outside this slice.

### ACT-002: Check authority and evidence before preparation

The host must check the current grant and the frozen operation binding. It must require an assessment with status `complete` and a preparation result with status `ready`. The preparation must identify the selected eligible offer.

Function status `ready` is distinct from action state `PREPARED`. A preparation result with status `rejected` must not create an action intent.

The selected offer and cost must match the bound function receipt. The request, surface, kernel, graph revision, and source version must match the action dependencies.

The host must reject an incomplete result, an empty eligible set, a forged receipt, or a stale dependency. A published answer file does not authorize an action.

An unresolved action must block preparation of another reservation intent in this run. The runtime must not use a new key to avoid this restriction.

### ACT-003: Persist the intent before dispatch

The host must create and durably store the complete intent before it exposes an executable write option. This state is `PREPARED`. Preparation does not execute the reservation.

The intent must contain all common bindings, the native operation, typed arguments, and function receipt. It must also contain the source version, graph revision, action identifier, idempotency key, and intent digest.

The journal write must complete before native dispatch. A failed journal write must block dispatch.

The host must reuse the recorded action identifier and key after a process restart. It must reject a repeated key with a different intent digest. It must not alter a prepared intent in place.

### ACT-004: Use an exact action state machine

| Current state | Event and condition | Next state | Required effect |
| --- | --- | --- | --- |
| No action | All preparation checks pass and intent is durable | `PREPARED` | No reservation write |
| `PREPARED` | Model selects the bound call and the dispatch gate passes | `DISPATCHED` | Record the attempt durably, then call native MCP |
| `PREPARED` | Evidence changes, grant changes, or the run stops before dispatch | `CANCELLED` | No reservation write |
| `DISPATCHED` | The declared authoritative status lookup proves the exact reservation exists | `CONFIRMED` | Record the confirmed effect |
| `DISPATCHED` | Authoritative result proves the condition failed and no effect occurred | `REJECTED` | Record the rejection reason |
| `DISPATCHED` | Timeout, lost connection, invalid result, or host interruption prevents a conclusion | `UNKNOWN` | Block new reservation intents |
| `UNKNOWN` | Authoritative lookup finds the exact matching intent | `CONFIRMED` | Record the existing effect |
| `UNKNOWN` | Authoritative lookup proves absence, no invocation remains in flight, bindings pass all checks, and the episode is active | `PREPARED` | Permit a bounded retry with the same key |
| `UNKNOWN` | Authoritative lookup proves absence, but dependencies are stale or the run has stopped | `CANCELLED` | Permit no retry of this intent |
| `UNKNOWN` | Lookup cannot establish an outcome within the recovery limit | `UNKNOWN` | Stop inference and report the unresolved action |

`CONFIRMED`, `REJECTED`, and `CANCELLED` are terminal for that intent. A rejected or cancelled intent must not become a new intent automatically. A later attempt requires a new complete evidence batch and a new model selection under the same task grant.

Write success or an affected-row count alone must leave the action in `DISPATCHED` until the status lookup establishes its outcome. An inconclusive lookup changes the state to `UNKNOWN`. An explicit authoritative result can establish a rejection only if it proves that no effect occurred. Zero affected rows alone do not prove this condition.

The host must treat a recovered `DISPATCHED` journal entry as `UNKNOWN` until reconciliation establishes the outcome. It must not assume that a process interruption occurred before the database commit.

### ACT-005: Maintain authoritative source versions

The local database must contain one integer `source_version` for the supported source tables. The hotel source scope contains hotel, offer, and policy records. Every supported source insert, update, or delete must advance this version in the same transaction. Database triggers must enforce this discipline for the local slice.

This scope includes collection membership and relation membership. Adding a cheaper offer or changing a relation endpoint must invalidate an earlier decision. A version check on only the selected row is insufficient. The typed request remains fixed by `query_hash` for the run.

Source queries must return the source version and source records from one database statement. The envelope must keep the version when the record list is empty.

All reads in the accepted batch must have the same source version. A version mismatch must discard the unpublished batch and require complete reads again.

The source version must not advance for graph publication or action-journal updates. These are host evidence and control records. The host must not use `graph_revision` as a substitute for source freshness.

The local reservation does not change hotel, offer, or policy facts. It does not advance their source version. It does change action availability. Confirmation must invalidate the executable reservation option and any decision that depends on reservation existence.

A later declared action can change source facts or relation membership. Such an action must advance the affected source version in the same write. The first slice does not support undeclared action effects.

A schema change, trigger removal, or source mutation path that bypasses version discipline makes the provider incompatible. The host must stop protected writes until the contract is restored.

### ACT-006: Bind the Python decision to a conditional external write

The Python executor performs eligibility, cost, and selection computations before action preparation.
The host checks both function receipts, their dependencies, and the exact proposed action arguments.
It then locks the run's request, kernel, graph revision, and action intent against replacement during dispatch and reconciliation.
The durable pending-action state preserves that restriction after a host restart.

The SQLite action adapter produces one conditional native write from this checked immutable intent.
It does not translate or repeat the Python reasoning procedure in SQL.
The provider statement checks these conditions during the same database operation that inserts the reservation:

- The authoritative source version equals the intent's source version.
- No conflicting reservation exists for this intent or run.
- The idempotency key is unused, or an existing reservation has the identical intent.

Use a conditional `INSERT ... SELECT` and database uniqueness constraints for this local action adapter.
The inserted offer, cost, request hash, and receipt references come from the exact host-bound intent.
The Python receipt checks and provider write are separate operations.
The run-state lock prevents host evidence replacement between them.
The provider's atomic source-version check prevents a stale external decision from committing.

Do not claim that a database transaction checks the separate Python graph directly.
A separate source check followed by an unconditional `INSERT ... VALUES` does not meet this requirement.

The idempotency key must be unique. The local database must also permit at most one reservation effect per run. The reservation record must store the intent digest and dependency versions needed for verification.

The host must reject native Structured Query Language (SQL) that differs from the compiled statement.
A model must not add clauses, change selected records, or remove a condition.

The journal transaction and native write remain separate. The state machine must tolerate an interruption between them. It must not claim a distributed transaction across these boundaries.

### ACT-007: Confirm the exact effect

A successful transport response is insufficient. The host must check the reservation through the declared authoritative status operation.

The lookup must identify the reservation by action identifier and idempotency key. Its result must match the intent digest, offer, cost, request, and version bindings.

An affected-row count of zero does not identify the outcome. It can mean a repeated intent or a failed condition. The host must inspect the authoritative state.

The host must not mark an action confirmed because any reservation exists. It must confirm the exact intended reservation.

A conflicting record must produce `REJECTED` when the provider proves that this intent did not execute. Otherwise, the outcome remains `UNKNOWN` with an integrity error. The host must not overwrite the conflicting record.

### ACT-008: Reconcile uncertain outcomes before retry

After an uncertain dispatch, the host must first establish the original invocation's state at the provider boundary. The invocation must have ended or been cancelled. The host must then perform the declared status lookup.

The runtime must not infer absence from a timeout or a transient lookup error. It must not retry with a new key.

The initial limits are two dispatch attempts and three status lookups in total for one intent.
Status lookups include normal confirmation and uncertain-outcome reconciliation.
Before exposing a prepared action, reserve five slots from the run's 24-tool-invocation limit.
Python kernel calls and other MCP calls cannot consume these reserved slots.

If the model or CLI has stopped, the host must perform permitted read-only reconciliation. It must use the same existing MCP status binding. Record `origin=recovery` for these invocations and `origin=model` for model-selected invocations. Both consume the same call budget. Recovery does not create another reservation. A further write requires a permitted model-selected retry within the same episode limits.

A retry may occur only after authoritative absence is established and the dispatch preconditions still hold. It must use the same intent, action identifier, idempotency key, and compiled statement.

If source or graph bindings changed, the old intent must not retry. The host must establish absence before it can close that intent and permit new evidence collection.

When recovery is exhausted, the run must stop with `UNKNOWN`. It must preserve the journal and expose the exact status operation needed for later reconciliation. It must not report task success or definitive write failure.

### ACT-009: Reject providers that cannot enforce the contract

Before the first model call, the host must check these provider capabilities:

1. Source reads return records and a trustworthy version together.
2. Source changes update that version atomically.
3. The write checks the expected version and commits the effect atomically.
4. A repeated idempotency key cannot create a second effect.
5. Status lookup can establish the exact committed intent or authoritative absence.
6. The client can correlate calls and prevent overlapping dispatch for this run.

A missing capability must produce `PROVIDER_CAPABILITY_MISSING`. The host must not expose an executable protected-write option.

The host must not substitute a warning, model instruction, timeout, or local Boolean for a missing provider guarantee. Reads and analysis may continue only if their contracts still pass all checks. The final report must state that the requested action is unsupported.

The local SQLite implementation can support these capabilities through schema constraints, triggers, declared SQL, and the client dispatcher. An arbitrary external MCP server cannot be assumed to support them.

### ACT-010: Bound permissions during pending writes

From `DISPATCHED` until the outcome is known, the runtime must deny a new reservation. It must also deny graph replacement, kernel replacement, and a change of request. It must permit only the declared reconciliation operations and safe termination.

The runtime must serialize calls as specified in RUN-004. A file lock around separate before and after hooks does not satisfy this requirement.

The host must recheck the grant immediately before dispatch. A revoked grant prevents a new dispatch. It does not erase an effect that already occurred. Reconciliation may inspect that effect only through the host's configured recovery authority.

### ACT-011: Return actionable outcomes

| Outcome | Model-visible information | Permitted recovery |
| --- | --- | --- |
| `PREPARED` | Bound intent and exact native call option | Execute that option or stop without a write |
| `SOURCE_CHANGED` | Invalidated dependencies and no confirmed effect | Reconcile if necessary, then collect a complete new batch |
| `REJECTED` | Authoritative rejection reason | Do not repeat the same rejected intent |
| `CONFIRMED` | Exact reservation and receipt reference | Publish the task result |
| `UNKNOWN` | Action identifier, stable key reference, and uncertainty reason | Execute only the declared reconciliation operation |
| `PROVIDER_CAPABILITY_MISSING` | Missing guarantee and unsupported action | Complete analysis without claiming the action occurred |

The runtime must not include unvalidated raw provider text in these observations. The private trace keeps that text for diagnosis.

### ACT-012: Preserve effect status across run termination

The final report must separate action state, task result, model termination, and transport termination. A confirmed reservation remains confirmed if the model later reaches its turn limit.

An unconfirmed or unknown action prevents a successful end-to-end task result. An empty eligible set can complete the task without a reservation when the task contract permits this result.

The evaluation component must score first proposals separately from accepted effects. Runtime rejection must not erase an incorrect model proposal from the trace.

## Acceptance criteria

1. A wrong offer, wrong price, stale receipt, or ungranted action is rejected before native write dispatch.
2. A crash after intent persistence but before dispatch produces no reservation and preserves the same key.
3. A source mutation between function evaluation and dispatch causes the conditional write to insert no reservation.
4. A source mutation concurrent with the write produces a database order that satisfies the action contract. The write never commits against an obsolete version.
5. Two attempts with the same key and intent produce exactly one reservation.
6. The same key with different intent arguments never changes the earlier reservation.
7. Two keys for the same run cannot create two reservation effects.
8. A timeout after a successful commit enters `UNKNOWN`. Reconciliation finds the exact reservation and reaches `CONFIRMED` without another effect.
9. A zero-row write result is not treated as success or failure until the status operation establishes the outcome.
10. A failed status lookup does not authorize another booking key.
11. A provider without atomic conditional writes cannot expose the protected action.
12. A model or CLI failure after confirmation remains distinct from the committed business effect.

## Objections and release limits

A function can pass type checks and still implement the wrong domain rule. OWL consistency and runtime receipts do not remove that risk. Construction tests, unseen-case evaluation, and repair remain necessary.

The first slice tests a local fictional reservation. It does not establish safe payment, cancellation, stock allocation, or cross-provider transactions.

The current prototype does not meet ACT-003 through ACT-009. Unique keys and pre-dispatch checks alone must not be presented as proof of these requirements.
