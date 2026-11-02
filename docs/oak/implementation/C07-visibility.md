# C7: Version-bound inspection projections

Design version 0.4.0. Owner: C7. Status: proposed; service verification not run.

A user must distinguish a definition, an observed value, a computation, and a recorded action.
C7 converts authorized records into four typed read views. C11 renders those views without inventing relations or verification results.

The [shared contracts](CONTRACTS.md) define identifiers, artifact references, and errors.
[C2](C02-evidence.md) owns fact revisions. [C10](C10-service.md) exposes the endpoint. [C11](C11-interface.md) owns presentation.
This document refines the earlier [visibility specification](../07-kernel-data-and-visibility.md).

## Logic and reuse boundary

Use Pydantic for view contracts, SQLAlchemy for authorized metadata reads, and the official Neo4j driver for scoped graph reads.
Use fixed parameterized query templates. Browser input cannot supply Cypher, labels, property names, or filesystem locations.
Use `itsdangerous.URLSafeTimedSerializer` for cursor signing and expiry. Do not implement signing or token cryptography.
The signing dependency and key configuration require the normal D1 lockfile and service checks.

The first slice has no server-side view cache. C7 owns no persistent domain state.
C11 uses TanStack Query for browser caching. A later server cache requires explicit scope and invalidation tests.
React Flow and ELK remain frontend responsibilities. C7 does not compute canvas coordinates or create a graph database.

1. **C7-R01:** C7 must authorize each view and source reference before reading its contents.
2. **C7-R02:** C7 must bind every response to exact package and applicable evidence or event versions.
3. **C7-R03:** C7 must reject incompatible source versions before composing a view.
4. **C7-R04:** C7 must preserve distinct schema, fact, dependency, and execution relation meanings.
5. **C7-R05:** C7 must identify the source of every displayed assertion and verification status.
6. **C7-R06:** C7 must retain unknown, conflicting, stale, unsupported, and unrun states.
7. **C7-R07:** C7 must exclude evaluator-private and worker-only content from browser views.
8. **C7-R08:** C7 must bind pagination to the authorized query and immutable read boundary.
9. **C7-R09:** C7 must report truncation without claiming complete domain coverage.
10. **C7-R10:** C7 must return only edges whose endpoint nodes occur in the same response fragment.
11. **C7-R11:** C7 must preserve source time separately from replay and rendering time.
12. **C7-R12:** C7 must perform zero writes to domain facts, packages, reviews, and active pointers.

## Query and binding contracts

The endpoint is `GET /api/v1/projects/{project_id}/agents/{agent_id}/views/{view_kind}`.
Path scope comes from C10. Query parameters cannot replace the authenticated principal.
IDs, hashes, and timestamps use the shared scalar types. Unknown query fields fail validation.

| Model | Required fields and types |
| --- | --- |
| `GraphViewQuery` | `package_artifact_id: Id`; `package_sha256: Hash`; `evidence_context_id: Id_or_null`; `projection_id: Id_or_null`; `revision: integer>=0_or_null`; `run_id: Id_or_null`; `event_sequence_to: integer>=0_or_null`; `root_id: Hash[0..5]`; `radius: integer[0,2]=1`; `node_kind: NodeKind[]`; `relation_kind: RelationKind[]`; `text: string[0,128]`; `node_limit: integer[2,200]=100`; `edge_limit: integer[1,400]=200`; `cursor: string_or_null` |
| `ViewBinding` | `project_id: Id`; `agent_id: Id`; `view_kind: schema_or_facts_or_dependencies_or_execution`; `package_ref: ArtifactRef`; `graph_snapshot: GraphSnapshotRef_or_null`; `run_id: Id_or_null`; `event_sequence_to: integer>=0_or_null`; `source_set_sha256: Hash`; `query_sha256: Hash` |
| `ViewSnapshot` | `contract_version: literal(0.4.0)`; `binding: ViewBinding`; `binding_sha256: Hash`; `nodes: GraphNode[]`; `edges: GraphEdge[]`; `source_refs: ArtifactRef[]`; `coverage: ViewCoverage`; `next_cursor: string_or_null`; `generated_at: Timestamp` |
| `ViewCoverage` | `representation: real_or_synthetic_fixture_or_test_substitute`; `returned_nodes: integer>=0`; `returned_edges: integer>=0`; `projection_nodes: integer>=0`; `projection_edges: integer>=0`; `has_more: boolean`; `truncation: none_or_page_limit`; `domain_coverage: complete_or_partial_or_unknown_or_not_applicable`; `coverage_basis_ref: ArtifactRef_or_null` |

