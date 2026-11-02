# Onboarding an existing agent runtime

Design version 0.4.8. November 2, 2026. This is a proposed integration contract. The production ReAct loop and host adapters are not implemented. It defines the attachment points used by [C4](04-task-executor.md) and the [integration workflow](INTEGRATION.md).

The primary integration connects a replaceable ReAct working agent to OaK's frozen kernel. It receives a query, readable schema, and callable function contracts; it selects typed calls, reads results, and returns an answer. The agent need not write code or expose its private planner. C3 composes the executable functions before the worker uses them.

The [managed starting shape](implementation/AGENT-SHAPE.md) is the current engineering fixture. Its native registry and scripted decisions test local contracts. They do not implement or establish the production paper-aligned loop.

The paper specifies ReAct function calls over G and makes the frozen kernel the sole task-data channel. The common interface below preserves that algorithm. Host-specific adapters are our implementation choice. Native API retrieval during a task, agent-submitted evidence records, and guarded completion are deferred adaptations, not the primary algorithm. [OaK sections 3.1 to 3.3](https://arxiv.org/html/2608.22974v1#S3.SS1).

Use the [independent verification plan](INDEPENDENT-VERIFICATION.md) for cross-component checks.

## Primary worker protocol

For a new query q and its accompanying corpus Cq, C2 builds Gq under the frozen schema S. Give the worker q, readable S, and the names, descriptions, and input/output contracts of F. Register callable bindings to the F runtime. The worker does not receive an unrestricted corpus reader, database client, or alternate source of task data. [OaK section 3.3](https://arxiv.org/html/2608.22974v1#S3.SS3).

The worker chooses an F function and supplies typed arguments. The runtime validates them, injects the authorized query-graph context, executes the frozen function, and returns its output or explicit failure. The worker uses those observations to choose the next call or answer. The same call/observation boundary can serve different worker implementations without changing the OaK algorithm. Record observable calls, outputs, final answers, versions, and resource use; do not request hidden reasoning text.

A function may package several graph operations that the model would otherwise coordinate itself. That executable computation lives in F, not in code the working agent must invent during inference. The worker still interprets the question, chooses calls and arguments, and forms the answer. C5 checks task correctness independently; successful calls and a consistent schema do not prove a correct answer.

The runtime must verify that task data cannot bypass the kernel through native tools, delegates, retrieval, or memory. These routes must be disabled or isolated for the paper-aligned run. A host that cannot provide this boundary is unsupported for that profile, even if it accepts the schema in a prompt. Internal planner inspection and a universal native-tool catalog are unnecessary, but task-data isolation is required. S and F remain frozen throughout held-out inference. HermiT checks schema logic during construction and does not drive the worker's next action.

Construction receives task requirements, source material or recorded development evidence, representative cases, and independently specified evaluation contracts. It generates the initial schema and functions before the working agent's kernel-assisted trials. A finished ontology, native-tool catalog, or installed domain function bundle is not required from the user to begin general construction.

## Tool contracts and executable bindings

The model-visible contract and executable binding are both required for the primary F interface. The later native-observation hooks apply only to the deferred live-API adaptation.

| Interface | Consumer | Content |
| --- | --- | --- |
| Model-visible contract | Model or planner | Name, description, input schema, and documented results and effects |
| Executable binding | Host runtime | Tool implementation, connection, credentials, execution policy, and result delivery |

For example, the model selects a constructed accommodation-candidate function and supplies the city, dates, and party size. The host dispatches the installed F binding, which computes over Gq and returns candidates. The function description alone does not execute that computation.

Register F through the host's tool-registration interface. Its binding invokes the function runtime. That runtime injects a scoped graph revision and executes registered operators. In the primary profile, native task-data bindings are unavailable to the worker. Keeping native tools available and ingesting their results is a separate adaptation. An ontology property does not define an API endpoint.

## Host ownership

| Existing part | Treatment |
| --- | --- |
| Model and execution loop | The host retains ownership and must support the ReAct call/observation/final-answer boundary. C4 observes F calls and their results. |
| System prompt | Preserve it. Add a separate, versioned kernel-context fragment through a supported interface. |
| Native tools | Preserve their implementations outside the run. Disable alternate task-data access for the paper-aligned run and register F as its callable interface. |
| Memory | Declare and isolate task-data memory so it cannot bypass the kernel or contaminate a comparison. No memory migration is required. |
| Skills and delegation | Admit only behavior that preserves the same kernel-only task-data boundary. Uncontrolled delegates prevent admission to the primary profile. |

The added tools and instructions change the effective context. Record this change and its version as part of the intervention. Do not claim identical prompts when kernel context differs. Report conflicting host instructions. Do not silently replace them.

The adapter does not require universal prompt export or memory migration. It requires enough task scope, configuration references, and extension support for the selected mode. Report inaccessible context as a visibility limit.

## Host adapters and deferred native-observation hooks

The primary worker needs context delivery, F registration/dispatch, task binding, observations, final answers, and data-channel isolation. The following earlier adapter sketch additionally supports native-tool observation for the deferred live-API adaptation. It is proposed, not an existing SDK; these method names are not required of every host:

```text
describe_host() -> HostCapabilities
describe_tools() -> NativeToolManifest
mount_kernel(package, function_dispatcher, context_provider) -> MountReceipt
begin_task(task_id, package_id, declared_initial_evidence) -> TaskBinding
on_tool_completion(event) -> IngestReceipt
on_task_state(event) -> LifecycleReceipt
export_observable_trace(task_id) -> TraceRecord
```

### Describe capabilities and tools

`describe_host` reports tool registration, context addition, result observation, call ordering, task identity, nested events, and protected-operation interception. Verify claimed support with a bounded admission probe.

`describe_tools` supplies stable IDs, namespaces, versions, descriptions, input contracts, result/effect semantics, and binding references. Discovery can supply available metadata. Keep unknown semantics explicit. Record dynamically discovered contracts and versions before use. A frozen task cannot silently accept an incompatible tool.

### Mount the kernel

`mount_kernel` registers F and the compact context fragment. The host keeps its loop. Registration failures and name collisions prevent a ready result.

A partial mount must not expose callable F bindings as a ready package. Remove registrations and context additions made by the failed attempt where supported. Otherwise, disable those bindings and report incomplete cleanup. Preserve existing native registrations and host context. Save the attempted additions and cleanup outcomes in `MountReceipt`. Admission remains blocked until cleanup or isolation is verified.

### Bind a task

`begin_task` pins the package and assigns a graph context to the host task. Separate evidence between conversations, users, delegates, and comparison conditions. Obtain graph scope from `TaskBinding`. Do not accept a database context chosen by the model.

### Receive tool completion

`on_tool_completion` receives an actual host or dispatcher event. It captures the observation and calls C2. A synchronous hook can finish ingestion before returning the observation.

An asynchronous hook records pending ingestion. A dependent F call declares required observation IDs or an ordered observation watermark. It waits for their committed inclusion or returns an explicit pending/failure state. The receipt must identify the committed revision that includes those observations. A late acknowledgement must not move the task revision backward. Delayed telemetry alone does not establish this ordering. The adapter needs a sequencing mechanism.

Bind each event to its task, call ID, capability version, and execution generation. After task closure, do not ingest late events into another task or reopen function dispatch. Preserve the late event for audit or effect reconciliation in its original scope. Reconciliation can append evidence only through the original task's declared recovery path and C2.

### Record lifecycle and traces

`on_task_state` records supported start, completion, failure, suspension, and cancellation events. Task closure releases runtime bindings. It preserves immutable evidence and traces. F dispatch must use the pinned package, even if conversation history contains obsolete function descriptions.

`export_observable_trace` reports exposed calls, results, revisions, failures, and resource use. Unobserved internal operations remain unknown. Do not report them as zero. Do not request hidden reasoning.

C4's `existing_agent.next_operation` is conceptual notation. A real adapter can use callbacks around the existing loop. It need not expose that method or add a second planner.

## Prompt and memory boundary

The kernel context describes concepts, F functions, missing-evidence results, and the pinned package. It is an added context fragment. It does not replace the host prompt or include the full graph.

Memory is not automatically a source-backed evidence store. Separate user preferences, remembered observations, and agent summaries. A remembered price keeps its source time. Reading it again does not make it current. Only admitted observations become source-backed graph facts. Unsupported recollections remain labeled assertions.

A host may have memory that the adapter cannot inspect, but the primary profile must isolate it from task data. Unverified task-data memory access blocks a kernel-only claim. A separately declared adaptation may report a narrower visibility limit. Preserve declared memory conditions across comparisons and prevent held-out answers or another condition's observations from entering a comparison.

## Compound tools and delegated agents

This section applies to the deferred live-API adaptation. Treat `research_trip` as one capability unless it exposes internal operations. It can call services or another agent with separate context. Attaching the parent does not attach every delegate. Such an opaque capability is not allowed to bypass the kernel in the primary profile.

- With nested events, preserve parent/child IDs, capability versions, observations, completion states, and actual operation counts.
- Propagate task context explicitly where permitted.
- Without nested events, attribute the result to the compound tool. Do not invent internal calls or provider receipts.
- An asynchronous ticket records acceptance or pending work. Completion and effects require separate status observations.
- To let a delegate call F, provide its tools and graph context through a compatible adapter.
- Parent registration does not establish delegate inheritance.
- A parent pre-call check does not verify undisclosed downstream actions. Limit enforcement claims to paths with verified guards.

These event contracts are our requirements. They are not generic operators from the paper. [OaK section 3.2, Step 3; Appendix B](https://arxiv.org/html/2608.22974v1).

## Integration levels

| Available host interface | Supported result | Limit |
| --- | --- | --- |
| Query/schema context, callable F, scoped observations and final answers, verified task-data isolation | Primary ReAct worker interface using frozen S/F over Gq | Independent evaluation is still required; no correctness guarantee from tool use alone |
| Tool descriptions | Capability analysis and candidate construction from supplied evidence | No executable connection or result interception |
| Callable tools without task binding or channel isolation | Function calls only | Insufficient for primary-profile admission |
| Tool registration, task binding, native-result hooks, and sequencing | Deferred live-API adaptation with incremental evidence | Native access changes the paper's sole-kernel data policy |
| Protected dispatch and typed finalization hooks | Deferred guarded requirements on named paths | Other routes and delegates can remain uncovered |
| Black-box `invoke(request)` or typed evidence/result submission | Possible deferred completion-validation adaptation | Does not provide the primary F-call/observation loop or verified task-data isolation |

Show an admission report for claimed capabilities using supported, partial, or unavailable. The primary boundary verifies query/schema delivery, typed F calls and results, exact package and graph binding, final answers, and sole-kernel task-data access. The existing `optional_functions` and `guarded_requirements` enums describe the fixture and adaptations; neither establishes the primary profile by itself.

## Runtime example

Primary paper-aligned inference:

```text
query q + accompanying corpus Cq
    C2 builds Gq under frozen S
    worker receives q, readable S, callable frozen F
    worker selects F + typed arguments
        runtime executes F over authorized Gq -> result
    worker observes result -> another F call or final answer
    independent evaluator scores answer
```

Deferred live-API adaptation:

```text
Existing agent: prompt + memory + native tools + its own loop
    selects native search_offers
        host executes its existing binding
        completion hook -> C2 -> committed graph revision
    selects newly registered domain.check_observed_offers
        F runtime -> O -> scoped Neo4j evidence -> typed result
    selects another native read when evidence is missing
    produces a result through the host's normal completion path
        guarded mode additionally checks protected typed completion
```

The primary protocol needs an implemented kernel-tool connection and verified task-data isolation; a different working agent can use the same callable boundary. The observed-tool adaptation additionally needs compatible native hooks. Domain onboarding still defines tasks, business requirements, source interpretation, and independent evaluation.

## Independent admission tests

For the primary boundary, use two working-agent substitutes with different host implementations. Verify schema and F-contract delivery, typed calls/results, exact graph and package scope, explicit unknowns, invalid-call rejection, and final-answer delivery. Attempt alternate task-data access and S/F mutation during inference; both must be rejected. Neither substitute needs code-writing capability or private-planner access. These are proposed tests, not execution results.

For the optional host-hook adapter, use a fake host, saved packages, a C2 response fixture, and an F dispatcher recorder. Each substitute must record calls, arguments, versions, and results. Declare substitute behavior and hashes. No real provider, model, or graph database is needed for this boundary test.

The host owns native execution and its loop. The adapter owns registrations, bindings, event routing, and admission receipts. C2 owns domain-graph writes. The adapter must not bypass C2 to write facts.

| Test | Fault or action | Exact expected result |
| --- | --- | --- |
| HA-T1 | Mount a valid package and call F | One registered binding invokes the expected dispatcher with the pinned package |
| HA-T2 | Fail registration after one addition | Mount remains not ready; partial F bindings stay disabled; original registry/context hashes remain unchanged |
| HA-T3 | Delay the C2 acknowledgement | Dependent F executes zero times before acknowledgement, or returns a pending result |
| HA-T4 | Return a failed C2 receipt | Dependent F cannot claim to use the rejected observation |
| HA-T5 | Supply another task's context in model arguments | Dispatch rejects it or replaces it with the authorized binding; no cross-task read occurs |
| HA-T6 | Replay a completion event | Preserve duplicate identity; C2 applies its replay policy without duplicate assertions |
| HA-T7 | Deliver a late callback after closure | No new F dispatch or cross-task ingestion occurs; the late event remains traceable |
| HA-T8 | Use an opaque delegated result | Internal operation count remains unknown; no invented provider receipt appears |
| HA-T9 | Omit one protected route | Admission cannot claim guarded coverage for that route |
| HA-T10 | Resolve an obsolete function from conversation history | Dispatch rejects it or resolves the pinned compatible binding explicitly |

For HA-T3, record event order and the revision consumed by F. After acknowledgement, the revision must include the required observation or report incompatibility. Waiting alone is not a pass.

For HA-T5, inspect attempted reads as well as returned data. A rejected result after an unauthorized read still fails isolation. For HA-T2, inspect enabled registrations and context additions after cleanup. Compare original registry and context hashes. Any residual addition must remain isolated and must block ready admission.

Save input fixtures, expected results, actual results, operation logs, and residual state. Report passed tests over all assigned tests. Keep failures, timeouts, unsupported checks, and unrun tests visible. A passing fake-host test does not establish support in a real host. Repeat the applicable admission checks through the selected runtime before claiming attachment.

## Acceptance and current status

Primary admission must show query/schema delivery, callable F with typed arguments and returned observations, graph/package isolation, frozen S/F, final-answer delivery, and verified sole-kernel task-data access. It needs no private-planner access. The deferred observed-tool adaptation must additionally show actual native-result delivery to C2, acknowledged-revision use, and visible hook failures. Test asynchronous and nested behavior only where claimed. Guarded action mode requires evidence for every declared protected route. Record context changes and preserve permissions outside the admitted run.

These checks establish the claimed boundary behavior. They do not establish an ontology benefit. The production worker, adapters, and probes remain unimplemented. The runtime, benchmark, model settings, and execution budget remain unselected.
