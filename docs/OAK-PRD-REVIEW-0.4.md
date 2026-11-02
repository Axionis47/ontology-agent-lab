# OaK implementation design review, version 0.4.0

Date: November 2, 2026.

## Requested outcome

The user requested exact component logic, storage, contracts, auth, projects, agent configurations, and a human graph workspace.
The request also requires schema-change verification, adversarial integration review, a runnable harness, and one reviewer per component.
Later instructions require existing tools before custom infrastructure and graph-structured documentation for agent use.

The [implementation baseline](oak/implementation/README.md) is the entry point.
The [shared contracts](oak/implementation/CONTRACTS.md) and [architecture decisions](oak/implementation/DECISIONS.md) govern cross-component choices.
The [documentation standard](oak/implementation/DOCUMENTATION-STANDARD.md) defines the requirement graph.

## Review ownership

| Reviewer | Boundary |
| --- | --- |
| C0 | First task class, manifests, source access, admission |
| C1 | Schema declarations, OWL encoding, HermiT, local repair |
| C2 | Evidence mapping, provenance, graph storage and revisions |
| C3 | Audited function templates, typed bindings, domain computation |
| C4 | Host dispatch protocol, observations, barriers, finalization |
| C5 | Independent task evaluation and repair proposals |
| C6 | Candidates, verification, review, activation, rollback |
| C7 | Version-bound inspection projections |
| C8 | Bounded agent loop and actual callable bindings |
| C9 | Identity, projects, memberships, agent configurations |
| C10 | API, metadata, durable jobs, storage recovery |
| C11 | Human interface, graph inspection, user journeys |
| Integration | Cross-component challenges and the executable local harness |
| Documentation | StrictDoc graph, native validation, and exports |

Reviewers run in waves because the session limits concurrent agents.
The integration record contains the disputed choices and required release evidence.
Review participation is not a substitute for executed service tests.

## Resolved design choices

The first engineering class is read-only offer selection with two fixed fixture tools.
The host loop remains distinct from ontology construction and the domain graph.
An agent configuration lives inside a project and pins its execution settings.

Use established infrastructure: Keycloak, Authlib, session middleware, FastAPI, Pydantic, SQLAlchemy, Alembic, Procrastinate, and LangGraph.
Use the existing Neo4j driver, Owlready2, and HermiT for their respective boundaries.
Use React Flow, generated OpenAPI types, and TanStack Query for the frontend.
Use StrictDoc for requirements and traceability.

C3 begins with audited function templates. This intentionally limits composition and avoids arbitrary generated executable code.
Unsupported computations require a separately implemented and tested operator.
This is a bounded adaptation, not a completed unrestricted OaK composer.

## Schema-change closure

A schema change targets an immutable base. C1 validates declarations and performs the logical checks.
C2 rebuilds compatible projections from preserved source observations. C3 rebuilds and tests dependent functions.
C4 and C8 execute development regression cases. C5 evaluates the outcomes independently.
C6 binds trusted receipts and human review to the exact candidate before atomic activation.

A logical pass cannot replace task correctness. A model-generated explanation cannot replace reasoner diagnostics.
An old run retains its original package. Held-out defects do not repair that package.

## Executed evidence

The [harness report](oak/implementation/INTEGRATION-HARNESS.md) identifies the actual tests and local receipts.
Its recorded run passes 24 of 24 assigned local fault checks. The root environment supplies Python and Pydantic.
The fixture demonstration changes observed facts while schema and function implementations remain fixed.
This is evidence enrichment and software-contract verification, not schema repair or measured agent improvement.

The documentation tool parses native requirement sources and exports graph records for agent use.
Its [documentation report](oak/implementation/DOCUMENTATION-STANDARD.md) records the exact command and validation limits.
The [graph receipt](oak/requirements/validation-0.4.0.json) records 421 nodes, including 138 requirements and 243 test definitions.
Each numbered requirement has a specific planned test link. All 217 production test obligations remain unrun.
StrictDoc rejected duplicate IDs, missing targets, invalid status, and missing owners.
Its typed-parent cycle check required Python's standard `graphlib`; the combined workflow rejected the injected cycle.
Neither a graph edge nor a document validation result proves runtime behavior.

## Writing and preservation

Requirements use named owners, stable IDs, short actions, and consistent technical terms.
Full ASD-STE100 dictionary and grammar conformity remains unverified.
The [document-check receipt](oak/reviews/0.4.0-document-checks.json) covers links, headings, tables, placeholders, and selected writing rules.
All 20 active Markdown documents passed those checks, including the 25-word prose and 20-word numbered-instruction screens.
The official standard website returned HTTP 403 during this review. Existing source citations remain preserved.

Historical design receipts, source PDFs, synthetic inputs, previous experiments, and their outcomes remain unchanged by this work.
The [research narrative](oak/STATUS.md) records the new design, local harness evidence, and its limits.
No model experiment, task-provider action, benchmark, or publication is launched.

## Remaining implementation gates

The product API, auth integration, PostgreSQL and Neo4j service wiring, full schema repair, and browser interface remain unimplemented.
Their component specifications define required tests and failure responses.
The first live experiment still requires a registered population, capable fixed model, enabled thinking, evaluator, and resource budget.

These are explicit delivery gates, not silently assumed working integrations.
The review establishes a design baseline and a tested local subset. It does not certify a defect-free production system.
