# Project terms

[Documentation index](README.md)

Use these terms with the meanings in this table.
Exact code identifiers can differ from the prose term.

| Term | Meaning |
| --- | --- |
| Agent | The model-driven component that selects actions for a task instruction. |
| Task | A shared workspace with an objective, scope, members, connections, and agent configurations. |
| Task surface | An agent's responsibilities, rules, boundaries, success criteria, examples, and granted tools. |
| Tool grant | Permission for an agent to use one tool from a task connection. |
| Query | A task instruction that requests information, an external action, or both. |
| Training case | A saved query, selected tool list, and task-success description. |
| Trainer | The person responsible for correct training cases. |
| Discovery | The process that explores granted tools and proposes task requirements and a schema. |
| Ontology | A declared set of task concepts, properties, and relations. |
| Schema | The definitions of entity types, properties, identities, and relations. |
| Harness | The schema, typed functions, mappings, and execution declarations around the agent loop. |
| Kernel | The code and paper term for the harness definitions. |
| Candidate | One proposed version of the harness. |
| Accepted harness | A candidate that passes the necessary validation and training checks. |
| Typed function | An executable plan with declared input types, output types, and necessary evidence. |
| Graph query | A temporary data plan that reads the current evidence graph without changing harness definitions. |
| Repair review | A versioned record of failure evidence, examined definitions, tested routes, proposed cause, and change decision. |
| Definition catalog | A view of saved definitions, versions, dependencies, evidence, and use. |
| Change history | A view of reviews, route tests, changes, validation, and unchanged decisions. |
| Operator | A fixed runtime operation that a generated function can use. |
| Operation binding | A declaration that connects a native tool call to its request and function conditions. |
| Observation | A recorded tool response or error, with its arguments and call identity. |
| Evidence graph | The entities, properties, and relations accepted from observations in one episode. |
| Provenance | References that connect a fact or result to its source observations. |
| Coverage | The extent of the observed source data for a specified scope. |
| Episode | One execution of one query with its own context and evidence graph. |
| Baseline | The basic agent execution before the candidate harness is applied. |
| Training | Construction and improvement of harness definitions from saved cases. |
| Inference | Execution of a new query with fixed accepted definitions. |
| Evaluator | The internal component that judges task success from the case and execution evidence. |
| Repair | A targeted change to candidate declarations after a failed check or task outcome. |
| Digest | A content hash used to identify exact inputs, definitions, or evidence. |
| Cost reservation | An estimated amount held against a run allowance before a model call. |
| Unknown outcome | A call result that does not establish whether an external action completed. |

## Abbreviations

| Abbreviation | Meaning |
| --- | --- |
| ADC | Application Default Credentials |
| API | Application programming interface |
| CI | Continuous integration |
| CLI | Command-line interface |
| HTTP | Hypertext Transfer Protocol |
| HTTPS | HTTP over Transport Layer Security |
| JSON | JavaScript Object Notation |
| LLM | Large language model |
| MCP | Model Context Protocol |
| OWL | Web Ontology Language |
| ReAct | Reasoning and acting through a tool-call loop |
| SDK | Software development kit |
| SQL | Structured Query Language |
| STE | Simplified Technical English |
| TLS | Transport Layer Security |
| UUID | Universally unique identifier |

## Software terminology

Technical nouns also include frontend, backend, database, endpoint, token, cursor, callback, and migration.
These nouns identify software components or data structures.
The guides use compile, configure, decode, deploy, encode, encrypt, execute, parse, serialize, and validate as software process terms.

Enter and save refer to data input and persistent data storage.
Reset refers to software state restoration.
These uses follow the computer-process category in Rule 1.12.
These terms do not authorize different general-language meanings.
