# OaK component integration and query inference

Design version 0.3.0. November 2, 2026. Proposed contracts; runtime verification is pending.

The [PRD](DESIGN.md) defines scope. Each component owns its internal algorithm. This document owns shared handoffs, version rules, failure records, and execution order.

Use the [independent verification specification](INDEPENDENT-VERIFICATION.md) to test these contracts.

## What the graph is and how it is used

G stores observed entities, properties, and relationships. An edge can connect an offer to a hotel. That edge describes a domain relationship. It does not schedule an agent action.

F contains executable procedures. These functions use O to find entities, follow relationships, read properties, filter candidates, and compute results. See [OaK section 3.2, steps 2 and 3; Appendix B](https://arxiv.org/html/2608.22974v1).

| Object | Meaning | Example | Behavior during a new query |
| --- | --- | --- | --- |
| S | Domain schema | Occupancy and minimum-stay definitions | Frozen |
| G | Observed facts and relationships | Offer o3 has capacity four in this source context | New observations create revisions |
| O | Generic operators | Entity lookup and numeric filtering | Implementations stay fixed |
| F | Composed domain functions | Compare observed offers with a request | Implementation stays fixed; arguments and results vary |
| Agent loop | Host decisions about calls and results | Obtain missing details and repeat a function call | Decisions vary |
| LangGraph workflow | Component schedules, handoffs, and checkpoints | Execute C1 before dependent C2 work | Execution state advances |
| HermiT | Logical verification of OWL axioms | Detect an inconsistent restriction | Runs during schema verification |

LangGraph and Neo4j serve different purposes. Neo4j stores the domain graph. HermiT consumes an OWL encoding. Neo4j does not become an OWL reasoner. See [OaK section 3.2 and Appendix A](https://arxiv.org/html/2608.22974v1).

OaK inference means task execution with a frozen kernel. OWL inference means deduction from axioms. A new task does not necessarily require a HermiT call. See [OaK section 3.3 and Appendix A](https://arxiv.org/html/2608.22974v1).

## Component ownership and handoffs

| Owner | Specification | Responsibility | Output |
| --- | --- | --- | --- |
| Input surface | [Task and corpus](00-task-surface-and-corpus.md) | Task definition, sources, cases, and samples | TaskSurfacePackage |
| Host attachment | [Agent onboarding](08-agent-onboarding.md) | Capability verification and lifecycle connection | HostCapabilities, MountReceipt, TaskBinding |
| C1 | [Schema builder](01-schema-builder.md) | Requirements, schema, encoding, and logical checks | SchemaArtifact |
| C2 | [Evidence and graph builder](02-evidence-graph.md) | Extraction, identity, provenance, and graph writes | GraphSnapshotRef, IngestReceipt |
| C3 | [Function composer](03-function-composer.md) | Function plans and local behavior tests | FunctionBundle |
| C4 | [Host task executor](04-task-executor.md) | Dispatch protocol, observation order, function calls, and receipts | TrialRecord |
| C5 | [Evaluator and refiner](05-evaluator-refiner.md) | Independent scores and proposed repairs | Assessment, RepairPlan |
| User control layer | [Workspace](06-kernel-workspace.md) and [visibility](07-kernel-data-and-visibility.md) | Proposal review and versioned activation | EditRequest, ChangePlan, VerificationReport, PromotionReceipt |

The host owns its model loop, instructions, memory, and native implementations. C4 uses host extension points. It does not replace the host loop.

The coordinator owns schedules, total budgets, checkpoints, package assembly, compatibility checks, and repair routing. It cannot write a component's private state directly.

Our five components divide the paper's four construction steps. The paper's knowledge-reasoning step includes C3 and C4. See [OaK section 3.2](https://arxiv.org/html/2608.22974v1).

## Shared message contract

Every handoff must identify its contract version and producer version. It must include input artifact references, configuration reference, run ID, and status.

Use case and round IDs where applicable. Use explicit null values for fields that do not apply. Do not substitute a missing required version with null.

Add these correlation fields:

| Field | Meaning |
| --- | --- |
| `invocation_id` | One logical component request |
| `attempt_id` | One execution attempt within that request |
| `parent_call_id` | The immediate caller, or null at the root |
| `operation_id` | One tracked operation, stable across its delivery retries |
| `assignment_id` | One registered case, condition, and repetition; null outside a trial |
| `evidence_context_id` | The permitted graph scope; null when no graph applies |

Each persisted artifact needs an immutable ID, creation time, content hash, and location. Exclude credentials and authentication headers.

The shared `status` is `succeeded`, `failed`, or `cancelled` for a terminal result. A nonterminal event uses `running`. Component detail states remain in a separate `component_status` field.

A domain violation is not necessarily a component failure. For example, successful execution of a filter can reject every candidate. C5 can successfully score a task as incorrect.

A failed result must include `error.code`, `error.owner`, `error.stage`, `error.retryable`, and affected artifact references. Preserve the causal IDs of nested failures.

Partial outputs from a failed stage remain diagnostic artifacts. A consumer must not treat that failed stage as a successful handoff.

A successful output can contain incomplete domain evidence. Preserve its coverage limits and rejected items. An ingestion receipt can admit supported facts while reporting rejected candidates.

A later failed stage does not invalidate an earlier committed output. For example, a judge failure does not erase a completed independent score. Record separate stage outcomes.

A retry must retain previous attempts and their costs.

| Handoff | Required payload | Receiver requirement |
| --- | --- | --- |
| Input to construction | Task, tools, sources, case manifest, sample settings, evaluator reference | Resolve references and verify split permissions |
| C1 to C2/C3 | S, OWL export, requirements, encoding coverage, reasoner report, schema hash | Reject failed required checks or unsupported required axioms |
| C2 to C3/C4 | Context, committed revision, schema/extractor/mapping versions, sources, coverage, conflicts | Require compatible scope and a stable revision |
| C3 to coordinator | Contracts, plans, operator dependencies, evidence requirements, test reports | Resolve exact dependencies |
| Coordinator to C4 | CandidatePackage or KernelPackage and dependency manifest | Verify compatibility before execution |
| Native tool through C4 to C2 | Raw observation reference, call/tool identity, scope, time, pagination, invocation/effect states | Validate the envelope; treat source content as data |
| C4 to C5 | Assignment, calls, results, graph revisions, final output, effects, failures, settings, usage | Match the registered assignment and independent evaluator |
| C5 to coordinator | Score, targeted patches, trace references, invalidation requirements | Reject stale targets and undeclared changes |

These message contracts are implementation choices. The paper defines mathematical inputs and outputs. See [OaK section 3.2](https://arxiv.org/html/2608.22974v1).

## Independent execution and budgets

Each component must accept saved inputs without running its predecessors. Declare all dependencies. Supply saved responses or test substitutes through explicit interfaces.

A substitute test cannot establish real Neo4j, HermiT, provider, or host behavior. Execute separate service tests before claiming those connections work.

Recorded-response replay must use a declared clock, ID source, and response order. Compare outputs after only declared metadata normalization. Fresh model execution need not reproduce identical bytes.

The coordinator must save a resource reservation before dispatch. Each attempt consumes the same persistent ledger. Completion delivery must reconcile each reservation once.

Restart must preserve the absolute deadline and consumed budget. Unknown provider usage remains unknown. Reserve the configured upper bound when a strict cost ceiling requires one.

If a crash leaves dispatch uncertain, retain the reservation. Reconcile the operation before retry. Do not infer nonexecution from a missing local acknowledgement.

## Existing agent attachment

The adapter registers F and adds compact, versioned context. It binds task scope and receives actual tool results. The host retains native behavior and implementation ownership.

Admission distinguishes description-only input, callable access, optional-function integration, guarded integration, and black-box request/result access. A final answer alone cannot establish full integration.

Nested calls require explicit event and context propagation. A delegate summary does not establish its internal source receipts. Facts from memory retain source age and assertion status.

A failed mount must remove only its own staged changes. Existing host tools and context must remain intact. See [onboarding](08-agent-onboarding.md).

The first pilot requires one selected host adapter. New host runtimes require compatible extension points. This is an engineering adaptation. See [OaK sections 3.2 and 3.3](https://arxiv.org/html/2608.22974v1).

## Controlled human requirements and candidate changes

An edit targets an exact package version. C1 produces a requirement with scope, exceptions, evidence needs, unknown behavior, and hard/advisory mode. Source facts retain separate attribution.

The coordinator determines affected artifacts. Each owner builds its proposed changes. The isolated candidate records requirement-set and ChangePlan hashes.

Verification includes applicable OWL, extraction, function, regression, and enforcement-route tests. The user reviews the exact candidate and report. See [workspace](06-kernel-workspace.md).

Promotion compares the reviewed base with the active package atomically. A stale base requires a new candidate and affected tests. Normal promotion applies to new runs. Active runs retain their pinned versions.

Rollback selects a compatible previous package. It does not reverse external effects. Human review and approval extend the paper. See [OaK section 5](https://arxiv.org/html/2608.22974v1).

## Construction from configured development evidence

Separate task definitions, reference material, case observations, and evaluator answers. The development corpus need not contain every external record.

The paper samples development query/corpus pairs each round. It constructs S, builds G, composes F, executes tasks, evaluates results, and proposes repairs. See [OaK section 3.2](https://arxiv.org/html/2608.22974v1).

Our proposed sequence is:

```text
load TaskSurfacePackage and bounded bootstrap observations
validate sources, data splits, configuration, and independent evaluator

for each permitted construction round:
    D = sample eligible development cases
    save sample IDs, evidence manifests, and sampling configuration
    S = C1.Build(task surface, D, prior schema feedback)
    corpus = selected case responses plus permitted shared references
    G_design = C2.Build(S, corpus)
    F = C3.Compose(S, G_design, D.queries, O, prior function feedback)
    candidate = coordinator.assemble_and_validate(S, F, exact dependencies)

    for each registered development trial:
        load only permitted initial evidence
        trial = C4.Execute(request, candidate, native tools)
        C4 invokes C2 as new observations arrive

    assessment, repairs = C5.EvaluateAndPropose(trials, candidate)
    route repairs to their owners
    invalidate affected dependent artifacts
    apply the declared stop and budget rules

freeze an eligible identified candidate without dependency changes
```

The design graph supports function construction. It is not automatically available to a trial. Trials must use the same incremental observation protocol as deployment.

Construction changes external artifacts, not model weights. Keep model and thinking settings fixed within the declared comparison. Account for every role. Exclude held-out cases from construction.

Frozen S and F follow the paper. The extended dependency manifest is our reproducibility requirement. See [OaK sections 3.2 and 3.3](https://arxiv.org/html/2608.22974v1).

## Graph commits and function reads

C2 alone writes the domain graph. It serializes commits within each evidence context. Each commit atomically verifies its expected parent revision.

The replay key includes context, observation ID, and schema, extractor, mapping, and policy hashes. Bind the original observation to its payload digest. A different payload under the same observation identity is an error.

Save the ingest receipt in the same transaction as its graph revision. If acknowledgement is lost, replay returns that receipt. It must not create another revision or duplicate assertions.

A changed interpretation configuration creates a new versioned projection. It must not silently reuse a previous projection result.

Each dependent F invocation names its required observation IDs or an equivalent stream watermark. Its selected revision must include all required successful ingest receipts.

An out-of-order acknowledgement must not move the current revision pointer backward. If required ingestion fails, block the dependent call. Preserve native observations as evidence of what the host received.

Each F invocation uses one graph revision throughout execution. A later observation affects a later invocation. The graph version cannot change halfway through a function.

## The paper inference path and our live path

The paper defines `Gq = Build(S*, Cq)`, then `Agent(q, S*, Gq, F*)`. The accompanying corpus is available before graph construction. S and F receive no further edits. See [OaK section 3.3](https://arxiv.org/html/2608.22974v1).

Our live path obtains evidence incrementally:

```text
C(q, k+1) = append(C(q, k), new source observation)
G(q, k+1) = C2.Ingest(S*, G(q, k), new source observation)
result = execute f from F* over G(q, k+1)
```

Append preserves distinct and superseded observations. Conflicting prices do not both become accepted current values. Versioned source and conflict rules determine usable evidence.

Native tools observe or act. F computes over the graph. Registered model-backed operators remain possible, with separate usage records. Native access deliberately differs from the paper's exclusive kernel channel. See [OaK section 3.1 and Appendix B](https://arxiv.org/html/2608.22974v1).

In `optional_functions` mode, the agent chooses F calls. In `guarded_requirements` mode, C4 requires mandatory checks at declared protected boundaries.

Pin rule-set, checker, and guard versions. Unknown applicability or required evidence blocks a protected operation. Guard enforcement is an additional evaluation condition.

## Exactly what happens for a new query

The host loads the frozen function catalog and compact schema description. The runtime loads exact implementations and bindings. Initial graph evidence may be empty.

1. Bind explicit request values to function arguments.
2. Obtain scoped observations through native tools.
3. Pass observations to C2 under the frozen extraction configuration.
4. Wait for the required committed ingest receipts.
5. Invoke F with current arguments and one compatible graph revision.
6. Obtain missing evidence when the result identifies an unresolved requirement.
7. Apply mandatory guards before protected dispatch or finalization.
8. Return a supported answer or invoke a permitted native action.
9. Record and reconcile actual external effects.
10. Evaluate the completed task independently through C5.

The host adapter must apply step 7 at the actual dispatch or finalization boundary.

The paper supplies typed argument binding, graph construction, and frozen functions. Live retrieval, dependency tokens, and partial-evidence handling are our extensions. See [OaK sections 3.2 and 3.3; Appendix B](https://arxiv.org/html/2608.22974v1).

In held-out execution, C5 records defects without repairing the active package. New evidence can change G. It cannot silently change S, O, or F.

## Worked query with graph revisions

This is a [synthetic fixture](examples/README.md), not an executed result or selected benchmark.

Select an available offer for four people and two nights. The total budget is USD 420. The fixture defines totals as inclusive of fees. Reservations are outside this task.

The recorded search response contains:

| Offer | Maximum occupancy | Minimum nights | Total USD |
| --- | --- | --- | --- |
| o1 | 2 | 1 | 300 |
| o2 | 4 | 3 | 340 |
| o3 | 4 | Unknown | 390 |

The proposed graph g1 retains identifiers, source times, dates, and request scope. This notation describes relationships, not a physical Neo4j schema:

```text
(Offer o3) --HAS_QUOTE--> (Quote obs-search-001/o3)
(Quote obs-search-001/o3) --FOR_REQUEST--> (Request dev-001)
(Quote obs-search-001/o3) --SUPPORTED_BY--> (Observation obs-search-001)

o3.maximum_occupancy = 4
o3.minimum_nights = unknown
o3.availability_for_requested_stay = unknown
quote.total = 390
quote.currency = USD
quote.stay_context = this request's dates and party
```

The quote identity comes from the observation and offer record. It is not a provider quote ID. The example invents no hotel identity.

The proposed frozen function uses this sequence:

```text
lookup_entities(observed candidate IDs)
traverse_relations(quote and request relationships)
project_properties(occupancy, minimum nights, availability, total, currency, context)
retain missing or incompatible requirements in the diagnostic result
filter_categorical(availability for requested stay is true)
filter_numeric(occupancy >= 4, minimum nights <= 2, total <= 420)
return candidates, violations, unknowns, and source references
```

The named operations correspond to paper operators. The explicit unknown branch and result evidence contract are our live-observation adaptation. See [OaK Appendix B](https://arxiv.org/html/2608.22974v1).

Expected g1 result: o1 fails capacity; o2 fails minimum stay; o3 lacks minimum-stay and availability evidence. No calculation can supply those missing facts.

The detail fixture for o3 supplies minimum nights 1 and availability true for the same stay. C2 would commit g2. The unchanged function would then return o3 as satisfying the declared constraints.

An independent evaluator must verify that selection against source evidence. It must reject a reservation claim because the fixture includes no reservation action.

A reservation variant requires a native action tool, effect confirmation or reconciliation, and independent effect tests. This fixture does not exercise that variant.

## Freeze and invalidation rules

CandidatePackage pins S, F, operators, encoding, extraction, source interpretation, native contracts, runtime, and model-setting references. It also pins requirements, execution mode, and guard bindings.

Trials record the exact package ID. Freeze promotes that package without resolving newer dependencies.

| Change | Required response |
| --- | --- |
| New observation | Commit a new G revision; retain S and F |
| Schema meaning or identity | Repeat logical checks, affected graph projections, function validation, and trials |
| Function-only repair | Validate the function and affected trials; preserve source observations |
| Extractor or source interpretation | Version the change, reproject observations, and invalidate dependent results |
| Native tool contract | Reject incompatible execution and construct a compatible package |
| Held-out defect | Record the defect for a later package |
| Human requirement or enforcement scope | Construct an isolated proposal, test affected behavior, and activate only the reviewed candidate |

The paper explicitly freezes S and F. Our additional pins and invalidation rules control implementation dependencies. See [OaK section 3.3](https://arxiv.org/html/2608.22974v1).

## Decisions outside the paper's operational contract

| Question | Source boundary | Proposed decision |
| --- | --- | --- |
| How is live Cq obtained? | Section 3.3 starts with Cq | Native tools supply scoped observations |
| How is the task configured? | Section 3.2 defines tasks and query/corpus pairs | Versioned input manifest and coverage report |
| What if facts conflict or IDs are missing? | Step 2 supplies type/key equality | Scoped identities and explicit unresolved states |
| How does the schema become OWL? | Step 1 requires encoding | Supported profile, coverage report, and rejection of unsupported required axioms |
| How does F execute? | Step 3 defines typed realizations over O | Bounded plans with dependency and behavior tests |
| Is F the only data path? | Section 3.1 says yes | Native access remains available in our adaptation |
| What if an external write times out? | No general live-effect protocol | Separate invocation/effect states and reconciliation |
| How does Neo4j order commits? | No specified Neo4j protocol | Atomic parent verification and stable reads |
| Does this reduce cost? | Reported tradeoffs do not establish our effect | Paired task and cost evaluation |

See [OaK sections 3.1 to 3.3, section 4.7, and appendices A and B](https://arxiv.org/html/2608.22974v1).

## Integration acceptance

First, execute isolated component tests. Then execute real dependency tests. Finally, execute the declared integration fault cases.

The complete demonstration must preserve each handoff from one configured development case. It must expose a failed domain test, targeted repair, affected rebuild, and frozen execution with fresh evidence.

Use [independent verification](INDEPENDENT-VERIFICATION.md) for exact fault inputs, expected effects, denominators, and debugging records. All OaK runtime cases remain not run.

Task benefit requires a selected API, evaluator, population, model configuration, and budget. Document checks do not establish that benefit.
