# Shared loop and task contracts

Design version 0.4.6. Product boundary: one schema-backed task and evidence protocol usable by different working agents and toolsets.
Offer selection is a test fixture. It is not an agent class, a core type, or the product's permitted task list.
The general protocol below is proposed. The existing declaration validator and managed fixture implement a narrower boundary; they do not establish a working agent-independent gateway.

## General task and evidence handoff

OaK gives the working agent a task, constraints, the current schema, required evidence fields, and a typed result contract through a supported context or request interface. The working agent keeps its planner, model, memory, and native tools. OaK does not need their internal design or a complete native-tool catalog to validate the submitted record.

1. The agent inspects the required concepts, fields, relationships, and completion conditions.
2. It uses its own capabilities to gather evidence and submits typed assertions with source references, identity, units, and applicable time or task scope. Missing and conflicting values stay explicit.
3. It can invoke typed F functions when exposed. The completion gateway independently runs required deterministic checks over the submitted record even if the agent omits those calls.
4. It submits the typed task result and its supporting record. OaK validates structure, applicable constraints, evidence requirements, and independent task checks, then accepts completion or returns specific diagnostics for another bounded attempt.

Requiring this record makes the agent's proposed answer and supporting data inspectable. It does not expose or certify hidden reasoning. A filled field is an assertion, not proof of truth. Preserve agent-asserted source references separately from retrieved or independently verified evidence, and reject completion when the task's required evidence standard is unmet.

Enforcement covers completion routed through this gateway. An answer or external side effect that bypasses it is outside that guarantee. Native-tool observation and protected-action interception are optional stronger integrations, with their own verified hooks and scoped claims.

Construction starts with the task specification, source material or development evidence, representative cases, and independent completion/evaluator contracts. C1 and C3 generate candidate S and F; the user does not need to supply a finished ontology or function catalog. Seal the candidate's exact S/F dependencies before development trials; ordinary inference uses the verified, activated package. Source interpretations and mappings are proposed and verified where needed; they are not evidence of facts by themselves.

Verify this boundary with working-agent substitutes that have different native tools but submit the same task/evidence contract. Include missing facts, conflicting facts, unsupported source claims, invalid final results, and an omitted F call whose required check still runs. These are proposed acceptance cases, not completed tests.

The remaining strict declarations, tool registries, per-action hooks, and API records describe the managed fixture and its optional stronger integration profile. They are not universal input requirements for the general handoff. Their guarantees remain mandatory when that profile is selected.

## Four distinct objects

| Object | Responsibility | Changes when |
| --- | --- | --- |
| Agent loop definition | Control flow, registered native catalog, runtime, driver, observation hooks, finalization, and resource bounds | The loop implementation, available capabilities, or execution policy changes |
| Task definition | Input/result schemas, permitted tool subset, semantic requirements, mappings, function contracts, evaluator, and test policy | The meaning or contract of a task type changes |
| Task instance | Concrete input values and source context for one request | A user submits another request of that type |
| Kernel package | Verified schema, functions, mappings, policies, and dependencies for a task binding | Construction or repair produces another immutable package |

One agent can bind multiple task definitions. Each definition can accept many task instances without code changes.
A new task definition does not require another loop implementation.
The current managed fixture loop remains sequential and read-only. Those restrictions describe that integration profile, not the working agent behind the general completion boundary.

## Exact definition boundary

Use strict Pydantic models, generated JSON Schema, and ordinary dictionaries of installed Python handlers.
Do not introduce an adapter language, universal expression engine, dynamic import mechanism, or task-specific branches in the core.
The [declaration module](../../../oak_contracts/task_boundary.py) checks this boundary locally. It does not implement production execution.

