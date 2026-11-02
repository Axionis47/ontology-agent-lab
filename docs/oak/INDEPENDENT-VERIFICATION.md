# Independent component and integration verification

Design version 0.3.0. November 2, 2026.

## Purpose and present status

A complete workflow can hide the component that caused a wrong result. Test each component from saved inputs first. Then test the connections between components.

This document defines proposed tests. It does not implement a test runner, component, adapter, or evaluator. All runtime cases below have status `not_run`.

The [review receipt](../OAK-PRD-REVIEW-0.3.md) records document checks only. Installation probes remain separate evidence in [setup](../OAK-SETUP.md).

## Test levels

| Level | Dependencies | What a pass establishes | What remains unresolved |
| --- | --- | --- | --- |
| Isolated component | Saved input and declared substitutes | Behavior against the specified contract and fixture | Real service and host behavior |
| Service connection | One component and its actual required service | Tested service behavior and version compatibility | Complete task correctness |
| Integration | Actual component boundaries with controlled fault inputs | Tested ordering, ownership, and failure propagation | General task benefit |
| Task evaluation | Frozen package and registered task population | Measured task outcome under the declared comparison | Other populations and undeclared mechanisms |

Independent operation does not mean zero dependencies. C2 needs a graph interface. C1 needs a reasoner interface. C3 needs an operator interface. Declare each interface explicitly.

A component test must not import a predecessor's mutable working state. Supply its saved public output instead. Only the owning component may change its artifacts.

## Saved test package

Each test package must contain:

- Test ID, requirement ID, and responsible component.
- Input artifact versions, hashes, and allowed scope.
- Expected output fields and independently authored expected values.
- Initial persistent state and permitted changes.
- Dependency implementations or substitute versions.
- Model response recordings, where applicable.
- Clock, identifier source, response order, and random configuration.
- Injected failure and expected diagnostic owner.
- Resource limits and expected operation counts.
- Comparison rules and permitted metadata normalization.

Keep expected results separate from production functions. A validator must not derive its expected answer through the same function under test.

Recorded-response replay uses fixed provider responses. Fresh model execution tests a different condition. Identical fresh model outputs are not a required invariant.

Fail an isolated test if it makes an undeclared network call. A saved external response is evidence of fixture behavior only.

## Component boundaries

| Component | Saved entry input | Declared dependencies | Required independent observation |
| --- | --- | --- | --- |
| C1 | SchemaBuildRequest and source requirements | Model responses, OWL encoder, reasoner | Exact schema result, coverage, and logical diagnostics |
| C2 | IngestRequest, schema, observations, prior graph revision | Extractor responses and graph store | Committed assertions, source links, revision, and receipt |
| C3 | ComposeRequest, schema, graph references, operator catalog | Composer responses, graph reader, operators | Plan, contracts, independent fixture results, and operation trace |
| C4 | ExecuteRequest, package, initial state, native tools | Host adapter, C2 interface, function runtime | Call order, task scope, guards, effects, and TrialRecord |
| C5 | EvaluateRequest with assignments, trial records, and evaluator specification | Independent expected answers or effect reader | Complete assignment accounting, scores, diagnostics, and targeted RepairPlan |

Use exact component request names from each component specification when implementing the transport. This table describes their content; it does not supply executable Pydantic models.

The workspace, visibility layer, and host adapter also require isolated tests. Their local test tables define additional cases.

## Integration fault cases

Every row is a proposed test, not a passing result. Save the exact assigned case list before execution.

| ID | Owner | Input or injected failure | Required result and measurable invariant |
| --- | --- | --- | --- |
| IV-01 | Coordinator and receiver | Change one required artifact hash or contract version | Reject before dependent work; zero dependent operator/provider calls |
| IV-02 | C1 | Verify one contradictory candidate with repair disabled | Report logical failure; zero ready schemas and zero dependent trial dispatches |
| IV-03 | C2 | Commit an observation, lose the acknowledgement, then replay it | Return the original receipt/revision; zero extra assertions and zero extra revisions |
| IV-04 | C2 | Reuse an observation identity with different payload bytes | Report identity conflict; zero graph changes |
| IV-05 | C2 | Race two distinct observations with the same expected parent | Exactly one succeeds at that parent; the other reports a stale parent without partial writes |
| IV-06 | C2 and C4 | Deliver ingest acknowledgements out of order | Zero backward revision moves; zero F calls before required observations exist in the selected revision |
| IV-07 | C3 and function runtime | Supply a missing required property, then a conflict unresolved under the pinned policy | Preserve unknown/conflict diagnostics; zero unsupported successful candidates |
| IV-08 | Function runtime | Commit g2 while F reads pinned g1 | Every operation in that invocation reads g1; output identifies g1 |
| IV-09 | C4 and host | Invoke F while an operator times out | Preserve invocation-to-attempt-to-operator error chain; zero success-shaped replacement results |
| IV-10 | C4 | Provider performs a write, but its response is lost | Record uncertain effect; zero blind repeated writes; reconcile through supported provider evidence |
| IV-11 | Coordinator | Crash with one reserved call remaining; redeliver its completion after resume | One reservation reconciliation; zero duplicate debit; zero dispatch after exhaustion; unchanged deadline |
| IV-12 | C5 | Duplicate one assignment record and omit another | Reject duplicate matching; expose the missing assignment; retain the registered denominator |
| IV-13 | C5 | Return a wrong final selection after successful OWL and function execution | Independent task score is incorrect; successful local checks cannot override it |
| IV-14 | Input, C1 to C4 | Request evaluator-only expected answers | Deny access; zero expected-answer payloads in agent inputs or traces |
| IV-15 | Coordinator and C3 | Repair a schema property that an existing F depends on | Mark affected F unusable; zero dispatch through F before required validation |
| IV-16 | Coordinator | Attempt a schema, function, or dependency edit during held-out execution | Reject mutation; all pinned hashes unchanged; defect retained for a later package |
| IV-17 | Host adapter | Fail a registration after one F binding is staged | Zero active partial bindings; original tools and context unchanged |
| IV-18 | Host adapter and C4 | Deliver another task's result, then a callback after closure | Zero cross-task changes or reopened F dispatches; closed-task evidence changes require the original authorized recovery path |
| IV-19 | C4 guard | Omit required evidence or bypass a declared protected route | Block the protected operation; zero external dispatches through that route |
| IV-20 | Workspace | Change the active base or reviewed report hash before promotion | Reject activation; active package unchanged |
| IV-21 | Visibility layer | Combine a function result from g1 with values from g2 | Refuse a combined verified view; display the incompatible references |
| IV-22 | C4 and host | Replace the host with a recording substitute | Use only declared hooks; zero replacement model loops and zero host-owned configuration writes |

