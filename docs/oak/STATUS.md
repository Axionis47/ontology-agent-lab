# OaK research and implementation status

The active project implements the OaK paper only. The [complete design](DESIGN.md) contains the product requirements and detailed specification links.
Other experiments and reading material are historical context, outside the active build.
The previous cross-experiment narrative is preserved locally at `.runtime/history/oak-front-page-2026-11-02/RESEARCH-NARRATIVE.md`.
Unrelated published experiments, results, and papers have been removed from the active repository at the user’s request. There is no archive directory. Unpublished local experiments and research remain outside this cleanup commit.

The research question remains: when do explicit domain definitions and reusable functions improve a fixed-model agent's decisions, and at what cost?
Keep schema meaning, observed facts, computation, enforcement, and refinement distinct when answering it.

## Repository organization

The root README is a short entry point. The full design, current status, and OaK source paper live under `docs/oak/`.
The previous AppWorld project, dependencies, CI workflow, evidence viewer, and paper collection are removed from the active repository.
This changes navigation and test discovery only. It changes no OaK algorithm, requirement, or experiment conclusion.

## Current design and verification

The [0.4.2 task contract](implementation/TASK-CONTRACT.md) separates reusable loop behavior from task definitions and instances.
The [0.4.1 implementation baseline](implementation/README.md) supplies the service architecture.
The [task independence review](implementation/TASK-INDEPENDENCE-REVIEW.md) records remaining component alignment and isolation checks.
Offer selection is an engineering fixture. It is not the product's only permitted task.

The repeated engineering problem was that one offer-specific declaration conflated loop behavior and task contracts.
The new local consumer is `oak_contracts/task_boundary.py`, a strict declaration and registered-binding validator.
Its tests use offer selection and ticket classification to check different task schemas under one loop catalog.
These checks do not execute production construction, repair, activation, or task isolation.

The publication check passed 70 of 70 assigned local tests: 24 SQLite substitute tests, 30 starting-shape tests, and 16 task-boundary tests.
The source hashes and individual outcomes are in `.runtime/oak-contracts/20261102T213043Z-3e8a7225/receipt.json`.
The [harness report](implementation/INTEGRATION-HARNESS.md) explains the implemented path and limitations.
No model or task-provider calls ran. No task-performance difference, paired uncertainty interval, or cost saving was measured.
The existing demonstration changes observed evidence while keeping schema and functions fixed. It does not demonstrate learned refinement.

Production services, the managed agent loop, schema construction, and feedback-driven repair remain pending.
The task-boundary amendment is not yet fully reflected in the older component specifications and requirements graph.
No live benchmark, model configuration, evaluation population, or execution budget has been selected.
Future comparisons still require equivalent-information documentation, competent reusable functions, matched provider settings, and frozen held-out artifacts.
The claim that ontology refinement improves agent outcomes remains unresolved.

## Preserved OaK design history

The sections below record earlier design stages and their then-current evidence. Their versions and test counts are historical.

## Active OaK implementation: infrastructure stage

The intended engineering task is to construct and refine domain definitions and executable functions for a fixed-model agent, while making every consumer and operation inspectable. Provider APIs remain unchanged; local wrappers may compose their supported operations. Mapping live API responses is a declared extension of the paper's reference-corpus input. The exact target API/benchmark, independent evaluator, model, and run budget remain undecided.

The version 0.1.0 setup in [pyproject.toml](../../pyproject.toml), [Neo4j configuration](../../infra/compose.yaml), [project instructions](../../AGENTS.md), and [setup guide](../OAK-SETUP.md) selects Python/LangGraph for control flow, Pydantic for contracts, Neo4j for facts and relationships, LangSmith plus local records for observability, and Owlready2/HermiT with Java for formal schema checks. These are implementation choices, not claims that the paper used these exact packages or storage representation.

The installation probe exercises strict input validation, persisted LangGraph state and pause/resume, a rollback-only Neo4j query, and real HermiT inference and contradiction detection. It does not generate a task ontology, compose domain functions, call a model, or score benchmark cases. Probe receipts and dependency versions are recorded by the setup guide. There is no task-evaluation denominator, primary-metric difference, uncertainty interval, or measured agent benefit. Model/API execution cost for this setup is zero; installation effort and network transfer costs are not comprehensively measured.

Future comparisons must include competent handwritten or coding-agent-built wrappers and equivalent-information schemas/documentation. The ontology, additional facts, computation, enforcement, and refinement contributions remain separate questions. Infrastructure verification supports readiness only; the shared benefit hypothesis remains unresolved.

