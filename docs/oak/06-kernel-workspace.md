# Controlled kernel workspace and business rule editing

Design version 0.3.0. November 2, 2026. This document specifies a proposed interface and its integration contracts. The editing interface, promotion service, and enforcement guard are not implemented.

The workspace lets a user inspect domain knowledge and propose a change. The user reviews the candidate before activation. The workspace adds discussion, checks, and version control around the five components. It does not add a sixth learning algorithm.

The paper uses task traces and a model judge to propose schema and function repairs. It identifies human feedback and stronger verification as future work. This human editing path is an extension. [OaK section 3.2, Step 4; section 5](https://arxiv.org/html/2608.22974v1).

Use the [independent verification plan](INDEPENDENT-VERIFICATION.md) for cross-component checks.

## Purpose and limits

The interface must show the interpreted requirement, source evidence, implemented checks, and unresolved gaps. A successful report applies only to its named artifacts and cases. It cannot establish that every future task will succeed.

Discussion creates a proposal. It does not change the active kernel. The user can propose a requirement without writing OWL, Cypher, or function code. Technical details remain available for inspection.

The [data and visibility specification](07-kernel-data-and-visibility.md) connects requirements to schema, observations, functions, and version history.

## Interface views

| View | Visible information | Main action |
| --- | --- | --- |
| Task and sources | Supported work, task constraints, tool contracts, source material, and evidence coverage | Configure inputs or inspect a source |
| Kernel overview | Definitions, business requirements, active version, and implementation states | Select a requirement or concept |
| Discuss a change | Conversation beside a requirement, concept, function, or failed case | Describe the change |
| Change review | Interpreted meaning, before/after behavior, affected artifacts, source needs, and open questions | Revise the proposal or start declared checks |
| Verification | Separate check results and old/new outcomes for named cases | Inspect a failure |
| Versions | Active version, candidates, approval scope, activation time, pinned runs, and compatible rollback target | Activate a reviewed candidate or restore a compatible version |

Keep the active version and draft status visible. Preserve drafts when the user changes views. Discarding a draft must not affect active behavior. For a blocked state, show the cause and a relevant next action. Preserve the discussion with its structured interpretation.

Show plain-language summaries before technical details. Support keyboard access. Use text labels as well as colors. Show progress and failures explicitly. A model explanation cannot replace a failed check result.

## Classify the change

| User statement | Meaning | Receiving component |
| --- | --- | --- |
| An offer is a dated accommodation quote | Domain definition | C1 requirements and S |
| This offer accommodates four | Instance assertion | C2, with identity, context, source, and assertion status |
| Company selections must be refundable | Business policy | Requirement record, required S fields, F checker, and C4 guard when mandatory |
| My budget for this request is USD 420 | Task constraint | C4 arguments; no global change if already supported |
| Prefer downtown | Soft preference | Scoped ranking or guidance |
| The API total includes fees | Source interpretation correction | Versioned source policy and affected C2 projections |

A user policy is not a provider fact. For example, “select refundable offers” does not mean that every offer is refundable. Human assertions retain their source status. They cannot silently replace conflicting provider observations.

Record the original statement. Show the proposed interpretation. Include scope, hard/advisory mode, thresholds, units, exceptions, precedence, effective period, required evidence, and missing-evidence behavior. Ask about ambiguity that can change the result. Do not turn a task-specific constraint into a global rule without evidence of that intent.

## Report requirement coverage

Report each state separately:

| State | Required evidence |
| --- | --- |
| Meaning represented | Definitions, scope, and fields exist in the candidate schema or policy |
| Evidence available | Permitted sources supply usable values for the named records and context |
| Check implemented | A versioned function evaluates the requirement |
| Behavior verified | Independent examples and declared regression cases have recorded results |
| Enforcement bound | Each protected path in the declared scope invokes the required check |

Report OWL checks separately. Identify requirements with logical encodings and requirements with runtime computations. Do not combine these states into one coverage label. The paper's hotel example required a function repair after a schema repair. A field alone was insufficient. [OaK section 4.6](https://arxiv.org/html/2608.22974v1).

Each coverage report must name its population, snapshot, numerator, denominator, and unknown items. Populations can include registered requirements, eligible records, source fields, protected paths, or assigned cases. For a zero denominator, report `not_applicable` with a reason. Do not report 100% coverage. These measurements do not describe every possible business requirement.

Use these routes for gaps:

- If raw responses contain an ignored value, propose the required schema or extractor change. Then reproject those observations.
- If G contains the value but F ignores it, repair F.
- If a supported value has not been observed, identify an existing retrieval tool.
- If no permitted source supplies the value, report an unsupported evidence requirement.
- If sources conflict, are stale, or lack reliable identity, preserve the unresolved state and source references.

An API contract describes possible fields. It does not establish complete values for every record. Missing evidence cannot satisfy a requirement.

## Edit and promotion procedure

```text
capture EditRequest against an exact base package
C1.Analyze in analysis-only mode proposes InterpretedRequirement
resolve consequential ambiguity with the user
coordinator computes ChangePlan and downstream invalidation
owning components build an isolated candidate
run the declared verification plan
present exact diff, check results, evidence gaps, and expected changes
user activates that reviewed candidate and report
atomically promote only if the active base is still the reviewed base
record PromotionReceipt and preserve all previous artifacts
```

The interface states are Draft, Needs clarification, Proposal ready, Building, Verifying, Blocked, Ready for review, Active, and Superseded. A content or dependency change invalidates the associated verification. Return the draft to the appropriate earlier state. Discussion alone cannot make a candidate Active.

| Artifact | Required content |
| --- | --- |
| EditRequest | Original text, actor/source, discussion references, exact base package, requested scope, and timing |
| InterpretedRequirement | Stable rule ID, meaning, classification, conditions, units, exceptions, hard/advisory mode, applicability, and unknown behavior |
| ChangePlan | Differences, affected S/F/source/runtime dependencies, evidence needs, rebuild schedule, guard bindings, and verification plan |
| CandidatePackage | Base hash, ChangePlan hash, requirement-set hash, exact rebuilt dependencies, and validation receipts |
| VerificationReport | Base/candidate hashes, test/evaluator versions, assigned cases, intended changes, regressions, missing checks, coverage, and cost |
| PromotionRequest | Reviewed candidate/report hashes, approval reference, target scope, timing, active-run handling, and rollback target |
| PromotionReceipt | Previous/current package IDs, atomic outcome, effective scope, and effective time |

The coordinator routes schema work to C1, graph projections to C2, functions to C3, trials to C4, and independent evaluation to C5. Source and runtime changes retain separate dependency versions. Human proposals use `origin=human_requirement`. Do not label them as diagnoses of failures that did not occur.

## Checks before activation

| Check | Required result |
| --- | --- |
| Intent and scope | The interpretation is reviewable; consequential ambiguity is resolved |
| OWL/HermiT | Encoding coverage, consistency, and named-domain-class satisfiability are recorded; unsupported axioms remain visible |
| Data and extraction | Values have permitted source references, units, identity, time, and missing/conflict handling |
| Function behavior | Procedures return independent expected results, including boundary and unknown cases |
| Enforcement | Guards cover declared protected paths and reject bypass attempts |
| Regression | Declared unaffected cases retain required behavior; intended changes are recorded separately |

HermiT does not verify arbitrary calculations, required field presence, source truth, or API effects. Some requirements need F or an execution policy. A skipped or inapplicable encoding does not establish logical verification. [OaK Appendix A; section 3.2, Step 1](https://arxiv.org/html/2608.22974v1), [W3C OWL 2 Primer](https://www.w3.org/TR/owl2-primer/).

Each check reports passed, failed, not run, unsupported, or indeterminate. Include scope and evidence. Mark an inapplicable check explicitly and give the reason. A timeout or unsupported check cannot count as passed.

Regression cases must include valid behavior, violations, equality boundaries, missing facts, exceptions, and unaffected controls. Compare base and candidate against the same source snapshots and declared settings. Preserve old results. Register intended changes before inspecting candidate outcomes. A stricter policy can intentionally reject an earlier acceptable result.

For model-backed comparisons, declare repetitions and acceptance criteria. Do not require identical stochastic outputs. Report only the observed regressions in assigned cases. Show missing coverage.

Starting verification requires an explicit action with a displayed mode and budget. The default path uses saved evidence and fixtures. It performs no real external writes. Model-assisted or live-source checks require a separately admitted execution configuration. Typing a requirement does not start a benchmark or paid model run.

## Mandatory rules and native tools

In `optional_functions` mode, the agent can call native tools without F. A represented requirement is not necessarily enforced. `guarded_requirements` is a separate C4 execution mode.

Before a protected action or final selection, the host invokes the required check independently of agent choice. Final selections use a typed completion contract that identifies selected records and claims. Evidence-gathering reads and explanatory conversation can continue while a selection lacks evidence.

The guard binds the package, rule set, operation arguments or typed result, graph revision, applicability, and evidence freshness. A passing `ConstraintCheckReceipt` records these bindings. Changed arguments, expired evidence, a changed relevant revision, or an incompatible rule version invalidate receipt reuse.

Unknown applicability or required evidence returns `needs_evidence` or an unresolved outcome. It does not authorize the operation. A false condition rejects the operation. Do not label a hard rule enforced while an applicable path lacks a guard. The user can retain a draft or explicitly choose an advisory rule. Do not silently weaken a hard rule.

Use native implementations through host dispatch and finalization hooks. F does not acquire direct task-provider access. The guard is an additional execution-policy intervention. OWL does not supply it. [OaK sections 3.1 to 3.3](https://arxiv.org/html/2608.22974v1).

A successful check applies to the checked evidence. External conditions can change before execution. Use provider-supported conditions and effect reconciliation where required.

## Version isolation and recovery

Activation uses compare-and-swap against the reviewed base. Concurrent drafts are permitted. A stale candidate requires a new base, rebuild, and verification. Approval applies to exact candidate, report, and scope hashes. It does not apply to changed content.

Normal activation applies to new tasks. Active tasks retain their original package, policy, and graph interpretation. Show which runs retain the old version. Immediate changes require an explicit suspend/restart plan.

For immediate activation:

1. Stop admission of new covered operations with a dispatch barrier.
2. Invalidate queued check receipts from the old execution generation.
3. List calls that have already been dispatched.
4. Drain or reconcile those calls using supported provider behavior.
5. Activate the checked package when the transition conditions hold.
6. Restart affected runs under the new execution generation.

At dispatch, atomically verify the barrier and execution generation. An old receipt cannot authorize dispatch after the cutoff. Already-dispatched effects can still complete. Show these calls and unresolved outcomes. If immediate transition is unavailable, retain the barrier or report unsupported timing.

Held-out runs retain the frozen package. A change based on a held-out case belongs to a later package. That case becomes development evidence for the later package. It is no longer untouched evaluation evidence for that version. [OaK section 3.3](https://arxiv.org/html/2608.22974v1).

Rollback promotes a compatible older package for future tasks. Current tool contracts and mandatory requirements must still hold. Preserve raw observations and required versioned projections. Rollback does not reverse provider effects or remove failed checks and traces.

## Example: missing cancellation terms

A user adds a requirement to the synthetic selection task: “Only recommend offers with a full refund until 24 hours before check-in.”

Clarify the timezone, cutoff, scope, and exceptions.

The fixture contains occupancy, minimum stay, price, and availability. It contains no cancellation terms. The workspace must show this evidence gap. Adding a concept or checker cannot supply missing terms. A HermiT pass does not make an offer refundable.

If saved responses contain cancellation terms, C2 can reproject them after the required changes. Otherwise, identify or add a permitted source. Until evidence is available, keep the gap visible. Blocking unverifiable recommendations does not establish that the task can be completed.

The review must show intended outcome changes and constraints that must remain unchanged. It must identify missing source data. This process captures omitted business meaning without inventing facts.

## Independent verification contract

Test the workspace with saved packages, requests, check reports, and an in-memory active-version store. Replace C1 to C5 with declared response fixtures. Record fixture hashes and substitute versions. Do not start those components during this boundary test.

The workspace can write drafts, review records, and promotion requests. Only the coordinator can update the active-package pointer. It must not edit S, G, F, observations, or provider state directly. Compare artifact hashes and operation logs before and after every test.

| Test | Fault or action | Exact expected result |
| --- | --- | --- |
| KW-T1 | Submit and discard a draft | Active pointer and existing artifact hashes remain unchanged |
| KW-T2 | Omit cancellation evidence | Evidence state remains incomplete; no satisfied coverage item appears |
| KW-T3 | Change candidate bytes after approval | Promotion fails; active pointer remains unchanged |
| KW-T4 | Promote two candidates from one base | At most one succeeds; the other receives a stale-base result |
| KW-T5 | Mark a check timed out | Report retains a non-pass status; no ready label depends on that check |
| KW-T6 | Omit a required guard path | Enforcement remains incomplete; hard-rule activation cannot claim enforcement |
| KW-T7 | Dispatch with an old receipt after the barrier | Dispatch count is zero for that attempt |
| KW-T8 | Roll back with an incompatible tool contract | Promotion fails; prior observations and traces remain unchanged |
| KW-T9 | Change an intended outcome after seeing results | Report records a new plan/version; old results remain unchanged |

For each test, save the input, expected result, actual result, state difference, and operation log. Report passed tests over all assigned tests. Include failures, timeouts, and unrun tests in the assignment inventory. These tests are specified, not executed.

## Acceptance and implementation records

- KW1: Discussion leaves the active package unchanged and preserves the original statement and interpretation.
- KW2: Each requirement has separate meaning, evidence, implementation, verification, and enforcement states.
- KW3: Missing values and unsupported checks cannot produce successful coverage labels.
- KW4: Each ChangePlan identifies affected consumers and dependencies.
- KW5: Verification preserves failures and separates intended changes from regressions.
- KW6: Every declared protected path applies mandatory guards, even when the agent skips F.
- KW7: Exact approval hashes and atomic base checks prevent stale promotion.
- KW8: Active runs retain pinned versions; rollback retains compatibility and history.
- KW9: A user can inspect a failure and choose a relevant action without editing code.
- KW10: Each release links requirements to implementation, check receipts, and known deviations.

Map each requirement to a named test and receipt. A missing receipt means unverified behavior. A document change requires a new design version. These contracts support debugging; they do not prove that future software is error-free.
