# PRD 2: Test cases and ontology training

[Product documentation](../../docs/README.md) | [Current user guide](../../docs/use.md)

This document retains the detailed product requirements.
Use the current guides for setup, operation, and implementation status.

Status: Existing graph access and evidence-based repair review implemented. Controlled tests cover construction, repair, and inference. The earlier live Gemini check did not test version 3.
Date: 2026-11-09.

## 1. Purpose and scope

Improve agent reliability by making implicit task relationships explicit.

Provide a second page after [task surface discovery](01-task-surface-discovery.md).
The trainer adds test cases, runs training, and inspects task outcomes and execution traces.
Each case uses a query, selected tools, and a description of task success.
The initial demo uses semantic task success as its evaluation target.
The training loop supplies the evaluator as an internal stage.
The trainer does not select, configure, or write an evaluator for each case.

Semantic task success means that the observed result meets the intended request.
The evaluator judges the meaning of the result, rather than exact wording or one required sequence of calls.
The trainer does not supply a condition checklist, function program, graph, or expected reasoning path.
Training must identify the useful relationships and procedures from the task, examples, observations, and feedback.
The loop owns initial construction, failure diagnosis, and supported improvements to the shared kernel.

Treat the ontology as an evolving harness around a basic ReAct agent.
ReAct is the loop in which the agent selects an operation, receives an observation, and selects its next operation.
First, execute the training cases with this basic loop.
Then use those trajectories to construct the ontology harness.
Execute ReAct with the harness and improve it from task outcomes.
The basic runtime remains fixed. Training changes the task-specific definitions that the runtime executes.

This document replaces the earlier component draft for the current demo.
AppWorld, fixed domain profiles, benchmark splits, and large experiment counts are outside this scope.
The [AppWorld plan](07-implementation-plan.md) remains a separate benchmark proposal.

### Terms

| Term | Meaning |
| --- | --- |
| Trainer | The person who supplies the test cases. |
| Test case | One query, its selected tools, and a task-success description. |
| Evaluator | The internal training stage that judges semantic task success from the request and observed outcome. |
| Episode | One actual agent execution of a test case. |
| Kernel | The shared schema, source mappings, and typed functions for the agent's task surface. |
| Ontology harness | The task-specific execution layer that uses the kernel and working graph to guide the ReAct agent. |
| Working graph | The observed entities, properties, and relations available during one episode. |
| Trajectory | The ordered record of calls, observations, graph changes, function execution, and final output. |
| Defect | A diagnosed schema, mapping, relation, or function error that contributes to incorrect task behavior. |

Training changes the kernel. It does not update model weights.
Graph updates record new evidence during execution.
Kernel repairs change reusable definitions between episodes.
The harness develops during training. Inference uses its accepted fixed kernel with a graph that grows from observations.

## 2. Second page

**TRN-001.** Provide three sections on the agent's Training page.

| Section | Controls and information |
| --- | --- |
| Test cases | Add, edit, and remove cases. Select tools. Enter task-success descriptions. |
| Training | Show the discovery version and run limits. Start or stop a run. Identify basic ReAct or ReAct with the harness. |
| Results | Show one task-success outcome per episode. Expand a result to inspect its trace, evaluation, diagnosis, and repair. |

Show schema and function versions as expandable records.
Identify the harness version for each episode that uses one.
Show the initial basic ReAct results beside the results from ReAct with the harness.
Keep repair details beside the related failed result.
Do not require a separate repair dashboard or a condition-by-condition results table.

**TRN-002.** Preserve saved cases, run records, traces, and candidate versions after a page reload.
Opening or editing the page must not dispatch a model or tool call.
Start training begins actual execution within the saved task boundaries and run limits.
Stop prevents further dispatch. It does not promise to undo an external action.

## 3. Test case inputs

**TRN-003.** Save these inputs for each case.

| Input | Requirement |
| --- | --- |
| Query | A task instruction. It can require information, an external action, or both. |
| Selected tools | A subset of the agent's granted Model Context Protocol (MCP) tools. |
| Task success | A short description of the intended outcome in ordinary language. |

Assign each case a stable identifier.
The trainer is responsible for correct queries, tool selections, and success descriptions.
The task surface can contain many tools. A case can select only the few tools that it needs.
The selected tools define available sources and operations. Actual responses supply observed data.
The original task and boundaries remain authoritative.
Cases and repairs cannot override them.

