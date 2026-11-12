# PRD 03: Evidence intake, graph construction, and subgraph selection

[Product documentation](../../docs/README.md) | [Current system guide](../../docs/system.md)

This document retains component contracts and earlier research proposals.
Apply the current product scope before its benchmark-specific requirements.
Use the current system guide for implemented behavior.

Status: Retained component draft. AppWorld is the proposed benchmark environment.

## AppWorld scope revision

The [AppWorld implementation plan](07-implementation-plan.md) controls the proposed benchmark scope.
Retain this document's generic invariants and component responsibilities.
The hotel and stock profiles, fixed two-function catalog, and fixture-specific acceptance counts are superseded.
SQLite source templates and reservation transactions are not AppWorld requirements.
Do not assume global source versions, complete collection reads, or provider idempotency.
Revise these details against the actual AppWorld interface before implementation.
Use official AppWorld splits and evaluation instead of the former generated-world protocol.
This component draft is not yet an implementation-ready AppWorld specification.

## 1. User need

The agent must base a task decision on identifiable observations.
The runtime must know whether the available evidence is sufficient for a declared computation.
A tool success message alone does not supply that evidence.

## 2. Scope and storage

**EVD-001.** Build the accepted graph as immutable typed Python objects for each episode.
Use a private host store for graph snapshots, coverage, receipts, and runtime metadata.
Keep this store outside all MCP file and database grants.
The local SQLite source database contains fixture records and fictional reservations.
It does not execute ontology reasoning functions.

The source fixture supplies task data.
The trusted intake module is the only publisher of accepted graph revisions.
The agent cannot query source tables except through declared read operations.
The Python executor reads accepted graph snapshots only.
Do not give a function database connections, filesystem paths, or MCP clients.

Store raw observations in an append-only run directory.
Store their hashes and file references in metadata.
Do not expose the raw observation directory through agent Filesystem grants.
Keep the accepted graph for the run lifetime.
Keep its audit artifacts after the run.
Do not reuse its facts in a later run.

This design supports structured tool responses with checked mappings.
Free-text extraction is outside the first implementation.
A source that returns only unsupported free text produces `UNSUPPORTED_RESPONSE_MAPPING`.

## 3. Subcomponents

| Subcomponent | Input | Output |
|---|---|---|
| Response decoder | Native response and declared output contract | Parsed source envelope or validation error |
| Coverage checker | Envelope, query scope, page history | Coverage record |
| Mapping executor | Parsed records and frozen mapping | Typed fact and relation assertions |
| Identity merger | Assertions and declared keys | Canonical entities with conflict records |
| Graph publisher | Checked assertions and source batch | Atomic graph revision |
| Dependency planner | Function program and task requirements | Read plan |
| Subgraph selector | Read plan, request, graph revision | Working evidence view or missing dependencies |
| Receipt store | Validated observation and invocation identity | Read receipt |

None of these subcomponents requires a model call during inference.
Construction can use a model to propose mappings.
The host validates and freezes those mappings before inference.

## 4. Native read contract

**EVD-002.** Assign an `invocation_id` before dispatch.
Bind it to `run_id`, `operation_id`, exact registered tool name, and canonical arguments.
Also record the current grant and kernel versions.
Do not correlate calls only by tool name and argument digest.
Two identical calls remain two invocations.

The initial runtime dispatches one native call at a time.
The source adapter must return the version with the rows from the same source snapshot.
An empty result must also include its source version.
Reading a version after reading rows does not satisfy this contract.

The checked source envelope contains these fields:

| Field | Required meaning |
|---|---|
| `source_namespace` | Registered source identity within this task surface |
| `source_version` | Version of the snapshot that produced these rows |
| `scope` | Canonical filter and collection definition from the declared read operation |
| `records` | Array of source records, including an empty array for a successful empty read |
| `field_set` | Fields that the operation promises to return |
| `coverage_kind` | `collection`, `key_lookup`, or `partial` |
| `next_cursor` | Cursor for the next page, or null when the declared enumeration ends |
| `row_count` | Number of records in this response |
| `scope_count` | Total count in the stated scope when the local query can establish it |

The source adapter derives this envelope from declared native reads and their actual results.
The model cannot supply coverage or source-version fields.
For local SQLite, include version and scope count in the same read statement as the requested rows.
Generate a single envelope row so an empty collection still returns metadata.

The pinned SQLite package can return a Python literal representation of row dictionaries.
Discovery must check this format before the runtime accepts it.
Use a bounded literal decoder for that declared wrapper.
Require one row with one declared JavaScript Object Notation (JSON) envelope field.
Then decode and type-check that envelope.