Repeat array query parameters, for example `root_id=a&root_id=b`. An omitted array is empty.
Nullable query fields are omitted on the wire. The parsed contract uses explicit null values.
The response uses C2's complete `GraphSnapshotRef`, including its exact interpretation dependencies.

| View | Required binding | Fields that must be null |
| --- | --- | --- |
| `schema` | Exact package, schema, and encoding references | Graph, run, event sequence |
| `facts` | Exact package, evidence context, projection, revision | Event sequence; run may identify the owning run |
| `dependencies` | Exact package and dependency manifest | Graph, run, event sequence |
| `execution` | Exact package and run; frozen event high-water mark | Query-level graph fields; individual events retain their graph references |

Schema and dependency views use only package-pinned manifests and their intrinsic declarations.
Live review or test execution receipts remain in the candidate or run APIs. They cannot change a frozen dependency view silently.
If the dependency view names a test definition, display its execution status as `not_run` unless the source explicitly pins a receipt.

For the first execution request, null `event_sequence_to` resolves to the run's current maximum committed sequence.
All subsequent pages use that resolved sequence. Later events require a fresh view request.
An execution view can show different graph revisions on different operations. It cannot label them as one combined fact snapshot.

An Active selection is resolved through C10 before this request. C7 does not accept `latest` as a package or graph revision.
Zero revisions are valid empty evidence snapshots. Missing projection state is an error, not an empty verified graph.

## Nodes, edges, and inspection

`NodeKind` is `type`, `property`, `axiom`, `requirement`, `entity`, `assertion`, `observation`, `context`, `function`, `operator`, `test`, `artifact`, `invocation`, `attempt`, `operation`, or `receipt`.
Each view allows only its declared kinds. A kind filter outside that set fails validation.

| Model | Fields |
| --- | --- |
| `GraphNode` | `node_id: Hash`; `kind: NodeKind`; `semantic_id: string`; `label: string[1,256]`; `detail: NodeDetail`; `signals: Signal[]`; `inspection: InspectionRef[]` |
| `GraphEdge` | `edge_id: Hash`; `source: Hash`; `target: Hash`; `relation: RelationKind`; `label: string[1,128]`; `source_ref: ArtifactRef`; `source_pointer: string`; `semantic_ids: TermId[]` |
| `InspectionRef` | `artifact_ref: ArtifactRef`; `pointer: RFC6901_JSON_pointer_or_null`; `purpose: definition_or_source_or_computation_or_test_or_operation_or_diagnostic`; `title: string[1,128]` |
| `Signal` | `dimension: meaning_or_evidence_or_implementation_or_verification_or_enforcement`; `state: present_or_absent_or_unknown_or_conflict_or_stale_or_unsupported_or_not_run_or_passed_or_failed_or_error_or_not_applicable`; `basis_refs: ArtifactRef[]`; `reason_code: string` |

