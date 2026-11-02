# Architecture decisions

Design version 0.4.1. November 2, 2026.

These records explain selected choices, rejected alternatives, and consequences.
Acceptance of a design does not establish implementation or verification.

## ADR-001: Select one bounded agent loop

Status: accepted for the first engineering slice.

The agent must choose an offer using incomplete tool observations. Its loop obtains evidence and makes the final choice.
Use `offer-selection-v1` with the two existing read-only fixture tools.
The project records a loop configuration under a project. It does not clone or replace a complete agent application.

Reject arbitrary host adapters for this slice. Tool descriptions do not establish executable callbacks, observations, or dispatch control.
Defer full TravelPlanner until the loop, evidence handling, and repair protocol pass their service tests.
The existing fixture provides no scientific held-out population.

## ADR-002: Reuse infrastructure

Status: accepted and required by the user.

Use the libraries in [shared contracts](CONTRACTS.md#build-versus-reuse).
Custom code must implement source interpretation, domain rules, artifact dependencies, independent scoring, or narrow service binding.
Do not implement general infrastructure where a selected library already supplies it.

Procrastinate supplies job delivery. LangGraph supplies component workflow state.
Neither replaces domain idempotency or authoritative operation receipts.
Use the queue's retry policy for delivery. Use bounded component logic for semantic redrafting. Account for both separately.

## ADR-003: Separate application records, domain facts, and artifact bytes

Status: accepted.

Use PostgreSQL for ownership, configurations, runs, candidates, and activation records.
Use Neo4j for observed assertions and their relationships. Use immutable files for large versioned payloads.

Reject using Neo4j as the user/session/job database. Reject a custom graph store.
Reject cross-store atomicity claims. Each store supplies a local receipt and an idempotent recovery route.
The consequence is explicit reconciliation at store boundaries. C10 owns the recovery procedure.

## ADR-004: Use a restricted schema mapping and independent verification layers

Status: accepted.

C1 accepts typed declarations and maps them through Owlready2. HermiT checks the supported OWL encoding.
C1 rejects unsupported constructs. It must not silently approximate them or fabricate reasoner explanations.

Reject model-generated Python or arbitrary OWL as the first executable artifact format.
Reject treating a logical pass as business-rule coverage or task correctness.
C2, C3, and C5 supply separate projection, function, and outcome tests.
The supported profile is intentionally limited. Broader schema support requires a new profile and tests.

## ADR-005: Start composition with audited function templates

Status: accepted for engineering validation; limited algorithm scope.

C3 selects an approved template and binds schema terms through Pydantic-validated configuration.
Python callables implement the known domain operations. The first template evaluates offer eligibility.

Reject a new general programming language, arbitrary generated code, or a bespoke interpreter.
This choice limits what automatic refinement can express. A missing computation returns an explicit unsupported result.
Adding a new audited operator requires implementation and independent tests before use.
This is a bounded OaK-inspired adaptation, not a full implementation of open-ended function composition.

## ADR-006: Seal finalization before a guarded decision

Status: accepted; real-service verification required.

C4 stops new dispatch, reconciles already dispatched work, and resolves its committed observations before finalization.
It selects one stable graph revision and applies the package's declared guards.
The terminal result records that revision and those receipts.

Reject a guard evaluated while earlier calls can still commit contradictory evidence.
In optional mode, C5 can reject a bad final answer even when the host ignored F.
Enforcement remains a separate experimental condition.

## ADR-007: Use a requirements tool for the documentation graph

Status: accepted.

Use StrictDoc for stable requirement IDs, relation validation, trace views, and JSON export.
Use detailed Markdown specifications for technical explanations. Use generated contracts for exact service serialization.
Use arc42 as the architecture coverage checklist and C4 for system views.

Reject inventing a documentation language, RDF database, parser, or graph algorithm for this task.
StrictDoc 0.30.4 does not reject the tested typed-parent cycle. Use Python's standard `graphlib` to audit the exported dependencies.
This thin audit reads native JSON. It does not parse SDoc or implement graph traversal algorithms.
ReqIF is an exchange option when another requirements tool needs it.
The documentation graph is separate from the product's domain knowledge graph and its LangGraph workflow.

## ADR-008: Keep verification claims bound to actual evidence

Status: accepted.

The local harness establishes only its explicit substitute tests.
The production release requires real identity, storage, reasoner, queue, host, and browser tests.
A link to a test definition proves traceability. It does not prove that the test ran or passed.

Reject a single green status that combines proposed design and runtime behavior.
Record implemented, passed, failed, unrun, and unsupported states separately.
No agent-performance claim exists until the registered paired experiment runs.

## ADR-009: Admit one explicit managed loop boundary

Status: accepted.

Separate `sequential_readonly/1`, the loop profile, from `offer-selection-v1`, the task profile, and the versioned C8 host implementation.
The first user action selects a fixed server preset. Its complete `oak-agent-shape/1` declaration has strict Pydantic validation and generated JSON Schema.
It rejects arbitrary code, external attachment, hidden memory, extra tools, and premature kernel references.

Use existing version, binding, admission, verification, activation, and mount receipts to show progress.
Do not create an independent ready flag, generic adapter engine, or custom onboarding framework.
Pre-kernel probes establish native bindings and hook registration only. Full package probes establish actual dispatch, observation, recovery, and terminal boundaries.
The current declaration tests cannot stand in for those unrun production probes.

Candidate verification registers fresh session-scoped assignments and uses the normal authoritative run ledger.
It scores complete per-package batches through C5 and publishes a sealed verification-set reference for review.
This closes the identity and approval handoffs without a second execution engine.