Do not execute the response as code.
Enforce size and nesting bounds before accepting decoded content.
Catch literal or JSON decoding failures as `INVALID_SOURCE_RESPONSE`.
Reject an unrecognized wrapper.
Do not use a model to parse it during inference.

Do not infer valid records from a success phrase or an empty object.
An MCP error flag takes precedence over apparent data in the response.

## 5. Read receipt contract

**EVD-003.** Issue a successful read receipt only after response validation.
Record failed invocations in the trace without a successful receipt.

Each read receipt contains:

- The common run, request, agent, grant, kernel, and invocation identifiers.
- The declared operation and exact native server/tool identity.
- Canonical arguments and their digest.
- The source namespace, source version, scope, and field set.
- The raw response reference and digest.
- The decoder and mapping versions.
- The local receive time and provider observation time, when supplied.
- Coverage kind, row count, scope count, page links, and completion status.
- Accepted assertion references, conflict references, and validation issues.
- A receipt status of `VALID_COMPLETE`, `VALID_PARTIAL`, or `VALID_WITH_CONFLICTS`.

Receipt history is immutable.
Record expiration or supersession as a new state event.
Keep old receipts for audit, but exclude them from a new current decision.

## 6. Coverage mechanics

**EVD-004.** Compare read scope with the function's required scope.
A narrower response cannot satisfy a wider requirement.
A key lookup can prove a fact about the requested key.
It cannot prove collection completeness.

The first implementation reads each declared collection in one complete response.
It requires `next_cursor` to be null and `row_count` to equal `scope_count`.
The source query includes the complete declared field set.
An oversized collection returns `SOURCE_LIMIT`.
A non-null cursor leaves coverage partial and returns `UNSUPPORTED_PAGINATION`.
The runtime must not mark a truncated response complete.

Paged acquisition is outside this implementation.
A later adapter must preserve scope, cursor continuity, and source version across every page.
It must establish the final-page condition before it claims complete coverage.
The present negative tests check that partial responses cannot bypass this condition.
Start a fresh evidence batch when a source version changes.

Distinguish these conditions:

| Condition | Meaning | Result |
|---|---|---|
| Unknown | A required value is unavailable or unread | Request evidence or stop with a capability gap |
| Confirmed absent | A complete authoritative scope or lookup establishes no matching record | Permit the related absence result |
| Missing relation target | A required assertion has no resolved endpoint | Report an incomplete graph |
| Empty collection | A successful complete read returns no records | Preserve complete coverage with zero records |
| Conflict | Equal identity keys have incompatible assertions | Preserve both assertions and block affected decisions |

OWL uses open-world reasoning.
OWL consistency does not establish any of these coverage conditions.

## 7. Identity and relation construction

**EVD-005.** Compute identity from source namespace, entity type, and the ordered schema key values.
Use typed canonical JSON for that identity tuple.
Keep the tuple beside its digest.
If different tuples have the same digest, stop with `IDENTITY_COLLISION`.

Do not merge equal display names unless the schema declares them as the key.
Do not merge provider-local IDs across namespaces without a checked identity mapping.
Fuzzy lookup ranks observed entities without changing their identities.
The graph does not merge entities on the basis of similar names.
Version 3 preserves source identities, contexts, and evidence through projection and aggregation.
Each grouped result identifies its contributing source records.

For equal identity tuples:

1. Merge identical assertions.
2. Keep references to every source occurrence.
3. Preserve incompatible assertions as a conflict.
4. Do not select the latest received value as an automatic winner.

The first implementation requires complete declared records.
It does not combine partial fields across calls or versions.
An optional absent field remains absent.
A later revision can add a tested partial-record merge policy.

**EVD-006.** Construct a relation from the frozen source-field mapping.
Resolve its endpoint through the target type and key.
Record the source field assertion and resolved endpoint as relation evidence.
Check endpoint types and declared cardinality.
Do not infer a missing edge from textual similarity.
An unresolved required edge remains a named missing dependency.

Merge equal relation-type, source, and target tuples into one canonical edge.
Keep every supporting assertion and receipt reference.
Count distinct canonical targets for cardinality checks.
Do not count repeated observations of the same edge as different targets.

## 8. Evidence batch and graph publication

**EVD-007.** Collect accepted assertions in a staging batch.
All reads required for a complete local batch must have the same source version.
Keep partial receipt status visible while the batch is incomplete.

Serialize the accepted graph and coverage as a versioned snapshot in the private host store.
Commit its snapshot, provenance, receipt references, and `graph_revision` in one host-store transaction.
Publish the immutable Python graph handle only after that commit succeeds.
Publish only when all required source collections have complete coverage.
A published graph can still contain a reported integrity failure.
For example, complete source collections can contain an unresolved foreign key.
The function must then return `INCOMPLETE_EVIDENCE` rather than eligible results.

