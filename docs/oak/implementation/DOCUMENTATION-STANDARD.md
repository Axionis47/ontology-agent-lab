# Documentation standard and requirements graph

Design version 0.4.0. November 2, 2026.

Use a requirements graph that an agent can inspect through stable identifiers and typed links.
Keep technical explanations beside the graph. Keep exact wire contracts in their declared contract source.

There is no single standard that covers product requirements, architecture, APIs, runtime evidence, and agent navigation.
The selected combination uses existing specifications, methods, and software for their respective tasks.

## Selected standards and tools

| Need | Selection | Classification and purpose |
| --- | --- | --- |
| Linked requirements and traceability | StrictDoc 0.30.4 | Existing open-source tool, not an industry standard |
| Requirements exchange | OMG ReqIF 1.2 | Standard interchange format when another engineering tool requires it |
| Architecture coverage | arc42 | Architecture documentation template, not a wire contract |
| Architecture views | C4 model | System, container, component, and supporting diagrams |
| HTTP service contracts | OpenAPI 3.1-compatible export from FastAPI | Machine-readable API description, with generated frontend types |
| Artifact and function payloads | Pydantic-generated JSON Schema | Validation schemas derived from production models |
| Requirement wording | ASD-STE100 principles | Short instructions, named owners, consistent technical terms |
| Design choices | Architecture decision records | Context, selected choice, alternatives, and consequences |

