# C6: Candidate changes, verification, and activation

Design version 0.4.4. Owner: C6. Status: proposed; real-service acceptance is not run.

A schema repair can leave old facts and functions inconsistent with its new meaning.
C6 coordinates the complete change. It preserves the active package until all required dependencies and checks are ready.

The [shared contracts](CONTRACTS.md) govern payload identity, verification receipts, and package hashes.
[C10](C10-service.md) governs HTTP routes, transaction boundaries, and queued commands.
C6 owns domain change policy. C1 through C5 retain their existing artifact ownership.

## Reuse and scope

Use Pydantic for typed changes and SQLAlchemy for state transitions within PostgreSQL transactions.
Use LangGraph for component sequencing and persisted pauses. Use Procrastinate for job delivery and retry scheduling.
The project supplies dependency rules, verification policy, and activation preconditions. It does not build another workflow engine.

The first slice supports the schema profile in [C1](C01-schema.md) and the audited template bindings in [C3](C03-functions.md).
Unsupported source fields, computations, or schema constructs block the candidate. C6 cannot silently weaken a requirement.
The paper's local logical loop and task-driven repair loop remain separate. See the source comparison in C1 and [C5](C05-evaluation.md).
Human review, project ownership, and atomic activation are implementation adaptations.

## Normative requirements

1. **C6-R01:** C6 must bind each change to an exact base package and activation generation.
2. **C6-R02:** C6 must preserve source assertions separately from human policy requirements.
3. **C6-R03:** C6 must resolve consequential ambiguity before it starts a candidate build.
4. **C6-R04:** C6 must invalidate all schema-bound projections and functions after a schema change.
5. **C6-R05:** C6 must complete dependency rebuilding before it requests final candidate verification.
6. **C6-R06:** C6 must resolve trusted verification receipts from storage before release decisions.
7. **C6-R07:** C6 must reject failed, missing, errored, or unrun required gates.
8. **C6-R08:** C6 must bind approval to candidate, verification, policy, and base-generation hashes.
9. **C6-R09:** C6 must activate a package through one atomic compare-and-swap transaction.
10. **C6-R10:** C6 must preserve the package pinned by each existing run.
11. **C6-R11:** C6 must verify current compatibility before it activates a previous package.
12. **C6-R12:** C6 must preserve all rejected candidates, attempts, and verification results.
13. **C6-R13:** C6 must register verification-scoped assignments before candidate trials use the shared authoritative run service.
14. **C6-R14:** C6 must stop construction at a sealed candidate and run regression only through its separately bound verification command.
15. **C6-R15:** C6 must include every protected previously passing development case in the frozen verification manifest.
16. **C6-R16:** C6 must reject activation when a protected case regresses or its comparison is incomplete.
17. **C6-R17:** C6 must require predeclared, independently specified, and explicitly approved expectations for an intentional requirement change.
18. **C6-R18:** C6 must freeze a versioned development population, characteristic rules, sampling policy, and selected cases before candidate outcomes are available.
19. **C6-R19:** C6 must block the coverage gate when required strata, interactions, or mandatory cases are missing or underfilled.
20. **C6-R20:** C6 must report routine-sample and challenge-set results separately and restrict population claims to the registered sampling design.
21. **C6-R21:** C6 must retain every selection reason while assigning each selected case only once per condition and repetition.

## Exact component payloads

Use the shared `Id`, `TermId`, `Hash`, `Timestamp`, and `ArtifactRef`. Reject unknown fields and scalar coercion.
C10's `CandidateCreate`, `VerificationStart`, `ReviewCreate`, `ActivationRequest`, and response models are canonical HTTP types.
Their `change_ref` points to `ChangeRequest` below. A browser cannot submit an executable patch or verifier identity.

