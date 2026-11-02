# C9: Identity, projects, and agent configurations

Design version 0.4.1. Owner: C9. Status: proposed, service verification not run.

Users need project access before they can inspect an ontology or start a run.
C9 binds authenticated people and trusted workers to that access.
An agent is a configured ontology-consuming loop. It is not the complete agent application.

The [shared contracts](CONTRACTS.md) govern identifiers, references, errors, and envelopes.
The [baseline](README.md) governs deployment and storage. This component applies ASD-STE100 principles; full conformity remains unverified.

## Reuse and deployment decisions

| Responsibility | Selected implementation | Project-specific code |
| --- | --- | --- |
| Identity provider | Keycloak, local development realm `oak-local` | Realm/client configuration only |
| OIDC authorization code and PKCE | Authlib Starlette integration, S256 | Issuer configuration and validated identity binding |
| Server session and cookie lifecycle | `starsessions` middleware | PostgreSQL `SessionStore` adapter through SQLAlchemy |
| CSRF protection | `starlette-csrf` middleware | Protected-route and cookie configuration |
| Persistent ownership | PostgreSQL, SQLAlchemy, Alembic | Tables, constraints, membership policy, and migrations |

Authlib supports [OIDC clients and PKCE](https://docs.authlib.org/en/latest/oauth2/client/web/).
Keycloak supplies [discovery, authentication, and logout endpoints](https://www.keycloak.org/securing-apps/oidc-layers).
Use its discovered endpoints from one configured issuer. User input cannot select an issuer or token endpoint.

`starsessions` supplies [session lifecycle, rotation, and a store interface](https://github.com/alex-oleshkevich/starsessions).
The adapter implements only `read`, `write`, and `remove`, plus database expiry and revocation conditions.
It must not implement cookie generation, token validation, encryption algorithms, or an identity protocol.
This limited adapter avoids a Redis service used only for sessions. RedisStore remains the alternative if the adapter fails its acceptance tests.

Use the library's built-in Fernet encryption for provider data stored in sessions. Keep its key outside the database and tracked files.
Do not create a custom encryption class. Do not store provider tokens in browser storage or cookies.
Use [starlette-csrf](https://github.com/frankie567/starlette-csrf) for the signed double-submit check.

Bind development services to loopback. Keycloak `start-dev` is a local profile, not a public deployment configuration.
The application serves the frontend and API through one browser origin. Development frontend proxying preserves that API origin.
Use `http://127.0.0.1:8000` for the application and `http://127.0.0.1:8081` for the local Keycloak issuer.
The Vite development server at `127.0.0.1:5173` proxies API and authentication routes to the application.
Pin library versions and container digests before D1 service verification. No new service is installed by this specification.

## Ownership and immutable configuration

```text
User --ProjectMembership(role)--> Project
Project --> AgentConfig --> AgentVersion
AgentVersion + active KernelPackage --> Run
Run --> scoped evidence contexts, observations, events, and results
```

`AgentConfig` is a stable identity and display name. `AgentVersion` contains immutable execution settings.
The first `agent_class` is `offer-selection-v1`. Its tools are the two fixture contracts admitted by C0.
A new configuration creates a new version. It does not change an existing run or a frozen package.
Run creation pins both an agent version and a kernel package in one metadata transaction.
C6 owns kernel activation. C9 cannot bypass C6 verification by changing an agent version.

**C9-R01:** C9 must identify a user by the verified issuer and subject pair.
**C9-R02:** C9 must authorize every project-scoped lookup before resolving its contents.
**C9-R03:** C9 must reject an agent whose project differs from the requested scope.
**C9-R04:** C9 must preserve immutable agent versions and run bindings.
**C9-R05:** C9 must separate human roles from verifier and evaluator service capabilities.
**C9-R06:** C9 must recheck membership before each mutating transaction and worker-stage dispatch.
**C9-R07:** C9 must preserve at least one active owner for an active project.
**C9-R08:** C9 must revoke local session access before attempting provider logout.
**C9-R09:** C9 must reject browser-supplied role, principal, or worker identity claims.
**C9-R10:** C9 must exclude credentials from configuration artifacts, responses, and traces.

## Metadata schema

All timestamps use the shared `Timestamp`. IDs use the shared `Id`.
The application database role cannot create or alter tables. Alembic uses a separate migration role.

| Table | Required columns and constraints |
| --- | --- |
| `users` | `user_id PK`, `issuer text`, `subject text`, `display_name text`, `active boolean`, `session_epoch bigint`, `created_at`; unique `(issuer,subject)` |
| `projects` | `project_id PK`, `name varchar(120)`, `state active_or_archived`, `authorization_revision bigint`, `created_by FK users`, `created_at` |
| `project_memberships` | `project_id FK projects`, `user_id FK users`, `role owner_or_editor_or_viewer`, `revision bigint`; primary key `(project_id,user_id)` |
| `agent_configs` | `project_id FK projects`, `agent_id`, `name varchar(120)`, `agent_class literal(offer-selection-v1)`, `state active_or_archived`, `current_version bigint`, `revision bigint`; primary key `(project_id,agent_id)` |
| `agent_versions` | `project_id`, `agent_id`, `version bigint`, `config_ref FK artifact_index`, `created_by FK users`, `created_at`; primary key `(project_id,agent_id,version)`; composite FK to agent |
| `web_sessions` | `session_key_hash PK`, `encrypted_payload bytea`, `user_id nullable FK users`, `session_epoch bigint`, `created_at`, `absolute_expires_at`, `last_seen_at`, `revoked_at nullable` |
| `identity_audit` | `audit_id PK`, `actor_id`, `project_id nullable`, `action`, `target_id`, `outcome`, `operation_id`, `occurred_at`; append only |

Artifact and run foreign keys must include project scope. An agent ID alone cannot resolve a related object.
The session lookup key is SHA-256 of the middleware's opaque session identifier. Never log either value.
Session reads reject expired, revoked, or user-epoch-mismatched rows. Session writes cannot clear a prior revocation.
Concurrent writes use database conditions. They cannot recreate a removed or rotated session.
Keep revoked-session tombstones until their original absolute expiry, then remove them through the standard job worker.

The authenticated session payload becomes immutable after login. Ordinary API calls do not modify provider state.
Update idle activity with an atomic database maximum. Do not use middleware last-writer-wins payload updates for authorization decisions.
Only login, rotation, and logout may change identity payloads. Their transaction tests must cover concurrent stale requests.

## Public payloads and routes

All payloads use strict Pydantic models with unknown fields forbidden.
Names contain 1 through 120 Unicode characters. Return the authoritative record version after each mutation.

| Payload | Required fields |
| --- | --- |
| `SessionView` | `user_id: Id`, `display_name: string`, `expires_at: Timestamp`, `authenticated: true` |
| `CreateProject` | `name: string` |
| `ProjectView` | `project_id: Id`, `name: string`, `state: active_or_archived`, `role: owner_or_editor_or_viewer`, `authorization_revision: nonnegative_integer` |
| `SetMembership` | `user_id: Id`, `role: owner_or_editor_or_viewer`, `expected_authorization_revision: nonnegative_integer` |
| `CreateAgent` | `name: string`, `agent_class: literal(offer-selection-v1)`, `configuration: FixtureTemplateConfig_or_ArtifactConfig` |
| `FixtureTemplateConfig` | `kind: literal(fixture_template)`, `template_id: literal(offer-selection-v1)`, `template_version: literal(0.1.0)` |
| `ArtifactConfig` | `kind: literal(artifact_refs)`, `settings: AgentVersionPayload` |
| `AgentVersionPayload` | `starting_shape_ref`, `task_surface_ref`, `native_tool_manifest_ref`, `host_config_ref`, `budget_ref`, `runtime_ref`: `ArtifactRef`; `model_config_ref: ArtifactRef_or_null`; `execution_mode: optional_functions_or_guarded_requirements` |
| `CreateAgentVersion` | `expected_version: positive_integer`, `configuration: AgentVersionPayload` |
| `AgentView` | `project_id: Id`, `agent_id: Id`, `name: string`, `agent_class`, `state`, `current_version: positive_integer`, `revision: nonnegative_integer`, `config_ref: ArtifactRef`, `starting_shape_ref: ArtifactRef`, `binding_job_id: Id` |
| `AgentUpdate` | `name: string`, `state: active_or_archived`, `expected_revision: nonnegative_integer` |
| `AuthorizationDecision` | `principal_id: Id`, `project_id: Id`, `agent_id: Id_or_null`, `action: registered_action`, `allowed: boolean`, `authorization_revision: nonnegative_integer`, `operation_id: Id` |

`AuthorizationDecision` is an internal record, not a client bearer permission.
C10 must re-evaluate permission within the operation transaction. A saved decision does not grant later access.

`AgentUpdate` changes only display name and archive state. It increments the mutable record revision atomically.
An archived agent rejects new admissions, versions, candidates, and runs. Existing pinned runs may complete or receive a separate cancel command.
Archiving does not revoke project membership or modify a package. An editor or owner can restore the active state with the current revision.

### First-project setup

A fresh project has no artifact references. Its CreateAgent request must use `FixtureTemplateConfig`.
The server resolves the exact preset from a packaged, versioned registry. This registry contains only the first task class.
C0 supplies the public task, source, tool, clock, and case manifests. C8 supplies the callable and host configurations.
The trusted evaluator importer supplies a separate evaluator binding. The browser never receives its private artifact reference.
C10 writes project-scoped public artifact bytes before the agent creation transaction.
That transaction publishes the immutable agent version, template manifest, and server-only evaluator binding.
It also queues C8's `verify_registry` command atomically and returns its `binding_job_id`.
A version has one immutable binding command identity. Delivery retries retain that identity and its exact shape and implementation hashes.
A new implementation needs a new agent version. A completed rejected binding does not become ready through a new flag.
A failed transaction leaves no partially visible agent. Its unreferenced blobs follow C10's collection policy.

`ArtifactConfig` supports already published project artifacts. It cannot select evaluator-private content or arbitrary worker implementations.
The agent version pins the resolved template digest. A later preset release cannot alter an existing configuration.
This is a fixed starter preset, not a generic template execution engine.
The [starting shape](AGENT-SHAPE.md) supplies the exact declaration, resolved references, supported channels, and readiness chain.
`agent_class` names its task profile; `loop_profile` separately names its execution restrictions.
Selecting a preset registers configuration only. Admission waits for the server-issued pre-kernel binding receipt.
All artifact-based versions must resolve the same permitted implementation keys and match the shape's fields.
An artifact hash cannot authorize uploaded code, arbitrary imports, endpoints, or a different host architecture.

| Route | Request and response |
| --- | --- |
| `GET /auth/login` | Fixed same-origin return destination; redirect to configured Keycloak client |
| `GET /auth/callback` | Authlib validates provider response; redirect after session rotation |
| `GET /api/v1/me` | `SessionView`, or `401` |
| `POST /auth/logout` | CSRF check; revoke local session; return provider logout redirect and `local_session_revoked: true` |
| `POST /api/v1/projects` | `CreateProject` to `201 ProjectView`; creator becomes owner atomically |
| `GET /api/v1/projects` | Cursor-paginated accessible `ProjectView` records |
| `PUT /api/v1/projects/{project_id}/members/{user_id}` | `SetMembership` to updated `ProjectView`; path and body user IDs must match |
| `DELETE /api/v1/projects/{project_id}/members/{user_id}` | Expected authorization revision; `204` after last-owner check |
| `POST /api/v1/projects/{project_id}/agents` | `CreateAgent` to `201 AgentView` |
| `PATCH /api/v1/projects/{project_id}/agents/{agent_id}` | `AgentUpdate` to `200 AgentView`; owner or editor; stale revision returns `409` |
| `POST /api/v1/projects/{project_id}/agents/{agent_id}/versions` | `CreateAgentVersion` to `201 AgentView` |

C10 owns transport, pagination, idempotency, and generated OpenAPI. C9 owns these payloads and authorization decisions.
Members can be added only by exact existing application user ID. The target must have completed login previously.
The first release has no email invitations, public signup workflow, organization hierarchy, API keys, or delegated user impersonation.
Keycloak administrators provision local accounts. That operation is outside the application API.
Archive projects and agents instead of deleting referenced records. Export or erasure needs a separately reviewed retention procedure.

## Permissions and enforcement

| Action | Viewer | Editor | Owner | Trusted service |
| --- | --- | --- | --- | --- |
| Read permitted project artifacts and run summaries | Yes | Yes | Yes | Scoped by component capability |
| Create agent versions, candidates, engineering runs | No | Yes | Yes | Only the registered operation |
| Submit verification or propose repairs | No | Yes | Yes | Scoped construction worker |
| Approve and activate a candidate | No | No | Yes | C6 executes the owner's approved request |
| Change memberships or archive project | No | No | Yes | No general worker permission |
| Publish passing verification receipts | No | No | No | Verifier only |
| Read evaluator-private material | No | No | No | Evaluator identity only |

An owner does not receive evaluator answers through the artifact API.
The local machine administrator remains outside this application isolation boundary.
Neo4j Community is not assumed to provide project-specific database tenancy.
C2 applies scoped parameters on every query. The browser receives no database credentials or raw Cypher endpoint.

Membership changes lock the project row, compare its authorization revision, and check remaining owners before commit.
They increment that revision and append an audit event in the same transaction.
Other mutations acquire a compatible row lock and resolve current membership before writing.
This prevents a concurrent stale owner from changing membership after revocation commits.

Workers retain the initiating user ID and admitted scope, not that user's browser cookie.
At each new stage, C10 checks that the user is active and still has the required project role.
A denial stops new work and requests cancellation. It does not erase completed evidence or pretend to undo prior operations.
Verifier and evaluator credentials are separate service capabilities. Human membership changes cannot create either capability.

## Login, expiry, and logout algorithm

1. Authlib creates state, nonce, and a PKCE verifier for a server-side login session.
2. C9 stores the fixed return path and a five-minute login deadline.
3. Authlib validates issuer, signature, audience, expiry, state, nonce, and the authorization code response.
4. C9 resolves the verified `(issuer, subject)` and rejects disabled users.
5. C9 rotates the session ID and invalidates its earlier session record.
6. C9 records a new local session with the current user session epoch.
7. C9 loads current project membership separately for each authorized operation.

Use a 30-minute idle limit and an eight-hour absolute limit. Clamp expiry to the validated identity-token expiry.
The first release does not use refresh tokens or request `offline_access`. Expiry requires a new login.
Use `HttpOnly`, `SameSite=Lax`, path `/`, no Domain, and `Secure` under HTTPS.
The loopback HTTP profile uses a separate cookie name and explicitly disables `Secure` only for that profile.
Reject startup if the loopback profile binds a non-loopback address.

Unsafe browser methods require the CSRF header and an allowed Origin. CSRF exclusions are limited to verified provider callbacks.
Logout first revokes the local database session, then clears cookies, then attempts standard provider logout.
A provider outage cannot preserve local access. Report that provider logout remains incomplete without logging token contents.
Identity-provider revocation is not assumed to push into local sessions. A local user disable increments `session_epoch` immediately.
The short, token-clamped session lifetime bounds unobserved provider-side revocation. Back-channel logout is a later capability with separate tests.

## Design challenges and acceptance

| Challenge | Resolution |
| --- | --- |
| Put roles in a long-lived browser token | Read current membership from PostgreSQL for each operation |
| Build a password service | Delegate login and credential lifecycle to Keycloak |
| Use email as user identity | Bind exact verified issuer and subject; email is display data only |
| Add Redis only for sessions | Reuse PostgreSQL through the middleware's narrow store extension |
| Trust a previous authorization decision | Recheck inside the write transaction and before worker stages |
| Make project owners verifier administrators | Separate human approval from service-produced verification receipts |
| Delete an agent that has runs | Archive the configuration and retain immutable versions |

All cases below require real service execution. The local harness cannot establish OIDC or cookie correctness.

| Test ID | Fault or scenario | Required result |
| --- | --- | --- |
| C9-T01 | Correct login; wrong issuer, audience, nonce, state, or expiry | Correct login succeeds; each invalid response creates no authenticated session |
| C9-T02 | Reused callback or session fixation | Old session and callback cannot establish another login |
| C9-T03 | Missing CSRF header or disallowed Origin | Mutation rejected before database work |
| C9-T04 | Foreign project, agent, artifact, or evidence context | Generic scope rejection with no foreign contents |
| C9-T05 | Viewer sends editor or owner command | `403`; no mutation or queued job |
| C9-T06 | Two concurrent last-owner removals | At least one active owner remains |
| C9-T07 | Membership revoked before queued stage begins | Stage denied; no new component dispatch |
| C9-T08 | Stale authorization revision on membership write | `409`; current membership preserved |
| C9-T09 | Archived agent has a running trial | Existing trial remains pinned; new run admission fails |
| C9-T10 | Browser attempts verifier or evaluator capability | Denied; no private data or passing receipt |
| C9-T11 | Logout races a stale session write | Revoked session cannot be recreated or reused |
| C9-T12 | Idle, absolute, or token-clamped expiry | Session rejected; fresh login required |
| C9-T13 | Provider logout fails | Local access still revoked; provider failure reported separately |
| C9-T14 | New agent version uses another project's artifact | Version creation rejected before publication |
| C9-T15 | Local profile binds publicly or secrets enter a response | Startup or serialization gate fails |
| C9-T16 | Database/session store unavailable | Authentication fails closed; no cached privilege grants access |
| C9-T17 | Browser submits an owner role or another principal in a command body | Boundary rejects the override and retains the server-bound identity |
| C9-T18 | Create preset or artifact-based version, then fail registry probes | Shape and binding job remain inspectable; configuration exists but admission remains blocked |
| C9-T19 | Known artifact hash refers to an unregistered implementation, endpoint, or incompatible shape | Version publication rejects executable or profile substitution |

Exit requires those tests, version-pinned dependencies, and an inspected login-to-project-to-agent browser journey.
No authentication, project isolation, or production deployment claim follows from this document alone.
