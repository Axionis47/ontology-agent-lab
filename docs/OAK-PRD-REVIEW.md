# OaK design review and integration receipt

November 2, 2026. Design version 0.1.0. Classification: proposed adaptation and synthetic teaching material. No task execution, live model experiment, implemented UI, or measured agent benefit is reported.

The [PRD](OAK-PRD.md) indexes the separate input, component, and integration documents. The user requested multiple agents, explicit component ownership, paper citations, a full inference explanation, and configurable development corpora. This receipt records the resulting review and research-narrative update.

## Review ownership

| Review agent | Contribution |
| --- | --- |
| paper_boundary_audit | Primary-paper audit, C1 schema document, input/corpus document, and final source-fidelity review |
| live_integration_review | C2 graph document, graph-versus-functions explanation, and runtime/effect cross-review |
| component_contract_review | C3 composer and C5 evaluator documents, candidate/graph contract review, and fixture consistency review |
| Primary agent | PRD, C4 executor, integration walkthrough, example assets, synthesis integration, and final document checks |

The source is Xiaohui Zhang et al., *Toward Effective and Reliable LLM Agents via Dynamic Ontology*, [arXiv version 1](https://arxiv.org/html/2608.22974v1), licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Documents cite specific sections, steps, and appendices near substantive source claims. The [paper catalog](../papers/catalog.json) preserves the pinned source identity.

## Findings resolved before delivery

- Distinguished the paper's two overall stages and four construction steps from our five implementation components.
- Made fresh random sampling explicit for every construction round and limited its design graph to selected-case evidence plus explicitly shared references.
- Added coordinator-owned CandidatePackage assembly between function composition and task execution.
- Required serialized graph commits, atomic expected-parent checking, and stable revision reads.
- Separated invocation outcome from external-effect status and prohibited uncertain writes from becoming confirmed graph facts.
- Aligned the shared fixture across input, graph, and integration documents: selection only, four people, two nights, USD 420, and explicit availability evidence.
- Removed unsupported hotel edges from that fixture. Local quote identities derive from source records and are not provider identifiers.
- Kept recorded response availability separate from initially visible task evidence, with new run identities and preserved source times on replay.
- Kept evaluator expectations outside the corpus. The synthetic evaluator requires supported outcomes, not mandatory F use or a particular tool sequence.
- Labeled retained native tools as a deliberate departure from sole-kernel access, rather than an unspecified paper detail.

The final source and cross-component reviews reported no remaining must-fix issues within their review scopes. This is a documentation review, not verification of a running implementation.

## Compatibility with shared research records

| Shared concept | Mapping in this design |
| --- | --- |
| Study identifier | `oak-refinement`, with actual target still unselected |
| Evidence classification | `proposed_adaptation`; worked inputs are `teaching_fixture`, never `measured_result` |
| Design identity | PRD/component version 0.1.0; separate source, schema, extractor, function, operator, and runtime versions required for future runs |
| Primary metric | Existing TravelPlanner complete valid-plan rate remains conditional on selecting TravelPlanner. The synthetic `complete_task_success` example is not silently substituted into that study |
| Assignments and denominator | No research-run assignment matrix or evaluation denominator exists. One synthetic development case and zero held-out cases illustrate the interface |
| Trial and assessment contracts | Planned runtime artifacts; future adapters must map them explicitly to shared run/outcome/resource records |
| Conditions | Competent baseline, initial/refined artifacts, and information/computation controls require registration before evaluation |
| Claim status | Unrun; the shared benefit hypothesis remains unresolved |

No outcome or claim records were added to the shared JSON registers. Their hashes remained unchanged. The six required narrative answers appear in the new OaK design section of [RESEARCH-NARRATIVE.md](../RESEARCH-NARRATIVE.md).

## Document verification

Checked Markdown links, code-fence balance, unfinished placeholders, trailing whitespace, and the no-em-dash preference. Parsed the JSON and JSONL assets and embedded JSON examples. Verified configuration paths, matching inline/file examples, tool/response IDs, request dates and party scope, price units, evaluator separation, and the deliberately empty held-out manifest.

The single fixture's expected selection agrees with its displayed constraints and observations. This is an internal documentation consistency check. No extractor, graph function, replay service, evaluator implementation, or task agent was executed. Tool and evaluator implementations are explicitly absent; these assets cannot yet be loaded as a runnable experiment.

## Shared document hashes

The initial narrative hash was checked before the first scoped update. The intermediate narrative was checked again before expanding the design into separate documents. Other shared artifacts were read and remained unchanged.

| File or state | SHA 256 |
| --- | --- |
| Narrative before this work | `a47aa482f2e761f92674e0d7bd07569d2a6cede143372fc85bc369b6089b885f` |
| Narrative after initial PRD integration | `95a37e5603914fa94a2a2c7ed58cad4040ad94fb172642644e5df566ed0048d4` |
| Narrative after final integration | `eb7b52ef8a8712b33f4902585f894140d6693d0e57dee4baf3958ecc315af57f` |
| Shared record schema unchanged | `a82358e8d42600685bda833efdcaf8728f31a9d3097efbfc71c9ee79bc2de6b8` |
| Study register unchanged | `6e4a165cdbc295c83d5c1ac0a78ae68fffa1a81f8fa5668b8d87d989de5f6963` |
| Claim register unchanged | `b376ce38fbc18a92773778c59da4dcd26f16c1b91f38529cf006d281b1cccdef` |

## Delivered artifact hashes

These hashes identify the reviewed document set and example inputs. A later edit requires a new receipt or an updated explicitly identified review, rather than treating these hashes as current.

| File | SHA 256 |
| --- | --- |
| `docs/OAK-PRD.md` | `5af7ff9554da96a31b9911bab5f7ee21e37042dbfd4379e90474e4a88d501a79` |
| `docs/oak/00-task-surface-and-corpus.md` | `3c45b69de3ad8c74db25c798b4a255ac1dda00f1e05e5cdbbe303035189b2e05` |
| `docs/oak/01-schema-builder.md` | `7d1fc32e2f992e22c2b3f595a41e1d4b14121a71757e0124e493ab5b791004f3` |
| `docs/oak/02-evidence-graph.md` | `087ced0ef35a826ec36d1f0f6716f8a9544c6bb0ab5c40c97047aba72649062f` |
| `docs/oak/03-function-composer.md` | `89a065adbfc34fe7fb56cee2a794e32a36a1da5ae61a579fdbb4ebc105ca9f17` |
| `docs/oak/04-task-executor.md` | `5a6b65fe091dea5b0a95dc6b34e750c7a9ab37a809010e844aa110a03927e6f0` |
| `docs/oak/05-evaluator-refiner.md` | `9a3845d2050e21fd502a3c453aa8fc76690215711d80d8a9f623dd2253b47613` |
| `docs/oak/INTEGRATION.md` | `bcc9350dcd97505d77adb216a0a54ef66a3c8aeed5e0c2d55b4c2b220e2186cf` |
| `docs/oak/examples/README.md` | `95665ca98c0e82921d1ccac47a942da2418a202fe79e8f1c4a62b8f7ef57a1e4` |
| `docs/oak/examples/development-cases.jsonl` | `c47e7abd4d9f519942d9e77a25308218d99e31234c14968cfd39afdc48ced478` |
| `docs/oak/examples/domain-policy.txt` | `4ba1dff2e1dd9bf9ccee846a259fe832793fea5a5a78cea98c0b253f1f014107` |
| `docs/oak/examples/held-out-manifest.jsonl` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `docs/oak/examples/observations.jsonl` | `03255344e4849e96da34a0ed406174e449463b47b7305cd46d9a19d1bac72b77` |
| `docs/oak/examples/private/evaluation-spec.json` | `49c33f47b5f81ad3d6021411fc7638a448ed47733a587b9230e623cdeb7c960b` |
| `docs/oak/examples/task-surface.json` | `5455be8b3d9f4825fd88422e0b87c9d25dfa1a67dcc603d1ed82c93e656c118a` |
| `docs/oak/examples/tool-manifest.json` | `da0b418a905ccc37756c67c1c3ef1bbf8277ff4ddd70043a71a3473e7810db1a` |