| Model | Required fields |
| --- | --- |
| `AgentLoopDefinition` | `definition_id: Id`; `version: Version`; `loop_profile: sequential_readonly/1`; `attachment: managed`; `driver: scripted_fixture`; `native_tools: NativeToolContract[]`; `bounds`; declared observation/finalization hooks, action kinds, scope, memory, and concurrency policy |
| `NativeToolContract` | `tool_id: Id`; `tool_version: Version`; `binding_key: Id`; `input_profile`, `output_profile`: registered model IDs; `effect: read` |
| `TaskDefinition` | `task_id: Id`; `version: Version`; `input_profile`, `result_profile`: registered model IDs; `required_native_tools: ToolRef[]`; `functions: FunctionDeclaration[]`; `mapping_id`, `evaluator_id`, `suite_id`: registered IDs |
| `ToolRef` | `tool_id: Id`; `tool_version: Version` |
| `FunctionDeclaration` | `function_id: Id`; `function_version: Version`; `binding_key: Id`; `input_profile`, `result_profile`: registered model IDs |

The implementation's exported JSON Schema defines the exact local declaration fields and scalar validation.
Production wraps these declarations in immutable `ArtifactRef` values and resolves every registered ID to exact installed hashes.
An ID is a reference, not permission to import code or execute a callable.
Within this managed declaration profile, missing required code, schema, mapping, evaluator, or suite blocks admission with an identified dependency error. Registered task/result contracts and supported operator implementations are construction inputs; a completed S/F package is required for verification and mounting, not as a prerequisite for proposing the initial kernel.

`required_native_tools` is the task's complete permitted subset of the agent catalog.
Required means available and compatible. It does not require every run to call each tool.
Tool ID and version must resolve to exactly the registered input contract, output contract, effect, and binding key.
Functions can differ in number and signature. A task can declare no domain function when its release policy permits that case.
Neither an offer-selection result nor a five-check eligibility function is required by the core.

The published task artifact also pins `requirements_ref`, `mapping_ref`, `source_policy_ref`, `evaluation_public_ref`, `test_policy_ref`, and `suite_ref`.
Its optional `scripted_policy_ref` identifies the deterministic decision fixture. The policy is installed test code, not uploaded executable content.
The resolved artifact retains those hashes beside the declaration's IDs. C0 rejects any ID/hash disagreement.
Evaluator-private material stays in a separate server binding.

## Agent ownership and task bindings

| Production model | Required fields |
| --- | --- |
| `AgentVersionPayload` | `loop_definition_ref`, `native_tool_manifest_ref`, `host_config_ref`, `budget_ref`, `runtime_ref`: `ArtifactRef`; `model_config_ref: ArtifactRef\|null`; `execution_mode: optional_functions\|guarded_requirements` |
| `CreateAgent` | `name: string[1,120]`; `configuration`: registered loop preset selector or authorized `AgentVersionPayload` |
| `TaskBindingCreate` | `agent_version: positive_integer`; `task_definition_ref: ArtifactRef` |
| `AgentTaskBinding` | `task_binding_id`, `project_id`, `agent_id`: `Id`; `agent_version: positive_integer`; `task_definition_ref`, `resolved_catalog_ref`: `ArtifactRef`; `binding_job_id: Id` |
| `TaskInstance` | `task_instance_id: Id`; `task_binding_id: Id`; `input_ref`, `source_context_ref`: `ArtifactRef` |
| `TaskBindingView` | Binding fields plus `binding_receipt_ref: ArtifactRef\|null`; `active_package_ref: ArtifactRef\|null`; `active_generation: nonnegative_integer` |

A task binding is immutable and unique by project, agent, agent version, and task-definition digest.
Changing either definition creates a new binding. Existing admissions and runs keep their original binding.
Use `task_binding_id` as the initial knowledge and activation scope. A second mutable knowledge-scope abstraction is unnecessary.
Schema, function, and mapping artifacts can be shared by hash when compatible. Sharing bytes does not couple active pointers.
Each composite package pins one task-definition digest and the exact loop dependencies.

Agent creation registers the loop configuration. Creating a task binding resolves its subset, schemas, mappings, and evaluator and queues binding verification.
A passed receipt establishes those exact dependencies. A registered task name alone cannot establish readiness.
The user selects an agent, a task binding, and concrete task inputs. They do not create a new agent for each request.

