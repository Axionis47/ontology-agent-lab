# PRD 1: Task surface discovery

[Product documentation](../../docs/README.md) | [Current user guide](../../docs/use.md)

This document retains the detailed product requirements.
Use the current guides for setup, operation, and implementation status.

Status: Joint discovery loop implemented. Controlled checks cover the downstream flow.
Date: 2026-11-10.

## 1. Purpose and boundary

Discovery makes task requirements, tools, and source relationships inspectable.
It uses the saved task surface, agent scope, exact grants, and actual tool responses.
Training examples and an independent evaluator are not prerequisites.
Existing example cases remain optional task context.

The user supplies the test environment and its Model Context Protocol (MCP) connections.
Oak does not create isolation infrastructure or certify isolation.
AppWorld is a validation dependency. It is not a required product service.

Discovery produces initial requirements (`R_0`) and a schema proposal (`S_0`).
It also produces capability evidence, source bindings, operation contracts, and unresolved gaps.
These artifacts remain proposals. Discovery does not validate an ontology or train an agent.
Kernel construction, executable functions, inference, and task execution are later components.

The paper motivates explicit task relationships.
MCP integration, user controls, and evidence records are project requirements.
This product scope supersedes the earlier CLI-only and fixture-only discovery scope.
The hotel fields, fixed function count, and global SQLite version rules do not apply.

## 2. Inputs and controls

The original task and agent boundaries remain authoritative.
Save their exact text before the first probe.
Bind the run to the task, agent, grants, model configuration, and native catalog.
Keep credentials in the backend credential store.

The user enters an environment label and a model-cost allowance before Start.
Start permits read and write probes through the saved grants and boundaries.
The model proposes calls. The host validates and executes them.
Tool metadata remains untrusted source data.
An annotation cannot prove an effect or expand a grant.

The controller uses these stages:

`inputs -> tools -> exploration -> checks`

Exploration repeats requirement proposals, schema proposals, and MCP probes together.
Each exploration model call returns one complete draft and its next action.
The action is a probe, clarification, revision, finish request, finish with gaps, or conflict.
Each probe names an unresolved question, affected requirements and declarations, and expected information.
Actual responses and check results supply context for the next draft.
Keep declaration identifiers when their meaning remains unchanged.
Update dependent declarations in the same revision.

Apply these modeling rules:

| Item | Rule |
|---|---|
| Entity | The task must identify, connect, or track instances separately. Specify identity fields and their source scope. |
| Property | The task needs a value that describes an entity without separate identity. Specify its type, source, and applicable units. |
| Relation | The task needs a connection between entities. Support both endpoints and the connection with source evidence. |
| Function need | The task needs a computation or check. Specify typed inputs, output, evidence dependencies, and missing-evidence behavior. |

Record each choice's task purpose, representation reason, evidence, and unresolved assumptions.
A nested response object does not by itself require an entity.
Similar names do not establish identity or a relation.
Tool declarations can support proposed structure. Actual responses supply observed values.
A draft or explanation cannot supply source evidence for another modeling choice.

Allow incomplete drafts with explicit findings. Reject invalid evidence references before dispatch.
Require supported types, identity fields, source bindings, and relation endpoints before readiness.
Require a modeling explanation for each entity, property, relation, and function need.
Unresolved assumptions in these explanations prevent readiness.
Failed finish checks return their findings to exploration.
Finish with gaps preserves the proposal and does not enable training.

Function needs guide exploration. They contain no executable plans.
Training still runs the saved cases through basic ReAct before function construction.
Discovery uses the current runtime types and operations.
It does not change training, evaluation, or inference behavior.

Run status is `running`, `pausing`, `paused`, `completed`, or `stopped`.
The pause reason identifies questions, a user request, or a reached limit.
A completed run can contain gaps.

| Limit | Default | Backend ceiling setting |
|---|---|---|
| Model cost | Required user input | `OAK_SURFACE_MAX_COST_USD`, default USD 10 |
| MCP calls | 12 | `OAK_SURFACE_MAX_MCP_CALLS`, default 100 |
| Model calls | 14 | `OAK_SURFACE_MAX_MODEL_CALLS`, default 100 |
| Active time | 600 seconds | `OAK_SURFACE_MAX_ACTIVE_SECONDS`, default 3600 |
| Clarification rounds | 2 | `OAK_SURFACE_MAX_CLARIFICATION_ROUNDS`, default 10 |

