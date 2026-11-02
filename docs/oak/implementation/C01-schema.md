# C1 schema construction and repair

Design version 0.4.8. November 2, 2026. Owner: C1.

Status: specified. The production compiler, reasoner worker, and repair loop are not implemented by this document.

This specification refines the [schema-builder design](../01-schema-builder.md).

## Decision and boundary

Reuse Pydantic validation, Owlready2 ontology construction, and HermiT reasoning.
The project supplies a bounded mapping from domain declarations to Owlready2 calls.
It must not implement an OWL parser, reasoner, or general compiler framework.
Use pytest fixtures for coverage and failure checks. See [reuse rules](CONTRACTS.md#build-versus-reuse).

C1 defines domain meaning. It produces an immutable schema candidate and a formal verification receipt.

C1 does not fill missing facts, run selection functions, score task success, or activate a package.

The first engineering fixture is read-only offer selection with `search_offers` and `get_offer_details`. These tool names and this domain are not C1 admission requirements for the general product.

In that fixture, an agent must distinguish occupancy, minimum stay, availability, quote scope, and total price. Adding these fields alone cannot enforce their use.

C1 constructs meaning from the task and representative development evidence. It does not inspect the working agent's planner or require its full native tool catalog. The [construction sequence](../01-schema-builder.md#when-the-working-agent-runs) distinguishes the initial draft from later working-agent attempts and refinement. The [task contract](TASK-CONTRACT.md) defines the primary ReAct worker interface: typed F calls over the graph, with task data accessed only through the kernel. The detailed managed declarations below remain the narrower engineering fixture.

**C1-R01:** C1 must accept only a typed schema document, never model-generated Python, OWL text, or Cypher.

**C1-R02:** C1 must build each repair in a new candidate scope.

**C1-R03:** C1 must preserve the active schema and each run's pinned package.

## Paper requirement and implementation choice

The paper separates analysis, drafting, and formal verification. Failed drafts return to drafting with reasoner feedback. Its later task-evaluation loop proposes schema and function changes. [OaK version 1, section 3.2, Steps 1 and 4](https://arxiv.org/html/2608.22974v1).

Appendix A identifies disjointness, restrictions, property features, global consistency, and unsatisfiable classes. These are logical checks, not source-truth checks. [OaK Appendix A](https://arxiv.org/html/2608.22974v1).

The hotel case adds occupancy and minimum-stay fields, then repairs the function to use them. Section 4.4 compares removal of refinement and function components. These results motivate separate verification layers. They do not validate our implementation. [OaK sections 4.4 and 4.6](https://arxiv.org/html/2608.22974v1).

Our typed syntax, compiler limits, process isolation, bounded retries, independent regression tests, and human activation are implementation choices. Our tools acquire evidence incrementally. The paper supplies each query's accompanying corpus and freezes its schema and functions for inference. [OaK section 3.3](https://arxiv.org/html/2608.22974v1).

## Public contracts

All models use Pydantic strict validation and reject unknown fields. Every reference resolves within the server-bound project.

Use `ArtifactRef` and `Id` from the [shared contracts](CONTRACTS.md).

C10 resolves an artifact reference. A client cannot choose a filesystem path or storage key.
The service envelope uses `0.4.0`. The schema payload uses `oak-schema/1`. The local harness uses `oak-contract-harness/1`.

| Contract | Required fields and types |
| --- | --- |
| `SchemaBuildRequest` | `project_id: Id`, `agent_id: Id`, `invocation_id: Id`, `candidate_id: Id`, `mode: initial_or_repair`, `base_schema: ArtifactRef_or_null`, `requirements: ArtifactRef`, `task_surface: ArtifactRef`, `development_manifest: ArtifactRef`, `repair: ArtifactRef_or_null`, `competency_suite: ArtifactRef`, `compiler_profile: literal(oak-owl/1)`, `model_settings: ArtifactRef`, `budget: SchemaBudget` |
| `SchemaBudget` | `max_drafts: integer[1,3]`, `max_worker_retries: integer[0,1]`, `reasoner_timeout_seconds: integer[1,60]`, `deadline_utc: RFC3339`, `max_input_tokens: positive_integer`, `max_output_tokens: positive_integer`, `max_cost_minor_units: nonnegative_integer`, `cost_currency: ISO4217` |
| `SchemaDocument` | `contract_version: literal(oak-schema/1)`, `types: TypeDecl[]`, `properties: PropertyDecl[]`, `axioms: Axiom[]`, `requirements: RequirementLink[]`, `identity_rules: IdentityRule[]` |
| `SchemaPatch` | `base_schema_sha256: hash`, `operations: PatchOperation[]`, `source_assessment: ArtifactRef_or_null`, `reason: nonempty_string`, `changed_requirement_ids: string[]` |
| `PatchOperation` | `action: add_or_replace_or_remove`, `target_kind: type_or_property_or_axiom_or_identity`, `target_id: string`, `expected_old_hash: hash_or_null`, `replacement: matching_declaration_or_null` |
| `SchemaArtifact` | `schema: ArtifactRef`, `owl: ArtifactRef`, `coverage: ArtifactRef`, `reasoner_report: ArtifactRef`, `competency_report: ArtifactRef`, `requirements: ArtifactRef`, `compiler_profile: string`, `compiler_version: string`, `changed_term_ids: string[]`, `dependency_manifest: ArtifactRef` |
| `SchemaBuildResult` | Shared outcome envelope, `artifact: SchemaArtifact_or_null`, `attempts: ArtifactRef[]`, `failure: Error_or_null` |

For an initial build, `base_schema` and `repair` must be null. A repair requires both references.

The coordinator admits budgets before dispatch. C1 must charge all attempts to that reservation. C1 cannot expand its limits.

`model_settings` must identify the provider, model version, enabled thinking settings, and actual request settings. Recorded-response tests name their substitute instead.

The shared envelope retains run, attempt, parent-call, operation, and assignment identifiers. C1 records input and output hashes for each attempt.

**C1-R04:** C1 must reject held-out construction requests before model or reasoner dispatch.

**C1-R05:** C1 must reject a patch whose base hash or target hash differs from its saved base.

## Exact schema language

`TermId` matches `[a-z][a-z0-9_]{0,63}`. IDs are unique across classes and properties. Labels are separate display text.

The compiler derives stable IRIs from `urn:oak:{project_id}:term:{term_id}`. Model text cannot supply an IRI or import.

| Declaration | Fields |
| --- | --- |
| `TypeDecl` | `id: TermId`, `label: string`, `definition: string`, `requirement_ids: string[]` |
| `PropertyDecl` | `id: TermId`, `label: string`, `definition: string`, `kind: object_or_data`, `domain: TermId`, `range: TermId_or_string_integer_boolean`, `requirement_ids: string[]` |
| `IdentityRule` | `type_id: TermId`, `scope_fields: string[]`, `key_fields: TermId[]`, `authority: string`, `missing_key: literal(reject)` |
| `RequirementLink` | `requirement_id: string`, `disposition: logical_or_runtime_or_mixed`, `axiom_ids: string[]`, `runtime_consumer_ids: string[]`, `source_refs: ArtifactRef[]` |

Identity rules are C2 instructions. C1 does not translate them into `owl:hasKey` or assert record equality.

The supported `Axiom` is a tagged union. Each member also has `id` and `requirement_ids`.

| `kind` | Payload | OWL translation |
| --- | --- | --- |
| `subclass` | `child`, `parent`: named classes | `SubClassOf(child parent)` |
| `equivalent_intersection` | `class_id`, `members: named_class[2..32]` | Equivalent class with an intersection |
| `disjoint` | `members: named_class[2..32]` | Pairwise class disjointness |
| `object_restriction` | `class_id`, `property_id`, `quantifier: some_or_only_or_min_or_max_or_exactly`, `filler: named_class`, `count: integer[0,1000]_or_null` | Named object-property restriction on the class |
| `property_feature` | `property_id`, `feature: functional_or_inverse_functional_or_transitive_or_symmetric_or_asymmetric_or_reflexive_or_irreflexive` | The named property characteristic |
| `inverse` | `property_id`, `inverse_id` | Inverse object properties |

`count` is required only for `min`, `max`, and `exactly`. All other variants require null.

Object properties have one named domain and range. Data properties support only string, integer, and boolean ranges in this profile.

Only `functional` applies to data properties. Object restrictions and inverse declarations require object properties.

The profile forbids imported ontologies, property chains, subproperties, arbitrary expressions, individuals, rules, and datatype facets.

The profile excludes reserved top and bottom class identifiers. Each user-defined class must be satisfiable.

The compiler computes non-simple object properties from each transitive property and its inverse closure.

Non-simple properties cannot occur in cardinality restrictions or functional, inverse-functional, asymmetric, or irreflexive declarations.

This restricted profile avoids a general OWL parser. Its implementation must follow OWL 2 DL structural restrictions. [W3C OWL 2 Structural Specification, section 11](https://www.w3.org/TR/owl2-syntax/#Global_Restrictions_on_Axioms_in_OWL_2_DL).

**C1-R06:** Unsupported declarations must fail with `UNSUPPORTED_SCHEMA_CONSTRUCT`.

**C1-R07:** The compiler must not discard, weaken, or silently approximate an unsupported axiom.

Future language extensions require a new compiler profile and new tests. The first profile does not claim complete OWL expressiveness.

## Runtime meaning that OWL does not enforce

| Offer-selection rule | Owner and operation |
| --- | --- |
| Occupancy is an integer for the observed offer | C1 defines it. C2 validates and stores the source value. |
| Occupancy must cover the request's party size | C3 compares values. C5 evaluates the selected result independently. |
| Minimum stay must fit the requested stay | C3 compares values from the same request context. |
| Missing availability cannot support selection | C2 retains unknown. C3 returns unresolved evidence. C4 blocks guarded finalization. |
| A quote belongs to the requested dates and party | C2 preserves context. C3 rejects incompatible evidence. |
| Total price includes the permitted fees | C2 uses the versioned source interpretation. C5 verifies against raw evidence. |

For the first USD task, computation uses integer cents. C2 preserves the original value and rejects non-exact conversion.

The logical schema can declare integer `total_minor_units` and string `currency`. It does not perform currency conversion or arithmetic.

The original API field names remain unchanged. A versioned C2 mapping connects them to schema fields.

Open-world reasoning cannot establish that an unobserved value is false. A domain axiom can infer a type without rejecting a bad input.

**C1-R08:** Each requirement must name all runtime consumers needed beyond its logical encoding.

**C1-R09:** The coverage report must separate represented meaning from implemented and tested behavior.

## Build and local verification procedure

1. Resolve each input under the admitted project and agent.
2. Validate hashes, development access, patch preconditions, and the remaining budget.
3. Produce source-linked requirements from the admitted task and development evidence.
4. Request one typed draft, or apply the typed repair to a copied base.
5. Validate structure, references, identity rules, and requirement coverage.
6. Compile all supported declarations in a fresh Owlready2 `World`.
7. Save the schema, emitted OWL, and declaration-to-axiom coverage before reasoning.
8. Start one isolated reasoner worker with the pinned Java and package versions.
9. Enforce the admitted timeout and terminate the worker process group on expiry.
10. Save the real process result, diagnostic stream, and resource usage.
11. If consistent, collect unsatisfiable user classes from the same world.
12. Run the admitted semantic competency suite against the candidate.
13. If all C1 gates pass, publish the immutable schema artifact.
14. Otherwise, retry only under the failure policy below.

The parent process launches the worker with an argument array. It does not interpolate schema text into a shell command.

The worker has a temporary directory, no provider credentials, and no domain-graph write credentials. Imported network resources are forbidden.

Use Java 21 and the root project's pinned Owlready2 dependency. Record the actual Java version and bundled reasoner JAR hash.

Owlready2 runs a modified bundled HermiT through `sync_reasoner`. It exposes ontology inconsistency errors and unsatisfiable classes. Its documentation does not promise HermiT explanations for each failure. [Owlready2 reasoning documentation](https://owlready2.readthedocs.io/en/latest/reasoning.html).

Set `ignore_unsupported_datatypes=False`. Read only the declared ontology and the worker's own inference world.

Do not call `close_world` to make missing source values appear false. Any closed-world application check belongs to its explicit runtime consumer.

The compiler must produce the same axiom set from the same normalized schema. OWL serialization need not be byte-canonical.

Store two hashes: the canonical schema-content hash and the exact emitted OWL-byte hash. A reasoner receipt binds both.

Canonical schema JSON uses UTF-8, sorted object keys, no insignificant whitespace, and sorted declaration arrays by ID. Set-valued members are sorted.

The compiler rejects duplicate IDs before canonicalization. It preserves definition text exactly. Presentation-only changes still create a new schema artifact.

## Verification report and evidence

| Field | Exact state or value |
| --- | --- |
| `schema_sha256`, `owl_sha256` | Exact input hashes |
| `compiler_profile`, `compiler_version` | Pinned implementation identity |
| `owlready2_version`, `java_version`, `hermit_jar_sha256` | Observed dependency identities |
| `profile` | `passed`, `failed`, or `not_run` |
| `global_consistency` | `consistent`, `inconsistent`, or `unknown` |
| `class_analysis` | `passed`, `failed`, or `not_run` |
| `unsatisfiable_classes` | Sorted IDs, or null when class analysis did not run |
| `coverage` | Required declaration count, emitted count, runtime-only count, unsupported IDs |
| `competency` | Passed IDs, failed IDs, not-run IDs, suite hash |
| `process_outcome` | `completed`, `timeout`, `crashed`, or `cancelled` |
| `diagnostic_refs` | Raw stderr/stdout references and parsed diagnostics |
| `elapsed_ms`, `attempt_id` | Actual measurement and causal identifier |

An empty class list is valid only after completed class analysis. A timeout, crash, or global inconsistency cannot produce a successful empty list.

A competency question is an independently authored expected distinction. For example, `Offer` and `Quote` must remain separate concepts.

The suite contains typed assertions over declared terms and expected entailments. Each entailment fixture runs in a fresh copied ontology world.

It also includes negative tests. Missing required fields must fail the suite even when HermiT reports consistency.

The model that drafts the schema cannot revise expected answers during verification. C5 owns later task-outcome checks.

## Repair routing and retries

| Failure | C1 behavior | Retry limit |
| --- | --- | --- |
| Malformed draft or resolvable logical contradiction | Save diagnostics and request a corrected draft | Three drafts total, including the first |
| Unsupported construct or unresolved requirement meaning | Return a blocked candidate to its owner | No automatic relaxation |
| Stale base, wrong project, or held-out input | Reject before dependent work | No automatic retry |
| Worker startup or temporary filesystem failure | Retry the identical candidate after saving the failure | One worker retry across the invocation |
| Reasoner timeout | Return `REASONER_TIMEOUT` with unknown logical results | No automatic retry |
| Compiler error or inconsistent encoding coverage | Return `COMPILER_FAILURE` | No model retry |
| Deadline, cancellation, or cost exhaustion | Stop dispatch and retain diagnostic artifacts | No retry |

Every retry consumes the existing deadline and reservation. A model cannot declare its own failure resolved.

C1 sends the actual reasoner message to drafting. Where explanations are absent, it reports that limitation.

An optional future explanation service requires its own contract and verification. It is not a dependency of this first design.

**C1-R10:** A repair must retain the requirement set unless an explicit requirement-change proposal authorizes its change.

**C1-R11:** Removing an axiom to pass HermiT must fail if that removal deletes a required distinction.

## Schema-change regression protection

Every schema change must preserve verified task behavior before activation. C1's structural, OWL, and competency checks establish a schema candidate; they do not establish that dependent functions or previously passing tasks still work.

**C1-R12:** C1 must return changed-term and dependency references for every schema change so C6 can rebuild and verify the complete candidate.

**C1-R13:** A schema change must remain inactive until C6 verifies required task-surface coverage and zero unintended regressions in the frozen development suite.

C1 reports every changed term and identity declaration. C10 constructs the dependency closure from the saved manifest.

| Change | Required downstream operation |
| --- | --- |
| Class, property, axiom, meaning, unit, or identity change | Invalidate old C2 projections and C3 bundles for the new candidate |
| New required evidence field | Reproject saved raw observations with a new C2 mapping or report an evidence gap |
| Identity change | Build a separate graph projection with new keys; preserve the previous graph |
| Function input or result meaning change | Require new C3 contracts, plans, and tests |
| Requirement or protected-boundary change | Require new C4 guard bindings and coverage tests |
| Any candidate artifact change | Invalidate C6 verification and approval bound to the old hashes |

Version 1 conservatively rebuilds all C2 candidate projections and C3 functions after any schema-content change. Selective reuse is deferred. Previous projections, function receipts, and package verification bound to the old schema cannot establish correctness for the changed candidate. Preserve them for the old package and its pinned runs.

C2 may replay existing observations. It cannot fabricate a value absent from the raw evidence.

After C1 passes, C2 validates projection and provenance. C3 validates function behavior. C6 dispatches the frozen base/candidate assignments through C4, and C5 independently scores their outcomes.

Use [C6's task-surface selection and regression gates](C06-workspace.md#select-cases-across-the-task-surface). The suite combines the stratified routine sample, mandatory known regressions and boundaries, required interactions, and change-targeted cases. Keep the broad sample even when dependency analysis suggests a narrow change. Protect previously passing selected cases and mandatory historical regressions, retain failing and negative-control cases, and compare the same inputs, evaluator, settings, and budgets in both conditions.

C6 blocks activation for any unintended regression, incomplete required comparison, or missing required coverage, even when C1 and HermiT pass. An intended requirement change must follow C6's predeclared and independently specified expectation-change policy; failed expectations cannot be rewritten after results are known. A confirmed new regression enters the mandatory registry before repair.

Route schema diagnostics to C1 and function diagnostics to C3 under the admitted repair budget. Each changed candidate invalidates its earlier verification and must repeat the complete required checks against its exact hashes. The interface shows the failing cases and affected characteristic groups separately from the OWL result.

C6 presents the exact candidate and all required receipts. C10 activates only the reviewed hashes against the unchanged active base.

No C1 report can substitute for those downstream gates. Passing establishes no observed unintended regression in the declared suite, not correctness for every unseen task. Held-out cases remain outside selection and repair, and a frozen held-out run cannot invoke this path.

## Storage ownership

C10 owns artifact storage, relational metadata, authorization, and job state. C1 writes through C10's admitted artifact service.

Immutable blobs contain schema JSON, OWL bytes, coverage, diagnostics, competency results, prompts, and model responses permitted by the tracing policy.

PostgreSQL rows contain project/agent/candidate IDs, artifact references, attempt states, dependencies, and result indexes. They contain no raw secrets.

C1 owns no Neo4j mutation. It cannot migrate active graph nodes or edit a function bundle.

Artifact publication follows write, hash verification, then metadata commit. An unpublished blob is not an eligible schema.

The schema result and its job-completion event use one metadata transaction. A replay returns the saved terminal result for the same invocation hash.

Reusing an invocation ID with different input content returns `IDEMPOTENCY_CONFLICT`.

## Debate and disposition

| Challenge | Decision and reason | Evidence that must challenge the decision |
| --- | --- | --- |
| Why use OWL for four numeric checks? | OWL verifies concept structure. Numeric checks remain ordinary typed computation. | Measure compiler cost separately from task-function benefit. |
| Why not generate arbitrary OWL? | A typed subset gives complete encoding coverage and bounded executable behavior. | Unsupported required meaning blocks admission and requires a versioned extension. |
| Can a consistent schema still be wrong? | Yes. Requirement coverage, competency questions, source validation, and task evaluation remain separate. | A missing-occupancy fixture must pass logical checks but fail semantic coverage. |
| Can HermiT explain every contradiction? | This adapter makes no such promise. Preserve actual diagnostics. | Real adapter tests must verify its observed error classes and streams. |
| Can C1 repair active graph data directly? | No. New schema versions require new projections. | Restart and rollback tests must retain old facts and package pins. |
| Can a model delete a troublesome rule? | Only an explicit requirement change can authorize removal. | A contradiction fixture that drops a required rule must remain blocked. |
| Why not reuse every unaffected function? | Version 1 rebuilds conservatively because semantic dependency detection is not yet proven. | Later reuse needs equivalent-behavior tests and complete dependency manifests. |

## Required tests and release gate

These tests are specified, not executed by this document. The contract harness uses recorded formal-gate outcomes.

| Test ID | Input or fault | Required receipt |
| --- | --- | --- |
| C1-T01 | Same canonical schema compiled twice | Same semantic hash and axiom set; both OWL-byte hashes retained |
| C1-T02 | Named subclass of two declared disjoint classes | Global consistency may pass; unsatisfiable class blocks publication |
| C1-T03 | Required relation has minimum one and maximum zero | Unsatisfiable class identified; no deployable schema |
| C1-T04 | Transitive property used in cardinality | Profile rejection before HermiT |
| C1-T05 | Valid supported schema | Exact versions, coverage, completed consistency, and empty unsatisfiable list |
| C1-T06 | Omitted required occupancy field | Semantic coverage fails even if the ontology is consistent |
| C1-T07 | Worker timeout or Java crash | Unknown logical result; distinct process failure; zero promotions |
| C1-T08 | Encoder omits one required axiom | Coverage fails before publication |
| C1-T09 | Correction removes a required distinction | Repair rejected; original requirement retained |
| C1-T10 | Changed base hash or project ID | No model, compiler, or reasoner dispatch |
| C1-T11 | Schema adds occupancy but C3 ignores it | C1 can pass; complete package verification fails |
| C1-T12 | Schema repair during a pinned held-out run | New candidate only; active run and graph hashes remain unchanged |
| C1-T13 | Same invocation replayed after lost acknowledgement | Same artifact refs and terminal receipt; no second publication |
| C1-T14 | Failure consumes final attempt or reservation | No next dispatch; all attempts and costs remain visible |
| C1-T15 | Input supplies executable Python, raw OWL, Cypher, or unknown schema fields | Typed boundary rejects it before compilation or execution |
| C1-T16 | Request identifies held-out schema construction | Rejection with zero model and reasoner dispatches |
| C1-T17 | A runtime requirement lacks its consumer binding | Coverage gate rejects the incomplete schema artifact |
| C1-T18 | Logical checks pass without runtime execution receipts | Coverage distinguishes represented meaning from unverified runtime behavior |
| C1-T19 | Schema and OWL checks pass but a protected previously passing task fails after rebuilding | C6 records the regression and blocks activation; the active package remains unchanged |
| C1-T20 | Schema repair passes executed cases but omits a mandatory regression, required group, or required comparison | Missing coverage or incomplete comparison blocks activation; no case is silently removed |
| C1-T21 | Changed schema is paired with projection, function, or verification receipts bound to the old schema | Changed-term and dependency references trigger rebuilding and complete re-verification; stale receipts cannot authorize activation |

Before production release, execute real compiler and HermiT tests in the root environment. Then execute downstream integration and activation tests.

Passing substitute tests establishes only the substitute boundary. Installation probes and consistent OWL do not establish improved agent performance.
