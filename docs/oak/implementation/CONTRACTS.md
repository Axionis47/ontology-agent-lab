# Shared production contracts

Design version 0.4.1. These definitions govern all C0 through C11 service boundaries.

The service envelope remains `0.4.0` in this unimplemented design. No deployed-client compatibility is claimed for revised payload fields.
The [agent starting shape](AGENT-SHAPE.md) has its own implemented declaration profile, `oak-agent-shape/1`.
Its strict parser does not implement the service payloads, callable registry, or runtime probes.

The [local harness](INTEGRATION-HARNESS.md) uses a narrower contract. It is not a generated production API client.
Component payload profiles, such as `oak-schema/1`, version their content separately from the service envelope.

## Reuse rule

Use Pydantic models as the production contract source. Generate JSON Schema and FastAPI OpenAPI from those models.
Generate frontend types with [openapi-typescript](https://openapi-ts.dev/introduction). Do not maintain duplicate handwritten frontend interfaces.
The generated types do not perform runtime validation. The API must still validate each request and response.

This document defines the required models. Production models and OpenAPI generation remain delivery gate D1.
The harness models implement only the tested subset listed in its receipt.

## Scalar types

| Type | Definition |
| --- | --- |
| `Id` | Opaque nonempty ASCII string matching `[A-Za-z0-9_-]{1,128}` |
| `Hash` | SHA-256 digest matching `[0-9a-f]{64}` |
| `Timestamp` | RFC 3339 UTC timestamp, serialized with `Z` |
| `Version` | Nonempty ASCII string, at most 64 characters |
| `MinorAmount` | Strict integer, 0 through 100000000, currency units divided by 100 for USD |
| `TermId` | `[a-z][a-z0-9_]{0,63}` |

Resource IDs are opaque to clients. Fixture case and source identifiers remain source strings under their own contracts.
Domain requirement references use `Id`. Schema class and property references use `TermId`.
Documentation requirement UIDs, such as `C1-R01`, belong to the StrictDoc graph and remain separate from task-domain requirements.
Reject booleans as integers. Reject NaN, infinity, and numeric strings where a number is required.
Use ISO dates for stay boundaries. C0 limits the first class to 1 through 30 nights and 1 through 100 people.

## ArtifactRef

All fields are required. Use this definition instead of component-local variants.

| Field | Type | Meaning |
| --- | --- | --- |
| `artifact_id` | `Id` | Index identity resolved within authenticated project scope |
| `kind` | `Version` | Registered artifact kind, such as `schema` or `function_bundle` |
| `sha256` | `Hash` | Digest of the stored bytes |
| `media_type` | String, 1 through 128 characters | Registered MIME type |
| `contract_version` | `Version` | Payload profile, such as `oak-schema/1` |
| `producer_version` | `Version` | Exact producer implementation version |

The artifact index adds `project_id`, nullable `agent_id`, `byte_length`, `created_at`, `visibility`, and `availability`.
`visibility` is `project`, `worker_only`, or `evaluator_only`.
`availability` is `staged`, `ready`, or `unavailable`.
Only `ready` artifacts can satisfy a handoff.

Artifact IDs and hashes never grant access by themselves. C9 authorizes the resolved artifact and its data role.
A worker must present the operation scope. A browser cannot submit a worker identity.

## Component envelope

| Field | Type | Rule |
| --- | --- | --- |
| `contract_version` | Literal `0.4.0` | Service envelope version |
| `message_type` | Registered string | Selects the exact payload model |
| `producer_version` | `Version` | Producer implementation |
| `project_id` | `Id` | Server-authorized project |
| `agent_id` | `Id` or null | Required for agent-owned work |
| `invocation_id` | `Id` | One logical request |
| `attempt_id` | `Id` | One execution attempt |
| `operation_id` | `Id` | Stable across delivery retries |
| `parent_call_id` | `Id` or null | Immediate parent |
| `run_id` | `Id` or null | Run correlation |
| `assignment_id` | `Id` or null | Registered case, condition, and repetition |
| `evidence_context_id` | `Id` or null | Permitted evidence scope |
| `input_refs` | Unique `ArtifactRef[]` | Exact immutable dependencies |
| `configuration_ref` | `ArtifactRef` | Fixed settings and budget configuration |
| `created_at` | `Timestamp` | Server time |

Each request and result adds its component payload. Do not allow an unrestricted JSON payload in the production union.
Result envelopes add `status`, `component_status`, `output_refs`, and `error`.
`status` is `running`, `succeeded`, `failed`, or `cancelled`.
`component_status` is an enum defined by the selected component result model.
`error` is null for successful process completion. Domain rejection stays in the component payload.

## Error

`EventRef` contains `run_id: Id` and `sequence: positive_integer`.
Resolve it within the envelope's project and agent. It names C10's `(project_id, run_id, sequence)` event key.

`Error` contains `code: string`, `owner: C0..C11`, `stage: string`, `retryable: boolean`, and `operation_id: Id`.
It also contains `affected_refs: ArtifactRef[]`, `message: string`, and `trace_id: Id`.
Messages contain no credentials, private evaluator values, foreign-project identities, or arbitrary source excerpts.
Restricted artifacts can hold detailed diagnostics for authorized operators.

HTTP uses `401` for missing authentication, `403` for a denied action on a visible resource, and `404` for unavailable scope.
Use `409` for stale state or idempotency conflicts, `422` for invalid input, and `503` for unavailable dependencies.
An asynchronous component failure appears in the job result. It does not change the original `202 Accepted` response.

## Version, dependency, and package rules

`PackageManifest` contains `project_id`, `agent_id`, `schema_ref`, `function_bundle_ref`, `operator_registry_ref`, and `extractor_ref`.
It also pins `mapping_ref`, `normalization_ref`, `source_policy_ref`, `requirements_ref`, `native_tool_manifest_ref`, `host_config_ref`, and `runtime_ref`.
`model_config_ref` is null only for deterministic engineering replay.
`execution_mode` is `optional_functions` or `guarded_requirements`. `guard_bindings_ref` is required in guarded mode.
The manifest pins `dependency_manifest_ref`, `test_policy_ref`, `test_suite_ref`, and `evaluator_public_ref`.
Verification receipts and review records are stored beside the manifest. They are not inputs to the candidate digest they verify.

Compute the package hash from canonical manifest bytes. Store the manifest as an artifact.
An active pointer contains `package_ref`, `generation: nonnegative_integer`, and `activated_at`.
Activation compares both the expected base hash and generation in one metadata transaction.

`DependencyEdge` contains `consumer_ref`, `dependency_ref`, `dependency_kind`, and `semantic_ids: TermId[]`.
`dependency_kind` is `schema`, `function`, `operator`, `extractor`, `mapping`, `normalization`, `source_policy`, `guard`, `runtime`, or `test`.
Each graph projection uses the admission's pinned scenario clock. A caller cannot supply a later time to refresh old evidence.
The first schema repair invalidates all schema-bound graph projections and function bundles.
Use selective rebuilding only after an independent dependency-completeness test exists.

## Verification receipt

`VerificationReceipt` contains `candidate_ref`, `gate`, `input_refs`, `suite_ref`, `runner_ref`, `result`, and `diagnostic_refs`.
It also contains `operation_id`, `started_at`, `finished_at`, and the server-bound verifier identity.
`result` is `passed`, `failed`, `error`, or `not_run`.
`gate` is `structure`, `coverage`, `logic`, `projection`, `functions`, `regression`, or `guard_routes`.

Only the verifier service may publish a verification receipt.
C6 must resolve stored receipts, compare their inputs, and require every applicable gate.
A browser cannot create a passing receipt by submitting a status field.
Optional mode marks `guard_routes` inapplicable in the frozen test policy. It cannot silently omit other gates.

Review approval binds the candidate hash, verification-set hash, test-policy hash, and base generation.
A changed candidate or test policy invalidates approval. A passing logical receipt cannot override a failed task receipt.

## Canonicalization and replay

Use UTF-8 JSON, sorted object keys, compact separators, and `ensure_ascii=False` for canonical project artifacts.
Arrays preserve order unless their payload contract explicitly defines an unordered set.
Do not normalize source bytes. Hash raw payload bytes separately from interpreted canonical records.

An API idempotency key is scoped by principal, project, route, and HTTP method.
Save its canonical body digest and original response for at least 24 hours.
Identical retries return that response. Changed bodies return `409`.
Long-lived operation identities and ingestion identities remain durable after API-key expiry.

Store the domain operation ID before dispatch. Reconcile target receipts after uncertain delivery.
An off-the-shelf queue supplies delivery and retry mechanics. Domain receipts decide whether an operation already committed.

## Build versus reuse

| Responsibility | Reuse | Permitted project code |
| --- | --- | --- |
| HTTP validation and serialization | FastAPI and Pydantic | Payload models and authorization dependencies |
| OIDC protocol and tokens | Keycloak and Authlib | Project membership and session-to-principal binding |
| Metadata access and migrations | SQLAlchemy and Alembic | Tables, constraints, queries, and migration content |
| Job storage, workers, retries | Procrastinate on PostgreSQL | Component task registration and domain reconciliation |
| Workflow state | LangGraph checkpointer | State schema, nodes, transitions, and artifact references |
| Graph transactions | Neo4j official driver and database | Parameterized scoped queries and source mapping |
| OWL and reasoning | Owlready2 and bundled HermiT | Restricted domain-to-library mapping and receipt handling |
| Client transport and caching | Generated OpenAPI client and TanStack Query | Screens, query keys, and domain interactions |
| Graph rendering | React Flow and an established layout engine | Node meanings, styles, inspectors, and projection selection |
| Domain computation | Standard Python and Pydantic | Offer constraints, source interpretation, invalidation, independent scoring |

Do not build a custom queue, ORM, identity provider, graph canvas, reasoner, general expression language, or migration framework.
Any exception needs a recorded unmet requirement, alternatives considered, maintenance cost, and a boundary test.
Do not add a library only because it is available. Prefer the smallest established dependency that satisfies the requirement.
