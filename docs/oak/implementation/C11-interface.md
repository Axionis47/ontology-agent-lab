# C11: Human interface and graph workspace

Design version 0.4.1. Owner: C11. Status: proposed; browser verification not run.

Users must understand a requirement, its meaning, its evidence, and the consumer that applies it.
C11 presents that chain and submits explicit commands. It does not validate domain truth or activate packages locally.

The [shared contracts](CONTRACTS.md) define payload types. [C9](C09-identity.md) defines identity and permissions.
[C10](C10-service.md) owns HTTP operations. [C7](C07-visibility.md) owns version-bound read projections.
This specification applies ASD-STE100 principles. Full dictionary and grammar conformity remains unverified.

## Reuse and component boundary

| Responsibility | Selected implementation | Project-specific work |
| --- | --- | --- |
| Browser application | React, TypeScript, Vite, React Router | Routes, screens, and domain interactions |
| HTTP types and transport | `openapi-typescript`, `openapi-fetch` | Generated operation bindings and error presentation |
| Server state | TanStack Query | Scope-aware query keys, polling, and invalidation |
| Graph rendering and layout | React Flow and ELK through `elkjs` | Domain node labels, relation meanings, and inspectors |
| Accessible controls | Radix Primitives and native HTML | Labels, screen structure, dialogs, and task-specific content |
| Forms | React Hook Form | Declared form fields and server-error mapping |
| Browser verification | Playwright and axe-core | Product journeys, fault fixtures, and assertions |