## OaK component design proposal

The November 2, 2026 [task surface PRD](../OAK-PRD.md), initially version 0.1.0 and now extended to 0.3.0, links separate specifications for five independently implementable components: schema builder, evidence and graph builder, function composer, host task executor, and evaluator/refiner. The [integration document](INTEGRATION.md) defines versioned handoffs, candidate assembly, repair routing, and query inference; each component owns its internal algorithm and bounded retries. This decomposes the paper's knowledge-reasoning step into composition and execution. The [version 0.1.0](../OAK-PRD-REVIEW.md) and [version 0.2.0](../OAK-PRD-REVIEW-0.2.md) review receipts remain historical; the [version 0.2.1 receipt](../OAK-PRD-REVIEW-0.2.1.md) covers the onboarding clarification below.

The [input-surface specification](00-task-surface-and-corpus.md) separates task definition, reference material, development requests, observed evidence, round sampling, and independent evaluation. Its [synthetic example package](examples/README.md) supplies inspectable JSON/text assets for one selection request and two recorded responses. These are documentation fixtures, with no implemented input UI, replay service, extractor, or task evaluator. The example's held-out manifest is intentionally empty and supplies no evaluation population. Graph consolidation, function composition, and feedback-driven artifact refinement remain distinct operations.

The version 0.1.0 live-pilot design keeps the host's native tools and adds functions that compute over observed graph facts without direct provider API access. An observation bridge sends tool responses to the graph builder before dependent function calls. This explicitly changes the paper's sole-kernel data-access policy and does not enforce use of the ontology on every native action. The corpus consists of scoped case evidence gathered over time; domain documentation explains meanings separately. Construction and inference use the same incremental acquisition protocol, with no whole-world preload.

| Narrative requirement | Design status |
| --- | --- |
| Repeated task decision | The targeted work is repeated interpretation and checking of domain constraints against observed records. This design adds no new observed task failure or performance result. |
| Changed artifact | PRD 0.1.0 defines schema, graph, function, trial, assessment, and repair handoffs, with explicit ownership, dependency invalidation, and frozen-package rules. It changes the proposed design, not executable experiment code. |
| Consumer and observable behavior | Planned consumers are the five components and the host agent. Acceptance criteria require source observations, graph revisions, function inputs and outputs, and independent effect receipts. No such task consumer has run for this design. |
| Metric and cost | The target API, case population, evaluator, model settings, and budget remain unselected. There is no evaluation denominator, metric difference, uncertainty interval, or new task-execution cost. The existing TravelPlanner metric remains conditional on selecting that task. |
| Alternatives and controls | The PRD requires competent baselines, equivalent-information documentation and reusable-function controls as appropriate, and separates native-tool access from mandatory enforcement. Extraction, representation, computation, and refinement remain distinguishable interventions. |
| Shared claim | The design is unrun. It supplies implementable boundaries and acceptance requirements, not evidence that ontology improves correctness, reasoning effort, or cost. The shared benefit hypothesis remains unresolved. |

## Controlled human editing and kernel visibility proposal

The user requested a controlled way to inspect the kernel and add business constraints that automatic construction may miss. PRD 0.2.0 adds the [kernel workspace](06-kernel-workspace.md) and [data hierarchy and visibility specification](07-kernel-data-and-visibility.md). Formal ontology types/properties/axioms, observed graph instances, executable functions, and UI navigation remain distinct. The proposed user path follows a business requirement through its meaning, source observations, computation, independent checks, and active version. The existing synthetic selection fixture supplies inspectable raw values; no populated graph or passing model result is implied.

Natural-language input becomes a versioned requirement and isolated candidate, with scope, exceptions, unknown handling, source needs, and affected dependencies. C1 through C5 remain the planned consumers through their original ownership boundaries. The workspace adds reviewable differences, layered verification, declared regression cases, atomic promotion, active-run pinning, and compatible rollback. There are no new execution receipts, metric denominators, uncertainty estimates, or measured usability outcomes. Actual task API, evaluator, model settings, and budget remain unselected.

Version 0.2.0 distinguishes `optional_functions` from `guarded_requirements`. A rule cannot be called enforced in the optional mode. The proposed guarded mode adds mandatory C4 checks at declared protected dispatch/finalization paths, with exact version/argument/evidence receipts and unknown-data handling. Immediate policy activation additionally requires a dispatch barrier and reconciliation of already-dispatched operations. These are execution-policy requirements, not implemented protections or properties supplied by OWL.

