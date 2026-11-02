# Agent starting shape and compatibility boundary

Design version 0.4.8. Owner: C8, with C0, C4, C9, and C10 integration obligations.
The declaration validator is implemented. The managed host and service conformance probes remain unimplemented and unrun.

An agent application can contain many loops, tools, users, and memory stores.
The product's primary [worker interface](TASK-CONTRACT.md#general-task-and-evidence-handoff) supplies the query, readable schema, and callable function contracts to a ReAct working agent. The worker selects typed F calls, observes their results over Gq, and returns an answer. C3 composes executable functions beforehand. The worker need not write code or reveal its private planner. [OaK sections 3.2 and 3.3](https://arxiv.org/html/2608.22974v1#S3.SS3).

The paper-aligned runtime must make the frozen kernel the sole task-data channel. A host may remain internally replaceable, but unrestricted native retrieval, delegates, and task-data memory cannot bypass that boundary. Schema text alone does not enforce it. [OaK section 3.1](https://arxiv.org/html/2608.22974v1#S3.SS1).

This document defines the existing managed fixture declaration and the proposed services that would execute it. Its native catalog, scripted driver, and incremental evidence flow test local contracts; they are not the production ReAct implementation. The broader live-API and record-submission integrations are deferred adaptations. No current declaration check establishes those runtimes.

## Three separate identities

| Identity | First value | Meaning |
| --- | --- | --- |
| Loop profile | `sequential_readonly/1` | One typed action at a time, bounded execution, read-only native tools, controlled finalization |
| Task profile | `offer-selection-v1` | Search accommodation offers, obtain missing evidence, and select one supported offer |
| Host implementation | Versioned C8 LangGraph workflow artifact | Executable code that implements the loop profile |

`CreateAgent.agent_class` is the existing wire name for the task profile. It does not identify a universal agent architecture.
The server must match it to `AgentStartingShape.task_profile` and expose the distinct loop profile through the shape artifact.
A registry key names a permitted implementation. An artifact hash identifies its exact bytes. Neither replaces executed conformance evidence.

## The user starting point

After login and project creation, the browser submits this body to `POST /api/v1/projects/{project_id}/agents`:

```json
{
  "name": "Offer selector",
  "agent_class": "offer-selection-v1",
  "configuration": {
    "kind": "fixture_template",
    "template_id": "offer-selection-v1",
    "template_version": "0.1.0"
  }
}
```

The server resolves the [complete starting declaration](examples/agent-starting-shape.json).
The [strict model](../../../oak_contracts/agent_shape.py) defines its fields and exports the [JSON Schema](examples/agent-starting-shape.schema.json).
The declaration contains real profile names and binding keys. It contains no invented artifact hashes or ready flag.

C9 publishes `AgentVersionPayload.starting_shape_ref` with the resolved task, native manifest, host, runtime, and budget references.
`AgentView.starting_shape_ref` lets the user inspect the declaration for the returned version.
C10 stores those bytes before publishing the version. C8 resolves profile names to exact registered contract artifacts and implementation hashes.
Missing implementations prevent binding verification. They do not turn into a description-only callable.

The shape uses `TaskRequest@0.4.0` and `FinalSelection@0.4.0` as aliases for C0 and C4's specified models.
The native aliases are `fixture.search_offers.input@0.1.0`, `fixture.search_offers.output@0.1.0`,
`fixture.get_offer_details.input@0.1.0`, and `fixture.get_offer_details.output@0.1.0`.
The registry must resolve each alias to the corresponding immutable schema before issuing a binding receipt.
The current declaration parser does not implement or prove these runtime contracts.

The fixture's unresolved kernel port names `select_eligible_offers`, `offer-selection-input/1`, and `offer-selection-result/1`. These are fixture contracts, not universal function names or signatures.
It deliberately has no bundle or package reference before construction.
At mount, C8 resolves those references from the sealed package and checks the exact contracts.

## Invariants for the managed integration profile

These are compatibility requirements for the managed per-action integration profile. They remain mandatory when that profile is selected. The primary worker interface has its own kernel-tool and task-data isolation obligations; passing this native-tool fixture does not establish the paper's inference algorithm.

| Invariant | Concrete boundary | Owner and rejection |
| --- | --- | --- |
| **SH-R01:** Every run must pin scope, task, configuration, and treatment dependencies. | Task, project, agent version, run, package, clock, source policy, and implementation hashes are pinned | C0/C10/C8 reject mismatched references before dispatch |
| **SH-R02:** Every decision and terminal outcome must satisfy the admitted typed boundary. | A decision yields an `ActionRequest`; termination yields C4's typed result or explicit terminal failure | C8/C4 reject an opaque final-answer-only interface |
| **SH-R03:** Every visible tool must have verified executable bindings and exact contracts. | Each visible tool has an exact input contract, output contract, effect, registered callable, and version | C8 rejects descriptions without registered code and successful probes |
| **SH-R04:** Each native observation must preserve actual call identity, inputs, outputs, sources, and time. | Each native result retains actual arguments, operation identity, response bytes, source identity, and timestamps | C4 rejects unmatched or unrecorded observations |
| **SH-R05:** Every source interpretation must pin identity, scope, units, freshness, conflict, absence, and completeness rules. | C2's mapping pins identity, task scope, units, freshness, conflict, missing-value, and completeness rules | C0/C2 reject missing mappings; signatures alone cannot supply meaning |
| **SH-R06:** Required observation ingestion must finish before a dependent function reads its snapshot. | C4 completes required ingestion before F reads the resulting snapshot | C4 blocks a dependent call after incomplete ingestion |
| **SH-R07:** Every final result must pass the declared C4 release boundary. | Every final result passes C4; guarded mode applies its checker before release | C4 rejects finalization bypass; no silent downgrade to optional mode |
| **SH-R08:** Restart must preserve operation identity, budgets, cancellation, and terminal records. | Saved decision and operation IDs, budgets, cancellation, and terminal records survive restart | C8/C10 reconcile before another action; missing code blocks resume |
| **SH-R09:** Every task-relevant tool, delegate, retrieval source, and memory channel must be declared and observed. | All tools, delegates, retrieval, and memory that can affect the task are declared and observed | The first profile rejects extra channels and cross-run memory |
| **SH-R10:** Readiness must require server-issued evidence for the exact registered implementation and contracts. | Server probes exercise the exact registered implementation and contract versions | Client capability claims cannot establish readiness |

Input and output schemas are structural contracts. They cannot establish source truth, complete search coverage, or independent task success.
C5 remains the task evaluator. A successful mount, valid OWL schema, or completed loop cannot replace its assessment.

## Restrictions of the first profile

The first attachment is `managed`; its driver is `scripted_fixture`.
It admits exactly the two native fixture tools at `0.1.0`, plus the declared kernel function port.
Each decision is `native`, `function`, or `finalize`. One action can be in flight.
The default execution mode is `optional_functions`; `guarded_requirements` requires its additional release checks.
These existing modes describe the fixture and live-API adaptation. Neither mode by itself establishes the paper's sole-kernel data channel.

Initial observation IDs must be empty. Evidence becomes available only after an exact case, tool, version, and argument match.
No conversation memory, hidden retrieval, delegate, parallel branch, arbitrary endpoint, executable upload, or external write is admitted.
Unknown or absent fields remain unknown. They do not become passing constraints.

The starter allows at most 12 decisions and 900 seconds per run.
C10 sets `deadline_at` from the run creation time and the smaller applicable admitted time limit.
Queue delay counts against that deadline. Restart cannot extend it.
Decision limits include invalid decisions and rejected finalization. The declared bounds do not themselves enforce runtime limits.
Construction has its own C0 budget and three-round ceiling. It cannot borrow a fresh run budget to evade that ceiling.

The broader C8 document describes a future fixed-model driver. `oak-agent-shape/1` rejects that driver.
A live driver needs a new registered shape profile, explicit execution admission, enabled thinking, actual provider settings, and budget authorization.
This prevents a later feature from appearing supported merely because its name exists in a design document.

## Readiness is a chain of evidence

Do not store an independent `agent.ready` boolean or create a second onboarding workflow engine.
The API derives progress from the existing immutable records. The interface must show failed, missing, and unrun evidence.

| Stage | Required record | Permitted next operation |
| --- | --- | --- |
| Configuration registered | C9 immutable version, shape, and resolved references | Inspect configuration and its scheduled binding verification |
| Bindings verified | C8 server-issued `RegistryCapabilityReceipt` with passed pre-kernel probes | C0 may admit this implementation |
| Task admitted | C0 receipt and public `StarterManifest` | Create the initial or repaired candidate |
| Candidate sealed | C6 immutable package with exact dependencies | Request candidate verification through the trusted worker |
| Candidate verified | Trusted `VerificationSet` for that candidate, policy, and suite | Owner review and activation |
| Kernel active | C6 activation receipt and current generation | Request a normal run |
| Run mounted | C8 mount receipt for the exact run, implementation, package, scope, and checkpoint | Dispatch that run through C4 |

C9's server preset publication schedules the pre-kernel binding probe job through C10's existing command queue.
`AgentView.binding_job_id` identifies that job; its typed result is a `RegistryCapabilityReceipt` artifact.
The agent can exist while the job is pending or rejected. Admission returns `bindings_not_verified` until the matching receipt passes.
C0 reads the receipt. Admission itself does not invoke tools or models.
Registry probes use dedicated public conformance fixtures, never evaluator-private cases or run evidence.

The shared metadata and receipt services supply this sequence. No generic adapter discovery, plugin executor, or readiness service is required.
C8 rechecks the binding fingerprint at mount. C10 rechecks permissions and package eligibility at run creation.
Candidate verification can mount a sealed inactive package only through its typed internal command.
It receives no permission to activate that package or to change a held-out run.

## Required server probes

`HostCapabilities` describes required properties. It is not evidence that they hold.
`CapabilityProbeReceipt` records `probe_id`, `phase`, `implementation_fingerprint`, `suite_ref`, `input_refs`, `observed_refs`, `status`, and `diagnostic_refs`.
`phase` is `registry` or `mount`; `status` is `passed`, `failed`, `error`, or `not_run`.
The fingerprint is the hash of the canonical ordered shape, workflow, registry, contract, hook, and runtime hashes.
Registry fingerprints include no future package hash. Mount fingerprints also include the package hash.
The parent mount receipt binds the exact run scope.
All fields use shared scalar and artifact types. `probe_id` comes from the fixed table below, not client input.

| Probe ID | Phase | Required observed behavior |
| --- | --- | --- |
| `native_contracts` | registry | Both callables run on public fixtures; wrong input, wrong output, and wrong arguments fail before evidence acceptance |
| `hook_registration` | registry | Required C4 hook and function-dispatch implementation keys resolve to the pinned registered code; unknown keys fail |
| `correlated_observation` | mount | Callback contains the actual operation, arguments, and response; loss blocks; a duplicate cannot ingest twice |
| `dispatch_authority` | mount | Unknown tools, hidden channels, and direct-finalization bypass are rejected |
| `restart_reconciliation` | mount | A crash after dispatch reuses the committed result; lost or changed implementation code blocks resume |
| `scope_and_limits` | mount | Foreign scope, a thirteenth decision, parallel dispatch, and an expired deadline are rejected |
| `package_binding` | mount | Exact schema, function, mapping, policy, registry, runtime, and run references match; incompatible or missing artifacts reject mount |
| `observation_barrier` | mount | Function execution cannot read before the native observation commits under the mounted interpretation |
| `terminal_routes` | mount | Typed finalization reaches C4; guarded mode blocks unmet requirements; optional mode retains its declared semantics |

Registry probes invoke native callables on dedicated fixtures and resolve registered hook code. They do not execute a complete C4 task.
This pre-kernel evidence cannot establish observation barriers, guards, or restart behavior.
Package probes use the [nonrecursive conformance contract](MOUNT-CONFORMANCE.md).
C8 first prepares bindings. C10 records isolated `host_conformance` child runs and server-only grants.
The installed pytest suite exercises the same handlers through that staged path, without requesting another full mount.
Only passing probes permit a ready mount for ordinary or candidate-verification execution.
They cannot populate a task's evidence snapshot or consume its source responses.
Cache reusable probe receipts by fingerprint, probe ID, and suite hash through the existing artifact index.
The cache key also includes the registered pytest runner hash. A grant or child run is never reused for another mount.
Mount must still check exact scope, current authorization, artifact availability, and checkpoint identity each time.
Missing, failed, errored, or unrun required probes reject readiness. Browser-supplied receipts and booleans are never accepted.

## Storage, ownership, and extension gate

PostgreSQL stores agent versions, binding jobs, admissions, candidate verification sessions, assignments, runs, and operation identities.
Immutable artifacts store the shape, contract schemas, mappings, raw responses, and probe receipts.
LangGraph's selected checkpointer stores bounded run state. Neo4j stores C2's versioned domain projections.
Use C10's existing stores and transactions. A second registry database or custom adapter framework is unnecessary.

An external integration claiming this managed profile's stronger guarantees starts with one named runtime and a concrete hook mapping to these boundaries.
Its design must identify who controls dispatch, receives actual results, blocks finalization, records hidden channels, and reconciles restart.
Only after its implementation passes the same conformance obligations can a new profile admit it.
An opaque API that accepts a prompt and returns prose does not supply these per-action controls or the primary typed F-call interface. Record submission and completion validation would be a separate deferred adaptation. They cannot establish kernel-mediated task reasoning or control hidden task-data channels.

The 30 local shape checks validate the declaration and generated schema only.
They do not run the LangGraph host, the native dispatcher, source mapping, authentication, or schema-repair verification.
Production acceptance remains in C8, C0, C6, C9, C10, and C11. Their requirements and tests remain linked in the native StrictDoc graph.