Any source-version mismatch invalidates the batch for a new decision.
Keep the failed batch in the audit record.
Collect a new batch rather than merge across source versions.

Use Python indexes for type/key identity, relation endpoints, and fields used by read plans.
An identity index maps a typed key to one canonical entity.
Adjacency indexes map an entity and relation type to canonical endpoint references.
Property indexes map declared values to matching entity references.
Use sorted integer indexes for supported range predicates.

The first implementation loads its bounded accepted graph into the host process.
It keeps immutable tuples and read-only mappings for a published revision.
A function cannot change that revision.
On restart, load the committed snapshot and check its hash before rebuilding indexes.
Do not rebuild accepted facts from the raw source database during recovery.

## 9. Read plans and subgraph selection

**EVD-008.** Derive each read plan from the typed function program and the task's evidence requirements.
Do not use a second model to choose an unverified graph neighborhood.

A read plan contains:

- Root entity types and typed request-bound filters.
- Required fields and relation traversals.
- Relation direction and traversal bounds.
- Aggregate and ordering dependencies.
- Required source scopes and completeness conditions.
- Task-wide integrity checks that precede local selection.
- Source operations that can satisfy missing dependencies.

The dependency planner computes a conservative closure.
A missing function predicate cannot remove an independently declared task evidence requirement.

Selection follows this procedure:

1. Check the request, kernel, grants, and current graph revision.
2. Check task-wide coverage and integrity conditions.
3. Use indexes to select candidate roots.
4. Include the fields and linked assertions required by the read plan.
5. Record unresolved dependencies.
6. Execute the function only when its required evidence is sufficient.

The working subgraph is a read-only Python view over the selected entity, edge, and field references.
It binds one published graph revision.
It does not require a copy of the full graph.
Include negative decisions and excluded candidates in the evidence needed for completeness claims.

**EVD-009.** Preserve aggregate scope.
A cheapest-result claim requires complete related candidate coverage.
A local subgraph cannot hide a lower-cost candidate or a required unresolved edge.
The current hotel task checks integrity across its entire declared snapshot.

Cache that check by source and graph revision after a complete check.
Do not repeat it for every function at the same revision.
A later task can declare a narrower integrity scope through its task contract.

Accepted graphs use indexed selection.
If a bound prevents required coverage, return a partial state.
Do not claim that the first implementation proves large-graph scalability.
Paged acquisition requires a later adapter and its own acceptance tests.

## 10. Function result and invalidation

**EVD-010.** Bind every accepted function result to its input receipt set and graph revision.
Also bind its function version, typed arguments, request hash, and kernel version.
Record the operator trace and per-requirement result.
Use a host-owned `function_receipt_id`.
The response must carry this binding with the typed output.

The first implementation invalidates all function receipts after any new graph publication.
It also invalidates them after a changed request, grant, kernel, or related source version.
This conservative rule includes newly added candidates and removed relations.
Dependency-specific invalidation is outside the first implementation.

Do not equate a matching graph revision with current external state.
The action executor also checks the source version at commit.
See PRD 05.

## 11. Agent observation

**EVD-011.** Replace raw source content before the model receives the tool result.
Return a typed decision observation with its receipt references.
Include useful counts, missing dependencies, validation issues, and available next operations.
Do not return only an opaque receipt identifier.
Return decision fields and evidence paths from declared function outputs.

A rendered observation is a view of host state.
The agent cannot create facts by restating that observation.
If the context loses a receipt reference, the host can render the current valid state again.

## 12. Failure and acceptance cases

| Case | Required result |
|---|---|
| MCP returns an error with a text success phrase | No successful read receipt |
| MCP returns `{}` for a declared collection | Response validation fails |
| Query returns only a count | It cannot satisfy row or field evidence requirements |
| Successful empty collection | Version and complete zero-record coverage remain available |
| Equal keys with identical records | One canonical entity with all source references |
| Equal keys with different policy values | Conflict remains explicit |
| A page comes from a newer source version | Batch cannot publish as a consistent complete batch |
| Wrong request scope | Receipt cannot satisfy the current request |
| New cheaper candidate appears | Old aggregate receipt cannot authorize a write |
| A required relation target is absent | Incomplete evidence, even if other candidates are valid |
| Different valid read order | Same accepted graph and eligible result |
| New task uses a composite key | Generic identity code works without task-specific branches |

## 13. Current gap and implementation boundary

Current `sql_kernel.py` loads fixture rows before the agent reads them.
Current `hook.py` marks table reads without ingesting validated returned rows.
The new intake path must replace those markers with the receipt protocol in this PRD.
The current native client does not yet prove raw-result replacement or registered Python function dispatch.
Treat that integration test as a prerequisite for this component's acceptance.
