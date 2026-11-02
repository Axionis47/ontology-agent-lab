# OaK: product design

We are building the algorithm in the [OaK paper](paper/2608.22974v1.pdf): observable construction, refinement, and inference around a fixed-model agent.
This document contains the complete product design. The linked specifications contain the detailed component contracts.

Design baseline 0.4.1 with task-boundary amendment 0.4.2. November 2, 2026.
Proposed product design with separate local contract checks.

**Start here:** [shared loop and task contracts](implementation/TASK-CONTRACT.md), [component architecture](implementation/README.md), [requirements graph](requirements/README.md), and [local setup](../OAK-SETUP.md).

The existing infrastructure is installed. The production input interface and OaK algorithms remain unimplemented.
The [implementation baseline](implementation/README.md) defines C0 through C11, storage, service boundaries, and delivery gates.
Its [harness report](implementation/INTEGRATION-HARNESS.md) states which local contracts have executable checks.

The [0.4.2 task contract](implementation/TASK-CONTRACT.md) governs the separation of agent loops, task definitions, task instances, and kernel packages.
It takes precedence over the offer-specific assumptions in the 0.4.1 baseline.
The baseline governs the remaining service boundaries and takes precedence over conflicting 0.3.0 details.
The [task independence review](implementation/TASK-INDEPENDENCE-REVIEW.md) identifies component corrections and service tests that remain pending.

## First product slice

Users authenticate, open a project, and select an agent configuration within that project.
An agent configuration describes the loop that uses the ontology. It does not represent a replacement for the complete agent application.

Use the managed `sequential_readonly/1` loop. One agent can bind multiple task definitions, each with its own typed inputs, tools, functions, evaluator, and kernel package.
Offer selection is the first engineering fixture. It does not define the product's permitted task list.
The [agent starting shape](implementation/AGENT-SHAPE.md) supplies the earlier complete fixture declaration; the 0.4.2 task contract defines its general boundary.
The offer fixture uses the existing read-only `search_offers` and `get_offer_details` tools.
Test unknown evidence, constrained selection, schema repair, dependency rebuilding, and activation before adding host adapters.
The local suite passes 70 of 70 checks: 24 SQLite substitute checks, 30 starting-shape checks, and 16 task-boundary checks.
The [harness report](implementation/INTEGRATION-HARNESS.md) explains their scope. Production construction, repair, and multi-task isolation remain unverified.
The synthetic harness does not select a live benchmark or demonstrate model improvement.

