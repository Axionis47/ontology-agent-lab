# C1: Schema builder and logical verifier

Design version 0.3.0. November 2, 2026. This component is proposed. It is not implemented.

Installation probes establish infrastructure readiness only. The [PRD](../OAK-PRD.md) defines product requirements. The [integration specification](INTEGRATION.md) defines component handoffs. Use the [writing guide](WRITING-GUIDE.md) for document terms and review limits.

## Purpose and ownership

C1 converts development requirements into a readable domain schema, S. It then verifies the formal meaning expressed by the OWL encoding.

For example, C1 can define maximum occupancy. C2 obtains an offer's observed occupancy. A function compares that value with party size. C5 checks the completed task.

The paper defines the kernel as `K = (S, F)`. C1 produces S. C3 produces F. The paper has two stages and four construction steps. Our implementation separates construction into five components. [OaK sections 3.1 and 3.2, Step 1](https://arxiv.org/html/2608.22974v1).

C1 owns its prompts, schema contract, OWL encoder, reasoner adapter, diagnostics, and local repair procedure. Model weights stay fixed.

The coordinator owns round selection and total budgets. C2 owns graph writes. C3 owns functions. C5 owns task evaluation. C1 cannot change those components to make its checks pass.

## Source requirements and design choices

| Topic | Paper requirement | Open detail | Proposed implementation |
| --- | --- | --- | --- |
| Requirements | `R = Analyze(T, D_t)` identifies scope, entities, relations, and constraints. [Step 1](https://arxiv.org/html/2608.22974v1) | Record format and source attribution | Strict requirement records with source references and unresolved meanings |
| Draft | `S_t = Draft(R, previous schema feedback)` defines properties, primary keys, and typed relation endpoints. [Step 1](https://arxiv.org/html/2608.22974v1) | Schema language and prompts | A versioned Pydantic contract, readable JSON, and a declared logical subset |
| Verification | Encode the schema as OWL. Use reasoner diagnostics to retry failed drafts. [Step 1 and Appendix A](https://arxiv.org/html/2608.22974v1) | Translation, explanations, timeouts, and retries | Encoding coverage, isolated reasoner runs, saved diagnostics, and bounded attempts |
| Runtime access | The frozen kernel mediates data access. [Section 3.1](https://arxiv.org/html/2608.22974v1) | This is an explicit policy | Our live pilot retains native tools. C1 verifies S; it does not verify all host behavior. |
| Freeze | S and F remain fixed during inference. [Section 3.3](https://arxiv.org/html/2608.22974v1) | Packaging and dependency identifiers | Disable C1 during held-out inference. Pin the schema, encoder, and reasoner dependencies. |

## Inputs

The coordinator submits a `SchemaBuildRequest` with the shared envelope and declared mode. Its payload contains:

- Task scope, completion constraints, domain references, and relevant tool or skill descriptions.
- Selected development examples and their evidence references.
- The previous schema identity and applicable C5 feedback, with exact target versions.
- Attempt, token, elapsed-time, and reasoner budgets.
- The actual model settings.

Exclude expected answers and private grader data.

The coordinator selects the development sample. C1 must not resample it. The paper draws a fresh random sample each round. A query's corpus supplies evidence for that query. It is not an inventory of all possible entities. [OaK section 3.2, opening paragraphs](https://arxiv.org/html/2608.22974v1).

## Outputs

A successful response contains a `SchemaArtifact` with:

- Readable S and source-linked requirements.
- Stable type, property, and relation identifiers.
- Identity declarations, units, and context metadata.
- The OWL artifact and encoding coverage report.
- The verification report and unresolved requirements.
- Immutable artifact identifiers and content hashes.

Identity metadata tells C2 how to interpret keys. It does not merge records.

An unsuccessful response preserves candidate and diagnostic references. It contains no deployable schema. The `component_status` is `ready`, `invalid_input`, `unsupported_input`, `budget_exhausted`, or `execution_failure`.

Use the shared envelope for terminal status and invocation identifiers. A ready result uses `status: succeeded`. The listed unsuccessful results use `status: failed`. Component readiness and task success are separate.

The verification report has separate fields for global consistency, unsatisfiable classes, coverage, profile compatibility, timeout, and reasoner error. Mark uncomputed checks as uncomputed. For example, global inconsistency must not produce an empty class list labeled as a successful class analysis.

## Internal procedure

This proposed procedure expands the paper's analysis, draft, verify, and retry sequence. [OaK section 3.2, Step 1](https://arxiv.org/html/2608.22974v1).

```text
validate request, dependency versions, development scope, and remaining budget
reject stale schema feedback or held-out construction requests
R = Analyze(task, references, selected development examples)
persist R with evidence references and unresolved meanings
for attempt within the admitted budget:
    S = Draft(R, prior schema feedback, local diagnostics)
    validate schema structure, references, identities, and declared semantics
    classify every declaration: logical, runtime concern, or unsupported
    OWL, coverage = Encode(S, encoder_version)
    check supported coverage and OWL 2 DL profile compatibility
    run HermiT in an isolated context with a deadline
    collect consistency and, when available, class-satisfiability results
    persist candidate, diagnostics, versions, and resource usage
    if all required checks pass:
        publish immutable SchemaArtifact and return ready
    if repair is appropriate and budget remains:
        retain diagnostics for the next draft
    else:
        return the explicit unsuccessful outcome
```

A repair must preserve each required distinction. It must not remove a requirement only to obtain consistency.

Some requirements need runtime checks. Record their intended consumer and unresolved implementation status. Publishing S does not establish that C3 implemented those checks.

## OWL coverage and logical checks

Map each logical declaration to its emitted axioms. Map each runtime requirement to its intended consumer. Unsupported logical declarations block publication.

A comparison between a quote and a customer's budget is a runtime check. Do not present it as a HermiT guarantee.

The paper identifies five check categories. The concrete receipts and fixtures below are our implementation requirements. [OaK Appendix A](https://arxiv.org/html/2608.22974v1).

| Category | Required behavior and test |
| --- | --- |
| Disjointness consistency | Encode declared disjoint classes. A subclass of two disjoint classes must be unsatisfiable. Class names alone do not declare disjointness. |
| Restriction consistency | Encode supported existential, universal, and cardinality restrictions. A Trip requiring at least one and at most zero `hasDay` values must be unsatisfiable. |
| Property-level consistency | Cover functional, inverse-functional, transitive, symmetric, asymmetric, reflexive, irreflexive, and inverse-property declarations. Reject unsupported OWL 2 DL combinations before reasoning. |
| Global consistency | Report whether the encoded ontology admits a model. An inconsistent ontology must fail, even if its readable schema passes structural validation. |
| Unsatisfiable classes | Report user-defined classes that cannot have instances. Exclude the built-in bottom class. Reject these classes even when the ontology is globally consistent. |

These categories do not require five separate reasoner passes. Distinguish tested categories from categories with no applicable axioms.

The adapter uses Owlready2's bundled HermiT and Java. Record the package version, reasoner distribution or binary hash, Java version, and invocation settings.

Owlready2 supports inconsistency exceptions and class-satisfiability inspection. A complete service for explanatory counterexamples is not assumed. Do not describe its bundled modified reasoner as the paper's exact binary. [Owlready2 reasoning documentation](https://owlready2.readthedocs.io/en/latest/reasoning.html).

OWL uses open-world semantics. Missing observations do not establish falsity. Domain and range axioms can infer types instead of rejecting input records.

Declared primary keys give C2 identity instructions. OWL does not automatically enforce them as database uniqueness constraints. Numeric checks, required fields, and source faithfulness need separate checks. [W3C OWL 2 Primer, sections 3 to 6](https://www.w3.org/TR/owl2-primer/).

## Repairs and failures

Malformed model output or a logical contradiction can cause another local draft. Unsupported encoding, exhausted budgets, and persistent reasoner failures return terminal failures.

Infrastructure retries have separate limits from drafting attempts. Both consume the same run budget. A timeout never counts as a consistency pass.

The coordinator passes the exact successful schema hash to C2 and C3. A schema repair creates a new artifact. It invalidates affected graph projections and functions. C1 reports dependencies; the coordinator schedules rebuilding.

C5 sends schema feedback to C1 and function feedback to C3. [OaK section 3.2, Step 4](https://arxiv.org/html/2608.22974v1).

## Independent verification

These are required tests, not completed test results. Use the shared [verification protocol](INDEPENDENT-VERIFICATION.md).

Run C1 from a saved `SchemaBuildRequest`. Do not run C2 through C5. Supply a recorded model-response stub for deterministic orchestration tests. Use the real encoder and HermiT for logical tests.

A reasoner stub can test timeout handling. It cannot establish logical correctness. Fresh model calls can produce different drafts despite identical settings.

| Test input or injected fault | Expected output | Measurable pass condition |
| --- | --- | --- |
| Valid schema fixture | Matching schema, OWL, coverage, and dependency references | Every required declaration has a recorded disposition. All required checks pass. |
| Contradiction fixture for each applicable category | Rejection with the relevant diagnostic | No deployable artifact; the expected contradiction is identified |
| Globally consistent schema with an unsatisfiable user class | Rejection | The class appears in the unsatisfiable-class result |
| Encoder omits one required declaration | Coverage failure | Publication count is zero |
| Unsupported axiom, timeout, or Java failure | Separate failure reports | No failure is labeled as a consistency pass |
| Local repair followed by retry exhaustion | Saved candidates and costs | Source requirements remain present; no deployable artifact is published |
| Stale feedback or held-out request | Input rejection | Model-call and reasoner-call counts are both zero |
| Schema omits an occupancy requirement | Logical success can remain possible | Independent task evaluation can still reject the outcome |

C1 may write candidate artifacts, diagnostics, and receipts. It must not write G or change F. Compare their hashes before and after each isolation test.

These tests establish component behavior. They do not establish complete domain coverage or improved agent performance.

Source attribution: Xiaohui Zhang et al., *Toward Effective and Reliable LLM Agents via Dynamic Ontology*, [arXiv:2608.22974v1](https://arxiv.org/abs/2608.22974v1), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