`NodeDetail` is a strict tagged union. It is not an unrestricted map.
Definition nodes use `DefinitionDetail`; fact nodes use `FactDetail`; dependency nodes use `DependencyDetail`; execution nodes use `ExecutionDetail`.
The Pydantic union must reject a detail variant that differs from the view and node kind.
`DefinitionDetail` contains `definition`, `unit_or_null`, `requirement_ids`, and `encoding_disposition`.
`FactDetail` contains `predicate_id_or_null`, `value`, `value_state`, `unit_or_null`, `observed_at_or_null`, `replayed_at_or_null`, and `request_scope_sha256`.
Its `value` is a string, strict integer, boolean, or null. Its `value_state` is `known`, `unknown`, `conflict`, `invalid`, or `stale`.
`DependencyDetail` contains `artifact_ref`, `contract_name_or_null`, `semantic_ids`, and `implementation_status`.
`ExecutionDetail` contains `operation_id`, `attempt_id_or_null`, `parent_call_id_or_null`, `sequence`, `process_status`, `graph_snapshot_or_null`, and `elapsed_ms_or_null`.
Unmeasured elapsed time is null. It cannot become zero by default.

| View | RelationKind values and meaning |
| --- | --- |
| Schema | `subclass`, `domain`, `range`, `restriction`, `disjoint`, `inverse`, `expresses_requirement`; schema declarations only |
| Facts | `domain_relation`, `subject`, `object`, `supported_by`, `for_context`; observed assertion and provenance relations |
| Dependencies | `depends_on`, `implements_requirement`, `verifies_requirement`; consumer points to dependency or requirement |
| Execution | `parent_call`, `precedes`, `produced_receipt`, `used_snapshot`; recorded causality or sequence only |

A domain-relation edge retains its original predicate ID in `semantic_ids` and its source assertion pointer.
No navigation parent becomes `subclass`. No display adjacency becomes a recorded causal edge.
Node IDs hash the scope, view kind, source artifact identity, record identity, and relevant version boundary.
Edge IDs additionally hash the relation and endpoint IDs. Hash canonical arrays, not concatenated labels.
Identical labels do not merge identities. Repeated page endpoints use identical node IDs and content.

Inspection uses C10's existing authorized artifact-content endpoint. It adds no arbitrary record-query endpoint.
JSON pointers address the pinned artifact bytes. An invalid pointer returns a structured missing-source diagnostic.
Raw text has a null pointer. C11 renders it as text with its recorded media type.
Published source bytes must fit C10's bounded content policy. C7 cannot widen artifact visibility.

## Projection and pagination algorithm

1. Authenticate and authorize the project, agent, package, and applicable run or evidence context.
2. Resolve the exact source artifacts and verify their hashes and visibility.
3. Verify schema, interpretation, package, run, and graph compatibility before joining records.
4. Resolve the execution high-water mark when the first request requires it.
5. Apply registered node, relation, root, radius, and text filters within that authorized source set.
6. Build the typed projection from fixed artifact mappings or parameterized Neo4j read queries.
7. Reject projections above 10000 nodes or 20000 edges with `view_projection_limit`.
8. Produce bounded fragments using the ordering and cursor rules below.
9. Recheck current access before returning the response and its authorized source references.
10. Return explicit coverage, status evidence, and the exact immutable binding.

An empty `root_id` selects the whole scoped projection, subject to the server cap.
Otherwise include nodes within the declared undirected inspection radius of the roots. Edge direction remains unchanged.
Text filtering uses Unicode casefolded substring matching on labels. It does not search raw evidence or private fields.
All counts describe this filtered, authorized projection. They do not describe the entire database or market.

For pagination, define one unit for each edge with both endpoints, and one unit for each isolated node.
Order units by minimum distance from the selected roots, then edge-before-isolate, then immutable record ID.
Without roots, use distance zero. Add whole units until the next unit would exceed a requested node or edge limit.
Every fragment therefore contains its edge endpoints. Endpoint nodes may repeat across pages and retain the same identity.
Clients merge fragments by ID and must preserve their total viewport cap.
The cursor records the last emitted unit. No unit is split, skipped, or returned under a different source boundary.

The signed cursor binds user ID, authorization revision, query digest, binding digest, last unit, and format version.
It expires after 15 minutes. C9 authorization is still required on every page; a valid cursor grants no access by itself.
Changed filters, limits, scope, package, or version require a new cursor sequence.
Signing makes tampering detectable. It does not encrypt the cursor; include no source values, credentials, or evaluator material.

