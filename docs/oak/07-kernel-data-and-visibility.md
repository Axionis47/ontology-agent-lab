# Kernel data, hierarchy, and user visibility

Design version 0.4.3. November 2, 2026. This document defines proposed data views for the [kernel workspace](06-kernel-workspace.md). The interface is not implemented. The [input specification](00-task-surface-and-corpus.md) and [integration contract](INTEGRATION.md) define construction and execution.

A user must be able to connect a business requirement to its meaning, evidence, executable check, evaluation, and version. A graph image alone does not establish these connections.

Use the [independent verification plan](INDEPENDENT-VERIFICATION.md) for cross-component checks.

## Four separate structures

| Structure | Meaning | Interface view |
| --- | --- | --- |
| Ontology schema S | Types, properties, relationships, identities, and supported axioms | Concept and relationship browser with formal details |
| Instance graph G | Observed entities, values, relationships, and sources under S | Scoped records and connected graph records |
| Navigation hierarchy | Product groups that help users find information | Requirements, concepts, evidence, checks, and versions |
| Computation and control | F operations and workflow transitions | Function trace and separate workflow view |

The paper separates schema, evidence graph, and typed functions. Generic operators provide executable graph and data procedures. [OaK sections 3.1 to 3.3 and Appendix B](https://arxiv.org/html/2608.22974v1). Navigation and storage views are our implementation choices.

A class hierarchy expresses subtype relationships. One class can have multiple declared parents. It need not fit a folder tree. `Offer HAS_QUOTE LocalQuote` does not make a quote a subtype of offer. Disjointness and restrictions are logical axioms. [W3C OWL 2 Primer, sections 4.2 to 4.4 and 5.1](https://www.w3.org/TR/owl2-primer/).

Keep the supported OWL encoding and HermiT report separately inspectable. [OaK section 3.2, Step 1; Appendix A](https://arxiv.org/html/2608.22974v1).

`Offer`, `LocalQuote`, `Request`, and `Observation` are proposed fixture types. They are not an implemented schema. Do not invent subclasses for display. `Business rules > Stay suitability > Minimum stay` is a navigation path. It is not an OWL assertion. A numbered function trace records computation, not domain relationships.

## Records and ownership

The conceptual kernel is K = (S, F). G supplies task evidence. [OaK sections 3.1 and 3.2, Steps 2 to 3](https://arxiv.org/html/2608.22974v1). The proposed storage design adds inspection and reproducibility.

| Record | Representation | Owner and visible information |
| --- | --- | --- |
| Business requirement | Versioned structured record | Requirement owner: intent, source, applicability, hard/advisory status, exceptions, and open questions |
| S | Readable JSON and OWL export | C1: concept/field IDs, definitions, units, relationships, and encoding coverage |
| Raw observation | Immutable payload and envelope | C4 captures; C2 references fields, scope, source time, and outcomes |
| G and revision manifest | Scoped Neo4j domain and evidence records | C2: accepted assertions, unresolved identities, conflicts, and source references |
| F | Typed contracts and bounded executable plans | C3: arguments, operators, evidence needs, checks, and outputs |
| Evaluation and trace | Immutable reports and ordered events | C4/C5: operations, results, failures, assignments, and resource use |
| Package and review history | Immutable manifests, proposals, and decisions | Coordinator: versions, comparisons, validation receipts, and activation state |

Neo4j answers graph queries from operators. JSON and OWL describe the schema. They do not supply observed values. F plans define computations. LangGraph checkpoints store workflow progress. Each view must identify its artifact type and version.

C2 initially uses schema-guided Phi extraction. Direct JSON-field mapping would be a separate, versioned implementation choice. The paper describes chunking, extraction, and primary-key merging. It does not specify our Neo4j storage representation. [OaK section 3.2, Step 2](https://arxiv.org/html/2608.22974v1).

## Existing fixture data and proposed graph data

The [example package](examples/README.md) contains synthetic source files. Extraction has not run. No domain graph or validated function bundle exists for this fixture. Distinguish source records from proposed graph data in every view.

[dev-001](examples/development-cases.jsonl) requests an available offer for four people in Example City. The stay is March 10 to 12, 2027. The budget is USD 420, including fees. Reservations are outside this fixture's scope.

The initial observation list is empty. Matching replay calls can expose the recorded responses. The responses are not automatically available to the agent.

[observations.jsonl](examples/observations.jsonl) contains these values:

| Source | Exact o3 values | Context and source time |
| --- | --- | --- |
| obs-search-001, `payload.offers[2]` | `offer_id=o3`, `max_occupancy=4`, `min_nights=null`, `total_price=390`; availability absent | March 10 to 12, party 4; March 1, 2027, 10:00 UTC |
| obs-detail-001, `payload` | `offer_id=o3`, `max_occupancy=4`, `min_nights=1`, `available=true`, `total_price=390`, `currency=USD` | Same dates and party; March 1, 2027, 10:01 UTC |

The search envelope specifies USD and `total_for_requested_stay_including_fees`. The detail response repeats that price basis. The [fixture policy](examples/domain-policy.txt) defines null as unknown. Availability applies to the stated request. The fixture makes no live inventory claim.

Search includes a next-page token. Its three offers are not the complete result population. Replay must preserve the original source timestamps.

A proposed projection is:

```text
Offer o3
  HAS_QUOTE -> LocalQuote obs-detail-001/o3
LocalQuote obs-detail-001/o3
  FOR_REQUEST -> Request dev-001
  SUPPORTED_BY -> Observation obs-detail-001
  total = 390 USD, including fixture fees
  stay = 2027-03-10 to 2027-03-12, party = 4
```

The local quote ID comes from the observation and offer IDs. It is not a provider quote ID. The source supplies no hotel ID. Do not invent a Hotel node.

Keep normalized fields linked to original fields. The physical schema is not implemented. Unknown search availability must remain unknown. Detail evidence applies only after C2 admits that observation.

## Inspect a business requirement

The default entry is “An offer's minimum stay must fit the requested stay.” Its view has these sections:

1. **Intent:** show the source, scope, exceptions, and hard/advisory mode.
2. **Meaning:** show the minimum-night field, units, and offer/request context. The runtime comparison is not automatically an OWL axiom.
3. **Evidence:** show search null and detail one night for o3. Include field references and source times.
4. **Computation:** show the proposed comparison with the two-night request. Include related occupancy, availability, and price checks.
5. **Evaluation:** show expected behavior and actual receipts when available. For this fixture, show “Not executed.”
6. **Version:** identify the schema, extractor, graph revision, function, and package for each result.

Provide both a graph view and a record table. Selecting a value must reveal its source. Selecting a failed check must reveal its inputs and operations. A change discussion creates a draft with stable target references. See the [workspace contract](06-kernel-workspace.md).

Selecting a function must reveal its typed inputs and outputs, schema dependencies, evidence needs, and example results.
The user can suggest a change from a schema item, graph record, function, requirement, or task result. The suggestion creates a candidate rather than editing the active item.
The candidate view shows the agent's interpretation and the schema/function diff beside separate OWL, projection, function-test, and regression results.
The regression table includes protected previously passing development cases and their base/candidate outcomes. A logical pass and a task failure must remain visibly distinct.

## Separate status signals

| Status | What it establishes | Remaining limit |
| --- | --- | --- |
| Meaning represented | The distinction has a reviewed definition | Sources can still omit values |
| Evidence available | Applicable observations support a value | The function can ignore it; the value can become stale |
| Check implemented | A named procedure evaluates the requirement | Its behavior can remain untested |
| Behavior verified | Named independent tests have passing results | Other inputs can fail |
| Enforcement bound | Named protected paths require the check | Undeclared paths can remain uncovered |

Give logical consistency, source faithfulness, function behavior, and task outcomes separate reports. Show unknown, conflicting, stale, unsupported, and not-run states with their causes. Coverage must name its registered requirements or assigned cases. For zero eligible items, show `not_applicable` and a reason.

The optional-functions pilot permits native tools alongside F. It cannot claim universal enforcement. Mandatory guards require a separate execution-policy version. This differs from the paper's exclusive kernel data channel. [OaK section 3.1](https://arxiv.org/html/2608.22974v1).

## Independent view contract

Build each view from an immutable, scoped read snapshot. Bind the package, evidence context, graph revision, and result references. Reject incompatible references before showing a verified result. A missing receipt must produce an explicit unknown or not-run state.

Test this view without C1 to C5 or a live graph database. Supply saved source records, projection fixtures, function receipts, and evaluation reports. Mark projection fixtures as simulated. Use a read-only fixture repository that records attempted writes. The view must not write domain data or active packages.

| Test | Input or fault | Exact expected result |
| --- | --- | --- |
| KV-T1 | Source records with no extraction or check receipts | Source values appear; graph and check states remain not executed |
| KV-T2 | Search record with null stay and absent availability | Both requirements remain unknown; neither becomes false or satisfied |
| KV-T3 | Detail record from another task context | It does not satisfy this task's evidence requirement |
| KV-T4 | Function receipt with an incompatible graph revision | Verified status is withheld; the mismatch is visible |
| KV-T5 | Navigation parent and a non-subtype relationship | Neither becomes an OWL subclass assertion |
| KV-T6 | Evaluator-only expected answers | Constructor and agent views expose zero evaluator-only values |
| KV-T7 | Empty coverage population | Show `not_applicable`, denominator zero, and a reason |
| KV-T8 | Replayed source response | Source time remains unchanged; replay time appears separately |
| KV-T9 | Open, filter, and inspect all views | Domain-data and active-package write counts remain zero |

Save expected labels, actual labels, source references, and operation counts for every assigned test. Report mismatches and missing receipts. These tests are proposed and have not run.

## Acceptance and limits

The user must distinguish missing definitions, extraction omissions, unavailable evidence, and unused checks without reading code. Every result must reveal its scope and version. Keep evaluator-only expectations outside constructor and agent views. Preserve active artifacts and historical receipts when candidates change.

The paper identifies extractor and judge dependence as limitations. It also identifies evaluator quality, incremental graphs, and human feedback as further work. [OaK section 5](https://arxiv.org/html/2608.22974v1). This interface is our proposed extension. Inspection does not guarantee correct behavior or complete knowledge.

Source attribution: Xiaohui Zhang et al., *Toward Effective and Reliable LLM Agents via Dynamic Ontology*, [arXiv:2608.22974v1](https://arxiv.org/abs/2608.22974v1), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