The paper describes model-judge repairs and identifies human feedback as future work; its hotel case also required function changes after schema changes. See [OaK sections 3.2, 4.6, and 5](https://arxiv.org/html/2608.22974v1). Human-provided information, execution guards, visibility, and artifact refinement are separate proposed contributions. Comparisons must declare those interventions rather than attributing their combined effect to ontology representation. No new benefit claim is supported: the extension is unrun, its UI and guard are unimplemented, and the shared hypothesis remains unresolved. The review receipt records the exact changed documents, source audit, acceptance requirements, and before/after narrative hashes.

## Existing agent onboarding clarification

PRD 0.2.1 adds the [existing-agent attachment contract](08-agent-onboarding.md). The unresolved engineering issue was that tool descriptions alone do not supply executable bindings, host result hooks, memory provenance, or access to delegated operations. The proposed AgentAdapter retains the host's model loop, instructions, memory, skills, and native implementations while registering F, adding versioned kernel context, binding task scope, and ingesting actual tool events. C4's pseudocode is a conceptual protocol, not a requirement to replace the host loop.

The new capability report distinguishes description-only input, callable access, fully connected optional-function operation, guarded operation, and black-box request/result access. Opaque delegate results do not establish inner provider receipts or guarded behavior; remembered observations retain source age. The prospective consumers are C4 and host adapters, with admission receipts and operation traces required before claiming an integration works. No adapter, admission probe, new case assignment, metric difference, or runtime result was produced. Prompt/context additions, memory conditions, partial observability, and enforcement remain declared controls and limitations. This is a proposed integration clarification, with no new measured support for the shared benefit hypothesis.

## Independent OaK components and document revision

Design version 0.3.0 rewrites the OaK specifications with short sentences and consistent technical terms. The [writing guide](WRITING-GUIDE.md) defines the review limits. Full ASD-STE100 conformity remains unverified.

The review found conflicting host-loop ownership and incomplete replay, event-order, budget-recovery, and failure-record contracts. These are design gaps, not observed runtime failures. The host retains its loop. C4 owns the integration protocol through declared host interfaces.

The [integration contract](INTEGRATION.md) now defines causal IDs, separate process and task states, durable resource reservations, and observation dependencies. C2 must bind observation identity to payload hashes. Its graph commit and ingest receipt must persist atomically. Component tests use saved inputs and declared dependencies.

The [independent verification specification](INDEPENDENT-VERIFICATION.md) defines 22 integration fault cases. Each case names its owner, injected fault, expected result, and measurable invariant. Component, workspace, visibility, and adapter documents add isolated tests. Expected answers remain separate from production functions.

| Narrative requirement | Revision evidence and limit |
| --- | --- |
| Repeated engineering problem | Broad acceptance statements did not always identify exact fault inputs, allowed effects, or failure ownership. |
| Changed artifact | PRD and component design version 0.3.0, with shared execution contracts and explicit independent tests. |
| Consumer | Future component implementers and test runners. Document checks ran; OaK runtime consumers did not. |
| Outcome and cost | Runtime tests are not run. Task denominators, metric differences, uncertainty, and costs remain unmeasured. The review receipt reports document checks separately. |
| Alternatives and controls | Recorded-response replay separates local logic from fresh model variation. Service tests separate substitute behavior from real dependencies. Independent expected outputs detect agreement on a wrong answer. |
| Shared claim | The revision improves the precision of the proposed design. It supplies no measured agent benefit or proven runtime reliability. |

The [version 0.3.0 review receipt](../OAK-PRD-REVIEW-0.3.md) records document checks and preserved historical artifacts. No benchmark, model run, or provider action was launched. Earlier experiment results and source papers remain unchanged.

## OaK implementation baseline and documentation graph, version 0.4.0

The November 2, 2026 [implementation baseline](implementation/README.md) extends the proposed product to C0 through C11.
It defines authentication, projects, agent-loop configurations, API coordination, graph inspection, and controlled schema changes.
An agent configuration identifies the loop that consumes domain knowledge. It does not replace a complete agent application.
The [shared contracts](implementation/CONTRACTS.md) define storage authority and versioned handoffs.
The [architecture decisions](implementation/DECISIONS.md) require existing libraries for general infrastructure.

The selected first engineering class is a bounded, read-only offer-selection loop over the existing synthetic tools.
The domain problem is deciding whether observed capacity, minimum stay, availability, and inclusive price support one selection.
This choice fixes the first tools and consumer protocol. It does not select a live API, scientific case population, model, or budget.
The planned C3 implementation initially binds an audited function template. This is a limited adaptation of open-ended function composition.

The [local contract harness](implementation/INTEGRATION-HARNESS.md) executes strict Pydantic handoffs and SQLite substitute storage.
Its saved source observations first leave offer `o3` unresolved. A detail observation supplies the missing evidence, after which the fixed function accepts `o3`.
The schema and function remain unchanged in this demonstration. The observed change is evidence enrichment, not schema refinement.
The published fixture evaluator supplies an independent literal expected selection. It is not a general source-grounded benchmark scorer.

The harness passes 24 of 24 assigned software fault checks in the recorded run.
That denominator concerns the named integration tests, including failed-gate blocking, scoped access, replay, and immutable run bindings.
It is not a task-performance denominator or a paired treatment comparison. No uncertainty interval or model-efficiency conclusion follows from it.
The harness makes zero model and task-provider calls. Full construction effort and infrastructure cost were not measured.

Production OIDC, API, PostgreSQL, Neo4j integration, schema compilation and repair, queue recovery, and browser journeys remain release gates.
HermiT results, source interpretation, function behavior, and independent task outcomes require separate receipts.
The proposed repair route rebuilds dependent projections and functions before review and atomic activation.
Held-out execution remains frozen. Auth, human review, and incremental tool observations remain explicit adaptations.

The [documentation standard](implementation/DOCUMENTATION-STANDARD.md) uses StrictDoc for stable requirement IDs, typed relations, and agent-readable exports.
StrictDoc is a development dependency. Its transitive RDF tooling is for documentation, not a change to the Neo4j domain backend.
Graph validation establishes documentation structure only. A relation to a test does not establish a passing test result.
The [documentation receipt](requirements/validation-0.4.0.json) records 421 graph nodes and 138 linked requirements.
Its native checks reject four malformed-source cases. A standard-library dependency audit rejects a cycle accepted by StrictDoc's typed-relation export.
All 217 production test obligations remain unrun. The 24 passing harness checks retain their separate substitute scope.

Alternative explanations remain unchanged: additional facts, reusable computation, enforcement, and representation can each explain observed behavior.
Future fixed-model comparisons must include competent baselines and the declared equivalent-information and reusable-function controls.
The shared ontology-benefit claim remains unresolved. This session adds design and local software-contract evidence, not a new agent-benefit result.

## OaK starting-shape amendment, version 0.4.1

The engineering gap was an underspecified onboarding boundary: task profile, loop structure, implementation identity, and readiness were conflated.
The [starting shape](implementation/AGENT-SHAPE.md) now separates them and defines ten explicit compatibility invariants.
The first profile is a managed sequential read-only loop, with two exact fixture tools, typed decisions, empty initial evidence, and no cross-run memory.
Its task remains offer selection. This is a narrower implementation commitment, not a universal format for all agent applications.

The implemented consumer is the strict Pydantic declaration validator, with a complete JSON preset and generated JSON Schema.
The recorded check receipt (`.runtime/oak-contracts/20261102T204349Z-5627fb0c/receipt.json`, local only) contains 30 passing declaration checks and the existing 24 passing SQLite substitute checks.
It records tested code and fixture hashes. The schema, function, model, and task-performance results from earlier work do not change.
The 54-test denominator measures software assertions only. No paired task comparison, primary-metric change, uncertainty estimate, or efficiency result follows.

The design now retains agent-version identity through admission and defines separate pre-kernel binding and full-package conformance evidence.
Candidate verification uses fresh session-scoped assignments, the shared run ledger, and complete per-package C5 scoring batches.
Owner review receives the exact server-sealed verification set. Initial evidence without a loading contract is rejected.
The active PRD defers external-runtime attachment until a concrete bridge passes the required boundary tests.

The host, API, authentication, reasoner-based repair, queue recovery, and browser paths remain unimplemented production gates.
The declaration parser does not prove callable execution or hook behavior. No model or task-provider call ran.
Alternative explanations and the required equivalent-information, computation, and enforcement controls remain unchanged.
This amendment resolves design ambiguity and supplies local contract evidence. The shared ontology-benefit claim remains unresolved.