| Model | Required fields |
| --- | --- |
| `ChangeRequest` | `profile: "oak-change/1"`; `change_kind: initial\|repair\|rollback`; `origin: initial_template\|human_requirement\|development_repair\|rollback`; `base_package_ref: ArtifactRef\|null`; `original_text: string[0,4096]`; `source_proposal_ref: ArtifactRef\|null`; `requested_scope: project_agent`; `requirement_specs: RequirementSpec[]`; `rollback_target_ref: ArtifactRef\|null` |
| `RequirementSpec` | `requirement_id: Id`; `statement: string[1,2048]`; `classification: definition\|task_constraint\|business_policy\|source_mapping`; `mode: hard\|advisory`; `scope_ref: ArtifactRef`; `condition_ref: ArtifactRef`; `exceptions_ref: ArtifactRef`; `effective_from: Timestamp\|null`; `effective_until: Timestamp\|null`; `unknown_behavior: block_selection\|report_unresolved`; `source_need_refs: ArtifactRef[]` |
| `InterpretedChange` | `change_ref: ArtifactRef`; `requirements_ref: ArtifactRef`; `schema_patch_ref: ArtifactRef\|null`; `function_recipe_ref: ArtifactRef\|null`; `engineering_defect_refs: ArtifactRef[]`; `ambiguities: Ambiguity[]`; `unsupported_codes: string[]`; `interpreter_ref: ArtifactRef` |
| `Ambiguity` | `field: string[1,128]`; `question: string[1,1024]`; `consequence: string[1,1024]`; `answer: string[1,2048]\|null` |
| `ChangePlan` | `change_ref`, `interpretation_ref`, `requirements_ref`, `test_policy_ref`: `ArtifactRef`; `base_package_ref: ArtifactRef\|null`; `base_generation: integer>=0`; `changed_semantic_ids: TermId[]`; `rebuild: RebuildTarget[]`; `ordered_stages: Stage[]`; `intended_outcome_changes_ref: ArtifactRef`; `source_manifest_ref: ArtifactRef`; `budget_ref: ArtifactRef` |
| `TestPolicy` | `profile: "oak-release-policy/1"`; `required_gates: Gate[]`; `suite_refs: ArtifactRef[]`; `selection_policy_ref`, `case_manifest_ref`, `protected_cases_ref`, `comparison_config_ref`: `ArtifactRef`; `intended_changes_ref: ArtifactRef`; `regression_rule: "zero_unintended_regressions"`; `evaluator_ref: ArtifactRef`; `guard_applicability: required\|not_applicable_optional_mode`; `policy_registry_version: Version` |
| `RegressionSelectionPolicy` | `profile: "oak-regression-selection/1"`; `population_ref`, `characteristic_rules_ref`, `strata_plan_ref`, `mandatory_cases_ref`, `interaction_plan_ref`, `change_impact_ref`, `budget_ref`, `sampling_implementation_ref`: `ArtifactRef`; `seed: uint32`; `claim: coverage_only\|target_population_estimate`; `target_distribution_ref: ArtifactRef\|null` |
| `VerificationAssignments` | `verification_id: Id`; `admission_id: Id`; `candidate_ref`, `test_policy_ref`, `suite_ref`: `ArtifactRef`; `base_package_ref: ArtifactRef\|null`; `entries: VerificationAssignment[]` |
| `VerificationAssignment` | `assignment_id`, `case_id`, `condition_id`: `Id`; `condition_role: base\|candidate`; `repetition: integer>=1`; `package_ref: ArtifactRef` |
| `VerificationCaseManifest` | `profile: "oak-verification-cases/1"`; `admission_id: Id`; `entries: VerificationCase[]` |
| `VerificationCase` | `case_id`, `stratum_id`: `Id`; `task_ref`, `source_manifest_ref`: `ArtifactRef`; `risk_tags: Id[]`; `selection_reasons: SelectionReason[]`; `inclusion_probability: number(0,1]\|null`; `target_weight: number>=0\|null`; `repetitions: integer>=1`; `prior_pass_ref: ArtifactRef\|null` |
| `ProtectedCaseManifest` | `profile: "oak-protected-cases/1"`; `task_binding_id: Id`; `base_package_ref: ArtifactRef\|null`; `cases: VerificationCase[]`; `suite_ref: ArtifactRef` |
| `ComparisonConfig` | `evaluator_binding_id: Id`; `evaluation_spec_ref`, `clock_ref`, `source_access_ref`, `driver_ref`, `budget_ref`: `ArtifactRef`; `model_config_ref: ArtifactRef\|null`; `replay_policy_ref: ArtifactRef` |
| `RegressionComparison` | `assignment_manifest_ref`, `protected_cases_ref`, `comparison_config_ref`, `intended_changes_ref`, `coverage_ref`: `ArtifactRef`; `case_results: RegressionCaseResult[]`; `assigned_case_count`, `completed_case_count`, `protected_case_count`, `protected_preserved_count`, `protected_intended_change_count`, `regression_count`, `fix_count`, `incomplete_case_count`: nonnegative integers; `state: passed\|blocked` |
| `RegressionCoverage` | `selection_policy_ref: ArtifactRef`; `strata: StratumCoverage[]`; `interaction_coverage_ref: ArtifactRef`; `missing_mandatory_case_ids: Id[]`; `gaps: string[]`; `state: passed\|blocked` |
| `StratumCoverage` | `stratum_id: Id`; `eligible_case_count`, `required_sample_count`, `sampled_case_count`, `selected_case_count`, `base_executed_case_count`, `candidate_executed_case_count`: nonnegative integers |
| `RegressionCaseResult` | `case_id: Id`; `repetition: integer>=1`; `prior_pass_ref`, `original_baseline_result_ref`: `ArtifactRef\|null`; `base_outcome: pass\|fail\|incomplete\|not_run\|null`; `candidate_outcome: pass\|fail\|incomplete\|not_run`; `transition: pass_to_pass\|pass_to_fail\|fail_to_pass\|fail_to_fail\|incomplete\|candidate_only`; `intended_change_ref: ArtifactRef\|null`; `diagnostic_ref: ArtifactRef` |
| `VerificationAssignmentBatch` | `verification_id: Id`; `parent_manifest_ref`, `package_ref`: `ArtifactRef`; `condition_role: base\|candidate`; `entries: VerificationAssignment[]` |
| `VerificationSet` | `verification_id: Id`; `candidate_ref`, `plan_ref`, `test_policy_ref`, `assignment_manifest_ref`: `ArtifactRef`; `receipt_refs: ArtifactRef[]`; `assessment_refs: ArtifactRef[]`; `missing_gates: Gate[]`; `state: passed\|blocked`; `summary_ref: ArtifactRef` |

