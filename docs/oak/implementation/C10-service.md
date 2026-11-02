# C10: API, storage, and durable coordination

Design version 0.4.1. November 2, 2026. Proposed service contract.

The [baseline](README.md) selects one modular API process and one worker process.
The [shared contracts](CONTRACTS.md) define scalar types, envelopes, artifacts, errors, and package identity.
This document specifies a production target. It does not implement the API, PostgreSQL, or queue integration.

## Logic and reuse boundary

C10 authenticates requests through C9, resolves authorized resources, commits commands, and schedules component work.
Components own domain algorithms. C10 cannot reinterpret a failed logical or task check as success.

| Responsibility | Selected existing implementation | Project-specific code |
| --- | --- | --- |
| HTTP and schema generation | FastAPI and Pydantic | Routes, request models, response models, scope dependencies |
| Metadata transactions and migrations | SQLAlchemy and Alembic | Domain tables, constraints, and migration contents |
| Durable job delivery | Procrastinate on PostgreSQL | Registered component jobs and domain receipt reconciliation |
| Workflow recovery | LangGraph with official PostgreSQL checkpointer | Workflow state and version-bound component transitions |
| Graph operations | Official Neo4j driver | C2's parameterized, scoped query templates |
| Client types | Generated OpenAPI and openapi-typescript | Domain screens and query keys |