Count dispatched attempts, including failures and confirmation reads.
Exclude paused time from active time.
Reserve the bounded model cost before dispatch.
Retain the reservation if usage is unknown.
Keep discovery accounting separate from the connection-check allowance.

Pause for review when a limit prevents the next call.
The user can increase a limit while paused, then select Resume.
Counters and costs remain cumulative.
Changing a USD 1 limit to USD 2 sets a USD 2 total allowance for that run.
Pause prevents the next call. An in-flight call can still finish.
Stop ends the run and preserves its evidence.
Neither control promises rollback of an external write.

## 3. Questions and continuation

A question identifies unresolved intent or missing user input.
Include source references, affected objects, and the reason an answer is needed.
Capability gaps remain findings. A user answer cannot prove a source guarantee.
Continue independent work where possible.
Pause before an operation that depends on an unanswered blocking question.
Publish at most three questions per clarification round.
Provide choices where useful and a text answer field.

Answer and resume submits the answers and explicitly continues the run.
Typing an answer does not dispatch a call.
Store each submitted answer, author, and time.
Keep original task text unchanged.
An answer cannot expand grants or weaken an explicit boundary.
Report a conflict instead of using a conflicting answer for a probe.
A repeated question must explain the remaining ambiguity.
Pause for review when the clarification-round limit is reached.
The user can increase the limit to publish the pending questions.

Before continuation, validate the request ID and expected run revision.
Recheck grants, model configuration, connection status, and native catalogs.
Recheck source data before another write.
Rebuild proposals that depend on new answers.
Do not replay completed writes.

Hold no model request or MCP session while paused.
Permit one executing run for the backend.
Permit one unfinished run per agent.
A paused run releases the execution slot.
After a backend interruption, stop unfinished execution and preserve unknown outcomes.
Do not resume automatically after restart.

## 4. Evidence and invariants

Read native catalog pages through the same client used for probes.
Record protocol, server identity, input schemas, output schemas, and annotations.
Record absent output schemas explicitly.
Pass only granted tool metadata to the model.

Give each dispatch a host-issued invocation ID.
Save its arguments, actual response, parsing result, duration, and error state.
Use the session request boundary without automatic tool retries.
Reject invalid arguments before dispatch.
Check structured responses against declared output schemas where available.
Keep failed observations distinct from accepted response fields.
Support structured responses and text observations.
Do not follow resource links or execute generated code to interpret responses.
Oversized responses retain an omission marker and digest. They are incomplete evidence.

Preserve these invariants:

- Original scope and current grants remain authoritative.
- User answers establish intent, not external facts.
- Every observation references an actual call.
- Declared, observed, proposed, unsupported, and unknown remain distinct.
- Incomplete reads do not prove complete coverage or confirmed absence.
- A write acknowledgment does not establish a confirmed effect.
- Unknown writes are not automatically retried.
- Cost and resource counters survive every resume.
- Relevant configuration changes invalidate affected work.
- Page loading, polling, and answer entry do not dispatch model or tool calls.
- Discovery completion does not imply training success.

A later read can compare specified fields with a write observation or its saved arguments.
The host performs the comparison and records both observations.
The comparison establishes only the matching fields.
It does not establish provider atomicity, idempotency, or complete coverage.
An uncertain write stops discovery.

Requirements reference original source text or explicit clarifications.
Source bindings identify granted tools and existing source paths.
Relations reference both endpoint bindings and motivating requirements.
Check identity declarations and cross-artifact references.
Report missing requirement coverage and unsupported mappings.
Keep schema proposals distinct from validated schemas.

## 5. Data model

PostgreSQL stores state. Pydantic validates variable artifact payloads.

| Table | Content |
|---|---|
| `discovery_runs` | Original inputs, digests, limits, stage, status, checkpoint, revision, and active time |
| `discovery_calls` | Dispatch identity, request, proposed effect, result reference, usage, and cost accounting |
| `discovery_artifacts` | Immutable model configuration, catalogs, observations, capability reports, proposals, comparisons, and checks |
| `discovery_questions` | Question batches, evidence links, submitted answers, authors, and times |
| `discovery_events` | Ordered progress, pause/resume records, request deduplication, and limit history |
| `discovery_credentials` | Private encrypted values or Vault references, scoped to a run and connection |

