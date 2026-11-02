# OaK implementation

## Purpose and current scope

Build the algorithm in the OaK paper. Use the [root design document](README.md) as the product entry point. Explain the problem, the mechanism, and the measured outcome. Treat ontology as an engineering choice whose value must be tested.

We are implementing the algorithm in the OaK paper, with observable construction, refinement, and inference loops. External provider APIs remain unchanged; our ontology-aware functions may wrap and compose their supported calls. A live-API extension is an explicit adaptation of the paper's accompanying-corpus workflow. The live benchmark/API and model configuration still need to be selected before live task execution. Offer selection is a local engineering fixture; the [task contract](docs/oak/implementation/TASK-CONTRACT.md) defines support for multiple task definitions under one loop.

Only OaK is in the active implementation scope. Other paper walkthroughs and experiments are not build requirements. Preserve existing experiments, results, and papers.

## Agreed stack and working style

- Python 3.12 in the root `.venv`, managed by `uv`; `pyproject.toml` declares dependencies and `uv.lock` pins resolved versions. Do not use global packages as evidence that the project environment is ready.
- LangGraph coordinates construction/refinement and frozen-kernel inference. Its workflow graph is distinct from the domain knowledge graph. Use persistent checkpoints for local pause/resume and keep the frozen kernel immutable during held-out inference.
- Pydantic defines strict artifact and function contracts. Neo4j Community stores the knowledge graph; Python functions use the official Neo4j driver and parameterized Cypher. Neo4j Browser is the graph inspection UI.
- OWL/HermiT verifies the schema separately from graph storage and task validation. Owlready2 provides the Python integration, and OpenJDK 21 runs its bundled HermiT. Record this reasoner distribution/version; do not claim it is the paper's exact binary. RDFLib is not required for the chosen Neo4j backend.
- LangSmith provides nested execution traces, with Studio for workflow/state inspection once its account connection is configured. Keep local JSONL events and immutable artifact snapshots as well. Hosted observability is not configured merely because the SDK imports.
- Trace schema/function versions, graph provenance, actual provider settings, tool inputs/outputs, internal API/Cypher operations, checks, retries, failures, timing, and token/cost accounting. Count an agent-visible wrapper call separately from the underlying operations. Do not request hidden reasoning text.
- Keep the user in the loop: explain each milestone, show the actual artifacts and traces, and state what is implemented, simulated, unverified, or still pending. Do not silently launch a full benchmark while discussing setup or design.
- Keep credentials in ignored `.env` and local service/evidence state in ignored locations. Never print credentials. Bind development services to localhost and preserve existing Neo4j data when stopping/restarting services.
- See [setup and verification](docs/OAK-SETUP.md). Installation probes establish infrastructure readiness, not an implemented OaK algorithm or improved agent behavior.

## Shared research narrative responsibility

Read [RESEARCH-NARRATIVE.md](RESEARCH-NARRATIVE.md) before designing, implementing, evaluating, or interpreting OaK. It records the research question, mechanisms, implementation evidence, and current conclusions.

The person or assistant changing an experiment owns the corresponding synthesis update in the same work session. Keep detailed evidence with the experiment and link it from the narrative. Before calling the work complete, ensure the narrative reflects any changed design, result, or conclusion.

Every substantive experiment update must explain:

1. The task decision that was failing or the engineering work being repeated.
2. The exact distinction, relationship, mapping, function, or check that changed, with artifact versions.
3. The consumer that used that change, supported by observable inputs, operations, and outputs.
4. The difference in the primary metric, relevant errors, and costs, with denominators and uncertainty.
5. Alternative explanations and the controls used to distinguish them.
6. Which shared claim is supported, weakened, contradicted, or unresolved.

Preserve the common question while allowing the answer to change. Include failures, regressions, inconclusive comparisons, and cases where ontology adds no benefit. Do not select results to manufacture a positive narrative or average incompatible outcomes into one ontology score.

## Fixed-model scope