Use Procrastinate's `SQLAlchemyPsycopg2Connector` for API job deferral on the API's SQLAlchemy connection.
Use its asynchronous `PsycopgConnector` for the worker. The two processes use the same PostgreSQL database and queue schema.
These connector roles are documented by [Procrastinate](https://procrastinate.readthedocs.io/en/stable/howto/basics/connector.html).
Do not pass an arbitrary SQLAlchemy connection to a psycopg3 connector.

1. **C10-R01:** C10 must authorize each resource before resolving its contents.
2. **C10-R02:** C10 must commit a command and its queued job in one PostgreSQL transaction.
3. **C10-R03:** C10 must preserve an operation identity across queue retries.
4. **C10-R04:** C10 must reconcile authoritative receipts before repeating uncertain work.
5. **C10-R05:** C10 must pin a run's package and configuration at creation.
6. **C10-R06:** C10 must reject browser-supplied verification receipts and worker identities.
7. **C10-R07:** C10 must publish artifact references only after their bytes are durable.
8. **C10-R08:** C10 must preserve deadlines and consumed budgets after restart.
9. **C10-R09:** C10 must generate client contracts from the production Pydantic models.
10. **C10-R10:** C10 must use polling before introducing a streaming transport.
11. **C10-R11:** C10 must use the same authoritative run ledger for ordinary runs and separately scoped candidate-verification trials.
12. **C10-R12:** C10 must expose the server-sealed verification-set reference used for owner review.

## HTTP conventions

All domain routes start with `/api/v1`. `P` below means `/api/v1/projects/{project_id}`.
`A` means `P/agents/{agent_id}`. All path IDs use the shared `Id` type.
Server code constructs component envelopes. Browser bodies cannot set the principal, producer, attempt, or worker identity.
Request and response models reject unknown fields. JSON requests have a 1 MiB limit.

`read` permits owner, editor, or viewer. `edit` permits owner or editor. `own` permits owner only.
C9 also applies artifact visibility and data-role restrictions. Project membership cannot grant access to private evaluator answers.
Every mutation requires C9's CSRF check and an `Idempotency-Key` header, except identity-provider callbacks.
The shared error contract supplies `401`, `403`, `404`, `409`, `422`, and `503` behavior.

Responses include `X-Request-Id`. `202` responses contain `Accepted` and a `Location` header for the job resource.
The client polls that resource every two seconds while visible, with a 30-second maximum backoff after transport errors.
Terminal states stop polling. Polling never repeats a mutation automatically without its original idempotency key.

### Endpoint registry

| Method and route | Permission | Body or query | Success response |
| --- | --- | --- | --- |
| `GET /api/v1/me` | Authenticated | None | `200 SessionView`, defined by C9 |
| `GET /api/v1/projects` | Authenticated | `PageQuery` | `200 Page[ProjectView]` |
| `POST /api/v1/projects` | Authenticated | `CreateProject` | `201 ProjectView` |
| `GET P` | read | None | `200 ProjectView` |
| `PATCH P` | own | `ProjectUpdate` | `200 ProjectView` |
| `GET P/members` | own | `PageQuery` | `200 Page[MembershipView]` |
| `PUT P/members/{user_id}` | own | `SetMembership` | `200 ProjectView` |
| `DELETE P/members/{user_id}` | own | `expected_authorization_revision` query | `204`, subject to C9's last-owner rule |
| `GET P/agents` | read | `PageQuery` | `200 Page[AgentView]` |
| `POST P/agents` | edit | `CreateAgent` | `201 AgentView` |
| `GET A` | read | None | `200 AgentView` |
| `PATCH A` | edit | C9 `AgentUpdate` | `200 AgentView` |
| `POST A/versions` | edit | `CreateAgentVersion` | `201 AgentView` |
| `POST A/admissions` | edit | `AdmissionCreate` | `202 Accepted` |
| `GET A/admissions/{admission_id}` | read | None | `200 AdmissionReceipt` with restricted references redacted |
| `POST A/candidates` | edit | `CandidateCreate` | `202 Accepted` |
| `GET A/candidates` | read | `PageQuery` | `200 Page[CandidateView]` |
| `GET A/candidates/{candidate_id}` | read | None | `200 CandidateView` |
| `POST A/candidates/{candidate_id}/verification` | edit | `VerificationStart` | `202 Accepted` |
| `POST A/candidates/{candidate_id}/reviews` | own | `ReviewCreate` | `201 ReviewView` |
| `POST A/activation` | own | `ActivationRequest` | `200 PromotionReceipt` |
| `GET A/activation` | read | None | `200 ActivePointer` |
| `GET A/activation/history` | read | `PageQuery` | `200 Page[PromotionReceipt]` |
| `GET A/packages/{artifact_id}` | read | None | `200 PackageManifest` |
| `POST A/runs` | edit | `RunCreate` | `202 Accepted` |
| `GET A/runs` | read | `PageQuery` | `200 Page[RunView]` |
| `GET A/runs/{run_id}` | read | None | `200 RunView` |
| `POST A/runs/{run_id}/cancel` | edit | `RunCommand` | `202 Accepted` |
| `POST A/runs/{run_id}/resume` | edit | `RunCommand` | `202 Accepted` |
| `GET A/runs/{run_id}/events` | read | `after_sequence`, `limit` | `200 EventPage` |
| `GET A/views/{view_kind}` | read | C7 version-bound view query | `200 ViewSnapshot` |
| `GET P/jobs/{job_id}` | read | None | `200 JobView` |
| `POST P/artifacts` | edit | `ArtifactUpload` multipart fields and bytes | `201 ArtifactRef` |
| `GET P/artifacts/{artifact_id}` | read plus visibility | None | `200 ArtifactMetadata` |
| `GET P/artifacts/{artifact_id}/content` | read plus visibility | None | `200` bytes with recorded media type |

Login, callback, logout, membership bodies, and identity views follow C9.
The first release does not expose raw Cypher, arbitrary worker dispatch, checkpoint editing, physical deletion, or client-created passing receipts.
Rollback uses `POST A/activation` with a newly reviewed compatible previous package. It does not reverse provider effects.

### Service payloads

All fields below are required unless marked nullable. Component-specific referenced payloads retain their component owner.

| Model | Fields |
| --- | --- |
| `ProjectUpdate` | `name: string[1,120]`; `state: active\|archived`; `expected_authorization_revision: integer>=0` |
| `MembershipView` | `user_id: Id`; `display_name: string`; `role: owner\|editor\|viewer` |
| `PageQuery` | `limit: integer[1,100]=50`; `after: Id\|null=null` |
| `Page[T]` | `items: T[]`; `next_after: Id\|null` |
| `Accepted` | `job_id: Id`; `operation_id: Id`; `resource_id: Id`; `status: "queued"` |
| `AdmissionCreate` | `agent_version: integer>=1`; `purpose: literal(engineering_replay)` |
| `JobView` | `job_id: Id`; `operation_id: Id`; `kind: verify_registry\|admission\|construction\|verification\|run\|cancel\|resume`; `state: queued\|running\|waiting_review\|succeeded\|failed\|cancelled`; `resource_id: Id`; `result_ref: ArtifactRef\|null`; `error: Error\|null`; `updated_at: Timestamp` |
| `CandidateCreate` | `admission_id: Id`; `agent_version: integer>=1`; `base_package_ref: ArtifactRef\|null`; `expected_active_generation: integer>=0`; `change_ref: ArtifactRef`; `test_policy_ref: ArtifactRef` |
| `CandidateView` | `candidate_id: Id`; `state: draft\|building\|verification_pending\|verified\|rejected\|stale\|active`; `base_package_ref: ArtifactRef\|null`; `base_generation: integer>=0`; `candidate_ref: ArtifactRef\|null`; `change_ref: ArtifactRef`; `verification_refs: ArtifactRef[]`; `verification_set_ref: ArtifactRef\|null`; `review_ids: Id[]` |
| `VerificationStart` | `candidate_sha256: Hash`; `test_policy_ref: ArtifactRef`; `suite_ref: ArtifactRef` |
| `ReviewCreate` | `candidate_sha256: Hash`; `verification_set_sha256: Hash`; `test_policy_sha256: Hash`; `base_generation: integer>=0`; `decision: approve\|reject`; `comment: string[0,4096]` |
| `ReviewView` | ReviewCreate fields plus `review_id: Id`; `reviewer_user_id: Id`; `created_at: Timestamp` |
| `ActivationRequest` | `candidate_id: Id`; `review_id: Id`; `candidate_sha256: Hash`; `expected_base_sha256: Hash\|null`; `expected_active_generation: integer>=0` |
| `PromotionReceipt` | `promotion_id: Id`; `previous_package_ref: ArtifactRef\|null`; `package_ref: ArtifactRef`; `previous_generation: integer>=0`; `generation: integer>=1`; `review_id: Id`; `activated_at: Timestamp` |
| `RunCreate` | `admission_id: Id`; `agent_version: integer>=1`; `assignment_id: Id`; `package_ref: ArtifactRef`; `mode: engineering_replay\|model_development\|held_out_evaluation`; `expected_active_generation: integer>=0` |
| `RegistryCheckCommand` | Internal shared envelope; `agent_version: integer>=1`; `starting_shape_ref`, `host_config_ref`, `registry_ref`, `suite_ref`: `ArtifactRef` |
| `VerificationRunCreate` | Internal shared envelope; `verification_id`, `admission_id`, `assignment_id`: `Id`; `agent_version: integer>=1`; `assignment_manifest_ref`, `package_ref`: `ArtifactRef`; `condition_role: base\|candidate`; `mode: literal(engineering_replay)` |
| `RunCommand` | `expected_state_version: integer>=0`; `reason: string[1,1024]` |
| `RunView` | `run_id: Id`; `assignment_id: Id`; `agent_version: integer>=1`; `package_ref: ArtifactRef`; `purpose: ordinary\|candidate_verification\|host_conformance`; `verification_id`, `parent_run_id`: `Id\|null`; `state: queued\|running\|finalizing\|paused\|succeeded\|failed\|cancelled`; `state_version: integer>=0`; `steps_used: integer[0,12]`; `deadline_at: Timestamp`; `trial_ref: ArtifactRef\|null`; `assessment_ref: ArtifactRef\|null`; `error: Error\|null` |
| `RunEvent` | `sequence: integer>=1`; `operation_id: Id`; `attempt_id: Id`; `owner: C0..C11`; `stage: string`; `status: running\|succeeded\|failed\|cancelled`; `artifact_refs: ArtifactRef[]`; `created_at: Timestamp` |
| `EventPage` | `run_id: Id`; `events: RunEvent[]`; `next_sequence: integer>=0`; `terminal: boolean` |
| `ArtifactUpload` | `agent_id: Id\|null`; `kind: domain_material\|task_surface\|case_manifest\|source_response\|change_request`; `media_type: application/json\|text/plain`; `payload_profile: Version`; `sha256: Hash`; `file: bytes[0,10485760]` |

Lists order by ID ascending and use exclusive `after` pagination. IDs never change after creation.
Concurrent insertion may appear on a later refresh. A list response is not a frozen evaluation population.
Event pages use ascending sequence, `after_sequence>=0`, and `limit` from 1 through 100.
The event cursor advances only to the last returned event. Retain run events with their run for the first release.

`RegistryCheckCommand` is queued during C9 version publication; it has no browser command route.
Its result kind is `registry_capability_receipt`. C0 must resolve that exact version-bound receipt before admission.
The `verification` job result kind is `verification_set`; construction's result kind is `package_manifest` when sealing succeeds.
`CandidateView.verification_set_ref` remains null until a trusted verifier seals the set, including a blocked result.
Review must match that exact reference, candidate, and policy. Individual receipt lists do not authorize a browser-assembled set.
Construction ends at `verification_pending`; `VerificationStart` creates or returns the unique session for its candidate, policy, and suite.

Private evaluator admission uses a trusted administrative import command with explicit project scope, outside the browser upload endpoint.
For the first slice, `AdmissionCreate` selects the versioned fixture preset resolved during C9 agent creation.
C10 constructs C0's full internal `AdmissionRequest` from the saved manifests, callable receipt, clock, and evaluator binding.
The browser cannot submit a private evaluator reference or grant model execution through this route.
The accepted receipt exposes C0's public `StarterManifest`. It supplies initial-change, policy, suite, and registered assignment references.
Live development and held-out admission require the later registered execution configuration and a new admitted API profile.
The command stores no private content in the builder manifest and has an audited operator identity.
All uploaded bodies are data. C1, C2, and C3 decide whether their payload profile is usable.
Unknown result unions or response schema failures become server errors with restricted diagnostic receipts.

## Metadata storage contract

Use PostgreSQL 18 with `app`, `queue`, and `checkpoints` schemas. Alembic owns `app`; each library owns its schema migrations.
C9 owns users, memberships, projects, agents, versions, and sessions. Their exact identity constraints remain in C9.
Every agent-owned table contains `project_id` and `agent_id` with a composite foreign key to its agent.

| Table | Required identity, foreign keys, and constraints |
| --- | --- |
| `artifact_index` | PK `(project_id,artifact_id)`; nullable agent FK; `kind`, `sha256`, `media_type`, `payload_profile`, `producer_version`, `byte_length>=0`, `visibility`, `availability`, `created_at`; unique `(project_id,artifact_id,sha256)` |
| `admissions` | PK `(project_id,agent_id,admission_id)`; agent-version FK; configuration and manifest artifact FKs; purpose; immutable `request_sha256`; accepted/rejected outcome |
| `assignments` | PK `(project_id,agent_id,assignment_id)`; admission FK; nullable verification-session FK; `purpose: ordinary\|candidate_verification\|host_conformance`; nullable `conformance_suite_ref`, `conformance_case_id`; unique `(admission_id,case_id,condition_id,repetition)` |
| `packages` | PK `(project_id,agent_id,package_sha256)`; manifest artifact FK; immutable validated dependency-set digest |
| `candidates` | PK `(project_id,agent_id,candidate_id)`; admission FK; base package FK nullable; base generation; change artifact FK; current candidate package FK nullable; state |
| `verification_receipts` | PK `(project_id,receipt_id)`; candidate FK; receipt artifact FK; gate; input-set digest; verifier principal; result |
| `verification_sessions` | PK `(project_id,agent_id,verification_id)`; candidate FK; agent-version FK; policy, suite, assignment-manifest, and nullable verification-set artifact FKs; job ID; unique `(project_id,agent_id,candidate_id,test_policy_sha256,suite_sha256)` |
| `reviews` | PK `(project_id,review_id)`; candidate FK; reviewer user FK; exact candidate, verification-set, and policy digests; base generation; decision |
| `active_packages` | PK `(project_id,agent_id)`; package FK nullable; `generation>=0`; activation timestamp nullable |
| `promotions` | PK `(project_id,promotion_id)`; review FK; old/new package FKs; unique `(project_id,agent_id,generation)` |
| `runs` | PK `(project_id,agent_id,run_id)`; assignment FK; agent-version FK; package FK; `purpose`; nullable verification-session FK; nullable `parent_run_id`, `prepared_binding_ref`, `conformance_grant_ref`; unique `checkpoint_thread_id`; state version; absolute deadline; terminal artifacts |
| `commands` | PK `(project_id,operation_id)`; resource FK; initiating user FK; command digest; queue job ID; state; result artifact FK; registry checks have a scoped agent-version FK and one command per version |
| `api_idempotency` | PK `(principal_id,project_scope,method,route,key)`; body digest; response status/body; expiration; never stores credentials |
| `operations` | PK `(project_id,operation_id)`; run FK; stable call identity; argument digest; dispatch state; receipt artifact FK; unique `(run_id,step)` for semantic actions |
| `attempts` | PK `(project_id,attempt_id)`; operation FK; attempt number; timestamps; usage artifact FK; unique `(operation_id,attempt_number)` |
| `reservations` | PK `(project_id,reservation_id)`; operation FK; reserved and consumed limits; deadline; state; unique operation reservation |
| `events` | PK `(project_id,run_id,sequence)`; operation and attempt FKs; event payload; creation time |
| `graph_receipt_mirrors` | PK `(project_id,operation_id)`; authoritative Neo4j receipt digest; snapshot reference; mirrored time |

Use composite foreign keys for project-scoped references. A matching artifact ID in another project cannot satisfy a reference.
Use `RESTRICT` for deletion of referenced immutable artifacts. The first release exposes archive actions only where C9 defines them.
Index list queries by their project/agent prefixes and ID. Index pending commands and run events by their polling keys.
Use `READ COMMITTED` for normal transactions. Use row locks and conditional updates for membership, run transitions, reservations, and activation.
Activation and run creation lock the same agent active-pointer row. The winner defines the package pinned by the new run.
Run creation must match its mode to the admission and its assignment to that admission's registered assignment set.
The runs table has a unique constraint on `(project_id, agent_id, assignment_id)`.
An original idempotency-key retry returns the existing run. A different-key duplicate assignment returns `409`.
Resume and delivery retries retain that run. A deliberate repetition needs a newly registered assignment and repetition number.
It must match the agent version's task, tools, host, runtime, and execution mode to the package dependencies.
It must also match the submitted package and expected generation to the current active pointer.
Reject any mismatch before queue insertion. A first-profile deadline starts at run creation and cannot exceed 900 seconds.

Candidate regression uses the internal `VerificationRunCreate` command, authorized only for C6's registered verification worker.
This command uses the same run, operation, reservation, event, and checkpoint code and tables as normal runs.
Its package must equal the registered assignment's package and the session's candidate or base package for that role.
It requires a sealed candidate and an admitted development or engineering case. It does not require the package to be active.
The session pins the initiating command and principal, agent version, policy, suite, complete assignment manifest, and permitted package hashes.
C10 writes the manifest bytes first, then publishes the session, all assignments, and verification command in one metadata transaction.
No trial can start before that publication commits. C6's verifier scores the complete saved manifest through C5.
The runs table still permits only one run per assignment. Redelivery returns that run instead of allocating a new trial.
Ordinary HTTP runs cannot select verification assignments or set a verification purpose.
`verification_id` is nonnull exactly when purpose is `candidate_verification`; enforce this in assignments and runs.
Keep verification runs visible with that purpose in run summaries and filter them out of ordinary evaluation denominators.
No second execution engine or untracked internal runner is permitted.
Full-package mounting uses the [isolated conformance contract](MOUNT-CONFORMANCE.md) through these same tables and handlers.
Only registered verifier code can create its child assignments, runs, and grants. The HTTP run route rejects that purpose and those assignments.
Conformance-only fields are nonnull exactly for `host_conformance`; its verification-session field is null.
Its parent must be an ordinary or candidate-verification run with matching project, agent, version, admission, and package.
The registered suite supplies its public cases. These are excluded from scored case populations and have no evaluator access.
Conformance setup costs remain separate, retained usage. Its deadline cannot exceed the parent's original deadline.
Lock ordering is project, agent, active pointer, run, operation. Do not hold metadata locks during model or graph calls.

## Commands, queue delivery, and restart

1. Authenticate, validate CSRF, and authorize the current membership.
2. Validate the route-specific request and scoped artifact references.
3. Begin a short SQLAlchemy transaction and reserve the scoped idempotency key.
4. Save the domain command, immutable inputs, operation identity, deadline, and reservation.
5. Defer its registered task using the same SQLAlchemy connection.
6. Save the queue job ID and original `202` response, then commit.
7. The worker loads the command and rechecks its current execution authorization.
8. The worker reconciles existing receipts, then resumes the matching LangGraph thread.
9. The worker persists the terminal component result and resource accounting.

Procrastinate supports job deferral through an external transaction connection. [Official transaction guidance](https://procrastinate.readthedocs.io/en/stable/howto/production/external_connection.html).
Queue retries deliver the same domain operation. They do not create a new semantic action or refresh its budget.
Select Procrastinate's documented retry and stalled-job recovery mechanisms. Do not build a lease table or scheduler.
An expired deadline creates a failed receipt without dispatch. A revoked initiating member blocks new dispatch and preserves prior evidence.

Use the official PostgreSQL LangGraph checkpointer for deployed workers. SQLite remains the local harness substitute.
Allocate an opaque server-side checkpoint thread ID and map it uniquely to project, agent, run, and workflow version.
A browser cannot choose a checkpoint namespace. Construction candidates receive separate thread IDs from inference runs.
Checkpoints contain versioned references, step state, and pending operation IDs. Authoritative receipts stay in their owning stores.
Resume loads the pinned implementation version. Missing versions block resume instead of executing newer code silently.
Do not permit frontend time travel or arbitrary checkpoint mutation. [LangGraph persistence guidance](https://docs.langchain.com/oss/python/langgraph/persistence).

## Artifact publication and cross-store recovery

The file store root is ignored `.runtime/artifacts`. Resolve paths server-side as project, visibility, digest prefix, and digest.
Never accept client paths. Separate project namespaces even when two payloads have identical bytes.
Write to a temporary file on the same filesystem, verify size and digest, synchronize it, then rename atomically.
Synchronize the containing directory before publishing a `ready` database reference.
Use restrictive filesystem permissions. Return authenticated content responses, not public filesystem URLs.

If file publication succeeds but metadata fails, the file is an orphan. Retry may reuse verified bytes.
If a referenced file disappears, mark it unavailable and block dependent work. Do not regenerate bytes under the same identity.
An operator may collect unreferenced files after seven days, under an exclusive collection lock and a final reference check.
Preserve artifact and metadata backups together. Restore testing must verify every referenced hash before reopening dispatch.

C2 commits graph revisions and ingestion receipts inside Neo4j. PostgreSQL stores only a display and recovery mirror.
After an uncertain graph call, query C2 by operation identity before retrying ingestion.
After a mirror failure, repeat the mirror write from the authoritative graph receipt.
No transaction spans PostgreSQL, Neo4j, and the file store. A checkpoint does not create that transaction either.

## Local deployment and health

| Process or service | Local binding | Startup prerequisite |
| --- | --- | --- |
| PostgreSQL | `127.0.0.1:5432` | Separate application, queue, checkpoint, and Keycloak roles |
| Keycloak development | `127.0.0.1:8081` | C9 realm and exact redirect URI |
| Neo4j | Existing `127.0.0.1:7474` and `127.0.0.1:7687` | Preserve existing named volumes |
| FastAPI plus built React assets | `127.0.0.1:8000` | Migrations, artifact root, identity metadata, generated contract version |
| Vite development server | `127.0.0.1:5173` | Proxy `/api` and `/auth` to FastAPI; same public origin policy |
| Procrastinate worker | No browser port | Queue migrations, checkpoint setup, pinned runtime, Neo4j, and Java |

Install declared dependencies with `uv` and pinned lockfiles. Apply Alembic, Procrastinate, and checkpoint setup once before processes start.
Do not run migrations from every API worker. Configure named database schemas and privileges explicitly.
Start databases, apply migrations, verify library connections, start the worker, then start the API and UI.
Required secret settings stay in ignored `.env`: database credentials, OIDC client secret, session keys, and Neo4j credentials.
Non-secret settings pin artifact root, OIDC issuer, redirect URI, allowed origin, runtime version, and tracing mode.
Health checks report dependency states without exposing credentials. API readiness fails when its schema version or required storage is unavailable.
Deployment dependency versions and container digests remain D1 installation inputs. This design supplies no fabricated lockfile or startup success receipt.

## Challenges and required verification

| Challenge | Decision |
| --- | --- |
| FastAPI background work disappears on restart | Use a committed Procrastinate job, not request-local background execution |
| A queue promises exactly-once domain behavior | Reconcile operation receipts; delivery retries alone cannot establish semantic uniqueness |
| A shared database makes all writes atomic | Treat graph, files, metadata, and checkpoints as distinct commit boundaries |
| More streaming infrastructure seems useful | Poll indexed jobs and events first; add streaming only after a measured need |
| A generic JSON field appears extensible | Use exact Pydantic unions and generate OpenAPI from them |
| Every component becomes a microservice | Keep internal contracts within one modular application and worker deployment |

All cases below are proposed real-service tests. A SQLite harness pass does not execute these integrations.

| ID | Fault or scenario | Required observation |
| --- | --- | --- |
| C10-T01 | Metadata write or queue insertion fails | Both roll back; no runnable orphan command |
| C10-T02 | API response lost after commit | Original key returns the same job and response |
| C10-T03 | Same idempotency key, changed body | `409`; original operation remains unchanged |
| C10-T04 | Worker dies after graph commit | Recovery finds the C2 receipt and creates no duplicate revision |
| C10-T05 | Activation races with run creation | Run pins one complete package and generation |
| C10-T06 | Removed member's queued command | No new domain dispatch; prior effects and costs remain recorded |
| C10-T07 | Same resource IDs in another project | Every route, content download, and job poll rejects cross-project access |
| C10-T08 | Missing or altered artifact bytes | Dependent work blocks with an integrity error |
| C10-T09 | Restart near resource limit | Original deadline, steps, and reservation consumption remain effective |
| C10-T10 | Queue redelivery after terminal receipt | Same result; no repeated semantic action |
| C10-T11 | Generated API client and server schema differ | Build fails before frontend deployment |
| C10-T12 | Replayed event-page request | Stable order and no skipped acknowledged sequence |
| C10-T13 | Restore metadata without required blobs | Dispatch remains unavailable until integrity checks pass |
| C10-T14 | New runtime replaces a paused run's version | Resume blocks until the pinned implementation is available |
| C10-T15 | Browser submits a verifier receipt or worker identity | Boundary rejects the forged capability before persistence or dispatch |
| C10-T16 | Run mode, admission, assignment, agent dependencies, package, or generation disagree | Admission rejects the mismatch before any queued run job |
| C10-T17 | First-release job completes while the client polls its resource | Terminal state is available through polling; no streaming transport is required or exposed |
| C10-T18 | Retry a scoped assignment run with the same key, another key, then a new assignment | Same key returns the saved run; another key receives 409; a deliberate repeat requires a newly registered assignment |
| C10-T19 | Internal candidate trial, ordinary HTTP attempt with its assignment, and queue redelivery | One shared run ledger; HTTP misuse rejected; redelivery retains assignment, package, run, deadline, and checkpoint |
| C10-T20 | Owner review uses a reconstructed, missing, or older verification-set hash | Review rejects the binding; only the exact server-published set can support approval |
| C10-T21 | Version publication or binding-job queue insertion fails | Both roll back; no published version without its scoped binding command |
| C10-T22 | Conformance child creation fails, redelivers, or tries another parent or scored assignment | Atomic grant and row publication; retry retains identity and deadline; scope or purpose substitution is rejected |

These checks establish service integration only. They do not establish improved agent outcomes or complete ASD-STE100 conformity.