## Typed run protocol

All requests use the shared scope and version envelope, including `task_binding_id` on task-owned work.
Task values may be JSON on the wire, but they must validate against the binding's exact registered model before use.
Use Pydantic `TypeAdapter` or the registered strict model. Never accept an unvalidated arbitrary payload as a completed handoff.

| Boundary | Common fields | Task-owned content |
| --- | --- | --- |
| Input | Task instance and binding identity, input contract reference, input digest | Validated task arguments |
| Native action | Step, tool ID/version, input contract, correlated operation | Arguments validated by that registered native model |
| Function action | Step, function ID/version, bundle, arguments, evidence barrier, snapshot | Arguments validated by the mounted function contract |
| Observation | Actual call inputs, response reference, source identity/time, scope, operation ID | Response validated by its registered model, interpreted by the pinned mapping |
| Finalization | Task and binding identity, result contract, validated result, evidence references | Selection, classification, lookup result, plan, or another admitted typed result |
| Evaluation | Assignment manifest, task definition, evaluator version, trial references | Independent task-specific scoring and diagnostics |

C8 reserves the decision, requests one typed action, dispatches through C4, records the result, and repeats within admitted limits.
Its core contains no offer sorting, search/detail sequence, ticket priority rule, field names, or task-ID branches.
Deterministic task policies belong to test fixtures. A future fixed-model driver uses the same action boundary with separately admitted provider settings.
C4 validates the selected callable against the binding's subset and verifies every output before evidence ingestion.
The final task identity must match the run. A structurally similar result from another task is still rejected.

Bounds are positive configured values, checked against the deployment's pinned resource policy at admission.
Twelve decisions and 900 seconds are defaults for the offer fixture, not universal task limits.
Restart preserves the admitted values. A new task cannot enlarge an existing run's budget.
Initial evidence remains empty for the first loop protocol. Other ingestion modes require an explicit protocol contract.

## API and storage scope

Let `A` be `/api/v1/projects/{project_id}/agents/{agent_id}` and `B` be `A/task-bindings/{task_binding_id}`.

| Route | Contract |
| --- | --- |
| `GET /api/v1/projects/{project_id}/task-definitions` | Authorized published definition references and supported/unavailable dependency status |
| `POST A/task-bindings` | `TaskBindingCreate` to `201 TaskBindingView`; idempotent publication and binding job |
| `GET A/task-bindings` | Paginated task bindings with definition versions and evidence status |
| `GET B` | Exact binding and active generation |
| `POST B/admissions` | Binding identity from path, purpose, case manifest, source manifest, and clock references |
| `B/candidates`, `B/activation`, `B/runs`, `B/views/{kind}` | Existing C10 verbs and payloads, scoped to the selected binding |

The starter UI can select a registered definition and its case/source preset. It must not hardcode an offer-only form or tool count.
Task-specific forms use the admitted JSON Schema. Unsupported schema controls use validated JSON input with server error paths.
C11 displays generic provenance and graph structure. Registered domain labels and units come from the task definition and schema.

Add `task_bindings` with its exact uniqueness key and scoped foreign keys.
Admissions, candidates, verification sessions, active pointers, assignments, runs, projections, and task views retain `task_binding_id`.
The active-pointer primary key is `(project_id, agent_id, task_binding_id)`.
Activation locks that binding's pointer and compares its own generation. It cannot advance another binding.
Packages and every downstream record must match the selected binding's task-definition digest and agent version.
C2 evidence contexts and C7/C11 cache/cursor bindings include this scope, even when source IDs or semantic labels overlap.
Conformance children inherit their parent's task binding. Their suite comes from that definition and tests the same common protocol.
Ordinary, verification, and conformance purposes retain their existing separation.
Compatibility and probe caches include the task's exact contracts and installed implementations. A shared host alone cannot justify reuse.

