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
