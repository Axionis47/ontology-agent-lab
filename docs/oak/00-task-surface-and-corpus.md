# Task surface, corpus inputs, and round configuration

Design version 0.4.8. November 2, 2026. This input and inspection design is proposed. The input UI and task pipeline are not implemented.

Use the [PRD](DESIGN.md) and [integration specification](INTEGRATION.md) with this document. All examples are synthetic. They do not select a pilot or authorize execution.

The example input format remains version 0.1.0. Human-editing artifacts are separate versioned inputs.

## Fixed construction policy

Use **`oak-construction-policy/1`** for production ontology construction. Here, training means constructing and refining external schema S, functions F, and their interpretation dependencies. Model weights remain fixed. This section is the canonical policy; the old offer fixture and its three-round configuration are teaching inputs, not production defaults. The policy is specified, not implemented, and does not select a live benchmark or authorize a run.

A campaign is one bounded construction attempt under an immutable policy and source snapshot. C0 validates the policy and inputs, C1 through C5 perform their declared work, and C6 owns candidate acceptance and freeze. A change to the task scope, sources, corpus, collector, evaluator, model settings, or budget requires a new campaign version. Never change those inputs in place to rescue an unfavorable result.

Existing internal split names map as follows: `development` means construction/repair/regression data from the official **train** split; `selection` means final validation from official **dev**; `held_out` means official **test**. References to a development or regression suite in this policy never admit the official dev split into repair. For custom splits, register the same three roles explicitly.

### What the corpus is and who solves the task

`Cq` means the source-information bundle accompanying a particular query q. It is data, not an agent or a component ID. For an email task, it can contain permitted retrieved message records with sender IDs, text, and timestamps. API documentation describes the operations and fields that make those records accessible. The graph G is a schema-guided representation extracted from the corpus. Neither the API list nor the schema is a substitute for the source records.

