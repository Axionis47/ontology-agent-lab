# AppWorld implementation plan for review

Status: Proposed. This plan does not start implementation or paid model runs.
Product scope update, 2026-11-08: [PRD 1](01-task-surface-discovery.md) controls product discovery.
Its frontend, backend SDK, user controls, and supplied-environment requirements supersede this draft for discovery.
This document retains the scope of a later AppWorld benchmark comparison.
Scope revision: AppWorld replaces the local hotel and stock fixtures as the evaluation environment.

## 1. Deliverable and controlling scope

Build and evaluate one ReAct agent on AppWorld tasks.
Use AppWorld's existing Model Context Protocol (MCP) server for external operations.
Use Python for typed graph operators and generated function plans.
Use Web Ontology Language (OWL) and HermiT for supported schema checks.
Do not add a memory subsystem, frontend, or new MCP server.

This scope supersedes fixture-specific requirements in the other component documents.
The hotel and stock profiles are no longer implementation targets.
The fixed two-function catalog is no longer a requirement.
The earlier fixture results remain historical evidence only.
They provide no evidence of AppWorld performance.

Keep the generic invariants from [PRD 00](00-system-contracts.md).
Revise each component's source assumptions against observed AppWorld capabilities before implementation.
Do not carry over a global source version, database transaction, or idempotency guarantee without evidence.

## 2. Verified environment and project decisions