`RebuildTarget` is `schema`, `projection`, `function_bundle`, `guard_binding`, or `verification`.
`Stage` is `interpret`, `schema`, `projection`, `functions`, `seal`, `regression`, `verify`, or `review`.
`SelectionReason` is `routine_sample`, `mandatory_boundary`, `known_regression`, `interaction`, or `change_targeted`.
`Gate` uses the shared receipt enum. The first condition profile contains `profile: "offer-condition/1"` and C5's exact `check_id` enum.
It selects the corresponding fixed C3 comparison. It cannot override its direction, threshold source, or unknown behavior.
The first exception profile contains `profile: "no-exceptions/1"` and `exceptions: []` only.
The scope profile contains `profile: "agent-scope/1"`, `project_id: Id`, and `agent_id: Id` matching the command scope.
The first five required checks use `mode: hard`, `unknown_behavior: block_selection`, and null effective-time fields.
`TestPolicy.evaluator_ref` points only to the public evaluator contract. C5 resolves private scoring material through its server-only binding.
Advisory rules, exceptions, or time-limited policies require a later supported rule profile. They cannot pass the first profile accidentally.
A task-specific budget change remains a request change when the schema already supports it.

`change_kind: initial` requires `origin: initial_template`, null base and proposal references, and generation zero.
It creates the initial typed schema and recipe. It does not invent a patch against a missing base.
`change_kind: repair` requires a base. Origin `development_repair` also requires a C5 proposal with a matching base hash.
`change_kind: rollback` requires origin `rollback` and a compatible target package reference.
Other kinds require a null rollback target. All kinds require the applicable verification gates.
User-provided facts go through C2's source assertion path. They cannot enter `RequirementSpec` as silently trusted provider values.

