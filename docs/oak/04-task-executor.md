# C4: Host task executor

Design version 0.4.8. November 2, 2026. This component is proposed. It is not implemented.

Use the [PRD](DESIGN.md), [integration contract](INTEGRATION.md), and [agent onboarding contract](08-agent-onboarding.md) with this specification.

## Purpose and ownership

C4 connects a request and its prepared graph to a replaceable ReAct working agent. The worker reads the schema and function contracts, chooses typed function calls, observes their outputs, and returns an answer. It need not write code or expose its private planner.

C3 composes and tests executable F before the worker runs. C2 builds G from the admitted corpus. C4 validates the worker's requests and dispatches the installed functions over G, then records observable execution. C4 does not construct S, repair F, or assign its own task score.

A concrete `AgentAdapter` supplies function registration, task binding, call/result transport, and trace collection. The paper profile permits task-data access only through the kernel. Other host tools and memory must not provide a bypass for that run. Exposing schema text alone does not establish this restriction.

The pseudocode below describes responsibilities. It does not require a replacement host loop or a literal `next_operation` API.

## Source requirements and design choices

The paper's executor receives q, S, G, and F. Its ReAct loop selects functions, binds typed arguments, and executes them over G. During construction, the execution trajectory records operator traces, function outputs, and final answers for evaluation. S and F remain fixed during inference. [OaK section 3.2, Step 3, and section 3.3, PDF p. 4](paper/2608.22974v1.pdf#page=4).

The primary design follows that ReAct execution path and the paper's exclusive kernel data channel. A coding agent can implement the worker interface, but code generation is not a required worker capability.

