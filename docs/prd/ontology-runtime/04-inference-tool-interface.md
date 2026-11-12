# PRD 04: Inference and native tool interface

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

The runtime runs one ReAct agent against one frozen ontology kernel. ReAct means that the model selects an operation, observes its result, and selects the next operation.

The runtime uses existing Model Context Protocol (MCP) servers. It does not create an MCP server. It does not add a memory subsystem or a user interface.

The client also registers the frozen kernel's typed Python functions as internal model tools.
These functions compute over accepted evidence and cannot access external tools.

The kernel contains a schema, declared functions, and their executable bindings. The runtime makes task relationships explicit at each accepted operation. It does not claim to inspect the model's internal reasoning.

Read this document with [the shared contracts](00-system-contracts.md), [graph construction](03-evidence-graph.md), and [action execution](05-action-execution.md). The shared contracts control common identifiers.

## Basis and current implementation

The [paper](../../paper/source/oak-2608.22974v1.pdf), Sections 3.1 to 3.3, freezes the schema and function catalog before inference. It routes declared computations through functions over a schema-guided graph. It does not specify MCP transport, client hooks, receipt formats, or write recovery.

The current [native runner](../../../backend/examples/ontology_loop/native.py) uses the Gemini command-line interface (CLI). It exposes real SQLite and Filesystem MCP tools. The [hook](../../../backend/examples/ontology_loop/hook.py) checks calls before execution. The [Structured Query Language (SQL) compiler](../../../backend/examples/ontology_loop/sql_kernel.py) creates generated views.

The current prototype has these limits:

- Raw source rows reach the model.
- Generated views read the preloaded source tables.
- A Boolean records whether the generated view was read.
- The hook matches calls by tool name and arguments. Identical calls can collide.
- Hook configuration orders hook handlers. It does not enforce serial tool execution.
- The inspected CLI path can block a result or add context. Raw-result replacement before model delivery has not been checked.

The proposed runtime must correct these limits before it meets this document.

## Inputs and outputs

| Input | Required content |
| --- | --- |
| Run binding | `run_id`, `surface_id`, `surface_version`, `agent_id`, and `grant_version` |
| Request | One request validated against the kernel's request type and its canonical `query_hash` |
| Frozen kernel | `kernel_version`, schema, function contracts, validated Python operator plans, and binding versions |
| Grant manifest | Exact server identity, actual tool name, and permitted operation bindings |
| Source contracts | Fixed source queries, response types, source version rules, and coverage rules |
| Runtime limits | Model turn, total tool invocation, response size, context size, and retry limits |

| Output | Required content |
| --- | --- |
| Model observation | A validated receipt, function result, action result, or rejection |
| Private trace | Proposed call, executed call, raw response, validation result, and state transition |
| Run result | Final function receipt, final action state, termination reason, and resource counts |

The runtime creates `invocation_id`. It does not accept this identifier from model arguments. Each trace event carries the run binding and the applicable kernel version.

## Native calls and declared operations

An `operation_id` names a declared operation.
Its binding kind is `mcp` or `python_kernel`.
An MCP binding records the existing server, registered tool name, and permitted argument contract.
A Python binding records a registered model tool name, frozen function ID, and typed argument schema.

Register Python function names as `oak_` followed by the validated function ID.
For example, register `oak_assess_stays` and `oak_prepare_reservation` for the hotel kernel.
Reject a name collision before inference starts.
These are client function tools, not MCP server tools.
Do not interpret a model's textual answer as a function invocation.

