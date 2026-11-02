# C2: Evidence and graph projection

Design version 0.4.0. November 2, 2026. Proposed service contract.

The [baseline](README.md) controls shared contracts. [C0](C00-task-admission.md) defines admitted sources and the first task.
The existing [C2 specification](../02-evidence-graph.md) supplies the paper comparison.
All service acceptance tests below are required and not run. The local harness uses a separate SQLite substitute.

## Purpose and selected mechanism

C2 turns observed source values into scoped facts that functions can inspect.
C2 owns extraction, identity resolution, graph revisions, provenance, and ingestion receipts.
C2 cannot modify the schema, function implementation, active package, or source-provider state.

The first class uses deterministic field mappings over the two admitted JSON tool responses.
The mapping preserves absent fields as unknown. It converts legacy dollar amounts through C0's exact decimal conversion.
This is a declared implementation adaptation. The paper uses schema-conditioned extraction and key-based merging in its construction loop.
See [OaK section 3.2, Step 2](https://arxiv.org/html/2608.22974v1#S3.SS2).

Do not introduce model extraction until deterministic projection and independent source-faithfulness tests pass.
A later model extractor must return the same typed candidates. Its prompts, settings, outputs, and costs require separate versions and receipts.

## Normative requirements

1. **C2-R01:** C2 must resolve every input within its authorized project, agent, and evidence context.
2. **C2-R02:** C2 must bind each observation identity to one immutable raw payload digest.
3. **C2-R03:** C2 must retain source identity, source time, request scope, and source pointers for each assertion.
4. **C2-R04:** C2 must reject unsupported values without inventing replacements.
5. **C2-R05:** C2 must commit a graph revision and its ingestion receipt in one Neo4j transaction.
6. **C2-R06:** C2 must preserve all committed revision contents.
7. **C2-R07:** C2 must return the original receipt when an identical ingestion request repeats.
8. **C2-R08:** C2 must create a new projection when an interpretation dependency changes.
9. **C2-R09:** C2 must block a dependent read until its required observations have successful ingestion receipts.
10. **C2-R10:** C2 must reject private evaluator references as world-evidence inputs.

## Exact payload contracts

Objects use strict validation and reject unknown fields. IDs and artifact references follow C0.
`Scope` contains `project_id`, `agent_id`, and `evidence_context_id`.
The context belongs to one run or one construction sample, never both.
`RequestScope` contains `case_id`, `city`, `check_in`, `check_out`, and `party_size` with C0's bounds.
`ProjectionConfig.scenario_now` must equal the admission's pinned `ClockConfig.scenario_now`.
Its mapping and normalization references must match the package. Reject a caller-selected interpretation or clock before ingestion.

| Object | Required fields and types |
| --- | --- |
| `ToolObservation` | `scope: Scope`; `observation_id: ID`; `call_id: ID`; `tool_id: admitted enum`; `tool_version: "0.1.0"`; `arguments_sha256: Digest`; `request_scope: RequestScope`; `raw_ref: ArtifactRef`; `provider_namespace: string`; `account_scope: string`; `source_record_id: ID`; `observed_at: Timestamp`; `received_at: Timestamp`; `replayed_at: Timestamp`; `invocation_status: completed\|failed\|timed_out`; `effect_status: "not_applicable"`; `coverage: Coverage` |
| `Coverage` | `state: partial\|complete\|unknown`; `next_page_token: string\|null`; `scope_sha256: Digest`; `basis: source_assertion\|fixture_manifest\|unknown`; `basis_ref: ArtifactRef\|null` |
| `ProjectionConfig` | `schema_ref: ArtifactRef`; `schema_verification_ref: ArtifactRef`; `extractor_ref: ArtifactRef`; `mapping_ref: ArtifactRef`; `source_policy_ref: ArtifactRef`; `normalization_ref: ArtifactRef`; `scenario_now: Timestamp` |
| `IngestRequest` | Shared envelope; `scope: Scope`; `projection_id: ID`; `config: ProjectionConfig`; `expected_parent_revision: integer>=0`; `observation: ToolObservation`; `deadline_at: Timestamp`; `budget_reservation_id: ID` |
| `GraphSnapshotRef` | `scope: Scope`; `projection_id: ID`; `revision: integer>=0`; `revision_sha256: Digest`; all six configuration artifact digests; `scenario_now: Timestamp`; `included_observation_ids: unique ID[]`; `coverage: Coverage` |
| `IngestReceipt` | `receipt_id: ID`; `operation_id: ID`; `replay_key: Digest`; `payload_sha256: Digest`; `status: succeeded\|failed\|cancelled`; `component_status: complete\|partial\|rejected`; `snapshot: GraphSnapshotRef\|null`; `parent_revision: integer>=0`; `accepted_assertion_ids: ID[]`; `rejected_items: Diagnostic[]`; `unknown_fields: FieldAddress[]`; `conflicts: Conflict[]`; `created_at: Timestamp` |
| `ReadBarrier` | `scope: Scope`; `projection_id: ID`; `required_observation_ids: unique ID[]`; `minimum_revision: integer>=0`; `config_sha256: Digest` |

`Diagnostic` contains `code`, `owner`, `stage`, `operation_id`, `source_pointer`, `retryable`, and `message`.
`FieldAddress` contains `entity_key`, `predicate_id`, and `reason` from `absent`, `null`, `invalid`, `stale`, or `conflict`.
`Conflict` contains `entity_key`, `predicate_id`, `assertion_ids`, and `resolution: "unknown"`.
Failed ingestion returns no snapshot. A partial successful receipt permits only supported facts and explicitly preserves its limitations.

## Physical graph model

Use one Neo4j database with service-only credentials. C9 and C10 enforce user authorization before C2 resolves graph objects.
Every stored node has `project_id`, `agent_id`, `evidence_context_id`, and an immutable `key` digest.
Projection-specific nodes also contain `projection_id`. No query may omit the project and context predicates.
Dynamic domain names remain parameter values, not Cypher labels or query fragments.

| Fixed label | Additional properties | Immutable identity input |
| --- | --- | --- |
| `OakObservation` | `observation_id`, `payload_sha256`, `artifact_id`, `observed_at`, `request_scope_sha256`, `tool_id`, `call_id` | Scope + observation ID |
| `OakProjection` | `projection_id`, six configuration digests, `scenario_now`, `head_revision`, `lock_version` | Scope + projection ID |
| `OakRevision` | `revision`, `revision_sha256`, `parent_revision`, `coverage_json` | Scope + projection ID + revision |
| `OakEntity` | `type_id`, `external_id`, `provider_namespace`, `account_scope`, `identity_json` | Scope + projection ID + type ID + declared identity tuple |
| `OakAssertion` | `predicate_id`, `subject_key`, `object_key` or `literal_json`, `datatype`, `unit`, `source_pointer`, `observed_at`, `request_scope_sha256` | Projection identity + canonical assertion content + observation identity |
| `OakIngestReceipt` | `replay_key`, `payload_sha256`, `receipt_json`, `receipt_sha256`, `revision` | Scope + projection ID + observation ID + configuration digest |

All identities hash canonical JSON arrays, not ambiguous concatenated strings.
Missing identity fields reject the affected record. Two records must never merge through a null identity.
Offer identity uses provider namespace, account scope, type ID, and external offer ID within the evidence context.
Quote identity adds observation ID and request-scope digest. It is a local identity unless the provider supplies an authoritative quote ID.
Domain type and predicate identifiers must exist in the pinned schema.

Fixed relationships are `HAS_REVISION`, `INCLUDES_ASSERTION`, `INCLUDES_OBSERVATION`, `SUBJECT`, `OBJECT`, and `SUPPORTED_BY`.
A revision explicitly lists its full assertion and observation membership.
An assertion links to its subject, optional object, and supporting observation.
Literal assertions use canonical `literal_json` plus a datatype. Relation assertions use an object and no literal.
Neo4j properties cannot store nested JSON objects directly. Canonical JSON strings preserve those nested values.

Create a uniqueness constraint on `key` for each fixed label.
Add range indexes for `(project_id, agent_id, evidence_context_id, projection_id)` on projections and revisions.
Pydantic and C2 enforce required properties and types. Do not assume Enterprise-only existence or key constraints.
See the [Neo4j constraint reference](https://neo4j.com/docs/cypher-manual/current/schema/constraints/create-constraints/).

Complete membership costs more storage than in-place updates. The first fixture is small enough to accept that cost.
Limit each evidence context to 100 observations.
Limit each projection to 10000 distinct assertions and 100 committed revisions after revision zero.
Reject a commit that exceeds a limit with `projection_limit_exceeded` before graph writes.
These limits belong to the pinned task configuration. A new limit requires capacity tests and a configuration revision.
Do not optimize to temporal validity ranges before equivalent stable-read and recovery tests exist.

Reuse the official Neo4j driver, database transactions, uniqueness constraints, and range indexes.
Do not build a graph database, transaction manager, lock service, or custom connection pool.
The custom code is limited to task-specific mappings, assertion provenance, scope checks, and revision membership.
C10 owns dispatch through its selected PostgreSQL job library. C2 does not create another queue.
This separation keeps reusable infrastructure outside the ontology-specific implementation.

## Projection and commit procedure

1. Verify scope, schema approval, configuration hashes, deadline, and budget reservation.
2. Resolve raw bytes through C10 and verify the raw digest.
3. Validate exact tool arguments and response scope against the case request.
4. Produce typed candidates using the pinned mapping outside the graph transaction.
5. Validate identities, source pointers, units, schema terms, and supported value types.
6. Build immutable assertions and a deterministic merge result.
7. Begin one explicit Neo4j transaction.
8. Lock the existing projection head before reading its current revision.
9. Reject changed payload bytes under an existing observation identity.
10. Return an existing identical receipt before checking its original expected-parent value.
11. Compare the expected parent with the locked current revision.
12. Create the next revision, complete membership, observation identity, and ingestion receipt.
13. Set the projection head to that revision and commit.
14. Return the stored receipt and enqueue its PostgreSQL mirror through C10.

Projection initialization creates revision zero and its head in one transaction, under a unique key.
Concurrent initialization resolves the same key, then verifies identical configuration.
Use a write lock before the parent comparison. The implementation can increment `lock_version` with a direct property dependency.
Neo4j documents this lock behavior and non-repeatable-read limits in [concurrent access](https://neo4j.com/docs/operations-manual/current/database-internals/concurrent-data-access/).

The observation identity belongs to the context, not the projection. A changed schema cannot conceal a payload collision.
Two projections may concurrently ingest one observation. Its unique identity and digest comparison must remain in their write transactions.
If uniqueness contention aborts a transaction, retry with the same payload and re-read that observation identity.

No provider call, model call, file publication, or event publication occurs inside the graph transaction.
The [driver transaction contract](https://neo4j.com/docs/python-manual/current/transactions/) explains retry behavior.
Use explicit transactions with at most two transient retries, bounded by the shared deadline and reservation.
Each retry keeps the operation ID and adds a distinct attempt ID.

If commit acknowledgement is lost, C10 reconciles by replay key before dispatching more work.
The graph and receipt either exist together or do not exist. The PostgreSQL mirror can lag without changing that fact.
There is no atomic transaction across Neo4j, PostgreSQL, and artifact files.

## Value resolution and stable reads

Only assertions in the selected revision may contribute to a function result.
Filter them by exact request scope and the pinned source-age policy at `scenario_now`.
Missing, null, invalid, or stale values produce unknown diagnostics. They do not produce zero or false assertions.
An explicit source `false` availability value remains false.
Failed and timed-out invocations may add observation provenance. They cannot add domain values without a separately admitted successful observation.

Equal valid assertions reinforce one value while retaining each source.
Different valid values for the same field remain a conflict unless the policy names an explicit supersession relation.
Arrival order and replay time cannot resolve a conflict. The first fixture policy accepts new details for previously unknown fields.
It does not silently replace contradictory known values with the newest payload.

A quote's total must match the dates, party size, currency, and inclusive-price basis.
Pagination affects search coverage. A valid selected offer does not require a complete market search.
An empty page alone cannot establish that no eligible offer exists.

C4 supplies a `ReadBarrier` before each dependent C3 call.
C2 resolves a committed revision that contains every required observation receipt and matches every pinned interpretation digest.
C3 receives that exact `GraphSnapshotRef`; each operator uses its immutable membership.
Later ingestion can advance the head but cannot alter the function's selected revision.

## Schema changes and reprojection

A schema, extractor, mapping, policy, normalization, or scenario-clock change requires a new projection ID.
C6 sends a manifest of original observation IDs and exact raw digests to C2.
C2 replays that manifest in its saved order using the candidate configuration.
C2 preserves old projections and source bytes. Failed reprojection cannot change the active package.
C3 must consume the new projection and rebuild any affected function dependency.
The new projection becomes eligible only after source-faithfulness and regression gates pass.

## Errors, debate, and acceptance

`scope_denied`, `payload_collision`, `config_mismatch`, `private_source`, and `invalid_source` are not retryable.
`stale_parent` requires explicit C10 rescheduling with a newly inspected parent.
`dependency_pending` blocks reads without consuming a function attempt. `dependency_failed` ends the dependent call.
`commit_unknown` requires reconciliation. `transient_store_failure` permits the bounded retries above.

| Challenge | Rejected approach | Resolution |
| --- | --- | --- |
| A revision label might hide overwritten prices | Mutate properties on one offer node | Immutable assertions and explicit revision membership |
| SQLite passing tests might imply Neo4j correctness | Treat substitute receipts as service evidence | Separate real transaction, locking, and crash tests |
| A schema repair might change historical facts | Reuse old projection ID under a new schema | New projection with raw-source replay |
| A faster extractor might conceal semantic loss | Drop unsupported fields without a receipt | Reject or report each field and test source faithfulness |
| One database cannot commit another database's receipt | Publish PostgreSQL success before graph commit | Neo4j is authoritative; reconcile the mirror |

| Test ID | Injected condition | Required result |
| --- | --- | --- |
| C2-T01 | Existing search then detail fixtures | Known violations retained; o3 becomes supported only after detail evidence |
| C2-T02 | Identical replay after lost acknowledgement | Same receipt and revision; zero duplicate assertions |
| C2-T03 | Same observation ID with changed bytes | Collision; original digest and revision unchanged |
| C2-T04 | Concurrent commits against one parent | One commit; other request gets stale-parent or identical replay |
| C2-T05 | Concurrent projections with conflicting bytes | One immutable observation identity; conflicting transaction rejected |
| C2-T06 | Read g1 while g2 commits | Exact g1 answer and source set remain unchanged |
| C2-T07 | Same source IDs in another project or context | No cross-scope facts or receipt reuse |
| C2-T08 | Missing, null, false, conflict, stale quote | Each distinct state appears correctly in the typed result |
| C2-T09 | Wrong dates, party, unit, or price basis | Rejection or unknown diagnostic; no eligible assertion invented |
| C2-T10 | Required observation pending or failed | C3 cannot execute with an insufficient snapshot |
| C2-T11 | Candidate schema removes a required predicate | Reprojection failure; previous graph and package remain readable |
| C2-T12 | Crash before commit, after commit, and before mirror | Zero partial graph commits; reconciliation restores the correct receipt |
| C2-T13 | Projection request includes private evaluator artifact | Rejection before graph writes |
| C2-T14 | Extracted scalar disagrees with raw source pointer | Independent source-faithfulness gate fails |

Record real Neo4j version, driver version, operations, attempts, latency, and before/after revision hashes for service tests.
These tests establish engineering behavior. They do not measure ontology benefit or formal schema consistency.
