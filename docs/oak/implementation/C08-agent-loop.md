# C8: The first ontology-consuming agent loop

Design version 0.4.1. Owner: C8. Status: proposed; service verification not run.

The host chooses the next action. The ontology supplies domain definitions and reusable computation.
C8 implements one bounded host loop. C4 controls dispatch, evidence ordering, and finalization.
An agent record is this loop's project-owned configuration. It is not a complete agent application.

The [shared contracts](CONTRACTS.md) govern IDs, artifacts, envelopes, errors, and package identity.
[C0](C00-task-admission.md) admits inputs. [C4](C04-execution.md) owns action contracts. [C9](C09-identity.md) owns configurations.

## Selected class and reuse

Use loop profile `sequential_readonly/1` with task profile `offer-selection-v1` and the managed C8 host.
The [starting shape](AGENT-SHAPE.md) defines their separate identities, minimum boundaries, preset, probes, and extension gate.
The task selects one observed offer using two read-only native tools and one optional domain function.
The class cannot book accommodation, alter external records, access arbitrary tools, or load arbitrary host adapters.

| Responsibility | Existing implementation | Project-specific work |
| --- | --- | --- |
| Control flow | LangGraph `StateGraph`, nodes, conditional edges, `START`, `END` | The bounded decision and dispatch graph |
| Persistence | Official PostgreSQL checkpointer; SQLite for isolated local development | Server-owned run/thread mapping and receipt references |
| Input and action validation | Pydantic strict models and discriminated unions | Task state, configuration, and allowed action fields |
| Native dispatch | Ordinary registered Python callables | Exact fixture lookup and source-envelope binding |
| Model communication | Selected provider's supported SDK | Versioned prompt, structured action parsing, recorded actual settings |
| Job delivery | C10's Procrastinate worker | One named loop task and scoped resumption |

