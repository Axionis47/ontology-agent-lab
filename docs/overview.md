# Project overview

[Documentation index](README.md)

## Objective

Oak aims to improve agent reliability through explicit task concepts, relations, and reasoning functions.
A reliable agent must use evidence that supports the requested result.
It must also stay within the task boundaries and granted tool access.

An ontology describes the concepts and relations for a task.
Oak combines this ontology with typed functions and execution rules in a harness.
A typed function has declared input types, output types, and executable operations.

The harness makes the necessary relationships available to the runtime.
For example, an action condition can specify a relation between the selected record and a permitted account.
The runtime uses observed tool results to evaluate that relation.
It records the function result and the action decision.

## Current scope

- A task contains one or more agent configurations.
- Each agent has its own task surface and tool grants.
- A task surface states responsibilities, rules, boundaries, success criteria, and examples.
- Task members can access all agents in that task.
- One agent executes each inference query.
- Model Context Protocol (MCP) supplies the external tool interface.
- Other developers and software teams provide the existing MCP tool implementations.
- Read tools and write tools use the same call interface and observation path.

The agent can follow existing graph relations without saving a new function.
A repair requires evidence of a specific definition gap.
The current scope excludes recursive agents and multi-agent coordination and a persistent agent memory system.
It also excludes model weight training and arbitrary generated-code execution.

## Product flow

| Stage | Input | Result |
| --- | --- | --- |
| Configuration | Task surface, tool connections, and grants | Saved agent configuration |
| Discovery | Configuration and a supplied tool environment | Observations, questions, requirements, and schema proposals |
| Baseline | All saved training cases | Basic agent trajectories and task evaluations |
| Construction | A compatible accepted candidate, or discovery and baseline evidence | A provisional candidate for validation |
| Validation and repair | Candidate definitions and saved cases | Rejected candidates or an accepted harness |
| Inference | Accepted harness and a new query | New observations, function results, and an answer or action outcome |

A prebuilt MCP tool is a unit of external work.
The baseline uses ReAct, a loop that selects actions and uses their results for the next decision.
The ReAct loop is the agent execution unit that selects and uses those tools.
Training improves the harness around this loop.
The trainer supplies each case's query, selected tools, and task-success description.
The internal evaluator judges the outcome from saved execution evidence.

During training, the runtime, tool grants, evaluator, and operator implementations remain fixed.
During inference, the accepted definitions also remain fixed.
New observations change the evidence graph for that inference episode.

## Paper and project decisions

The basis is *Toward Effective and Reliable LLM Agents via Dynamic Ontology*, arXiv:2608.22974v1.
See the abstract, Introduction, and Sections 3.1 through 3.3 in the [source paper](paper/source/oak-2608.22974v1.pdf).

| Paper mechanism | Project adaptation |
| --- | --- |
| Task schema and typed reasoning functions | A versioned harness with source mappings and tool bindings |
| Graph construction from task data | Graph updates from actual MCP responses |
| Construction with training examples | All saved trainer cases, including baseline trajectories |
| Formal schema verification | A supported Web Ontology Language (OWL) profile with HermiT |
| Evaluation and repair | Internal semantic evaluation and targeted declaration changes |
| Fixed definitions for unseen queries | Accepted definitions with a fresh graph for each inference episode |

Task membership, tool grants, the interface, and deployment choices are project decisions.
These product features are outside the paper mechanism.
The paper's benchmark results are not results from this repository.

## Engineering decisions

The paper defines a research mechanism. This project makes specific choices for its implementation and use with live MCP tools.
The tables distinguish implementation details from changes to the execution model.
They do not claim that every choice is new research or a required part of OaK.

### Implementing the paper mechanisms

| Paper basis | Concrete engineering choice | Source |
| --- | --- | --- |
| Schema verification | Define the supported OWL profile and run HermiT within resource limits. Separate invalid declarations from verifier failures. | [Schema verification](../backend/oak/ontology_verification.py) |
| Typed operator composition | Validate plan references and execute fixed operators with type, unit, scope, and computation checks. Distinguish missing values from empty results. | [Execution engine](../backend/oak/kernel_execution.py) |
| Entity identity and graph construction | Map actual tool responses to entities and relations. Define identity, source references, partial updates, replacement updates, and evidence completeness. | [Evidence graph](../backend/oak/evidence_graph.py) |
| Evaluation and iterative refinement | Run a basic ReAct baseline and evaluate every saved case against the candidate. Separate failure, inconclusive results, and evaluator errors. | [Training loop](../backend/oak/training.py), [task evaluator](../backend/oak/training_evaluation.py) |