Apply [task-binding scope](TASK-CONTRACT.md#api-and-storage-scope) to these payloads. Protected cases cannot cross bindings.
`VerificationSet.summary_ref` resolves to `RegressionComparison`, with component gate results referenced by the same verification set.
The comparison uses public case diagnostics. Evaluator-private expected answers remain behind C5's server binding.
`prior_pass_ref` resolves the recorded independent case result, its original expectation and evaluator versions, and its input/source references.
The interface shows that recorded result separately from the fresh base and candidate outcomes.
For a protected case, `original_baseline_result_ref` identifies C5's fresh base-replay assessment under its original frozen expectations; it is null only for a case without a prior pass.
Each case result identifies an acceptance result against independent expectations, not a replacement for C5's complete-task metric.
An expected rejection can pass a negative-control test while its task outcome remains incomplete or failed.
Initial construction uses null `base_outcome` and `candidate_only`; it must satisfy every required candidate expectation.
Comparison totals count scheduled case/repetition rows. Protected totals count distinct cases, preserved only when every required repetition passes under unchanged expectations.
`protected_intended_change_count` counts protected cases that satisfy a separately approved changed expectation. Keep them separate from preserved behavior and ordinary fixes.
The per-condition C5 assessments retain their own assignment totals.

`RegressionSelectionPolicy.population_ref` pins eligible development case IDs, task/source versions, and characteristic values.
Every selected ID must belong to that population. Admit additional challenge fixtures before freezing it; do not draw cases from held-out data.
`characteristic_rules_ref` pins deterministic extraction rules, including explicit unknown values. No characteristic can depend on the candidate's result.
`strata_plan_ref` defines mutually exclusive strata, their required status, per-stratum sample allocations, and the intended allocation rationale.
`mandatory_cases_ref` lists critical boundary and known-regression case IDs with reasons; `interaction_plan_ref` lists feasible required combinations, quotas, and feasibility exclusions.
`change_impact_ref` records changed schema terms, functions, and their additional targeted case IDs. Empty lists require an explicit recorded rationale.
The registered budget covers the deduplicated union, both conditions when applicable, and every required repetition.
The pinned sampler selects without replacement from stable ordered IDs in each stratum using the saved seed.
`inclusion_probability` records routine-sample inclusion under that design; `target_weight` records an admitted target-population weight when applicable.
Cases selected only for a challenge reason have null routine-sample probabilities and weights. A case selected by both routes retains its routine-sample membership and all reasons.
`target_distribution_ref` pins the target population, source of its proportions, estimator, weighting rules, and uncertainty method when a population estimate is claimed.
Derive and validate inclusion probabilities and target weights from that admitted estimator, the frozen population, and the stratum allocations; arbitrary per-case weights are rejected.
For `target_population_estimate`, every positive-mass target stratum requires a nonzero routine-sample allocation, nonzero inclusion probabilities, and a declared sufficient allocation for the estimator and precision claim.
If the budget or eligible frame cannot support those allocations, register a narrower target population or `coverage_only` before outcomes are visible. Do not silently omit an unsampled target stratum from an estimate.
Unknown target proportions require `claim: coverage_only` and a null target distribution. Do not invent weights from a challenge set's frequency.
All stratum counts are distinct case IDs; executed counts require all registered repetitions to finish scoring in that condition, whether they pass or fail.
`sampled_case_count` counts only `routine_sample` cases; challenge cases cannot fill a missing routine-sample allocation.
`interaction_coverage_ref` records each required feasible combination, quota, selected case IDs, completed counts by condition, and gaps.
The coverage summary retains zero-count required strata and combinations. A blocked summary cannot be hidden by an aggregate pass rate.
The trusted verifier binds the selection policy, selected manifest, and coverage summary through the coverage receipt's input references.

## Candidate state machine

The candidate row uses C10's enum. Detailed stage and job errors remain separate fields and receipts.

| Current state | Trigger and precondition | Next state |
| --- | --- | --- |
| `draft` | Interpretation is complete, supported, and bound to the admitted policy | `building` |
| `draft` | Ambiguity or unsupported requirement remains | `draft`, with a blocking diagnostic |
| `building` | Required outputs exist and the immutable manifest is sealed | `verification_pending` |
| `building` | Terminal component failure or exhausted budget | `rejected` |
| `verification_pending` | Every applicable gate passes for the sealed candidate | `verified` |
| `verification_pending` | A required gate fails or ends without a pass | `rejected` |
| `verified` | Exact owner approval and atomic activation preconditions hold | `active` |
| `draft`, `building`, `verification_pending`, or `verified` | Base hash or generation no longer matches | `stale` |
| `rejected` or `stale` | User submits a corrected proposal | New candidate ID; old candidate remains unchanged |

An `active` candidate means that it has an activation receipt. The active pointer identifies the package used for new runs now.
A previously activated candidate remains historical after later promotion. C11 must not infer current activity from candidate state alone.
An owner rejection appends a review and makes an unactivated candidate `rejected`.
Editing a sealed candidate creates a new candidate. It cannot replace artifact bytes under the old hash.
To answer a draft's ambiguity, submit a corrected `ChangeRequest` through the existing candidate-creation route.
The first slice creates a new candidate and preserves the old diagnostic draft. It does not require an unspecified draft-edit endpoint.

## Build and verification procedure

1. C9 authorizes the initiating editor and C10 saves the idempotent candidate command.
2. C6 resolves the admitted task, exact base, agent version, and registry-approved test policy.
3. In engineering mode, C1 validates typed requirements or a recorded supported patch without a model call.
4. C6 returns unresolved consequential questions to the workspace and keeps the candidate in `draft`.
5. C6 saves the change plan, intended behavior changes, frozen selection policy and selected/protected case manifests, comparison configuration, source manifest, and complete rebuild set.
6. C1 applies the supported typed patch in an isolated candidate scope.
7. C1 compiles through Owlready2, runs HermiT, and saves actual logical and coverage diagnostics.
8. C2 creates a new projection from preserved raw observations under the new schema and interpretation hashes.
9. C3 rebuilds the recipe bindings and runs independent function fixtures against that projection.
10. C6 seals the complete package manifest with exact dependencies, test policy, and runtime references.
11. C6 registers verification-scoped development assignments, then C4 and C8 run them under their pinned packages.
12. C5 scores every assignment independently. C6 compares every paired case, including protected prior passes, intended changes, regressions, fixes, and incomplete evaluation.
13. The trusted verifier produces candidate-bound receipts after it verifies each underlying result and its inputs.
14. C6 resolves those receipts and publishes the review summary only when every applicable gate passes.
15. The owner reviews the exact hashes and submits approval through C10.
16. C6 activates the approved candidate only after the atomic preconditions below succeed.

`CandidateCreate` owns steps 1 through 10. It stops at `verification_pending` after sealing the package.
`VerificationStart` owns steps 11 through 14 and binds the candidate hash, policy, and suite before any trial.
One verification session is permitted for that candidate, policy, and suite tuple. Same-input retries return its existing job and results.
Changed inputs require a new candidate. Queue retry does not start another regression population.
The trusted verifier publishes the sealed `VerificationSet` through `CandidateView.verification_set_ref`.
It also publishes a blocked set on terminal failure. The browser never assembles a set from individual receipts.

The package hash excludes later verification and review receipts. Otherwise, the receipt would change the artifact it verifies.
Engineering replay cannot interpret arbitrary natural-language changes. Free text remains unprocessed supporting material.
The workspace must request supported typed fields or return `unsupported_interpretation_mode` before building.
Model-assisted interpretation requires a separately admitted execution profile, model configuration, and budget.
C1's logical report initially binds a schema hash. The verifier links it to the candidate only after checking the candidate's exact schema dependency.
The verifier must not convert a prior report for different bytes into a pass by replacing its reference.

A schema change rebuilds every schema-bound projection and function bundle in the candidate scope.
It does not delete old projections or mark old pinned runs invalid. Old runs remain compatible with their original schema.
A function-only change rebuilds its bundle and affected guards, then reruns all first-slice regression cases.
Mapping, source policy, template implementation, and evaluator changes retain their own versioned engineering review routes.

## Gate policy and regression meaning

The registry requires `structure`, `coverage`, `logic`, `projection`, `functions`, and `regression` for every first-slice candidate.
Guarded mode also requires `guard_routes`. Optional mode records its explicit inapplicability in the test policy.
A browser cannot remove a gate, change expected results, or select a weaker policy through an arbitrary artifact reference.
The server compares the submitted policy with the task's registry-approved policy before dispatch.

The initial deterministic suite requires complete expected outcomes for all assigned fixtures and zero unintended regressions.
A HermiT pass satisfies only the `logic` gate. It cannot satisfy function behavior or regression gates.

### Select cases across the task surface

Apply [the task-characteristic sampling method](../00-task-surface-and-corpus.md#group-cases-by-task-characteristics) as an engineering extension of the development verification loop.
Freeze the eligible development population and characteristic rules before selecting cases. Include previously failing cases, new cases, and negative controls; eligibility cannot mean only previous passes.
Group cases into mutually exclusive sampling strata. Keep overlapping risk tags for features such as boundary values, unknown evidence, conflicting constraints, or affected functions.
Use task structure and source attributes to assign these values, not the candidate's output or expected ease of passing.

Select a seeded stratified routine sample with registered per-stratum allocations. There is no universal fixed sample size.
Choose allocations, repetitions, and feasible interaction quotas against the declared workload, risk, precision needs when estimating rates, and available budget before outcomes are visible.
Then add every registered critical boundary case and known regression sentinel, required interaction cases, and cases targeted by the proposed change.
The interaction plan covers declared feasible pairs and explicitly identified higher-order high-risk combinations; pair coverage alone does not establish all interaction behavior.
Record why combinations are infeasible. A feasible combination without an available case remains an uncovered gap, not an exclusion.
The selected manifest is the union of these sets, deduplicated by stable case ID while retaining every selection reason and risk tag.
Base and candidate use this exact same union and registered repetitions. A case that is both sampled and mandatory runs once per condition and repetition.

Missing mandatory cases, empty or underfilled required strata, and unfilled required interaction quotas block coverage before trial dispatch.
During verification, missing required executions keep coverage blocked as well as making the comparison incomplete.
The candidate's `coverage` gate requires this task-coverage check as well as C1's schema-coverage evidence; neither substitutes for the other.
Report the gap and either add independently specified development cases under a new frozen policy or declare the narrower supported scope before another candidate attempt.
Budget pressure cannot silently remove a mandatory regression or relabel required coverage as optional after outcomes are known.

Report routine-sample outcomes by stratum, with their assigned denominators, separately from mandatory, interaction, and change-targeted challenge outcomes.
Challenge reason groups can overlap; show that overlap and never sum their counts as independent cases.
Use admitted inclusion probabilities or target weights for a task-population estimate, retain failures and timeouts, and group all repeated trials of a case when estimating uncertainty.
An unweighted rate from an oversampled risk group, a sample of past successes, or a pooled challenge set is not the workload's success rate.
With unknown workload proportions this is a task-coverage sample. Passing it establishes only the registered coverage and outcomes, not statistical representation of all future requests.
The current one-case synthetic development fixture cannot establish representative coverage or empirical performance.
Held-out cases remain outside this selection and refinement loop.

### Protect previously passing cases

Before candidate execution, resolve the frozen selected manifest and the task binding's registered prior passing assessments.
`ProtectedCaseManifest` pins every previously passing case in the selected union plus every mandatory prior regression case, with exact task/source versions, repetition counts, and prior-pass evidence.
Mandatory prior regressions remain protected even when the random draw does not select them. Sampling cannot retire them.
A newly confirmed regression from any selection route enters the mandatory regression registry before repair, preserving its original case, expectations, base-pass evidence, and failing result.
The rejected candidate remains unchanged. Its repair and later sample rotations must include that regression under the next admitted policy; a new draw cannot make the known defect disappear.
The development suite and mandatory registry are maintained for the task binding; they do not mean every historical request or held-out example.
An initial package has an empty prior-pass set and still runs its complete selected acceptance manifest, including all mandatory cases.
For later changes, the verification manifest contains the full protected set plus selected new, failing, and negative-control cases.
The server rejects a submitted subset that omits a protected case. A candidate cannot retire a case or replace its expected answer to obtain a pass.
Suite evolution requires a separate approved policy version, with retired or superseded cases and reasons visible before candidate verification.

Freeze both case manifests, independent evaluator/version, source snapshots, task inputs, clock, driver, and budgets before trials.
`ComparisonConfig` also pins model version and enabled thinking settings when model execution is admitted.
Base and candidate use that same configuration; only declared artifact interventions may differ.
Recorded replay is the first profile. Live variation requires predeclared repetitions and decision thresholds, with no selective reruns.
Use new scoped evidence contexts for each condition while retaining identical source inputs.
Held-out cases cannot enter construction, regression repair, or the protected development set.

C6 publishes one comparison row for every assigned case and repetition, including those that never completed.
Display the prior-pass marker, base outcome, candidate outcome, transition, intended-change reference, and failure diagnostic.
Report `pass_to_pass`, `pass_to_fail`, `fail_to_pass`, `fail_to_fail`, and `incomplete` separately; initial construction uses `candidate_only`.
The full-suite counts retain earlier failures and negative controls; the protected-case summary additionally shows preserved cases over all protected cases.
Timeouts, missing trials, skipped work, unavailable evidence, and scorer errors remain in the denominator and cannot count as preserved passes.
If the base replay cannot reproduce a protected prior pass under its original frozen expectations, report an incomplete baseline comparison and block activation until resolved.
Do not relabel that case as an ordinary baseline failure and claim a candidate fix.
A protected case with any required incomplete or unexpected candidate result blocks activation, even if OWL and function unit tests pass.

An intentional requirement change must identify affected cases and the permitted outcome transitions before execution.
An independent evaluator owner specifies revised expectations; the proposing agent cannot alter expected answers.
Obtain explicit requirement-change approval before trials and retain the original prior expectations and results alongside the revised policy.
Compare both packages under the same admitted policy, label the intentional transitions, and require their exact approval again at activation.
The prior result retains its original policy. C5 separately scores the base replay against the authoritative original expectations and retains that assessment.
Both base and candidate also receive the same revised-policy assessment; the original-policy check reuses the base trajectory rather than dispatching another task run.
A predeclared base failure under the revised rule is an intentional transition and does not itself block activation. A failure to reproduce the old baseline under its original rule still blocks activation.
Every affected case remains in the protected denominator. Report a satisfied changed expectation separately; a missing or unexpected result still blocks activation.
This is a declared behavior change, never an automatically waived regression. An undeclared change remains blocking.

### Register and evaluate every assignment

`TestPolicy.case_manifest_ref` pins admitted development case IDs, task/source hashes, and repetition counts, not reusable run identities.
Before trials, C6 derives and stores `VerificationAssignments` for the session.
For an initial candidate it contains candidate entries only. A repair or rollback contains paired base and candidate entries.
Each entry receives a new `assignment_id` and a condition ID equal to `v_` plus SHA-256 of canonical JSON `[verification_id, condition_role, package_sha256]`.
C10 preserves its existing uniqueness constraints and stores every entry before queueing any trial.
The same case in another candidate has a different verification identity. A retry within this session retains the original identity.
C6 submits C10's typed internal `VerificationRunCreate`. C5 evaluates this exact manifest, including failed or missing trials.
For C5's single-package request, C6 stores one `VerificationAssignmentBatch` for each condition role.
Each batch is the complete corresponding subset of the registered parent manifest, with no omitted or added assignment.
C5 rejects another package, role, or parent. C6 requires assessments covering every batch before it issues a regression pass.
Initial construction has one batch; repairs and rollbacks have two, even when their package hashes happen to match.
Only cases already admitted for development or engineering can enter this manifest. Held-out cases are rejected.
Each trial uses the same admitted task, clock, source access, driver, mode, and budgets except for the declared package intervention.
Verification trials and ordinary replay assignments have separate denominators and cannot be pooled as an experiment result.
Register intended behavior changes before candidate execution. Compare base and candidate against the same source snapshots and task settings.
Missing trials, scorer errors, unknown required evidence, or incomplete assignments cannot satisfy a required success case.
Known negative-control cases must match their declared expected rejection or incomplete outcome.
Do not relabel safe abstention as complete task success. C5 retains its original task metric.

Fresh model comparisons require a separately admitted model policy, enabled thinking, repetitions, thresholds, and budgets.
The first fixture default uses recorded responses. Editing text does not authorize a model run or live provider call.
Three construction rounds are the maximum under C0's first fixture budget. Budget exhaustion stops work without proving convergence.

## Atomic activation, rollback, and recovery

C10 locks the project membership, agent, and active-pointer rows in its defined order.
Within that transaction, C6 verifies current owner access, candidate readiness, the approved hashes, and artifact availability.
It resolves the complete regression summary and rejects missing protected cases, incomplete comparisons, and unintended regressions. Owner approval cannot bypass a failed gate.
It compares the active package hash and generation with the reviewed base. It also verifies current native-contract and runtime compatibility.
On success, it updates the pointer, increments generation, and appends the promotion and audit records together.
On conflict, it returns `409` and changes no active pointer. A stale candidate needs a new base and affected checks.

Existing runs keep their pinned package. This first slice does not support replacing a package inside a running task.
An urgent change requires cancellation and a separately admitted new run. Already recorded outcomes and costs remain intact.
Held-out defects cannot activate a repair within that evaluation population.

Rollback creates a candidate against the current base and points to a preserved previous package.
Reverify current task, source, tool, runtime, mandatory-policy, and artifact availability compatibility.
Reuse unchanged component receipts only when their exact inputs, suites, and runner versions match the approved policy.
Run current compatibility and regression gates, then obtain a new review. Rollback uses the same activation transaction.
It does not undo provider effects or erase observations, assessments, and history.

Queue retries retain the same operation ID and reconcile saved stage receipts before execution.
Transient delivery failure uses C10's library retry policy within the original reservation and deadline.
A semantic rejection needs a new bounded candidate attempt. It is not an infrastructure retry.
Checkpoint state holds artifact references. PostgreSQL records and store-local operation receipts remain authoritative after restart.

## Storage and failures

PostgreSQL stores candidates, stage indexes, review rows, verification indexes, active pointers, and promotion history through C10.
Immutable blobs store original requests, interpretations, plans, manifests, reports, and source-linked diagnostics.
C6 cannot edit schema bytes, source observations, graph assertions, function code, or evaluator answers directly.

| Error code | Meaning and required response |
| --- | --- |
| `change_ambiguous` | Keep draft; request the unresolved field without dispatching dependent work |
| `change_unsupported` | Keep the explicit gap; route engineering work without weakening the requirement |
| `stale_change_base` | Preserve candidate; reject mutation or activation against the changed base |
| `required_gate_incomplete` | Block review readiness or activation; retain failed and missing receipts |
| `protected_case_missing` | Reject an incomplete verification manifest before trial dispatch |
| `regression_coverage_incomplete` | Block coverage; identify missing mandatory cases, underfilled required strata or interactions, and incomplete required executions |
| `regression_detected` | Block activation and show the previous pass beside the unexpected candidate outcome |
| `baseline_replay_incomplete` | Block activation until the protected prior-pass comparison can be reproduced or its policy change is separately resolved |
| `verification_binding_mismatch` | Reject mismatched candidate, inputs, suite, policy, or verifier identity |
| `review_binding_mismatch` | Reject changed bytes or policy after approval |
| `rollback_incompatible` | Preserve current pointer and identify the incompatible dependency |
| `artifact_unavailable` | Block dependent work; reconcile storage without silently fetching a newer version |

## Adversarial review and acceptance

Reject schema-only promotion because old consumers can apply the wrong meaning.
Reject automatic approval from a judge because diagnosis is not a trusted verification receipt.
Reject selectively rebuilding undocumented dependencies because an omitted consumer can preserve an old interpretation.
Reject hidden immediate activation because running tasks would change treatment.

All cases below are proposed real-service tests. Local harness checks cover only their explicitly documented subsets.

| ID | Fault or scenario | Required observation |
| --- | --- | --- |
| C6-T01 | Abandon an unsubmitted form; submit corrected typed changes as a new candidate | Active package, graph, and functions remain unchanged; saved diagnostics remain inspectable |
| C6-T02 | Human policy says offers are refundable without source terms | Missing evidence remains explicit; no provider fact is invented |
| C6-T03 | Change an occupied schema property | New schema, projection, function, and guard dependencies precede verification |
| C6-T04 | HermiT passes but C5 rejects the intended task | Regression gate blocks activation |
| C6-T05 | UI submits passing booleans or a foreign verifier receipt | Rejection before review readiness |
| C6-T06 | Required receipt is missing, unrun, errored, or timed out | No verified candidate or promotion |
| C6-T07 | Candidate, suite, inputs, or policy changes after approval | Exact binding rejection; active pointer unchanged |
| C6-T08 | Two approved candidates share one base | At most one activation; the other receives `409` |
| C6-T09 | Run creation races activation | Each run pins one complete old or new package |
| C6-T10 | First candidate uses null base at generation zero | Same applicable gates; no bootstrap verification bypass |
| C6-T11 | Restart after a completed component or promotion commit | Saved receipts reconcile; no repeated semantic stage or promotion |
| C6-T12 | Rollback target has an obsolete tool contract | Compatibility rejection; history and source evidence remain intact |
| C6-T13 | Candidate policy omits guards or alters expected results | Registry-policy rejection before verification |
| C6-T14 | Held-out defect or exhausted third round proposes repair | No in-evaluation mutation or fourth construction round |
| C6-T15 | Owner access is revoked before activation | Transaction rejects promotion despite an earlier saved approval |
| C6-T16 | Verification receipt is added after the package is sealed | Package hash remains unchanged; receipt binds that exact hash |
| C6-T17 | Correct a rejected candidate after failed attempts | New candidate identity; original changes, receipts, and costs remain readable |
| C6-T18 | Engineering replay receives arbitrary free text or a supported typed patch | Free text blocks before model or build dispatch; the supported typed patch follows normal gates |
| C6-T19 | Verify two candidate versions over the same development cases and retry one session | Distinct session assignments, one run per assignment, and no duplicate trial on retry |
| C6-T20 | Initial build, repair, or rollback enters verification | Initial build has one complete candidate batch; later changes have complete paired base and candidate batches |
| C6-T21 | Create candidate, then send repeated identical Verify commands | Build stops after sealing; one bound verification job starts regression and publishes the exact set reference |
| C6-T22 | HermiT and function tests pass, but a protected previously passing case fails | Regression summary shows pass_to_fail and activation remains blocked |
| C6-T23 | Omit a protected case, or skip or time out its candidate trial | Omission is rejected; skipped or timed-out work remains in the denominator and cannot pass verification |
| C6-T24 | Change input snapshots, evaluator, model settings, or budget for one comparison condition | Comparability validation rejects the change before any regression pass |
| C6-T25 | Change a requirement intentionally or rewrite an expected answer after seeing a failure | Only predeclared independently specified changes with exact approval proceed; post-result answer changes are rejected |
| C6-T26 | A protected historical pass fails in the base replay while other cases improve | Baseline comparison is incomplete; all case outcomes remain visible and activation is blocked |
| C6-T27 | Rebuild selection with the same pinned population, strata, sampler, and seed, or attempt to resample after candidate outcomes | The selected IDs are reproducible and shared by both conditions; outcome-driven resampling is rejected |
| C6-T28 | Leave a required stratum empty or underfilled, or omit a mandatory prior regression that the random draw missed | Coverage remains blocked with the exact gaps; mandatory prior passes remain protected |
| C6-T29 | One case has several risk tags and is selected by routine, mandatory, and change-targeted routes | All reasons remain visible; one case is assigned per condition and repetition, with no duplicated denominator |
| C6-T30 | Claim a population rate from only prior passes, a pooled unweighted challenge set, or a positive-mass stratum with zero allocation | The claim is rejected; every positive-mass target stratum needs nonzero selection probability and a declared sufficient allocation, with routine and challenge denominators kept separate |
| C6-T31 | Cover every individual stratum but omit a required feasible pair or higher-order risk combination | Interaction coverage identifies the unfilled quota and blocks the coverage gate |

The requirements apply ASD-STE100 principles. Full dictionary and grammar conformity remains unverified.
