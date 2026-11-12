# Project instructions

## Project mission

**Improve agent reliability by making implicit task relationships explicit.**

Every mechanism and implementation change must serve this mission.
The mission summarizes the paper's purpose. It is not a direct quotation or a claim of proven project results.

Source: *Toward Effective and Reliable LLM Agents via Dynamic Ontology*, arXiv:2608.22974v1.
See the abstract, Introduction, and Sections 3.1 to 3.3 in the [original paper](docs/paper/source/oak-2608.22974v1.pdf).
The paper makes domain concepts, relations, and reasoning procedures explicit to support decisions based on evidence.

## Agreed scope

- Focus on single-agent inference.
- Define one mechanism at a time. Implement only the requirements agreed with the user.
- Keep the implementation small. Add complexity only when a current requirement needs it.
- Do not build a general framework or speculative features for future needs.
- Use the paper and current user decisions as the project basis. Do not use the old repository as a design reference.
- Do not create a data model or additional design documents unless the user requests them.

## Task surfaces and tool access

These are project decisions. They are not requirements stated in the paper.

- A task can contain multiple agents.
- Each agent has its own task surface.
- Users with access to a task can access all agents in that task.
- Model Context Protocol (MCP) is the standard interface for access to tools in this project.
- The task has a shared set of tools from multiple MCP servers.
- The user selects which individual tools each agent can access from that shared set.
- Each agent can access only the tools that the user grants to it.
- Generate the ontology for the task surface within these access boundaries.
- The agent structure allows future multi-agent support. Multi-agent coordination is outside the current single-agent inference work.

## MCP tools and task queries

- A query is a task instruction. It can require information, external actions, or both.
- Treat each granted MCP tool as one callable operation.
- Validate its arguments against its declared input schema.
- Use the same call interface for tools that read data and tools that change data.
- Do not require separate read and write workflows for the demo.
- Keep construction, training, and inference independent of particular task domains and tool names.
- Record the actual arguments and response or error for each call.
- Use actual tool responses as task context and evidence.
- Use one result-processing path for read and write tools. Both can supply facts for the working graph.
- Record successful executions and returned facts for later reasoning. Do not require a separate read to use a write response.
- Keep the original task boundaries and tool grants authoritative.

## Training samples and initial demo

The trainer is the person who supplies the training samples.
The trainer is responsible for correct sample queries, tool selections, and task-success descriptions.

- Each training sample contains a query, selected tools, and a plain-language task-success description.
- Select each sample's tools from the agent's granted tools.
- The task surface can have more tools than one sample needs.
- The selected tools define the available sources and operations. Actual tool responses supply the observed task data.
- The training loop supplies one internal semantic evaluator for the samples. Do not require evaluator setup during sample entry.
- Start with exploration and the initial requirement and schema proposals.
- Treat the ontology as an evolving task-specific harness around a basic ReAct loop.
- Run the saved cases through basic ReAct first. Use these trajectories and discovery proposals to construct the harness.
- Run ReAct with the harness on all saved cases. Use task outcomes and traces to improve its schema and typed functions.
- Keep the base runtime, tool grants, evaluator, and operator implementations fixed during training.
- Run all saved training samples. Use their observations, outcomes, and traces to construct and improve the shared schema and typed functions.
- Use the internal evaluator to judge semantic task success for the requested answer, external outcome, or both.
- The loop identifies supported construction changes and targeted repairs. The trainer does not supply a condition checklist or repair plan.
- Use the resulting schema and typed functions during inference on new queries.
- Keep the accepted harness definitions fixed during inference. Update its working graph from new observations.
- Record actual calls, observations, function execution, and evaluator results.
- Keep the initial demo small. Its purpose is to demonstrate the construction loop and inference with its output.
- Use the reviewed Darwin-Agent/HarnessX execution and evolution strategy described in PRD 2 as an implementation reference.
- Evolve ontology declarations through the existing runtime. Keep the internal evaluator and original task boundaries fixed.

## Personal writing preferences

- Never use em dashes in conversation or user-facing writing.
- Use commas, colons, parentheses, or separate sentences instead.

## Documentation standard

Use **ASD-STE100 Simplified Technical English (STE)** for all project documentation that you create or change.
Use **Issue 9, dated January 15, 2025**, as the reference edition.
The [official ASD-STE100 website](https://www.asd-ste100.org/) identifies this edition.

Apply this rule to requirements, design documents, data model definitions, plans, procedures, API documentation, comments, and change records.
Use the same clear style in project explanations and progress reports.

Follow the official writing rules and controlled dictionary.
The instructions below are a project summary. They do not replace the standard.

- Use short sentences with a clear subject and action.
- Give one instruction in each sentence. Use the command form for procedures.
- Use active voice where possible. Identify the person or component that performs each action.
- Use each approved word with its approved meaning and part of speech.
- Use technical nouns and technical verbs as permitted by the standard.
- Define project terms before use. Use one term for each concept throughout the documentation.
- Explain each abbreviation at its first use.
- Avoid idioms, slang, metaphors, and unnecessary words.
- Preserve technical meaning when you simplify a sentence.
- Preserve exact code identifiers, API names, file paths, formulas, and units.
- Keep source papers, direct quotations, and source snapshots unchanged. Apply STE to the explanations that we write.
- Review new and changed text against the official rules and dictionary. Do not claim full STE compliance without this review.
