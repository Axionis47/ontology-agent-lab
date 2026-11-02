# OaK requirements graph

Version 0.4.1. Source format: StrictDoc SDoc. Tool version: 0.30.4.

These files hold identified requirements, owners, named contracts, acceptance tests, and architecture decisions.
Read the [documentation standard](../implementation/DOCUMENTATION-STANDARD.md) for authority, relation meanings, and scope limits.
Read the [implementation baseline](../implementation/README.md) for the product design.
The [task-boundary amendment](../implementation/TASK-CONTRACT.md) is version 0.4.2.
Its multiple-task requirements are not yet fully propagated into this 0.4.1 graph.

## Files

| Source | Content |
| --- | --- |
| [oak.sgra](oak.sgra) | Native StrictDoc grammar configuration and required fields |
| [00-system.sdoc](00-system.sdoc) | System boundary and cross-component requirements |
| [01-contracts.sdoc](01-contracts.sdoc) | Shared and component contract pointers |
| [02-decisions.sdoc](02-decisions.sdoc) | Architecture decision nodes |
| [03-agent-boundary.sdoc](03-agent-boundary.sdoc) | Ten explicit invariants for every supported OaK loop integration |
| `C00.sdoc` through `C11.sdoc` | Component requirements and specific acceptance links |
| [90-harness.sdoc](90-harness.sdoc) | Actual local substitute tests and their receipt |
| [91-document-checks.sdoc](91-document-checks.sdoc) | Document validation evidence and its scope |
| [92-agent-shape-checks.sdoc](92-agent-shape-checks.sdoc) | Actual declaration checks, separate from unrun runtime conformance |
| [Publication validation](validation-publication-2026-11-02.json) | Newly checked source hashes, export, counts, parity, and explicit limits |
| [Version 0.4.1 Markdown checks](../reviews/0.4.1-document-checks.json) | Preserved checks for 22 Markdown files; separate from requirements export |
| [validation-0.4.0.json](validation-0.4.0.json) | Preserved historical validation receipt |

Production tests remain unrun unless an identified real-service receipt establishes their result.
The local harness and document checks use separate evidence scopes.

## Install and export

Run from the repository root. Use the root environment and locked dependencies.

```sh
uv sync --locked --cache-dir .cache/uv
.venv/bin/python scripts/check_oak_requirements.py --output-dir .runtime/docs/strictdoc-publication-2026-11-02
```

The [small command wrapper](../../../scripts/check_oak_requirements.py) calls StrictDoc's native HTML and JSON export.
StrictDoc parses the source, validates required fields, and rejects duplicate or missing UIDs.
Version 0.30.4 accepts cycles through named parent roles in the tested fixture.
The wrapper uses Python's standard-library `graphlib.TopologicalSorter` to reject these cycles in the native JSON export.
It contains no SDoc parser or custom graph algorithm.
Generated files stay in ignored local runtime storage.

- HTML project index: `.runtime/docs/strictdoc-publication-2026-11-02/html/index.html`
- Native JSON export: `.runtime/docs/strictdoc-publication-2026-11-02/json/index.json`

The generated files are available after export. A new checkout must run the command first.
No server, model, identity provider, or benchmark starts during export.

## Current evidence

The graph has 157 requirements: 139 component requirements, eight system requirements, and ten agent-boundary invariants.
It has 233 component acceptance tests, eight system acceptance tests, and 54 recorded local checks.
Each requirement has an explicit test link. This establishes traceability, not test sufficiency.

All 239 production test obligations remain unrun. One document check passed and one document review remains unrun.
The local checks comprise 24 SQLite substitute tests and 30 starting-declaration checks. Neither scope establishes host readiness.
The publication receipt records component statement parity, all 12 component owners, 19 contract pointers, and nine architecture decisions.
These counts describe the 0.4.1 graph. They exclude the later task-boundary declaration suite and its proposed production checks.

The historical 0.4.0 receipt records injected duplicate UIDs, missing targets, invalid status, missing owners, and typed parent cycles.
The publication audit reruns export, graph checks, and parity. It does not repeat those historical fault-injection checks.
Contract pointers link to detailed payload fields. These checks do not prove executable field constraints or service compatibility.

The previously referenced `validation-0.4.1.json` was absent during publication review.
The new publication receipt records checks performed now. It does not reconstruct that missing historical receipt.

## Read one graph path

`C2-T02` points to `C2-R05` and `C2-R07` through `Verifies` links.
Those requirements point to the C2 owner and its graph-ingestion contract.
The contract points to the detailed Neo4j transaction and replay design.
All three remain proposed production behavior until their real-service tests run.

A local harness receipt can exercise related invariants. It cannot convert these proposed Neo4j tests into passing results.

## Review discipline

Keep requirement UIDs stable. Add explicit test mappings for each changed requirement.
Do not link every component test to every requirement merely to remove a coverage gap.
Do not use a passing document export as a software release gate.

The SDoc sources and the linked detailed Markdown specification must agree.
The initial migration preserves the current numbered requirement statements.
Future edits must update both sources during the same review.

StrictDoc is pinned in the development dependency group.
Its transitive export dependencies do not become selected OaK runtime technologies.
In particular, its RDFLib dependency does not change the Neo4j backend decision.