- Keep model weights fixed. Do not implement or launch fine-tuning, reinforcement learning, gradient updates, or learned updater training.
- Improve external artifacts: definitions, source-linked facts, mappings, retrieval, prompts, typed functions, and deterministic checks.
- Use development examples to construct and refine artifacts. Freeze artifacts before evaluating their use on separate held-out cases. Explain that this changes external knowledge and procedures rather than model parameters.
- Keep model version, thinking configuration, source access, examples, and budgets fixed across a paired comparison except for the declared intervention. Record the actual settings sent to the provider.
- Thinking must remain enabled for the planned LLM comparisons. Do not silently disable it to save cost or create a larger treatment effect. Record reasoning-token usage without requesting hidden reasoning text.
- Use a capable current model for the main LLM question. Treat comparisons across model strengths as separate declared experiments, without weakening a baseline to force a gain.
- Reading papers or editing documentation does not authorize launching live model experiments. Execute live work within the user's requested scope and the environment's permissions.

## Experimental design and measurement

Define the intervention, competent baseline, task population, primary metric, scoring method, and resource budget before evaluating. Use the same target cases across conditions. Verify that cases require the distinction being tested and include controls where ontology may offer no benefit. Keep learning, selection, and held-out evaluation data distinct.

The primary metric is complete task success under the selected independent evaluator.
If TravelPlanner is selected, use complete valid-plan rate. Report constraint violations, fixes, regressions, tokens, tool operations, latency, and cost.
Local fixture and contract-test pass counts are software checks, not agent-performance metrics.

- Use independent expected answers or effect checks. Agreement between implementations, schema validity, or mandatory tool use alone does not establish task correctness.
- Count all assigned cases, including failures and timeouts. Define the denominator for every rate. Report paired differences and uncertainty; repeated runs of a case remain grouped when estimating uncertainty.
- Separate complete success from partial constraint satisfaction. Report targeted errors alongside final task completion.
- Separate input, output, cached, and reasoning tokens as supported by the provider, avoiding double counting. Include all model roles and failed attempts in costs.
- Count agent-visible tool calls and underlying operations separately. A composed function can hide operations without eliminating them.
- Report construction, refinement, and maintenance costs separately from execution, then amortize over a declared workload. Include failed execution costs in cost per correct result. With zero correct results, report that this ratio is undefined.
- Evaluate efficiency at comparable correctness. Fewer tokens from early failure is not an improvement.
- Preserve historical results and treatment identities. Put new runs in new locations and capture artifact versions, observable traces, checks, and effect receipts.

## Identify what actually contributed

Separate the conceptual model, instance facts, provenance, computation, and execution policy. A schema defines maximum occupancy; a source supplies a hotel's occupancy value; a function checks it against party size; an evaluator verifies the resulting plan. Identify which of these changed.

Distinguish the effects of additional information, explicit representation, reusable computation, enforcement, and refinement. If testing representation itself, provide a control with equivalent information in ordinary documentation or schemas. If functions or tools also change, label the combined intervention.

A model-written rule is a proposal until a consumer uses it. Trace observable behavior rather than treating the model's explanation as proof of causation. Logical consistency, data conformance, source faithfulness, function correctness, and verified effects are separate checks.

Unknown is not false. State completeness assumptions used to infer absence. Resolve identity through authoritative identifiers and scope. Preserve units, time, negation, exceptions, and source references. OWL domain and range axioms are not ordinary input-validation rules.

## Sources and writing

- Use the pinned [OaK paper](papers/pdfs/2608.22974v1.pdf) as the algorithm reference. Inspect the primary source for substantive claims and cite its relevant section, table, or PDF page.
- Distinguish source claims, our interpretations, proposed experiments, teaching fixtures, historical observations, and new live results. Label adaptations and inspired experiments accurately instead of calling them exact reproductions.
- Keep mirrored PDFs unchanged. Respect distribution restrictions. Never commit credentials, private databases, private grader answers, or decrypted benchmark derivatives. Keep temporary research tools and extracted text outside the tracked tree.
- Explain the problem before introducing terminology. Define concepts through a concrete example and keep its meaning consistent.
- Never use em dashes in conversation or user-facing writing. Use commas, colons, parentheses, or separate sentences.

## Verification

For documentation changes, check local references, source accuracy, unfinished placeholders, and the no-em-dash preference. Check YAML frontmatter when editing skills. These are document checks, not evidence of improved agent behavior.

For software changes, inspect the actual environment and run checks appropriate to the implementation. Preserve unrelated user changes.
