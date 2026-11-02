# C5: Evaluator and refiner

Design version 0.3.0. November 2, 2026. This component is proposed. It is not implemented.

A schema can pass HermiT while the agent completes the wrong task. A function can execute successfully and still give a wrong result.

C5 evaluates the observed task outcome. During development, it also proposes specific repairs. It owns scoring and diagnosis. It cannot edit another component's artifacts or decide deployment.

The [integration specification](INTEGRATION.md) defines repair routing and promotion. [C4](04-task-executor.md) supplies trial records.

The paper separates `scores = Eval(trajectories)` from `feedback = Judge(S, G, F, trajectories, scores)`. Eval uses the dataset protocol. Judge proposes changes from artifacts, execution, and scores. [OaK section 3.2, Step 4](https://arxiv.org/html/2608.22974v1#S3.SS2).

A favorable diagnosis cannot replace a failed outcome score.

## Source requirements and design choices

| Topic | Paper requirement | Open detail | Proposed implementation |
| --- | --- | --- | --- |
| Scoring | Apply the dataset evaluation protocol before repair diagnosis. [Sections 3.2 and 4.1](https://arxiv.org/html/2608.22974v1#S4.SS1) | Evaluator for the unselected live API | Register independent expected answers or effect checks before execution |
| Judge inputs | S, G, F, trajectories, and scores. [Step 4](https://arxiv.org/html/2608.22974v1#S3.SS2) | Prompt, evidence selection, output contract | Version prompts, record selected evidence, and validate typed proposals |
| Repair form | Target, add/delete/modify action, proposed change, and reason. [Step 4](https://arxiv.org/html/2608.22974v1#S3.SS2) | Stale patches and dependencies | Exact artifact hashes and declared invalidation requirements |
| Routing | Schema feedback returns to construction; function feedback returns to composition. [Step 4](https://arxiv.org/html/2608.22974v1#S3.SS2) | Ingestion, adapter, and infrastructure repairs | Separate engineering defect records |
| Stopping | Stop with no blocking fault or at the iteration limit. Freeze S/F for unseen cases. [Sections 3.2 and 3.3](https://arxiv.org/html/2608.22974v1#S3.SS3) | Release policy and scoring failures | The coordinator controls stopping and promotion. Held-out evaluation produces no actionable repair plan. |

The [PRD](../OAK-PRD.md) defines the wider requirements. These contracts do not guarantee correct diagnosis or convergence.

## Inputs

Use the shared envelope for terminal status and invocation identifiers. Component detail states belong in `component_status`. Task outcomes remain separate. A completed evaluation can use `status: succeeded` while reporting task failure. An evaluator execution failure uses `status: failed`.

An `EvaluateRequest` contains:

- The shared envelope and mode.
- Assigned case IDs, condition IDs, repetition IDs, and assignment IDs.
- TrialRecords and the exact candidate or frozen package reference.
- S/F references and graph revisions.
- An `EvaluationSpec` and diagnostic access policy.
- Judge configuration and budget.

Each assignment ID identifies one case, condition, and repetition. Validate uniqueness before scoring. Repeated runs of a case remain separate assignments, but stay grouped for uncertainty estimation.

A missing TrialRecord remains an assigned incomplete outcome. Do not remove it from the denominator. Reject duplicate or conflicting records for one assignment. Preserve them for diagnosis without double counting.

The `EvaluationSpec` defines the population, completion criteria, constraint checks, evaluator version, and treatment of indeterminate outcomes. It also identifies independent expected answers or effect evidence.

Private answers stay behind the evaluator boundary. Development diagnostics can identify violated requirements. They must not become C2 world facts or held-out agent context.

## Outputs

An `Assessment` records each assignment's:

- Score state, task outcome, and constraint results.
- Supporting evidence and evaluator version.
- Resource references and scorer failures.

Keep task failure, missing evidence, and evaluator failure distinct. A scorer error cannot become success or an excluded assignment.

Construction mode can also return a `RepairPlan`. Each proposal records:

- Target kind, ID, and exact artifact hash.
- Add, delete, or modify operation.
- Proposed definition or patch.
- Diagnosed reason and supporting trace references.
- Downstream invalidation requirements.

Related schema and function repairs can form one group. Rebuild the schema before validating its dependent functions.

The coordinator routes accepted proposals to C1 or C3. It assembles a validated candidate and schedules new trials. A proposal itself changes no artifact.

## Internal procedure

The paper permits repairs to entity types, relation types, and functions. It separates schema feedback from function feedback for the next round. [OaK section 3.2, Step 4](https://arxiv.org/html/2608.22974v1#S3.SS2).

This proposed procedure adds explicit failure handling and held-out isolation:

```text
validate mode, assignment identities, trial records, package, and evaluator version
reject duplicate or conflicting records for one assignment
for every assigned case/condition/repetition:
    retain missing trial records as incomplete assigned outcomes
    score available outcomes using the registered independent evaluator
    retain task failures, timeouts, missing evidence, and scorer errors
persist Assessment with the exact evidence used
if mode is held_out:
    return Assessment and non-actionable defect records
if scoring is incomplete:
    return Assessment with evaluation failure; do not claim a ready repair round
collect permitted development artifacts, graph revisions, traces, and scores
repeat within the judge budget:
    proposals = Judge(S, G, F, trials, scores)
    validate structure, targets, versions, evidence links, and allowed operations
    separate ontology/function proposals from engineering defects
    if output checks pass:
        return Assessment, RepairPlan, and engineering defect records
    retain diagnostics and retry malformed or invalid proposals
return Assessment and explicit diagnosis failure with all attempts
```

Eval must not use generated F as its sole correctness oracle. F outputs describe what happened. The registered evaluation specification defines expected behavior. Otherwise, the same mistake could generate and certify the result.

Judge inspects observable inputs, operations, outputs, and scores. It does not require hidden reasoning text.

Separate an observed failure from a hypothesis about its cause. A source reference supports inspection; it does not prove a causal explanation.

## Repair ownership

Schema proposals go to C1. C1 rebuilds and verifies S. The coordinator invalidates affected graph projections and functions before further execution.

Function proposals go to C3. C3 regenerates or validates F under the current schema. Raw observations remain unchanged.

Extraction errors, wrong unit mappings, provider changes, and faulty scorers are engineering defects. C5 can identify evidence and suspected dependencies. It cannot disguise those corrections as schema or function patches.

Each engineering correction receives a new version. Reproject or reassess affected records as required. Preserve earlier assessments as historical records.

Reject stale proposals. If the target changed, obtain a diagnosis against the current candidate. A failed patch must not overwrite the preceding viable artifact.

The paper's hotel case required schema and function repairs. [OaK section 4.6](https://arxiv.org/html/2608.22974v1#S4.SS6). This supports inspecting both definitions and their consumers. Tests must also cover faulty observations, task interpretation, and final actions.

## Development and held-out modes

Development trials supply feedback for later artifact versions. Model weights stay fixed. Each accepted repair creates a candidate with visible differences and new validation.

A judge reporting no blocking fault can satisfy a declared stopping condition. It does not prove universal correctness.

Held-out evaluation records scores and defects only. It cannot issue an actionable `RepairPlan`, invoke C1/C3, or modify the frozen package. [OaK section 3.3](https://arxiv.org/html/2608.22974v1#S3.SS3).

A later improvement requires a new package and evaluation cycle. The coordinator owns iteration budgets and promotion.

Budget exhaustion can leave unresolved failures. The declared protocol may retain a technically valid candidate for evaluation. Exhaustion does not convert failed checks into successful checks.

## Failures

Judge formatting retries consume C5's shared budget. They must not alter saved scores.

Evaluator errors require explicit handling. Do not ask the judge to replace an error with a favorable judgment. Preserve each attempt, settings, elapsed time, and usage.

## Independent verification

These are required tests, not completed results. Use the [verification protocol](INDEPENDENT-VERIFICATION.md).

Supply saved TrialRecords, assignments, package references, and an EvaluationSpec. Use an independent fixture evaluator and a recorded judge-response stub. C1 through C4 do not run. No external write is permitted.

| Test input or injected fault | Expected output | Measurable pass condition |
| --- | --- | --- |
| Saved valid trial | Assessment from stored evidence | Zero agent reruns and zero external writes |
| Wrong answer with successful HermiT and function checks | Task failure | Independent expected result rejects the answer |
| Missing trial or timeout | Incomplete or failed assigned outcome | Assessment count equals assigned count |
| Duplicate or conflicting assignment records | Explicit validation failure | No double counting and no silent record selection |
| Evaluator exception | Scorer failure | No success score or dropped assignment |
| Unsupported target, stale hash, or missing trace reference | Rejected proposal | No accepted patch for the invalid target |
| Schema repair proposal | Declared graph/function invalidation | Required dependency references are present |
| Function repair proposal | Function-only change request | Original observation hashes stay fixed |
| Wrong mapping or faulty scorer | Engineering defect record | No hidden mapping or evaluator edit in a C1/C3 patch |
| Held-out request | Assessment and non-actionable defects | Zero actionable repairs and unchanged package hashes |
| Private answer marker in evaluator fixture | No marker in diagnostic exports | Zero private-answer occurrences in graph or agent payloads |

C5 may write assessments, proposals, diagnostics, and receipts. It cannot mutate the active package.

Recorded judge responses permit deterministic replay. Fresh model diagnoses can differ. Stubbed judges test proposal validation, not diagnosis quality.

Outcome reports separate complete success from partial constraint satisfaction. Preserve paired assignments, uncertainty, regressions, and costs for every model role.

The first API or benchmark, evaluator, model settings, and budget remain unselected. No live task pilot is authorized by this document.
