# Task independence review

Design review 0.4.1. Owner: integration. Status: required design corrections and unrun acceptance checks.

The product must support different tasks. Offer selection is the first engineering fixture, not the product's agent type.
One project-owned agent can bind several task definitions. Each run selects exactly one immutable binding version.
The first supported loop can remain sequential and read-only. Those execution restrictions do not fix a task's tools, ontology, request, result, or evaluator.
This review does not claim support for arbitrary external agents, uploaded code, or every task.

## Boundary to enforce

| Shared core owns | Each versioned task definition owns |
| --- | --- |
| Project authorization, agent identity, task-binding identity, immutable references, lifecycle, and audit | Task identity, description, request schema, completion schema, and domain requirements |
| Sequential decision, dispatch, observation, finalization, cancellation, and recovery protocol | Permitted native tools, their exact contracts, installed callable bindings, and source policies |
| Schema compilation profile, logical verification, projection transactions, and provenance | Domain classes, predicates, identities, units, mappings, competency questions, and example evidence |
| Function dispatch and dependency validation | Approved function templates, typed function contracts, domain computation, and tests |
| Evaluation protocol, full assignment accounting, and protected evaluator access | Independent evaluator binding, task metrics, check identifiers, expected outcomes, and abstention meaning |
| Candidate state, verification sessions, review, and atomic activation | Required task checks, guard contracts, intended changes, and regression case manifests |
| Typed graph and trace views, accessible controls, and generated HTTP bindings | Domain labels, task input fields, completion rendering, and task-specific diagnostics |

Task-specific bytes remain strict typed artifacts. A core envelope identifies their registered contract and immutable reference.
At the task boundary, validate the payload with the selected Pydantic model or TypeAdapter. Do not replace exact contracts with an unchecked JSON object.
Use an explicit registry of installed implementations. A task definition cannot provide Python source, import paths, shell commands, or arbitrary provider endpoints.
Task extension can require new reviewed domain code and fixtures. It must not require edits to shared lifecycle, authorization, scheduling, or storage algorithms.
The schema compiler's supported OWL syntax and the core's structural graph relations remain explicit versioned limits.
Domain predicate names and task check IDs must not become enums in those shared mechanisms.

## Component findings and required tests

These findings identify the offer-specific assumptions in the component specifications that must move behind the task-definition boundary.
The tests below are proposed release checks. They have not run.

