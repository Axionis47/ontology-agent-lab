# OaK design review, version 0.3.0

Date: November 2, 2026.

## Scope

The user requested ASD-STE100 writing principles and independent components with measurable integration checks. The confirmed scope is OaK design documents only.

This revision changes 12 existing design documents. It adds the [writing guide](oak/WRITING-GUIDE.md) and [independent verification specification](oak/INDEPENDENT-VERIFICATION.md).

The shared research narrative records the changed design. Source papers, historical reviews, experiment results, setup evidence, runtime code, and example data remain unchanged.

This receipt records document revision only. Repository publication is a separate operation.

## Corrections to the proposed design

| Finding | Correction | Required verification |
| --- | --- | --- |
| C4 and host both appeared to own the agent loop | Host owns the loop; C4 owns the adapter protocol | IV-22 records calls through declared host hooks |
| Replay did not define payload collisions or lost acknowledgements fully | Scoped replay key, immutable payload digest, and atomic graph/receipt commit | IV-03 to IV-05 verify replay, collisions, and concurrent commits |
| Async ingestion lacked an explicit dependency requirement | Each dependent F call names required observations or a watermark | IV-06 and IV-08 verify order and stable reads |
| Shared failures lacked exact causal records | Invocation, attempt, parent, operation, and assignment IDs identify each boundary | IV-09 requires the nested failure chain |
| Budget ownership lacked a restart protocol | Durable reservations, single reconciliation, and persistent deadlines | IV-11 verifies restart and redelivery |
| Assignment matching could hide missing or duplicate trials | Match unique registered assignments before scoring | IV-12 preserves the denominator and exposes matching errors |
| Partial host registration lacked cleanup requirements | Isolate or remove failed-mount additions before ready admission | IV-17 and HA-T2 verify residual state |
| Inspection could combine incompatible artifact versions | Bind views to one compatible package, context, and graph revision | IV-21 refuses an unsupported combined verified view |

These are document findings. No runtime fault was reproduced during this revision.

## Writing review

The revision uses shorter sentences, named owners, consistent terms, and separate instructions. Technical identifiers and citations retain their meanings.

Full ASD-STE100 conformity is unverified. The review did not validate the complete approved dictionary, grammatical forms, or every technical-term category.

The official sources and local rules are in the [writing guide](oak/WRITING-GUIDE.md). A prose-length scan is only a screening check.

## Document checks

The [machine-readable receipt](oak/reviews/0.3.0-document-checks.json) contains file hashes, counts, scope, and limitations.

Checks cover the 14 active design documents. They exclude this receipt, historical snapshots, and unrelated project documents.

- Resolve local Markdown file links.
- Compare external source URLs with the previous documents.
- Find em dashes and unfinished TODO/TBD/FIXME markers.
- Screen prose sentences against the 25-word ceiling.
- Screen numbered instructions against the 20-word ceiling.
- Verify that historical reviews, setup evidence, and example data remain unchanged.
- Review ownership, process status, domain outcome, and failure tests for consistency.

The sentence scan removes Markdown link destinations. It excludes headings, tables, and fenced code. Word counts are approximate whitespace counts, not formal STE counts.

Source-URL preservation does not revalidate every paper claim. The rewrite preserves existing source claims. New operational contracts are explicitly our proposed implementation requirements.

## Runtime evidence and limits

The 22 shared integration fault cases have status `not_run`. The local component and interface cases also remain unrun.

No OaK implementation, host adapter, test runner, or complete evaluator was added. No live model or benchmark execution occurred.

Document checks cannot prove logical consistency, source truth, function correctness, safe external effects, or task benefit. Those claims require the specified execution receipts.
