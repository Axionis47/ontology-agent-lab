# C3: Function composer

Design version 0.3.0. November 2, 2026. This component and its operator runtime are proposed. They are not implemented.

C3 converts repeated domain computations into callable functions, F. Each function has explicit arguments, results, and evidence requirements. The agent can reuse that procedure on later requests.

C3 owns composition and local function validation. The coordinator supplies validated inputs, receives a `FunctionBundle`, and selects the next step. The [integration specification](INTEGRATION.md) defines handoffs and package assembly. [C4](04-task-executor.md) integrates task execution.

G contains observed data. F contains procedures that read and compute over G. A new graph revision can change a result without changing F.

The paper's composer receives O, S, G, development queries, and previous function feedback. It produces typed procedures over O. [OaK section 3.2, Step 3](https://arxiv.org/html/2608.22974v1#S3.SS2).

## Source requirements and design choices

| Topic | Paper requirement | Open detail | Proposed implementation |
| --- | --- | --- | --- |
| Construction | Compose, specialize, or lightly adapt operators. Test execution on G. [Step 3](https://arxiv.org/html/2608.22974v1#S3.SS2) | Prompts, program format, and semantic tests | Versioned prompts, bounded plans, dependency validation, and independent expected results |
| Primitive library | Nine public operators with signatures. [Appendix B](https://arxiv.org/html/2608.22974v1#A2) | Neo4j implementation and revision semantics | Versioned implementations, scoped reads, and parameterized Cypher |
| Runtime access | F supplies the kernel computation interface. [Sections 3.1 and 3.3](https://arxiv.org/html/2608.22974v1#S3.SS1) | Tool registration and graph binding | Register F as the worker's task-data tools and bind execution to Gq built from Cq. Native task-provider access belongs only to the deferred live-API adaptation. |
| Incomplete evidence | Property projection has a missing-value parameter. [Appendix B](https://arxiv.org/html/2608.22974v1#A2) | Partial evidence, freshness, and conflicts | Required unknown values remain visible. They cannot silently pass a constraint. |
| Refinement | Function feedback returns to the composer. [Step 4](https://arxiv.org/html/2608.22974v1#S3.SS2) | Concurrent patches, invalidation, and retries | Exact target versions, bounded repairs, and rebuilding by the responsible component |

These choices implement the [pilot PRD](DESIGN.md). Successful execution does not establish semantic correctness. Available F does not establish that the host used it.

## Inputs

A `ComposeRequest` contains:

- The shared versioned envelope.
- A verified `SchemaArtifact`.
- Committed development `GraphSnapshotRef` records.
- Development queries and an `OperatorCatalog`.
- An optional prior `FunctionBundle` and `RepairPlan`.
- Composer configuration and a resource budget.

Each graph declares its schema, evidence context, extraction policy, and revision. The operator catalog declares argument contracts, return contracts, implementation hashes, effects, and model use.

## Outputs

A successful `FunctionBundle` contains:

- Function IDs and descriptions for the host tool registry.
- Strict argument and result contracts.
- Schema dependencies and evidence requirements.
- Executable plans, operator dependencies, helpers, and bounded control flow.
- Behavior for missing, conflicting, stale, or unsupported evidence.
- Validation reports, development graph references, model settings, and usage records.

The coordinator combines the bundle with the exact schema and dependencies. It validates the resulting `CandidatePackage` before a C4 trial.

C3 does not freeze packages or select the benchmark. It cannot edit upstream artifacts or register tools directly into the host.

Use `component_status` for ready, invalid input, unsupported requirement, budget exhausted, and execution failure.

Use the shared envelope for terminal status and invocation identifiers. A ready bundle uses `status: succeeded`. A rejected or exhausted composition uses `status: failed`. Component readiness and task success are separate. Preserve diagnostics and costs for failed attempts. An unverified catalog must not be labeled ready.

## Generic operator library

An operator performs one reusable graph or data operation. A composed function combines operators for a domain task.

The following names and responsibilities come from [OaK Appendix B](https://arxiv.org/html/2608.22974v1#A2). Implementations remain replaceable behind their declared contracts.

| Operator | Responsibility |
| --- | --- |
| `extract_runtime_slots` | Use an LLM to extract declared typed constraints and evidence from the query |
| `lookup_entities` | Select entities by identifiers, keys, types, properties, or text |
| `traverse_relations` | Follow selected relationships with bounded direction and depth |
| `project_properties` | Return selected fields while preserving identity |
| `filter_property_categorical` | Apply categorical inclusion or exclusion; public alias `filter_categorical` |
| `filter_relation_connected` | Select entities connected to specified anchors |
| `filter_numeric` | Apply numerical comparisons or intervals |
| `filter_set_overlap` | Evaluate overlap with requested set values |
| `aggregate_values` | Compute count, sum, minimum, maximum, or average, with optional grouping |

The implementation must supply and register O before C3 can run. C3 proposes uses of those operations. It cannot silently invent a primitive.

Lightweight transformations require declared, versioned helpers. An unsupported operation produces a requirement for a later library version.

The slot extractor can call a model during F execution. Record its settings, usage, retries, and evidence. Other operators can be deterministic. These operators do not automatically call domain APIs, such as a hotel reservation endpoint.

## Internal procedure

The source equation is `F_t = Compose(O, S_t, G_t, Q_t, function_feedback)`. The paper permits composition, specialization, and lightweight adaptation. It then tests each function on the graph. [OaK section 3.2, Step 3](https://arxiv.org/html/2608.22974v1#S3.SS2).

The following validation loop is our proposed implementation:

```text
validate request, schema, graphs, operator catalog, and feedback versions
derive recurring computations and their evidence requirements
repeat within the composition budget:
    propose typed functions and bounded operator plans
    resolve every schema name, operator, helper, and data dependency
    validate argument contracts, result contracts, and control-flow bounds
    check explicit handling of required unknown or conflicting values
    execute against committed development graph revisions
    compare semantic fixtures with independently declared expected results
    if all release checks pass:
        return FunctionBundle and validation receipts
    retain diagnostics and repair within this component's scope
return unsuccessful result with unresolved requirements and all attempts
```

A plan defines argument binding, operator calls, data flow, branches, and permitted transformations. The runtime supplies a graph handle bound to one context and revision.

Under our selected runtime policy, generated plans cannot write domain facts, import arbitrary code, or call task-provider APIs. This restriction defines the implementation's execution boundary; it is not a claim that the paper prohibits every possible network call. A typed plan is not a proof of correctness.

If a function needs an undeclared property, C3 returns a schema requirement. It must not edit S. After a schema change, the coordinator requires validation or regeneration of dependent functions.

## Runtime example and limits

Each function has an agent-visible typed contract and an installed executable realization over O. The contract names arguments and results using S; the realization reads instance facts from G and performs the declared computation. F contains the reusable procedure, while G supplies the data for the current query. These are distinct artifacts. [OaK section 3.2, Step 3, PDF p. 4](paper/2608.22974v1.pdf#page=4).

For example, the following is a teaching sketch, not code supplied by the paper or an implemented function. The field names and result contract are illustrative:

```text
Agent-visible contract:
    eligible_offers(party_size: int, nights: int, max_total_usd: float)
        -> OfferEligibilityResult

Installed procedure, with G supplied by the runtime:
    lookup Offer entities in G
    read occupancy, minimum nights, and total price for the requested stay
    retain missing fields as unknown
    filter known records by occupancy >= party_size
    filter by minimum nights <= nights and total USD <= max_total_usd
    return eligible IDs and unresolved requirements
```

The agent chooses this function and supplies arguments. Its installed procedure performs the lookup and comparisons using O. The runtime's graph binding is our implementation choice. Function execution is not a second autonomous agent loop. The slot-extraction operator may itself call an LLM, as Appendix B specifies, without reconstructing F. [OaK Appendix B, PDF pp. 10 to 11](paper/2608.22974v1.pdf#page=10).

Consider the teaching function `check_offer_candidates(candidate_ids, party_size, nights)`. It looks up observed offers and reads the relevant fields. It separates incomplete records. It compares known occupancy and minimum-stay values with the arguments.

Its result contains evaluated outcomes and evidence references. This example does not select the pilot domain.

Each result records:

- Function version and graph revision.
- Evaluated constraints and their outcomes.
- Satisfied constraints, violated constraints, and unknown requirements.
- Source references and coverage limits.

A filter must not hide required unknowns. An empty result describes the searched graph and retrieval scope. It does not establish universal absence.

In the primary implementation, C2 builds Gq from the accompanying corpus Cq before the worker starts. C4 dispatches frozen F over that prepared graph. A function name or ontology field cannot create an endpoint binding.

The deferred live-API adaptation instead obtains native observations and adds supported facts through C2. Keeping native task-data tools alongside F changes the paper's exclusive kernel access policy and is not the primary implementation. [OaK sections 3.1 and 3.3](https://arxiv.org/html/2608.22974v1#S3.SS1).

During held-out execution, F remains fixed. The paper applies fixed S and F to new query graphs. [OaK section 3.3](https://arxiv.org/html/2608.22974v1#S3.SS3). C3 is disabled in this mode. Record defects for a later package.

## Failures

Local retries handle malformed proposals and failed plan validation within the shared budget. Incompatible revisions, undeclared concepts, and unavailable operators produce explicit diagnostics.

Distinguish a provider or operator fault from a wrong generated plan. Restarting C3 must preserve consumed budgets and failed attempts.

## Independent verification

These are required tests, not completed results. Use the [verification protocol](INDEPENDENT-VERIFICATION.md).

Supply a saved `ComposeRequest`, schema, graph snapshot, operator catalog, and independent expected results. C1 and C2 do not run. Use a recorded composer-response stub to test orchestration. Use fixed graph fixtures to test the plan runtime and operators.

| Test input or injected fault | Expected output | Measurable pass condition |
| --- | --- | --- |
| Valid saved request | FunctionBundle and validation receipts | All declared semantic fixtures produce independent expected results |
| Undeclared property or unregistered operator | Rejection | Zero plan executions |
| Mismatched schema or graph revision | Rejection | Zero graph reads through the rejected plan |
| Boundary value, missing value, conflict, or empty input | Typed result with evidence limits | Every expected outcome matches; no required unknown becomes satisfied |
| New graph revision during a call | Result from the bound revision | Every graph operation records the same revision |
| New facts with unchanged F | Updated result | Function hash stays fixed; result changes only as expected |
| Slot-extraction model failure | Explicit operator failure | Failure and costs remain recorded; no invented slots |
| Held-out composition request | Rejection | Zero composer model calls and no FunctionBundle mutation |

Stubbed operators test plan routing only. Test the real operators separately against literal expected results. Fresh model calls can produce different plans or slots.

C3 may write candidate plans, validation reports, and receipts. It must not change S, G, or provider state. Verify those boundaries with hashes and recorded call counts.

Record each operator, Cypher query, and model call beneath the agent-visible function call. [C5](05-evaluator-refiner.md) evaluates complete task correctness independently.