In the primary paper flow, the corpus is available before graph construction. C2 builds G from it, C3 supplies executable F, and the working agent uses F as its task-data interface. The worker is a ReAct tool user; it does not gather Cq by filling a record or writing code. Collection when no corpus is supplied and incremental native retrieval are separately declared adaptations. [OaK sections 3.1 to 3.3](https://arxiv.org/html/2608.22974v1#S3).

| Role | Responsibility | Boundary |
| --- | --- | --- |
| C0 and the dataset owner | Define the task population, allowed sources, fixed collection policy, and corpus snapshots | Control what construction can read independently of the worker under test |
| Collection runner | Acquire permitted training evidence when a supplied corpus is unavailable | Fixed implementation/prompt/model and budgets; retrieves evidence, never supplies the scored task answer or performs business mutations |
| C1 schema builder | Read task requirements and sampled evidence; propose and check S | Does not solve the working agent's task or change the corpus |
| C2 and C3 | Extract G and compose/test F | Distinguish source facts, schema meaning, and executable computation |
| Actual plugged-in working agent | Attempt development tasks through candidate F over G, then unseen tasks through frozen F over Gq | Chooses typed calls and reads outputs; the runtime makes the kernel the sole task-data channel in the primary flow; C5 evaluates observable results |
| C5 and C6 | Independently score results, diagnose training failures, verify regressions, and control candidate acceptance | No private answer leakage into collection or construction |

The collection runner is a separate role under C0's admitted plan and C2's evidence handling, not another domain-specific product component. It may use a fixed collection agent with permitted read tools or an existing source importer. Its configuration and source access remain unchanged when the working agent changes. Reuse the exact sealed construction corpus across worker comparisons; declare the changed worker configuration separately. Sharing a model family between collector, builder, and worker does not merge their contexts, permissions, or costs.

| Decision | Fixed rule |
| --- | --- |
| Task boundary | Register supported task families, completion conditions, exclusions, evidence standards, and independently checkable success criteria before collection |
| Data roles | Use the benchmark's official training split for construction and repair, development split for final validation, and test split for held-out evaluation. If official splits do not exist, require a frozen, disjoint, group-aware split manifest before execution |
| Leakage unit | Keep related variants together when creating custom splits; record and respect any official scenario overlap rather than claiming a stronger split than the benchmark supplies |
| Source choice | Use the supplied reference corpus when the benchmark provides one. Otherwise use the independently pinned collection runner and permitted source interface under the acquisition procedure below |
| Shared reference material | Pin task/domain policies, field definitions, and the disclosed API/tool capability catalog separately from case-specific observations and actual call traces |
| Corpus lifetime | Seal a construction corpus before round 1. Keep that corpus fixed throughout the campaign; unresolved gaps stay visible |
| Model configuration | Pin each constructor, extractor, composer, worker, and judge model/version, prompts, settings, and enabled thinking configuration. No fine-tuning or weight updates |
| Construction samples | Seed `42`; at most five outer rounds; each round draws `max(1, ceil(0.20 * N_h))` cases without replacement from each nonempty training stratum h. Freeze the sampler version, per-round random streams, selected IDs, and order before outcomes |
| Regression population | Separately freeze C6's broad stratified development suite from the training population, with mandatory boundary, interaction, and known-regression cases. Add change-targeted cases before candidate execution; confirmed new regressions become mandatory before repair |
| Local attempts | At most three schema drafts and three function proposals per outer round, including the first attempt. Infrastructure retries retain their existing separate bounded policy and consume the same reservation |
| Resource limits | Require explicit finite per-case and campaign call, token, elapsed-time, and cost limits, including collection and failed attempts. Reserve final training rechecks and validation separately; held-out execution needs its own admitted reservation. Missing model bindings, limits, or task-specific success thresholds block execution |
| Candidate acceptance | Require applicable structure, semantic coverage, OWL, projection, function, task-coverage, regression, and effect checks. Zero unintended regressions on protected cases; incomplete required work cannot pass |
| Final choice | Recheck the last eligible incumbent against the final required suite, including newly mandatory and targeted cases. Use it only if still eligible, never the last attempted draft or a candidate selected after seeing validation/test results |
| Early stop | Stop only when the incumbent meets the declared success threshold, required coverage/checks are complete, and no blocking fault or pending repair remains. Otherwise stop at the round or resource limit without declaring convergence |
| Final validation | Evaluate the final eligible incumbent once on the separate validation population using predeclared thresholds. Do not send validation case-level outcomes to the builder or judge for repair in this campaign |
| Held-out use | Freeze the validated package before test execution. New task evidence can populate G; S, F, interpretation rules, and execution policy remain pinned. Test outcomes cannot select or repair the kernel |

The seed, stratified 20-percent draw, five-round limit, and local attempt caps are selected engineering defaults. The paper uses fresh random training samples and reports 20 percent with at most five iterations; stratification, corpus acquisition, regression protection, and our validation rule are explicit adaptations. [OaK sections 3.2 and 4.2](https://arxiv.org/html/2608.22974v1). Seeded sampling fixes case assignments, not stochastic model responses or mutable external services.

The model, benchmark, population size, task-specific thresholds, and concrete resource limits remain run inputs because no live pilot has been selected. Every value must be resolved before execution. Changing a default requires a new policy version and a declared reason before outcomes, not an informal override during a run.

### Capability context and observed calls

Present available APIs/tools explicitly during construction when they are part of the task's environment. The fixed training input has three distinct parts: **task specification and examples**, **capability/reference context**, and **case-specific evidence and execution records**. Public capability descriptions tell OaK what operations or data could be available. Actual calls tell it what was invoked and observed. Neither requires access to the working agent's private planner.

| Input | Pinned content | Construction use |
| --- | --- | --- |
| Task specification and query | Supported work, constraints, completion conditions, and case inputs | C1 identifies the reusable meanings and distinctions the kernel must support |
| API/tool capability catalog | Stable tool ID/name, documentation version, purpose, input arguments, output fields/types and meanings, read/write effects, preconditions, pagination, errors, limits, and source scope | C1 proposes source-linked concepts and evidence needs; acquisition selects supported retrieval operations |
| Availability status | Whether a capability is merely documented, bound in the selected integration, or observed executing; missing or undisclosed status stays explicit | Prevent a description from being treated as a connected or tested callable |
| Observed call record | Task and call IDs, tool/version when exposed, non-secret arguments, raw result/error reference, source time/state, provenance status, and measured resource use | C2 extracts scoped facts from source results; training failures and traces help diagnose missing distinctions or procedures |
| Generated kernel functions | Candidate F signatures, supported operator compositions, dependency versions, and independent test results | C3 supplies validated computation over the admitted graph, after construction rather than as an input assumption |

For API-based collection, obtain capability documentation through the collector's permitted source interface and pin its version. A large catalog may be searched using the task and app descriptions under a fixed retrieval policy; save the selected documentation and retrieval steps. Do not use hidden reference solutions or `required_apis` to choose that subset. Documentation retrieval consumes the collection budget. For a supplied corpus without source APIs, mark source capability context absent. The primary worker still receives the generated F contracts; those are distinct from a native API catalog. No private planner inspection or unsupported capability claim is required.

For example, a documented message-search operation may describe sender IDs and message timestamps. Sample responses supply actual messages and values. C1 can propose Message, Person, sender relationships, and time scope from that material. C3 can compose graph lookup and filtering into a reusable message-selection function. The presence of a search operation does not prove a particular message exists or that a recorded call succeeded.

The native API catalog and OaK's generic operator library are different inputs. C3 composes F from admitted operators. Listing a provider API does not automatically turn it into an executable OaK function or authorize F to call it directly. In the primary flow, source acquisition precedes graph construction and the worker obtains task data through F. Only a separately admitted live-API adaptation gives the worker native retrieval or business actions. A missing fact can identify a source gap; it cannot produce an invented endpoint or value.

Tool-execution receipts provide stronger provenance than an agent's asserted call description. Keep both statuses visible rather than treating a submitted narrative as proof of execution. Preserve failed calls and unexpected responses as diagnostics, not source-backed domain facts.

### Corpus acquisition

1. **Admit the collection plan.** Pin eligible training case IDs, task-visible instructions/context, source permissions, reference/capability-document versions, documentation retrieval policy, collector prompt/model/settings, and finite collection budgets. C0 validates this plan without calling tools. A supplied benchmark corpus skips collection and proceeds to sealing.
2. **Collect through permitted access.** For each case, the separate collection runner reads its instruction and available documentation, chooses relevant retrieval calls, and returns source-linked observations. Its policy is independent of the worker under test and candidate outcomes. OaK does not need the worker's planner implementation or private native-tool catalog. Direct collection integrations must validate the contracts they actually invoke. Authentication/session setup may follow the declared access policy; collection must not perform the task's business mutations.
3. **Use a fixed stop rule.** The collector tracks the information needed by the task and stops when those needs are supported, explicitly unresolved after available retrieval, or a budget limit is reached. Record that decision and its evidence. This is not an oracle for complete relevance. A claim requiring exhaustive search needs complete pagination or equivalent source support; an unvisited page remains a gap.
4. **Retain the whole assigned collection outcome.** Save source payloads, case identity, call inputs when available, record IDs, source time, applicable state/context, pagination, provenance status, and content hashes. Keep failed calls, empty results, conflicts, and truncated responses as diagnostics. Do not discard a case because retrieval failed or keep fetching until it passes. Credentials remain in the host's protected access state, outside model-visible corpora and graph facts.
5. **Separate evidence from labels.** API documentation describes possible operations and fields; responses describe observed values. Collector summaries, synthesized fixtures, asserted sources, and verified source responses retain distinct provenance. Solutions, private evaluator answers/tests, privileged database dumps, and answer-derived API lists cannot select or populate the corpus. Unknown stays unknown.
6. **Seal before construction.** Produce a per-case corpus manifest and a shared reference manifest with immutable versions and explicit gaps. C0 binds the construction admission to those manifests and the original collection-policy hash. C1 sees the task, sampled cases, and admitted evidence, not the evaluator's answer key. Collection failures remain in the registered population and costs.

Do not use corpus acquisition to solve the task secretly or precompute the correct answer. It ends with source records and gaps, not an evaluator-approved final result. The same task-visible source rights and declared retrieval limits apply to compared conditions. An additional discovery pass is a measured construction cost, not free information supplied only to the treatment at evaluation.

### Construction and repair sequence

```text
pin policy and data roles -> collect or admit source corpora -> seal corpus
-> preselect round cases and broad regression suite
-> C1 requirements, schema draft, coverage and OWL checks
-> C2 schema-guided graph extraction -> C3 typed function composition and tests
-> working-agent development trials -> C5 independent scores and judge feedback
-> C6 coverage and regression decision -> accept incumbent or retain failure
-> bounded next round, or final validation -> freeze -> held-out evaluation
```

The first schema is built from task requirements and example evidence. The worker's later trial results guide repair; the worker cannot silently edit the active ontology or expected answers. Seal each candidate's dependencies before its trials. Initial verification has candidate-only assignments; later schema/function changes compare the incumbent and candidate using the same assigned cases, source conditions, evaluator, actual provider settings, and budgets.

The changing construction sample is for discovering improvements. It is not the population used to compare round quality. Compare candidates on C6's separately frozen broad suite plus declared mandatory and targeted additions, with those additions run against both conditions. A failed candidate never replaces the incumbent. Newly confirmed regressions remain mandatory through later rounds; candidate changes invalidate earlier verification tied to different hashes.

The judge receives allowed training diagnostics and observed trajectories, never private expected answers. A corpus gap can produce an explicit failure or a proposed future collection need. It cannot cause silent source expansion. Adding observations to the builder's corpus, changing collection behavior, or importing newly authored development evidence requires a new campaign with fresh manifests and repeated affected comparisons. Keep the previous campaign's failures and costs.

At a construction budget or round limit, stop construction dispatch and preserve an already eligible incumbent only if its required checks and thresholds still hold. Final training rechecks and validation must fit their remaining reserved limits; exhausting the total reservation leaves the campaign incomplete, with no automatic top-up. If no eligible incumbent exists, report no eligible kernel. Validation failure blocks release; it does not grant another construction attempt against the same validation answers. If later work uses those failures, record the validation population as consumed and reserve new independent validation where benchmark rules permit. Never silently reassign official splits.

### Runtime evidence and mutable API tasks

Primary inference builds Gq from the new query's admitted Cq before the working agent runs. S and F stay frozen. The remaining paragraphs describe the optional mutable-API adaptation, where runtime retrieval and effects require additional controls.

The frozen construction corpus is not the world state for every future task. Runtime observations stay scoped to their task and condition, including observation order and effects. They do not automatically become new builder evidence. A static replay may answer only its exact admitted calls and contexts; missing calls are explicit failures, not permission to fabricate responses or make undeclared live calls.

For mutable environments, each paired trial starts in a separate copy of the same pinned initial world and task clock. New reads and post-write reads come from that trial's actual state under the fixed access policy. Invalidate or refresh facts affected by writes rather than treating a pre-write response as current. Actual mutations and independently verified effects are required for action tasks. Resetting worlds between trials provides comparable starts; arbitrary rollback inside a trial is not a free recovery capability.

For an AppWorld adaptation, the collector would choose calls from task-visible instructions and documentation. It must not use hidden `required_apis`, reference solutions, or direct database access to preselect the answer-bearing records. AppWorld restricts hardcoded API calls in agent logic and reserves test sets for final scoring; keep those restrictions in the benchmark binding. [Official AppWorld development restrictions](https://github.com/StonyBrookNLP/appworld#-agent-development-restrictions). Its evaluator checks actual state changes, not merely a completed record. [AppWorld task and evaluation structure](https://github.com/StonyBrookNLP/appworld/blob/main/guides/developing_new_task_generators.md#-overview). AppWorld remains an example adaptation, not a selected or executed benchmark.

### Required policy evidence

The run record must resolve the policy, task/split manifests, characteristic assignments, collection settings and receipts, corpus/reference snapshots, round selections, regression assignments, candidate hashes, independent assessments, gate results, final-validation result, and frozen package. Show missing artifacts as incomplete. These are runtime inputs and evidence, not tracked documentation audits.

Report corpus acquisition, schema/graph/function construction, worker trials, judge/repair work, validation, and held-out execution costs separately. Count failed and timed-out assignments in their registered denominators, and distinguish an expected rejection passing a test from complete task success. The UI shows what is sealed, collected with gaps, under construction, blocked, eligible for validation, or frozen, with exact reasons.

## What the user supplies

A task surface defines the work an agent supports and the tools available for that work. It identifies task families, constraints, and completion conditions. It does not list every request or load every external record.

This fixture selects an available accommodation offer for a party, stay, and budget. It excludes reservation execution.

The paper pairs each development query `q` with an accompanying corpus `Cq`. Requirement analysis also receives the task description `T`. The corpus supplies query evidence. The paper does not specify its production acquisition procedure. [OaK section 3.2, opening paragraphs and Step 1](https://arxiv.org/html/2608.22974v1).

The following table defines proposed input sections. These are not existing screens. The fixed policy above takes precedence over the older fixture's sampling and round settings.

| Field | User supplies | Preview and validation |
| --- | --- | --- |
| `task_spec` | Supported requests, completion conditions, required distinctions, exclusions | Success example, ambiguities, unsupported work |
| `construction_policy` | The registered fixed policy and resolved campaign settings | Complete data roles, sources, collector, thresholds, assignments, and budgets before execution |
| `tool_manifest` | Available source API documentation; exact tool bindings for direct collection or managed native profiles | Source APIs can be absent for supplied corpora; callable bindings are required wherever this integration invokes them; generated F is supplied separately to the worker |
| `domain_material` | Policies, field definitions, documentation, skill procedures | Source identity, version, format, content excerpts |
| `development_cases` | Requests, context, tags, initial evidence | Counts, unique IDs, scope, excluded evaluator answers |
| `observation_store` | Permitted recorded or sampled responses | Structure, source scope, timestamps, identity coverage |
| `sampling` | Method, seed, rounds, sample size, coverage policy | Selected IDs and coverage counts |
| `budgets` | Construction, reasoning, execution, token, and time limits | Admitted limits and stopping behavior |
| `evaluation_spec` | Independent evaluator ID and protected configuration | Metric and version; private answers stay hidden from builders |
| `held_out_manifest` | Reserved cases and access policy | Metadata only during construction |

Submission resolves references and validates formats. It produces an immutable manifest with hashes. It does not launch model calls.

A separate run configuration supplies model settings, thinking configuration, credentials, and execution authorization.

## Additional business constraints

Users can propose missing meanings or business constraints before construction or against an existing package. The [workspace](06-kernel-workspace.md) records an EditRequest and requirement set.

Human requirements must not become provider observations. Record their scope, hard/advisory mode, exceptions, evidence needs, and unknown behavior.

A current budget can bind an existing argument. A reusable policy can require schema, function, source-interpretation, or guard changes.

If saved responses contain the needed data, reproject them under the candidate. If no source supplies it, display the gap. The [data hierarchy](07-kernel-data-and-visibility.md) links these objects.

Human requirements extend the paper's model-judge refinement loop. The paper identifies human feedback as future work. [OaK section 3.2, Step 4; section 5](https://arxiv.org/html/2608.22974v1).

Changed requirements or mappings create a candidate and verification record. They must not silently modify admitted corpora or frozen runs.

## Illustrative configuration

Paths below are relative to the configuration file. The [example package](examples/README.md) contains the matching [task-surface.json](examples/task-surface.json).

These files do not establish provider compatibility or an executable runtime. Admission adds the shared run envelope around these authoring fields.

```json
{
  "task_spec": {
    "id": "accommodation-selection-fixture",
    "version": "0.1.0",
    "definition": "Select an observed available offer satisfying party size, stay, and total budget.",
    "completion_conditions": ["Return the selected offer ID with evidence for every required constraint."],
    "required_constraints": ["occupancy", "minimum_stay", "availability", "total_price"],
    "unsupported": ["reservation execution", "global cheapest-offer claims"]
  },
  "tool_manifest": {"path": "tool-manifest.json", "version": "0.1.0"},
  "domain_material": [
    {"id": "fixture-policy", "path": "domain-policy.txt", "media_type": "text/plain"}
  ],
  "development_cases": {"path": "development-cases.jsonl", "format": "jsonl"},
  "observation_store": {"path": "observations.jsonl", "format": "jsonl", "synthetic": true},
  "sampling": {
    "method": "seeded_random_without_replacement_within_round",
    "seed": 42,
    "rounds": 3,
    "cases_per_round": 1,
    "coverage_tags": ["capacity", "minimum_stay", "unknown"],
    "coverage_policy": "report_only"
  },
  "budgets": {
    "schema_attempts": 3,
    "function_attempts": 3,
    "agent_steps_per_case": 12,
    "max_model_tokens_per_run": 50000,
    "max_seconds_per_run": 900,
    "reasoner_timeout_seconds": 30
  },
  "evaluation_spec": {
    "id": "fixture-selection-checker",
    "version": "0.1.0",
    "private_ref": "private/evaluation-spec.json",
    "primary_metric": "complete_task_success"
  },
  "held_out_manifest": {"path": "held-out-manifest.jsonl", "access": "evaluation_only"}
}
```

These budgets are teaching values. They are not experiment settings. One case demonstrates an interface but cannot establish generalization.

Reject sample sizes larger than the eligible pool. Refuse held-out evaluation when its declared population is empty.

## Query, context, and source responses

This record separates the request from its available evidence:

```json
{
  "case_id": "dev-001",
  "split": "development",
  "request": "Find an available offer for four people for two nights, at most 420 USD total including fees.",
  "context": {
    "city": "Example City",
    "check_in": "2027-03-10",
    "check_out": "2027-03-12",
    "party_size": 4,
    "budget_total": 420,
    "currency": "USD"
  },
  "coverage_tags": ["capacity", "minimum_stay", "unknown"],
  "initial_observation_ids": [],
  "source_response_ids": ["obs-search-001", "obs-detail-001"]
}
```

This JSON describes the native-tool replay fixture, not the primary supplied-corpus protocol. Here `source_response_ids` makes records available to a future replay tool. It does not reveal them before matching calls.

Replay must match the tool ID, version, arguments, and case scope. A fixed response sequence would hide tool-selection errors.

Construction may inspect declared development responses to build S and F. This adaptation fixture starts trials with empty evidence and obtains records through replayed native calls. Primary paper trials instead use the graph built from their admitted reference corpus before worker execution.

Replay produces a new run-scoped observation and call ID. Retain the fixture reference as provenance. The fixture call ID is not a receipt for a new execution.

Keep original source time separate from replay time.

## Corpus content

A text file can supply policy. JSON can supply an API response. JSONL can store observation envelopes.

The envelope records provenance. The payload contains evidence. The paper requires bounded chunks and schema-guided LLM extraction. It does not define a universal raw-corpus format. These formats are our design choice. [OaK section 3.2, Step 2](https://arxiv.org/html/2608.22974v1).

Example search observation:

```json
{
  "observation_id": "obs-search-001",
  "case_id": "dev-001",
  "tool_id": "fixture.search_offers",
  "tool_version": "0.1.0",
  "call_id": "call-search-001",
  "arguments": {
    "city": "Example City",
    "check_in": "2027-03-10",
    "check_out": "2027-03-12",
    "party_size": 4
  },
  "invocation_status": "completed",
  "effect_status": "not_applicable",
  "effect_evidence_refs": [],
  "observed_at": "2027-03-01T10:00:00Z",
  "media_type": "application/json",
  "payload": {
    "currency": "USD",
    "price_basis": "total_for_requested_stay_including_fees",
    "offers": [
      {"offer_id": "o1", "max_occupancy": 2, "min_nights": 1, "total_price": 300},
      {"offer_id": "o2", "max_occupancy": 4, "min_nights": 3, "total_price": 340},
      {"offer_id": "o3", "max_occupancy": 4, "min_nights": null, "total_price": 390}
    ],
    "next_page_token": "fixture-page-2"
  },
  "synthetic": true
}
```

The fixture allows search results that violate party constraints. A `null` value means unknown.

The detail observation supplies `o3`, the same stay dates, `min_nights: 1`, and `available: true`. Its source observation time is `2027-03-01T10:01:00Z`.

That observation must not assert availability for another stay. Evidence time and requested stay dates are separate fields.

The proposed preview shows:

| Source | Evidence | Meaning and limits |
| --- | --- | --- |
| Policy text | Prices include fees; occupancy applies to the offered accommodation | Interpretation rules, not offer values |
| Search JSON | Three offers; o3 minimum stay unknown; more pages exist | Candidate evidence with incomplete market coverage |
| Detail JSON | o3 minimum stay is one night; availability is true for this stay | Evidence needed before a supported eligibility claim |

Expected answers belong in the separate evaluator. They do not belong in the corpus.

Distinguish raw content, extraction candidates, accepted facts, rejected facts, and conflicts. A declared property does not establish its value.

C2 initially applies Phi to bounded content, including serialized JSON with field names preserved. Deterministic envelope parsing does not replace semantic extraction.

A future direct JSON-to-graph mapping needs a separate version. Source pointers retain record and field paths for inspection.

## Select each construction round

The paper draws a fresh random sample each round. Its reported experiment uses 20 percent of training examples and at most five rounds. Those values are experiment settings, not universal algorithm requirements. [OaK sections 3.2 and 4.2](https://arxiv.org/html/2608.22974v1).

Our proposed sampler uses a saved seed and a deterministic random stream for each round. Sampling has no replacement within one round. Separate rounds can overlap.

Save eligible IDs, selected IDs, order, seed, and tag coverage. This singleton fixture naturally repeats.

Before a real run, select cases covering success, violations, missing evidence, conflicts, and controls where ontology may provide no benefit.

The old construction fixture's `report_only` coverage policy reports tags without changing selection. Production follows the fixed stratified construction policy above. C6 separately owns regression selection below. This design amendment does not change the current C0 parser or saved example configuration.

Do not redraw samples because results are unfavorable. Exclude held-out cases from construction and coverage-based editing.

## Group cases by task characteristics

A regression suite should exercise the supported task surface, including work that the current kernel handles incorrectly. Selecting only previous successes would hide gaps. Protect previous passes within the selected suite and keep known regression cases mandatory.

Define a versioned characteristic model for each task binding before inspecting candidate outcomes. The agent can propose groups from the task specification, source contracts, schema, and function dependencies; the user reviews the group definitions and gaps before freezing the policy. Use observable request and evidence properties, with reviewed labels and an explicit unknown group. Similar wording alone does not establish equivalent task behavior. For offer selection, useful characteristics include:

| Characteristic | Example groups | Behavior exercised |
| --- | --- | --- |
| Task or operation | Find eligible offers, compare eligible offers, explain no supported selection | Different completion contracts and functions |
| Constraint boundary | Party below, at, or above capacity; stay below, at, or above minimum | Inequalities, equality, and off-by-one errors |
| Price meaning | Within budget, exactly at budget, over budget; fees included or unresolved | Units, price basis, and total-price computation |
| Evidence state | Known, missing, conflicting, stale | Retrieval, unknown handling, and refusal to invent facts |
| Identity and scope | Matching or mismatched offer, provider, or stay dates | Entity resolution and applicability of facts |
| Required execution path | Search sufficient, detail lookup needed, pagination needed, unavailable source | Function composition and tool use |
| Constraint interaction | Capacity plus stay; budget plus fees; missing detail plus date mismatch | Combined requirements that can fail despite isolated checks |

These are proposed groups, not claims that every operation or case already exists. Admit only supported tasks. Derive execution-path labels from the fixture contract and available evidence, not from the candidate's chosen trajectory.

Use a small set of mutually exclusive strata for random selection, such as task family crossed with evidence state. Each eligible case belongs to exactly one stratum. Keep additional overlapping tags for boundaries, risk, functions, and interactions. Avoid crossing every characteristic into a mostly empty grid. Stratified sampling divides a defined population into groups before sampling within them. [NIST definition](https://csrc.nist.gov/glossary/term/stratified_sampling).

The verification suite combines four selections:

| Selection | Purpose | Selection rule |
| --- | --- | --- |
| Routine sample | Exercise the declared normal workload | Seeded sampling without replacement within each stratum, using declared allocations |
| Mandatory cases | Preserve known fixes and critical behavior | Always include registered regression cases and required boundary cases |
| Interaction cases | Exercise combinations of characteristics | Cover declared feasible pairs and higher-order combinations where risk requires them |
| Change-targeted cases | Exercise affected schema terms, functions, and dependent paths | Add cases identified from the candidate's declared change and dependency map |

Pairwise coverage exercises every declared feasible pair of characteristic values. It does not cover every higher-order interaction or prove correctness. Declare invalid combinations and higher-strength targets explicitly. This follows the distinction in [NIST's combinatorial testing account](https://www.nist.gov/publications/combinatorial-t-way-testing-software-adaptation-design-experiments). Newly authored cases need independent expected behavior and admission before the comparison; a generated combination is not automatically a valid test.

Freeze the eligible development population, characteristic definitions and assignments, sampler version, seed, allocations, mandatory IDs, interaction targets, and budget before candidate execution. Select from all eligible cases, retaining failing and negative-control cases. Choose sample sizes from declared coverage and precision goals within the budget. If a required group lacks enough cases or the budget cannot cover mandatory work, report the gap and block the required coverage gate. Do not lower quotas or remove cases after observing outcomes.

Execute the union of unique case IDs and declared repetitions. Preserve every selection reason when a case belongs to several selections, but count its execution only once per repetition. The base and candidate receive identical assignments and comparison settings. C6 freezes previously passing selected cases and mandatory historical regression cases in the protected manifest. Filters and candidate failures cannot shrink that manifest.

Report per group the eligible population, required and selected counts, previous passes, completed comparisons, candidate outcomes, regressions, and gaps. Keep routine-sample metrics separate from mandatory, interaction, and change-targeted results. A challenge case that was also randomly selected retains its routine-sample membership, but additional challenge cases do not enter that sample's score.

To estimate performance for a target workload, declare its population or frequencies, sampling frame, inclusion probabilities, weighting rules, and uncertainty method. Every group with positive target frequency needs nonzero sampling probability and its declared allocation; otherwise narrow the claimed target before execution or report coverage only. Keep repetitions grouped by case. Missing or incomplete outcomes remain in assigned denominators and cannot count as success. If workload frequencies are unknown, label the result a coverage sample and report per-group outcomes, not a representative population score. Meeting coverage targets is evidence about the declared groups, not all possible tasks.

Keep mandatory regression cases across comparisons. A confirmed new regression enters the mandatory registry with its original inputs and expectations before repair, so later sample rotation cannot remove it. Rotate the routine sample only under a predeclared policy in a new versioned comparison, never in response to unfavorable results. Reserve independent held-out cases for final evaluation because repeated refinement can overfit development cases.

The [C6 selection and comparison contract](implementation/C06-workspace.md) defines the artifacts and gates. The [C11 verification view](implementation/C11-interface.md) exposes the plan before Verify and the group results afterward. This is our proposed engineering extension to the paper's random development sampling. The saved development example contains one teaching case, `dev-001`; it cannot demonstrate representative coverage or an implemented sampler.

## Evidence consolidation

Evidence consolidation combines the selected development corpora. It divides them into chunks, applies `Phi_S`, and merges typed candidates into `G_t`.

The paper merges by entity type and primary key. [OaK section 3.2, Step 2](https://arxiv.org/html/2608.22974v1).

Our implementation also preserves case/provider scope, dates, sources, and conflicts. Combining corpora must not create timeless prices. It must not reveal all development responses to every trial.

## Feedback consolidation

Feedback consolidation uses task outcomes to propose artifact repairs. Execute the selected trials. Score every assignment. Supply S, G, F, trajectories, and scores to Judge.

Judge proposes add/delete/modify repairs to entity types, relation types, and functions. Schema feedback goes to C1. Function feedback goes to C3. [OaK section 3.2, Steps 3 and 4](https://arxiv.org/html/2608.22974v1).

Our repair admission removes duplicate proposals and preserves supporting traces. It rejects stale versions and explicitly resolves conflicting proposals before rebuilding.

Private answers must not enter the graph. Agreement between model opinions does not establish correctness.

```text
select round -> analyze/draft/check S -> Build development G -> compose F
-> execute declared trials -> independent scores -> Judge repair proposals
-> validate targeted repairs -> next round, stop, or freeze eligible package
```

During inference, the paper fixes S/F and builds a graph from the new query's corpus. [OaK section 3.3](https://arxiv.org/html/2608.22974v1).

The deferred live adaptation grows that corpus through native observations. Definitions and procedures stay fixed. Retained native access changes the paper's sole-kernel policy, as the PRD records; it is not the primary inference algorithm.

## Independent input verification

These are required tests, not completed pipeline results. Use the [verification protocol](INDEPENDENT-VERIFICATION.md).

Run admission with the saved example files and a callable-registry stub. Do not run C1 through C5. Use fixed sampler seeds and independent expected selections.

| Test input or injected fault | Expected output | Measurable pass condition |
| --- | --- | --- |
| Valid input package | Immutable manifest and preview | All references resolve; hashes match the supplied files |
| Duplicate case ID or development/held-out overlap | Rejection | Zero admitted run manifests |
| Unresolved callable or mismatched contract | Rejection | No invented endpoint and zero tool calls |
| Requested sample larger than pool | Rejection | No sample is silently reduced |
| Repeated sampling with identical saved inputs | Same selected IDs and order | Exact selection equality |
| Empty held-out manifest | Held-out evaluation rejection | Zero admitted held-out assignments |
| Replay call with wrong arguments or absent page | Explicit unavailable-fixture result | No unrelated response is returned |
| Private answer marker in evaluator fixture | No marker in construction inputs | Zero marker occurrences in builder payloads |

Admission may write a manifest and diagnostics. It must not call models, change graphs, or invoke provider tools.

The saved-input test is deterministic only when inputs and sampler implementation are fixed. Live providers and model responses are outside this test.

Passing admission establishes a reviewable run specification. It establishes neither task benefit nor permission to execute.

Source attribution: Xiaohui Zhang et al., *Toward Effective and Reliable LLM Agents via Dynamic Ontology*, [arXiv:2608.22974v1](https://arxiv.org/abs/2608.22974v1), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