| Owner | Current coupling or missing boundary | Required split | Test that prevents recurrence |
| --- | --- | --- | --- |
| [C0](C00-task-admission.md) | Admission fixes `offer-selection-v1`; TaskRequest fixes city, stay, party, USD, and offer source fields | Admit a selected task-binding version; resolve its request model, sources, cases, and task-specific bounds | Admit two different task request shapes for one agent; reject each payload under the other binding without changing admission code |
| [C1](C01-schema.md) | Offer examples and occupancy coverage can be read as universal schema obligations | Keep the compiler and typed patch protocol in core; obtain terms, requirements, and competency suites from the task definition | Compile two disjoint vocabularies with the same compiler; reject unsupported syntax rather than an unfamiliar domain term |
| [C2](C02-evidence.md) | ToolObservation, RequestScope, entity identity, quote semantics, and USD normalization assume accommodation | Keep observation identity, immutable revisions, conflict states, and receipt transactions in core; bind source identity, request scope, extraction, and normalization to the task | Project a source with no offer, date, party, or money fields; reject a mapper or source manifest from another binding |
| [C3](C03-functions.md) | One `select_eligible_offers` function, one EligibilityRecipe, five checks, and offer-shaped results are universal payload types | Core dispatches registered functions through exact task-owned input and result contracts; the eligibility template stays with its fixture | Invoke a second task's approved function with a different signature; reject an unknown template and cross-task bundle without editing dispatcher logic |
| [C4](C04-execution.md) | NativeCall admits exactly SearchOffers/GetOfferDetails; FunctionCall and FinalSelection fix the whole action payload | Keep action kinds and controlled dispatch in core; resolve the tool arguments, function contracts, completion payload, and guard from the run's binding | Execute a different native tool and typed completion through the same handlers; reject a completion or function from the other task before release |
| [C5](C05-evaluation.md) | CheckId, complete success, abstention, and scoring logic encode one selection evaluator | Core preserves assignments and evaluation status; the task supplies its independent evaluator and typed metric/check report | Evaluate two task result shapes independently; reject an evaluator mismatch and prove that no offer scorer is a default fallback |
| [C6](C06-workspace.md) | Five requirement conditions, a sole eligibility recipe, and agent-wide activation assume one task per agent | Keep review and verification machinery; bind requirements, regression policy, candidate, and active pointer to one task binding | Activate a repair for binding A while binding B runs; B's pointer, generation, evidence, and pinned package must remain unchanged |
| [C7](C07-visibility.md) | Domain predicates are already data, but ViewBinding lacks explicit task-binding identity | Preserve structural node/relation kinds; add the selected binding to view scope and use task metadata for domain meaning | Render an unfamiliar predicate without a core enum change; reject a view assembled from another binding's package or snapshot |
| [C8](C08-agent-loop.md) | Host configuration and scripted policy fix offer tools, a single function port, and offer-detail decisions | Core owns the bounded loop and hooks; resolve task action contracts and registered decision policy or prompt through the binding | Run two distinct registered task policies on the same host implementation; readiness receipts must bind the selected task contracts and implementations |
| [C9](C09-identity.md) | Agent identity, `agent_class`, version configuration, and preset publication are tied to one task | Keep agent identity and host configuration independent; store multiple versioned task bindings below that agent | Attach A and B to one agent, update A, and verify that B's binding version and authorization remain unchanged |
| [C10](C10-service.md) | Routes and active-package key select only project/agent; run, candidate, and admission scope do not select a task binding | Require the binding on task-owned commands and rows; use composite constraints for all dependent references | Reject an A assignment with a B package; concurrent activations for A and B succeed independently; same-binding stale activation still returns conflict |
| [C11](C11-interface.md) | New-agent flow offers only the selection preset and authoritative result rendering assumes FinalSelection | Separate agent creation from task attachment; select a binding before admission, workspace, activation, or run; render the selected completion contract | Show two tasks under one agent, submit each input shape, retain selected task on reload, and never render one task's score or result as the other's |

## Binding and activation isolation

Use one stable task-binding ID for each agent-to-task association, with immutable binding versions.
The binding selects the task-definition version and its exact compatible tool, mapper, function, guard, evaluator, and test contracts.
Agent configuration identifies the host and loop. Updating a task does not rename the agent or silently revise its other bindings.

Every admission, candidate, verification session, assignment, package, run, projection context, and review must resolve to that binding version.
The active pointer key must include `(project_id, agent_id, task_binding_id)`, with a generation local to that key.
Run creation locks only the selected binding's pointer and pins its package, binding version, and agent version.
Existing runs keep those versions after either task or agent configuration changes.
Artifact or assignment IDs alone cannot cross this boundary. A foreign binding reference fails before work is queued.
Conformance children retain their parent's binding, version, package, and isolated evidence context; they remain excluded from task scoring.
Compatibility or probe caches must include the selected task's contracts and implementations. A shared host implementation alone cannot justify reuse.

## Evidence needed to close this review

1. Define a second deterministic task fixture with different tools, vocabulary, request fields, completion shape, and evaluator checks. It must contain no accommodation or currency requirement.
2. Bind both fixtures to the same agent and run them through the same core admission, construction, dispatch, verification, and activation code.
3. Keep each task's registered definitions, domain callables, source mappings, independent scorer, and tests separate from core modules.
4. Execute the cross-binding rejection and concurrent activation checks above. Preserve all failed trials and separate denominators.
5. Show that adding the second task changes only registered task assets and domain implementations, not core task-name branches or shared enums.

A declaration parser accepting two names is insufficient. The release evidence must show both task bindings reaching observable consumers through the shared services.
Until those checks run, task-independent behavior is a design obligation, not an implemented capability or a measured ontology benefit.