The frontend uses a human interface with separate schema, facts, dependencies, and run views.
Each view identifies its package and graph revision. Changes create candidates and require verification before activation.
See the [component map and architecture](implementation/README.md#component-map).

Use FastAPI and a separate worker, PostgreSQL application records, Neo4j facts, and immutable artifact files.
Use React with TypeScript and React Flow for the interface. Use OIDC with server-managed sessions for authentication.
These are selected design targets. The current harness does not establish that those services work together.

The [0.4.0 review](../OAK-PRD-REVIEW-0.4.md) records component reviews, integration challenges, and verification limits.

The first product adds reusable domain definitions and functions to a managed task loop.
Development evidence supplies the construction inputs. A frozen package supports later tasks with new observations.

Attachment to an existing external host is deferred until one concrete bridge passes the same boundary tests.
The first loop has a registered native catalog, a permitted tool subset per task binding, no cross-run memory, and no hidden task-relevant channels.
Tool descriptions alone do not supply executable bindings or result callbacks.

**The coordinator controls handoffs. Each component owns its internal algorithm.** Components exchange versioned artifacts. A replacement implementation must satisfy the same public contract.

## Document set

Read the shared loop and task contract first, then the architecture and component specifications. The input package and integration example show the offer-selection fixture.

| Document | Purpose |
| --- | --- |
| [Shared loop and task contract 0.4.2](implementation/TASK-CONTRACT.md) | Separate reusable loop behavior from task definitions, instances, and scoped kernel packages |
| [Task independence review](implementation/TASK-INDEPENDENCE-REVIEW.md) | Identify component alignment work and required multi-task isolation tests |
| [Implementation baseline 0.4.1](implementation/README.md) | Define the selected task, C0 through C11, storage, contracts, and release sequence |
| [Agent starting shape](implementation/AGENT-SHAPE.md) | Define the exact preset, loop invariants, binding probes, readiness evidence, and rejected integrations |
| [Task surface and corpus inputs](00-task-surface-and-corpus.md) | Define tasks, tools, sources, cases, and development samples |
| [C1 Schema builder](01-schema-builder.md) | Define S, encode supported OWL axioms, and run logical checks |
| [C2 Evidence and graph builder](02-evidence-graph.md) | Extract facts, resolve identity, preserve sources, and commit graph revisions |
| [C3 Function composer](03-function-composer.md) | Combine operators into typed domain functions |
| [C4 Host task executor](04-task-executor.md) | Apply the execution protocol through the host adapter |
| [C5 Evaluator and refiner](05-evaluator-refiner.md) | Score results independently and propose targeted repairs |
| [Controlled kernel workspace](06-kernel-workspace.md) | Propose business rules, verify changes, and activate reviewed versions |
| [Kernel data and user visibility](07-kernel-data-and-visibility.md) | Show definitions, observations, computations, and their evidence |
| [Deferred external-agent attachment](08-agent-onboarding.md) | Supporting analysis for a later concrete host integration |
| [Integration and query inference](INTEGRATION.md) | Define shared contracts, ownership, construction, and frozen execution |
| [Independent verification](INDEPENDENT-VERIFICATION.md) | Define isolated tests, injected faults, measurements, and debug records |
| [Writing guide](WRITING-GUIDE.md) | Define consistent terms and the limits of the STE review |
| [Example input package](examples/README.md) | Inspect synthetic inputs and expected results |
| [Version 0.3.0 review](../OAK-PRD-REVIEW-0.3.md) | Inspect design corrections and document checks |

The previous [0.2.1](../OAK-PRD-REVIEW-0.2.1.md), [0.2.0](../OAK-PRD-REVIEW-0.2.md), and [0.1.0](../OAK-PRD-REVIEW.md) receipts remain historical.

The five components are our implementation boundaries. The paper defines construction and inference, with four construction steps. We separate its knowledge-reasoning step into C3 and C4. See [OaK version 1, section 3.2](https://arxiv.org/html/2608.22974v1).

## Product problem and intended result

An agent can repeat the same work on each request. It interprets terms, connects records, compares constraints, and selects operations.

Consider a hotel offer. S defines occupancy and minimum stay. Observations supply the values. F compares those values with the request. An independent evaluator verifies the completed selection.

G stores observed facts and relationships. F computes over G. The agent selects calls. LangGraph controls component execution.

The intended result is an implementation whose behavior can be inspected and measured. Higher accuracy, fewer reasoning tokens, and lower cost remain hypotheses.

A successful HermiT result establishes a logical property of the encoded schema. It does not establish source truth or task success.

The workspace must expose rule meaning, sources, executable checks, test results, and enforcement scope. Each requirement needs links to its implementation and test receipts. Record any versioned deviation explicitly.

## Scope and source boundary

The first managed host supports the sequential read-only protocol. Each admitted task definition supplies its own contracts and permitted tools. General external-host attachment remains later work.

The scope includes input configuration, schema construction, graph extraction, function composition, execution, evaluation, and refinement. It also includes controlled edits, frozen packages, and observable handoffs.

The paper freezes K = (S, F). It builds each new graph from the query's accompanying corpus. Data access passes through the kernel. See [OaK sections 3.1 and 3.3](https://arxiv.org/html/2608.22974v1).

Our proposed live adaptation retains admitted native tools. F computes over observed facts and has no direct task-provider API access.
In the first managed loop, C4 sends actual tool observations to C2. A live provider remains separately gated.

The package selects one execution mode:

| Mode | Required behavior |
| --- | --- |
| `optional_functions` | The agent chooses whether to use F. No mandatory enforcement claim applies. |
| `guarded_requirements` | C4 applies version-bound checks at every declared protected action or final-result boundary. |

The package pins the mode and guard bindings. Comparisons must identify this intervention separately from ontology representation.

Human review and activation are also adaptations. The paper identifies human feedback as future work. See [OaK section 5](https://arxiv.org/html/2608.22974v1).

Model weights remain fixed. Provider contracts and native implementations remain unchanged. Previous removed implementations remain removed.

Before task execution, select the target API, evaluator, case population, model configuration, and budget. Teaching fixtures do not select or authorize a benchmark.

## Required boundaries

| Owner | Output | Permitted responsibility |
| --- | --- | --- |
| C1 | SchemaArtifact | Requirements, definitions, OWL encoding, and logical checks |
| C2 | GraphSnapshotRef and IngestReceipt | Domain-graph writes and source interpretation |
| C3 | FunctionBundle | Function plans, dependencies, and local behavior tests |
| C4 | TrialRecord | Dispatch protocol, observation order, function calls, and host integration |
| C5 | Assessment and RepairPlan | Independent scores and repair proposals |
| Host | Native tool results and host events | Model loop, instructions, memory, and native tool implementations |
| Coordinator | CandidatePackage and KernelPackage | Schedules, shared budgets, checkpoints, compatibility, freeze, and repair routing |

C5 cannot mutate active artifacts. The coordinator cannot modify a component's internal state directly. Each component must reject incompatible inputs before dependent work.

Independent operation means execution from saved inputs and declared dependencies. It does not mean that every component needs no database, model, or reasoner.

Use substitutes for isolation tests. Use real dependencies for separate service tests. Report those results separately.

## Implementation acceptance

Use the numbered cases and release criteria in [independent verification](INDEPENDENT-VERIFICATION.md).

1. Execute each component with saved inputs and declared dependencies.
2. Reject incompatible contracts, hashes, scopes, and versions before dependent work.
3. Report unsupported OWL encoding and unsatisfiable domain classes.
4. Preserve unknown values, conflicts, source identity, units, and time scope.
5. Reject observation-ID collisions with different payloads.
6. Preserve one committed revision when a completed ingest request is replayed.
7. Bind each function call to one stable graph revision.
8. Distinguish a tool invocation result from its external effect.
9. Resume uncertain writes through reconciliation, without blind repetition.
10. Invalidate affected projections and functions after schema changes.
11. Reject edits to frozen implementations and dependencies.
12. Permit independent evaluation to reject an otherwise successful execution.
13. Record every attempt, including failed calls and consumed resources.
14. Keep proposed human edits separate from the active package.
15. Block protected operations when required evidence is unknown.
16. Reject activation against a stale package or changed review hashes.
17. Preserve active-run versions and compatible rollback history.
18. Report intended changes, regressions, missing coverage, and tests not run.

These are proposed software acceptance criteria. They do not establish improved agent performance.

## Measurement requirements

Before evaluation, register the intervention, baseline, population, evaluator, assignments, primary metric, stopping rules, thresholds, and budget.

Use a competent baseline. Match model version, thinking configuration, source access, initial evidence, and budgets except for the declared intervention. Separate development, selection, and held-out cases.

If TravelPlanner is selected, use complete valid-plan rate. For another task, register its complete-success metric before evaluation. No target or evaluation denominator is selected here.

Compare initial and refined artifacts. Include equivalent-information documentation and competent reusable-function controls where necessary. Separate information, representation, computation, enforcement, and refinement effects.

Include every assigned failure and timeout. Report paired differences and case-grouped uncertainty. Report constraint errors, fixes, regressions, latency, and all model-role costs.

Separate construction cost from execution cost. Amortize construction over a declared workload. Compare efficiency at comparable correctness. At zero correct outcomes, cost per correct outcome is undefined.

The paper motivates measurement of these tradeoffs. It does not establish savings for our pilot. See [OaK section 4.7](https://arxiv.org/html/2608.22974v1).

## Implementation milestones

| Milestone | Required deliverable |
| --- | --- |
| M1 Input and contracts | Managed loop shape, registered bindings, input admission, saved handoffs, and isolated contract tests |
| M2 Schema boundary | C1, OWL coverage, logical checks, and failure receipts |
| M3 Evidence boundary | C2, source and identity policies, graph revisions, and replay tests |
| M4 Function boundary | Operator registry, plan runtime, C3, and independent expected results |
| M5 Host integration | C4, observation order, function calls, effect reconciliation, and traces |
| M6 Refinement and freeze | C5, repair routing, dependency invalidation, and immutable packages |
| M6a Controlled workspace | Rule review, regression reports, guards, atomic activation, and compatible rollback |
| M7 Selected task pilot | Registered, authorized task execution with complete outcomes and costs |

Use the stack in [setup and verification](../OAK-SETUP.md). The [research narrative](STATUS.md) records the design status.

This document revision launches no task execution, live model experiment, or benchmark.
