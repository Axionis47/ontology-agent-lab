# C3: Typed function composition and execution

Design version 0.4.0. November 2, 2026. Owner: C3.

Status: proposed production design. The local harness implements a smaller deterministic function boundary.
The [baseline](README.md) controls deployment. [Shared contracts](CONTRACTS.md) control envelopes, references, scope, hashes, and errors.
This document refines the [earlier C3 design](../03-function-composer.md). Full ASD-STE100 conformity remains unverified.

## Purpose and decision

An agent repeatedly compares observed offers with occupancy, stay, availability, and budget requirements.
C3 binds an approved computation template to the schema. The resulting function reads one committed graph revision.
C3 owns function recipes, binding validation, and local behavior tests. C4 owns dispatch. C5 independently scores the completed task.

The paper composes typed functions from generic operators and tests their execution on G. See [OaK section 3.2, Step 3](https://arxiv.org/html/2608.22974v1#S3.SS2).
Our template selection, evidence states, limits, and independent expected results are implementation choices.
The first slice uses an audited Python template. It does not implement the paper's complete operator library or open-ended composer.

**C3-R01:** C3 must accept typed template bindings only. Model-generated Python, Cypher, imports, and provider calls are forbidden.

**C3-R02:** C3 must preserve every violated and unresolved requirement in its result.

**C3-R03:** C3 must bind each function invocation to one authorized graph revision.

**C3-R04:** C3 must reject changes to a frozen recipe or its dependencies.

## Public contracts

All objects reject unknown fields. Integers reject booleans and numeric strings. References resolve under the server-bound project.
`Id`, `Hash`, `ArtifactRef`, and `Error` use the shared contracts. `TermId` uses C1's schema profile.

| Contract | Required fields and types |
| --- | --- |
| `ComposeRequest` | Shared envelope; `candidate_id: Id`, `schema_ref: ArtifactRef`, `development_graph_refs: GraphSnapshotRef[]`, `development_cases_ref: ArtifactRef`, `operator_catalog_ref: ArtifactRef`, `expected_results_ref: ArtifactRef`, `prior_bundle_ref: ArtifactRef\|null`, `repair_ref: ArtifactRef\|null`, `composer_settings_ref: ArtifactRef`, `budget_ref: ArtifactRef` |
| `FunctionBundle` | `profile: literal(oak-function-recipe/1)`, `schema_hash: Hash`, `functions: FunctionSpec[1]`, `operator_catalog_hash: Hash`, `runtime_hash: Hash`, `test_report_ref: ArtifactRef`, `dependency_manifest_ref: ArtifactRef` |
| `FunctionSpec` | `function_id: literal(select_eligible_offers)`, `description: string[1..2048]`, `argument_contract: literal(offer-selection-input/1)`, `result_contract: literal(offer-selection-result/1)`, `recipe: EligibilityRecipe`, `requirement_ids: Id[]`, `schema_term_ids: TermId[]` |
| `InvokeFunctionRequest` | Shared envelope; `bundle_ref: ArtifactRef`, `function_id`, `graph: GraphSnapshotRef`, `required_observation_ids: unique Id[]`, `task_request_ref: ArtifactRef`, `candidate_ids: unique Id[0..100]` |
| `FunctionResult` | Shared outcome envelope; `bundle_hash: Hash`, `recipe_hash: Hash`, `graph: GraphSnapshotRef`, `request_hash: Hash`, `offers: OfferOutcome[]`, `eligible_ids: Id[]`, `coverage: Coverage`, `operation_receipts_ref: ArtifactRef`, `error: Error\|null` |
| `OfferOutcome` | `offer_id: Id`, `status: eligible\|violated\|unresolved`, `checks: RequirementResult[]`, `source_observation_ids: unique Id[]`, `assertion_ids: unique Id[]` |
| `RequirementResult` | `requirement_id: Id`, `outcome: satisfied\|violated\|unknown`, `reason: known_comparison\|missing\|conflict\|invalid\|stale\|scope_mismatch`, `assertion_ids: unique Id[]`, `expected: integer\|boolean\|string`, `observed: integer\|boolean\|string\|null` |
| `Coverage` | `requested_ids: Id[]`, `observed_ids: Id[]`, `missing_ids: Id[]`, `search_complete: boolean`, `evidence_limitations: string[]` |

`GraphSnapshotRef` includes project, agent, evidence context, projection, revision, schema hash, and interpretation hashes.
C2 defines its authoritative fields. C3 cannot replace it with the latest graph pointer.

The task request uses C0's exact fields and bounds: party size 1..100, stay 1..30 nights, and integer USD `budget_minor`.
The stored semantic price field is `total_minor_units`. Both names mean integer cents in this first profile.
C3 consumes the admitted values. It does not parse free text, convert currencies, or reinterpret source price units.
Composition result `component_status` is `ready`, `invalid_input`, `unsupported_requirement`, `budget_exhausted`, or `execution_failure`.
Invocation result `component_status` is `completed`, `blocked`, `budget_exhausted`, or `execution_failure`.
Only `ready` and `completed` are successful handoffs. An eligible-offer count of zero does not change process success.

`eligible_ids` contains all and only offers with status `eligible`, sorted by UTF-8 offer ID.
This ordering is deterministic. It is not a ranking or cheapest-offer claim.
An absent requested offer receives five unknown requirement results with reason `missing`. It cannot disappear from coverage.

## Reuse decision and the first recipe

Use Pydantic models with a tagged `template_id` field. Use ordinary Python calls for execution.
Do not build a custom programming language, expression parser, bytecode format, interpreter, or general compiler.
The first registry contains one template: `offer-eligibility/1`.

| Need | Reused implementation | Project-specific work |
| --- | --- | --- |
| Typed payload and JSON Schema | Pydantic strict models and discriminated unions | Declare the bounded recipe and result fields |
| Graph access | Official Neo4j driver and existing C2 repository boundary | Supply fixed parameterized queries and version scope |
| Comparison and date arithmetic | Python integer operators and `datetime.date` | Define occupancy, stay, availability, and price semantics |
| Function dispatch | An explicit Python dictionary of approved callables | Bind one template ID to one audited callable |
| Workflow scheduling and retries | LangGraph and the shared coordinator | Define component handoffs and budget policy |
| Behavior verification | pytest and independently authored fixtures | Supply expected domain outcomes and failure cases |

These reuse choices avoid a custom runtime platform. Domain rules and source mappings remain application logic.
Pydantic supports [tagged unions](https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions).
Its validator checks the recipe shape. It does not prove the domain computation correct.

`EligibilityRecipe` contains exactly:

| Field | Type and permitted value |
| --- | --- |
| `template_id` | Literal `offer-eligibility/1` |
| `template_hash` | Hash of the audited Python implementation and its declared helpers |
| `offer_type`, `quote_type` | C1 `TermId` class references |
| `offer_quote_relation` | C1 object-property reference with matching endpoint types |
| `occupancy_property`, `minimum_nights_property`, `total_property` | C1 integer-property references |
| `availability_property` | C1 boolean-property reference |
| `currency_property`, `request_context_property`, `price_basis_property` | C1 string-property references |
| `requirement_ids` | Exact named bindings for occupancy, minimum stay, availability, total price, and quote scope |
| `result_contract` | Literal `offer-selection-result/1` |

The recipe cannot change comparison directions, expected availability, currency, or missing-value behavior.
Those semantics belong to the reviewed template version. A required change creates a new implementation and test receipt.
The quote-scope result compares canonical expected and observed scope hashes. Any mismatched member makes that requirement fail.
Its detailed diagnostic identifies the differing scope members without combining several independently satisfied checks into one success.

The callable performs these ordinary Python operations in a fixed order:

| Operation | Input and result |
| --- | --- |
| `reader.get_offers` | Candidate IDs and pinned graph handle produce observed offers plus missing-ID diagnostics |
| `reader.get_quote_evidence` | Offers and request context produce request-specific quote rows and source assertions |
| `evaluate_requirements` | Typed request and evidence rows produce every satisfied, violated, and unresolved requirement |
| `format_selection` | Requirement rows produce all candidate outcomes, eligible IDs, coverage, and provenance |

These operation names are application interfaces, not a new plan language.
C2's reader uses fixed query templates. Recipe identifiers resolve through the schema and never become arbitrary query text.

An evidence cell contains `state`, `value`, `assertion_ids`, and `source_observation_ids`.
State is `known`, `unknown`, `conflict`, `invalid`, or `stale`. Only `known` contains a usable typed value.
C2 resolves evidence before evaluation. C3 cannot choose a conflicting value or replace missing data with zero.

The catalog pins the callable, dependency hashes, `effect: read_only`, and `uses_model: false`.
`operator_catalog_ref` names this approved callable registry. It does not introduce a second runtime or an extensible code loader.
One call permits 100 candidates, 100 related rows per candidate, and five seconds of elapsed time.
Exceeding a limit fails the call. It cannot return a successful truncated selection.
A changed limit set changes the runtime dependency hash.

Runtime slot extraction is excluded because C0 already provides typed requests. New model-backed operations need a separate versioned contract.
The composer can propose supported schema bindings and descriptions. It cannot generate the callable or modify its fixed logic.
This limits repair coverage deliberately. A missing approved computation returns `FUNCTION_UNSUPPORTED_REQUIREMENT`.

## Bind and verify

1. Resolve authorized inputs and verify all hashes.
2. Reject held-out data, stale feedback, or incompatible schema and graph versions.
3. Request one typed template binding under the admitted composer settings.
4. Validate the recipe with Pydantic and reject an unknown template ID.
5. Resolve every schema term and verify its declared type.
6. Verify the callable hash, read-only effect, and required requirement bindings.
7. Execute saved development fixtures against their pinned graph revisions.
8. Compare complete outputs with independently specified expected results.
9. Save the recipe, dependency manifest, operation receipts, and test results.
10. Publish a ready bundle only when all required tests pass.

Validation rejects an integer binding to a boolean property or a relation with incorrect endpoint types.
All five requirement bindings are mandatory. The composer cannot omit a difficult check.
Structural coverage does not establish semantic correctness. C5 still scores complete task behavior independently.

C3 permits three binding attempts in total. Each failed proposal consumes the same persistent reservation.
Infrastructure failure permits one identical retry. Unsupported computation requires an approved template change, not a weaker condition.
The composer cannot edit expected results, C1 schema, template code, or the operator registry.

## Exact offer-selection behavior

1. Verify the required observations committed under the selected projection.
2. Bind the graph handle to the supplied revision for the complete call.
3. Resolve candidate offers and their request-specific quote evidence.
4. Preserve every unknown, invalid, stale, or conflicting cell.
5. Compare occupancy with party size using `occupancy >= party_size`.
6. Compare minimum stay with calendar nights using `minimum_nights <= nights`.
7. Require observed availability to equal true.
8. Compare inclusive total cents with `budget_minor` using `total_minor_units <= budget_minor`.
9. Require the quote's request scope, currency, and price basis to match.
10. Return every requirement result and its source references.

A known false availability value is a violation. A missing availability value is unknown.
An invalid occupancy value is unresolved evidence. It is not proof that capacity is inadequate.
If any check is violated, offer status is `violated`. Otherwise, any unknown check makes status `unresolved`.
Only all satisfied checks produce `eligible`. Known violations and unknown checks can coexist in the same outcome.

A later observation creates a later graph revision and a new invocation result. It cannot change an earlier result.
No eligible offer means no supported choice in this observed scope. It does not prove that the market contains no suitable offer.
An incomplete source search keeps `search_complete: false` even if the function evaluates every supplied candidate.

In `optional_functions` mode, the host chooses whether to invoke this function.
In `guarded_requirements` mode, C4 invokes the version-bound finalization guard and verifies its evidence dependency.
C3 cannot enforce native-tool use or final-answer policy. C5 does not require an F call to recognize an independently correct answer.

## Storage, repair, and failure handling

C3 writes immutable recipes, catalogs, test results, dependency manifests, and call receipts through C10's artifact service.
PostgreSQL indexes their scope and lifecycle. C3 reads Neo4j through C2's version-bound reader and cannot write domain facts.
One receipt records the wrapper invocation. Nested receipts count each operator and database operation separately.
The recipe hash includes bindings, argument/result contracts, schema dependencies, and callable/runtime hashes.

C6 invalidates the candidate's C3 bundle after any schema-content change. C3 validates new bindings and retests against the new C2 projection.
Version 1 performs a full candidate rebuild. It makes no unproven claim that an apparently unaffected function is reusable.
Function-only repair also creates a new bundle and invalidates its downstream verification and review records.
Active runs retain their original package. Held-out defects create records, not mutable functions.

| Error code | Required behavior |
| --- | --- |
| `FUNCTION_DEPENDENCY_MISMATCH` | Reject schema, recipe, catalog, runtime, or projection mismatch before graph access |
| `FUNCTION_RECIPE_INVALID` | Preserve validation diagnostics; allow only the remaining bounded binding attempts |
| `FUNCTION_UNSUPPORTED_REQUIREMENT` | Return the missing primitive or schema requirement to C6; do not invent an operation |
| `OBSERVATION_BARRIER_UNSATISFIED` | Block the call until required successful ingestion receipts exist |
| `FUNCTION_SCOPE_MISMATCH` | Reject foreign project, agent, context, or request without revealing foreign facts |
| `FUNCTION_LIMIT_EXCEEDED` | Fail without a deployable result; preserve consumed resources and partial diagnostic traces |
| `FUNCTION_STORAGE_UNAVAILABLE` | Permit one same-input read retry within the original deadline |
| `FUNCTION_EXPECTATION_FAILED` | Preserve expected and actual output references; no ready bundle |

Identical invocation replay returns the saved result only when scope, arguments, graph revision, and dependency hashes match.
A repeated invocation ID with different inputs is an idempotency conflict. Deterministic computation does not justify silently reusing stale results.

## Debate and required evidence

| Challenge | Decision and consequence |
| --- | --- |
| A typed binding can still select the wrong property | Independent boundary fixtures must reject incorrect bindings and broken template comparisons |
| Filtering unknown rows makes results shorter | Preserve all outcomes; missing evidence must remain available to C8's next decision |
| Runtime code generation is more expressive | Reuse audited callables first; unsupported meaning blocks release and requires an approved template extension |
| A handwritten function could do the same work | Include an equally informed competent function control; do not attribute computation gains solely to ontology |
| A graph query can return the latest values cheaply | Pin one immutable revision; a changing view can combine incompatible observations |
| Mandatory function calls prove ontology use | Trace actual inputs, operators, and outputs; separate enforcement from representation effects |

## Required acceptance cases

These production cases are proposed and unrun. The harness report identifies any separately executed subset.

| Test ID | Fault or case | Expected result |
| --- | --- | --- |
| C3-T01 | Existing search fixture, four people, two nights, USD 420 | o1 capacity violation; o2 stay violation; o3 unresolved availability and minimum stay |
| C3-T02 | Matching o3 detail observation committed | o3 eligible; exact search and detail provenance retained |
| C3-T03 | Occupancy equals party; stay equals minimum; total equals budget | All three inclusive boundaries pass |
| C3-T04 | False availability, zero price, or missing minimum stay | False violates; zero compares normally; missing remains unknown |
| C3-T05 | Known capacity failure plus missing availability | Both diagnostics remain; offer is violated |
| C3-T06 | Conflicting totals, invalid numeric string, or stale quote | No usable comparison and no eligible result |
| C3-T07 | Different dates, party, currency, or fee basis | Scope or semantic check blocks eligibility |
| C3-T08 | Recipe injects Cypher, unknown template, extra field, or wrong property type | Rejection before callable execution |
| C3-T09 | Old bundle with repaired schema or missing observation barrier | No graph computation or result publication |
| C3-T10 | New observation commits halfway through a function | Every operator reads the original revision |
| C3-T11 | Candidate absent or source pagination incomplete | Explicit missing coverage; no universal-absence claim |
| C3-T12 | Broken template inequality or incorrect property binding | Independent expected-output tests reject the bundle |
| C3-T13 | Cross-project invocation or changed idempotent request | Rejection without foreign facts or stale results |
| C3-T14 | Time, candidate, or related-row bound exceeded | Explicit failure with all consumed operations retained |
| C3-T15 | Same result under optional and guarded execution | Function output matches; C4 enforcement receipts differ |
| C3-T16 | Frozen recipe or operator bytes change under a pinned reference | Integrity rejection before function dispatch; original artifact remains immutable |

Passing these tests would establish the declared function behavior. It would not establish model improvement, cheaper reasoning, or generalization.