[StrictDoc](https://strictdoc.readthedocs.io/en/stable/stable/docs/strictdoc_01_user_guide.html) supplies source parsing, relation validation, trace views, and JSON export.
Its SDoc format is selected because its Markdown support is experimental.
Do not invent a requirements language or documentation graph engine.

[ReqIF](https://www.omg.org/spec/ReqIF/) supplies standardized requirements exchange.
It is an optional export boundary here. No external requirements system is connected.
[OSLC Requirements Management](https://oslc-op.github.io/oslc-specs/specs/rm/requirements-management-spec.html) addresses linked lifecycle service interfaces.
Deploying an OSLC server is outside this local repository slice.

[arc42](https://arc42.org/overview/) structures architecture coverage.
The [C4 model](https://c4model.com/) supplies view levels.
The C4 diagramming method is separate from our component named C4, which owns execution protocol.

[OpenAPI](https://spec.openapis.org/oas/v3.1.2.html) defines HTTP interface descriptions.
Use a version supported by the selected FastAPI and TypeScript tooling instead of selecting the newest specification by name.
The production OpenAPI file remains unimplemented. Written payload tables are not executable schema validation.

## Source ownership

| Source | Authority |
| --- | --- |
| [StrictDoc source folder](../requirements/README.md) | Stable requirement and test UIDs, typed trace relations, owners, and recorded status |
| [Component specifications](README.md#component-map) | Internal logic, algorithms, storage, failures, exact proposed payload fields, and technical explanation |
| [Shared contracts](CONTRACTS.md) | Common proposed envelope, artifacts, package identity, errors, and verification receipts |
| Production Pydantic models, when implemented | Executable service and artifact validation; generated schemas must match the approved design |
| [Architecture decisions](DECISIONS.md) | Selected choices, rejected alternatives, consequences, and scope limits |
| [Harness receipt](INTEGRATION-HARNESS.md) | Actual local substitute test results and their limits |

During this migration, each explicitly numbered component requirement is copied into a StrictDoc node with the same UID.
The detailed Markdown document remains its linked technical explanation.
If their statements disagree, stop the affected change and reconcile both sources in the same review.
Do not silently select the more convenient version.

New requirements start in StrictDoc. Retain the UID when moving a requirement between documents.
Retire a requirement explicitly. Do not reuse its UID for another meaning.
Do not edit generated HTML or JSON. Regenerate those files with StrictDoc.

## Native graph model

The project configures six node types through StrictDoc's supported grammar extension.
Each node requires a UID, status, owner, source, scope, verification state, title, and statement.
This is configuration of an existing parser. It is not a new parsing framework.

| Node type | Content |
| --- | --- |
| `COMPONENT` | One owner and its responsibility boundary |
| `REQUIREMENT` | One required behavior or constraint |
| `CONTRACT` | A named handoff with a reference to its exact payload source |
| `TEST` | Input or fault, expected observation, scope, and linked requirement or contract |
| `DECISION` | Selected architecture choice and its rationale |
| `EVIDENCE` | An actual receipt with a limited claim and source reference |

| Relation role | Direction and meaning |
| --- | --- |
| `OwnedBy` | Requirement, contract, or test points to its responsible component |
| `ConstrainedBy` | Requirement, test, or contract points to its governing contract |
| `Consumes` | Consumer requirement points to an input contract |
| `Verifies` | Test definition points to the requirement it is intended to test |
| `Exercises` | Narrower test points to a related production requirement without claiming full verification |
| `Supports` | Evidence points to the executed test or limited claim it supports |
| `DecidedBy` | Requirement points to its architecture decision |

StrictDoc validates linked UIDs and required fields.
The isolated negative test showed that version 0.30.4 accepts cycles through named parent roles.
The export command therefore uses Python's standard-library `graphlib.TopologicalSorter` on StrictDoc's native JSON to reject those cycles.
It adds no SDoc parser or custom graph algorithm.
The trace graph describes ownership, constraints, and verification dependencies.
Runtime repair loops remain in component procedures and dynamic diagrams.
Do not force an execution loop into an acyclic requirements hierarchy.

The documentation graph, LangGraph workflow, Neo4j domain graph, and HUI graph views are distinct representations.
Their nodes can refer to one another through versioned contracts. They are not interchangeable graphs.

## Agent navigation contract

The native JSON export is `.runtime/docs/strictdoc/json/index.json`.
It contains `DOCUMENTS`, each with `NODES`.
Each node exposes `_NODE_TYPE`, `UID`, typed status fields, and `RELATIONS` where applicable.
Each relation exposes `TYPE`, `VALUE`, and `ROLE`.

An agent starts with a requirement UID. It resolves `OwnedBy` and `ConstrainedBy`, then follows the contract's source.
It finds planned tests by locating incoming `Verifies` links.
It finds limited local checks through incoming `Exercises` links.
It checks evidence scope before making any implementation or release claim.

Contract-node statements summarize handoffs. They do not replace the linked payload tables or future generated schemas.
An agent must read that exact contract source before changing a producer or consumer.

Use the graph to answer questions such as:

- Which component owns `C2-R05`, and which test covers its atomic graph commit?
- Which consumers depend on the schema and graph snapshot contracts?
- Which requirements have planned tests but no executed service evidence?
- Which decisions explain the fixed template limit or the selected storage split?

## Verification status

`Production` marks proposed product behavior and real-service test obligations.
`EngineeringHarness` marks the narrower local substitute implementation.
`Documentation` marks decisions and document-tool evidence.

A `Verifies` edge does not mean that a test ran.
A test for an unnumbered contract detail uses `ConstrainedBy` instead of claiming to verify an unrelated requirement.
A `Supports` edge does not expand an evidence receipt beyond its declared scope.
Passing a SQLite test does not mark a Neo4j transaction requirement verified.
Passing StrictDoc validation does not prove task correctness, API compatibility, or complete test coverage.

The initial graph includes the explicitly numbered component requirements and their acceptance definitions.
Unnumbered detailed design statements remain linked technical content.
Convert a changed normative statement into an identified requirement before claiming complete traceability for that change.

## Architecture coverage map

| arc42 topic | Repository location |
| --- | --- |
| Introduction and goals | [PRD](../../OAK-PRD.md), [research narrative](../../../RESEARCH-NARRATIVE.md) |
| Constraints | [Project instructions](../../../AGENTS.md), [shared contracts](CONTRACTS.md) |
| Context and scope | [Baseline](README.md), [C0](C00-task-admission.md), [C8](C08-agent-loop.md) |
| Solution strategy | [Decisions](DECISIONS.md) |
| Building blocks | [C0 through C11](README.md#component-map) |
| Runtime behavior | [C4](C04-execution.md), [C5](C05-evaluation.md), [C6](C06-workspace.md), [C10](C10-service.md) |
| Deployment | [C9](C09-identity.md), [C10](C10-service.md), [setup guide](../../OAK-SETUP.md) |
| Cross-cutting concepts | [Contracts](CONTRACTS.md), [writing guide](../WRITING-GUIDE.md) |
| Architecture decisions | [Decision record](DECISIONS.md) |
| Quality requirements | Typed requirement and test nodes in [StrictDoc](../requirements/README.md) |
| Risks and technical debt | [Integration challenge record](integration-review.md), [harness limits](INTEGRATION-HARNESS.md) |
| Glossary | [Writing guide](../WRITING-GUIDE.md#project-terms), [shared scalar types](CONTRACTS.md#scalar-types) |

## Change procedure

1. Identify the requirement UID and its owner.
2. Read the linked contract and affected consumers.
3. Update the requirement and detailed design together.
4. Add specific test links for the changed behavior.
5. Record any changed architecture decision.
6. Run the native export and standard-library cycle audit, then inspect the trace view.
7. Run the affected software tests separately.
8. Attach actual receipts with their execution scope.

Use [the requirements README](../requirements/README.md) for exact commands and current validation evidence.
Full ASD-STE100 conformity remains unverified. Document graph validity is a separate property from controlled-language conformity.
