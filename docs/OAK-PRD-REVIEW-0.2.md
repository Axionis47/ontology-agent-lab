# OaK design review for controlled kernel editing

Version 0.2.0, November 2, 2026. Classification: proposed adaptation. This extends the [PRD](OAK-PRD.md) with the [controlled workspace](oak/06-kernel-workspace.md) and [kernel data visibility](oak/07-kernel-data-and-visibility.md). The [version 0.1.0 receipt](OAK-PRD-REVIEW.md) remains an unchanged historical record, with hashes for that earlier document state.

## Review scope and outcome

Three specialist agents reviewed source fidelity, edit/promotion contracts, and user-facing data visibility. They confirmed that the proposed interface distinguishes ontology definitions, observed graph facts, computation, and execution control. The raw synthetic values used in the visibility document were checked against the existing example files.

The main resolved design issues were:

- A business policy is not an instance fact. User instructions retain author, scope, intent, exceptions, and unknown handling.
- Adding a schema field is distinct from obtaining evidence, implementing a checker, testing it, and binding enforcement.
- The original optional-F mode cannot guarantee a mandatory business rule. The new guarded mode is a separate execution-policy adaptation.
- Exact candidate/report approval and atomic promotion preserve reviewed versions. In-progress tasks normally remain pinned.
- Immediate activation needs a dispatch barrier and execution-generation check, with already-dispatched calls drained or reconciled. Package-pointer promotion alone does not close that race.
- Intended policy changes must remain distinct from unexpected regressions. Passing named cases does not guarantee all unseen behavior.
- The hierarchy example uses real fields from synthetic source files, with proposed graph structures explicitly labeled as unimplemented.

The paper's model-judge repair loop, paired schema/function repair, and human-feedback future-work statement were checked in [OaK sections 3.2, 4.6, and 5](https://arxiv.org/html/2608.22974v1). OWL coverage limits and hierarchy semantics were checked against the [W3C OWL 2 Primer](https://www.w3.org/TR/owl2-primer/). Human editing, UI organization, promotion, and host guards are our extensions.

## Shared narrative integration

| Required question | Answer |
| --- | --- |
| Repeated work or missed decision | Business constraints can be absent from construction evidence or represented without an executable consumer. Users need to identify and inspect those gaps. No new runtime failure was measured. |
| Changed artifact | PRD 0.2.0 adds user requirements, edit/verification/promotion contracts, guarded execution mode, and hierarchy/visibility requirements. |
| Consumer | Planned consumers are C1 to C5, the coordinator, and the host guard. No new software consumer has executed these contracts. |
| Metric, denominator, costs and uncertainty | No task or usability study ran. There is no new denominator, measured effect, uncertainty estimate, or task-execution cost. |
| Alternatives and controls | Human-provided information, UI visibility, function repair, and enforcement are separate interventions. Future comparisons must declare them. |
| Shared claim | Unrun and unresolved. The documents make proposed behavior inspectable; they do not establish improved correctness, confidence, or cost. |

The existing example corpus and evaluator fixtures were not changed. Target API, evaluator implementation, model configuration, and execution budget remain unselected. No current live protection, error-free design, or complete business coverage is claimed.

## Documentation verification

Checked local references, code fences, embedded JSON, placeholders, and the no-em-dash preference. Reviewed cross-document consistency of `optional_functions` versus `guarded_requirements`, version pinning, protected finalization, unknown applicability, and activation behavior. The new visibility table matches the o3 values and context in the synthetic observation files.

These are document checks. No UI, guard, model experiment, ontology extraction, regression suite, or provider action was implemented or run. Requirements KW1 to KW10 specify future conformance evidence; they do not claim that such evidence already exists.

## Narrative and unchanged registers

| State | SHA 256 |
| --- | --- |
| Narrative before update | `eb7b52ef8a8712b33f4902585f894140d6693d0e57dee4baf3958ecc315af57f` |
| Narrative after update | `879810b9bccda88fd20de324996d0ce242d5d8898d2b6883e39da01f115e8ffe` |
| Shared schema unchanged | `a82358e8d42600685bda833efdcaf8728f31a9d3097efbfc71c9ee79bc2de6b8` |
| Study register unchanged | `6e4a165cdbc295c83d5c1ac0a78ae68fffa1a81f8fa5668b8d87d989de5f6963` |
| Claim register unchanged | `b376ce38fbc18a92773778c59da4dcd26f16c1b91f38529cf006d281b1cccdef` |

The narrative hash was checked immediately before the scoped edit. No outcome/claim records were added. The proposal remains associated with `oak-refinement`; metric mappings and assigned cases require registration before execution.

## Artifact versions

| File | Before SHA 256 | After SHA 256 |
| --- | --- | --- |
| `docs/OAK-PRD.md` | `5af7ff9554da96a31b9911bab5f7ee21e37042dbfd4379e90474e4a88d501a79` | `dbafca8931f7e309c9a7851551a22ce6ab9eac0ea2e97df35060cb2eaaa41b67` |
| `docs/oak/00-task-surface-and-corpus.md` | `3c45b69de3ad8c74db25c798b4a255ac1dda00f1e05e5cdbbe303035189b2e05` | `05be57d31d8e0e6a5b8844a20becd817e88e42c5da76d4468fad99dcee693757` |
| `docs/oak/04-task-executor.md` | `5a6b65fe091dea5b0a95dc6b34e750c7a9ab37a809010e844aa110a03927e6f0` | `64a835364464735b5b694ad301e1d7dfb2b04a34901826aa2237fedc7f7fa04b` |
| `docs/oak/INTEGRATION.md` | `bcc9350dcd97505d77adb216a0a54ef66a3c8aeed5e0c2d55b4c2b220e2186cf` | `ad934a1af9a665463aab39f00ef1fb7cd16a24d92ce538affe4a5ab0e4395311` |
| `docs/oak/06-kernel-workspace.md` | `new file` | `61a930ecf0951d3fd788759a6d3120f26626da1bb514dd8227d70c12641851b8` |
| `docs/oak/07-kernel-data-and-visibility.md` | `new file` | `b05e35aed7da4dc54db3528a2ce655ddc752bb88b8d787bc79a2d7d13cab587d` |