Graph operators execute inside declared function compositions.
They do not form an unrestricted second tool catalog for the agent.
See [PRD 00, Section 9.1](00-system-contracts.md#91-operator-composition-and-native-execution) for the execution layers and trace contract.

The initial native catalog contains these actual Gemini tool names:

- `mcp_sqlite_read_query`
- `mcp_sqlite_write_query`
- `mcp_filesystem_write_file`
- `mcp_filesystem_read_text_file`

The runtime must use the names returned by discovery. It must reject a catalog that differs from the frozen grant manifest. It must not infer tool names from documentation for another package version.

| Declared operation | Registered call | Purpose and side effect |
| --- | --- | --- |
| Read hotels | SQLite `read_query` with the declared hotel source query | Read source records. The host stages accepted facts. |
| Read offers | SQLite `read_query` with the declared offer source query | Read source records. The host stages accepted facts. |
| Read policies | SQLite `read_query` with the declared policy source query | Read source records. The host stages accepted facts. |
| `assess_stays` | Client tool `oak_assess_stays` calls the Python executor | Execute the validated plan over the accepted graph. Return the assessment and evidence. |
| `prepare_reservation` | Client tool `oak_prepare_reservation` calls the Python executor | Check a proposed offer against a bound assessment. Return a typed action plan without a reservation. |
| Reserve offer | SQLite `write_query` with the bound action statement | Create one local fictional reservation under the action contract. |
| Inspect action | SQLite `read_query` with the declared action-status query | Read the exact action outcome by its identifier. |
| Publish result | Filesystem `write_file` with one fixed path | Write the validated task result. This does not authorize a reservation. |
| Read published result | Filesystem `read_text_file` with that fixed path | Read the validated result artifact. |

The operation catalog must supply the registered call and typed arguments for each permitted choice.
Python function calls contain no SQL, Python source text, or storage paths.
The host checks receipt bindings before dispatch.
It supplies the read-only graph handle and validated typed arguments to the Python executor.
External MCP calls keep their discovered interfaces.

The existing source database remains the fictional data source.
The Python graph contains facts obtained from actual native responses.
Functions receive a read-only graph view and cannot query the source database.
The executor must reject undeclared operator IDs and external-operation nodes.

## Requirements

### RUN-001: Fix the run dependencies

The runtime must bind one request to one surface version, grant version, and kernel version. It must check these bindings before the first model call. It must stop the run if a binding changes. It must reconcile a pending write before it reports termination.

The runtime must not repair the kernel during inference. It must not reuse evidence from another run. A later construction round can use the trace after this run ends.

### RUN-002: Enforce the grant and the operation contract

Before each external or kernel function dispatch, check all of these conditions:

1. The external tool is granted, or the internal function belongs to this agent's frozen kernel.
2. The call matches one declared operation binding.
3. Its logical arguments have the declared types and units.
4. Its request, kernel, and evidence bindings match this run.
5. Its required evidence and state exist.
6. No unresolved write prevents the operation.
7. Its execution remains within the run limits.

The tool allowlist must not replace these checks. Generated schema or function content must not enlarge a user grant.

The runtime must record a rejected proposal before it returns the rejection. It must not execute a rejected call.

### RUN-003: Describe each operation as a complete contract

Each operation description must state what it does, when to use it, and what it returns. It must state its argument types, units, permitted values, side effects, prerequisites, failure statuses, and recovery steps.

The request type comes from the kernel. For example, the hotel request uses integer nights and adult count. It also uses integer child age in years and integer budget in cents. Costs use integer cents.

The contract must distinguish guest capacity from stock availability. The first slice does not model room stock.

System-owned identifiers and versions must be bound by the host. The model must not invent them. The runtime may supply a complete native argument object in `next_options`.

### RUN-004: Correlate and serialize tool invocations

The host must assign one unique `invocation_id` before each dispatch. The same identifier must bind the gate decision, executed arguments, raw response, observation, and state change.

The initial runtime permits only one external or kernel function invocation in flight per run.
It enforces this rule in the dispatcher.
A model instruction, hook ordering setting, or model-supplied sequencing flag is insufficient.

If the model proposes several calls, the dispatcher must process them in proposal order. It must recheck each call after the preceding call ends. It must not authorize the entire group against an earlier state.

The current hook does not expose a checked invocation identifier. The client integration must support this capability. It must not use an argument digest as a substitute.

### RUN-005: Mediate source results before model delivery

The host must receive the actual native source response before any model-visible delivery. It must validate the response against the declared source contract. It must pass accepted records to graph ingestion.

The host must return only the declared source receipt and coverage observation to the model. It must keep raw records in the private trace. This rule also applies to raw values in errors, attached resources, and tool display content that enters model context.

Adding a receipt beside the raw response does not satisfy this requirement. An integration that cannot replace the model-visible source result must fail the capability check before a run starts.

The client must support these boundaries:

- Before dispatch: validate and authorize the proposed external or kernel call.
- Before model delivery: validate the actual result and construct the permitted observation.
- Function registration: expose typed Python functions and route their actual model tool calls to the executor.

The current hooks do not establish all three boundaries.
Test result transformation and Python function registration before the first episode.
Stop with `CLIENT_BOUNDARY_UNAVAILABLE` if either capability is unavailable.
The MCP servers remain unchanged.

### RUN-006: Use actual observations to construct the graph

Only actual source responses may supply graph facts.
Do not populate the accepted Python graph from the fixture file, reference answers, or an independent source query.

The first slice uses complete fixed source reads and one request-scoped batch. It does not merge partial fields or use a cross-run cache.

The graph component stages each validated response.
It commits the graph snapshot, coverage, provenance, and new `graph_revision` together.
It then publishes the immutable Python graph handle.
It must keep conflicting assertions for diagnosis.
It must not overwrite them by primary key.

A source receipt must identify its source operation, invocation, source version, record count, coverage, and validation issues. Its model observation must include a typed summary and the missing source operations. An opaque receipt identifier is insufficient. An empty successful read must keep its source version and complete coverage. A failed read must not count as complete coverage.

A complete observed batch can contain unresolved relationships. The function must report that graph as incomplete. The runtime must distinguish unread sources from observed but inconsistent data.

### RUN-007: Bind function results to the accepted graph

The runtime must permit function execution only after graph publication. The function must use the current accepted graph revision.

The Python executor returns one typed result with decision status, result records, query binding, and evidence references.
The host adds the kernel version, graph revision, source version, and receipt reference to that result.
Separate status and result calls do not satisfy this contract.

The host must validate that response. It must create a `function_receipt_id` that binds the exact result and its dependencies. A successful call flag is insufficient.

The function's declared procedure controls eligibility, cost, and any selection rule used by an action. The host must not silently replace a missing function with an independently written correct-answer calculation.

The hotel kernel declares `assess_stays` and `prepare_reservation`. Assessment returns the complete eligible set and per-requirement evidence. Preparation accepts the assessment receipt and a requested `offer_id`.

Preparation must use the approved `select_min` primitive with explicit ordering. The hotel order is total cost, then ascending offer identifier. Preparation must check the requested offer against that order. An unsupported primitive must block construction. It must not trigger a hidden host implementation of the rule.

The preparation output contains `selected_offer`, integer `total_cents`, and a typed action plan. It binds the assessment receipt, request, kernel, graph revision, and source version. The host must keep distinct assessment and preparation receipts.

Assessment status is `complete` or `incomplete`. Preparation status is `ready` or `rejected`. A rejected preparation may have a validated execution receipt, but it cannot authorize an action. A `ready` function result is distinct from the durable action state `PREPARED`.

Both functions must return a typed decision summary and evidence references.
The host issues each function receipt after result validation.
The generated plan cannot issue an authoritative receipt identifier itself.

### RUN-008: Return permitted next choices without granting authority

Each observation must include `next_options` derived from current runtime state.
Each option identifies its operation, binding kind, registered tool name, and typed arguments.
This rule applies to external MCP tools and internal Python functions.

An option is guidance. It is not permission to bypass the next dispatch check. An option can become invalid after a source change or a state transition.

The model chooses the next option. The runtime must not force a complete fixed action sequence when several declared operations are permitted.

When evidence is missing, the observation must name the missing source operation. When evidence is stale, it must require a new complete read batch. When a write is unresolved, it must expose only reconciliation or termination choices permitted by the action contract.

### RUN-009: Keep model context bounded

Model context must contain the task, typed request, frozen schema, operation contracts, current typed observations, and currently permitted choices. It must not contain a persistent memory subsystem, previous-run evidence, raw source responses, or private trace files.

The initial limits are 12 model turns and 24 total tool invocations.
Count MCP calls, Python function calls, denied calls, and recovery calls toward that limit.
A source response must not exceed 60,000 bytes in the 8-bit Unicode Transformation Format (UTF-8).
An observation must not exceed 16,384 UTF-8 bytes.
The final serialized model request must not exceed 131,072 UTF-8 bytes.

The client must check the final model request after it adds its own instructions and tool declarations. It must also enforce the selected model's checked input-token limit. The request must pass both limits. A byte limit does not establish a token count.

The runtime must not silently truncate records, evidence, constraints, or tool contracts. It must not use a model summary as authoritative evidence. It must return `SOURCE_LIMIT`, `OBSERVATION_LIMIT`, or `CONTEXT_LIMIT` when a limit prevents a complete operation.

The first slice must stop safely instead of adding context compaction. A pending write must enter reconciliation before run termination.

### RUN-010: Separate task state from transport termination

The run state must distinguish source collection, graph readiness, function readiness, action execution, and termination. Action state remains authoritative for effects.

| Run state | Entry condition | Permitted progress |
| --- | --- | --- |
| `COLLECTING` | Run bindings pass capability checks | Read missing sources and stage actual responses |
| `GRAPH_READY` | A complete batch is published | Execute declared functions |
| `ASSESSMENT_READY` | A bound assessment receipt contains eligible offers | Execute `prepare_reservation` |
| `DECISION_READY` | A `ready` preparation receipt exists, or an assessment requires no action | Publish the result or prepare an authorized action |
| `ACTION_PENDING` | An action is prepared or dispatched | Follow the action state machine |
| `COMPLETE` | The task result and required action outcome are confirmed | Return the final report |
| `STOPPED` | A limit, invalid binding, or unrecoverable error ends inference | Preserve state and report the reason |

An incomplete graph may produce a validated incomplete task result. It must not authorize a reservation. A complete result with no eligible offer must not authorize a reservation.

A rejected preparation returns the run to `ASSESSMENT_READY` if its assessment still passes all checks. The model can select a corrected declared call. The host must not create an action intent from the rejection.

A model text response does not establish task completion. A CLI error after a confirmed write does not mean that the write failed. The run report must keep both the action outcome and the transport termination reason.

### RUN-011: Fail closed and return useful failures

The dispatcher must deny a call if a required gate is absent, fails, or times out. The runtime must not mark a read successful from a tool name alone. It must validate the response and its correlation.

| Failure | Required observation and recovery |
| --- | --- |
| `UNGRANTED_TOOL` | Identify the denied tool. Return only granted choices. |
| `UNDECLARED_OPERATION` | Identify the contract mismatch. Return the exact permitted native template. |
| `INVALID_ARGUMENT` | Name the field, expected type or unit, and permitted value pattern. |
| `MISSING_EVIDENCE` | Name the required source read. Do not execute the function or action. |
| `SOURCE_CHANGED` | Invalidate dependent receipts. Start a new complete read batch if no write is unresolved. |
| `INVALID_SOURCE_RESPONSE` | Record the raw response privately. Do not create complete coverage. |
| `INVALID_FUNCTION_RESULT` | Reject the result. Do not create a function receipt. |
| `CLIENT_BOUNDARY_UNAVAILABLE` | Stop before the first model call. Do not fall back to raw delivery. |
| `ACTION_UNRESOLVED` | Permit the declared status operation. Do not create another action key. |

Read transport failures may receive at most one retry. Semantic validation failures must not receive an automatic identical retry. All attempts count toward run limits. Action retries follow PRD 05.

Complete source coverage can still reveal a required missing relation or conflicting identity.
In that case, return an incomplete assessment with the declared no-action outcome.
Offer the task's incomplete-result publication operation.
Do not repeatedly read the same unchanged complete source or invent the missing fact.

### RUN-012: Preserve an auditable trajectory


The private trace records each model proposal before validation.
It records the binding kind, registered tool name, gate decision, arguments, result, accepted observation, and state transition.
For MCP calls, keep the server response reference.
For Python calls, keep the plan ID and operator trace.

The trace must preserve denied calls and transport failures. It must distinguish function execution from model selection. It must not claim to record private model reasoning.

## Acceptance criteria

1. Discovery exposes only granted MCP tools. Kernel registration adds only the checked functions from the active package.
2. A source response changed by a test fixture changes the accepted graph. Unread fixture records never appear in that graph.
3. Raw source payloads are absent from every model-visible response channel. Typed decision summaries and receipts remain visible. Declared function outputs may contain source values.
4. An empty complete response creates coverage. A failed response does not.
5. The graph remains unpublished until the complete batch is available. Publication changes facts, metadata, and revision together.
6. A Python function cannot read raw source records or call MCP tools. Its response binds results, request, and graph revision.
7. Two identical proposed calls receive different invocation identifiers. The second call cannot overlap the first call.
8. A missing gate, failed gate, or result-boundary failure prevents execution or delivery at the required boundary.
9. A stale option fails a new per-call check. It does not keep earlier authority.
10. An oversized response stops safely without partial acceptance or silent truncation.
11. The trace records both a confirmed action and a later CLI error without treating them as the same event.
12. Actual model function calls reach the Python executor. Text that resembles a function call does not execute.

## Objections and release limits

Receipt-only observations change the information available to the model. Evaluation must report this treatment difference from a raw-read baseline.

The evaluation controller may select an explicit baseline condition before a run starts. That condition may expose validated source payloads and permit ordinary read-only source queries. It has no generated function receipt. It uses the same physical grants, source-version checks, idempotency rules, and run uniqueness checks.

The baseline submits a typed model intent bound to observed sources. It receives neither a generated function nor an independent semantic oracle. PRD 06 defines this comparison. The model cannot select this condition or use it as a runtime fallback.

OWL schema checks do not establish factual truth, source completeness, or function correctness. Graph validation and held-out function tests remain required.

An existing agent is compatible only if its client supports checked dispatch, result transformation, and registered Python kernel functions.
A prompt-only integration does not satisfy this specification.

The current prototype does not meet RUN-004 through RUN-007. It must not be described as an implementation of these proposed requirements.
