# Visibility Policy for Compounding Knowledge

Version: 1. Date: 2026-10-16. Scope: walkthroughs and any later implementations of the five mechanisms in this collection. This is our learning and evidence policy, not a claim about what every cited paper exposes. It supplements the repository's [required visible experiment record](../../evidence/README.md) and [experiment documentation policy](../../evidence/README.md). Existing experiment protocols and gates remain binding.

The learner must be able to follow what the system knew, which evidence arrived, what change was proposed, what actually changed, and what happened when that knowledge was available to a later task. A readable summary must link to inspectable evidence. Documentation alone does not establish that this policy is enforced by software.

## Three levels of visibility

1. **Walkthrough view:** show the task, relevant evidence, knowledge before, proposed change, actual change, later use, and evaluation in execution order. Keep the explanation short enough to follow one case.
2. **Inspection view:** expose the exact permitted source excerpts, model-visible requests and responses, retrieval results, versioned differences, tool arguments, validation results, and effect receipts behind that explanation.
3. **Restricted audit view:** preserve authorized operational records needed for reconstruction, with access controls, redaction, and retention. Sensitive evidence must not become visible to another user or tenant through a trace or summary.

Capture observable actions and brief evidence-backed explanations. Do not request or record hidden chain-of-thought. A model's explanation is a claim to inspect, not proof of why an outcome occurred.

## Evidence required for each case

| Boundary | What must be inspectable |
| --- | --- |
| Task | Goal, success criteria, case identity, owner, authority, and constraints. |
| New evidence | Source identity/version, relevant content, provenance, timestamp, and permission scope. Label original benchmark material, paper illustration, and our teaching example separately. |
| Knowledge before | Exact relevant fact, playbook, skill, or prompt version, with scope, validity, and source references. Reference bulky archives rather than loading them all. |
| Selection and context | Query/filters, returned candidate identities and scores when available, selected and omitted items, selection rule or stated reason, actual model-visible content, and size. Unknown or unexposed information stays explicitly unknown. |
| Proposed update | Observable operation, target identity, before/after difference, supporting source references, applicability, exceptions, and proposing actor. Include rejected, ignored, and no-change proposals. |
| Validation and authority | Checks and versions, their results, conflict findings, and permission/approval decision under the declared authority policy. Record automated and human decisions accurately. |
| Committed update | Actual saved version, checksum/reference, writer, concurrency version, operation identity, and receipt. A proposal or successful tool message alone does not establish a committed change. |
| Later execution | Exact knowledge version actually loaded, observable actions, citations where present, resulting artifacts/effects, and independent outcome checks. |
| Evaluation | Baseline/candidate identities, learning/validation/test split, rubric and grader versions, per-case outcomes, regressions, exclusions, and unresolved findings. |
| Operations | Correlated run/step/call identities, model/prompt/tool/code versions, origin classification, retries, token usage, and separate timing/cost components where available. Unknown is not zero. |

For model calls, retain `live`, `cached-live`, `replayed-live`, or `not-a-model` classification; provider; requested and resolved model when available; prompt version; and call identity. Only eligible live measurements support model-quality, variance, latency, or cost conclusions.

## Evidence specific to the five mechanisms

1. **Fact maintenance, Mem0 and Zep:** show old and new claims, add/update/delete/ignore decisions, entity resolution, source support, and temporal validity. Distinguish a corrected error from a claim that was valid historically. Distinguish retiring knowledge from deleting source data under a retention policy.
2. **Playbook updates, ACE:** show the execution feedback, proposed lesson, exact entry difference, helpful/harmful counter changes, deduplication, and the playbook loaded later. A counter increment is feedback, not established usefulness.
3. **Skill consolidation, Trace2Skill:** show the included/excluded executions, proposed patches, merge decisions, preserved exceptions, final skill version, and what was loaded or executed. Keep withheld test cases and gold labels out of skill creation and decision context. Separate skill quality from skill selection failures.
4. **Candidate optimization, GEPA:** show parent/candidate relationships, changed instructions, feedback used, selection scores and rules, and final held-out results. Preserve rejected candidates and regressions. Reusing validation results for selection does not make them untouched test evidence.
5. **Consolidation scheduling and verification, RecMem and TrustMem:** show the trigger or deferral, grouping criteria, source coverage, before/after memory, and omission/corruption/unsupported-addition findings. Separate the scheduling decision from update faithfulness. Repeated mentions are not independent confirmation. Label a small teaching adaptation separately from reproducing a trained memory updater.

## What counts as evidence of learning

Keep these claims separate: knowledge was stored; retrieved; loaded into context; referenced in an observable decision; followed by a correct outcome; and shown to improve outcomes in a fair comparison. One does not establish the next. A successful case after an update does not establish that the update caused the success.

Before claiming improvement, declare the comparison, learning boundary, success criteria, and fixed controls. Controlled experiments vary one independent variable. Use unseen cases and counterexamples, retain conclusive failures, and report missing/inconclusive/excluded counts beside aggregates. Missing visibility or a supporting failure makes the affected claim inconclusive; it is not automatically a model failure. Preserve the first observable broken contract without inventing a causal explanation.

## Worked visibility example

This is a hypothetical walkthrough, not a recorded model execution:

- **Before:** home city is Seattle, linked to the source establishing the move.
- **Incoming evidence:** the user says they are visiting Boston this week.
- **Proposal to inspect:** change home city to Boston.
- **Contract check:** the source supports a temporary visit, not a new home. Flag the proposed replacement for correction under the declared update policy.
- **Actual commit:** show the receipt and resulting records if a corrected update is saved; otherwise display pending or rejected status.
- **Later test:** distinguish a question about the user's home from a question about their location during the visit. An unanswered test stays pending.

The learner should be able to locate the first unsupported transition before seeing the final answer.

## Publication and recovery

Preserve previous versions and rejected proposals through authorized history. Corrections and rollbacks create identified records; do not rewrite original outcomes. Record retention/deletion actions without retaining prohibited sensitive content in audit copies. Failures in the visibility pipeline must themselves be visible and must block claims requiring the missing evidence.

Every walkthrough ends with what was observed, what remains uncertain, and which requirement would change the design choice. A policy document, a plausible lesson, or a larger memory store is not completion evidence.