The graph input differs from the paper's corpus extraction procedure.
Oak receives observations over time from external tools, including tools that change data.
Mappings must specify how those observations update the graph.
An incomplete response cannot establish that an unobserved entity or relation does not exist.

### Extending execution and repair

| Engineering question | Project decision | Source |
| --- | --- | --- |
| Which tools may the agent use? | Discover existing MCP tools within the user's grants. Check tool identity and declared arguments before each external call. | [Discovery](../backend/oak/discovery.py), [dispatcher](../backend/oak/kernel_dispatcher.py) |
| Which request controls the checks? | Extract typed values and check their preservation against the original request. Observations cannot redefine the user's task. | [Request preparation](../backend/oak/request_preparation.py) |
| How does missing data become an external request? | Derive dependencies from functions and validated graph queries. Check source selectors, requested fields, and pagination against the accepted source declarations. | [Evidence acquisition](../backend/oak/acquisition.py) |
| How can the agent change external state? | Run declared conditions against the proposed arguments and current graph. Issue a permit for that specific call. Record the actual response or error. | [Call checks](../backend/oak/kernel_dispatcher.py) |
| What follows an uncertain action outcome? | Stop without an automatic retry. Keep successful write responses as graph evidence. Repeated training requires prepared conditions or a trainer declaration of stable state. | [Execution and environment handling](../backend/oak/training.py) |
| Must every task route become a function? | Expose saved functions through `run_function` and temporary data plans through `query_graph`. Successful routes remain evidence without automatic function creation. | [Graph access](../backend/oak/graph_query.py) |
| What justifies a repair? | Record examined definitions, tested routes, evidence, and a proposed cause. Reproduce a definition defect from recorded inputs before checking its correction. | [Repair review](../backend/oak/repair_review.py) |
| What limits persistent growth? | Reuse compatible accepted definitions. Require support for additions. Reject exact duplicate definitions and unsupported constants. Remember rejected proposals against unchanged definitions and evidence. | [Definition checks](../backend/oak/definition_checks.py), [construction](../backend/oak/training_construction.py) |
| When can a candidate serve new queries? | Require validation, every saved case to pass, and matching task inputs and runtime versions. Keep accepted definitions fixed during inference. | [Acceptance checks](../backend/oak/kernel_acceptance.py) |
| How does execution stay within limits? | Bound model calls, tool calls, tokens, cost, and time. Save observations outside the model context and supply bounded views through references. | [Training manager](../backend/oak/training.py), [evidence access](../backend/oak/evidence_access.py) |
| How can a person inspect the changes? | Use saved candidates and events to show definitions, dependencies, reviews, routes, validation, and unchanged decisions. Identify historical records that lack repair reviews. | [Training views](../frontend/src/features/training/harness-ledger.tsx) |

Temporary graph access extends the paper's function-catalog interface.
Processing all saved cases also differs from the paper's random sampling in each construction round.
These are deliberate project choices. They require evaluation in this implementation.

Diagnosis uses recorded observations and cannot make external calls.
A failed route search does not prove that a definition is missing.
An unresolved cause can end training with no harness change.
The checks apply declared conditions. They cannot guarantee that the declarations cover every task requirement.

The current evidence views do not perform automatic semantic compaction.
Recurring-pattern promotion and coordination between ReAct loops remain future work.
See the opening README for the [future direction](../README.md#future-direction).

## Success conditions

The first demonstration must complete discovery, baseline execution, construction, validation, and inference on a small task surface.
Each result must keep its actual tool calls and supporting evidence.
Inference must preserve the accepted definitions and original access boundaries.

A separate comparison on new requests is necessary before a reliability claim.
The comparison must use the same model, initial conditions, grants, and resource limits.
It must report failures and incomplete runs as well as successes.
See [Tests](tests.md#live-model-evaluation) for the current evidence limits.