For IV-10, first use a recording provider substitute. An actual provider test needs a separately authorized, reversible operation.

For IV-14, the published synthetic evaluator file is not private benchmark data. Use a separate access-controlled test artifact to verify denial. A directory name alone provides no access control.

For IV-19, enumerate all declared protected routes before the test. A passing test on one route does not prove complete coverage.

## Assignment and result records

An assignment identifies study/run, case, condition, and repetition. Its key must be unique. Expected assignments come from the registered manifest, not from returned results.

Each assignment must have one terminal outcome. Missing records remain visible. Duplicate or unexpected records cause a matching error; they cannot silently replace another outcome.

Separate these fields:

| Field | Values or requirement |
| --- | --- |
| Test execution state | `not_run`, `passed`, `failed`, or `blocked` |
| Component status | Shared transport status plus component detail state |
| Task outcome | Independent score or explicit unavailable score |
| Actual output | Artifact reference and hash |
| State difference | Permitted and unexpected changes |
| Observed operations | Counts by agent call, operator, provider, Cypher, and storage operation |
| Error | Owner, stage, code, causal IDs, and retry policy |
| Timing | Start, end, elapsed time, and deadline |
| Usage | Provider-reported token categories and explicit unknown values |
| Evidence | Input, output, trace, and effect receipt references |

Do not combine task success with infrastructure status. A failed task can have a complete, valid execution record.

## Measurements and release criteria

Report raw counts with every rate. Count blocked and unrun cases separately; they cannot count as passes.

| Measure | Numerator | Denominator | Proposed release requirement |
| --- | --- | --- | --- |
| Test completion | Cases with an executed terminal result | All assigned required cases | Every required case executed |
| Contract pass rate | Cases that satisfy every declared expectation | All assigned required cases | Every required case passes |
| Fault detection | Injected faults that produce the expected rejection and diagnostic | All assigned fault cases | Every required fault detected |
| Causal trace coverage | Executed boundary calls with complete required references | All executed boundary calls | Complete coverage |
| Guard-route coverage | Declared routes with passing positive and negative cases | All declared protected routes | Complete coverage in guarded mode |
| Forbidden side effects | Observed changes outside permitted writes | All executed attempts | Zero forbidden changes |
| Duplicate effects | Extra effects after replay/resume | All assigned replay/resume cases | Zero extra effects |

At denominator zero, report `not_applicable` or `not_run` with its reason. Never report 100% for an empty test set.

For local fixed fixtures, report exact counts. Do not infer population accuracy or a confidence interval from exhaustive fixture checks.

Record latency for each test. Set performance limits before performance acceptance runs. No latency or cost target is selected by this document.

All runtime results are currently `not_run`. The 22 IV cases are a proposed inventory. Their runtime pass rate is unmeasured, not zero and not 100%.

## Debug procedure

1. Find the earliest boundary whose actual result differs from its expected result.
2. Open its input, output, and dependency hashes.
3. Follow its parent call and nested operation IDs.
4. Compare the permitted writes with the actual state difference.
5. Replay that component with recorded dependency responses.
6. Classify the defect as contract, logic, source, service, ordering, or resource failure.
7. Repair only the owning component or versioned contract.
8. Repeat the failed isolated test.
9. Repeat affected integration tests and regression cases.
10. Preserve the original failure receipt.

An early failure locates the first observed divergence. It does not prove the ultimate cause. Independent expected answers and dependency tests must support the diagnosis.

## Full demonstration gate

After the required component and integration tests pass, run the declared development demonstration. Preserve each C1-to-C5 artifact and its version.

Show one failed domain decision, a targeted repair, the affected rebuild, and a frozen query with fresh observations. Keep held-out cases out of repair.

A correct teaching demonstration still does not establish agent benefit. That claim needs the [PRD measurement protocol](../OAK-PRD.md).
