# C4: Host task executor

Design version 0.3.0. November 2, 2026. This component is proposed. It is not implemented.

Use the [PRD](../OAK-PRD.md), [integration contract](INTEGRATION.md), and [agent onboarding contract](08-agent-onboarding.md) with this specification.

## Purpose and ownership

C4 connects a request to the host agent. The host already owns its tools, skills, instructions, memory, and model loop.

The host selects and executes operations. C4 integrates their observations, waits for required ingestion, and records observable execution. C4 does not construct S, repair F, or assign its own task score.

A concrete `AgentAdapter` supplies registration, task binding, callbacks, trace collection, and supported guards. Version the added kernel context. Preserve the host's original instructions and memory.

The pseudocode below describes responsibilities. It does not require a replacement host loop or a literal `next_operation` API.

## Source requirements and design choices

The paper's executor receives q, S, G, and F. Its ReAct loop selects functions, binds typed arguments, and executes them over G. It records operator traces, results, and final answers. S and F remain fixed during inference. [OaK section 3.2, Step 3, and section 3.3](https://arxiv.org/html/2608.22974v1).

Our pilot keeps native search and action tools alongside F. Native tools access external task systems. F computes over the observed graph. C4 submits native observations to C2.

This changes the paper's sole-kernel data policy. It is a declared adaptation, not an exact reproduction. [OaK section 3.1](https://arxiv.org/html/2608.22974v1).

| Topic | Paper requirement | Proposed implementation |
| --- | --- | --- |
| Task reasoning | ReAct selects typed functions over G | Retain the host loop and register F as tools |
| Data access | The fixed kernel is the sole data channel | Keep native tools and ingest their observed results |
| New query | Build Gq from Cq and run fixed S/F | Start with declared initial evidence and add observations |
| Results | Record function results and operator traces | Also record graph revisions, constraint outcomes, unknowns, and sources |
| Write recovery | No general provider-effect protocol in sections 3.1 to 3.3 | Separate invocation status from effect status; reconcile uncertain writes |
| Checkpointing | No concrete host checkpoint contract in those sections | Use the ordering and resume rules below |

The first four source requirements come from [OaK sections 3.1 to 3.3](https://arxiv.org/html/2608.22974v1). The added runtime protocol is our design.

## Inputs and output

An `ExecuteRequest` contains the inputs below. Development trials receive a validated `CandidatePackage`. Frozen inference receives a `KernelPackage`. C4 must not combine whichever files happen to be newest.

| Input | Required content |
| --- | --- |
| Request | Case ID, user request, explicit constraints, declared initial evidence |
| Admitted host binding | Verified capabilities, native callables, task scope, nested visibility limits, integration mode |
| Package | Exact S/F references; operator, extraction, interpretation, tool, and runtime versions |
| Native tool registry | Real implementations and registered contracts; credentials stay in the host |
| Graph context | Task/evidence scope, compatible schema, last committed revision |
| Execution configuration | Actual model and thinking settings, budgets, retry limits, trace destination, allowed source scope |

The immutable `TrialRecord` contains:

- Request and package ID.
- Ordered operations, observable arguments, and results.
- Observation references, ingestion receipts, and graph revisions.
- Final output, effect receipts, and terminal state.
- Resource accounting, including failed attempts.

Hidden reasoning text is not required. C4 must not receive expected answers or private grader data.

Use the shared [integration envelope](INTEGRATION.md) for terminal status and invocation identifiers. Component detail states belong in `component_status`. Reject unresolved dependencies before the first model or tool operation.

## Internal procedure

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

For example, `check_observed_offers` can confirm capacity but report unknown minimum stay. The host selects an existing detail tool. C4 submits its observation to C2. The same function then reads the new revision. S and F stay fixed.

The paper's operators include graph/data procedures and an LLM slot extractor. They do not create arbitrary endpoint bindings. The native registry supplies actual endpoint implementations. [OaK Appendix B](https://arxiv.org/html/2608.22974v1).

The host still selects observations, tools, and permitted actions. It also resolves missing user constraints.

In `optional_functions` mode, the host can complete a task without F. Record actual function use and subsequent observable decisions. Do not attribute every success to the ontology.

## Guarded requirements

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

A proposed action, successful API response, and verified task effect are different observations. Preserve provider receipts. Use supported status operations when needed. C5 still evaluates complete task success.

Before retrying a write, inspect its saved receipts. Use the provider's supported idempotency or reconciliation mechanism. If the effect remains unknown, report it. Do not retry only because the local success message is absent.

Read retries, argument corrections, and ingestion rescheduling consume C4's budget. Schema and function changes require C5 and coordinator routing.

During held-out inference, record defects for a later version. Do not repair the current package. [OaK section 3.3](https://arxiv.org/html/2608.22974v1).

## Independent verification

These are required tests, not completed results. Use the [verification protocol](INDEPENDENT-VERIFICATION.md).

Supply a saved package, request, host binding, and checkpoint. Use a scripted host, native-tool stubs, C2 receipt stubs, and fixed F results. The test must not call live providers. C1, C3, and C5 do not run.

| Test input or injected fault | Expected output | Measurable pass condition |
| --- | --- | --- |
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

Scripted replay tests orchestration. It does not prove host compatibility or live model behavior. Test the real adapter separately with its admitted capabilities.

Record native, model, function, operator, and Cypher operations separately. Include failed attempts and the exact guard receipt. Task benefit requires the paired evaluation in the [PRD](../OAK-PRD.md).