Do not require the trainer to list every implicit condition.
Do not require reference answers or a prescribed trajectory for every case.
If evaluation uses private reference data, keep that data outside the agent's observations.

### Example case

| Input | Example |
| --- | --- |
| Query | Book suitable accommodation for three people for two nights. Report the booking result. |
| Selected tools | Search accommodation, inspect an offer, create a booking, and inspect a booking. |
| Task success | The requested stay is booked for the party. The reported booking details and status match the actual outcome. |

The example does not supply occupancy predicates or minimum-stay code.
The agent must obtain relevant offer policies through its selected tools.
Training can expose missing relationships between those policies and the requested stay.
A later case can test a different party size or stay length without supplying a new procedure.
These tool names are illustrative. They do not define a required domain or provider.

## 4. Start and run training

**TRN-004.** Keep the discovery requirement and schema proposals, `R_0` and `S_0`, as construction inputs.
Keep their evidence and unresolved gaps.
Discovery does not need training cases to be complete before it can produce these proposals.
The first training executions use basic ReAct with the saved task and selected tools.
Do not require a completed schema or generated functions before these executions.
Use discovery and the resulting trajectories to construct the first ontology harness.

**TRN-005.** Fix the run inputs before the first episode.
Record the task, discovery version, grants, case inputs, model configuration, and operator version.
The system also records its internal evaluator version. This is not a case input.
Record limits for model cost, calls, active time, and repair rounds.
Reject an unavailable selected tool before dispatch.
Changed inputs require a new recorded run.

**TRN-006.** Execute all cases saved at the start of the run with one agent.
Use the same MCP call interface for all selected tools.
Validate tool arguments against the declared input schema.
A recorded host probe or direct Python test does not count as a native agent episode.

Use this sequence:

1. Execute every saved case through basic ReAct.
2. Save its trajectory and internal semantic task-success evaluation.
3. Reuse a compatible accepted candidate, or construct the minimum initial harness from discovery and baseline evidence.
4. Validate typed declarations, formal schema consistency, requirement coverage, and fixed negative cases.
5. Execute every saved case through ReAct with that harness.
6. Save its trajectory and evaluate task success with the same evaluator.
7. Review failed outcomes, existing routes, and definition evidence before requesting a change.
8. Apply supported changes to the affected harness definitions.
9. Validate the new version through ReAct with the harness on all saved cases.
10. Accept the new version or retain the previous one.

Repeat harness evaluation and improvement until all cases pass or a run limit stops training.
If no supported change can resolve the remaining problem, stop with its evidence and reason.
Success in the basic ReAct run does not skip harness construction or validation.
Keep task inputs, selected tools, model settings, evaluator, and episode limits consistent when comparing the two modes.

Keep each candidate fixed during an episode.
Keep successful routes as execution evidence.
Do not convert them into saved functions automatically.
A failed episode supplies evidence for diagnosis, but does not by itself authorize repair.
The trainer does not choose the artifact to change or write the repair.
Each completed round must account for every saved case.
Do not omit failed cases or substitute an unreported subset.
Run limits can end training before success.
Preserve incomplete runs, failures, costs, and the stop reason.
A passing case does not require a repair.

## 5. Graph-guided execution

The basic ReAct run records actual tool observations without requiring a generated ontology harness.
The requirements below govern execution after the harness is attached.
The harness organizes observations into graph evidence and supplies typed functions for reasoning over that evidence.
Function results and missing dependencies guide the agent's next operation.
The runtime enforces the declared executable prerequisites and the original tool grants.

**TRN-007.** Start each episode that uses the harness with an empty or partial working graph.
Do not require a complete source graph or an enumeration of every possible action.
Obtain evidence as the agent deals with the query.

Use this execution loop:

`current graph -> next function or tool call -> actual observation -> graph update -> next decision`

