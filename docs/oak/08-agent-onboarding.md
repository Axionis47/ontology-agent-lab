# Onboarding an existing agent runtime

Design version 0.3.0. November 2, 2026. This is a proposed integration contract. The adapter is not implemented. It defines the attachment points used by [C4](04-task-executor.md) and the [integration workflow](INTEGRATION.md).

Deferred external-integration analysis. The current first product uses the [managed starting shape](implementation/AGENT-SHAPE.md).
This document does not authorize arbitrary external hosts, memory, or tools in that profile.

The product attaches a kernel to an existing agent runtime. That runtime has its own model, instructions, memory, skills, tools, and execution loop. Tool descriptions alone do not provide this connection.

The paper specifies an agent that consumes S, G, and F and calls typed functions. It does not specify adapters for arbitrary runtimes, memories, or nested agents. This contract defines that extension. Native tools remain available under the declared adaptation. [OaK sections 3.1 to 3.3](https://arxiv.org/html/2608.22974v1).

Use the [independent verification plan](INDEPENDENT-VERIFICATION.md) for cross-component checks.

## Tool contracts and executable bindings

| Interface | Consumer | Content |
| --- | --- | --- |
| Model-visible contract | Model or planner | Name, description, input schema, and documented results and effects |
| Executable binding | Host runtime | Tool implementation, connection, credentials, execution policy, and result delivery |

For example, the model selects `search_offers(city, dates, party_size)`. The host executes its existing client and returns an observation. The input schema does not connect to a provider.

Register F through the host's tool-registration interface. Its binding invokes the function runtime. That runtime injects a scoped graph revision and executes registered operators. Native tools retain their original bindings. An ontology property does not define an API endpoint.

## Host ownership

| Existing part | Treatment |
| --- | --- |
| Model and execution loop | The host retains ownership. C4 uses supported callbacks or middleware. |
| System prompt | Preserve it. Add a separate, versioned kernel-context fragment through a supported interface. |
| Native tools | Preserve implementations and permissions. Register F in a separate namespace. |
| Memory | Preserve it. Read available context and provenance through declared host interfaces. |
| Skills and delegation | Preserve them. Report capability and observation limits. |

The added tools and instructions change the effective context. Record this change and its version as part of the intervention. Do not claim identical prompts when kernel context differs. Report conflicting host instructions. Do not silently replace them.

The adapter does not require universal prompt export or memory migration. It requires enough task scope, configuration references, and extension support for the selected mode. Report inaccessible context as a visibility limit.

## Adapter contract

These are proposed operations, not an existing SDK:

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

The host can use memory that the adapter cannot inspect. Report this limit when interpreting kernel effects. Preserve declared memory conditions across comparisons. Prevent held-out answers and another condition's observations from entering a comparison.

## Compound tools and delegated agents

Treat `research_trip` as one capability unless it exposes internal operations. It can call services or another agent with separate context. Attaching the parent does not attach every delegate.

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
| Tool descriptions | Capability analysis and candidate construction from supplied evidence | No executable connection or result interception |
| Callable tools without host hooks | Calls through a separately admitted harness | Existing runtime remains unattached |
| Tool registration, task binding, result hooks, and sequencing | Optional-functions mode with incremental evidence | Mandatory enforcement needs additional hooks |
| Protected dispatch and typed finalization hooks | Guarded requirements on named paths | Other routes and delegates can remain uncovered |
| Black-box `invoke(request)` | Outer request/result inspection and advice through available context | No per-tool ordering, internal accounting, or inner-action enforcement |

Show an admission report for each capability. Use supported, partial, or unavailable. Include registration, context addition, top-level observations, nested observations, memory provenance, task binding, protected dispatch, and typed completion. Select the integration mode from verified capabilities.

## Runtime example

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

The pilot must implement one selected adapter. A different framework requires compatible bindings to its extension points. Domain onboarding still defines tasks, business requirements, and source interpretation.

## Independent admission tests

Test the adapter with a fake host, saved packages, a C2 response fixture, and an F dispatcher recorder. Each substitute must record calls, arguments, versions, and results. Declare substitute behavior and hashes. No real provider, model, or graph database is needed for this boundary test.

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

Admission must show callable F, actual native-result delivery to C2, acknowledged-revision use, task isolation, and visible failures. Test asynchronous and nested behavior only where claimed. Guarded mode requires evidence for every declared protected route. Preserve native permissions and record context changes.

These checks establish attachment behavior. They do not establish task correctness or an ontology benefit. The adapter and probes remain unimplemented. The runtime, task API, model settings, and execution budget remain unselected.
