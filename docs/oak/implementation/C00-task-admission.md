# C0: Task and construction-policy admission

Design version 0.4.7. November 2, 2026. Proposed service contract.

This document defines the fixed construction-policy admission and retains the first engineering fixture's narrower contract. It does not select a scientific benchmark or authorize model execution.

The [implementation baseline](README.md) controls shared envelopes, storage rules, and delivery gates.

The [fixed construction policy](../00-task-surface-and-corpus.md#fixed-construction-policy) governs production construction campaigns. The [example package](../examples/README.md) supplies synthetic records.

The requirements use ASD-STE100 principles. Full conformity with the standard remains unverified.

## Purpose and boundary

An agent must distinguish an eligible offer from a search result. Search results can contain capacity violations, stay violations, and missing availability.

C0 admits a complete, immutable task definition. It separates domain material, observations, case assignments, and evaluator answers.

The first agent class is `offer-selection-v1`. Its host loop can inspect recorded offers and request offer details.

An agent record belongs to one project. It identifies a configured loop, its native tools, and its kernel binding.

C0 does not implement the host loop. C8 owns that loop. C4 owns its observation and function-call protocol.

The task, tools, and loop restrictions below apply to the managed offer fixture. The general [task/evidence handoff](TASK-CONTRACT.md#general-task-and-evidence-handoff) does not require the working agent's planner or full native catalog. Its construction admission needs the supplied corpus or a compatible evidence-collection interface, independently checkable task contracts, and the policy described below.

| Item | Selected value |
| --- | --- |
| Task | Select one observed offer that satisfies the request |
| Native tools | `fixture.search_offers@0.1.0`, `fixture.get_offer_details@0.1.0` |
| Required distinctions | Occupancy, minimum nights, availability, inclusive total price, request scope |
| Tool effect | Read only |
| First execution source | Saved synthetic responses with exact call matching |
| Initial trial evidence | Empty; seeded observations and cross-run memory are unsupported |
| Missing evidence | Unknown; never a false value or an inferred passing value |
| Unsupported result claims | Booking, payment, global cheapest offer, exhaustive market search |
| Native adapters | Only the fixture replay binding in the first release |
| Construction access | Declared development requests, domain material, and development responses |
| Trial access | The current request and responses obtained through permitted calls |
| Frozen inference | New observations may change G; S, F, O, and interpretation dependencies remain pinned |

The repository's current tool manifest describes contracts. It does not register executable callables.

A callable registry receipt is therefore required before execution admission. A correct tool name alone is insufficient.
Admission uses C8's preconstruction `RegistryCapabilityReceipt`, not a kernel-specific `HostMountReceipt`.
The complete function binding is required at run mount, after the candidate package exists.

## Normative requirements

1. **C0-R01:** C0 must verify project membership before it resolves an input reference.
2. **C0-R02:** C0 must verify that the agent belongs to the requested project.
3. **C0-R03:** C0 must reject tools outside the two selected native contracts.
4. **C0-R04:** C0 must preserve the distinction between source facts and human requirements.
5. **C0-R05:** C0 must exclude private evaluator data from builder manifests.
6. **C0-R06:** C0 must reject overlapping development, selection, and held-out case identities.
7. **C0-R07:** C0 must preserve every assigned case, including failures and timeouts.
8. **C0-R08:** C0 must reject missing or incompatible artifact hashes before dispatch.
9. **C0-R09:** C0 must save admission results without calling models, tools, or C1 through C5.
10. **C0-R10:** C0 must require a separate authorized run request before execution.
11. **C0-R11:** C0 must reject held-out execution with an empty assigned population.
12. **C0-R12:** C0 must reject live model execution without complete model settings and resource limits.
13. **C0-R13:** C0 must require enabled thinking for declared LLM comparisons.
14. **C0-R14:** C0 must reject credential values in exported manifests and diagnostic payloads.
15. **C0-R15:** C0 must reject seeded evidence and unverified starting-shape bindings for the first loop profile.
16. **C0-R16:** C0 must bind each construction campaign to a complete immutable policy, concrete budgets, model settings, data splits, and sealed construction corpus before C1 dispatch.
17. **C0-R17:** C0 must reject builder access to private evaluator inputs, undeclared corpus changes, and runtime observations silently substituted for the sealed construction corpus.

## Fixed construction-policy admission

Production construction uses `construction_policy_ref` to identify the immutable `oak-construction-policy/1` policy. The admission and builder manifest retain that reference and the sealed corpus reference. This is a proposed production amendment, not an added field accepted by the existing `0.4.0` fixture parser. The saved fixture's three-round budget and `report_only` sampler remain teaching settings; they do not configure the general policy.

Map existing internal `split` values explicitly: `development` is official train construction/repair/regression, `selection` is official dev final validation, and `held_out` is official test. The older name `development` does not authorize official dev data in the builder. A custom dataset must register equivalent disjoint roles before admission.

C0 validates the following before construction becomes executable:

| Pinned policy input | Admission rule |
| --- | --- |
| Task and population | Exact task/scope, case versions, characteristic definitions, and independent evaluator; use official train for construction, dev for validation, and test for held-out evaluation, with disjoint identities |
| Sources and acquisition | Supplied benchmark corpora are versioned directly; otherwise pin a separate collection role's prompt, model, thinking settings, permitted source access, stop rules, and evidence-recording interface independently of the working agent under test |
| Capability context | For API collection, pin public tool/API IDs, descriptions, argument and return contracts, effects, preconditions, limits, pagination, source scope, documentation versions, and availability evidence through the collector interface |
| Collection behavior | The separate collector selects retrieval calls from the task-visible query and permitted documentation under its fixed policy. Auth/session setup follows the access policy; collection cannot perform business writes, use hidden required-API lists, inspect solutions/private graders, or obtain privileged database dumps |
| Corpus seal | Preserve task-scoped content, source identity/time, actual requests/responses, pagination state, conflicts, failed collection attempts, and missing evidence. Keep credentials and evaluator-private values out of exported builder material |
| Construction schedule | Seed `42`, at most five outer rounds, and `max(1, ceil(0.20 * N_h))` cases from each nonempty training stratum of size `N_h`, without replacement within the round; pin sampler version and per-round seed derivation |
| Regression policy | Resolve C6's separately frozen broad suite plus required boundary, interaction, and known-regression cases; changing construction samples cannot shrink that verification suite |
| Models and resources | Pin actual provider/model versions, enabled thinking settings, collector/builder/judge configurations, and finite per-case and campaign call, token, time, and cost limits |
| Acceptance | Pin complete-task success metric, release thresholds, required gates, repetitions, and stopping rule before outcomes; missing values or unresolved bindings block execution readiness |

The sampling numbers are engineering defaults for this policy. Task-specific budgets and acceptance thresholds must have concrete admitted values; C0 does not invent them from those defaults. Required strata that have no eligible cases remain coverage gaps. Store the complete round schedule before execution so retries cannot draw an easier population.

For API collection, C0 first validates the collection plan and its policy hash without calling a model or source. A separately authorized collection runner executes that plan through the permitted source interface, and C2 admits its evidence. C0 then verifies and seals construction admission against the resulting corpus manifest before C1 can start. This uses existing admission and evidence ownership rather than adding another product component. A supplied corpus can proceed directly to this seal. Collection exhaustion or failure remains explicit in the corpus record and assigned denominator; it cannot trigger case replacement or unbounded collection. Required evidence or coverage gaps block the affected readiness gate.

Corpus acquisition is independent of the plugged-in working agent. C0 pins the collection runner before worker comparison; neither worker internals nor candidate outputs select its sources or calls. The same task receives the same sealed corpus when comparing workers. Changing the worker cannot change the collector, its budget, or the corpus. If collection and task execution use the same model, they still have separate role identities, contexts, traces, and resource reservations. The collection role prepares evidence; the working agent later performs the actual task.

Keep [capability context and observed calls](../00-task-surface-and-corpus.md#capability-context-and-observed-calls) separate in admission. `advertised` means documentation describes a capability; `bound` means a verified executable connection exists; `observed` identifies an actual recorded call and its outcome, including failure. No state implies that the returned task facts are correct. The fixed documentation-retrieval policy selects context from task-visible instructions and public documentation, never hidden required-API lists. Count documentation retrieval, failed calls, and successful collection within the admitted budgets. Preserve actual arguments, raw response or error references, task/world state, source receipts, and provenance status for each observed call.

This API-collection requirement does not require planner introspection or a private host inventory. Supplied-corpus and opaque-submission integrations can use supplied capability documentation when available and report absent metadata explicitly. C1 uses it to propose meanings and evidence needs, not to invent facts. C3 still composes admitted generic operators; an advertised native API neither creates an executable OaK function nor authorizes a direct provider wrapper. Missing evidence can identify a supported retrieval capability for the working agent without claiming that call has occurred.

The sealed construction corpus remains fixed for the campaign. Mutable API trials still start from the same pinned initial world for paired comparisons and collect fresh task-scoped observations under the admitted acquisition policy. Those runtime observations remain separate from the builder corpus; a response-only replay cannot stand in for unavailable calls or post-write state. Adding runtime evidence to construction requires a new corpus and campaign version with affected comparisons repeated. C0 rejects silent append, replacement, or source-snapshot changes under the old policy reference.

Source descriptions identify capabilities and meanings; response payloads provide observed facts. A source reference asserted by an agent is not automatically verified provenance. C0 preserves that distinction, and C2 applies the admitted evidence policy. Model weights stay fixed throughout collection, construction, refinement, and evaluation.

## Public contracts

The remaining payload tables describe the earlier managed engineering profile. Their strict fixture-specific fields are not the universal interface for `oak-construction-policy/1`.

All objects use strict Pydantic validation. Unknown fields fail validation. Integer fields reject booleans and numeric strings.

The shared envelope supplies invocation, attempt, operation, producer, and run correlation fields. The fields below define the component payload.

JSON dates use `YYYY-MM-DD`. Timestamps use UTC with an explicit offset. Identifiers use nonempty strings with a maximum of 128 characters.

Use the complete `ArtifactRef` in [shared contracts](CONTRACTS.md#artifactref).
Its required fields include artifact identity, kind, digest, media type, payload version, and producer version.

C10 resolves the reference within the authorized project. A client cannot supply an arbitrary filesystem path or remote fetch URL.

### AdmissionRequest

This is an internal component payload. The browser uses C10's smaller `AdmissionCreate` preset request.
C10 resolves C9's pinned fixture manifest and server-only evaluator binding before constructing this payload.

| Field | Type | Required behavior |
| --- | --- | --- |
| `contract_version` | Literal `0.4.0` | Match the shared service contract |
| `message_type` | Literal `task_admission_request` | Identify this component payload |
| `project_id` | Identifier | Match the authenticated project scope |
| `agent_id` | Identifier | Resolve a project-owned `offer-selection-v1` configuration |
| `agent_version` | Positive strict integer | Resolve this exact immutable C9 version and its binding command |
| `agent_config_ref` | Artifact reference | Match the saved configuration for that version |
| `request_id` | Identifier | Stable client request identity |
| `idempotency_key` | String, 1 to 128 characters | Bind to the canonical request digest and principal |
| `purpose` | `engineering_replay`, `model_development`, or `held_out_evaluation` | Select the corresponding admission gate |
| `task_surface_ref` | Artifact reference | Pin task definition and domain requirements |
| `tool_manifest_ref` | Artifact reference | Pin native tool contracts |
| `callable_registry_ref` | Artifact reference | Pin actual fixture binding implementation and capability receipt |
| `domain_material_refs` | Array of artifact references | Exclude private evaluator material |
| `case_manifest_ref` | Artifact reference | Pin case identity, split, and request references |
| `observation_manifest_ref` | Artifact reference | Pin source response identity and payload references |
| `source_policy_ref` | Artifact reference | Pin source scope, time policy, identity, and interpretation rules |
| `evaluation_public_ref` | Artifact reference | Expose evaluator identity, metric, and contract only |
| `evaluation_private_ref` | Artifact reference | Resolve through the protected evaluator access path |
| `sampling` | `SamplingConfig` | Admit only the declared eligible population |
| `budget_ref` | Artifact reference | Pin enforced operation, time, and resource limits |
| `model_config_ref` | Artifact reference or null | Required for model execution; null for deterministic replay |
| `clock` | `ClockConfig` | Separate scenario time from actual execution time |

The authenticated principal comes from C9. The request body cannot replace that principal or supply membership claims.
The version's configuration, starting shape, host, and binding receipt must agree exactly.
The admission record preserves that version. Candidate and run requests cannot substitute a newer agent version.

`engineering_replay` permits deterministic recorded-response execution. It does not permit an LLM call or a task-provider call.

`model_development` requires explicit execution authorization, a complete model configuration, and development-only assignments.

`held_out_evaluation` also requires a frozen package, a registered nonempty assignment set, and a pinned independent evaluator.

Admission stores authorization requirements. It does not grant execution permission by itself.

### TaskRequest

| Field | Type | Meaning |
| --- | --- | --- |
| `task_request_id` | Identifier | Stable identity of this request |
| `case_id` | Identifier | Identity in the admitted case manifest |
| `split` | `development`, `selection`, `held_out`, or `engineering` | Data-use boundary |
| `request_text` | String, 1 to 4096 characters | User-visible request |
| `city` | String, 1 to 128 characters | Exact fixture city |
| `check_in` | Date | First stay date |
| `check_out` | Date | Exclusive final stay date |
| `party_size` | Strict integer, 1 to 100 | Requested guest count |
| `budget_minor` | Strict integer, 0 to 100000000 | Inclusive total budget in currency minor units |
| `currency` | Literal `USD` | First class supports one currency |
| `initial_observation_ids` | Empty array only | First profile has no seeded evidence; nonempty input is rejected |
| `permitted_response_ids` | Unique identifier array | Responses available through matching tool calls |
| `coverage_tags` | Unique string array | Declared design coverage, not a task success label |

`check_out` must follow `check_in`. Stay length is the integer calendar-date difference. Time zones do not change this calculation.

The first class accepts stays from 1 through 30 nights. Wider bounds require a new task-contract version.
The [starting shape](AGENT-SHAPE.md) pins the managed loop profile separately from this task profile.
Its per-run bounds are at most 12 decisions and 900 seconds. C10 sets an absolute deadline before queue insertion.
C0 reads C8's binding receipt; a pending, rejected, missing, or mismatched receipt returns `bindings_not_verified`.
It never executes the binding probes during admission.

The legacy fixture uses `budget_total: 420`. Its admission adapter converts that value to `budget_minor: 42000`.

The adapter uses exact decimal arithmetic. It rejects negative values, excess decimal places, and unsupported currencies.

This conversion has its own pinned version. It does not silently change the stored source record.

`permitted_response_ids` are replay metadata. The host does not receive their payloads before matching calls.

### SamplingConfig and ClockConfig

`SamplingConfig` contains `method`, `seed`, `rounds`, `cases_per_round`, and `coverage_policy`.

`method` is `seeded_without_replacement`. `seed` is a strict unsigned 32-bit integer. Counts are positive strict integers.

`coverage_policy` is `report_only`. C0 rejects a requested sample larger than the eligible population.

For reproducibility, C0 sorts eligible case IDs by UTF-8 bytes before sampling. Each round uses a saved, implementation-versioned random stream.

C0 records the stream version, seed, round number, selected IDs, and order. Repeated rounds may select the same case.

`ClockConfig` contains `mode`, `scenario_now`, and `clock_version`. `mode` is `fixed_fixture` for the first class.

`scenario_now` is an explicit fixture timestamp. The source policy defines permitted source age relative to that timestamp.

Actual `received_at` and `replayed_at` remain execution timestamps. They cannot update source freshness.

The historical fixture contains synthetic future dates. A real current-time freshness claim would therefore be invalid.

### AdmissionReceipt

| Field | Type | Meaning |
| --- | --- | --- |
| `admission_id` | Identifier | Server-generated admission identity |
| `project_id`, `agent_id` | Identifiers | Authorized ownership scope |
| `agent_version` | Positive strict integer | Pin the admitted C9 version |
| `agent_config_ref` | Artifact reference | Pin that version's resolved configuration |
| `request_digest` | SHA-256 digest | Immutable canonical request identity |
| `status` | `succeeded`, `failed`, or `cancelled` | Terminal process outcome |
| `admission_status` | `accepted` or `rejected` | Separate admission outcome |
| `purpose` | Admission purpose enum | Scope of the accepted specification |
| `manifest_ref` | Artifact reference or null | Present only after successful immutable publication |
| `builder_manifest_ref` | Artifact reference or null | Safe construction projection |
| `evaluator_binding_id` | Identifier or null | Protected evaluator binding, without private contents |
| `case_counts` | Map of split to nonnegative integer | Full population counts |
| `capability_receipt_ref` | Artifact reference or null | Evidence of registered tool bindings |
| `starter_manifest_ref` | Artifact reference or null | Public preset actions, verification inputs, and registered assignments for an accepted engineering admission |
| `diagnostics` | Array of structured diagnostic objects | Errors, warnings, and unsupported coverage |
| `execution_authorized` | Literal false | Admission does not dispatch a run |
| `created_at` | UTC timestamp | Receipt time |

Each diagnostic contains `code`, `owner`, `stage`, `operation_id`, `field_path`, `artifact_id`, `retryable`, and `message`.

A completed validation can report `status: succeeded` and `admission_status: rejected`. Storage failure reports `status: failed` and `admission_status: rejected`.

### StarterManifest

An accepted engineering admission publishes `StarterManifest` with profile `oak-starter/1`.
It contains `admission_id: Id`, `agent_version: positive_integer`, `initial_change_ref`, `test_policy_ref`, and `suite_ref`.
Those three references use `ArtifactRef` and resolve to approved project-visible preset artifacts.
It also contains `assignments: StarterAssignment[]` and `callable_receipt_ref: ArtifactRef`.
Each `StarterAssignment` contains `assignment_id: Id`, `case_id: Id`, `condition_id: Id`, and `repetition: positive_integer`.

C0 registers these assignments before publishing the manifest. The preset supplies their fixed engineering condition and repetition.
C11 uses this manifest to create the initial candidate, start verification, and select a registered run assignment.
It never invents IDs, policy references, or evaluator bindings. Missing required preset artifacts reject admission.
The manifest contains no private answers, private evaluator references, or unobserved source payloads.

Client diagnostics omit private answer values and foreign-project identifiers. Restricted internal diagnostics preserve sufficient evidence for authorized debugging.

## Admission algorithm

1. C9 authenticates the principal and resolves project membership.
2. C0 verifies the agent's project and selected class.
3. C0 reserves the scoped idempotency key through C10.
4. C0 compares an existing request digest before any repeated work.
5. C0 resolves authorized artifacts and verifies their byte hashes.
6. C0 parses strict contracts and verifies the fixture callable receipt.
7. C0 validates case identities, split separation, and source-response ownership.
8. C0 validates sampling, budgets, clock, model settings, and execution prerequisites.
9. C0 creates separate builder and evaluator manifests.
10. C0 writes immutable manifest blobs through C10.
11. C10 commits artifact indexes, admission receipt, and idempotency result in one metadata transaction.
12. C0 returns the saved receipt without dispatching component work.

An identical retry returns the original receipt. A reused idempotency key with different bytes fails with `idempotency_conflict`.

Blob writes precede the metadata commit. A failed transaction can leave an unreferenced blob, but cannot publish a partial admission.

C10 may remove unreferenced blobs after its retention delay. A successful receipt must reference durable, verified bytes.

## Storage and access contracts

| Data | Authoritative storage | Writer | Permitted readers |
| --- | --- | --- | --- |
| Task definitions and source policy | Content-addressed blobs plus PostgreSQL artifact index | C0 through C10 | Authorized project users and admitted component workers |
| Admission status and idempotency result | PostgreSQL | C0 through C10 | Project users with task-read access |
| Case identity and split registry | PostgreSQL | C0 through C10 | Trusted admission and assignment services |
| Raw source responses | Content-addressed blobs | Admission or observation intake through C10 | C2 and run-scoped consumers under manifest permissions |
| Private evaluator configuration | Protected blob namespace and metadata binding | Trusted evaluator admission | C5 evaluator identity only |
| Builder manifest | Content-addressed blob | C0 through C10 | C1, C2, C3, and authorized development workflow |
| Domain graph | Neo4j | C2 only | Version-bound graph readers |
| Local harness admission state | SQLite | Local harness | Explicit substitute-test participants |

Project scope is mandatory on every metadata row and lookup. Agent scope is mandatory for agent-owned artifacts and admissions.

An artifact hash proves byte identity. It does not grant access to those bytes.

The published synthetic evaluator file is illustrative, not secret. Production permissions must still prevent evaluator material from reaching builder contexts.

C0 never writes Neo4j. It supplies references and scope to C2.

## Failure and retry rules

| Code | Cause | Response and retry rule |
| --- | --- | --- |
| `unauthenticated` | No valid session | Reject before artifact lookup |
| `scope_not_found` | Project or agent unavailable to principal | Reject without revealing foreign ownership |
| `unsupported_agent_class` | Another loop or tool set | Reject; require a separately versioned design |
| `initial_evidence_unsupported` | Nonempty initial observations or undeclared memory | Reject before admission; first profile requires tool-obtained evidence |
| `bindings_not_verified` | Required C8 registry receipt is absent, pending, rejected, or mismatched | Reject admission without tool or model dispatch |
| `unresolved_callable` | Contract exists without an executable binding | Reject execution readiness |
| `artifact_hash_mismatch` | Saved bytes differ from the reference | Reject; do not repair the digest silently |
| `split_overlap` | A case belongs to incompatible populations | Reject the entire admission |
| `private_evidence_leak` | Builder projection includes evaluator-only input | Reject publication and preserve a restricted diagnostic |
| `source_scope_mismatch` | Response dates, provider, case, or account disagree | Reject the response binding |
| `sample_exceeds_population` | Requested sample is too large | Reject; do not reduce the requested size |
| `empty_evaluation_population` | No assigned held-out cases | Reject evaluation admission |
| `missing_model_configuration` | Model execution lacks pinned settings | Reject execution readiness |
| `thinking_disabled` | LLM comparison disables thinking | Reject the comparison configuration |
| `idempotency_conflict` | Same key, different canonical request | Reject with a conflict response |
| `storage_unavailable` | Metadata or blob store unavailable | Retry the same key after recovery |

Validation errors consume no model budget. Admission attempts still create audit events and timing records.

Admission retries do not retry provider calls because admission cannot make provider calls.

## Adversarial design decisions

| Challenge | Decision | Reason and remaining test |
| --- | --- | --- |
| Start with an arbitrary host adapter | Select one bounded fixture loop first | A generic tool description cannot establish callbacks, scope, or dispatch ownership |
| Begin with a full travel planner | Start with offer selection | This class exercises the target distinctions with independently inspectable expected results |
| Treat the existing fixture as a benchmark | Label it engineering verification | One development case and an empty held-out file provide no generalization denominator |
| Let builders inspect expected answers | Give builders a separate manifest | Correctness must remain independently testable |
| Load every saved response before a trial | Reveal responses only after matching calls | Preloading would remove the missing-evidence decision being tested |
| Use replay time as evidence time | Pin a scenario clock and preserve source time | Replay does not refresh provider evidence |
| Accept any JSON field with a compatible name | Require versioned source mapping | Matching spelling does not establish meaning, units, or scope |
| Store all artifacts in Neo4j | Store metadata and immutable blobs separately | Domain relationships do not replace access control, job state, or artifact integrity |

These decisions concern the first implementation. A broader agent class requires a separate capability contract and its own fault tests.

## Independent acceptance cases

The tests below are required service cases. A local harness receipt establishes only the cases that it explicitly executes.

| Test ID | Input or injected fault | Required observation |
| --- | --- | --- |
| C0-T01 | Valid synthetic package and registered replay tools | One immutable admission; zero model, provider, and graph operations |
| C0-T02 | Agent ID belongs to another project | Generic scope rejection before artifact resolution |
| C0-T03 | Duplicate case or cross-split case identity | No admitted manifest or run assignment |
| C0-T04 | Held-out file contains zero cases | `empty_evaluation_population`; no denominator invented |
| C0-T05 | Evaluator-private canary in protected input | Canary absent from builder blobs, prompts, logs, and error payloads |
| C0-T06 | Missing callable registration | `unresolved_callable` despite a valid JSON tool schema |
| C0-T07 | Repeated request with the same key and digest | Same receipt identity; one committed admission |
| C0-T08 | Same key with changed case bytes | `idempotency_conflict`; original receipt remains unchanged |
| C0-T09 | Failed metadata commit after blob write | No visible partial admission; retry commits once |
| C0-T10 | Wrong replay arguments or absent page token | Explicit unavailable-response result; no unrelated payload |
| C0-T11 | Detail response has another stay or party | Scope rejection; availability remains unknown |
| C0-T12 | Missing minimum nights and availability | Unknown diagnostics; no eligible offer assertion |
| C0-T13 | Capacity two for a party of four | Capacity violation remains visible to the checker |
| C0-T14 | Minimum stay three for a two-night request | Stay violation remains visible to the checker |
| C0-T15 | Conflicting same-scope source values | Conflict retained; no arbitrary last-value selection |
| C0-T16 | Search response has `next_page_token` | No exhaustive absence or global cheapest claim |
| C0-T17 | Same inputs, sampler version, seed, and round | Identical sample IDs and order |
| C0-T18 | Source timestamps changed only by replay | Freshness result remains tied to original source time |
| C0-T19 | Valid request exceeds resource ceiling | Admission rejection before a model or tool call |
| C0-T20 | Model comparison has thinking disabled | Configuration rejection before execution |
| C0-T21 | Credential canary enters input metadata or diagnostics | Admission or serialization rejects it; exported content contains no credential |
| C0-T22 | Identical text supplied as a requirement and a source assertion | Distinct roles and provenance remain explicit |
| C0-T23 | Artifact bytes change without a new reference digest | Integrity rejection before any component dispatch |
| C0-T24 | Assigned case has a failure or timeout | Assignment remains in the admitted population and later assessment denominator |
| C0-T25 | Accepted starter manifest is returned to the browser | Approved initial change, policy, suite, and registered assignment IDs are present; private references are absent |
| C0-T26 | A third native tool appears in the manifest | Admission rejects the unsupported tool before callable dispatch |
| C0-T27 | Admission is saved without a separate authorized run command | No model, native tool, or component task starts |
| C0-T28 | Live configuration omits provider, model, thinking, or budget fields | Execution readiness is rejected before any model call |
| C0-T29 | Nonempty initial observations or a cross-run memory channel enters the first profile | `initial_evidence_unsupported`; no admission or dispatch |
| C0-T30 | Binding job is pending, rejected, absent, or bound to another shape or version | `bindings_not_verified`; admission invokes no native tool or model |
| C0-T31 | An admission request, stored configuration, binding receipt, or later candidate uses another agent version | Exact version binding fails before downstream dispatch |
| C0-T32 | Construction lacks a sealed corpus, policy, concrete resource limit, acceptance threshold, or required model setting | C0 blocks C1 dispatch and identifies each missing input without executing collection or guessing defaults |
| C0-T33 | A builder input contains private evaluation data or adds runtime evidence under an existing corpus seal | Admission rejects the input; the original policy and corpus remain unchanged |
| C0-T34 | Re-admit the same stratified construction policy or retry after unfavorable outcomes | Pinned sampler and schedule produce the same round IDs; no outcome-driven redraw or reduction of the separate regression suite occurs |

C0-T11 through C0-T16 also exercise C2, C3, and C5 contracts. C0 must preserve the inputs required for those checks.

They do not require a specific ontology function call to count a correct task result. C5 verifies the final claim and its evidence independently.

## Exit criteria and measurement boundary

C0 is complete when the chosen contract parses, persists, replays, and rejects the specified faults under the actual service permissions.

The local harness may verify a documented subset with SQLite and fixture dependencies. That result cannot establish PostgreSQL, OIDC, Neo4j, or live-provider behavior.

The next experimental design must select a real population, capable fixed model, enabled thinking settings, independent evaluator, and budget.

It must register competent baseline, initial-kernel, and refined-kernel conditions before held-out execution. Equivalent-information and reusable-function controls remain necessary for contribution claims.

Every assigned case must remain in the denominator. Complete success, constraint errors, costs, latency, fixes, and regressions require separate reporting.

No complete-plan rate, paired improvement, uncertainty interval, or measured ontology benefit follows from this component specification.
