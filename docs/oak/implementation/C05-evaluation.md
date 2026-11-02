# C5: Independent evaluation and repair proposals

Design version 0.4.1. Owner: C5. Status: proposed; real-service acceptance is not run.

An offer can pass a function call and still fail the requested task.
C5 evaluates the final claim against independent evidence. During development, it proposes bounded artifact repairs.
It cannot change a schema, alter a score, or activate a package through a favorable model explanation.

The [shared contracts](CONTRACTS.md) define envelope, artifact, error, and package types.
[C4](C04-execution.md) supplies trials. [C1](C01-schema.md) and [C3](C03-functions.md) own executable repairs.
C6 owns candidate assembly, verification policy, review, and activation.

## Paper boundary and reuse

The paper scores answers with the dataset protocol before a judge reviews artifacts, trajectories, and scores.
The judge proposes target-specific additions, deletions, or modifications. Schema feedback returns to construction; function feedback returns to composition.
See [OaK section 3.2, Step 4](https://arxiv.org/html/2608.22974v1#S3.SS2).
The paper freezes schema and functions for unseen inference. See [section 3.3](https://arxiv.org/html/2608.22974v1#S3.SS3).

Our authorization, immutable assessments, repair preconditions, independent raw-source checks, and human activation extend that algorithm.
The first task uses an audited function template. C5 cannot turn an unsupported computation into executable model-written code.

Reuse Pydantic for strict contracts, pytest for deterministic scorer tests, and the selected provider SDK for any authorized judge call.
Reuse C10 persistence and job delivery. Use existing tracing facilities, with local records required and LangSmith export optional.
Custom code is limited to task-specific scoring, diagnostic redaction, repair validation, and artifact routing.
Do not build another evaluation platform, queue, model client, or expression language.

## Normative requirements

1. **C5-R01:** C5 must score every registered assignment, including missing trials and timeouts.
2. **C5-R02:** C5 must reject duplicate or unassigned trials before aggregation.
3. **C5-R03:** C5 must verify task results independently of C2 projection and C3 computation.
4. **C5-R04:** C5 must save immutable scores before it requests repair diagnosis.
5. **C5-R05:** C5 must keep evaluator-private data outside builder, host, and user diagnostic payloads.
6. **C5-R06:** C5 must bind each repair to exact target hashes and supporting trace references.
7. **C5-R07:** C5 must classify engineering defects separately from schema and function repairs.
8. **C5-R08:** C5 must return no actionable repair for held-out evaluation.
9. **C5-R09:** C5 must retain failed judge attempts and their consumed resources.
10. **C5-R10:** C5 must preserve earlier assessments when a scorer correction requires reassessment.
11. **C5-R11:** C5 must reject repair operations outside C1 and C3's supported profiles.
12. **C5-R12:** C5 must leave activation and release decisions to C6.

## Exact contracts

Use the shared `Id`, `Hash`, `Timestamp`, `ArtifactRef`, and result envelope. Pydantic rejects unknown fields and coercion.
Source IDs remain their admitted source strings. Resource references always resolve under the server-bound project and agent.

| Model | Required fields |
| --- | --- |
| `EvaluateRequest` | Shared envelope; `mode: engineering_replay\|model_development\|held_out_evaluation`; `assignment_manifest_ref`, `package_ref`, `evaluation_spec_ref`: `ArtifactRef`; `trial_refs: ArtifactRef[]`; `evaluator_binding_id: Id`; `diagnostic_policy_ref: ArtifactRef`; `judge_config_ref: ArtifactRef\|null`; `budget_reservation_id: Id` |
| `EvaluationSpec` | `profile: "offer-selection-evaluator/1"`; `evaluator_implementation_ref`, `public_contract_ref`, `private_case_manifest_ref`: `ArtifactRef`; `primary_metric: "complete_task_success"`; `required_checks: exact five CheckId values`; `abstention_policy: "incomplete"`; `unknown_policy: "not_success"`; `suite_ref: ArtifactRef` |
| `AssignedCase` | `assignment_id`, `case_id`, `condition_id`: `Id`; `repetition: integer>=1`; `split: engineering\|development\|selection\|held_out`; `task_request_ref: ArtifactRef`; `expected_source_manifest_ref: ArtifactRef` |
| `Assessment` | `assessment_id: Id`; `package_ref`, `evaluation_spec_ref`, `assignment_manifest_ref`: `ArtifactRef`; `outcomes: AssignmentOutcome[]`; `assigned_count`, `complete_success_count`, `incomplete_count`, `task_failure_count`, `evaluator_error_count`: nonnegative integers; `all_scores_available: boolean`; `usage_ref: ArtifactRef`; `created_at: Timestamp` |
| `AssignmentOutcome` | `assignment_id: Id`; `trial_ref: ArtifactRef\|null`; `score_state: scored\|evaluator_error`; `outcome: complete_success\|task_failure\|incomplete\|evaluator_error`; `reason: selected_valid\|constraint_violation\|unsupported_claim\|abstained\|missing_trial\|timeout\|cancelled\|source_unverifiable\|scorer_failed`; `checks: ScoreCheck[]`; `restricted_evidence_ref: ArtifactRef`; `public_diagnostic_ref: ArtifactRef`; `correct: boolean\|null` |
| `ScoreCheck` | `check_id: CheckId`; `result: satisfied\|violated\|unknown\|not_assessed`; `source_refs: ArtifactRef[]`; `detail_code: registered string` |
| `DiagnoseRequest` | Shared envelope; `assessment_ref`, `package_ref`, `development_trace_manifest_ref`, `judge_config_ref`: `ArtifactRef`; `round: integer[1,3]`; `budget_reservation_id: Id` |
| `Diagnosis` | `assessment_ref: ArtifactRef`; `proposals: RepairProposal[]`; `engineering_defects: EngineeringDefect[]`; `blocking_faults: boolean`; `coverage_limitations: string[]`; `judge_attempt_refs: ArtifactRef[]` |
| `RepairProposal` | `proposal_id: Id`; `target_kind: schema\|function_bundle`; `target_ref: ArtifactRef`; `base_package_sha256: Hash`; `action: add\|modify\|delete`; `patch_ref: ArtifactRef`; `requirement_ids: Id[]`; `reason_code: missing_definition\|incorrect_definition\|missing_binding\|incorrect_binding`; `reason: string[1,2048]`; `supporting_trial_refs: ArtifactRef[]`; `supporting_event_refs: EventRef[]`; `required_invalidation: Invalidation[]` |
| `EngineeringDefect` | `defect_id: Id`; `owner: C0\|C1\|C2\|C3\|C4\|C5\|C8\|C9\|C10`; `kind: mapping\|source\|encoding\|execution\|infrastructure\|evaluator\|unsupported_computation`; `affected_refs: ArtifactRef[]`; `trace_refs: ArtifactRef[]`; `description: string[1,2048]`; `actionable_during_held_out: false` |

`CheckId` is `occupancy`, `minimum_stay`, `availability`, `inclusive_total`, or `quote_scope`.
`Invalidation` is `schema`, `graph_projection`, `function_bundle`, `guard_binding`, or `verification_receipts`.
The assessment counts must sum to `assigned_count`. Each assignment appears exactly once.
Scored failures and incomplete outcomes use `correct: false`. Evaluator errors use `correct: null`, never true.
An empty assignment manifest fails validation. It does not produce a success rate with a zero denominator.
An assessment with evaluator errors sets `all_scores_available: false`. Its scoring stage fails and cannot satisfy C6's regression gate.
The saved partial assessment remains a diagnostic artifact, with all assignments present.

Candidate verification uses C6's `VerificationAssignmentBatch` as `assignment_manifest_ref`.
C5 checks its trusted registered parent, exact role subset, admitted cases, and single `package_ref` before scoring.
It uses the admission's existing evaluator binding. C6 cannot inject new expected answers through the batch.
Separate base and candidate assessments retain all assigned outcomes. C6 combines their comparison in the verification summary.
Ordinary and held-out assessments use their original admitted assignment manifests. Verification trials cannot enter those denominators.
C5 rejects `host_conformance` assignments before resolving an evaluator or scoring any trial.
Those child runs supply capability-test evidence only, as defined in the [mount conformance contract](MOUNT-CONFORMANCE.md).

`patch_ref` resolves to C1's `SchemaPatch` or a full replacement C3 `EligibilityRecipe` bound to the existing function ID.
The resolver validates the corresponding payload profile. It does not accept arbitrary JSON patch paths or executable text.
For function repair, the first profile permits `action: modify` only. Adding or deleting the sole required function is unsupported.
For schema repair, C5's actions map to C1's `add`, `replace`, and `remove` operations.
Each schema operation retains its expected old target hash. All replacement declarations must satisfy C1's typed profile.

## Independent offer-selection scoring

The trusted evaluator resolves the assigned request, expected source manifest, and submitted trial independently.
It verifies stored source hashes, observation IDs, admitted call arguments, source time, and source ownership.
The evaluator parses raw fixture responses through its separately authored scorer implementation.
It must not import C2's projection mapper, C3's eligibility helper, or their accepted/rejected result fields.
Shared Pydantic request contracts and the task specification may be reused. A shared acceptance computation may not be reused.

For an `observed_eligible_offer` claim, the evaluator performs these checks:

1. Resolve the selected source identity within the assigned case and permitted observations.
2. Verify the quoted dates, party, city, currency, and inclusive-price basis.
3. Verify that source occupancy covers the requested party.
4. Verify that source minimum stay does not exceed the requested nights.
5. Verify that source availability is explicitly true for the requested stay.
6. Convert the source total with independently specified exact decimal rules.
7. Verify that the inclusive total does not exceed the admitted USD budget.
8. Verify that submitted evidence references resolve to those permitted, hash-matching observations.

The five `ScoreCheck` values group currency and price basis under `inclusive_total`; request identity belongs to `quote_scope`.
Conflicting, stale, invalid, or missing source facts produce `unknown`. They cannot establish complete success.
Known violations remain visible even when another check is unknown.
All five checks must be satisfied for complete success. No required function call is part of the scoring rule.

The current C0 task requires a supported selection. `no_supported_offer` is a safe abstention with outcome `incomplete`.
It is not an exhaustive absence claim. A later task that rewards correct abstention needs a new evaluation profile.
Reservation, payment, or global-cheapest claims fail as unsupported.
The first profile requires `FinalSelection.explanation` to be empty. C11 renders a fixed summary from the structured result.
Nonempty explanatory text fails with `unsupported_claim`. This avoids an unspecified language judge inside deterministic scoring.
The host may retain prose as unverified trace commentary, outside the authoritative result.

The local harness has a published literal oracle for `dev-001` and offer `o3`.
That oracle tests independent expected selection and denominator handling. It does not implement the source-resolution procedure above.
See [harness limits](INTEGRATION-HARNESS.md). A passing literal comparison cannot prove correct evidence attribution.

## Score, diagnose, and route

1. Authenticate the evaluator capability and resolve the registered assignment set.
2. Reject foreign, duplicate, or unassigned trial references before scoring.
3. Match every assignment, retaining missing trials as incomplete outcomes.
4. Score each available trial against its independent expected evidence.
5. Save the immutable assessment, exact inputs, implementation hash, diagnostics, and usage.
6. If any scorer failed, return the assessment without automatic repair diagnosis.
7. If the mode is held out, return only non-actionable defect records.
8. For development, build the permitted judge view from artifacts, traces, and redacted score diagnostics.
9. Request one structured diagnosis under the admitted model configuration.
10. Validate target hashes, patch profiles, evidence references, and invalidation requirements.
11. Save accepted and rejected proposals with their reasons and consumed resources.
12. Send valid proposals to C6 for candidate planning, without modifying the current package.

The judge does not receive private expected answers or unrestricted evaluator source bundles.
Its diagnostics identify violated requirements and permitted development evidence. They do not copy evaluator-only values into prompts or graphs.
The evaluator and judge use distinct service capabilities. A model tool call cannot acquire evaluator access.

| Finding | Route and permitted change | Required invalidation |
| --- | --- | --- |
| Missing occupancy or stay definition | C6 creates a candidate; C1 applies a typed schema patch | Schema, all schema-bound projections, functions, guards, and verification receipts |
| Wrong recipe property binding | C6 routes a full supported replacement recipe to C3 | Function bundle, affected guards, and verification receipts |
| New arithmetic or behavior outside the approved template | C3 engineering maintenance defect; no automatic executable patch | New operator/runtime implementation and independent tests before candidate use |
| Wrong source mapping or stale evidence policy | C2 engineering defect; version the interpretation configuration | Affected projections, consumer verification, and new assessments |
| Dispatch, queue, or storage failure | C4, C8, or C10 engineering defect | No domain schema change solely for a transient failure |
| Incorrect expected answer or scorer logic | C5 evaluator defect; separately reviewed scorer version | Append new assessments and preserve original outcomes |

C6 orders a schema rebuild before reprojection and function verification. C5 cannot waive those stages.
A dependency omission rejects the proposal. C6 recomputes invalidation and may add dependencies; it cannot remove required invalidation silently.
Related schema and function proposals share a candidate and cannot be activated independently when their dependencies require both.

## Budgets, failure, and storage

The first fixture admits at most three construction rounds through C0. C5 does not start a fourth round.
Each diagnosis permits one initial response and one formatting retry within the shared reservation and absolute deadline.
An unsupported or stale semantic patch is rejected. It is not a formatting retry or permission to change the base.
A deterministic scorer exception receives one infrastructure retry with identical inputs, if the admitted deadline permits.
Persistent scorer failure remains `evaluator_error`. Judge failure leaves the saved assessment available and the diagnosis failed.
Queue redelivery resolves the stored operation receipt. It does not repeat a completed score or judge request blindly.

Stop diagnosis when there are no blocking proposals, the round limit is reached, or its budget is exhausted.
Stopping does not establish convergence or release eligibility. C6 still applies every required release gate.
Held-out defects cannot trigger a repair during that evaluation. A later candidate requires a separate development cycle.

C10 stores assessment indexes and operation receipts in PostgreSQL. Immutable artifact bytes hold scores, patches, and trace manifests.
Evaluator-only blobs use the restricted visibility defined by C9. Public diagnosis artifacts contain redacted references and safe codes.
C5 never writes Neo4j or the active-package pointer. All attempts retain timestamps, role, usage, model settings, and input/output hashes.
Record provider reasoning-token usage when available. Do not request hidden reasoning text.

Complete-success rate uses all registered assignments. Missing trials, timeouts, and cancellations remain in the denominator.
Report evaluator errors separately and mark the comparison incomplete until resolved. Never silently exclude them or score them as success.
For a live comparison, retain case-grouped paired outcomes, regressions, constraint errors, costs, and prespecified uncertainty.
The engineering fixture supplies no scientific effect estimate or evidence of model improvement.

## Adversarial decisions and acceptance

| Challenge | Decision |
| --- | --- |
| Reuse C3 to simplify the scorer | Reuse contracts, not the acceptance computation; an independent implementation can expose shared-path defects |
| Ask the judge to decide correctness | Persist deterministic source-based scores first; model diagnosis cannot change them |
| Treat abstention as success to improve rates | Keep C0's completion condition and count abstention as incomplete |
| Repair the ontology after a timeout | Route an execution defect unless observable evidence identifies a semantic error |
| Automatically implement a suggested computation | Reject unsupported operations and require reviewed implementation work |
| Hide scorer failures or missing trials | Preserve all assignments and mark unresolved evaluation explicitly |

All tests below are required real-service cases. They remain unrun unless a separate receipt identifies the exact executed subset.

| ID | Fault or scenario | Required observation |
| --- | --- | --- |
| C5-T01 | Valid saved selection with matching source evidence | Complete success without an agent rerun or source write |
| C5-T02 | Wrong selection after successful C1/C3 checks | Independent task failure |
| C5-T03 | Missing trial, timeout, and cancellation | Three assigned incomplete outcomes remain in the denominator |
| C5-T04 | Duplicate or unassigned trial | Explicit rejection without double counting |
| C5-T05 | Scorer exception or judge exception | Separate failed stage; persisted earlier scores remain unchanged |
| C5-T06 | Correct offer ID with forged or foreign evidence IDs | Evidence rejection; no complete-success result |
| C5-T07 | Unknown, conflicting, stale, or wrong-scope source value | Required check is not satisfied |
| C5-T08 | Abstention, nonempty explanation, or unsupported reservation/cheapest claim | Incomplete or unsupported outcome under the registered profile |
| C5-T09 | Stale target hash or missing diagnostic trace | Rejected repair; no candidate mutation |
| C5-T10 | Schema proposal without downstream invalidation | Rejection before C1 dispatch |
| C5-T11 | Template patch requests new executable behavior | Unsupported-computation defect; no model code execution |
| C5-T12 | Mapping, queue, and scorer faults | Correct engineering owner; no disguised schema patch |
| C5-T13 | Held-out trial with a clear repair opportunity | Scores and non-actionable defects only; pinned package unchanged |
| C5-T14 | Private-answer canary in evaluator input | Canary absent from judge prompts, host context, graph, and public diagnostics |
| C5-T15 | Completed third round or exhausted reservation | No fourth-round diagnosis or further budget-consuming work |
| C5-T16 | Reassessment after a scorer correction | New versioned assessment; original outcome and cost records retained |
| C5-T17 | Evaluator service attempts an active-package mutation | Access denied; the active pointer and activation history remain unchanged |
| C5-T18 | Supporting event has a foreign run ID or invalid sequence | Repair evidence is rejected before diagnosis publication or mutation |
| C5-T19 | Judge fails and retries after scores are saved | Each attempt and its resource usage remain recorded; original scores remain unchanged |
| C5-T20 | Verification batch omits an assignment, changes package or role, imports a held-out case, or supplies its own expected answer | Reject the batch before scoring; parent assignments and evaluator binding remain authoritative |
| C5-T21 | A completed conformance child trial is submitted as task or regression evidence | Reject before evaluator resolution; scored assignment counts remain unchanged |

These contracts apply ASD-STE100 principles. Full dictionary and grammar conformity remains unverified.
