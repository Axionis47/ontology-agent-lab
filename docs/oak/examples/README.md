# Synthetic task surface input package

Design guide version 0.3.0. The fixture data format remains version 0.1.0.

These files illustrate the [input specification](../00-task-surface-and-corpus.md). They describe one synthetic accommodation-selection case. They are documentation fixtures. No live connection, replay service, or benchmark result is supplied.

Start with [task-surface.json](task-surface.json).

| File | Consumer and purpose |
| --- | --- |
| [tool-manifest.json](tool-manifest.json) | Input admission and host integration: two read-tool contracts and matching rules |
| [domain-policy.txt](domain-policy.txt) | Construction: definitions, scope, units, unknown values, and completion conditions |
| [development-cases.jsonl](development-cases.jsonl) | Sampler: request, context, coverage tags, initial evidence, and available responses |
| [observations.jsonl](observations.jsonl) | Construction and future replay: one search response and one detail response |
| [private/evaluation-spec.json](private/evaluation-spec.json) | Future evaluator: synthetic expected results and evidence requirements |
| [held-out-manifest.jsonl](held-out-manifest.jsonl) | Empty reserved-case manifest |

The evaluator file contains invented teaching expectations. It contains no real private grader data. Its separate location demonstrates a future runtime boundary. A directory does not enforce access control. A future loader must exclude this file from builder and agent prompts.

The agent starts with no observations. `source_response_ids` lists responses available to matching replay calls. It does not make those responses initially visible.

A future replay adapter must match the tool ID, version, arguments, and case scope. Unmatched requests return an explicit unavailable-fixture result.

Create new call and observation IDs for replay. Preserve the fixture source. Keep original observation time separate from replay time.

Search returns o1, o2, and o3. o1 violates capacity. o2 violates minimum stay. o3 needs detail evidence for minimum stay and availability.

A complete selection requires evidence for every required constraint. The evaluator does not require F or a particular tool sequence.

The pagination marker records incomplete coverage. No second-page fixture exists. The task requires a supported suitable offer, not an exhaustive market search. A request for the absent page must return an explicit fixture limitation.

Previous document verification covered JSON/JSONL syntax and internal references. Input admission, tools, replay, extraction, graph execution, and the evaluator remain unimplemented.

The [independent verification plan](../INDEPENDENT-VERIFICATION.md) defines future tests. Use these files as saved inputs. Add explicit test stubs and independent expected outcomes. Label stub results as engineering test results.

Budgets are illustrative. One development case and zero held-out cases cannot establish generalization or an ontology benefit.
