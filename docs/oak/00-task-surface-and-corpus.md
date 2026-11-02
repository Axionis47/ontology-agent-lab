# Task surface, corpus inputs, and round configuration

Design version 0.3.0. November 2, 2026. This input and inspection design is proposed. The input UI and task pipeline are not implemented.

Use the [PRD](../OAK-PRD.md) and [integration specification](INTEGRATION.md) with this document. All examples are synthetic. They do not select a pilot or authorize execution.

The example input format remains version 0.1.0. Human-editing artifacts are separate versioned inputs.

## What the user supplies

A task surface defines the work an agent supports and the tools available for that work. It identifies task families, constraints, and completion conditions. It does not list every request or load every external record.

This fixture selects an available accommodation offer for a party, stay, and budget. It excludes reservation execution.

The paper pairs each development query `q` with an accompanying corpus `Cq`. Requirement analysis also receives the task description `T`. The corpus supplies query evidence. The paper does not specify its production acquisition procedure. [OaK section 3.2, opening paragraphs and Step 1](https://arxiv.org/html/2608.22974v1).

The following table defines proposed input sections. These are not existing screens.

| Field | User supplies | Preview and validation |
| --- | --- | --- |
| `task_spec` | Supported requests, completion conditions, required distinctions, exclusions | Success example, ambiguities, unsupported work |
| `tool_manifest` | Existing tool IDs, contracts, versions, effects, limits | Supplied callables resolve; tool names do not create endpoint bindings |
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

`source_response_ids` makes records available to a future replay tool. It does not reveal them before matching calls.

Replay must match the tool ID, version, arguments, and case scope. A fixed response sequence would hide tool-selection errors.

Construction may inspect declared development responses to build S and F. Task trials start with declared initial evidence. This fixture starts empty.

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

The `report_only` coverage policy reports tags without changing selection. Quotas would require a declared stratified-sampling adaptation.

Do not redraw samples because results are unfavorable. Exclude held-out cases from construction and coverage-based editing.

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

Our live adaptation grows that corpus through native observations. Definitions and procedures stay fixed. Retained native access changes the paper's sole-kernel policy, as the PRD records.

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