Evidence references contain an identifier and JSON Pointer path.
Check ownership and path existence.
Artifacts retain a content digest and creation time.
New proposals create new records. Earlier proposals remain inspectable.
Save each usable draft with its revision, source proposal, and check findings.
The run checkpoint identifies the current draft and any pending probe.
Show this draft through the existing requirements and schema fields during exploration.
Publish final requirements, schema, and package checks in one transaction.
The checkpoint records their artifact identifiers and the final draft identifier.
Preserve the existing requirements and schema payload shapes for training.
Store modeling explanations and function needs only in discovery artifacts.
The existing tool catalog retains optional output schemas and annotations.
Task membership protects all discovery endpoints.
Redact authentication material from displayed evidence.
Replace returned credential values with opaque references before model access.
Resolve a reference only for its original run and MCP connection.
Keep private values while paused. Remove them when the run ends.
A credential reference cannot support a schema binding.

## 6. API and frontend

Use `/api/tasks/{task_id}/agents/{agent_id}/discovery` as the route base.

| Method and route | Behavior |
|---|---|
| `GET /` | Read readiness and paginated history |
| `POST /runs` | Start with an idempotent request ID and limits |
| `GET /runs/{run_id}` | Read state, counters, questions, calls, and artifacts |
| `GET /runs/{run_id}/events?after={sequence}` | Read ordered progress after a cursor |
| `GET /runs/{run_id}/artifacts/{artifact_id}` | Read authorized evidence |
| `POST /runs/{run_id}/pause` | Request a pause |
| `POST /runs/{run_id}/resume` | Submit answers or increased limits and explicitly continue |
| `POST /runs/{run_id}/stop` | End the run and preserve the partial package |

Add Discovery below Model connection on the existing agent page.
Show actual stages and counters, not an estimated percentage.
Provide Overview, Tools and probes, Requirements, Schema, Evidence map, and Review views.
The Schema view shows proposed entities, properties, and relations.
The Schema and Review views show the current revision and proposed function needs.
The inspector shows the selected declaration's modeling reason and supporting evidence.
The Review view shows unresolved modeling assumptions and draft findings.
Display exploration as a repeated stage instead of separate probe and schema stages.
The Evidence map shows links between requirements, tools, observations, and schema records.
Do not display questions or gaps as graph nodes.
The Review view separates user questions, evidence gaps, and package checks.
Keep submitted answers visible as user clarifications.
An answer does not remove an evidence gap or prove an external fact.
Rows and map elements open the same evidence inspector.
Show only records linked to the selected item in the inspector.
Separate user clarifications from tool observations and source evidence.
Do not repeat all run gaps in each inspector.
Keep long record lists in bounded scroll areas.
Provide artifact history and run history. Generated artifacts remain read-only.
Reuse shadcn/Radix, Lucide, and Tailwind.
Load React Flow only when its tab opens. Disable graph edits.
Preserve keyboard access and equivalent table navigation.

## 7. Model boundary and acceptance

Use the asynchronous Google Gen AI SDK through Vertex AI.
Use separate discovery model settings.
Defaults are 32768 input tokens, 4096 probe output tokens, and 16384 proposal output tokens.
The model timeout is 90 seconds. The MCP timeout is 30 seconds.
Count complete model input before generation.
Reject oversized input and truncated or invalid output.
Disable SDK generation retries.
A proposal with invalid evidence references can receive one correction attempt.
Save the validation error and count the correction against the same limits.
Do not dispatch a tool from an invalid proposal.
The provider schema omits complex size constraints. Pydantic enforces the complete contract.

Test read/write probes, observed comparisons, and uncertain effects.
Test a property that becomes an entity after a source observation.
Test function dependencies that select further probes and failed finish checks that require revision.
Test incomplete drafts, final publication, and training rejection of packages with blocking gaps.
Run discovery, baseline ReAct, harness construction, evaluation, repair, and inference in the controlled environment.
Test clarification conflicts, repeated questions, all limits, and explicit increases.
Test deduplication, grants, catalog drift, invalid references, interruption, and redaction.
Browser tests cover start, questions, resume, limits, evidence, and reload persistence.
Assert that page loading and answer entry cause no model or MCP dispatch.
Keep existing task, agent, connection, and model tests passing.

Live validation uses a user-authorized environment and a separate allowance.
AppWorld validation does not establish benchmark performance.
Completion requires inspectable evidence, cumulative limits, controlled continuation, and no write replay.