Projection reads use exact immutable revision membership. C7 never follows a mutable head after resolving a requested revision.
Missing authoritative sources fail the entire combined view. There is no fallback to newer artifacts or a stale metadata mirror.
Unknown fields remain visible through typed detail and signals. Missing receipts yield `not_run`, not a green verification label.

## Storage, failures, and retries

C7 reads C1/C3/package blobs, C2's exact graph snapshot, and C10's immutable run events up to the bound sequence.
C10 serves these protected view responses with `Cache-Control: no-store`. Shared HTTP caches cannot retain them.
C7 makes no domain write, activation, normalization, repair, or provenance correction.
Ordinary access logging belongs to C10 and does not alter the inspected records.
Use a fresh read for retry. Retain the original binding and cursor; do not silently resolve a newer version.

| Code | HTTP status and behavior |
| --- | --- |
| `scope_not_found` | `404`; reveal no foreign IDs, counts, labels, or hashes |
| `view_binding_mismatch` | `409`; reject mixed package, projection, run, or interpretation versions |
| `view_cursor_expired` | `409`; require a new view sequence |
| `view_cursor_invalid` | `422`; reject signature, query, user, or scope mismatch |
| `view_projection_limit` | `422`; require narrower roots, radius, or filters |
| `view_source_unavailable` | `503`; no combined partial verified view |
| `view_source_integrity` | `503`; retain restricted diagnostics and block the read |
| `view_contract_invalid` | `422`; reject unsupported filters, kinds, or field combinations |

Retries consume no model budget. Log latency, read operations, and byte counts separately from agent-visible tool calls.
No inspection query can call a model, a task provider, C1 construction, or C2 ingestion.

## Adversarial decisions and acceptance

| Challenge | Resolution |
| --- | --- |
| Cache all views for speed | Start with authoritative reads; add caching only after evidence of need and scope tests |
| Merge old schema with current facts | Reject incompatible bindings before emitting a combined result |
| Treat a signed cursor as authorization | Recheck C9 access on every page and before returning content |
| Hide unresolved values for a cleaner graph | Preserve their states and causes in graph and table projections |
| Show all test definitions as verified | Require a pinned execution receipt for a passed signal |
| Use one relation type for all lines | Keep four view-specific relation vocabularies and original source identities |

All tests below are required real-service cases. None is executed by this document.

| Test ID | Input or fault | Required observation |
| --- | --- | --- |
| C7-T01 | Valid schema, facts, dependency, and execution fixtures | Exact distinct node and relation types with source references |
| C7-T02 | Same IDs in another project or agent | Generic denial and zero foreign values or counts |
| C7-T03 | Package schema differs from projection schema | `view_binding_mismatch`; no composed result |
| C7-T04 | Read old revision while a new revision commits | Old values, sources, and IDs remain unchanged |
| C7-T05 | Unknown, false, conflict, stale, and missing receipts | Distinct states; no inferred truth or verification pass |
| C7-T06 | Source observation replayed later | Original source time and separate replay time |
| C7-T07 | Evaluator-private or worker-only canary | No value, pointer, count, or artifact reference in browser response |
| C7-T08 | Paginate a graph with shared endpoints | No dangling edges, skipped units, inconsistent duplicates, or bound changes |
| C7-T09 | Alter cursor, query, user, or scope | Cursor rejection before protected data emission |
| C7-T10 | Revoke access between pages | Next page denied despite a valid signed cursor |
| C7-T11 | Append events during execution-view pagination | Original high-water mark preserved; new events require refresh |
| C7-T12 | Missing or altered artifact bytes | No fallback source; explicit unavailable or integrity failure |
| C7-T13 | Inspect all supported views and source links | Zero writes to facts, packages, reviews, and active pointers |
| C7-T14 | Projection exceeds limits or is empty | Explicit limit error or valid empty coverage; no completeness invention |

Document traceability and successful inspection do not establish task correctness or improved agent behavior.
The writing applies ASD-STE100 principles. Full dictionary and grammar conformity remains unverified.