React Flow documents [accessibility](https://reactflow.dev/learn/advanced-use/accessibility) and [layout integration](https://reactflow.dev/learn/layouting/layouting).
Radix supplies [accessible control primitives](https://www.radix-ui.com/primitives/docs/overview/accessibility).
Their use does not establish that this application's final composition is accessible.

Use TanStack Query's [query-key model](https://tanstack.com/query/latest/docs/framework/react/guides/query-keys) for remote state.
Do not create a custom canvas, layout solver, client SDK, form framework, or server-state store.
Do not add an in-browser graph database. C7 supplies the bounded projection required by the current view.

## Normative requirements

1. **C11-R01:** C11 must load the current session before it requests project data.
2. **C11-R02:** C11 must include project and agent scope in every applicable request and cache key.
3. **C11-R03:** C11 must display the package and evidence revision used by each result.
4. **C11-R04:** C11 must keep schema, facts, dependencies, and execution views separate.
5. **C11-R05:** C11 must expose source references and consumers for each displayed requirement.
6. **C11-R06:** C11 must retain unknown, conflicting, stale, unsupported, and unrun states.
7. **C11-R07:** C11 must create candidates through C10 instead of modifying active artifacts.
8. **C11-R08:** C11 must submit reviewed hashes when it requests approval or activation.
9. **C11-R09:** C11 must wait for the authoritative activation response before it changes the active-version display.
10. **C11-R10:** C11 must discard delayed responses whose view binding differs from the selected binding.
11. **C11-R11:** C11 must clear sensitive state after logout, session expiry, or scope revocation.
12. **C11-R12:** C11 must provide a keyboard-accessible table for every graph view.
13. **C11-R13:** C11 must label truncation and require explicit expansion before it requests more graph data.
14. **C11-R14:** C11 must keep credentials and evaluator-private material outside browser payloads and storage.
15. **C11-R15:** C11 must show the execution mode and admitted budget before a run or verification command.
16. **C11-R16:** C11 must display the resolved loop shape and distinguish configuration, binding, admission, verification, and mount evidence.

## Navigation and user questions

`p`, `a`, `r`, and `c` below are opaque project, agent, run, and candidate IDs.
Browser routes are presentation routes. They do not replace C10's versioned API paths.

| Browser route | Question answered | Required data and primary action |
| --- | --- | --- |
| `/login` | How do I enter my workspace? | Session status; sign in through C9 |
| `/projects` | Which projects can I access? | Accessible projects, role, state; create project |
| `/projects/:p` | Which agent loops belong here? | Project, memberships, agent list; create `offer-selection-v1` configuration |
| `/projects/:p/agents/:a` | What does this loop do and which kernel does it use? | Agent version, two native tools, mode, active package, readiness gates |
| `/projects/:p/agents/:a/kernel` | What meaning and computation are available? | Package selector; schema and dependency views |
| `/projects/:p/agents/:a/evidence` | What was observed in this request context? | Context, projection, revision selector; facts graph and source table |
| `/projects/:p/agents/:a/changes` | What changes are proposed? | Candidate list, base hashes, invalidation summary |
| `/projects/:p/agents/:a/changes/:c` | Is this exact change ready to activate? | Structured diff, affected consumers, gates, review, activation history |
| `/projects/:p/agents/:a/runs` | What ran, with which configuration? | Paginated run list; explicit engineering replay command |
| `/projects/:p/agents/:a/runs/:r` | Why did this result succeed, fail, or stop? | Pinned versions, ordered operations, graph revisions, task score, resource use |

The agent summary explains that an agent record configures the ontology-consuming loop.
It lists the two native tools and states that booking is unsupported in the first class.
The new-agent form offers the versioned `offer-selection-v1` starter preset.
It identifies the managed sequential loop, scripted driver, read-only effects, empty initial evidence, and absence of cross-run memory.
The [starting shape](AGENT-SHAPE.md) defines the exact request and complete resolved declaration.
The returned `starting_shape_ref` supplies its inspector. `binding_job_id` supplies probe progress through the existing job poll.
Configuration creation cannot show a ready-to-run badge. Display each required receipt as passed, failed, missing, or unrun.
It submits `configuration.kind=fixture_template`, `template_id=offer-selection-v1`, and `template_version=0.1.0` through `CreateAgent`.
C9 resolves the scoped artifact references and evaluator binding on the server. The browser does not construct private evaluator references.
An expert form may select `configuration.kind=artifact_refs` only when exact authorized references already exist.
The first run form exposes engineering replay only. Live model execution stays unavailable until C0 admits its complete configuration.

## Graph views and inspector behavior

The workspace has a view selector, version bar, searchable graph/table area, and a selected-item inspector.
The version bar remains visible during loading, errors, and comparison. It never displays an inferred compatible version.

| View | Nodes | Edges and direction | Inspector content |
| --- | --- | --- | --- |
| Schema | Named types, properties, and declared axioms | Named subclass, domain/range, restriction, and relation declarations | Definition, units, requirement IDs, exact encoding, supported-profile disposition |
| Facts | Observed entities, assertions, request contexts, observations | Declared domain relations and provenance links | Original field, normalized value, source time, source scope, conflicts, interpretation version |
| Dependencies | Requirements, schema terms, functions, operators, tests, package artifacts | Consumer to dependency; verification links use their declared relation label | Exact artifact hashes, affected semantic IDs, implemented/tested status, invalidation reason |
| Execution | Invocations, attempts, tool calls, ingestion commits, function calls, finalization | Recorded parent-call or execution order | Inputs, outputs, duration, operation identity, receipt, graph revision, failure chain |

Do not convert a navigation parent into a subclass. Do not render a domain relation as workflow execution.
Do not connect two nodes because their display labels match. Use C7's stable node and edge identities.
Use arrows and text labels. Color is a secondary cue, never the only indication of meaning or status.

Selecting a requirement opens intent, scope, meaning, evidence needs, function consumers, tests, enforcement mode, and version.
Selecting a source value opens its authorized observation and field pointer. Preserve source time separately from replay time.
Selecting a failure opens the actual inputs and diagnostic receipt. Do not substitute a model explanation for recorded evidence.

The canvas is read only for domain content. Moving nodes changes layout only.
An Edit requirement action opens a candidate form with stable target references. Drawing an edge cannot change the schema.
Use ELK for layout of the bounded returned graph. Persist no domain meaning in node coordinates.

The initial view requests at most 100 nodes and 200 edges. Expansion requests remain bounded to 200 nodes and 400 edges total.
If C7 applies a lower limit, use that limit. Show returned counts, omitted counts when known, and the server's truncation reason.
Offer node search and paginated tables for larger projections. Do not fetch a complete Neo4j database for client filtering.

## Read binding, cache, and storage contracts

Every graph response carries C7's immutable view binding and source artifact references.
The binding includes `project_id`, `agent_id`, `package_ref`, `view_kind`, and the applicable run and graph references.
Fact views require `evidence_context_id`, `projection_id`, and `revision`. Execution views require a `run_id`.
Schema and dependency views must not pretend to have a graph revision when none applies.

A query key contains the authenticated session generation, project, agent, view kind, package hash, and applicable run/context/projection/revision.
It also contains filters, selected root IDs, and pagination cursor. Use explicit nulls for inapplicable fields.
Never reuse a key based only on an agent ID, artifact hash, or display name.

Resolve an Active selection to an exact package before requesting dependent views.
If activation changes the active pointer, show a newer-version notice. Keep the inspected snapshot until the user selects the new version.
Abort obsolete requests when scope changes. Also reject late responses by binding, since cancellation can arrive too late.

Use C10 polling for jobs and runs. Stop polling on terminal state, lost authorization, or an unmounted view.
Use the server's retry delay. Do not build a custom event broker or duplicate a terminal result from several polling responses.

| Browser state | Storage and lifetime |
| --- | --- |
| Server records and graph projections | In-memory TanStack Query cache; discard on session or scope revocation |
| Unsubmitted candidate text | Component form state; show unsaved-change warning on navigation |
| Selected tab, graph/table mode, zoom | Memory or nonsensitive preference storage; no source values or artifact content |
| Source payloads and diagnostics | Authorized, bounded in-memory inspector state; no browser persistence |
| Authentication credentials | HttpOnly session cookie managed by C9; never readable by application code |

No offline queue stores mutation commands. A page reload requires a fresh authoritative read before review or activation.

## Mutation protocol and repair workflow

C11 uses generated C10 operation bindings. It does not construct filesystem paths, Cypher, SQL, or provider requests.
All unsafe requests include C9's CSRF header and a scoped idempotency key.
Retry an uncertain submission with the same key and identical body. Changed input requires a new key.

`P` means `/api/v1/projects/{project_id}`. `A` means `P/agents/{agent_id}`.
The generated C10 models control every field below. C11 must not maintain alternate copies of their definitions.

| User action | API contract | UI completion rule |
| --- | --- | --- |
| Create first agent | `POST P/agents`, `CreateAgent` with fixed starter preset | Display saved agent version and resolved readiness |
| Admit replay inputs | `POST A/admissions`, `AdmissionCreate` with agent version and `purpose=engineering_replay` | Poll job; retain accepted admission ID |
| Save change input | `POST P/artifacts`, `ArtifactUpload` with `kind=change_request` | Retain returned immutable `ArtifactRef` |
| Create candidate | `POST A/candidates`, `CandidateCreate` | Poll `Accepted.job_id`; load `CandidateView` |
| Verify candidate | `POST A/candidates/{candidate_id}/verification`, `VerificationStart` | Poll job; display each stored gate receipt |
| Review candidate | `POST A/candidates/{candidate_id}/reviews`, `ReviewCreate` | Display server-bound reviewer and hash bindings |
| Activate candidate | `POST A/activation`, `ActivationRequest` | Reload `GET A/activation`; display `PromotionReceipt` |
| Start replay | `POST A/runs`, `RunCreate` | Poll job and `GET A/runs/{run_id}` |
| Cancel or resume run | `POST A/runs/{run_id}/cancel` or `/resume`, `RunCommand` | Wait for authoritative state-version change |
| Read graph | `GET A/views/{view_kind}`, C7 view query | Accept only the requested `ViewSnapshot` binding |

Poll `GET P/jobs/{job_id}` every two seconds while visible. Back off to at most 30 seconds after transport errors.
Read run events through `GET A/runs/{run_id}/events`. Advance the cursor only to the last returned sequence.

1. Load the exact active package and generation.
2. Submit the requirement change against that base through C10.
3. Display the saved candidate, typed interpretation, affected artifacts, and unsupported requirements.
4. Display the pinned mode and budget, then submit the candidate hash, policy reference, and suite reference.
5. Poll the returned job and display each stored gate result independently.
6. Display the candidate diff and tests before requesting owner review.
7. Submit approval bound to candidate, verification-set, test-policy, and base-generation hashes.
8. Submit activation against the same reviewed bindings.
9. Reload the active pointer and display the authoritative activation receipt.

Editors can propose changes and request verification. Owners can approve and activate. The server enforces those permissions independently.
Buttons never submit passing gate statuses. Only the verifier service can publish verification receipts.
Read the set hash from `CandidateView.verification_set_ref`. Never hash or reconstruct the displayed receipt list.
Construction stops at a sealed candidate. The explicit Verify command starts the separately bound verification job.
Run lists label `candidate_verification` and its session identity. They do not combine these trials with ordinary evaluation totals.
They also label `host_conformance` and its parent run. A probe selection is never presented as the user's task result.
Verification cannot override the admission's execution mode or budget.
Show represented meaning, available evidence, implemented computation, passed tests, and bound enforcement as separate signals.

A `409` keeps the candidate visible but marks it stale. Reload the base and request a new candidate or review.
A `422` maps server field errors to the form. A `503` preserves the submitted command identity for reconciliation.
A `401` clears cached protected data and returns to login. A `403` or scope `404` clears the affected scope and stops polling.
Render source strings as text. Do not inject raw source HTML or execute links supplied by source observations.

## Design challenges and acceptance

| Challenge | Resolution |
| --- | --- |
| Make one attractive graph for everything | Four typed views preserve different meanings and consumers |
| Show green after a HermiT pass | Display each verification layer and its exact evidence separately |
| Let users edit the active graph directly | Submit a candidate with explicit base and target references |
| Optimistically show activation success | Wait for C6's persisted response and reload the active pointer |
| Cache by artifact hash alone | Include session and full authorized view scope |
| Require artifact IDs from a fresh-project user | Resolve the fixed versioned starter preset through C9; keep evaluator binding server-side |
| Implement custom graph controls and transport | Reuse React Flow, ELK, generated clients, and TanStack Query |

All cases below are required browser tests. None has run for this proposed interface.

| Test ID | Scenario or fault | Required result |
| --- | --- | --- |
| C11-T01 | Login, create project, create preset agent, admit replay | Correct scoped references; no private evaluator reference or manual artifact-ID requirement |
| C11-T02 | Viewer opens editor or activation route directly | Read-only view or denial; server receives no authorized mutation |
| C11-T03 | Navigate between projects while old requests finish | No old-project data appears in the new view |
| C11-T04 | View source fixture before projection or function execution | Source values appear; graph and test statuses remain unrun |
| C11-T05 | Unknown, conflict, false, stale, and unsupported values | Distinct text labels and causes; none becomes an implicit pass |
| C11-T06 | Inspect a property, assertion, function, and failure | Correct version, source, dependency, and operation references |
| C11-T07 | Open facts with an incompatible package or revision | No combined verified view; mismatch remains visible |
| C11-T08 | Propose a schema change and move canvas nodes | Only candidate command submitted; active schema and facts remain unchanged |
| C11-T09 | Verification fails, times out, or lacks a gate | Separate non-pass states; activation remains unavailable |
| C11-T10 | Candidate or base changes after approval | `409`; no optimistic activation or reused approval |
| C11-T11 | Repeat submission after response loss | Same key and body; one saved command and one displayed result |
| C11-T12 | Logout or membership revocation during polling | Polling stops; protected caches and inspectors clear |
| C11-T13 | Graph exceeds its requested bounds | Truncation shown; explicit bounded expansion or paginated table |
| C11-T14 | Keyboard and screen-reader inspection | Graph/table parity, named controls, focus restoration, no color-only information |
| C11-T15 | Raw HTML, evaluator canary, or credential enters a response | Text rendering or boundary rejection; no executable markup or secret persistence |
| C11-T16 | Show replay result and operation totals | Synthetic status, pinned versions, partial coverage, and separate operation categories remain visible |
| C11-T17 | Create a preset while registry probes are queued or failed | Display resolved shape and distinct evidence stages; never show configuration creation as run readiness |
| C11-T18 | Inspect a sealed verification set and a candidate-verification run | Approval uses the returned set hash; run purpose and denominator stay separate from ordinary evaluation |

Exit requires a generated-client compatibility test and real browser journeys against C9/C10/C7.
Render authoritative results from the structured C4 selection and evidence fields.
After admission, resolve its public `starter_manifest_ref` through the authorized artifact endpoint.
Use its initial-change, policy, suite, and assignment references for candidate, verification, and run commands.
Engineering-mode edit forms submit supported typed requirements. They must not promise arbitrary natural-language interpretation.
The first profile requires an empty `FinalSelection.explanation`. Host prose appears only as unverified trace commentary.
The local Python harness does not establish frontend behavior, accessibility, or production authorization.