The inference worker is the agentic loop: choose an installed function and arguments, receive its result, then choose again or answer. F provides executable procedures inside that loop; it does not introduce another autonomous agent around the worker. Construction and refinement produce S/F beforehand and do not restart during held-out inference. Our runtime can implement the ReAct loop directly or connect a compatible existing worker, provided both enforce the same kernel-only interface. The paper specifies this execution behavior, not a required host framework. [OaK section 3.2, Step 3, and section 3.3, PDF p. 4](paper/2608.22974v1.pdf#page=4).

The later native-tool, ingestion, guard, and external-effect sections specify an optional live-API adaptation. That adaptation lets native search and action tools remain available alongside F and sends their observations through C2. It is deferred, changes the sole-kernel data policy, and is not the primary paper implementation. [OaK section 3.1, PDF p. 3](paper/2608.22974v1.pdf#page=3).

| Topic | Paper statement or scope limit | Proposed implementation |
| --- | --- | --- |
| Task reasoning | ReAct invokes F as tools, binds typed arguments under S, and executes over G. [Section 3.2, Step 3, final paragraph; section 3.3, PDF p. 4](paper/2608.22974v1.pdf#page=4) | Register the constructed F with a replaceable ReAct worker; dispatch its typed calls through C4 |
| Data access | The frozen kernel is the sole data channel. [Section 3.1, opening paragraph continued below Figure 1, PDF p. 3](paper/2608.22974v1.pdf#page=3) | Restrict task-data access to F over the admitted graph; reject unregistered operations |
| New query | Build Gq = Build(S*, Cq) from the query's accompanying test corpus, then execute with frozen S* and F*. [Section 3.3, opening paragraph and equations, PDF p. 4](paper/2608.22974v1.pdf#page=4) | C2 prepares Gq from Cq before C4 starts the worker with frozen S/F |
| Results | The construction trajectory collects operator traces, function outputs, and final answers for evaluation. [Section 3.2, Step 3, final sentence before Step 4, PDF p. 4](paper/2608.22974v1.pdf#page=4) | Retain these records during construction and inference; also record graph revisions, constraint outcomes, unknowns, and sources |
| Write recovery | A general external-provider write/effect recovery protocol is not specified in sections 3.1 to 3.3, PDF pp. 2 to 4. This is our reading of the scope, not an explicit paper requirement. [Reviewed sections](paper/2608.22974v1.pdf#page=2) | Only in the live-API adaptation: separate invocation status from effect status and reconcile uncertain writes |
| Checkpointing | A host checkpoint/resume contract is not specified in sections 3.1 to 3.3, PDF pp. 2 to 4. This is our reading of the scope, not an explicit paper requirement. [Reviewed sections](paper/2608.22974v1.pdf#page=2) | Use the ordering and resume rules below |

These citations use page numbers in the pinned 11-page PDF. S denotes the schema, F the function catalog, G the evidence graph, and Cq the corpus accompanying query q; an asterisk denotes a frozen artifact. The first four rows paraphrase explicit paper statements. The last two identify details not specified in the reviewed sections. The added runtime protocol, including the inference logging contract, is our design.

## Inputs and output

An `ExecuteRequest` contains the inputs below. Development trials receive a validated `CandidatePackage`. Frozen inference receives a `KernelPackage`. C4 must not combine whichever files happen to be newest.

| Input | Required content |
| --- | --- |
| Request | Case ID, user query, explicit constraints, and admitted corpus reference |
| Admitted worker binding | Verified F call/result transport, task scope, and enforcement of the kernel-only task-data channel |
| Package | Exact S/F references; operator, extraction, interpretation, tool, and runtime versions |
| Function registry | Installed F implementations and typed contracts with their permitted operator dependencies |
| Graph context | C2-prepared graph from the admitted corpus, task/evidence scope, compatible schema, and committed revision |
| Execution configuration | Actual model and thinking settings, budgets, retry limits, trace destination, allowed source scope |

The immutable `TrialRecord` contains:

- Request and package ID.
- Ordered operations, observable arguments, and results.
- Observation references, ingestion receipts, and graph revisions.
- Final output, effect receipts, and terminal state.
- Resource accounting, including failed attempts.

Hidden reasoning text is not required. C4 must not receive expected answers or private grader data.

Native callables, live ingestion capabilities, and guard bindings are additional inputs only for the explicitly selected live-API adaptation. The current scripted offer harness exercises narrower orchestration contracts; it does not implement this production ReAct worker.

Use the shared [integration envelope](INTEGRATION.md) for terminal status and invocation identifiers. Component detail states belong in `component_status`. Reject unresolved dependencies before the first model or tool operation.

## Internal procedure

The primary procedure is:

```text
Execute(request, package, prepared_graph, worker, execution_config):
    validate package dependencies, corpus scope, and prepared graph
    verify the run's task-data access is restricted to the kernel
    present q, readable S, and the typed F catalog to the worker

    while task budget remains:
        choice = worker.next_operation(observable_state)
        if choice selects an installed function from F:
            validate typed arguments and evidence prerequisites
            execute the installed function through O over the prepared graph
            record operator traces, function result, provenance, and usage
            return the result to the worker
        else if choice returns a final answer:
            retain the answer and end according to the task protocol
        else:
            return a structured unsupported-operation result

    emit TrialRecord, including failures and budget exhaustion
```

This pseudocode specifies observable responsibilities, not a required host method name. The worker chooses the next call; the runtime executes previously constructed functions. S and F are immutable throughout the trial. Independent C5 evaluation determines task success. [OaK section 3.2, Step 3; section 3.3](https://arxiv.org/html/2608.22974v1).

## Optional live-API procedure

The following is a separate, deferred adaptation. It is not a substitute for the primary procedure above.

```text
Execute(request, package, native_tools, execution_config):
    validate package dependencies and request scope
    create or resume the task context
    ingest only the request's declared initial evidence through C2
    present schema summary, native tools, and F descriptions to the host

    while task budget remains:
        choice = existing_agent.next_operation(observable_state)

        if choice selects a native tool:
            check arguments against the registered tool contract
            if guarded mode applies: require the dispatch guard's receipt
            record invocation intent and execute the existing implementation
            record invocation outcome and any external-effect evidence
            observation = create ToolObservation
            receipt = await C2.Ingest(observation, expected_graph_revision)
            expose the observation and ingestion status to the host

        else if choice selects F:
            validate typed arguments and evidence prerequisites
            bind a compatible committed graph revision
            execute the registered plan through O
            return the result, checked constraints, unknowns, and provenance

        else if choice returns an answer or claims completion:
            if a protected result in guarded mode: require finalization checks
            retain the answer and supporting effect receipts
            end according to the task protocol

        else:
            return a structured unsupported-operation result

    emit TrialRecord, including failed attempts and unresolved outcomes
```

Function selection and argument binding follow the paper. The native-tool branch and incremental ingestion are our extensions. [OaK section 3.2, Step 3; section 3.3](https://arxiv.org/html/2608.22974v1).

## Observation handoff

This handoff applies to the optional live-API procedure.

Each terminal native invocation produces a `ToolObservation`, including failed calls and calls with no usable facts. Record the call ID, tool version, request scope, and immutable response reference.

Also record observation time, supplied validity time, authoritative IDs, and known pagination or coverage metadata. A timeout observation can have no response payload.

Keep these fields separate:

```text
invocation_status = completed | failed | timed_out
effect_status = not_applicable | confirmed | rejected | unknown
effect_evidence_refs = provider receipts or later status observations
```

An invocation can time out while its effect remains unknown. C2 must preserve that uncertainty. A failed invocation is not proof that the external action failed.

C4 submits relevant content to C2. A dependent F call waits for the required `IngestReceipt`. Failed ingestion must not advance the incorporated-evidence state.

## Asynchronous ordering

These incremental-ingestion rules apply to the live-API adaptation. The primary path waits for its prepared graph before starting the worker and binds each function call to that graph.

Every F dispatch declares its required observation IDs or an equivalent recorded event watermark. Bind the call to a revision that incorporates those required observations.

If required ingestion is pending, wait within the budget or return an explicit pending result. If ingestion failed, return that failure. Do not silently evaluate an older graph as if ingestion succeeded.

Track event order with task-scoped sequence identifiers. Arrival time alone does not establish source order or incorporation. A late acknowledgment must not move the current graph pointer backward.

C2 serializes commits per context and compares expected parents atomically. C4 reschedules stale requests through the declared protocol. It never overwrites graph state.

Each F call uses one stable revision. New observations affect later calls, not an active computation.

Delegated tools supply inner evidence only when they expose it. Otherwise, retain the outer result and its visibility limit. A parent callback does not establish that hidden child operations used guards.

The [onboarding contract](08-agent-onboarding.md) defines delegate coverage, capability admission, and memory provenance.

## Function results and host decisions

An F result reports a computation outcome. It does not certify complete task success.

Results can contain candidate IDs, constraint outcomes, violations, missing evidence, stale evidence, unsupported requirements, and source references.

For example, a function can filter candidates by occupancy and minimum stay using facts already in G. The worker supplies the party size and stay length, reads the returned candidates, and chooses its next F call or answer. Missing source facts remain unknown.

In the optional live-API adaptation, `check_observed_offers` can report unknown minimum stay, after which the host selects an existing detail tool. C4 submits its observation to C2. The same function then reads the new revision. This acquisition loop is an extension; it is not the paper's accompanying-corpus inference path.

The paper's operators include graph/data procedures and an LLM slot extractor. They do not create arbitrary endpoint bindings. The native registry supplies actual endpoint implementations. [OaK Appendix B](https://arxiv.org/html/2608.22974v1).

The primary worker still interprets the query, binds arguments, selects F calls, and produces the final answer. A valid function result does not guarantee that the worker uses it correctly.

In the adaptation's `optional_functions` mode, the host can complete a task without F. Record actual function use and subsequent observable decisions. This existing mode does not establish the paper's kernel-only data boundary.

## Guarded requirements

This is an added enforcement intervention for the optional adaptation, not the paper's task-reasoning algorithm. Neither existing `optional_functions` nor `guarded_requirements` declarations alone establish a kernel-only worker.

The [workspace](06-kernel-workspace.md) can activate mandatory requirements only with explicit execution bindings. `guarded_requirements` is a separate mode from `optional_functions`.

The package pins the requirement set, execution policy, guard bindings, and checker versions.

Before each covered action or protected typed final selection, C4 runs the required checker. This occurs independently of agent-visible F calls.

A `ConstraintCheckReceipt` binds exact arguments, package/rule versions, graph revision, applicability, and evidence freshness. Changed arguments, expired evidence, or an incompatible revision invalidate the receipt.

Unknown applicability or required evidence returns `needs_evidence`. A violated rule blocks the protected operation. Exploratory reads and explanations can continue.

```text
before native dispatch or typed result release:
    identify applicable mandatory requirements under the pinned policy
    if applicability cannot be established:
        return needs_evidence
    if protected:
        check exact arguments/result against compatible current evidence
        require passed receipts for every applicable mandatory requirement
    dispatch the existing tool or release the checked typed result
```

Enumerate every protected route. An unguarded alternative prevents an enforcement claim for that scope.

Retain original tool clients behind the host hook. Do not create duplicate agent-visible APIs for ingestion. F still has no task-provider access.

A passed guard verifies declared prerequisites. External state can change later. Provider conditions and effect reconciliation remain necessary.

Normal promotion affects new runs. Immediate policy changes require a dispatch barrier and an execution-generation comparison at the actual dispatch point.

1. Suspend new covered dispatches.
2. Invalidate queued receipts from the old version.
3. Drain or reconcile already dispatched calls.
4. Resume under the new policy.

Already dispatched effects can complete. Preserve their outcomes. Use the [workspace activation protocol](06-kernel-workspace.md).

Guards and human policy editing are added interventions. They are not benefits supplied by OWL alone. [OaK sections 3.1 to 3.3 and section 5](https://arxiv.org/html/2608.22974v1).

## Effects and recovery

These external-effect rules apply when the live-API adaptation is selected.

A proposed action, successful API response, and verified task effect are different observations. Preserve provider receipts. Use supported status operations when needed. C5 still evaluates complete task success.

Before retrying a write, inspect its saved receipts. Use the provider's supported idempotency or reconciliation mechanism. If the effect remains unknown, report it. Do not retry only because the local success message is absent.

Read retries, argument corrections, and ingestion rescheduling consume C4's budget. Schema and function changes require C5 and coordinator routing.

During held-out inference, record defects for a later version. Do not repair the current package. [OaK section 3.3](https://arxiv.org/html/2608.22974v1).

## Independent verification

These are required tests, not completed results. Use the [verification protocol](INDEPENDENT-VERIFICATION.md).

Supply a saved package, request, worker binding, prepared graph, and checkpoint. Use a scripted worker and fixed F results to check call/result transport, kernel-only access, and immutable S/F. Separately use native-tool and C2 receipt stubs for the adaptation tests. These tests must not call live providers. C1, C3, and C5 do not run.

| Test input or injected fault | Expected output | Measurable pass condition |
| --- | --- | --- |
| Prepared graph, typed F call, then answer | Recorded call, installed-function result, and final answer | Exact package and graph references preserved; no worker code generation required |
| Worker requests an undeclared function or alternate task-data source | Rejected operation | Zero bypass dispatches in the primary profile |
| Worker attempts to mutate S or F | Rejection | Frozen artifact hashes unchanged |
| Missing corpus fact in the primary path | Explicit unknown or unsupported result | No invented evidence or silent native lookup |
| Native response followed by F | Observation, ingestion receipt, and bound F result | Required observations belong to the selected revision |
| Missing evidence followed by detail response | New revision and updated result | S/F hashes remain unchanged |
| Pending or failed ingestion | Pending or failed dependent call | Zero F dispatches that claim incorporation of missing evidence |
| Out-of-order ingestion acknowledgments | Monotonic current revision | No graph-pointer regression |
| Write timeout followed by resume | Reconciliation or unknown effect | Zero blind duplicate writes |
| Optional-mode host never selects F | Complete trace with zero F calls | Native completion remains possible and correctly labeled |
| Frozen package mutation or incompatible revision | Rejection | Zero dependent operations |
| Guarded action without agent-visible F | Mandatory checker invocation | No dispatch without all required passed receipts |
| Changed arguments, stale receipt, or unknown applicability | Rejection or `needs_evidence` | Zero protected dispatches |
| Alternative protected route | Guard invocation or failed admission | No unsupported enforcement claim |

C4 may write checkpoints, observations, and trial receipts. Stubs record requested effects without changing provider state.

Rows involving native observations, external writes, optional-function mode, or guards test the optional adaptation only.

Scripted replay tests orchestration. It does not prove host compatibility or live model behavior. Test the real adapter separately with its admitted capabilities.

Record model, function, operator, and Cypher operations separately. In the optional adaptation, also record native operations and applicable guard receipts. Include failed attempts. Task benefit requires the paired evaluation in the [PRD](DESIGN.md).