Do not build another agent framework, scheduler, checkpoint store, or plugin discovery system.
LangGraph supplies state transitions and checkpoints. It does not make provider calls and database effects one transaction.
See its [Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api) and [persistence guide](https://docs.langchain.com/oss/python/langgraph/persistence).

## Normative requirements

1. **C8-R01:** C8 must admit only the selected agent class and its pinned callable registry.
2. **C8-R02:** C8 must keep the host decision loop separate from C4 dispatch authority.
3. **C8-R03:** C8 must accept exactly one native, function, or finalization action per decision.
4. **C8-R04:** C8 must preserve the 12-decision ceiling and original deadline after restart.
5. **C8-R05:** C8 must persist a decision before dispatching its selected action.
6. **C8-R06:** C8 must reconcile pending operations before requesting another decision.
7. **C8-R07:** C8 must preserve the run's frozen package, agent version, and interpretation dependencies.
8. **C8-R08:** C8 must expose source content as data without granting new execution capabilities.
9. **C8-R09:** C8 must match fixture calls by case, tool, version, and canonical arguments.
10. **C8-R10:** C8 must keep evaluator-private material outside host state and prompts.
11. **C8-R11:** C8 must record actual model settings, failed attempts, usage, and function use.
12. **C8-R12:** C8 must require complete authorized model configuration before model-driven execution.
13. **C8-R13:** C8 must resolve the starting shape to compatible registered contracts and implementations before binding verification.
14. **C8-R14:** C8 must derive readiness from server-issued probe receipts for the exact implementation and package.
15. **C8-R15:** C8 must reject hidden task-relevant tools, delegates, retrieval, memory, and unsupported attachment modes.

## Exact configuration and binding contracts

All payloads reject unknown fields and coercion. Artifact resolution uses the authenticated project, agent, and admitted data role.
The service envelope is `0.4.0`. `host-loop/1` identifies this component's saved payload profile.

| Model | Required fields |
| --- | --- |
| `HostConfig` | `profile: "host-loop/1"`; `agent_class: "offer-selection-v1"`; `loop_profile: "sequential_readonly/1"`; `starting_shape_ref: ArtifactRef`; `driver: scripted_fixture\|fixed_model`; `workflow_ref`, `callable_registry_ref`, `prompt_profile_ref`, `budget_ref`: `ArtifactRef`; `model_config_ref: ArtifactRef\|null`; `max_decisions: integer[1,12]`; `parallel_actions: false` |
| `CallableRegistry` | `profile: "offer-callables/1"`; `native_entries: NativeBinding[2]`; `function_entry: FunctionBindingDeclaration`; `fixture_manifest_ref: ArtifactRef`; `registry_implementation_ref: ArtifactRef` |
| `NativeBinding` | `tool_id: fixture.search_offers\|fixture.get_offer_details`; `tool_version: "0.1.0"`; `input_contract_ref`, `output_contract_ref`, `implementation_ref`: `ArtifactRef`; `effect: "read"`; `binding_key: fixture_search\|fixture_detail` |
| `FunctionBindingDeclaration` | `function_id: "select_eligible_offers"`; `input_contract_ref`, `result_contract_ref`: `ArtifactRef`; `binding_key: "c4_function_dispatch"` |
| `ResolvedFunctionBinding` | Declaration fields plus `bundle_ref: ArtifactRef`; `package_ref: ArtifactRef` |
| `RegistryCapabilityReceipt` | `registry_ref`, `starting_shape_ref`: `ArtifactRef`; `native_binding_hashes: Hash[2]`; `dispatch_implementation_ref: ArtifactRef`; `probe_refs: ArtifactRef[2]`; `status: registered\|rejected`; `full_mount_required: true`; `diagnostic_refs: ArtifactRef[]` |
| `CapabilityProbeReceipt` | `probe_id`: fixed enum in AGENT-SHAPE; `phase: registry\|mount`; `implementation_fingerprint: Hash`; `suite_ref: ArtifactRef`; `input_refs`, `observed_refs`, `diagnostic_refs`: `ArtifactRef[]`; `status: passed\|failed\|error\|not_run` |
| `HostMountRequest` | Shared envelope; `agent_version: integer>=1`; `host_config_ref`, `package_ref`, `admission_ref`, `task_request_ref`: `ArtifactRef`; `checkpoint_thread_id: Id` |
| `HostMountReceipt` | `binding_id: Id`; all mount input references; `registry_sha256: Hash`; `workflow_sha256: Hash`; `resolved_function: ResolvedFunctionBinding\|null`; `status: ready\|rejected`; `capabilities: HostCapabilities`; `probe_refs: ArtifactRef[7]`; `diagnostic_refs: ArtifactRef[]` |
| `HostCapabilities` | `native_callbacks: true`; `single_action_dispatch: true`; `observation_barrier: true`; `typed_finalization: true`; `guarded_finalization: true`; `external_writes: false`; `arbitrary_adapters: false` |
| `HostPromptProfile` | `profile: "offer-prompt/1"`; `instruction_ref`, `action_schema_ref`: `ArtifactRef`; `source_role: "untrusted_data"`; `private_evaluator_access: false`; `authoritative_prose: false` |
| `DecisionReceipt` | `decision_id`, `operation_id`: `Id`; `step: integer[1,12]`; `input_state_sha256: Hash`; `prompt_ref: ArtifactRef\|null`; `driver_result_ref`, `usage_ref`: `ArtifactRef`; `action: C4.ActionRequest\|null`; `outcome: accepted\|invalid\|failed`; `created_at: Timestamp` |

The registry has each native tool exactly once. Binding keys select server-defined callables from an explicit Python registry.
`HostConfig.agent_class` must equal the shape's task profile. Its loop profile, driver, bounds, and tools must also match.
C8 compares execution mode from `AgentVersionPayload` and the package with the shape's declared mode.
`oak-agent-shape/1` accepts only the scripted driver. The future `fixed_model` design requires a new admitted shape profile.
`HostCapabilities` lists required properties. Only the server's executed probe receipts establish those properties.
The two registry and seven mount probe IDs, inputs, fingerprint rules, and isolation requirements are defined in the starting shape.
The [conformance contract](MOUNT-CONFORMANCE.md) defines prepared bindings, verifier-only grants, and recorded child runs without recursive mounting.
Each required probe must appear exactly once. Failed or unrun probes cannot produce a registered or ready result.
A client cannot provide an import path, executable body, or provider endpoint.
The registry declares the function contract without pinning a future function bundle.
C0 may use `RegistryCapabilityReceipt` before construction. It verifies native callables and the registered function-dispatch boundary only.
It cannot establish that a kernel-specific function is ready.
At mount, C8 resolves the function bundle from the run's package and matches its function ID and contracts to the declaration.
The mount receipt pins that resolved binding. A repaired bundle creates a new mount without changing the immutable host configuration.
The mount process resolves hashes, verifies callable signatures, and confirms the required C4 hooks.
It exposes a tool description only after its callable is registered. A manifest alone cannot produce `status: ready`.
The mount publishes all bindings together. Failed mounting leaves no partial function catalog or host context.

The C9 starter preset supplies these references through the server's pinned registry.
It does not put evaluator references in the browser or preload fixture responses into host state.
The current callable fixture contracts remain unchanged. Null `page_token` is removed before native matching, as specified by C4.

## State and graph design

Use one LangGraph graph per run. Construction and candidate verification use different thread identities.
The C8 worker completes mounting before creating an ordinary or candidate-verification `HostState`.
Conformance child state uses the prepared-binding branch instead. It never calls full mount from `load`.
The graph has five nodes: `load`, `decide`, `dispatch`, `record`, and `close`.
Each node returns a state update. Conditional edges select the next node. No parallel branch is needed for this class.

| `HostState` field | Type and authority |
| --- | --- |
| `project_id`, `agent_id`, `run_id`, `assignment_id`, `checkpoint_thread_id` | `Id`; server-created scope |
| `agent_version` | Positive integer; pinned at run creation |
| `package_ref`, `host_config_ref`, `task_request_ref` | Immutable `ArtifactRef` values |
| `mount_receipt_ref`, `prepared_binding_ref` | `ArtifactRef\|null`; exactly one is nonnull; prepared binding is permitted only for authoritative `host_conformance` purpose |
| `phase` | `loading\|deciding\|dispatching\|recording\|closing\|terminal` |
| `decisions_used`, `state_version` | Nonnegative integers; reconciled from C10 before new work |
| `deadline_at`, `budget_reservation_id` | `Timestamp`, `Id`; immutable admitted resource boundary |
| `pending_decision_ref`, `pending_operation_id` | `ArtifactRef\|null`, `Id\|null` |
| `incorporated_snapshot` | C2 `GraphSnapshotRef\|null`; advances only from successful C4 results |
| `observed_response_refs`, `decision_refs`, `action_result_refs` | Ordered `ArtifactRef[]`; unique by operation identity |
| `attempted_detail_ids` | Unique source offer IDs, used by the scripted policy |
| `final_result_ref`, `trial_ref` | `ArtifactRef\|null` |
| `terminal_reason` | C4 terminal-reason enum or null |

Checkpoints hold references and bounded decision state. Raw evidence, prompts, and receipts remain immutable artifacts.
Use ordinary replacement updates for this sequential graph. Do not append duplicate messages through retry-sensitive list reducers.
C10's run and operation records remain authoritative if a checkpoint is older than a committed dispatch result.

```text
START -> load -> decide -> dispatch -> record
                  ^                    |
                  |                    +-> decide, if another decision is permitted
                  |                    +-> close -> END, if terminal or exhausted
```

`load` resolves the pinned runtime, scope, package, and outstanding receipts.
It starts with no observations or cross-run memory. C0 rejects nonempty initial observation IDs for this profile.
`decide` consumes the bounded visible context and produces one typed action or an explicit decision failure.
Before calling the driver, C10 reserves the next decision step. C4 uses that same reservation and never increments it again.
An invalid decision routes directly to `record`, with no C4 callable dispatch. Its step and usage remain consumed.
`dispatch` submits that saved action to C4. It does not call native tools or Neo4j directly.
`record` incorporates C4's completed response and committed snapshot reference.
`close` obtains the terminal C4 trial record. It never assigns an independent task-success score.

The 12-decision ceiling counts host decisions, including invalid actions and rejected finalization.
LangGraph super-steps are implementation transitions. Its recursion limit is a separate emergency bound, not the task budget.
Set that bound in the pinned workflow configuration and test it against the complete 12-decision path.
Do not silently terminate a task early because one decision traverses several graph nodes.

## Scripted engineering driver

The first executable host uses a deterministic policy. It must not inspect the evaluator's expected offer ID.

1. Call `fixture.search_offers` with the admitted request and no page token.
2. Call `select_eligible_offers` after C4 completes the search observation barrier.
3. If an eligible offer exists, select the first UTF-8-sorted offer ID from the function result.
4. Otherwise, choose an unresolved offer without a known violation or an earlier detail attempt.
5. Call `fixture.get_offer_details` for that offer and the original stay and party.
6. Repeat the function call after the detail observation commits.
7. If no supported selection can be obtained, finalize with `no_supported_offer`.

The policy considers at most 100 observed offers. It does not claim that search results exhaust the market.
It does not repeat a missing fixture call to manufacture evidence. Failed calls remain in the trace.
Known violations remain visible even when another constraint is unknown.
Finalization uses C4's exact `FinalSelection`, with `explanation: ""` and source observation IDs.
C5 treats safe abstention as incomplete under the current completion contract.

This scripted policy always calls F. It tests integration behavior only, not autonomous tool choice or an ontology treatment effect.
The existing harness demonstration loads source files directly. It does not yet execute this LangGraph host or its exact fixture dispatcher.

## Future fixed-model driver and experiment boundary

The model sees the typed task, pinned schema/function descriptions, admitted instructions, and observations actually returned through C4.
It receives no private answers, future fixture responses, graph data from another case, or automatic development-corpus preload.
Source text is marked as untrusted data. Restricted action schemas and C4's allowlist limit what source instructions can cause.
Do not claim that prompt delimiters alone establish prompt-injection resistance.

The model returns one C4 action. Parallel calls, booking claims, changed task arguments, and arbitrary tool names fail validation.
Record the raw provider response as restricted evidence. Record any parsed action separately.
Malformed output consumes a decision and its actual model cost. A new correction request consumes another decision.
Provider transport attempts remain separate from decision count and retain their usage or explicitly unknown usage.

`fixed_model` requires an admitted provider, exact model version, enabled thinking settings, prompt version, resource limits, and execution authorization.
Record the actual settings sent to the provider. Record supported reasoning-token usage without requesting hidden reasoning text.
No model is selected or called by this component specification.

In optional mode, a model may select F or finish from native evidence. C5 scores its result independently of mandatory function use.
In guarded mode, C4 applies the pinned finalization checker. C8 cannot bypass it through a different output channel.
Paired comparisons retain model, thinking, native tools, evidence access, prompts, and budgets except for the declared intervention.
Initial and refined kernels use separate pinned package identities. Held-out inference changes observations, never S, F, O, or their dependencies.

## Recovery, failures, and storage

Persist the decision receipt before C4 dispatch. C10 saves action intent and reservation before invoking the selected callable.
If a worker restarts, resolve the pending decision and C4 operation before requesting another decision.
A committed result can repair an older checkpoint by reference. It cannot create a second semantic action.
An uncertain model response may require another charged provider attempt. Do not infer zero cost from a missing response.

C10 allocates the checkpoint thread ID and authorizes every resume. A browser cannot choose a thread namespace.
Use the pinned workflow implementation on resume. Missing code or incompatible checkpoint state blocks the run.
Cancellation prevents new decisions and dispatch. C4 reconciles completed in-flight work before closing the trial.
Never reset the absolute deadline, decision count, or resource ledger during pause and resume.

| Failure | Required result |
| --- | --- |
| Registry, callback, or implementation hash mismatch | `host_binding_invalid`; no ready mount or dispatch |
| Unknown fixture key or changed arguments | `fixture_response_unavailable`; no substituted response |
| Invalid model action | Saved failed decision; no native dispatch; remaining budget decides continuation |
| Failed required ingestion | No dependent F call; preserve the response and return the C4 dependency failure |
| Frozen package or thread-scope mismatch | `host_scope_mismatch`; no newer-package fallback |
| Exhausted decision or time budget | C4 trial with `budget_exhausted`; assignment remains in C5's denominator |
| Lost decision or action acknowledgement | Reconcile the stable operation before any new decision |

## Challenges and required acceptance

Reject a generic adapter layer until this loop's hooks and failure behavior pass.
Reject a second state machine outside LangGraph for workflow control. C10's ledger tracks durable effects, not replacement graph scheduling.
Reject a success label from host completion. Only C5 evaluates the assigned task independently.
All tests below are proposed real-host cases. The current local harness does not mark them passed.

| Test ID | Scenario or fault | Required observation |
| --- | --- | --- |
| C8-T01 | Valid fixed fixture registry and scoped mount | Ready receipt with exact callable hashes; no partial registration |
| C8-T02 | Tool descriptions without executable binding | Rejected mount before run dispatch |
| C8-T03 | Wrong case, tool version, arguments, or page token | Explicit unavailable response; no unrelated fixture |
| C8-T04 | Search, F, missing detail, F, final selection | Ordered C4 barriers and source-backed structured result |
| C8-T05 | Remove evaluator access from scripted host | Same policy decisions; no oracle or private-source reads |
| C8-T06 | Twelve decisions, including invalid actions | No thirteenth decision; internal graph transitions do not consume decision budget |
| C8-T07 | Crash after saved decision or completed dispatch | Reconciliation returns one decision/action identity without duplicate source ingestion |
| C8-T08 | Resume near deadline and resource limit | Original limits, costs, and decision count remain effective |
| C8-T09 | Activate another kernel during a paused run | Resume uses the original package and workflow |
| C8-T10 | Foreign project thread or modified agent version | Denial before checkpoint, source, or artifact access |
| C8-T11 | Source text requests booking or another tool | No new callable capability; invalid action is recorded and rejected |
| C8-T12 | Model config absent or thinking disabled | Admission failure; zero model calls |
| C8-T13 | Optional F skipped versus guarded finalization | Optional path remains scoreable; guarded path cannot bypass its checker |
| C8-T14 | Missing, conflicting, or unavailable detail evidence | Safe abstention or failed trial; no inferred passing fact or complete-success label |
| C8-T15 | Cancellation during pending dispatch | No new decision; actual completed work and costs remain recorded |
| C8-T16 | Malformed output, failed provider attempt, or free-form final prose | Attempt and usage retained; no authoritative prose release or hidden-reasoning request |
| C8-T17 | Validate the initial registry before a package exists, then mount original, incompatible, and repaired bundles | Capability validation needs no package; the incompatible contract is rejected; a compatible repaired bundle mounts without changing the agent version |
| C8-T18 | Shape aliases, task profile, loop profile, mode, or registered code differ from the saved host configuration | Binding verification rejects the mismatch without installing a callable |
| C8-T19 | Client claims capabilities, or a required probe is absent, failed, errored, unrun, duplicated, or bound to old code | No registered or ready receipt; exact probe diagnostics remain available |
| C8-T20 | Attempt external attachment, hidden retrieval, cross-run memory, or a delegate | Unsupported channel is rejected before task execution |
| C8-T21 | Validate pre-kernel hooks, then fail a package-specific observation, restart, or terminal-route probe | Pre-kernel receipt remains limited; full mount fails and dispatch stays blocked |
| C8-T22 | Run full-package probes without an existing ready mount, then attempt recursive probes or ordinary use of the staged binding | Recorded conformance children use the same handlers without recursion; ordinary dispatch remains blocked until all required probes pass |

Exit requires the registered callable, LangGraph, checkpoint, C4, and independent evaluator path to pass together.
These tests establish this host integration. They do not establish improved agent behavior or complete ASD-STE100 conformity.