The project adopts the nine public capabilities from paper Appendix B.
The [operator rationale](../../docs/system.md#why-the-nine-operator-capabilities-matter) explains their purpose, expected benefits, and runtime mapping.
The count describes the paper's public library.
The current implementation uses request preparation and eleven plan-step types to provide these capabilities and operation checks.

Typed functions compose the supported graph operators.
These operators include entity lookup, relation traversal, property projection, filtering, and aggregation.
Version 3 adds typed collections, decimals, categorical sets, set overlap, connectivity filtering, fuzzy lookup, and grouped averages.
Construction emits `oak.candidate.v3`. The runtime supplies the operator meanings and execution limits.
The original evaluator remains fixed.
The runtime supplies their implementations.
Training can change their composition in a function. It cannot change the operators' behavior.

**TRN-008.** Execute graph functions against a fixed revision of the working graph.
Return typed results, evidence references, and any missing dependencies.
Use these results to guide the next permitted call.
A missing required fact can lead to further evidence acquisition.
Missing information in an unrelated part of the graph must not block a function that has sufficient evidence.

Make sure that the evidence covers the scope that a computation needs.
For example, a minimum over all relevant candidates requires evidence that supports that scope.
Absence from the working graph does not establish absence from the source.
An incomplete result must remain distinct from a complete empty result.

**TRN-009.** Add relevant facts from actual tool responses to the working graph.
Use one result-processing path for tools that read data and tools that change data.
Record the execution and returned information from both kinds of call.
A successful write can immediately supply graph facts that later functions use.
Do not require a separate read before using information that the write response already supplies.
Keep the original response as evidence.
Connect each accepted fact to its source invocation.
Use declared identities to update an existing entity.
Preserve the evidence for earlier states.

A booking response can add its identifier, selected offer, price, and observed status.
A later response can update that same booking from pending to confirmed.
A successful tool invocation does not by itself prove that the requested booking succeeded.
An unknown action outcome must not cause an automatic repeat of the action.

New graph evidence can make a previous function result outdated.
Validate its evidence dependencies before using that result for another decision.
The host controls graph revisions. An agent-written claim cannot publish an observed fact.

## 6. Trajectories

**TRN-010.** Save structured execution events in order.
Each event identifies the run, case, episode, candidate version, event type, time, and sequence number.
Label each episode as basic ReAct or ReAct with the ontology harness.
Record the candidate version only when an episode uses a harness.
Use invocation identifiers to connect proposals, dispatches, and results.

| Event | Required evidence |
| --- | --- |
| Tool call | Tool identifier, proposed and dispatched arguments, actual response or error, and observed completion status. |
| Graph update | Previous and new revisions, changed entities or relations, source references, and mapping version. |
| Function execution | Function version, typed arguments, graph revision, operator trace, result, and missing dependencies. |
| Agent observation | The exact content delivered to the agent after a call or function execution. |
| Episode end | Final output, execution status, stop reason, and unresolved external outcomes. |
| Evaluation | Evaluator version, task-success result, short reason, and supporting evidence references. |
| Repair | Diagnosis, artifact changes, previous version, replay results, and acceptance decision. |

Record denied calls and errors.
Keep model proposals separate from actual execution.
Keep generated explanations separate from observed evidence.
Do not request private model thoughts.
The trajectory shows observable decisions and program execution.

## 7. Semantic task-success evaluation

**TRN-011.** Produce one overall task-success result for each episode.
Use the semantic evaluator supplied by the training runtime.
Use the query, task-success description, actual trajectory, and available outcome evidence.
Supply the original task and boundaries to the evaluator.
Evaluate the answer, external outcome, or both, as the query requires.
A semantic evaluator can use model judgment. The agent must not score its own result.
The evaluator can inspect function results and traces.
It must judge task success independently of the learned function implementation.
A function result is not its own proof of correctness.

| Result | Meaning |
| --- | --- |
| Passed | Available evidence supports that the task succeeded. |
| Failed | Available evidence shows that the task did not meet the intended outcome. |
| Inconclusive | The evaluator lacks evidence to determine task success. |
| Error | Evaluation could not complete because of an evaluator or infrastructure error. |

Return a short reason and supporting evidence references.
Accept different valid answers and execution paths.
Do not require exact wording, an expected call sequence, or manual condition labels.
Do not substitute tool-call success for task success.
An evaluator failure or an unknown external outcome cannot become a task pass.

**TRN-012.** Keep the internal evaluator and task-success description fixed during a run.
A repair cannot change either one to improve its score.
Private reference data can support evaluation but cannot supply graph facts to the agent.
Record the evaluator's uncertainty when the available evidence is insufficient.

Semantic evaluation does not replace generic type, grant, and version checks.
Those checks protect execution integrity.
The evaluator determines whether the intended task succeeded.
An evaluator pass does not prove that every possible implicit condition was checked.

## 8. Reuse, diagnosis, and targeted repairs

Start from the latest structurally compatible accepted candidate for the same agent and task-input digest.
Copy it into the new run as a provisional candidate.
Validate it under the current runtime before acceptance.
If no compatible candidate exists, construct the minimum schema, mappings, source bindings, and required operation checks.
Use discovery and actual baseline evidence.
Do not generate a helper function merely because a baseline trajectory succeeded.

Process every saved case against the candidate before proposing an addition for that case.
Keep successful routes as execution evidence.
Apply the same review requirement to later construction revisions and repair patches.
An empty change set is valid.
Keep definitions fixed during inference.
New observations change only the working graph.

**TRN-013.** Save a `RepairReview` before requesting a patch.
Record the candidate digest, failure evidence, definitions examined, routes tested, proposed cause, and decision.
Check deterministic validation failures before model diagnosis.
Keep failed, inconclusive, and evaluator-error outcomes separate.

| Decision | Required behavior |
| --- | --- |
| Existing route available | Record the route. Keep definitions unchanged. |
| Missing evidence or tool failure | Record the unresolved dependency. Do not change the harness on this basis. |
| Agent-use problem | Record the available capability and observed misuse. Keep definitions unchanged. |
| Verified definition defect | Permit a targeted correction. |
| Supported missing definition | Permit the smallest necessary addition. |
| Cause unresolved | Record uncertainty. Do not request a patch. |

Diagnosis can inspect saved evidence and test existing graph routes.
It cannot make external calls or repeat unresolved actions.
For a defect, reproduce the result with recorded inputs and source expectations.
Run the correction against the same inputs.
The existing requirement and all acceptance checks must still pass.
For an addition, identify a concrete missing element, supporting source evidence, and examined alternatives.
A search limit or unsuccessful route does not establish absence.
A missing function name alone does not authorize a new data function.
The model explanation remains a proposed cause.
The runtime verifies references, candidate versions, replay results, and permitted edits.

**TRN-014.** Apply one targeted change after a supported review.
One verified gap is sufficient.
Reject changes outside the reviewed targets.
Reject an exact duplicate under a new ID after normalization.
Reject persistent sample constants unless the original task or tool contract fixes them.
Record the source for each permitted new constant.
Use parameters for other sample values.
Require a fixed coverage-evaluator decision for each exact constant use.
Check the whole source requirement, including negation, scope, units, and the proposed use.
A matching word or number does not establish that the contract fixes the value.
Reject acceptance if a decision is missing, duplicated, unsupported, or requires a parameter.
Validate each supporting reference against the original task or native tool contract.

Record rejected proposals and their evidence digest.
Block identical proposals against unchanged definitions and evidence.
Keep candidate snapshots, patches, discovery artifacts, and training events as the source of truth.
The definition catalog and change history are views of these records.
Do not add a registry database.

**TRN-015.** Validate the corrected replay, then run all saved cases before acceptance.
Preserve successful simple cases.
A difficult case cannot compensate for a regression.
Require comparable prepared state before repeated external execution.
Stop when an external outcome is unresolved.
If no supported change remains, finish with an explicit unresolved result.
Do not create a patch to consume a remaining round.

### Graph access

Expose saved data functions through `run_function(function_id, arguments_json)`.
Keep stored function IDs unchanged.
Expose `query_graph(query_json)` as a fixed, read-only tool.
Validate each temporary plan against `GraphQuery` on the server.
Reuse the existing typed plan grammar and execution engine.
Permit data operations only.
Exclude action dispatch and permission decisions.

A request does not need a dedicated function.
It can use a saved function, a graph query, or both.
A graph query can use a previous function result as an argument.
Preserve arguments fixed by the original request.
Keep separate argument bindings for later calls to the same function.
Do not make the first call's record identifier a permanent request constraint.
The query does not enter the function library or change the candidate digest.
Keep the four-hop limit for each traversal and all other execution limits.
Preserve evidence scope, missing-data status, completeness, units, and result references.

Derive acquisition needs from validated graph queries and saved functions.
Retain tool grants, argument validation, source-access rules, and operation checks for every external call.
Permit a repeated valid data read to refresh existing evidence within the same run limits.
Completeness does not establish freshness.
Let task requirements and source contracts determine when a refresh is necessary.
Do not introduce a universal expiry time.
Start a paged refresh at its declared initial cursor after the previous sequence completes.
Keep the new page population separate from earlier observations.
Do not retry an external action with an unknown outcome.
Put the catalog and query schema in `harness_catalog` in the existing evidence store.
Provide a short index in model context.
Use `read_evidence` for complete definitions.

### Records and compatibility

Show **Definition catalog** and **Change history** in Training results.
Show versions, dependencies, supporting evidence, use, reviews, tested routes, changes, validation, and rejection reasons.
Use links to the saved evidence.
Label historical runs that lack a repair review.

Keep existing REST endpoints and `oak.candidate.v3`.
Use `oak.repair-review.v1` and `oak.graph-route.v1` event records.
Use `oak.dispatcher.v5`, `oak.request.v5`, and `oak.graph-access.v1` runtime compatibility versions.
Historical candidates remain inspectable.
They require validation under the new runtime before inference.
No database migration is required.

## 9. Accepted output and inference

**TRN-016.** Accept a kernel for demo inference only after the supplied cases pass through the actual agent runner.
These acceptance episodes must run ReAct with the candidate harness.
The initial basic ReAct results cannot substitute for this evidence.
Require valid typed artifacts and execution evidence for the functions exposed to inference.
Require a successful actual execution for every enabled operation binding.
Require HermiT verification and passing fixed validation cases before acceptance.
Local replay tests or supplied report fixtures do not establish native training success.
Save the accepted kernel version with its cases, trajectories, internal evaluator version, and results.

Use the fixed kernel on a new query with fresh observations.
The working graph can grow during inference.
The schema, mappings, request fields, conditions, functions, and operation bindings remain fixed.
Prepare the original request before tool execution. Preserve its constraints separately from proposed arguments.
Run each operation's bound checks through `KernelDispatcher`, including checks that the model does not call.
Use only tools that are granted, selected for the run, and bound in the accepted kernel.
Record an unsupported new condition instead of silently editing the kernel.

Task success on the training set does not establish general reliability.
Use a new query to demonstrate reuse.
Do not describe one new query as a benchmark result.

## 10. Implementation status and limits

The current local modules provide typed plans, bounded execution, versioned patches, and repair decisions:

- [Typed declarations](../../backend/oak/repair_schemas.py).
- [Patch validation](../../backend/oak/repair_patch.py).
- [Local executor](../../backend/oak/repair_executor.py).
- [Version 2 executor](../../backend/oak/kernel_execution.py).
- [Mandatory dispatcher](../../backend/oak/kernel_dispatcher.py).
- [Formal verification](../../backend/oak/ontology_verification.py).
- [Shared inference eligibility](../../backend/oak/kernel_acceptance.py).
- [Repair decisions](../../backend/oak/repair_workflow.py).

The [training manager](../../backend/oak/training.py) stores cases, runs, episodes, candidates, and events in Postgres.
The [native runner](../../backend/oak/training_runner.py) executes both the baseline and the fixed harness.
The [evidence graph](../../backend/oak/evidence_graph.py) accepts observed facts from read and write responses.
It supports repeated observations, object results, partial properties, and property-level evidence references.
The [constructor](../../backend/oak/training_construction.py) builds a typed candidate from discovery and actual episodes.
The [evaluator](../../backend/oak/training_evaluation.py) returns one semantic task-success result for each case.
Case setup has no evaluator selector or condition checklist.

The Training page supports case entry, limits, Start, Stop, saved results, and candidate changes.
The Inference page supports new queries, tool selection, run limits, and saved inference runs.
It displays accepted entity types, declared relations, and observed-record counts during execution.
Select an entity or activity to inspect its values and source observations.
The page restores state from saved graph events. The completed graph supplies the final state.
Saved inference runs display their pinned candidate, even after another candidate is accepted.
The application saves full native traces. Construction and evaluation receive execution evidence without repeated provider-message history.
Inference pins the accepted candidate identifier and uses a fresh graph.
Inference does not change declarations or invoke the training evaluator.

The version 2 and version 3 patch language preserves original requirements and their operation coverage.
It permits supported corrections to generated conditions. Fixed validation expectations cannot change.
A construction repair can cite a saved validation report before a harness episode exists.
Repair receives one focused brief for the selected failed case or validation report.
The brief follows saved invocation IDs, observation IDs, and evidence references.
It includes the affected declarations and preserves evidence context and coverage.
The evaluator can cite an existing field or array item below a supplied evidence reference.
Repair can request additional saved evidence at most twice through `evidence_requests`.
These requests cannot execute MCP tools. All model calls use the existing run budget.
Large records remain available by reference. An omitted record cannot establish absence.
The complete candidate and episode records remain in host storage.
Unsupported repairs remain explicit. An invalid initial construction does not replace an accepted version.
Initial construction permits one correction attempt with exact validation errors and the rejected proposal.
The correction remains subject to the original requirements, tool grants, typed schema, and static checks.
The graph labels local rows as observed evidence. Global aggregates require complete source evidence.
Graph facts include their request-dependent scope. Replacement responses invalidate omitted mapped properties.
Only a validated source contract can establish collection completeness or partial update semantics.
Graph updates are atomic. A failed graph update preserves the external outcome and stops dependent execution.
An unknown operation outcome stops the episode. The application does not retry that operation automatically.
Repeated training requires a server preparation adapter or an explicit assertion of comparable state.
These mechanisms do not establish reliability gains on an external benchmark.

The earlier live check used two saved note cases with a controlled MCP server and prepared discovery inputs.
Gemini executed both baseline cases and constructed the typed harness from their actual results.
Both harness cases passed. Each used the generated `get_note_by_title` function.
A new inference query created `note-3` and used the same accepted function.
The write response supplied graph facts directly. The inference episode used one external call and no readback.
Controlled integration tests also cover targeted repair and a graph-derived identifier used in a later external call.
The version 2 controlled test rejects an invalid proposal, executes a valid proposal, and uses its returned facts.
A second query uses the same accepted candidate digest.
The container resource check exceeded the verifier deadline under AMD64 emulation on an ARM64 host.
Keep deployment blocked until the complete service passes on native AMD64 at 512 MiB and 0.1 CPU.

## 11. Acceptance checks

| Check | Required result |
| --- | --- |
| Simple case entry | Save several queries with selected tools and a task-success description. No evaluator setup or condition checklist is required. |
| All saved cases | Each completed round includes every case saved at run start. The loop records incomplete rounds and never hides failures. |
| Basic ReAct start | Run every saved case before a generated harness exists. Preserve its actual trajectory and task-success evaluation. |
| Automatic construction | Discovery and case evidence produce the shared schema, mappings, and functions. The trainer does not supply a finished solution. |
| Harness execution | ReAct uses the generated graph functions and their evidence during later episodes. Storing ontology text alone does not satisfy this check. |
| Tool access | Each episode can call only its case's selected tools. Different cases can select different subsets. |
| Native execution | Start runs the actual agent. The saved trace contains actual calls, responses, function results, and final output. |
| Incremental graph | The graph grows from observations. A later decision uses a fact returned by an earlier action. |
| Write-result evidence | A successful write supplies an identifier and status. Both enter the graph and support a later operation. |
| Scoped evidence | A function can execute with sufficient local evidence. Missing relevant evidence produces an explicit incomplete result. |
| Semantic success | Different valid answers or call sequences can pass. A claimed action without outcome evidence cannot pass. |
| Diagnosis and repair | A recorded failure leads to a supported artifact change. The target case passes and earlier task passes remain passes. |
| Unknown outcome | An unresolved action remains visible. The runner does not repeat it automatically or label the task successful. |
| Repeat preparation | If a comparable prepared state is unavailable, the repeated episode dispatches no calls. Record the reason without assigning task success or failure. |
| Durable inspection | Reload shows the same cases, traces, evaluations, candidate versions, and repair decisions. |
| Fixed inference | A new query uses the accepted kernel with fresh graph evidence. Kernel hashes remain unchanged. |

## 12. Paper basis and project choices

The [paper, Sections 3.2 and 3.3](../../docs/paper/source/oak-2608.22974v1.pdf), constructs a schema, graph, and typed functions.
It runs training examples, scores answers, and uses judge feedback for repairs.
It samples training examples per round and freezes the kernel for inference.
Its graph construction uses the accompanying corpora.
It also checks an ontology representation with HermiT.

This demo uses trainer-supplied cases and semantic task success.
It starts with basic ReAct executions and constructs an evolving ontology harness from their evidence and the discovery proposals.
It adds MCP integration, incremental graph updates from tool observations, and version-checked repairs.
The first demo evaluates all saved training cases through its internal semantic evaluator.
These choices adapt the paper. They are not claims about its exact implementation.
The fixed encoder translates supported schema declarations into OWL for HermiT verification.
OWL is the Web Ontology Language. Verification requires global consistency and satisfiable declared classes.
The runtime does not use inferred individuals as observed evidence.
Formal checks, requirement coverage, and negative cases provide bounded evidence of correctness.
They do not prove that all natural-language constraints were captured.

## 13. Implementation plan from HarnessX

Reference: [Darwin-Agent/HarnessX](https://github.com/Darwin-Agent/HarnessX/tree/ccb411691343d06b4a5c44c4e11104d694318e8f).
Reviewed commit: `ccb411691343d06b4a5c44c4e11104d694318e8f`, dated November 3, 2026.
The review used the execution, MCP, trajectory, evaluation, and evolution source files.
This section records the implementation reference. Version 2 adds mandatory ontology checks to its execution pattern.

### Adopted execution strategy

HarnessX separates the agent loop from processors attached to execution hooks.
Its runtime dispatches a tool, processes its result, and adds a correlated tool message to the next model context.
Its evolution recipe runs the task set, saves trajectories, proposes a new configuration, and evaluates another round.
These are the relevant patterns for Oak.

Implement the following hooks as fixed functions in Oak's episode runner.

| Hook | Oak responsibility |
| --- | --- |
| Before model | Assemble the query, conversation, available tools, and current graph context. Save the exact dispatched model input. |
| Before tool | Validate access, arguments, and limits. Execute the accepted checks on the fixed request and graph. Save the exact decision. Dispatch only an allowed call. |
| After tool | Save the external outcome. Validate its response. Publish graph facts atomically. Save the correlated observation. |
| Episode end | Save the final output and unresolved outcomes. Run the internal semantic task-success evaluation. |

Use this path for every MCP tool:

`proposal -> fixed kernel checks -> saved decision -> allowed call -> saved external outcome -> atomic graph update -> correlated observation`

The basic ReAct run saves responses without requiring graph construction.
ReAct with the harness adds graph processing to that same path.
A tool's read or write label must not select a different observation workflow.
Store both the invocation outcome and the task facts that its response supports.
If a result already establishes a booking status, use that evidence directly.
Further calls obtain information that the task still needs.

The execution record and source response remain available when extraction cannot represent a field yet.
Record that mapping gap for construction or repair.
Do not repeat the source action merely to obtain its already saved response.

### Implementation order

| Step | Work and code location | Completion evidence |
| --- | --- | --- |
| 1. Cases and saved runs | Add the next database migration, `training_schemas.py`, and `training.py`. Register routes in `main.py`. Save only query, selected tools, and task success as editable case inputs. | Multiple cases survive reload. Start copies every case and its tool selection into an immutable run record. |
| 2. Native ReAct and one tool-result path | Add `training_runner.py`. Add a separate native function-call turn method to `model_client.py`. Reuse `Connections.session()` from `mcp_client.py`. Save dispatch, response, and delivered observation separately. | Every saved case executes through actual model tool calls. A write result can supply arguments for the next call. |
| 3. Internal semantic evaluation | Add `training_evaluation.py`. Use the existing structured model client for one overall result, reason, and evidence references per episode. | Baseline results cover all saved cases. A completion claim without outcome evidence cannot pass. No evaluator setup appears in the case form. |
| 4. Ontology construction and incremental graph | Add `training_construction.py` and `evidence_graph.py`. Construct the first schema, mappings, and functions from discovery and baseline traces. Adapt `repair_executor.py` to read graph revisions. | Read and write responses enter the same graph. Functions use source references and report missing dependencies within their required scope. |
| 5. Evolution rounds and accepted versions | Connect construction to the existing repair modules. Add an internal case-level task-success adapter. Save candidate versions and decisions. | Each changed candidate runs all saved cases. The target failure is corrected, earlier task passes remain passes, and rejected changes do not replace the accepted version. |
| 6. Complete the Training page and inference check | Add `frontend/src/features/training/`. Connect case entry, runs, episode detail, candidate inspection, and Try accepted version to saved backend records. | The user can inspect a write, its graph facts, the later reasoning that uses them, and the task result. A new query uses the accepted kernel unchanged. |

The new Python modules belong in `backend/oak/`.
Use the current database, authentication, credential storage, and model configuration.
Keep model and operator implementations fixed while the ontology declarations evolve.
Use supported declaration patches for changes to an existing harness.
The initial constructor can create missing definitions before a repair session exists.

### Integration details

The current `GeminiClient.generate()` accepts structured output and rejects model function calls.
Keep it for construction, evaluation, and diagnosis.
The native turn method must preserve provider call identifiers and the conversation parts needed for subsequent turns.
Record the final request after context transformations.

The current discovery probe controller contains separate read and write rules.
Reuse its connection and credential components for training.
Implement the shared dispatch and observation path in the new episode runner.
Keep discovery behavior unchanged while this training path is added.

The current repair executor permits one observation per mapped tool.
Replace that restriction with an episode graph that can combine successive observations by declared entity identity.
Require only the facts and coverage needed by the selected function.
Retain the current deterministic operators and patch checks where their contracts still apply.

Store baseline episodes before creating a `RepairSession`, which currently requires a candidate.
Use one internal task-success check per case when adapting the existing repair decision interface.
Construction and evidence-based improvement need an explicit path beyond the current failed-target repair entry point.
Preserve the accepted candidate digest as the base for every subsequent change.
An unchanged candidate is a valid outcome when the review finds no supported improvement.

Use agent-scoped routes under `/api/tasks/{task_id}/agents/{agent_id}/training`.
Provide cases, runs, explicit stop, episode details, candidate inspection, and events after a cursor.
Start returns promptly while the saved run continues on the backend.
GET requests inspect saved state and never dispatch model or MCP calls.
Interrupted dispatch remains recorded. Restart must not repeat it automatically.

Add `agentPage=training` to the existing workspace navigation.
Reuse `FormDialog` and the controlled selection interface in `ToolCatalog`.
Fix the API proxy to preserve query parameters for event cursors.
Regenerate OpenAPI and frontend API types after route changes.

### First complete demonstration

Use a controlled MCP environment with a task that creates a booking and then uses the returned information.
Keep the application logic independent of these example tool names.

1. Execute `create_booking` through the shared dispatcher.
2. Save its actual response, such as `booking_id=B42`, `status=confirmed`, and the returned price.
3. Add the execution record and supported booking facts to the graph.
4. Execute a generated graph function that selects B42 for the next task step.
5. Use B42 in a subsequent permitted call, such as adding the requested booking note.
6. Add that call's returned information through the same result-processing path.
7. Evaluate the requested task outcome from the saved evidence.
8. Inspect the calls, graph changes, function execution, and semantic result on the Training page.

Also exercise a source result that reports pending status or an unresolved outcome.
The graph must preserve the observed status.
Do not require an extra read solely because the previous tool changed data.
Use comparable prepared environments for baseline and harness repetitions.

### Verification and reference limits

Use controlled integration tests for call correlation, graph updates, persistent traces, and interruption behavior.
Use browser tests for case entry, Start, Stop, reload, result inspection, and inference with the accepted version.
Keep those tests distinct from a budgeted native model demonstration.
Report baseline and harness task results separately.

HarnessX's diagnostic judge does not grade task correctness.
Its synthetic replay establishes runtime startup, not successful execution of the saved cases.
Oak must evaluate actual task outcomes and preserve individual case passes.
Its MCP adapter also transforms response content before delivery.
Oak must retain the complete permitted response separately, including structured content, before producing the agent's observation.

Verified source references:

- [Run-loop dispatch and result delivery](https://github.com/Darwin-Agent/HarnessX/blob/ccb411691343d06b4a5c44c4e11104d694318e8f/harnessx/core/runloop.py#L505-L599).
- [MCP result processing](https://github.com/Darwin-Agent/HarnessX/blob/ccb411691343d06b4a5c44c4e11104d694318e8f/harnessx/tools/mcp.py#L285-L342).
- [Structured trajectories](https://github.com/Darwin-Agent/HarnessX/blob/ccb411691343d06b4a5c44c4e11104d694318e8f/docs/concepts/trajectory.md).
- [Evolution recipe](https://github.com/Darwin-Agent/HarnessX/blob/ccb411691343d06b4a5c44c4e11104d694318e8f/recipe/gaia_evolver/README.md).
- [Diagnostic judge contract](https://github.com/Darwin-Agent/HarnessX/blob/ccb411691343d06b4a5c44c4e11104d694318e8f/harnessx/processors/evaluation/llm_judge.py#L154-L156).
- [Synthetic replay scope](https://github.com/Darwin-Agent/HarnessX/blob/ccb411691343d06b4a5c44c4e11104d694318e8f/harnessx/meta_harness/replay.py#L208-L229).
- [MCP publishing example with reusable action results](https://github.com/Darwin-Agent/HarnessX/blob/ccb411691343d06b4a5c44c4e11104d694318e8f/examples/deed_page/publish.py#L30-L50).