## Component implementation work

The older component specifications still contain offer-specific payloads. Apply these changes before implementing the shared services:

- Separate the general task/evidence submission path from the managed per-action dispatcher. OaK must validate a completion without requiring the working agent's native catalog or internal planner. Keep stronger trace and action-enforcement guarantees conditional on verified integration hooks.
- C0 and C9 resolve task definitions and bindings separately from agent creation. C10 scopes commands, rows, active pointers, and assignments to the selected binding.
- C1 gets domain terms and competency questions from the task definition. C2 gets source identity, request scope, mapping, units, and normalization from it.
- C3 and C4 resolve registered tool, function, and completion schemas through the binding. Keep offer sorting, eligibility rules, and field names in domain handlers.
- C5 selects the task's independent evaluator and metrics. A missing evaluator cannot fall back to the offer scorer.
- C6 binds verification, regression policy, repair, and activation to one task. Repairing one binding must preserve the other binding's package and queued or paused runs.
- C7 and C11 include the task binding in views and cached state. Forms, labels, and completion rendering come from its registered schemas.
- C8 runs the same bounded loop for both fixtures. Different task tools, functions, and deterministic policies must not add task-name branches or domain enums to that loop.

Verify these paths with two task definitions that differ in tools, vocabulary, request fields, results, and evaluator checks.
Run both through construction, verification, activation, execution, and repair. Declaration validation alone does not establish shared-service behavior.

## Extending tasks without a new core

1. Publish the task inputs, completion conditions, permitted evidence, development cases, independent evaluator, and test policy.
2. Bind the working agent's supported request/context and typed-submission interfaces. Resolve native-tool contracts only for an integration that observes or controls those tools.
3. Construct candidate schema, evidence interpretations, and functions from those inputs through the common OaK loop.
4. Resolve and verify generated artifacts, run the frozen task and regression suite, and review and activate the exact package.
5. Submit later task/evidence records against that package. The managed fixture additionally follows its registry, action, and mounting contracts above.

Existing handlers can support new definitions through data and artifact changes alone.
A missing supported operator or evaluator needs a reviewed implementation with tests; a new domain schema or composition uses the construction loop rather than a new generic dispatcher.
That work does not authorize changes to the generic dispatcher or a catch-all arbitrary-code loader.
Unsupported OWL constructs, effects, or runtime hooks remain explicit compatibility errors rather than silently weakened behavior.

## Required evidence of reuse

The following IDs retain the managed multi-task profile's requirements and tests. The general completion boundary additionally needs the record-submission acceptance cases above; these local checks do not establish it.

**MT-R01:** One agent version must admit multiple task definitions without task-specific changes to the core.
**MT-R02:** Every task instance and action must validate against its pinned binding's registered contracts.
**MT-R03:** Task-specific schemas, tools, functions, mappings, policies, and evaluators must remain outside generic loop logic.
**MT-R04:** Activation, repair, evidence, and scoring must remain isolated by task binding.
**MT-R05:** Adding task data must not grant unregistered execution capabilities or larger resource authority.

| ID | Test | Required observation |
| --- | --- | --- |
| MT-T01 | Bind offer selection and ticket classification to one agent catalog with different tool counts and result schemas | Both declarations validate through the same core; foreign task results and unavailable bindings fail |
| MT-T02 | Submit two different instances for each definition | Values vary without core changes; each instance retains its definition and input contract |
| MT-T03 | Run construction, verification, activation, execution, and repair for both task bindings | Identical core hashes; domain handlers and artifacts are explicit; no branch on task ID in core |
| MT-T04 | Repair binding A while binding B is queued or paused | B retains its active generation, package, evidence, admission, checkpoint, and denominator |
| MT-T05 | Reuse source IDs and semantic labels across task bindings | No foreign evidence, view state, or scorer result is accepted |

Local declaration tests establish only the first boundary checks. Full MT-T03 through MT-T05 service execution remains unrun.