AppWorld provides an MCP server for its application programming interfaces (APIs).
Its official guide describes connecting the Gemini command-line interface (CLI) and activating a task world.
The guide also requires explicit state saving after direct MCP execution.
See the [terminal-agent guide](https://github.com/StonyBrookNLP/appworld/blob/main/guides/evaluating_terminal_agents.md).

AppWorld supplies train, development, and two test splits.
Its evaluator checks task outcomes and unintended state changes.
See the [official evaluation and development rules](https://github.com/StonyBrookNLP/appworld#no_entry_sign-agent-development-restrictions).

| Decision | Required behavior |
|---|---|
| Target | AppWorld tasks and the official evaluator |
| Inference | One Gemini ReAct agent per isolated task attempt |
| External calls | Model-selected calls through the existing AppWorld MCP server |
| Reasoning | Typed Python functions composed from trusted graph operators |
| Function catalog F | Generated from the agent's task surface, API contracts, and training evidence |
| Function count | Determined by required computations. No fixed count or required hotel function names |
| Graph G | Facts accepted from actual tool responses during the current attempt |
| Working subgraph g | Indexed evidence selected from a function's declared dependencies |
| Schema S | Generated declarations checked through OWL and separate evidence validation |
| Repair | Training feedback identifies the schema, mapping, relation, or function to change |
| Final comparison | Plain ReAct and ontology-guided ReAct on matched AppWorld tasks |
| Completion | Save final world state, then run the official evaluator outside the agent |

The agent still selects native tools and kernel functions.
The runtime checks their declared prerequisites.
Python functions cannot contain hidden application calls or read AppWorld databases directly.
The function catalog can change between construction rounds.
It remains fixed during a scored inference attempt.

## 3. Data separation

Use official `train` tasks for construction examples, probes, trajectories, and targeted repair.
Reserve complete training scenario groups for internal regression checks.
Keep scenario variants together when making this internal split.

Use `dev` for configuration selection and development error analysis.
Do not use development examples as construction demonstrations.
Record every configuration change influenced by development results.
A revised candidate must pass the retained training regressions again.

Use `test_normal` and `test_challenge` only after the configuration and kernel are frozen.
Do not inspect their task-level failures to improve prompts, mappings, relations, or functions.
Keep test trajectories outside the construction and repair corpus.
Report official aggregate results for each test split separately.
These boundaries follow the [AppWorld development rules](https://github.com/StonyBrookNLP/appworld#no_entry_sign-agent-development-restrictions).

The running agent receives its task instruction and permitted interface information.
It does not receive solutions, evaluator code, expected state, or hidden task metadata.
Keep benchmark data and evaluation files outside its filesystem and shell access.
Do not add hardcoded application calls to the harness.
AppWorld requires the agent to select those calls.

## 4. First implementation phase: establish AppWorld access

Pin the AppWorld package, data release, server, Gemini CLI, and integration versions.
Run the official installation checks before model experiments.
Activate one training task using AppWorld's world initialization interface.
Use an isolated world for each attempt and each comparison condition.
A server holding one active world must not serve concurrent attempts.

Connect Gemini to the official MCP server.
Discover its actual tool names, input types, output format, and permitted grants.
Check authentication, pagination, task time, completion, and write responses using training worlds.
Record the exact protocol observations.
Do not infer capabilities from tool names alone.

Prove the before-dispatch gate and the result transformation boundary.
Prove client registration and dispatch for the internal Python function tools.
A prompt that describes a function is not proof of executable tool registration.
Stop with a capability error if the client cannot support these boundaries.

Save the world state after native MCP execution.
Run AppWorld's official evaluator outside the model process.
This first phase must demonstrate native interaction and evaluator output before ontology experiments start.

## 5. Task surface and construction

Inspect training instructions, allowed API documentation, and observed training tool responses.
Select a bounded task surface with relevant read and write operations.
Record its task IDs, scenario groups, grants, requirements, and limits before candidate generation.
Choose the surface from this evidence. Do not invent a replacement task.
Report its selection rule and denominator in every subset result.

Generate an initial requirement analysis and schema proposal.
Associate each proposed relation with a task requirement and an observed source-field mapping.
Reject relations that have no supported role or evidence.
Check the supported OWL declarations and report unsupported axioms.
Check identities, missing facts, conflicting facts, and coverage separately.
OWL consistency alone does not establish correct task behavior.

Generate a function catalog from recurring computations in the training tasks and trajectories.
Each function declares typed inputs, outputs, dependencies, and incomplete-evidence results.
Its executable plan composes the trusted Python operator library.
The catalog must not encode training entity IDs, expected answers, or task-specific exceptions.
Do not require exactly two functions or two relations.

Run the training agent with native tools and the candidate catalog.
Record successful, failed, rejected, and uncertain operations.
Compare the final world with the official training evaluator.
Use this feedback to diagnose the earliest failed requirement or component.

Create a candidate patch against exact artifact versions.
Patch the affected mapping, relation, schema declaration, or function plan.
Keep original requirements, grants, primitive semantics, and the evaluator fixed.
Run affected regression cases first, then the complete retained training suite.
Record newly failed cases and their dependency paths before candidate selection.
A failed candidate does not replace the previous valid kernel.

## 6. Inference and action flow

```text
AppWorld instruction + frozen task-surface kernel
                         |
                         v
                    ReAct decision
                    /            \
        native AppWorld MCP     typed Python function
                 |                       |
        validate actual result     select working g
                 |                       |
       update graph and coverage   execute operators
                 \                      /
                  typed observation + evidence
                              |
                       next ReAct decision
                              |
                    permitted native action
                              |
                observe effect and update evidence
                              |
                   complete, save, evaluate
```

Each accepted fact refers to an actual tool observation.
Publish partial evidence with explicit scope and missing dependencies.
A partial page does not prove that no other matching records exist.
A function that needs complete coverage must wait for that coverage.
Do not require a complete copy of every AppWorld application database.

Preserve typed identities within their application and resource namespaces.
Keep conflicting observations and their provenance.
A working subgraph contains only the facts needed for the current function and its coverage checks.
The model receives relevant results, missing evidence, and available next operations.
The full graph remains outside model context.

Use an episode-local graph revision for evidence changes.
Use provider versions only when an actual interface supplies them.
A local revision does not establish an atomic snapshot across applications.

Before a write, bind its target and arguments to the current request and supporting function results.
Record the intent before dispatch.
Serialize calls within one attempt.
Invalidate affected evidence after a state change.
Use a supported read operation to confirm the result when required by the action contract.

If a write times out, preserve an unknown outcome.
Use documented reconciliation capabilities where they exist.
Do not invent an idempotency key or retry an uncertain non-idempotent write automatically.
Do not modify AppWorld applications to add transaction features for the ontology condition.

## 7. AppWorld comparison and victory criteria

Run plain ReAct and ontology-guided ReAct with the same model and AppWorld interface.
Give them the same tasks, initial states, grants, base instructions, and resource limits.
Count Python calls and MCP calls explicitly.
Record result projection and semantic admission as parts of the ontology treatment.
A difference between these conditions measures the complete treatment.
Use a predeclared ablation before attributing that difference to one component alone.

Use AppWorld's official task and scenario success measures as the outcome metrics.
Keep task success separate from client termination, graph validity, and tool-call validity.
Report cost, model tokens, calls, retries, latency, and blocked valid operations.
A blocked action or an OWL pass is not a completed benchmark task.

Select initial limits using training and development evidence.
The former 12-turn, 24-call, 30-world, and 240-world fixture settings do not define this experiment.
Record task membership, limits, repetitions, statistical method, and stopping rules before final testing.
Do not choose favorable test subsets after inspecting outcomes.

A mechanism demonstration requires all of these results:

1. Native AppWorld observations populate the graph with traceable facts.
2. Generated Python functions use those facts and affect a subsequent agent decision.
3. At least one actual AppWorld action has an observed outcome.
4. A targeted construction repair fixes a training failure without breaking retained regressions.
5. The frozen candidate completes held-out development tasks under the official evaluator.

A reliability claim additionally requires a matched improvement over plain ReAct on frozen test evaluation.
Report task and scenario scores, denominators, and uncertainty for paired differences.
Define the statistical procedure before testing and account for related scenario variants.
Report `inconclusive` when the evidence does not support an improvement.
Do not claim that the mechanism prevents all long-tail failures.

## 8. Component revision checklist

| Component | Retain | Revise for AppWorld before implementation |
|---|---|---|
| 00: System contracts | Single-agent scope, Python operators, OWL, grants, receipts, frozen inference | Provider-dependent versions, operation scope, and calibrated limits |
| 01: Discovery | Catalog evidence, requirement trace, capability tests | Official MCP bindings and training-derived task surface |
| 02: Construction | Typed plans, targeted patches, corpus lineage, retained regressions | AppWorld samples and a variable function catalog |
| 03: Evidence | Typed identity, provenance, conflicts, indexed subgraphs | Per-tool pagination, partial publication, and mutation invalidation |
| 04: Inference | Typed observations, checked dispatch, actual function registration | Dynamic AppWorld operations and task-derived prerequisites |
| 05: Actions | Bound intent, outcome confirmation, unknown-state handling | Actual API capabilities without synthetic database guarantees |
| 06: Evaluation | Independent scoring, paired comparison, repair logs | Official splits, task evaluator, scenario metrics, and test isolation |

The retained component drafts contain superseded fixture details.
Their status notes prevent those details from becoming AppWorld requirements.
Complete each revision from the discovered interface evidence before implementing that component.
Do not treat the old module paths or fixture code as an AppWorld design reference.

## 9. Deliverables and current status

The implementation must produce:

- A versioned AppWorld environment and task selection manifest.
- The generated schema, OWL report, mappings, function plans, and operator traces.
- Construction trajectories, targeted patches, and retained regression results.
- Native inference traces, receipts, action outcomes, and saved world references.
- Official evaluator outputs, matched comparison results, and the cost ledger.
- A clear statement of tested scope, failed cases, and unsupported capabilities.

No AppWorld integration or benchmark execution occurred during this plan revision.
No paid model call is authorized by this document.
Check the remaining authorized experiment budget before scheduling future calls.
